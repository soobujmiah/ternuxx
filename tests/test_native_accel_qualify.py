import json
from pathlib import Path
import tempfile
import unittest

from tools.native_accel_qualify import parse_result, process_snapshot, read_memavailable_kib, read_temperatures, resource_violations


class NativeAccelQualificationTests(unittest.TestCase):
    def test_temperature_zones_are_grouped_and_millidegrees_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures = {
                "thermal_zone0": ("cpu_therm", "43817"),
                "thermal_zone1": ("cpu-2-0-1", "61000"),
                "thermal_zone2": ("gpu-0", "47000"),
                "thermal_zone3": ("nsphvx-0", "53100"),
                "thermal_zone4": ("battery", "41000"),
                "thermal_zone5": ("socd", "65"),
                "thermal_zone6": ("empty", "-273000"),
            }
            for zone, (kind, value) in fixtures.items():
                path = root / zone
                path.mkdir()
                (path / "type").write_text(kind)
                (path / "temp").write_text(value)

            self.assertEqual(read_temperatures(root), {
                "cpu": 61.0, "gpu": 47.0, "htp": 53.1, "battery": 41.0, "socd": 65.0,
            })

    def test_resource_guards_apply_temperature_max_and_memory_min(self):
        limits = {"cpu": 60.0, "gpu": 60.0}
        below = {"cpu": 59.9, "gpu": 40.0, "memavailable_kib": 3 * 1024 * 1024}
        self.assertEqual(resource_violations(below, limits, 2 * 1024 * 1024), [])
        high_cpu = {**below, "cpu": 60.0}
        self.assertIn("cpu=60.0 C reached guard 60.0 C",
                      resource_violations(high_cpu, limits, 2 * 1024 * 1024))
        low_memory = {**below, "memavailable_kib": 2 * 1024 * 1024 - 1}
        self.assertTrue(any("MemAvailable" in item
                            for item in resource_violations(low_memory, limits, 2 * 1024 * 1024)))

    def test_memavailable_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meminfo"
            path.write_text("MemTotal: 100 kB\nMemAvailable: 2048 kB\n")
            self.assertEqual(read_memavailable_kib(path), 2048)
            path.write_text("MemTotal: 100 kB\n")
            self.assertIsNone(read_memavailable_kib(path))

    def test_vulkan_pass_requires_complete_positive_layer_offload(self):
        good = {"ok": True, "data": {"backend": "Vulkan", "gpu_layers": 29,
                "gpu_total_layers": 29, "output": "4"}}
        passed, data, error = parse_result(json.dumps(good), "vulkan")
        self.assertTrue(passed)
        self.assertEqual(data["gpu_layers"], 29)
        self.assertIsNone(error)
        partial = {"ok": True, "data": {"backend": "Vulkan", "gpu_layers": 28,
                   "gpu_total_layers": 29, "output": "4"}}
        self.assertFalse(parse_result(json.dumps(partial), "vulkan")[0])

    def test_htp_pass_requires_full_offload_and_no_silent_fallback(self):
        base = {"backend": "Hexagon HTP", "npu_layers": 29, "total_layers": 29,
                "silent_fallback": False, "output": "4"}
        self.assertTrue(parse_result(json.dumps({"ok": True, "data": base}), "npu")[0])
        fallback = {**base, "silent_fallback": True}
        self.assertFalse(parse_result(json.dumps({"ok": True, "data": fallback}), "npu")[0])

    def test_process_inventory_matches_comm_not_arbitrary_cmdline_text(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            for pid, comm, rss in (("100", "python", "120 kB"), ("101", "llama-cli", "8192 kB")):
                entry = proc / pid
                entry.mkdir()
                (entry / "comm").write_text(comm + "\n")
                (entry / "cmdline").write_text("python mentions llama-cli in script text")
                (entry / "status").write_text("Name:\tprocess\nVmRSS:\t" + rss + "\n")
            self.assertEqual(process_snapshot(proc), {101: 8192})


if __name__ == "__main__":
    unittest.main()
