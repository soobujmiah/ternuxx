from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_packages


class ProotPackageInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-package-db-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_apk_inventory_groups_packages_and_checks_native_architecture(self):
        database = self.root / "lib/apk/db/installed"
        database.parent.mkdir(parents=True)
        database.write_text(
            "P:alpine-baselayout\nV:3.6.8-r0\nA:aarch64\n\n"
            "P:apk-tools\nV:2.14.6-r3\nA:aarch64\n\n"
            "P:wrong-arch\nV:1.0-r0\nA:x86_64\n"
        )
        result = proot_packages.grouped_inventory(self.root, {
            "package_database": "apk-installed", "architecture": "aarch64",
            "packages": {"base": ["alpine-baselayout", "apk-tools", "wrong-arch", "missing"]},
        })
        self.assertEqual(result["package_database"], "apk-installed")
        self.assertRegex(result["package_database_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("dpkg_status_sha256", result)
        self.assertEqual(result["groups"]["base"]["installed"], 2)
        self.assertEqual(result["groups"]["base"]["missing"], ["wrong-arch", "missing"])
        self.assertEqual(result["groups"]["base"]["versions"]["apk-tools"]["version"], "2.14.6-r3")

    def test_dpkg_inventory_preserves_hold_and_legacy_digest_field(self):
        database = self.root / "var/lib/dpkg/status"
        database.parent.mkdir(parents=True)
        database.write_text(
            "Package: mesa-vulkan-drivers\nStatus: hold ok installed\nArchitecture: arm64\nVersion: 25.0.7-2\n\n"
            "Package: unfinished\nStatus: install ok unpacked\nArchitecture: arm64\nVersion: 1.0\n"
        )
        result = proot_packages.grouped_inventory(self.root, {
            "package_database": "dpkg-status", "architecture": "aarch64",
            "packages": {"graphics": ["mesa-vulkan-drivers", "unfinished"]},
        })
        self.assertEqual(result["package_database_sha256"], result["dpkg_status_sha256"])
        self.assertEqual(result["groups"]["graphics"]["held"], ["mesa-vulkan-drivers"])
        self.assertEqual(result["groups"]["graphics"]["missing"], ["unfinished"])

    def test_apk_version_inventory_is_normalized_and_requires_every_requested_package(self):
        database = self.root / "lib/apk/db/installed"
        database.parent.mkdir(parents=True)
        database.write_text(
            "P:apk-tools\nV:2.14.6-r3\nA:aarch64\n\n"
            "P:busybox\nV:1.37.0-r19\nA:aarch64\n"
        )
        rows = proot_packages.version_inventory_text(
            self.root, "apk-installed", ["busybox", "apk-tools"], "aarch64")
        self.assertEqual(rows, "ii \tapk-tools=2.14.6-r3\nii \tbusybox=1.37.0-r19\n")
        with self.assertRaisesRegex(proot_packages.PackageInventoryError, "missing from the installed inventory"):
            proot_packages.version_inventory_text(
                self.root, "apk-installed", ["absent"], "aarch64")

    def test_database_symlink_and_unknown_adapter_are_rejected(self):
        database = self.root / "var/lib/dpkg/status"
        database.parent.mkdir(parents=True)
        target = self.root / "outside"
        target.write_text("Package: bash\nStatus: install ok installed\nArchitecture: arm64\nVersion: 1\n")
        database.symlink_to(target)
        with self.assertRaisesRegex(proot_packages.PackageInventoryError, "symbolic link"):
            proot_packages.installed_packages(self.root, "dpkg-status")
        with self.assertRaisesRegex(proot_packages.PackageInventoryError, "unsupported"):
            proot_packages.installed_packages(self.root, "rpm-query")

    def test_database_parent_symlink_is_rejected(self):
        outside = self.root / "outside-var"
        database = outside / "lib/dpkg/status"
        database.parent.mkdir(parents=True)
        database.write_text("Package: bash\nStatus: install ok installed\nArchitecture: arm64\nVersion: 1\n")
        (self.root / "var").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(proot_packages.PackageInventoryError, "symbolic link"):
            proot_packages.installed_packages(self.root, "dpkg-status")

    def test_desktop_inventory_reuses_package_manager_database_adapter(self):
        import proot_desktops
        database = self.root / "var/lib/dpkg/status"
        database.parent.mkdir(parents=True)
        database.write_text(
            "Package: xfce4\nStatus: install ok installed\nArchitecture: all\nVersion: 4.20\n\n"
            "Package: xfce4-terminal\nStatus: install ok installed\nArchitecture: arm64\nVersion: 1.1\n"
        )
        self.assertEqual(proot_desktops.installed_desktops(self.root), ["xfce"])


if __name__ == "__main__":
    unittest.main()
