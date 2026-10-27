from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallEventLogTests(unittest.TestCase):
    def run_relay(self, log: Path, payload: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "lib/install_events.py"), "relay", str(log)],
            input=payload, capture_output=True, text=True, check=False,
        )

    def test_relay_redacts_output_and_keeps_log_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "install.log"
            result = self.run_relay(log, "fetch https://user:password@example.invalid/pkg?token=private\n")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("https://<redacted>@example.invalid/pkg?token=<redacted>", result.stdout)
            saved = log.read_text()
            self.assertNotIn("password", saved)
            self.assertNotIn("private", saved)
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_relay_refuses_a_symlink_log_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.write_text("preserve")
            link = Path(tmp) / "install.log"
            link.symlink_to(target)
            result = self.run_relay(link, "payload\n")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(), "preserve")

    def test_initialize_truncates_only_owned_regular_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "install.log"
            log.write_text("old")
            result = subprocess.run(
                [sys.executable, str(ROOT / "lib/install_events.py"), "init", str(log)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text(), "")
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
