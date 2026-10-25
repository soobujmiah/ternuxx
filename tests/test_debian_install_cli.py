import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "tx"


class DistroNamedInstallCLITests(unittest.TestCase):
    def test_debian_install_route_requests_account_before_running_preview(self):
        result = subprocess.run(
            ["bash", str(CLI), "install", "debian"],
            env={**os.environ, "TERMUX_VERSION": "fixture"},
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Choose a Debian guest account with --user NAME", result.stderr)
        self.assertNotIn("Unknown install option", result.stderr)

    def test_unknown_generic_guest_route_is_rejected_before_package_probes(self):
        env = {
            **os.environ,
            "TERMUX_VERSION": "fixture",
            "PREFIX": "/tmp/ternuxx-no-guest-install",
            "HOME": "/tmp/ternuxx-no-guest-install-home",
        }
        result = subprocess.run(
            ["bash", str(CLI), "install", "proot", "preview"],
            env=env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown install option", result.stderr)
        self.assertNotIn("proot_setup_present", result.stderr)


if __name__ == "__main__":
    unittest.main()
