from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_desktops


class ProotDesktopCatalogTests(unittest.TestCase):
    def test_debian_desktops_map_to_fixed_packages_and_session_commands(self):
        self.assertEqual(proot_desktops.validate_selection("debian-trixie", ["mate", "lxqt"]),
                         ("lxqt", "mate"))
        self.assertEqual(proot_desktops.packages_for("debian-trixie", ["lxde", "lxqt"]),
                         ["lxqt", "lxde-core"])
        self.assertEqual(proot_desktops.session_command("debian-trixie", "mate"), "mate-session")

    def test_invalid_or_unsupported_selections_fail_closed(self):
        for selection in ([], ["xfce", "xfce"], ["xfce;id"], ["unknown"]):
            with self.subTest(selection=selection), self.assertRaises(proot_desktops.DesktopError):
                proot_desktops.validate_selection("debian-trixie", selection)
        with self.assertRaises(proot_desktops.DesktopError):
            proot_desktops.validate_selection("ubuntu", ["xfce"])
        with self.assertRaises(proot_desktops.DesktopError):
            proot_desktops.session_command("debian-trixie", "$(id)")

    def test_inventory_reports_only_fully_installed_desktop_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status = root / "var/lib/dpkg/status"
            status.parent.mkdir(parents=True)
            status.write_text("Package: xfce4\nStatus: install ok installed\n\n"
                              "Package: lxqt\nStatus: install ok installed\n\n"
                              "Package: lxde-core\nStatus: deinstall ok config-files\n")
            self.assertEqual(proot_desktops.installed_desktops(root), ["xfce", "lxqt"])


if __name__ == "__main__":
    unittest.main()
