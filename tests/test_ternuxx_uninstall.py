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
    def test_git_metadata_directory_timestamp_is_volatile_but_contents_are_fingerprinted(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-uninstall-") as temp:
            checkout = Path(temp) / "checkout"
            git_dir = checkout / ".git"
            git_dir.mkdir(parents=True)
            head = git_dir / "HEAD"
            head.write_text("ref: refs/heads/main\n")
            first = ternuxx_uninstall._checkout_fingerprint(checkout)
            before = git_dir.stat()
            import os
            os.utime(git_dir, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
            self.assertEqual(first, ternuxx_uninstall._checkout_fingerprint(checkout))
            head.write_text("ref: refs/heads/other\n")
            self.assertNotEqual(first, ternuxx_uninstall._checkout_fingerprint(checkout))

    def test_internal_guest_previews_do_not_invalidate_full_uninstall_plan(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-uninstall-") as temp:
            home = Path(temp) / "home"
            home.mkdir()
            state = home / ".local/share/ternuxx"
            state.mkdir(parents=True)
            prefix = Path(temp) / "prefix"
            prefix.mkdir()
            def guest_preview(**kwargs):
                preview_dir = state / "removal-previews"
                preview_dir.mkdir(mode=0o700, exist_ok=True)
                (preview_dir / "guest-plan.json").write_text('{"plan_id":"stable"}')
                return {"alias": "debian", "plan_id": "stable"}
            with patch.object(ternuxx_uninstall, "EXPECTED_PREFIX", str(prefix)), \
                 patch.object(ternuxx_uninstall.shutil, "which", return_value="/fake/proot-distro"), \
                 patch.object(ternuxx_uninstall.proot_distro_removal, "_inventory", return_value={"debian"}), \
                 patch.object(ternuxx_uninstall.proot_distro_removal, "preview", side_effect=guest_preview):
                plan = ternuxx_uninstall.preview(prefix=str(prefix), home=str(home), state_dir=str(state))
                ternuxx_uninstall._verify(plan, prefix=str(prefix), home=str(home), state_dir=str(state))

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
