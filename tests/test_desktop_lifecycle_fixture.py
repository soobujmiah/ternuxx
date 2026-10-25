"""Exercise native desktop ownership using isolated mock processes on Linux."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DesktopLifecycleFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-desktop-fixture-")
        # unittest cleanups run after tearDown; register the temp directory
        # first so process-specific cleanups run before its mock executables
        # disappear.
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.tmp = self.base / "tmp"
        (self.tmp / ".X11-unix").mkdir(parents=True)
        self.bin_dir = self.base / "mock-bin"
        self.bin_dir.mkdir()

        self.lib_dir = self.base / "lib"
        shutil.copytree(ROOT / "lib", self.lib_dir)
        pulse_fixture = self.lib_dir / "pulse_lifecycle.py"
        pulse_fixture.write_text(
            "#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps({'command':'audio','state':'running','server':'tcp:127.0.0.1:4713'}))\n",
            encoding="utf-8",
        )
        pulse_fixture.chmod(0o755)
        supervisor = self.lib_dir / "desktop-supervisor.sh"
        lines = supervisor.read_text(encoding="utf-8").splitlines()
        lines[0] = "#!/usr/bin/env bash"  # Termux shebang is unavailable in Linux CI.
        supervisor.write_text("\n".join(lines) + "\n", encoding="utf-8")
        supervisor.chmod(0o755)

        self._write_executable(
            "termux-x11",
            """#!/usr/bin/env python3
import os, signal, socket, sys, time
display = sys.argv[1].lstrip(':')
path = os.path.join(os.environ['TMPDIR'], '.X11-unix', 'X' + display)
lock_path = os.path.join(os.environ['TMPDIR'], '.X' + display + '-lock')
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.bind(path)
sock.listen(1)
with open(lock_path, 'w', encoding='ascii') as lock:
    lock.write(str(os.getpid()).rjust(10) + '\\n')
def stop(_sig, _frame):
    sock.close()
    # Leave stale server artifacts so the supervisor's owner-checked cleanup
    # path is exercised by the fixture.
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
while True: time.sleep(0.1)
""",
        )
        self._write_executable(
            "dbus-launch",
            """#!/usr/bin/env python3
import os, sys
if len(sys.argv) < 3 or sys.argv[1] != "--exit-with-session":
    raise SystemExit(64)
os.execv(sys.argv[2], sys.argv[2:])
""",
        )
        self._write_executable(
            "xfce4-session",
            """#!/usr/bin/env python3
import os, time
with open(os.environ["FAKE_ENV_FILE"], "w", encoding="utf-8") as stream:
    stream.write(os.environ.get("LD_LIBRARY_PATH", "missing"))
while True:
    time.sleep(1)
