import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
import management_authorization
import management_catalog
import management_service
import management_sessions


class ManagementCatalogTests(unittest.TestCase):
    def test_catalog_distinguishes_implemented_and_planned_providers(self):
        catalog = management_catalog.build_catalog(set(management_service.OPERATIONS))
        domains = {domain["id"]: domain for domain in catalog["domains"]}
        self.assertIn("doctor.report", domains["doctor-diagnostics"]["available_operations"])
        self.assertIn("proot-runtime", domains)
        cloud = next(provider for provider in catalog["providers"] if provider["id"] == "cloud-api")
        self.assertEqual(cloud["status"], "planned-disabled")
        self.assertFalse(catalog["policy"]["external_cloud_calls_enabled"])
        self.assertFalse(catalog["policy"]["credentials_in_catalog"])
        remote_ai = next(resource for resource in catalog["resources"] if resource["id"] == "ai.runtime-providers")
        self.assertEqual(remote_ai["name"], "Remote AI providers")
        self.assertIn("local llama.cpp CPU, Vulkan, and HTP inference are listed separately", remote_ai["description"])

    def test_catalog_and_doctor_are_read_only_shared_operations(self):
        for operation in ("management.catalog", "doctor.report"):
            self.assertEqual(management_authorization.required_capability(operation), "diagnostics.read")
            self.assertIn(operation, management_sessions.READ_ONLY_OPERATIONS)
            self.assertNotIn(operation, management_sessions.MUTATING_OPERATIONS)
            self.assertIn(operation, management_service.OPERATIONS)


    def test_typed_resource_catalog_has_unique_ids_and_truthful_ownership(self):
        catalog = management_catalog.build_catalog(set(management_service.OPERATIONS))
        categories = {item["id"] for item in catalog["categories"]}
        resources = catalog["resources"]
        ids = [item["id"] for item in resources]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(item["category_id"] in categories for item in resources))
        self.assertEqual(catalog["schema_version"], 2)
        by_id = {item["id"]: item for item in resources}
        self.assertEqual(by_id["network.ssh.manual-8022"]["status"], "external")
        self.assertEqual(by_id["network.ssh.manual-8022"]["supported_operations"], ["ssh.inspect"])
        self.assertEqual(by_id["network.ssh.managed-8023"]["configuration"]["defaults"]["port"], 8023)
        self.assertIn("ssh.keys.list", by_id["network.ssh.managed-8023"]["supported_operations"])
        self.assertEqual(by_id["network.ssh.managed-8023"]["operation_capabilities"]["ssh.keys.list"], "ssh.credentials.read")
        self.assertIn("shared Termux account", by_id["network.ssh.managed-8023"]["description"])
        audio = by_id["native.audio.pulseaudio"]
        self.assertEqual(audio["status"], "partial")
        self.assertEqual(audio["ownership"]["authority"], "ternuxx-native-pulse-lifecycle")
        self.assertEqual(audio["supported_operations"], ["doctor.report"])
        self.assertIn("audible output remain unqualified", audio["description"])
        self.assertEqual(by_id["server.generic-deployment"]["status"], "planned")
        graphics = by_id["graphics.native"]
        self.assertIn("KGSL candidate is experimental", graphics["description"])
        self.assertIn("no Ternuxx installer", graphics["description"])
        debian_graphics = by_id["graphics.debian"]
        self.assertEqual(debian_graphics["status"], "external")
        self.assertEqual(debian_graphics["availability"], "guest-graphics-not-managed-or-verified")
        self.assertEqual(debian_graphics["supported_operations"], [])
        self.assertIn("guest is installed", debian_graphics["description"])
        inference = by_id["inference.cpu.local"]
        self.assertEqual(inference["state"]["desired"], "bounded-local-cpu")
        self.assertIn("offline execution has not been verified", inference["description"])
        accelerator = by_id["native.acceleration.qualification"]
        self.assertEqual(accelerator["status"], "partial")
        self.assertEqual(accelerator["supported_operations"], ["doctor.report"])
        self.assertTrue(accelerator["security"]["read_only"])
        self.assertIn("Native Termux", accelerator["description"])
        boot_profile = by_id["boot.termux.profile"]
        self.assertEqual(boot_profile["ownership"]["status"], "managed-generated-script-identity-queried")
        self.assertEqual(boot_profile["identity"]["installed"], "live-query-required")
        self.assertNotIn("mismatch", boot_profile["identity"]["installed"])
        for resource in resources:
            self.assertTrue(set(resource["supported_operations"]).issubset(management_service.OPERATIONS))
            self.assertEqual(set(resource["operation_capabilities"]), set(resource["supported_operations"]))

    def test_catalog_lists_installed_optional_proot_provider_and_resources(self):
        catalog = management_catalog.build_catalog(set(management_service.OPERATIONS))
        domain = next(item for item in catalog["domains"] if item["id"] == "proot-runtime")
        providers = {item["id"]: item for item in catalog["providers"]}
        self.assertEqual(providers["proot-distro"]["status"], "installed-live-acceptance-passed")
        resources = {item["id"]: item for item in catalog["resources"]}
        guest = resources["proot.debian.workloads"]
        self.assertEqual(guest["availability"], "installed-native-proot-debian-guest")
        self.assertIn("proot.start.preview", guest["supported_operations"])
        proot_resource_operations = {
            operation for resource in catalog["resources"]
            if resource["category_id"] == "proot"
            for operation in resource["supported_operations"]
        }
        self.assertEqual(proot_resource_operations, set(domain["available_operations"]))

    def test_catalog_category_query_and_status_filters(self):
        operations = set(management_service.OPERATIONS)
        service = management_catalog.build_catalog(operations, category="services")
        self.assertEqual({item["category_id"] for item in service["resources"]}, {"services"})
        filtered = management_catalog.build_catalog(operations, query="manual")
        self.assertEqual([item["id"] for item in filtered["resources"]], ["network.ssh.manual-8022"])
        planned = management_catalog.build_catalog(operations, status="planned")
        self.assertTrue(planned["resources"])
        self.assertTrue(all(item["status"] == "planned" for item in planned["resources"]))
        with self.assertRaises(ValueError):
            management_catalog.build_catalog(operations, category=[])
        with self.assertRaises(ValueError):
            management_catalog.build_catalog(operations, query="x" * 121)

    def test_catalog_api_accepts_filters_without_live_probes(self):
        env = {"TERMUX_VERSION":"test", "PREFIX":"/data/data/com.termux/files/usr", "HOME":"/tmp", "TERNUXX_STATE_DIR":"/tmp/state"}
        response = management_service.dispatch({"api_version":1,"request_id":"catalog-filter-1234","operation":"management.catalog","args":{"category":"networking"}}, env=env)
        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["filters"]["category"], "networking")
        self.assertTrue(all(item["category_id"] == "networking" for item in response["data"]["resources"]))
        bad = management_service.dispatch({"api_version":1,"request_id":"catalog-filter-5678","operation":"management.catalog","args":{"category":[]}}, env=env)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["error"]["code"], "invalid_arguments")



if __name__ == "__main__":
    unittest.main()
