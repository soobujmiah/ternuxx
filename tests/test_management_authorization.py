"""Default-deny capability policy for future non-CLI adapters."""
from __future__ import annotations

import ast
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import management_authorization  # noqa: E402
import management_service  # noqa: E402


class ManagementAuthorizationTests(unittest.TestCase):
    def test_operation_contract_has_no_silently_overridden_entries(self) -> None:
        tree = ast.parse((ROOT / "lib/management_service.py").read_text(encoding="utf-8"))
        operations = next(node for node in tree.body
                          if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "OPERATIONS"
                                  for target in node.targets))
        self.assertIsInstance(operations.value, ast.Dict)
        keys = [key.value for key in operations.value.keys if isinstance(key, ast.Constant)]
        self.assertEqual(len(keys), len(set(keys)), "duplicate operation silently replaces its contract")

    def test_every_application_operation_has_exactly_one_explicit_scope(self) -> None:
        # Ticket issuance is a transport-only Web operation handled by the
        # authenticated terminal endpoint, not generic management dispatch.
        self.assertEqual(set(management_authorization.OPERATION_CAPABILITIES),
                         set(management_service.OPERATIONS))
        self.assertTrue(all(isinstance(scope, str) and scope and "." in scope
                            for scope in management_authorization.OPERATION_CAPABILITIES.values()))

    def test_every_operation_has_exactly_one_web_session_security_class(self) -> None:
        import management_sessions
        operations = set(management_service.OPERATIONS)
        mutating = management_sessions.MUTATING_OPERATIONS
        read_only = management_sessions.READ_ONLY_OPERATIONS
        self.assertFalse(mutating & read_only, "operation cannot be both read-only and mutating")
        self.assertEqual(operations, mutating | read_only,
                         "every operation must explicitly receive CSRF or read-only classification")

    def test_proot_and_terminal_operations_require_explicit_scopes(self) -> None:
        expected = {"proot.status": "diagnostics.read", "proot.app.launch": "applications.launch",
                    "proot.sessions.health": "diagnostics.read",
                    "proot.shortcuts.apply": "applications.shortcuts.manage",
                    "terminal.start": "proot.session.manage", "terminal.input": "proot.session.manage"}
        for operation, capability in expected.items():
            self.assertEqual(management_authorization.required_capability(operation), capability)
            self.assertFalse(management_authorization.authorize(operation, {"diagnostics.read"})
                             if capability != "diagnostics.read" else
                             management_authorization.authorize(operation, set()))
            self.assertTrue(management_authorization.authorize(operation, {capability}))

    def test_replay_guest_lifecycle_has_a_narrow_scope_separate_from_icd_migration(self) -> None:
        replay_operations = ("proot.setup.retire.preview", "proot.setup.retire.apply",
                            "proot.setup.restore.preview", "proot.setup.restore.apply")
        for operation in replay_operations:
            self.assertEqual(management_authorization.required_capability(operation), "proot.replay.manage")
            self.assertTrue(management_authorization.authorize(operation, {"proot.replay.manage"}))
            self.assertFalse(management_authorization.authorize(operation, {"proot.guest.manage"}))
        for operation in ("proot.setup.icd-migrate.preview", "proot.setup.icd-migrate.apply",
                          "proot.setup.icd-migrate.rollback.preview", "proot.setup.icd-migrate.rollback.apply"):
            self.assertEqual(management_authorization.required_capability(operation), "proot.guest.manage")

    def test_unknown_or_malformed_operation_fails_closed(self) -> None:
        for operation in ("shell.exec", "adb.forward", None, [], {"ssh.inspect": True}):
            self.assertIsNone(management_authorization.required_capability(operation))
            self.assertFalse(management_authorization.authorize(operation, {"diagnostics.read"}))

    def test_ssh_key_inventory_has_separate_read_scope(self) -> None:
        self.assertEqual(management_authorization.required_capability("ssh.keys.list"), "ssh.credentials.read")
        self.assertFalse(management_authorization.authorize("ssh.keys.list", {"diagnostics.read"}))
        self.assertTrue(management_authorization.authorize("ssh.keys.list", {"ssh.credentials.read"}))
        import management_sessions
        self.assertIn("ssh.keys.list", management_sessions.READ_ONLY_OPERATIONS)
        self.assertNotIn("ssh.keys.list", management_sessions.MUTATING_OPERATIONS)

    def test_directory_tree_file_handoff_uses_read_only_diagnostics_scope(self) -> None:
        import management_sessions
        self.assertEqual(management_authorization.required_capability("software.app.run"), "software.manage")
        self.assertFalse(management_authorization.authorize("software.app.run", {"diagnostics.read"}))
        self.assertTrue(management_authorization.authorize("software.app.run", {"software.manage"}))
        self.assertIn("software.app.run", management_sessions.READ_ONLY_OPERATIONS)
        self.assertNotIn("software.app.run", management_sessions.MUTATING_OPERATIONS)

    def test_checkpoint_actions_use_scoped_capability_and_leave_reboot_tests_cli_only(self) -> None:
        import management_sessions
        for operation in ("continuity.prepare.preview", "continuity.prepare", "continuity.verify.preview", "continuity.verify"):
            self.assertEqual(management_authorization.required_capability(operation), "continuity.checkpoint.manage")
        self.assertEqual(management_authorization.required_capability("continuity.prepare-reboot-test"), "continuity.manage")
        self.assertTrue(management_authorization.authorize("continuity.prepare", {"continuity.checkpoint.manage"}))
        self.assertFalse(management_authorization.authorize("continuity.prepare-reboot-test", {"continuity.checkpoint.manage"}))
        self.assertIn("continuity.prepare.preview", management_sessions.READ_ONLY_OPERATIONS)
        self.assertIn("continuity.verify.preview", management_sessions.READ_ONLY_OPERATIONS)
        self.assertIn("continuity.prepare", management_sessions.MUTATING_OPERATIONS)
        self.assertIn("continuity.verify", management_sessions.MUTATING_OPERATIONS)

    def test_grants_are_exact_and_do_not_escalate(self) -> None:
        self.assertTrue(management_authorization.authorize("ssh.inspect", {"diagnostics.read"}))
        self.assertFalse(management_authorization.authorize("ssh.service.stop", {"diagnostics.read"}))
        self.assertFalse(management_authorization.authorize("ssh.inspect", {"services.manage"}))
        self.assertFalse(management_authorization.authorize("ssh.inspect", {"*"}))

    def test_invalid_grant_containers_fail_closed(self) -> None:
        for grants in ("diagnostics.read", b"diagnostics.read", None, 5):
            self.assertFalse(management_authorization.authorize("ssh.inspect", grants))


if __name__ == "__main__":
    unittest.main()
