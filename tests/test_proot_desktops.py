from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_desktops


class ProotDesktopCatalogTests(unittest.TestCase):
    def test_catalog_and_session_selection_are_route_specific(self):
        self.assertEqual(proot_desktops.catalog("debian-trixie", route="nested"),
                         ("xfce", "lxqt", "lxde", "mate"))
        self.assertEqual(proot_desktops.catalog("debian-trixie", route="standalone"),
                         ("xfce", "lxqt", "lxde", "mate", "plasma"))
        self.assertEqual(proot_desktops.validate_selection("debian-trixie", ["mate"], route="nested"),
                         ("mate",))
        with self.assertRaisesRegex(proot_desktops.DesktopError, "route-verified"):
            proot_desktops.validate_selection("debian-trixie", ["plasma"], route="nested")
        with self.assertRaisesRegex(proot_desktops.DesktopError, "this route"):
            proot_desktops.session_command("debian-trixie", "plasma", route="nested")

    def test_debian_desktops_map_to_fixed_packages_and_session_commands(self):
        self.assertEqual(proot_desktops.validate_selection("debian-trixie", ["mate", "lxqt"]),
                         ("lxqt", "mate"))
        self.assertEqual(proot_desktops.packages_for("debian-trixie", ["lxde", "lxqt"]),
                         ["lxqt", "openbox", "lxde-core"])
        self.assertEqual(proot_desktops.session_command("debian-trixie", "mate"), "mate-session")
        self.assertEqual(proot_desktops.catalog("debian-trixie"),
                         ("xfce", "lxqt", "lxde", "mate", "plasma", "gnome", "cinnamon"))
        self.assertEqual(proot_desktops.packages_for("debian-trixie", ["gnome"]), ["gnome-core"])
        self.assertEqual(proot_desktops.packages_for("debian-trixie", ["cinnamon"]),
                         ["cinnamon-desktop-environment"])
        self.assertEqual(proot_desktops.validate_selection("debian-trixie", ["plasma"], route="standalone"),
                         ("plasma",))
        for failed in ("gnome", "cinnamon"):
            with self.subTest(desktop=failed), self.assertRaises(proot_desktops.DesktopError):
                proot_desktops.validate_selection("debian-trixie", [failed], route="standalone")
            self.assertEqual(proot_desktops.DESKTOP_ROUTES[failed], frozenset())
        self.assertEqual(proot_desktops.DESKTOP_ROUTES["plasma"], frozenset({"standalone"}))

    def test_invalid_or_unsupported_selections_fail_closed(self):
        for selection in ([], ["xfce", "xfce"], ["xfce;id"], ["unknown"]):
            with self.subTest(selection=selection), self.assertRaises(proot_desktops.DesktopError):
                proot_desktops.validate_selection("debian-trixie", selection)
        self.assertEqual(proot_desktops.validate_selection("ubuntu-noble", ["xfce"]), ("xfce",))
        self.assertEqual(proot_desktops.packages_for("ubuntu-noble", ["xfce"]), ["xfce4", "xfce4-terminal"])
        self.assertEqual(proot_desktops.catalog("ubuntu-noble", route="nested"), ("xfce",))
        with self.assertRaises(proot_desktops.DesktopError):
            proot_desktops.validate_selection("ubuntu-noble", ["lxqt"])
        with self.assertRaises(proot_desktops.DesktopError):
            proot_desktops.session_command("debian-trixie", "$(id)")

    def test_base_profile_does_not_install_an_unselected_desktop(self):
        import json
        manifest = json.loads((ROOT / "config/proot/debian-trixie.json").read_text())
        base = manifest["packages"]["base"]
        self.assertTrue({"xfce4", "xfce4-terminal"}.issubset(base))
        self.assertEqual(proot_desktops.packages_for("debian-trixie", ["lxqt"]), ["lxqt", "openbox"])
        self.assertEqual(proot_desktops.packages_for("debian-trixie", ["plasma"]), ["kde-plasma-desktop", "kwin-x11"])
        setup = __import__("proot_fresh_setup")
        groups = ["base"]
        self.assertEqual(set(setup._workstation_packages(manifest, groups, ("lxqt",))), {"lxqt", "openbox"}.union(
            set(base) - {"xfce4", "xfce4-terminal"}))
        self.assertEqual(set(setup._workstation_packages(manifest, groups, ("xfce",))), set(base))

    def test_installed_plasma_package_is_launchable_only_on_standalone_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status = root / "var/lib/dpkg/status"
            status.parent.mkdir(parents=True)
            status.write_text("Package: kde-plasma-desktop\nStatus: install ok installed\n")
            self.assertNotIn("plasma", proot_desktops.installed_desktops(root))
            with status.open("a", encoding="utf-8") as stream:
                stream.write("\nPackage: kwin-x11\nStatus: install ok installed\n")
            installed = proot_desktops.installed_desktops(root)
            self.assertIn("plasma", installed)
            self.assertIn("plasma", proot_desktops.launchable_desktops(installed))
            self.assertNotIn("plasma", proot_desktops.launchable_desktops(installed, route="nested"))

    def test_inventory_reports_only_fully_installed_desktop_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status = root / "var/lib/dpkg/status"
            status.parent.mkdir(parents=True)
            status.write_text("Package: xfce4\nStatus: install ok installed\n\n"
                              "Package: xfce4-terminal\nStatus: install ok installed\n\n"
                              "Package: lxqt\nStatus: install ok installed\n\n"
                              "Package: openbox\nStatus: install ok installed\n\n"
                              "Package: kde-plasma-desktop\nStatus: install ok installed\n\n"
                              "Package: kwin-x11\nStatus: install ok installed\n\n"
                              "Package: lxde-core\nStatus: deinstall ok config-files\n")
            self.assertEqual(proot_desktops.installed_desktops(root),
                             ["xfce", "lxqt", "plasma"])


if __name__ == "__main__":
    unittest.main()
