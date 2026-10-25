from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import ssh_client_keys


class SshClientKeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir(mode=0o700)
        self.ssh = self.home / ".ssh"
        self.ssh.mkdir(mode=0o700)
        self.uid = os.getuid()

    def tearDown(self):
        self.tmp.cleanup()

    def preview(self, name="recovery"):
        return ssh_client_keys.preview(home=self.home, uid=self.uid, name=name)

    def apply(self, plan, name="recovery"):
        return ssh_client_keys.apply(home=self.home, uid=self.uid, name=name,
                                     confirmed=True, plan_id=plan["plan_id"])

    def test_confirmed_creation_has_private_permissions_and_no_private_content_in_result(self):
        plan = self.preview()
        self.assertEqual(plan["status"], "ready")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("later SSH key preview", plan["shared_account_impact"])
        result = self.apply(plan)
        private = self.ssh / "ternuxx-keys" / "recovery"
        public = Path(str(private) + ".pub")
        self.assertEqual(result["status"], "created")
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        self.assertEqual(public.stat().st_mode & 0o777, 0o644)
        self.assertEqual(private.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(result["private_key_path"], "~/.ssh/ternuxx-keys/recovery")
        self.assertTrue(result["enrollment_required"])
        self.assertNotIn(private.read_text(), repr(result))
        self.assertEqual(result["fingerprint"], ssh_client_keys._public_fingerprint(public, self.uid)[1])

    def test_key_name_cannot_escape_fixed_directory(self):
        for name in ("../escape", "UPPER", "white space", ".hidden", "a"*33):
            with self.subTest(name=name), self.assertRaises(ssh_client_keys.ClientKeyError):
                self.preview(name)

    def test_stale_preview_does_not_create_files(self):
        plan = self.preview()
        key_dir = self.ssh / "ternuxx-keys"
        key_dir.mkdir(mode=0o700)
        result = self.apply(plan)
        self.assertEqual(result["status"], "stale_plan")
        self.assertFalse((key_dir / "recovery").exists())

    def test_existing_pair_is_not_overwritten_and_is_reported_without_private_bytes(self):
        first = self.apply(self.preview())
        private = self.ssh / "ternuxx-keys" / "recovery"
        original = private.read_bytes()
        result = self.preview()
        self.assertEqual(result["status"], "already_exists")
        self.assertEqual(result["fingerprint"], first["fingerprint"])
        self.assertEqual(private.read_bytes(), original)
        self.assertNotIn(original.decode(errors="ignore"), repr(result))

    def test_symlinked_key_directory_is_rejected(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir(mode=0o700)
        (self.ssh / "ternuxx-keys").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ssh_client_keys.ClientKeyError, "directory"):
            self.preview()

    def test_existing_public_key_symlink_is_not_followed(self):
        key_dir = self.ssh / "ternuxx-keys"
        key_dir.mkdir(mode=0o700)
        private = key_dir / "recovery"
        private.write_text("private marker")
        private.chmod(0o600)
        outside = Path(self.tmp.name) / "outside.pub"
        outside.write_text("ssh-ed25519 AAAA outside")
        (key_dir / "recovery.pub").symlink_to(outside)
        result = self.preview()
        self.assertEqual(result["status"], "already_exists")
        self.assertIsNone(result["fingerprint"])
        self.assertFalse(result["private_key_valid"])

    def test_creation_failure_cleans_new_directory(self):
        plan = self.preview()
        with mock.patch.object(ssh_client_keys.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ssh_client_keys.ClientKeyError, "unavailable"):
                self.apply(plan)
        self.assertFalse((self.ssh / "ternuxx-keys").exists())


if __name__ == "__main__":
    unittest.main()
