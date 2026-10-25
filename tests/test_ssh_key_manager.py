from __future__ import annotations

import base64
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import ssh_key_inventory
import ssh_key_manager


class SshKeyManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir(mode=0o700)
        os.chown(self.home, os.getuid(), -1)
        self.ssh = self.home / ".ssh"
        self.ssh.mkdir(mode=0o700)
        os.chown(self.ssh, os.getuid(), -1)
        self.keys = self.ssh / "authorized_keys"
        self.uid = os.getuid()
        self.key_store = Path(self.tmp.name) / "test-credentials"
        self.key_store.mkdir(mode=0o700)
        self.first = self._generate("key-one", "first-test-key")
        self.second = self._generate("key-two", "second-test-key")
        self.fp1 = ssh_key_inventory._parse_line(self.first)["fingerprint"]
        self.fp2 = ssh_key_inventory._parse_line(self.second)["fingerprint"]

    def _generate(self, name: str, comment: str) -> str:
        path = self.key_store / name
        result = subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                                 "-C", comment, "-f", str(path)],
                                capture_output=True, text=True, timeout=10, check=False)
        if result.returncode:
            self.fail("temporary test key generation failed")
        return path.with_suffix(".pub").read_text(encoding="utf-8").strip()

    def tearDown(self):
        self.tmp.cleanup()

    def test_preview_add_contains_no_key_bytes_and_discloses_external_file_impact(self):
        plan = ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                                       fingerprint=self.fp1, public_key=self.first)
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["affects_services"],
                         ["external Native SSH configurations using this file"])
        self.assertNotIn(self.first, repr(plan))
        self.assertNotIn("fixture-key-one", repr(plan))

    def test_confirmed_add_is_atomic_mode_0600_and_idempotent(self):
        plan = ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                                       fingerprint=self.fp1, public_key=self.first)
        result = ssh_key_manager.apply("add", home=self.home, uid=self.uid,
            fingerprint=self.fp1, public_key=self.first, confirmed=True, plan_id=plan["plan_id"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(self.keys.read_text(), self.first + "\n")
        self.assertEqual(self.keys.stat().st_mode & 0o777, 0o600)
        again = ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                                        fingerprint=self.fp1, public_key=self.first)
        self.assertFalse(again["changed"])

    def test_dedicated_managed_enrollment_leaves_external_keys_unchanged(self):
        self.keys.write_text(self.first + "\n")
        self.keys.chmod(0o600)
        managed_dir = self.ssh / "ternuxx-keys"
        managed_dir.mkdir(mode=0o700)
        os.chown(managed_dir, self.uid, -1)
        managed = managed_dir / "authorized_keys"
        preview = ssh_key_manager.preview("add", home=self.home, uid=self.uid,
            fingerprint=self.fp2, public_key=self.second,
            authorized_keys_file=".ssh/ternuxx-keys/authorized_keys")
        self.assertEqual(preview["target"], ".ssh/ternuxx-keys/authorized_keys")
        self.assertEqual(preview["affects_services"], ["Ternuxx managed SSH service"])
        result = ssh_key_manager.apply("add", home=self.home, uid=self.uid,
            fingerprint=self.fp2, public_key=self.second, confirmed=True, plan_id=preview["plan_id"],
            authorized_keys_file=".ssh/ternuxx-keys/authorized_keys")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(managed.read_text(), self.second + "\n")
        self.assertEqual(managed.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.keys.read_text(), self.first + "\n")
        entries = ssh_key_manager.rollback_list(home=self.home, uid=self.uid,
            authorized_keys_file=".ssh/ternuxx-keys/authorized_keys")
        self.assertEqual(entries["count"], 1)
        rollback_id = entries["entries"][0]["rollback_id"]
        rollback = ssh_key_manager.rollback_preview(rollback_id, home=self.home, uid=self.uid,
            authorized_keys_file=".ssh/ternuxx-keys/authorized_keys")
        self.assertTrue(rollback["can_restore"])
        self.assertEqual(rollback["affects_services"], ["Ternuxx managed SSH service"])
        restored = ssh_key_manager.rollback_apply(rollback_id, home=self.home, uid=self.uid,
            confirmed=True, plan_id=rollback["plan_id"],
            authorized_keys_file=".ssh/ternuxx-keys/authorized_keys")
        self.assertEqual(restored["status"], "complete")
        self.assertFalse(managed.exists())
        self.assertEqual(self.keys.read_text(), self.first + "\n")

    def test_stale_plan_does_not_overwrite_concurrent_key_changes(self):
        plan = ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                                       fingerprint=self.fp1, public_key=self.first)
        self.keys.write_text(self.second + "\n")
        self.keys.chmod(0o600)
        result = ssh_key_manager.apply("add", home=self.home, uid=self.uid,
            fingerprint=self.fp1, public_key=self.first, confirmed=True, plan_id=plan["plan_id"])
        self.assertEqual(result["status"], "stale_plan")
        self.assertEqual(self.keys.read_text(), self.second + "\n")

    def test_remove_exact_fingerprint_preserves_other_records_and_invalid_lines(self):
        self.keys.write_text("# owner comment\n" + self.first + "\nnot-a-key\n" + self.second + "\n")
        self.keys.chmod(0o600)
        plan = ssh_key_manager.preview("remove", home=self.home, uid=self.uid, fingerprint=self.fp1)
        result = ssh_key_manager.apply("remove", home=self.home, uid=self.uid,
            fingerprint=self.fp1, confirmed=True, plan_id=plan["plan_id"])
        self.assertEqual(result["status"], "complete")
        updated = self.keys.read_text()
        self.assertNotIn(self.fp1, updated)
        self.assertIn("# owner comment", updated)
        self.assertIn("not-a-key", updated)
        self.assertIn(self.second, updated)
        self.assertEqual(self.keys.stat().st_mode & 0o777, 0o600)

    def test_malformed_fingerprint_is_rejected(self):
        with self.assertRaisesRegex(ssh_key_manager.SshKeyMutationError, "fingerprint"):
            ssh_key_manager.preview("remove", home=self.home, uid=self.uid,
                                    fingerprint="SHA256:abc")

    def test_last_authorized_key_cannot_be_removed_before_replacement_is_enrolled(self):
        self.keys.write_text(self.first + "\n")
        self.keys.chmod(0o600)
        with self.assertRaisesRegex(ssh_key_manager.SshKeyMutationError, "last authorized key"):
            ssh_key_manager.preview("remove", home=self.home, uid=self.uid, fingerprint=self.fp1)

    def test_public_key_control_characters_are_rejected(self):
        malformed = self.first + "\x00injected"
        with self.assertRaises(ssh_key_manager.SshKeyMutationError):
            ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                                    fingerprint=self.fp1, public_key=malformed)

    def test_remove_duplicate_records_removes_all_exact_matches(self):
        self.keys.write_text(self.first + "\n" + self.first + "\n" + self.second + "\n")
        self.keys.chmod(0o600)
        plan = ssh_key_manager.preview("remove", home=self.home, uid=self.uid, fingerprint=self.fp1)
        self.assertEqual(plan["matching_entries"], 2)
        result = ssh_key_manager.apply("remove", home=self.home, uid=self.uid,
            fingerprint=self.fp1, confirmed=True, plan_id=plan["plan_id"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(self.keys.read_text(), self.second + "\n")

    def test_malformed_key_blob_is_rejected_even_when_type_and_fingerprint_parse(self):
        blob = struct.pack(">I", len("ssh-ed25519")) + b"ssh-ed25519" + b"bad"
        bad_key = "ssh-ed25519 " + base64.b64encode(blob).decode() + " broken"
        fp = ssh_key_inventory._parse_line(bad_key)["fingerprint"]
        with self.assertRaises(ssh_key_manager.SshKeyMutationError):
            ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                                    fingerprint=fp, public_key=bad_key)

    def test_mismatched_fingerprint_and_policy_options_are_rejected(self):
        with self.assertRaises(ssh_key_manager.SshKeyMutationError):
            ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                                    fingerprint=self.fp2, public_key=self.first)
        with self.assertRaises(ssh_key_manager.SshKeyMutationError):
            ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                fingerprint=self.fp1, public_key="restrict,command=\"id\" " + self.first)

    def test_group_or_world_writable_authorized_keys_is_refused(self):
        self.keys.write_text(self.first + "\n")
        self.keys.chmod(0o666)
        original = self.keys.read_bytes()
        with self.assertRaises(ssh_key_manager.SshKeyMutationError):
            ssh_key_manager.preview("remove", home=self.home, uid=self.uid, fingerprint=self.fp1)
        self.assertEqual(self.keys.read_bytes(), original)
        self.assertEqual(self.keys.stat().st_mode & 0o777, 0o666)

    def test_symlink_target_and_unsafe_directory_are_rejected(self):
        outside = Path(self.tmp.name) / "outside"
        outside.write_text(self.first + "\n")
        self.keys.symlink_to(outside)
        with self.assertRaises(ssh_key_manager.SshKeyMutationError):
            ssh_key_manager.preview("remove", home=self.home, uid=self.uid, fingerprint=self.fp1)
        self.keys.unlink()
        self.ssh.chmod(0o755)
        with self.assertRaises(ssh_key_manager.SshKeyMutationError):
            ssh_key_manager.preview("add", home=self.home, uid=self.uid,
                                    fingerprint=self.fp1, public_key=self.first)


    def test_remove_rollback_restores_exact_snapshot_and_is_repeatable(self):
        original = b"# owner note\n" + self.first.encode() + b"\nlegacy-invalid-line\n" + self.second.encode()
        self.keys.write_bytes(original)
        self.keys.chmod(0o640)
        plan = ssh_key_manager.preview("remove", home=self.home, uid=self.uid, fingerprint=self.fp1)
        result = ssh_key_manager.apply("remove", home=self.home, uid=self.uid,
            fingerprint=self.fp1, confirmed=True, plan_id=plan["plan_id"])
        rollback_id = result["rollback_id"]
        self.assertEqual(result["status"], "complete")
        self.assertNotIn(self.first, self.keys.read_text())
        entries = ssh_key_manager.rollback_list(home=self.home, uid=self.uid)
        self.assertEqual(entries["count"], 1)
        self.assertNotIn(self.first, repr(entries))
        preview = ssh_key_manager.rollback_preview(rollback_id, home=self.home, uid=self.uid)
        self.assertTrue(preview["can_restore"])
        self.assertNotIn(original.decode(), repr(preview))
        restored = ssh_key_manager.rollback_apply(rollback_id, home=self.home, uid=self.uid,
            confirmed=True, plan_id=preview["plan_id"])
        self.assertEqual(restored["status"], "complete")
        self.assertEqual(self.keys.read_bytes(), original)
        self.assertEqual(self.keys.stat().st_mode & 0o777, 0o640)
        again = ssh_key_manager.rollback_preview(rollback_id, home=self.home, uid=self.uid)
        self.assertEqual(again["status"], "already_restored")

    def test_add_rollback_restores_absent_authorized_keys(self):
        plan = ssh_key_manager.preview("add", home=self.home, uid=self.uid,
            fingerprint=self.fp1, public_key=self.first)
        result = ssh_key_manager.apply("add", home=self.home, uid=self.uid,
            fingerprint=self.fp1, public_key=self.first, confirmed=True, plan_id=plan["plan_id"])
        self.assertTrue(self.keys.exists())
        rollback = ssh_key_manager.rollback_preview(result["rollback_id"], home=self.home, uid=self.uid)
        result = ssh_key_manager.rollback_apply(result["rollback_id"], home=self.home, uid=self.uid,
            confirmed=True, plan_id=rollback["plan_id"])
        self.assertEqual(result["status"], "complete")
        self.assertFalse(self.keys.exists())

    def test_rollback_refuses_permission_only_change_after_key_mutation(self):
        self.keys.write_text(self.first + "\n" + self.second + "\n")
        plan = ssh_key_manager.preview("remove", home=self.home, uid=self.uid, fingerprint=self.fp1)
        result = ssh_key_manager.apply("remove", home=self.home, uid=self.uid,
            fingerprint=self.fp1, confirmed=True, plan_id=plan["plan_id"])
        current_bytes = self.keys.read_bytes()
        self.keys.chmod(0o644)
        rollback = ssh_key_manager.rollback_preview(result["rollback_id"], home=self.home, uid=self.uid)
        self.assertEqual(rollback["status"], "conflict")
        denied = ssh_key_manager.rollback_apply(result["rollback_id"], home=self.home, uid=self.uid,
            confirmed=True, plan_id=rollback["plan_id"])
        self.assertEqual(denied["status"], "conflict")
        self.assertEqual(self.keys.read_bytes(), current_bytes)
        self.assertEqual(self.keys.stat().st_mode & 0o777, 0o644)

    def test_rollback_refuses_to_overwrite_concurrent_authorized_key_changes(self):
        self.keys.write_text(self.first + "\n" + self.second + "\n")
        self.keys.chmod(0o600)
        plan = ssh_key_manager.preview("remove", home=self.home, uid=self.uid, fingerprint=self.fp1)
        result = ssh_key_manager.apply("remove", home=self.home, uid=self.uid,
            fingerprint=self.fp1, confirmed=True, plan_id=plan["plan_id"])
        self.keys.write_text(self.second + "\n# concurrent owner change\n")
        self.keys.chmod(0o600)
        rollback = ssh_key_manager.rollback_preview(result["rollback_id"], home=self.home, uid=self.uid)
        self.assertTrue(rollback["conflict"])
        self.assertFalse(rollback["can_restore"])
        result = ssh_key_manager.rollback_apply(result["rollback_id"], home=self.home, uid=self.uid,
            confirmed=True, plan_id=rollback["plan_id"])
        self.assertEqual(result["status"], "conflict")
        self.assertIn("concurrent owner change", self.keys.read_text())

    def test_crash_after_atomic_replacement_keeps_recoverable_snapshot(self):
        plan = ssh_key_manager.preview("add", home=self.home, uid=self.uid,
            fingerprint=self.fp1, public_key=self.first)
        original = ssh_key_manager._set_rollback_snapshot_status
        def fail_after_replace(*args, **kwargs):
            raise ssh_key_manager.SshKeyMutationError("simulated crash after replacement")
        ssh_key_manager._set_rollback_snapshot_status = fail_after_replace
        try:
            with self.assertRaisesRegex(ssh_key_manager.SshKeyMutationError, "simulated crash"):
                ssh_key_manager.apply("add", home=self.home, uid=self.uid,
                    fingerprint=self.fp1, public_key=self.first, confirmed=True, plan_id=plan["plan_id"])
        finally:
            ssh_key_manager._set_rollback_snapshot_status = original
        entries = ssh_key_manager.rollback_list(home=self.home, uid=self.uid)
        self.assertEqual(entries["entries"][0]["status"], "prepared")
        rollback = ssh_key_manager.rollback_preview(entries["entries"][0]["rollback_id"],
            home=self.home, uid=self.uid)
        self.assertTrue(rollback["can_restore"])


if __name__ == "__main__":
    unittest.main()
