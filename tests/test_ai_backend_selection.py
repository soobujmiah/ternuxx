from __future__ import annotations

import unittest

from lib.ai_backend_selection import select_backend


class AIAutoBackendSelectionTests(unittest.TestCase):
    def test_prefers_usable_htp_over_vulkan(self):
        result = select_backend(
            {"available": True, "device": "HTP0"},
            {"available": True, "devices": [{"id": "Vulkan0", "name": "Adreno"}]},
        )
        self.assertEqual(result["backend"], "npu")
        self.assertEqual(result["device_id"], "HTP0")

    def test_uses_vulkan_when_htp_is_unavailable(self):
        result = select_backend(
            {"available": False, "device": None},
            {"available": True, "devices": [{"id": "Vulkan0", "name": "Adreno"}]},
        )
        self.assertEqual(result["backend"], "vulkan")
        self.assertEqual(result["device_id"], "Vulkan0")

    def test_uses_cpu_only_when_no_accelerator_is_available(self):
        result = select_backend(
            {"available": False, "device": None},
            {"available": False, "devices": []},
        )
        self.assertEqual(result["backend"], "cpu")
        self.assertIsNone(result["device_id"])

    def test_refuses_malformed_gpu_device_entry(self):
        result = select_backend(
            {"available": False},
            {"available": True, "devices": [{"id": "Vulkan0"}]},
        )
        self.assertEqual(result["backend"], "cpu")

    def test_npu_requires_exact_htp0_device(self):
        result = select_backend(
            {"available": True, "device": "HTP1"},
            {"available": False, "devices": []},
        )
        self.assertEqual(result["backend"], "cpu")
