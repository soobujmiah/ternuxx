from __future__ import annotations

import unittest
import ast
from pathlib import Path

from lib import management_presentation


class ManagementPresentationTests(unittest.TestCase):
    def test_operation_labels_have_unique_keys_and_canonical_ssh_label(self):
        source = Path(management_presentation.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        assignment = next(node for node in tree.body if isinstance(node, ast.AnnAssign)
                          and isinstance(node.target, ast.Name)
                          and node.target.id == "OPERATION_LABELS")
        keys = [item.value for item in assignment.value.keys if isinstance(item, ast.Constant)]
        self.assertEqual(len(keys), len(set(keys)), "duplicate presentation label silently overwrites a value")
        self.assertEqual(management_presentation.operation_label("ssh.inspect"), "SSH diagnostics")

    def test_proot_shortcut_inventory_is_compact_and_hides_localized_desktop_metadata(self):
        report = management_presentation.format_report({"ok": True, "data": {
            "resource_id": "proot.x11.shortcuts",
            "items": [{"id": "files", "name": "File manager", "shortcut_state": "absent"}],
            "desktop_applications": {"status": "available", "items": [{
                "desktop_id": "thunar.desktop", "name": "Files", "shortcut_state": "installed",
                "localized_comments": {"en": "This is metadata that should not be shown"},
            }], "diagnostics": [{"reason": "Hidden entry"}]},
        }})
        self.assertIn("Debian shortcuts - 1 fixed, 1 discovered app launchers", report)
        self.assertIn("files — File manager: absent", report)
        self.assertIn("thunar.desktop — Files: installed", report)
        self.assertIn("Discovery diagnostics: 1", report)
        self.assertNotIn("localized_comments", report)
        self.assertNotIn("This is metadata", report)


if __name__ == "__main__":
    unittest.main()
