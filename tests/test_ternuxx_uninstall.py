from __future__ import annotations
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import ternuxx_uninstall


class TernuxxUninstallTests(unittest.TestCase):
    def test_exact_preview_and_phrase_remove_only_private_state(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-uninstall-") as temp:
            home = Path(temp) / "home"
            home.mkdir()
            state = home / ".local/share/ternuxx"
            state.mkdir(parents=True)
            (state / "user-data.txt").write_text("owned state")
            prefix = Path(temp) / "prefix"
            prefix.mkdir()
            with patch.object(ternuxx_uninstall, "EXPECTED_PREFIX", str(prefix)), \
                 patch.object(ternuxx_uninstall.shutil, "which", return_value=None):
                plan = ternuxx_uninstall.preview(prefix=str(prefix), home=str(home), state_dir=str(state))
                with self.assertRaises(ternuxx_uninstall.UninstallError):
                    ternuxx_uninstall.apply(prefix=str(prefix), home=str(home), state_dir=str(state),
                        plan_id=plan["plan_id"], confirmation="REMOVE", confirmed=True)
                result = ternuxx_uninstall.apply(prefix=str(prefix), home=str(home), state_dir=str(state),
                    plan_id=plan["plan_id"], confirmation="UNINSTALL TERNUXX", confirmed=True)
            self.assertEqual(result["status"], "uninstalled")
            self.assertFalse(state.exists())
            self.assertTrue(prefix.exists())


if __name__ == "__main__":
    unittest.main()
