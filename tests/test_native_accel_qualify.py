import json
from argparse import Namespace
from pathlib import Path
import tempfile
import unittest

from tools.native_accel_qualify import (
    QUALIFICATION_CASES,
    _preflight_failure_report,
    collect_preflight,
    active_temperature_limits,
    parse_result,
    process_snapshot,
    qualification_case_for_run,
    read_memavailable_kib,
    read_temperatures,
    resource_violations,
)


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

    def test_temperature_limits_can_be_observed_without_blocking_explicit_run(self):
        args = Namespace(cpu_stop_c=60.0, gpu_stop_c=60.0, htp_stop_c=60.0,
                         battery_stop_c=45.0, socd_stop_c=70.0, ignore_thermal_limits=True)
        self.assertEqual(active_temperature_limits(args), {})
        self.assertEqual(resource_violations({"socd": 90.0, "memavailable_kib": 3 * 1024 * 1024},
                                             active_temperature_limits(args), 2 * 1024 * 1024), [])
        args.ignore_thermal_limits = False
        self.assertEqual(active_temperature_limits(args)["socd"], 70.0)

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

    def test_cpu_pass_requires_an_explicit_integer_zero_gpu_layers(self):
        for value in (None, False, 1):
            with self.subTest(gpu_layers=value):
                result = {"ok": True, "data": {"backend": "CPU", "gpu_layers": value, "output": "4"}}
                self.assertFalse(parse_result(json.dumps(result), "cpu")[0])

    def test_all_backends_require_the_exact_known_answer(self):
        cases = (
            ("cpu", {"backend": "CPU", "gpu_layers": 0}),
            ("vulkan", {"backend": "Vulkan", "gpu_layers": 29, "gpu_total_layers": 29}),
            ("npu", {"backend": "Hexagon HTP", "npu_layers": 29, "total_layers": 29,
                     "silent_fallback": False}),
        )
        for backend, data in cases:
            with self.subTest(backend=backend):
                correct = {"ok": True, "data": {**data, "output": "2 + 2 = 4."}}
                wrong = {"ok": True, "data": {**data, "output": "The answer is 5."}}
                self.assertTrue(parse_result(json.dumps(correct), backend)[0])
                passed, _, error = parse_result(json.dumps(wrong), backend)
                self.assertFalse(passed)
                self.assertIn("expected answer 4", error)

    def test_default_suite_covers_addition_subtraction_and_multiplication(self):
        self.assertEqual([qualification_case_for_run(index).case_id for index in range(1, 4)],
                         [case.case_id for case in QUALIFICATION_CASES])
        self.assertEqual(qualification_case_for_run(4), QUALIFICATION_CASES[0])
        cases = (
            (QUALIFICATION_CASES[0], "2 + 2 = 4."),
            (QUALIFICATION_CASES[1], "9 - 4 = 5."),
            (QUALIFICATION_CASES[2], "3 * 2 = 6."),
        )
        backend_data = {
            "cpu": {"backend": "CPU", "gpu_layers": 0},
            "vulkan": {"backend": "Vulkan", "gpu_layers": 29, "gpu_total_layers": 29},
            "npu": {"backend": "Hexagon HTP", "npu_layers": 29, "total_layers": 29,
                    "silent_fallback": False},
        }
        for backend, data in backend_data.items():
            for case, answer in cases:
                with self.subTest(backend=backend, case=case.case_id):
                    valid = {"ok": True, "data": {**data, "output": answer}}
                    invalid = {"ok": True, "data": {**data, "output": "The answer is wrong."}}
                    self.assertTrue(parse_result(json.dumps(valid), backend, case)[0])
                    self.assertFalse(parse_result(json.dumps(invalid), backend, case)[0])

    def test_guard_report_keeps_suite_and_scheduled_cases_without_claiming_runs(self):
        args = Namespace(backend="vulkan", max_tokens=8, runs=3)
        report = _preflight_failure_report(
            args, "preflight guard failed; no inference started", {"socd": 78.0},
            {"socd": 70.0}, 2 * 1024 * 1024, issues=["socd=78.0 C reached guard 70.0 C"])
        self.assertFalse(report["ok"])
        self.assertEqual(report["completed_runs"], 0)
        self.assertEqual(report["runs"], [])
        self.assertEqual(report["prompt_suite_id"], "arithmetic-operators-v1")
        self.assertEqual(report["scheduled_case_ids"], [case.case_id for case in QUALIFICATION_CASES])


    def test_preflight_only_records_guarded_sample_without_inference(self):
        args = Namespace(backend="npu", cpu_stop_c=60.0, gpu_stop_c=60.0, htp_stop_c=60.0,
                         battery_stop_c=45.0, socd_stop_c=70.0, ignore_thermal_limits=False,
                         minimum_mem_mib=2048, max_tokens=8, runs=3, idle_seconds=5.0)
        snapshot = {"cpu": 42.0, "gpu": 39.0, "htp": 40.0,
                    "battery": 31.0, "socd": 45.0, "memavailable_kib": 4 * 1024 * 1024}
        from unittest.mock import patch
        with patch("tools.native_accel_qualify._snapshot", return_value=snapshot), \
             patch("tools.native_accel_qualify.process_snapshot", return_value={}):
            report = collect_preflight(args)
        self.assertTrue(report["ok"])
        self.assertTrue(report["preflight_only"])
        self.assertFalse(report["will_start_inference"])
        self.assertEqual(report["snapshot"], snapshot)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["completed_runs"], 0)

    def test_preflight_only_fails_closed_on_heat_memory_or_existing_inference(self):
        args = Namespace(backend="npu", cpu_stop_c=60.0, gpu_stop_c=60.0, htp_stop_c=60.0,
                         battery_stop_c=45.0, socd_stop_c=70.0, ignore_thermal_limits=False,
                         minimum_mem_mib=2048, max_tokens=8, runs=3, idle_seconds=5.0)
        snapshot = {"cpu": 60.1, "gpu": 39.0, "htp": 40.0,
                    "battery": 31.0, "socd": 45.0, "memavailable_kib": 1024}
        from unittest.mock import patch
        with patch("tools.native_accel_qualify._snapshot", return_value=snapshot), \
             patch("tools.native_accel_qualify.process_snapshot", return_value={123: 99}):
            report = collect_preflight(args)
        self.assertFalse(report["ok"])
        self.assertFalse(report["will_start_inference"])
        self.assertEqual(report["pids"], [123])
        self.assertGreaterEqual(len(report["issues"]), 3)

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