""",
        )

        self.state = self.home / ".local/share/ternuxx-fixture"
        self.env = os.environ.copy()
        self.env.update(
            {
                "HOME": str(self.home),
                "TMPDIR": str(self.tmp),
                "TERMUX_VERSION": "fixture",
                "PREFIX": "/data/data/com.termux/files/usr",
                "TERNUXX_STATE_DIR": str(self.state),
                "TERNUXX_LIB_DIR": str(self.lib_dir),
                "FAKE_ENV_FILE": str(self.base / "desktop-loader-path"),
                "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            }
        )

    def tearDown(self) -> None:
        # Best-effort, scoped cleanup: ask only this fixture's session manager.
        if (self.state / "session.json").exists():
            subprocess.run(
                ["bash", str(ROOT / "bin/tx"), "stop"],
                env=self.env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # A full native suite can leave very little scheduling time
                # for fixture child shutdown on this device. Keep cleanup
                # bounded, but allow the scoped supervisor to finish normally.
                timeout=20,
                check=False,
            )

    def _write_executable(self, name: str, content: str) -> None:
        path = self.bin_dir / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def _run(self, *args: str, umask: int | None = None) -> subprocess.CompletedProcess[str]:
        configure_umask = (lambda: os.umask(umask)) if umask is not None else None
        result = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), *args],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=12,
            check=False,
            preexec_fn=configure_umask,
        )
        if result.returncode != 0:
            log = self.state / "desktop.log"
            if log.exists():
                result.stderr += "\nDESKTOP LOG:\n" + log.read_text(encoding="utf-8")
            state_file = self.state / "session.json"
            if state_file.exists():
                result.stderr += "\nSESSION STATE:\n" + state_file.read_text(encoding="utf-8")
        return result

    def _state(self) -> dict[str, object]:
        return json.loads((self.state / "session.json").read_text(encoding="utf-8"))

    def _run_activity_request(self, *, launcher_available: bool, launcher_exit: int = 0):
        prefix = self.base / "termux-prefix"
        launcher = prefix / "bin/am"
        if launcher_available:
            launcher.parent.mkdir(parents=True, exist_ok=True)
            launcher.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "with open(os.environ[\"ACTIVITY_ARGS_FILE\"], \"w\", encoding=\"utf-8\") as stream: \n"
                "    json.dump(sys.argv[1:], stream)\n"
                "raise SystemExit(int(os.environ.get(\"ACTIVITY_EXIT_CODE\", \"0\")))\n",
                encoding="utf-8",
            )
            launcher.chmod(0o755)
        env = self.env.copy()
        env.update({
            "PREFIX": str(prefix),
            "ACTIVITY_ARGS_FILE": str(self.base / "activity-args.json"),
            "ACTIVITY_EXIT_CODE": str(launcher_exit),
            "TERNUXX_QUIET": "0",
            "TERNUXX_VERBOSE": "0",
            "TERNUXX_JSON": "0",
        })
        return subprocess.run(
            ["bash", "-c", 'source "$TERNUXX_LIB_DIR/desktop.sh"; _nt_request_termux_x11_activity'],
            env=env, text=True, capture_output=True, timeout=5, check=False,
        )

    def test_x11_activity_request_uses_fixed_component_and_keeps_visibility_unknown(self) -> None:
        result = self._run_activity_request(launcher_available=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Requested the Termux:X11 activity", result.stderr)
        self.assertIn("actual GUI visibility remains unknown", result.stderr)
        self.assertEqual(
            json.loads((self.base / "activity-args.json").read_text(encoding="utf-8")),
            ["start", "--user", "0", "-n", "com.termux.x11/com.termux.x11.MainActivity"],
        )

    def test_x11_activity_rejection_reports_manual_open_fallback(self) -> None:
        result = self._run_activity_request(launcher_available=True, launcher_exit=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("did not accept the Termux:X11 activity request", result.stderr)
        self.assertIn("Open Termux:X11 manually", result.stderr)

    def test_missing_x11_activity_launcher_reports_manual_open_fallback(self) -> None:
        result = self._run_activity_request(launcher_available=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("activity launcher is unavailable", result.stderr)
        self.assertIn("Open Termux:X11 manually", result.stderr)
        self.assertFalse((self.base / "activity-args.json").exists())

    def test_stale_running_record_is_read_as_stale_then_reconciled_before_start(self) -> None:
        self.state.mkdir(parents=True, mode=0o700)
        missing_pid = 2**30
        self.state.chmod(0o700)
        session = {
            "schema": 2, "owner": "ternuxx", "provider": "native", "display": ":1",
            "status": "running", "error": None,
            "supervisor": {"pid": missing_pid, "start_ticks": "1", "command_marker": "desktop-supervisor.sh"},
            "x11": {"pid": missing_pid + 1, "start_ticks": "1", "pgid": missing_pid + 1, "sid": missing_pid + 1, "command_marker": "termux-x11"},
            "desktop": {"pid": missing_pid + 2, "start_ticks": "1", "pgid": missing_pid + 2, "sid": missing_pid + 2, "command_marker": "xfce4-session"},
        }
        stale_lock = self.tmp / ".X1-lock"
        stale_socket = self.tmp / ".X11-unix/X1"
        stale_lock.write_text(f"{missing_pid + 1}\n", encoding="ascii")
        stale_lock.chmod(0o600)
        stale_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale_listener.bind(str(stale_socket))
        stale_listener.close()
        record = self.state / "session.json"
        record.write_text(json.dumps(session), encoding="utf-8")
        record.chmod(0o600)

        status = self._run("--json", "gui", "status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["reconciliation_state"], "stale")
        self.assertEqual(json.loads(record.read_text())["status"], "running")  # status is read-only

        # Model a permissive CI/application umask; lock creation must remain private.
        started = self._run("start", umask=0o022)
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("Reconciled the exact stale Ternuxx :1 socket/lock pair", started.stderr)
        self.assertEqual(self._state()["status"], "running")
        self.assertEqual(self._state()["display"], ":1")
        self.assertNotEqual(stale_lock.read_text(encoding="ascii").strip(), str(missing_pid + 1))
        self.assertTrue(stale_socket.exists())

    def test_session_symlink_is_unsafe_and_never_replaced(self) -> None:
        self.state.mkdir(parents=True, mode=0o700)
        self.state.chmod(0o700)
        target = self.home / "session-target.json"
        original = '{"owner":"external"}\n'
        target.write_text(original, encoding="utf-8")
        target.chmod(0o600)
        (self.state / "session.json").symlink_to(target)

        status = self._run("--json", "gui", "status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["reconciliation_state"], "unsafe")
        start = self._run("start")
        self.assertNotEqual(start.returncode, 0)
        self.assertIn("unsafe", start.stderr)
        self.assertTrue((self.state / "session.json").is_symlink())
        self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_start_lock_contention_preserves_session_and_starts_nothing(self) -> None:
        self.state.mkdir(parents=True, mode=0o700)
        self.state.chmod(0o700)
        lock = self.state / ".session.lock"
        lock.mkdir()
        result = self._run("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("holds the session lock", result.stderr)
        self.assertFalse((self.state / "session.json").exists())

    def test_start_repeat_and_status_do_not_request_android_activity(self) -> None:
        marker = self.base / "activity-requested"
        env = self.env.copy()
        env["ACTIVITY_MARKER"] = str(marker)
        command = '''set -e
runner='source "$TERNUXX_LIB_DIR/core.sh"; source "$TERNUXX_LIB_DIR/desktop.sh"; _TN_LIB_DIR="$TERNUXX_LIB_DIR"; _nt_request_termux_x11_activity() { : > "$ACTIVITY_MARKER"; }; case "$1" in start) nt_cmd_start ;; status) nt_cmd_status ;; esac'
bash -c "$runner" _ start
bash -c "$runner" _ start
bash -c "$runner" _ status
'''
        result = subprocess.run(["bash", "-c", command], env=env,
                                text=True, capture_output=True, timeout=12, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        session = self._state()
        self.assertEqual(session["status"], "running")
        supervisor_pid = int(session["supervisor"]["pid"])
        self.assertEqual(os.getpgid(supervisor_pid), supervisor_pid)
        self.assertEqual(os.getsid(supervisor_pid), supervisor_pid)

    def test_default_start_prefers_native_display_one(self) -> None:
        result = self._run("start")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._state()["display"], ":1")
        loader_path = (self.base / "desktop-loader-path").read_text(encoding="utf-8")
        self.assertEqual(loader_path, f"{self.env['PREFIX']}/lib")
        self.assertFalse((self.tmp / ".X0-lock").exists())
        self.assertFalse((self.tmp / ".X11-unix/X0").exists())

    def test_default_start_fails_closed_when_canonical_display_one_is_busy(self) -> None:
        lock_path = self.tmp / ".X1-lock"
        lock_path.write_text("external-owner\n", encoding="ascii")

        result = self._run("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Canonical Native Termux display :1 is occupied or ambiguous", result.stderr)
        self.assertFalse((self.state / "session.json").exists())
        self.assertEqual(lock_path.read_text(encoding="ascii"), "external-owner\n")
        self.assertFalse((self.tmp / ".X0-lock").exists())
        self.assertFalse((self.tmp / ".X11-unix/X0").exists())

    def test_start_refuses_live_external_display_socket(self) -> None:
        import socket

        socket_path = self.tmp / ".X11-unix/X7"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(1)
        self.addCleanup(listener.close)

        result = self._run("start", "--display", "7")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("has a socket or lock", result.stderr)
        self.assertTrue(socket_path.exists())
        self.assertFalse((self.state / "session.json").exists())
        self.assertFalse((self.state / "operations").exists())

    def test_start_refuses_display_lock_without_deleting_it(self) -> None:
        lock_path = self.tmp / ".X7-lock"
        lock_path.write_text("external-owner\n", encoding="ascii")

        result = self._run("start", "--display", "7")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("has a socket or lock", result.stderr)
        self.assertEqual(lock_path.read_text(encoding="ascii"), "external-owner\n")
        self.assertFalse((self.state / "session.json").exists())
        self.assertFalse((self.state / "operations").exists())

    def test_start_is_idempotent_and_stop_is_scoped(self) -> None:
        start = self._run("start", "--display", ":7")
        self.assertEqual(start.returncode, 0, start.stderr)
        first = self._state()
        self.assertEqual(first["status"], "running")
        self.assertEqual(first["display"], ":7")
        journal = self.state / "operations"
        records = sorted(journal.glob("*.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(json.loads(records[0].read_text())["status"], "complete")

        repeated = self._run("start", "--display", "7")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        second = self._state()
        self.assertEqual(second["supervisor"], first["supervisor"])
        self.assertEqual(second["x11"], first["x11"])
        self.assertEqual(second["desktop"], first["desktop"])
        self.assertEqual(len(list(journal.glob("*.json"))), 1)

        status = self._run("--json", "status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["status"], "running")

        stop = self._run("stop")
        self.assertEqual(stop.returncode, 0, stop.stderr)
        self.assertEqual(self._state()["status"], "stopped")
        records = sorted(journal.glob("*.json"))
        self.assertEqual(len(records), 2)
        self.assertEqual({json.loads(item.read_text())["status"] for item in records}, {"complete"})

        repeated_stop = self._run("stop")
        self.assertEqual(repeated_stop.returncode, 0, repeated_stop.stderr)
        self.assertEqual(self._state()["status"], "stopped")
        self.assertFalse((self.tmp / ".X11-unix/X7").exists())
        self.assertFalse((self.tmp / ".X7-lock").exists())
        self.assertEqual(len(list(journal.glob("*.json"))), 3)

    def test_live_session_state_is_discovered_after_default_path_changes(self) -> None:
        start = self._run("start", "--display", "7")
        self.assertEqual(start.returncode, 0, start.stderr)
        original = self._state()
        env = self.env.copy()
        env.pop("TERNUXX_STATE_DIR")
        status = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), "--json", "status"],
            env=env, text=True, capture_output=True, timeout=8, check=False,
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["status"], "running")
        self.assertEqual(json.loads(status.stdout)["display"], ":7")
        repeated = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), "start", "--display", "7"],
            env=env, text=True, capture_output=True, timeout=8, check=False,
        )
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(self._state()["supervisor"], original["supervisor"])
        stopped = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), "stop"],
            env=env, text=True, capture_output=True, timeout=8, check=False,
        )
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertEqual(self._state()["status"], "stopped")

    def test_ambiguous_live_session_states_are_not_adopted(self) -> None:
        first = self._run("start", "--display", "7")
        self.assertEqual(first.returncode, 0, first.stderr)
        second_state = self.home / ".local/share/ternuxx-second-fixture"
        second_state.mkdir(parents=True)
        second_state.chmod(0o700)
        (second_state / "desktop.log").touch(mode=0o600)
        supervisor = subprocess.Popen(
            ["bash", str(self.lib_dir / "desktop-supervisor.sh"), ":8",
             str(second_state), str(self.tmp), str(self.bin_dir / "termux-x11"),
             str(self.bin_dir / "dbus-launch"), str(self.bin_dir / "xfce4-session"),
             str(self.lib_dir / "owned-exec.py")],
            cwd=ROOT, env=self.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        state_file = second_state / "session.json"

        def stop_second_supervisor() -> None:
            stop_env = {**self.env, "TERNUXX_STATE_DIR": str(second_state)}
            if state_file.exists():
                try:
                    subprocess.run(
                        ["bash", str(ROOT / "bin/tx"), "stop"], env=stop_env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=8, check=False,
                    )
                except subprocess.TimeoutExpired:
                    pass
            if supervisor.poll() is None:
                supervisor.send_signal(15)
                try:
                    supervisor.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    supervisor.kill()
                    supervisor.wait(timeout=3)

        self.addCleanup(stop_second_supervisor)
        for _ in range(120):
            try:
                if json.loads(state_file.read_text())["status"] == "running":
                    break
            except (FileNotFoundError, ValueError, KeyError):
                pass
            if supervisor.poll() is not None:
                self.fail("second isolated supervisor did not become ready")
            import time
            time.sleep(0.05)
        else:
            self.fail("second isolated supervisor did not report running")

        default_env = self.env.copy()
        default_env.pop("TERNUXX_STATE_DIR")
        status = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), "--json", "status"],
            env=default_env, text=True, capture_output=True, timeout=8, check=False,
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["status"], "stopped")
        self.assertEqual(self._state()["status"], "running")
        self.assertEqual(json.loads(state_file.read_text())["status"], "running")

        supervisor.send_signal(15)
        supervisor.wait(timeout=8)
        self.assertEqual(self._state()["status"], "running")

    def test_restart_releases_stop_lock_and_is_repeatable(self) -> None:
        first_start = self._run("start", "--display", "7")
        self.assertEqual(first_start.returncode, 0, first_start.stderr)
        before = self._state()

        restarted = self._run("restart", "--display", "7")
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        after = self._state()
        self.assertEqual(after["status"], "running")
        self.assertNotEqual(after["supervisor"]["pid"], before["supervisor"]["pid"])
        self.assertFalse((self.state / ".session.lock").exists())

        repeated = self._run("restart", "--display", "7")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(self._state()["status"], "running")
        self.assertFalse((self.state / ".session.lock").exists())

    def test_stop_and_restart_refuse_proot_before_any_mutation(self) -> None:
        started = self._run("start", "--display", "7")
        self.assertEqual(started.returncode, 0, started.stderr)
        state_before = (self.state / "session.json").read_bytes()
        journal_before = sorted(path.name for path in (self.state / "operations").glob("*.json"))

        env = self.env.copy()
        env.pop("TERMUX_VERSION", None)
        env.pop("PREFIX", None)
        for command in ("stop", "restart"):
            result = subprocess.run(
                ["bash", str(ROOT / "bin/tx"), command],
                env=env, text=True, capture_output=True, timeout=5, check=False,
            )
            self.assertNotEqual(result.returncode, 0, command)
            self.assertIn("requires the Native Termux environment", result.stderr, command)
            self.assertEqual((self.state / "session.json").read_bytes(), state_before, command)
            self.assertEqual(
                sorted(path.name for path in (self.state / "operations").glob("*.json")),
                journal_before,
                command,
            )
            self.assertFalse((self.state / ".session.lock").exists(), command)

    def test_native_lifecycle_refuses_proot_environment(self) -> None:
        env = self.env.copy()
        env.pop("TERMUX_VERSION", None)
        env.pop("PREFIX", None)
        result = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), "start"],
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires the Native Termux environment", result.stderr)
        self.assertFalse(self.state.exists())

    def test_checkpoint_cli_is_native_only_and_records_without_proot(self) -> None:
        previewed = self._run("--json", "checkpoint", "prepare", "--test-id", "native-only", "--pending-test", "boot-check")
        self.assertEqual(previewed.returncode, 0, previewed.stderr)
        preview = json.loads(previewed.stdout)
        self.assertTrue(preview["ok"], preview)
        plan_id = preview["data"]["plan_id"]
        prepared = self._run("--json", "checkpoint", "prepare", "--test-id", "native-only",
                             "--pending-test", "boot-check", "--yes", "--plan-id", plan_id)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        result = json.loads(prepared.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(result["operation"], "continuity.prepare")
        self.assertEqual(result["data"]["state"], "prepared")
        checkpoint_dir = self.state / "continuity/checkpoints"
        checkpoint = next(checkpoint_dir.glob("[0-9a-f]*.json"))
        record = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(record["test_id"], "native-only")
        self.assertFalse(record["task"]["automatic_resume"])
        existing_checkpoints = set(checkpoint_dir.glob("*.json"))

        env = self.env.copy()
        env.pop("TERMUX_VERSION", None)
        blocked = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), "checkpoint", "prepare", "--test-id", "blocked"],
            env=env, text=True, capture_output=True, timeout=5, check=False,
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(set(checkpoint_dir.glob("*.json")), existing_checkpoints)

    def test_ssh_inspect_cli_emits_safe_json_in_native_context(self) -> None:
        result = self._run("--json", "ssh", "inspect")
        self.assertEqual(result.returncode, 0, result.stderr)
        envelope = json.loads(result.stdout)
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["operation"], "ssh.inspect")
        report = envelope["data"]
        self.assertEqual(report["component"], "native_ssh_diagnostics")
        self.assertTrue(report["safety"]["read_only"])
        self.assertFalse(report["safety"]["credential_files_read"])
        self.assertIn(report["checks"]["listener_daemon_correlation"], {"unknown", "not_performed"})
        self.assertFalse((self.state / "continuity").exists())

    def test_boot_wakelock_and_reboot_status_share_management_contract(self) -> None:
        for command in (("boot", "status"), ("wakelock", "status"), ("reboot", "status")):
            result = self._run("--json", *command)
            self.assertEqual(result.returncode, 0, result.stderr)
            response = json.loads(result.stdout)
            self.assertTrue(response["ok"], response)
            self.assertEqual(response["api_version"], 1)
        self.assertFalse((self.state / "continuity").exists())


if __name__ == "__main__":
    unittest.main()
