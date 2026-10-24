from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import desktop_orphan_stop  # noqa: E402


class DesktopOrphanStopIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-orphan-stop-")
        self.proc = Path(self.temp.name) / "proc"
        self.proc.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _record(self, pid: int, marker: str, *, ticks: str = "123", pgid: int | None = None, sid: int | None = None) -> dict:
        root = self.proc / str(pid)
        root.mkdir()
        # /proc stat fields 3..22; state, parent, pgrp, session, then starttime.
        fields = ["S", "1", str(pgid or pid), str(sid or pid)] + ["0"] * 15 + [ticks]
        (root / "stat").write_text(f"{pid} (fixture) {' '.join(fields)}\n", encoding="ascii")
        (root / "cmdline").write_bytes(f"/fixture/{marker}\0".encode())
        uid = os.getuid()
        (root / "status").write_text(f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n", encoding="ascii")
        return {"pid": pid, "start_ticks": ticks, "command_marker": marker, "pgid": pgid or pid, "sid": sid or pid}

    def test_exact_recorded_proot_process_identity_is_accepted(self) -> None:
        record = self._record(101, "proot-display0")
        self.assertEqual(desktop_orphan_stop._identity("desktop", record, self.proc), (101, 101))

    def test_reused_pid_wrong_marker_or_group_is_refused(self) -> None:
        record = self._record(102, "other-command")
        with self.assertRaises(desktop_orphan_stop.OrphanStopError):
            desktop_orphan_stop._identity("desktop", record, self.proc)
        record = self._record(103, "proot-display0", pgid=5, sid=5)
        with self.assertRaises(desktop_orphan_stop.OrphanStopError):
            desktop_orphan_stop._identity("desktop", record, self.proc)


if __name__ == "__main__":
    unittest.main()
