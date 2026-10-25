"""Exact-version APT size estimate behavior and uncertainty handling."""
import subprocess
import unittest
from unittest import mock

from lib import package_estimates


class PackageEstimateTest(unittest.TestCase):
    def test_aggregate_uses_exact_architecture_and_versions(self):
        records = {
            "cmake=4.4.4": """Package: cmake
Version: 4.4.4
Architecture: aarch64
Size: 12000
Installed-Size: 100

Package: cmake
Version: 4.4.3
Architecture: aarch64
Size: 9000
Installed-Size: 90
""",
            "data=1.0": """Package: data
Version: 1.0
Architecture: all
Size: 2000
Installed-Size: 25
""",
        }

        def run(args, **kwargs):
            if args == ["dpkg", "--print-architecture"]:
                return subprocess.CompletedProcess(args, 0, "aarch64\n", "")
            if args[0:2] == ["apt-cache", "show"]:
                return subprocess.CompletedProcess(args, 0, records.get(args[2], ""), "")
            raise AssertionError(args)

        with mock.patch.object(package_estimates.subprocess, "run", side_effect=run), \
             mock.patch.object(package_estimates.shutil, "disk_usage", return_value=mock.Mock(free=500000)):
            result = package_estimates.estimate("/termux", ["cmake=4.4.4", "data=1.0"])

        self.assertTrue(result["complete"])
        self.assertEqual(result["download_bytes"], 14000)
        self.assertEqual(result["installed_kib"], 125)
        self.assertEqual(result["filesystem_free_bytes"], 500000)
        self.assertEqual([item["status"] for item in result["packages"]], ["estimated", "estimated"])

    def test_missing_or_conflicting_index_metadata_never_becomes_a_total(self):
        payload = """Package: pkg
Version: 2
Architecture: aarch64
Size: 10
Installed-Size: 4

Package: pkg
Version: 2
Architecture: aarch64
Size: 11
Installed-Size: 4
"""
        with mock.patch.object(package_estimates.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, payload, "")):
            result = package_estimates._metadata("pkg", "2", "aarch64")
        self.assertEqual(result["status"], "metadata-unavailable")
        self.assertIsNone(result["download_bytes"])
        self.assertIsNone(result["installed_kib"])

    def test_bad_apt_identifiers_are_not_passed_to_subprocess(self):
        with mock.patch.object(package_estimates.subprocess, "run") as run:
            result = package_estimates._metadata("pkg;touch-bad", "1", "aarch64")
        run.assert_not_called()
        self.assertEqual(result["status"], "invalid-apt-record")


if __name__ == "__main__":
    unittest.main()
