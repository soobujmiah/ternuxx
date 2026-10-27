"""Focused ownership checks for cooperative nested desktop shutdown."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import desktop_lifecycle_lock


class CooperativeNestedStopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-lock-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / "state"
        self.state.mkdir(mode=0o700)
        self.proc = self.base / "proc"
        self.proc.mkdir()
        self.pid = 87654
        self.lock = self.state / ".session.lock"
        self.lock.mkdir(mode=0o700)
        self.owner = self.lock / "owner.json"
        self._write_owner("PRoot nested start nested-stop-v1")
        process = self.proc / str(self.pid)
        process.mkdir()
        (process / "cmdline").write_bytes(
            b"/usr/bin/bash\0/home/ternuxx/scripts/proot-gui0.sh\0start\0--mode\0auto\0"
        )

    def _write_owner(self, operation: str) -> None:
        self.owner.write_text(json.dumps({"pid": self.pid, "start_ticks": "123", "operation": operation}) + "\n")
        self.owner.chmod(0o600)

    def test_request_signals_only_verified_cooperative_pgui_owner(self) -> None:
        with mock.patch.object(desktop_lifecycle_lock, "_ticks", return_value="123"), \
             mock.patch.object(desktop_lifecycle_lock.os, "kill") as send_signal:
            self.assertTrue(desktop_lifecycle_lock.request_nested_stop(self.state, self.proc))
        send_signal.assert_called_once_with(self.pid, desktop_lifecycle_lock.signal.SIGUSR1)

    def test_request_refuses_legacy_or_unrelated_lock_owner(self) -> None:
        self._write_owner("PRoot auto start")
        with mock.patch.object(desktop_lifecycle_lock, "_ticks", return_value="123"), \
             mock.patch.object(desktop_lifecycle_lock.os, "kill") as send_signal:
            self.assertFalse(desktop_lifecycle_lock.request_nested_stop(self.state, self.proc))
        send_signal.assert_not_called()

    def test_nested_exec_isolates_guest_into_its_own_process_group(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib/session_exec.py"), sys.executable,
             "-c", "import os; print(os.getpid(), os.getsid(0), os.getpgid(0))"],
            text=True, capture_output=True, timeout=5, check=True,
        )
        pid, sid, pgid = map(int, result.stdout.split())
        self.assertEqual(pid, sid)
        self.assertEqual(pid, pgid)

    def test_tag_binds_cooperative_stop_capability_to_current_lock_owner(self) -> None:
        with mock.patch.object(desktop_lifecycle_lock, "_ticks", return_value="123"):
            desktop_lifecycle_lock.tag_nested_stop(self.state, self.proc, self.pid)
        self.assertEqual(json.loads(self.owner.read_text())["operation"], "PRoot nested start nested-stop-v1")
        self.assertEqual(self.owner.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
