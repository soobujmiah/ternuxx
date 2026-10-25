from __future__ import annotations

import errno
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import ssh_managed_config  # noqa: E402


POLICY = """port 8023
addressfamily inet
listenaddress 127.0.0.1:8023
passwordauthentication no
kbdinteractiveauthentication no
pubkeyauthentication yes
authenticationmethods publickey
permitrootlogin no
authorizedkeysfile .ssh/ternuxx-keys/authorized_keys
"""


class ManagedSshConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-ssh-config-")
        root = Path(self.temp.name)
        self.home = root / "home"
        self.prefix = root / "prefix"
        self.home.mkdir(mode=0o700)
        self.prefix.mkdir(mode=0o700)
        (self.prefix / "tmp").mkdir(mode=0o700)
        (self.prefix / "etc/ssh").mkdir(parents=True, mode=0o700)
        (self.prefix / "bin").mkdir(mode=0o700)
        ssh_dir = self.home / ".ssh"
        ssh_dir.mkdir(mode=0o700)
        sshd = self.prefix / "bin/sshd"
        sshd.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        sshd.chmod(0o700)
        host_key = self.prefix / "etc/ssh/ssh_host_ed25519_key"
        host_key.write_text("fixture private key placeholder\n", encoding="utf-8")
        host_key.chmod(0o600)
        Path(str(host_key) + ".pub").write_text("fixture public key\n", encoding="utf-8")
        Path(str(host_key) + ".pub").chmod(0o644)
        self.state = self.home / ".local/share/ternuxx"
        self.calls = []
        self.runner = self._runner
        self.probe = self._free_port

    def tearDown(self):
        self.temp.cleanup()

    def _free_port(self, address, timeout):
        raise OSError(errno.ECONNREFUSED, "fixture port free")

    def _runner(self, argv, **kwargs):
        self.calls.append(list(argv))
        if "-T" in argv:
            return subprocess.CompletedProcess(argv, 0, POLICY, "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def _preview(self):
        return ssh_managed_config.preview(prefix=self.prefix, home=self.home,
                                          runner=self.runner, port_probe=self.probe)

    def test_preview_is_read_only_and_plans_isolated_loopback_policy(self):
        system_config = self.prefix / "etc/ssh/sshd_config"
        system_config.write_text("external Native SSH config\n", encoding="utf-8")
        before = system_config.read_bytes()
        result = self._preview()
        self.assertTrue(result["requires_confirmation"])
        self.assertEqual(result["username"], __import__("pwd").getpwuid(os.getuid()).pw_name)
        self.assertEqual(result["authorized_keys"], ".ssh/ternuxx-keys/authorized_keys")
        self.assertEqual(result["effective_policy"]["listenaddress"], "127.0.0.1:8023")
        self.assertFalse((self.home / ssh_managed_config.CONFIG_RELATIVE).exists())
        self.assertFalse((self.home / ".ssh/ternuxx-keys").exists())
        self.assertEqual(system_config.read_bytes(), before)

    def test_apply_creates_private_config_without_touching_external_ssh_files(self):
        system_config = self.prefix / "etc/ssh/sshd_config"
        system_config.write_text("external Native SSH config\n", encoding="utf-8")
        authorized = self.home / ".ssh/authorized_keys"
        authorized.write_text("owner key inventory remains untouched\n", encoding="utf-8")
        preview = self._preview()
        result = ssh_managed_config.apply(prefix=self.prefix, home=self.home, state_dir=self.state,
            confirmed=True, plan_id=preview["plan_id"], runner=self.runner, port_probe=self.probe)
        config = self.home / ssh_managed_config.CONFIG_RELATIVE
        self.assertEqual(result["status"], "configured")
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertIn("PasswordAuthentication no", config.read_text())
        self.assertIn("ListenAddress 127.0.0.1", config.read_text())
        self.assertIn("AuthorizedKeysFile .ssh/ternuxx-keys/authorized_keys", config.read_text())
        self.assertNotIn("8022", config.read_text())
        self.assertEqual((self.home / ".ssh/ternuxx-keys").stat().st_mode & 0o777, 0o700)
        self.assertEqual(authorized.read_text(), "owner key inventory remains untouched\n")
        self.assertEqual(system_config.read_text(), "external Native SSH config\n")

    def test_stale_plan_and_existing_drifted_config_are_refused_without_overwrite(self):
        preview = self._preview()
        with self.assertRaisesRegex(ssh_managed_config.ManagedSshConfigError, "exact"):
            ssh_managed_config.apply(prefix=self.prefix, home=self.home, state_dir=self.state,
                confirmed=True, plan_id="0" * 64, runner=self.runner, port_probe=self.probe)
        config = self.home / ssh_managed_config.CONFIG_RELATIVE
        config.parent.mkdir(parents=True, mode=0o700)
        config.write_text("owner-managed content\n", encoding="utf-8")
        config.chmod(0o600)
        with self.assertRaisesRegex(ssh_managed_config.ManagedSshConfigError, "differs"):
            self._preview()
        self.assertEqual(config.read_text(), "owner-managed content\n")

    def test_port_conflict_fails_closed(self):
        class Connection:
            def close(self): pass
        def occupied(*_args, **_kwargs): return Connection()
        with self.assertRaisesRegex(ssh_managed_config.ManagedSshConfigError, "already accepting"):
            ssh_managed_config.preview(prefix=self.prefix, home=self.home,
                                       runner=self.runner, port_probe=occupied)

    def test_symlinked_ssh_configuration_parent_is_rejected(self):
        outside = self.prefix / "outside"
        outside.mkdir(mode=0o700)
        (self.home / ".config").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ssh_managed_config.ManagedSshConfigError, "identity is unsafe"):
            self._preview()

    def test_non_loopback_or_password_enabled_effective_policy_is_rejected(self):
        def unsafe_runner(argv, **kwargs):
            self.calls.append(list(argv))
            if "-T" in argv:
                return subprocess.CompletedProcess(argv, 0, POLICY.replace("passwordauthentication no", "passwordauthentication yes"), "")
            return subprocess.CompletedProcess(argv, 0, "", "")
        with self.assertRaisesRegex(ssh_managed_config.ManagedSshConfigError, "effective SSH policy"):
            ssh_managed_config.preview(prefix=self.prefix, home=self.home,
                                       runner=unsafe_runner, port_probe=self.probe)

    def test_apply_validation_failure_removes_only_its_new_config_and_journals_failure(self):
        calls = {"effective": 0}
        def runner(argv, **kwargs):
            if "-T" in argv:
                calls["effective"] += 1
                value = POLICY if calls["effective"] <= 2 else POLICY.replace("listenaddress 127.0.0.1:8023", "listenaddress 0.0.0.0:8023")
                return subprocess.CompletedProcess(argv, 0, value, "")
            return subprocess.CompletedProcess(argv, 0, "", "")
        preview = ssh_managed_config.preview(prefix=self.prefix, home=self.home,
                                             runner=runner, port_probe=self.probe)
        with self.assertRaisesRegex(ssh_managed_config.ManagedSshConfigError, "effective SSH policy"):
            ssh_managed_config.apply(prefix=self.prefix, home=self.home, state_dir=self.state,
                confirmed=True, plan_id=preview["plan_id"], runner=runner, port_probe=self.probe)
        self.assertFalse((self.home / ssh_managed_config.CONFIG_RELATIVE).exists())
        self.assertFalse((self.home / ".ssh/ternuxx-keys").exists())


if __name__ == "__main__":
    unittest.main()
