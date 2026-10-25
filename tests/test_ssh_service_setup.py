from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import ssh_service_setup  # noqa: E402


class SshServiceSetupTests(unittest.TestCase):
    def _preview(self):
        return {"plan_id": "a" * 64, "requires_confirmation": True,
                "config": {"changed": True, "plan_id": "b" * 64},
                "service": {"plan_id": "c" * 64}}

    def test_apply_orders_config_then_fixed_service_then_readiness(self):
        calls = []
        with patch.object(ssh_service_setup, "preview", return_value=self._preview()), \
             patch.object(ssh_service_setup.ssh_managed_config, "apply", side_effect=lambda **_kw: calls.append("config") or {"status": "configured"}), \
             patch.object(ssh_service_setup.fixed_service_deployment, "install", side_effect=lambda **_kw: calls.append("service") or {"status": "running"}), \
             patch.object(ssh_service_setup.ssh_diagnostics, "inspect_native", side_effect=lambda **_kw: calls.append("probe") or {
                 "checks": {"managed_service": {"status": "running", "loopback_ssh_probe": {"status": "ssh_banner"}, "listener_correlation": "unknown"}}}):
            result = ssh_service_setup.apply(prefix="/prefix", home="/home", state_dir="/home/state",
                                             confirmed=True, plan_id="a" * 64)
        self.assertEqual(calls, ["config", "service", "probe"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["readiness"]["authenticated_access"], "not_tested")
        self.assertTrue(result["external_ssh_config_unchanged"])

    def test_wrong_plan_is_rejected_before_mutations(self):
        with patch.object(ssh_service_setup, "preview", return_value=self._preview()), \
             patch.object(ssh_service_setup.ssh_managed_config, "apply") as config_apply, \
             patch.object(ssh_service_setup.fixed_service_deployment, "install") as install:
            with self.assertRaisesRegex(ssh_service_setup.SshSetupError, "exact fresh"):
                ssh_service_setup.apply(prefix="/prefix", home="/home", state_dir="/home/state",
                                        confirmed=True, plan_id="0" * 64)
        config_apply.assert_not_called()
        install.assert_not_called()

    def test_unverified_ssh_readiness_is_reported_as_failure(self):
        with patch.object(ssh_service_setup, "preview", return_value=self._preview()), \
             patch.object(ssh_service_setup.ssh_managed_config, "apply", return_value={"status": "configured"}), \
             patch.object(ssh_service_setup.fixed_service_deployment, "install", return_value={"status": "running"}), \
             patch.object(ssh_service_setup.ssh_diagnostics, "inspect_native", return_value={
                 "checks": {"managed_service": {"status": "running", "loopback_ssh_probe": {"status": "refused"}}}}):
            with self.assertRaisesRegex(ssh_service_setup.SshSetupError, "readiness was not verified"):
                ssh_service_setup.apply(prefix="/prefix", home="/home", state_dir="/home/state",
                                        confirmed=True, plan_id="a" * 64)


if __name__ == "__main__":
    unittest.main()
