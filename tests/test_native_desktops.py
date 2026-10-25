from __future__ import annotations

import unittest

import native_desktops


class NativeDesktopCatalogTests(unittest.TestCase):
    def test_lists_each_supported_provider_with_installed_state(self):
        def which(name):
            return f"/prefix/bin/{name}" if name == "xfce4-session" else None
        items = native_desktops.list_desktops(which)
        self.assertEqual([item["id"] for item in items],
                         ["xfce", "lxqt", "mate", "cinnamon", "plasma"])
        self.assertTrue(items[0]["installed"])
        self.assertTrue(items[0]["default"])
        self.assertFalse(any(item["installed"] for item in items[1:]))

    def test_resolve_requires_known_installed_command(self):
        resolved = native_desktops.resolve("xfce", lambda name: f"/prefix/bin/{name}")
        self.assertEqual(resolved["command"], "/prefix/bin/xfce4-session")
        with self.assertRaisesRegex(ValueError, "not installed"):
            native_desktops.resolve("plasma", lambda _name: None)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            native_desktops.resolve("gnome", lambda _name: "/prefix/bin/gnome-session")


if __name__ == "__main__":
    unittest.main()
