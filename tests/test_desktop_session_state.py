"""Ownership-aware native desktop session classification fixtures."""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import struct
import sys
import threading
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import desktop_session_state  # noqa: E402


class DesktopSessionStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-session-state-")
        root = Path(self.temp.name)
        self.home = root / "home"
        self.home.mkdir()
        self.state = self.home / ".local/share/ternuxx"
        self.state.mkdir(parents=True, mode=0o700)
        self.state.chmod(0o700)
        self.proc = root / "proc"
        self.proc.mkdir()
        self.tmp = root / "tmp"
        (self.tmp / ".X11-unix").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _role(self, name: str, pid: int, *, ticks: str = "456", actual_ticks: str | None = None) -> dict:
        markers = desktop_session_state.MARKERS
        proc = self.proc / str(pid)
        proc.mkdir()
        pgid = pid
        fields = ["S", "1", str(pgid), str(pid)] + ["0"] * 15 + [actual_ticks or ticks]
        (proc / "stat").write_text(f"{pid} (fixture) {' '.join(fields)}\n", encoding="ascii")
        (proc / "cmdline").write_bytes(f"/fixture/{markers[name]}\0".encode())
        (proc / "status").write_text(f"Name:\tfixture\nUid:\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\n", encoding="ascii")
        record = {"pid": pid, "start_ticks": ticks, "command_marker": markers[name]}
        if name != "supervisor":
            record.update(pgid=pid, sid=pid)
        return record

    def _session(self, status: str = "running", *, process_ticks: str | None = None) -> dict:
        pids = {"supervisor": 101, "x11": 102, "desktop": 103}
        roles = {name: self._role(name, pid, actual_ticks=process_ticks)
                 for name, pid in pids.items()}
        session = {"schema": 2, "owner": "ternuxx", "provider": "native", "display": ":1",
                   "status": status, **roles, "error": None}
        path = self.state / "session.json"
        path.write_text(json.dumps(session), encoding="utf-8")
        path.chmod(0o600)
        return session

    def _inspect(self) -> dict:
        return desktop_session_state.inspect(self.home, self.state, self.proc, self.tmp)

    def _x11_server(self, path: Path) -> socket.socket:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path))
        listener.listen(4)
        listener.settimeout(3)
        def serve() -> None:
            while True:
                try:
                    client, _ = listener.accept()
                except OSError:
                    return
                with client:
                    try:
                        client.recv(12)
                        client.sendall(struct.pack("<BBHHH", 1, 0, 11, 0, 0))
                    except OSError:
                        pass
        threading.Thread(target=serve, daemon=True).start()
        self.addCleanup(listener.close)
        return listener

    def test_healthy_running_requires_all_identities_and_responsive_display(self) -> None:
        self._session()
        sock_path = self.tmp / ".X11-unix/X1"
        self._x11_server(sock_path)
        (self.tmp / ".X1-lock").write_text("102\n", encoding="ascii")
        result = self._inspect()
        self.assertEqual(result["state"], "running")
        self.assertEqual(result["display"], ":1")
        self.assertEqual(result["display_state"], "ready")

    def test_native_termux_x11_without_lock_is_classified_as_external(self) -> None:
        session = self._session("running", process_ticks="456")
        x11 = self.proc / "102"
        (x11 / "cmdline").write_bytes(b"termux-x11\0com.termux.x11\0:1\0")
        session["x11"].update(ownership="external", display=":1", pgid=None, sid=None)
        path = self.state / "session.json"
        path.write_text(json.dumps(session), encoding="utf-8")
        path.chmod(0o600)
        sock_path = self.tmp / ".X11-unix/X1"
        self._x11_server(sock_path)
        result = self._inspect()
        self.assertEqual(result["state"], "running")
        self.assertEqual(result["display_state"], "ready")

    def test_lockless_responsive_native_x11_allows_stopped_record_to_start(self) -> None:
        self._session("stopped", process_ticks="999")
        x11 = self.proc / "102"
        (x11 / "cmdline").write_bytes(b"termux-x11\0com.termux.x11\0:1\0")
        sock_path = self.tmp / ".X11-unix/X1"
        self._x11_server(sock_path)
        result = self._inspect()
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["display_state"], "external")

    def test_unidentified_lockless_display_remains_unknown(self) -> None:
        self._session("stopped", process_ticks="999")
        sock_path = self.tmp / ".X11-unix/X1"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(sock_path))
        listener.listen(2)
        self.addCleanup(listener.close)
        result = self._inspect()
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["display_state"], "unknown")

    def test_reused_pids_with_mismatched_start_ticks_are_stale(self) -> None:
        self._session(process_ticks="999")
        self.assertEqual(self._inspect()["state"], "stale")

    def test_starting_is_not_mistaken_for_stopped_or_running(self) -> None:
        self._session("starting")
        self.assertEqual(self._inspect()["state"], "starting")

    def test_shutdown_in_progress_is_reported_without_becoming_stopped(self) -> None:
        self._session("stopping")
        self.assertEqual(self._inspect()["state"], "stopping")

    def test_supervisor_child_disagreement_is_failed(self) -> None:
        self._session()
        import shutil
        shutil.rmtree(self.proc / "102")
        self.assertEqual(self._inspect()["state"], "failed")

    def test_interrupted_shutdown_with_absent_processes_is_failed(self) -> None:
        self._session("stop_incomplete", process_ticks="999")
        self.assertEqual(self._inspect()["state"], "failed")

    def test_incomplete_shutdown_with_dead_recorded_display_is_reconcilable(self) -> None:
        self._session("stop_incomplete", process_ticks="999")
        sock_path = self.tmp / ".X11-unix/X1"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(sock_path))
        listener.close()
        (self.tmp / ".X1-lock").write_text("102\n", encoding="ascii")
        result = self._inspect()
        self.assertEqual(result["state"], "stale")
        self.assertEqual(result["display_state"], "stale")

    def test_failed_lifecycle_state_is_reported_as_failed(self) -> None:
        self._session("failed", process_ticks="999")
        self.assertEqual(self._inspect()["state"], "failed")

    def test_incomplete_desktop_identity_is_absent_only_when_recorded_pid_is_gone(self) -> None:
        session = self._session("failed")
        desktop_pid = session["desktop"]["pid"]
        (self.proc / str(desktop_pid)).rename(self.proc / f"{desktop_pid}.saved")
        session["desktop"].update(start_ticks=None, pgid=None, sid=None)
        path = self.state / "session.json"
        path.write_text(json.dumps(session), encoding="utf-8")
        path.chmod(0o600)
        result = self._inspect()
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["processes"]["desktop"], "absent")
        (self.proc / str(desktop_pid)).mkdir()
        (self.proc / str(desktop_pid) / "stat").write_text(f"{desktop_pid} (fixture) S 1 1 1 0\n", encoding="ascii")
        self.assertEqual(self._inspect()["state"], "unknown")

    def test_proot_provider_record_is_classified_with_its_own_process_marker(self) -> None:
        session = self._session("failed", process_ticks="999")
        session["provider"] = "proot"
        session["desktop"]["command_marker"] = "proot-display0"
        path = self.state / "session.json"
        path.write_text(json.dumps(session), encoding="utf-8")
        path.chmod(0o600)
        result = self._inspect()
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["display_state"], "absent")
        self.assertEqual(result["processes"], {"supervisor": "absent", "x11": "absent", "desktop": "absent"})

    def _proot_readiness_fixture(self, *, omit: set[str] | None = None,
                                 other_group: set[str] | None = None) -> dict:
        import proot_desktops
        session = self._session()
        session.update(provider="proot", display=":0", desktop_id="xfce", guest_alias="debian")
        session["desktop"]["command_marker"] = "proot-display0"
        path = self.state / "session.json"
        path.write_text(json.dumps(session), encoding="utf-8")
        path.chmod(0o600)
        names = proot_desktops.DESKTOP_READY_PROCESSES["xfce"]
        pid = 104
        for name in names:
            if omit and name in omit:
                continue
            proc = self.proc / str(pid)
            proc.mkdir()
            fields = ["S", "1", "103", "103"] + ["0"] * 15 + ["789"]
            (proc / "stat").write_text(f"{pid} ({name}) {' '.join(fields)}\n", encoding="ascii")
            (proc / "comm").write_text(name + "\n", encoding="ascii")
            (proc / "status").write_text(
                f"Name:\t{name}\nUid:\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\n",
                encoding="ascii")
            pid += 1
        for name in other_group or set():
            proc = self.proc / str(pid)
            proc.mkdir()
            fields = ["S", "1", "999", "999"] + ["0"] * 15 + ["789"]
            (proc / "stat").write_text(f"{pid} ({name}) {' '.join(fields)}\n", encoding="ascii")
            (proc / "comm").write_text(name + "\n", encoding="ascii")
            (proc / "status").write_text(
                f"Name:\t{name}\nUid:\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\n",
                encoding="ascii")
            pid += 1
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.tmp / ".X11-unix/X0"))
        listener.listen(2)
        self.addCleanup(listener.close)
        (self.tmp / ".X0-lock").write_text("102\n", encoding="ascii")
        return self._inspect()

    def test_proot_readiness_requires_shell_wm_panel_and_desktop_in_owned_group(self) -> None:
        ready = self._proot_readiness_fixture()
        self.assertEqual(ready["state"], "running")
        self.assertEqual(ready["desktop_readiness"]["state"], "ready")
        self.assertEqual(ready["desktop_readiness"]["missing_processes"], [])

    def test_proot_readiness_ignores_expected_processes_outside_owned_group(self) -> None:
        partial = self._proot_readiness_fixture(omit={"xfce4-panel"}, other_group={"xfce4-panel"})
        self.assertEqual(partial["state"], "running")
        self.assertEqual(partial["desktop_readiness"]["state"], "starting")
        self.assertEqual(partial["desktop_readiness"]["missing_processes"], ["xfce4-panel"])

    def test_proot_exec_transition_uses_frozen_process_group_identity(self) -> None:
        session = self._session()
        session["provider"] = "proot"
        session["desktop"]["command_marker"] = "proot-display0"
        desktop_cmdline = self.proc / str(session["desktop"]["pid"]) / "cmdline"
        desktop_cmdline.write_bytes(b"/prefix/bin/proot\0login debian\0")
        path = self.state / "session.json"
        path.write_text(json.dumps(session), encoding="utf-8")
        path.chmod(0o600)
        socket_path = self.tmp / ".X11-unix/X1"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(2)
        self.addCleanup(listener.close)
        (self.tmp / ".X1-lock").write_text("102\n", encoding="ascii")
        result = self._inspect()
        self.assertEqual(result["state"], "running")
        self.assertEqual(result["processes"]["desktop"], "live")

    def test_proot_running_group_is_live_after_launcher_pid_exits(self) -> None:
        session = self._session()
        session["provider"] = "proot"
        session["desktop"]["command_marker"] = "proot-display0"
        leader_pid = session["desktop"]["pid"]
        import shutil
        shutil.rmtree(self.proc / str(leader_pid))
        member_pid = 104
        member = self.proc / str(member_pid)
        member.mkdir()
        fields = ["S", "1", str(leader_pid), str(leader_pid)] + ["0"] * 15 + ["789"]
        (member / "stat").write_text(f"{member_pid} (proot-child) {' '.join(fields)}\n", encoding="ascii")
        (member / "cmdline").write_bytes(b"/prefix/bin/proot\0login debian\0")
        (member / "status").write_text(f"Name:\tproot\nUid:\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\n", encoding="ascii")
        path = self.state / "session.json"
        path.write_text(json.dumps(session), encoding="utf-8")
        path.chmod(0o600)
        socket_path = self.tmp / ".X11-unix/X1"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(2)
        self.addCleanup(listener.close)
        (self.tmp / ".X1-lock").write_text("102\n", encoding="ascii")
        result = self._inspect()
        self.assertEqual(result["state"], "running")
        self.assertEqual(result["processes"]["desktop"], "live")

    def test_unavailable_process_inventory_is_unknown(self) -> None:
        self._session()
        self.assertEqual(desktop_session_state.inspect(self.home, self.state, self.proc / "missing", self.tmp)["state"], "unknown")

    def test_symlinked_display_artifact_is_unsafe(self) -> None:
        self._session()
        (self.tmp / ".X1-lock").write_text("102\n", encoding="ascii")
        (self.tmp / ".X11-unix/X1").symlink_to(self.temp.name)
        self.assertEqual(self._inspect()["state"], "unsafe")

    def test_missing_display_socket_does_not_report_healthy(self) -> None:
        self._session()
        (self.tmp / ".X1-lock").write_text("102\n", encoding="ascii")
        self.assertEqual(self._inspect()["state"], "failed")

    def test_stopped_session_without_socket_directory_or_lock_is_stopped(self) -> None:
        self._session("stopped", process_ticks="999")
        import shutil
        shutil.rmtree(self.tmp / ".X11-unix")
        result = self._inspect()
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["display_state"], "absent")

    def test_display_lock_without_socket_directory_remains_unknown(self) -> None:
        self._session("stopped", process_ticks="999")
        import shutil
        shutil.rmtree(self.tmp / ".X11-unix")
        (self.tmp / ".X1-lock").write_text("102\n", encoding="ascii")
        result = self._inspect()
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["display_state"], "unknown")

    def test_unresponsive_owned_display_is_stale_without_deleting_artifacts(self) -> None:
        self._session(process_ticks="999")
        socket_path = self.tmp / ".X11-unix/X1"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.close()
        lock_path = self.tmp / ".X1-lock"
        lock_path.write_text("102\n", encoding="ascii")
        result = self._inspect()
        self.assertEqual(result["state"], "stale")
        self.assertEqual(result["display"], ":1")
        self.assertEqual(result["display_state"], "stale")
        self.assertTrue(socket_path.exists())
        self.assertEqual(lock_path.read_text(encoding="ascii"), "102\n")

    def test_symlinked_tmp_root_is_unsafe(self) -> None:
        self._session(process_ticks="999")
        linked_tmp = self.home / "tmp-link"
        linked_tmp.symlink_to(self.tmp, target_is_directory=True)
        result = desktop_session_state.inspect(self.home, self.state, self.proc, linked_tmp)
        self.assertEqual(result["state"], "unsafe")

    def test_malformed_and_symlinked_session_records_are_unsafe(self) -> None:
        path = self.state / "session.json"
        path.write_text("{", encoding="utf-8")
        path.chmod(0o600)
        self.assertEqual(self._inspect()["state"], "unsafe")
        path.unlink()
        target = self.home / "target.json"
        target.write_text("{}", encoding="utf-8")
        target.chmod(0o600)
        path.symlink_to(target)
        self.assertEqual(self._inspect()["state"], "unsafe")

    def test_ensure_state_directory_refuses_symlink_components(self) -> None:
        unsafe_home = self.home / "unsafe-home"
        unsafe_home.mkdir()
        outside = unsafe_home / "outside"
        outside.mkdir(mode=0o755)
        outside.chmod(0o755)
        (unsafe_home / ".local").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(desktop_session_state.StateError, "ownership or type is unsafe"):
            desktop_session_state.ensure_state_dir(unsafe_home, unsafe_home / ".local/share/ternuxx")
        self.assertEqual((outside.stat().st_mode & 0o777), 0o755)
        self.assertFalse((outside / "share").exists())

    def test_stale_reconciliation_requires_private_lifecycle_lock(self) -> None:
        self._session(process_ticks="999")
        with self.assertRaisesRegex(desktop_session_state.StateError, "requires the lifecycle session lock"):
            desktop_session_state.reconcile_stale(self.home, self.state, self.proc, self.tmp)
        lock = self.state / ".session.lock"
        lock.mkdir(mode=0o700)
        lock.chmod(0o700)
        result = desktop_session_state.reconcile_stale(self.home, self.state, self.proc, self.tmp)
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(json.loads((self.state / "session.json").read_text())["status"], "stopped")

    def test_stale_reconciliation_rejects_unsafe_lifecycle_lock(self) -> None:
        self._session(process_ticks="999")
        lock = self.state / ".session.lock"
        lock.mkdir(mode=0o755)
        lock.chmod(0o755)
        with self.assertRaisesRegex(desktop_session_state.StateError, "permissions are unsafe"):
            desktop_session_state.reconcile_stale(self.home, self.state, self.proc, self.tmp)
        self.assertEqual(json.loads((self.state / "session.json").read_text())["status"], "running")

    def test_missing_session_record_is_stopped(self) -> None:
        self.assertEqual(self._inspect()["state"], "stopped")


if __name__ == "__main__":
    unittest.main()
