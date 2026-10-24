from __future__ import annotations

import unittest

from lib import management_presentation


class ManagementPresentationTests(unittest.TestCase):
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
