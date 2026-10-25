#!/usr/bin/env python3
"""Exercise owned desktop process-group cleanup with isolated fake clients."""
import json
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "lib" / "desktop-supervisor.sh"
OWNED_EXEC = ROOT / "lib" / "owned-exec.py"


X11_SCRIPT = r'''#!/usr/bin/env python3
import os, signal, socket, sys, time
display = sys.argv[1]
path = os.path.join(os.environ["TMPDIR"], ".X11-unix", "X" + display[1:])
server = socket.socket(socket.AF_UNIX)
server.bind(path)
server.listen(1)
def stop(_sig, _frame):
    server.close()
    try: os.unlink(path)
    except FileNotFoundError: pass
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
while True: time.sleep(1)
'''


XFCE_SCRIPT = r'''#!/usr/bin/env python3
import os, signal, subprocess, sys, time
child = subprocess.Popen(["/bin/sleep", "90"])
with open(os.environ["FAKE_XFCE_CHILD_PID"], "w", encoding="utf-8") as stream:
    stream.write(str(child.pid))
while True: time.sleep(1)
'''


DBUS_SCRIPT = r'''#!/usr/bin/env python3
import os, sys
if len(sys.argv) < 3 or sys.argv[1] != "--exit-with-session":
    raise SystemExit(64)
os.execv(sys.argv[2], sys.argv[2:])
'''


class DesktopSupervisorProcessGroupTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ternuxx-p2-")
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.tmp = self.root / "tmp"
        self.socket_dir = self.tmp / ".X11-unix"
        self.state.mkdir()
        self.socket_dir.mkdir(parents=True)
        self.x11 = self.root / "termux-x11"
        self.dbus = self.root / "dbus-launch"
        self.xfce = self.root / "xfce4-session"
        self.child_pid_file = self.root / "xfce-child.pid"
        self._write_executable(self.x11, X11_SCRIPT)
        self._write_executable(self.dbus, DBUS_SCRIPT)
        self._write_executable(self.xfce, XFCE_SCRIPT)
        self.environment = os.environ.copy()
        self.environment.update({
            "TMPDIR": str(self.tmp),
            "FAKE_XFCE_CHILD_PID": str(self.child_pid_file),
        })
        self.supervisor = None
        self.unrelated = None

    @staticmethod
    def _write_executable(path, contents):
        path.write_text(contents, encoding="utf-8")
        path.chmod(0o700)

    def _start(self):
        self.supervisor = subprocess.Popen(
            ["bash", str(SUPERVISOR), ":91", str(self.state), str(self.tmp),
             str(self.x11), str(self.dbus), str(self.xfce), str(OWNED_EXEC)],
            cwd=ROOT, env=self.environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )

    def _wait_for_state(self, wanted, timeout=8):
        state_file = self.state / "session.json"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                if state["status"] == wanted:
                    return state
            except (FileNotFoundError, ValueError, KeyError):
                pass
            if self.supervisor.poll() is not None:
                break
            time.sleep(0.05)
        state_text = state_file.read_text(encoding="utf-8") if state_file.exists() else "missing state"
        log_file = self.state / "desktop.log"
        log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else "missing log"
        self.fail("session did not reach state %r; supervisor=%r; state=%s; log=%s" %
                  (wanted, self.supervisor.poll(), state_text, log_text))

    def _stop_supervisor(self):
        if self.supervisor is not None and self.supervisor.poll() is None:
            self.supervisor.send_signal(signal.SIGTERM)
            try:
                self.supervisor.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.fail("supervisor did not exit after SIGTERM")

    def _assert_pid_not_live(self, pid):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
                rest = stat[stat.rfind(")") + 2:].split()
                if rest and rest[0] in ("Z", "X"):
                    return
            except FileNotFoundError:
                return
            time.sleep(0.05)
        self.fail(f"owned process {pid} remained live after group shutdown")

    def tearDown(self):
        try:
            self._stop_supervisor()
            if self.unrelated is not None and self.unrelated.poll() is None:
                self.unrelated.terminate()
                self.unrelated.wait(timeout=3)
        finally:
            self.temporary.cleanup()

    def test_native_plasma_uses_allowlisted_marker_and_private_environment(self):
        session = self.root / "startplasma-x11"
        self._write_executable(session, XFCE_SCRIPT)
        self.supervisor = subprocess.Popen(
            ["bash", str(SUPERVISOR), ":91", str(self.state), str(self.tmp),
             str(self.x11), str(self.dbus), str(session), str(OWNED_EXEC),
             "startplasma-x11", "native", "plasma"],
            cwd=ROOT, env=self.environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        state = self._wait_for_state("running")
        self.assertEqual(state["desktop_id"], "plasma")
        self.assertEqual(state["desktop"]["command_marker"], "startplasma-x11")
        self.assertTrue((self.state / "plasma/runtime").is_dir())
        self._stop_supervisor()
        self.assertEqual(json.loads((self.state / "session.json").read_text())["status"], "stopped")

    def test_proot_desktop_environment_uses_guest_ids_not_native_allowlist(self):
        session = self.root / "proot-display0"
        self._write_executable(session, XFCE_SCRIPT)
        self.supervisor = subprocess.Popen(
            ["bash", str(SUPERVISOR), ":91", str(self.state), str(self.tmp),
             str(self.x11), str(self.dbus), str(session), str(OWNED_EXEC),
             "proot-display0", "proot", "gnome"],
            cwd=ROOT, env=self.environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        state = self._wait_for_state("running")
        self.assertEqual(state["provider"], "proot")
        self.assertEqual(state["desktop_id"], "gnome")
        environ = Path(f"/proc/{state['desktop']['pid']}/environ").read_bytes().split(b"\0")
        self.assertIn(b"XDG_SESSION_TYPE=x11", environ)
        self.assertIn(b"XDG_CURRENT_DESKTOP=GNOME", environ)
        self._stop_supervisor()

    def test_proot_exec_transition_preserves_owned_process_group(self):
        session = self.root / "proot-display0"
        self._write_executable(
            session,
            "#!/usr/bin/env python3\nimport os,time\ntime.sleep(0.6)\nos.execv('/bin/sleep',['sleep','90'])\n",
        )
        self.supervisor = subprocess.Popen(
            ["bash", str(SUPERVISOR), ":91", str(self.state), str(self.tmp),
             str(self.x11), str(self.dbus), str(session), str(OWNED_EXEC),
             "proot-display0", "proot", "xfce"],
            cwd=ROOT, env=self.environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        state = self._wait_for_state("running")
        self.assertEqual(state["provider"], "proot")
        self.assertEqual(state["desktop"]["command_marker"], "proot-display0")
        self.assertNotIn(b"proot-display0", Path(f"/proc/{state['desktop']['pid']}/cmdline").read_bytes())
        self._stop_supervisor()
        self.assertEqual(
            json.loads((self.state / "session.json").read_text())["status"], "stopped",
            (self.state / "session.json").read_text())

    def test_proot_parent_exit_keeps_supervisor_on_owned_session_group(self):
        session = self.root / "proot-display0"
        self._write_executable(
            session,
            "#!/usr/bin/env python3\nimport os,subprocess,time\nchild=subprocess.Popen(['/bin/sleep','90'])\nopen(os.environ['FAKE_XFCE_CHILD_PID'],'w').write(str(child.pid))\ntime.sleep(0.6)\n",
        )
        self.supervisor = subprocess.Popen(
            ["bash", str(SUPERVISOR), ":91", str(self.state), str(self.tmp),
             str(self.x11), str(self.dbus), str(session), str(OWNED_EXEC),
             "proot-display0", "proot", "xfce"],
            cwd=ROOT, env=self.environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        state = self._wait_for_state("running")
        child_pid = int(self.child_pid_file.read_text(encoding="utf-8"))
        self.assertNotEqual(state["desktop"]["pid"], child_pid)
        self.assertFalse(Path(f"/proc/{state['desktop']['pid']}").exists())
        self._stop_supervisor()
        self.assertEqual(
            json.loads((self.state / "session.json").read_text())["status"], "stopped",
            (self.state / "session.json").read_text())
        self._assert_pid_not_live(child_pid)

    def test_clean_exit_during_stabilization_is_not_reported_running(self):
        self._write_executable(
            self.xfce,
            "#!/usr/bin/env python3\nimport time\ntime.sleep(0.45)\n",
        )
        self._start()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and self.supervisor.poll() is None:
            time.sleep(0.05)
        self.assertIsNotNone(self.supervisor.poll(), "short-lived session was accepted as running")
        state = json.loads((self.state / "session.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "failed")
        self.assertIn("exited before startup stabilization", state["error"])
        self._assert_pid_not_live(state["x11"]["pid"])

    def test_stop_terminates_only_owned_groups_and_descendants(self):
        self.unrelated = subprocess.Popen(["/bin/sleep", "90"])
        self._start()
        state = self._wait_for_state("running")
        self.assertEqual(state["schema"], 2)
        for role in ("x11", "desktop"):
            self.assertEqual(state[role]["pid"], state[role]["pgid"])
            self.assertEqual(state[role]["pgid"], state[role]["sid"])
        child_pid = int(self.child_pid_file.read_text(encoding="utf-8"))

        self._stop_supervisor()

        stopped = json.loads((self.state / "session.json").read_text(encoding="utf-8"))
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(self.supervisor.returncode, 0)
        self.assertIsNone(self.unrelated.poll(), "unrelated process was stopped")
        self._assert_pid_not_live(child_pid)

    def test_partial_startup_failure_cleans_owned_x11_group(self):
        self.environment["FAKE_NO_X11_SOCKET"] = "1"
        self.x11.write_text(X11_SCRIPT.replace(
            "server.bind(path)\nserver.listen(1)",
            "if os.environ.get('FAKE_NO_X11_SOCKET') != '1':\n    server.bind(path)\n    server.listen(1)\nelse:\n    time.sleep(90)"
        ), encoding="utf-8")
        self.x11.chmod(0o700)
        self._start()
        state_file = self.state / "session.json"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and self.supervisor.poll() is None:
            time.sleep(0.05)
        self.assertIsNotNone(self.supervisor.poll(), "failed startup did not exit")
        state = json.loads(state_file.read_text(encoding="utf-8"))
        log_file = self.state / "desktop.log"
        log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else "missing log"
        self.assertEqual(state["status"], "failed", log_text)
        self._assert_pid_not_live(state["x11"]["pid"])


if __name__ == "__main__":
    unittest.main()
