from __future__ import annotations

import base64
import contextlib
import io
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import management_authorization
import management_http_runtime
import management_service
import management_sessions
import terminal_ui


def ed25519_public() -> str:
    kind = "ssh-ed25519"
    key = b"x" * 32
    blob = struct.pack(">I", len(kind)) + kind.encode() + struct.pack(">I", len(key)) + key
    return f"{kind} {base64.b64encode(blob).decode()} test-key"


class SshKeyClientContractTests(unittest.TestCase):
    def test_cli_reads_public_key_from_stdin_and_derives_fingerprint_on_server(self):
        key = ed25519_public()
        response = {"ok": True, "operation": "ssh.keys.add.preview",
                    "data": {"fingerprint": "SHA256:redacted", "changed": True}}
        output = io.StringIO()
        with patch.dict(os.environ, {"TERMUX_VERSION": "test",
                "PREFIX": "/data/data/com.termux/files/usr",
                "HOME": "/tmp/fixture-home",
                "TERNUXX_STATE_DIR": "/tmp/fixture-home/.local/share/ternuxx"}), \
             patch.object(sys, "stdin", io.StringIO(key + "\n")), \
             patch.object(sys, "stdout", output), \
             patch.object(management_service, "dispatch", return_value=response) as dispatch:
            result = management_service.main([
                "--operation", "ssh.keys.add.preview", "--public-key-stdin", "--json"])
        self.assertEqual(result, 0)
        request = dispatch.call_args.args[0]
        self.assertEqual(request["args"], {"public_key": key})
        self.assertNotIn(key, output.getvalue())

    def test_ssh_wakelock_policy_cli_and_all_clients_share_the_typed_operation(self):
        response = {"ok": True, "data": {"changed": True, "requires_confirmation": True}}
        with patch.dict(os.environ, {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr", "HOME": "/tmp/home"}), \
             patch("sys.stdout", io.StringIO()), \
             patch.object(management_service, "dispatch", return_value=response) as dispatch:
            self.assertEqual(management_service.main(["--operation", "wakelock.ssh-policy.preview",
                "--ssh-wakelock-disabled", "--json"]), 0)
        self.assertEqual(dispatch.call_args.args[0]["args"], {"enabled": False})
        self.assertEqual(management_authorization.required_capability("wakelock.ssh-policy.status"), "diagnostics.read")
        self.assertEqual(management_authorization.required_capability("wakelock.ssh-policy.apply"), "wakelock.policy.manage")
        self.assertIn("wakelock.ssh-policy.preview", management_sessions.MUTATING_OPERATIONS)
        self.assertIn("wakelock.ssh-policy.apply", management_http_runtime._WEB_MUTATING_OPERATIONS)
        page = (ROOT / "lib/management_web_ui.html").read_text()
        tui = (ROOT / "lib/terminal_ui.py").read_text()
        gtk = (ROOT / "apps/management-center/management-center.c").read_text()
        bridge = (ROOT / "scripts/management_desktop_bridge.py").read_text()
        self.assertIn("Set managed SSH keep-awake preference", page)
        self.assertIn("_wakelock_action(screen)", tui)
        self.assertIn("ssh-wakelock-apply", gtk)
        self.assertIn("wakelock.ssh-policy.apply", bridge)

    def test_cli_ssh_autostart_preview_requires_typed_preference(self):
        response = {"ok": True, "data": {"status": "ready", "changed": True}}
        with patch.dict(os.environ, {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr", "HOME": "/tmp/home"}), \
             patch("sys.stdout", io.StringIO()), \
             patch.object(management_service, "dispatch", return_value=response) as dispatch:
            self.assertEqual(management_service.main(["--operation", "ssh.service.autostart.preview",
                "--autostart-disabled", "--json"]), 0)
        self.assertEqual(dispatch.call_args.args[0]["args"], {"enabled": False})

    def test_cli_client_key_preview_uses_typed_name_argument(self):
        response = {"ok": True, "data": {"status": "ready"}}
        output = io.StringIO()
        with patch.dict(os.environ, {"TERMUX_VERSION": "test",
                "PREFIX": "/data/data/com.termux/files/usr", "HOME": "/tmp/home"}), \
             patch.object(sys, "stdout", output), \
             patch.object(management_service, "dispatch", return_value=response) as dispatch:
            self.assertEqual(management_service.main([
                "--operation", "ssh.client-key.create.preview",
                "--key-name", "recovery8023", "--json"]), 0)
        self.assertEqual(dispatch.call_args.args[0]["args"], {"name": "recovery8023"})

    def test_web_and_session_policies_expose_only_scoped_previewed_key_mutations(self):
        expected = {"ssh.keys.add.preview", "ssh.keys.add.apply",
                    "ssh.keys.remove.preview", "ssh.keys.remove.apply",
                    "ssh.client-key.create.preview", "ssh.client-key.create.apply"}
        autostart_mutations = {"ssh.service.autostart.preview", "ssh.service.autostart.apply"}
        self.assertTrue(expected | autostart_mutations <= management_http_runtime._WEB_MUTATING_OPERATIONS)
        self.assertEqual({management_authorization.required_capability(op) for op in expected},
                         {"ssh.credentials.manage"})
        self.assertTrue(expected | autostart_mutations <= management_sessions.MUTATING_OPERATIONS)
        self.assertEqual(management_authorization.required_capability("ssh.service.autostart.status"), "diagnostics.read")
        page = (ROOT / "lib/management_web_ui.html").read_text()
        self.assertIn("Enroll a public key", page)
        self.assertIn("Remove a key by fingerprint", page)
        self.assertIn("sshKeyPlan(\"ssh.keys.add.preview\"", page)
        self.assertIn("sshKeyPlan(\"ssh.keys.remove.preview\"", page)
        self.assertIn("Ternuxx SSH uses its dedicated authorized-key file", page)
        self.assertIn("sshAffects(preview)", page)
        self.assertNotIn("both owner-managed SSH and Ternuxx SSH", page)

    def test_tui_catalog_lists_only_owned_regular_public_key_files(self):
        with tempfile.TemporaryDirectory(prefix="tui-ssh-keys-") as temp:
            home = Path(temp)
            ssh = home / ".ssh"
            ssh.mkdir(mode=0o700)
            (ssh / "laptop.pub").write_text(ed25519_public() + "\n")
            (ssh / "two-lines.pub").write_text(ed25519_public() + "\n" + ed25519_public() + "\n")
            (ssh / "bad.pub").write_text("not a key\n")
            (ssh / "link.pub").symlink_to(ssh / "laptop.pub")
            os.chown(home, os.getuid(), -1)
            os.chown(ssh, os.getuid(), -1)
            with patch.object(terminal_ui.Path, "home", return_value=home):
                keys = terminal_ui._public_key_catalog()
        self.assertEqual([item["name"] for item in keys], ["laptop.pub"])
        self.assertEqual(keys[0]["key_type"], "ssh-ed25519")

    def test_gtk_key_management_is_in_shared_resource_catalog(self):
        catalog = management_service.dispatch({
            "api_version": 1, "request_id": "gtk-key-catalog-001",
            "operation": "management.catalog", "args": {},
        }, env={"TERMUX_VERSION": "fixture", "PREFIX": "/data/data/com.termux/files/usr",
                "HOME": "/tmp", "TERNUXX_STATE_DIR": "/tmp/.local/share/ternuxx"})
        self.assertTrue(catalog["ok"])
        ssh = next(item for item in catalog["data"]["resources"]
                   if item["id"] == "network.ssh.managed-8023")
        self.assertIn("ssh.keys.add.preview", ssh["supported_operations"])
        self.assertIn("ssh.client-key.create.preview", ssh["supported_operations"])
        self.assertIn("ssh.service.autostart.status", ssh["supported_operations"])
        self.assertIn("ssh.service.autostart.preview", ssh["supported_operations"])
        self.assertIn("ssh.service.autostart.apply", ssh["supported_operations"])
        self.assertTrue({"ssh.keys.rollback.list", "ssh.keys.rollback.preview",
                         "ssh.keys.rollback.apply"} <= set(ssh["supported_operations"]))
        self.assertTrue({"ssh.keys.rollback.preview", "ssh.keys.rollback.apply"}
                        <= management_sessions.MUTATING_OPERATIONS)
        self.assertEqual(management_authorization.required_capability("ssh.keys.rollback.list"),
                         "ssh.credentials.read")
        self.assertEqual(management_authorization.required_capability("ssh.keys.rollback.apply"),
                         "ssh.credentials.manage")
        self.assertTrue({"ssh.keys.rollback.preview", "ssh.keys.rollback.apply"}
                        <= management_http_runtime._WEB_MUTATING_OPERATIONS)
        self.assertIn("Restore a previous SSH key change", (ROOT / "lib/terminal_ui.py").read_text())
        self.assertIn("restoreSshKeyChange", (ROOT / "lib/management_web_ui.html").read_text())
        gtk = (ROOT / "apps/management-center/management-center.c").read_text()
        self.assertIn("Restore previous SSH key change", gtk)
        self.assertIn("ssh-key-rollback-apply", gtk)


    def test_cli_ssh_rollback_uses_typed_id_and_exact_confirmed_plan(self):
        rollback_id = "a" * 32
        plan_id = "b" * 24
        response = {"ok": True, "data": {"status": "ready"}}
        with patch.dict(os.environ, {"TERMUX_VERSION": "test",
                "PREFIX": "/data/data/com.termux/files/usr", "HOME": "/tmp/home"}), \
             patch("sys.stdout", io.StringIO()), \
             patch.object(management_service, "dispatch", return_value=response) as dispatch:
            self.assertEqual(management_service.main([
                "--operation", "ssh.keys.rollback.preview",
                "--operation-id", rollback_id, "--json"]), 0)
            self.assertEqual(dispatch.call_args.args[0]["args"], {"rollback_id": rollback_id})
            self.assertEqual(management_service.main([
                "--operation", "ssh.keys.rollback.apply",
                "--operation-id", rollback_id, "--yes", "--plan-id", plan_id, "--json"]), 0)
            self.assertEqual(dispatch.call_args.args[0]["args"], {
                "rollback_id": rollback_id, "confirmed": True, "plan_id": plan_id})


if __name__ == "__main__":
    unittest.main()
