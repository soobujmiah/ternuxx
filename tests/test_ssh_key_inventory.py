from __future__ import annotations

import base64
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import ssh_key_inventory


def entry(key_type: str = "ssh-ed25519", comment: str = "workstation") -> str:
    blob = struct.pack(">I", len(key_type)) + key_type.encode("ascii") + b"fixture-key-material"
    return f"{key_type} {base64.b64encode(blob).decode()} {comment}"


class SshKeyInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.ssh_dir = self.home / ".ssh"
        self.ssh_dir.mkdir(mode=0o700)
        self.keys = self.ssh_dir / "authorized_keys"
        self.uid = os.getuid()
        os.chown(self.home, self.uid, -1)
        os.chown(self.ssh_dir, self.uid, -1)

    def tearDown(self):
        self.tmp.cleanup()

    def test_managed_inventory_refuses_external_native_key_path(self):
        config = self.home / ".config/ternuxx/sshd_recovery.conf"
        config.parent.mkdir(parents=True)
        config.write_text("Port 8023\n")
        self.keys.write_text(entry() + "\n")
        self.keys.chmod(0o600)
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0,
                stdout="authorizedkeysfile .ssh/authorized_keys\n", stderr="")
        result = ssh_key_inventory.list_managed_authorized_keys(
            home=self.home, uid=self.uid, which=lambda _name: "/fixture/sshd", runner=runner)
        self.assertEqual(result["status"], "unsupported_path")
        self.assertNotIn("authorized_keys_file", result)
        self.assertEqual(result["keys"], [])
        self.assertEqual(calls[0][0][1:4], ["-T", "-f", str(config)])
        self.assertIn("user=", calls[0][0][-1])

    def test_managed_inventory_uses_isolated_ternuxx_key_file_when_configured(self):
        config = self.home / ".config/ternuxx/sshd_recovery.conf"
        config.parent.mkdir(parents=True)
        config.write_text("Port 8023\n")
        dedicated = self.ssh_dir / "ternuxx-keys"
        dedicated.mkdir(mode=0o700)
        os.chown(dedicated, self.uid, -1)
        managed_keys = dedicated / "authorized_keys"
        managed_keys.write_text(entry(comment="Ternuxx-only") + "\n")
        managed_keys.chmod(0o600)
        self.keys.write_text(entry(comment="Owner external SSH") + "\n")
        self.keys.chmod(0o600)
        result = ssh_key_inventory.list_managed_authorized_keys(
            home=self.home, uid=self.uid, which=lambda _name: "/fixture/sshd",
            runner=lambda argv, **kwargs: subprocess.CompletedProcess(
                argv, 0, stdout="authorizedkeysfile .ssh/ternuxx-keys/authorized_keys\n", stderr=""))
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["authorized_keys_file"], ".ssh/ternuxx-keys/authorized_keys")
        self.assertEqual(result["key_count"], 1)
        self.assertEqual(result["keys"][0]["label"], "Ternuxx-only")
        self.assertNotIn("Owner external SSH", repr(result))

    def test_managed_inventory_rejects_configured_alternate_key_paths(self):
        config = self.home / ".config/ternuxx/sshd_recovery.conf"
        config.parent.mkdir(parents=True)
        config.write_text("Port 8023\n")
        result = ssh_key_inventory.list_managed_authorized_keys(
            home=self.home, uid=self.uid, which=lambda _name: "/fixture/sshd",
            runner=lambda argv, **kwargs: subprocess.CompletedProcess(
                argv, 0, stdout="authorizedkeysfile /tmp/other_keys\n", stderr=""))
        self.assertEqual(result["status"], "unsupported_path")
        self.assertEqual(result["keys"], [])

    def test_missing_inventory_is_read_only_and_empty(self):
        result = ssh_key_inventory.list_authorized_keys(home=self.home, uid=self.uid)
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["keys"], [])

    def test_lists_only_fingerprints_types_and_sanitized_comments(self):
        self.keys.write_text("# comment\n" + entry(comment="laptop\n\tprivate?\n") + "\n")
        self.keys.chmod(0o600)
        result = ssh_key_inventory.list_authorized_keys(home=self.home, uid=self.uid)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["key_count"], 1)
        self.assertEqual(result["keys"][0]["key_type"], "ssh-ed25519")
        self.assertEqual(result["keys"][0]["label"], "laptop")
        self.assertTrue(result["keys"][0]["fingerprint"].startswith("SHA256:"))
        self.assertNotIn("fixture-key-material", repr(result))
        self.assertNotIn("private?", result["keys"][0]["label"])
        self.assertEqual(ssh_key_inventory._safe_comment("workstation"), "workstation")
        self.assertEqual(ssh_key_inventory._safe_comment("workstation\x00 user"), "workstation  user")

    def test_invalid_entries_counted_but_raw_lines_are_not_returned(self):
        self.keys.write_text("not a key; do not echo\n" + entry() + "\n")
        result = ssh_key_inventory.list_authorized_keys(home=self.home, uid=self.uid)
        self.assertEqual(result["invalid_entries"], 1)
        self.assertNotIn("not a key", repr(result))

    def test_algorithm_looking_comment_is_not_misread_as_a_key(self):
        self.keys.write_text("broken record ssh-ed25519 " + entry().split()[1] + "\n")
        result = ssh_key_inventory.list_authorized_keys(home=self.home, uid=self.uid)
        self.assertEqual(result["key_count"], 0)
        self.assertEqual(result["invalid_entries"], 1)

    def test_algorithm_looking_comment_is_not_misread_as_a_key(self):
        self.keys.write_text("broken record ssh-ed25519 " + entry().split()[1] + "\n")
        result = ssh_key_inventory.list_authorized_keys(home=self.home, uid=self.uid)
        self.assertEqual(result["key_count"], 0)
        self.assertEqual(result["invalid_entries"], 1)

    def test_symlink_file_and_directory_are_rejected(self):
        target = self.ssh_dir / "real"
        target.write_text(entry())
        self.keys.symlink_to(target)
        self.assertEqual(ssh_key_inventory.list_authorized_keys(home=self.home, uid=self.uid)["status"], "unsafe_path")
        self.keys.unlink()
        self.ssh_dir.rename(self.home / "real-ssh")
        self.ssh_dir.symlink_to(self.home / "real-ssh")
        self.assertEqual(ssh_key_inventory.list_authorized_keys(home=self.home, uid=self.uid)["status"], "unsafe_path")

    def test_oversized_file_is_rejected(self):
        self.keys.write_bytes(b"x" * (ssh_key_inventory._MAX_FILE_BYTES + 1))
        self.assertEqual(ssh_key_inventory.list_authorized_keys(home=self.home, uid=self.uid)["status"], "too_large")


if __name__ == "__main__":
    unittest.main()
