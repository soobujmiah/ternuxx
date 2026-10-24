from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_cpuinfo  # noqa: E402


class ProotCpuInfoTests(unittest.TestCase):
    def test_model_names_are_added_per_cpu_without_losing_native_fields(self) -> None:
        cpuinfo = "processor\t: 0\nCPU implementer\t: 0x41\nCPU part\t: 0xd81\n\nprocessor\t: 1\nFeatures\t: asimd\n"
        models = "# CPU,Model name\n0,Cortex-A720\n1,Cortex-X4\n"
        rendered = proot_cpuinfo.render(cpuinfo, models)
        self.assertIn("processor\t: 0\nmodel name\t: Cortex-A720\nCPU implementer", rendered)
        self.assertIn("processor\t: 1\nmodel name\t: Cortex-X4\nFeatures", rendered)

    def test_unmatched_cpu_and_unsafe_model_data_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            proot_cpuinfo.render("processor : 0\n", "# CPU,Model name\n0,\n")
        with self.assertRaises(ValueError):
            proot_cpuinfo.render("processor : 0\n", "0,\x1b[31mfalse\n")

    def test_prepare_requires_private_directory_and_writes_private_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "state"
            output_dir.mkdir(mode=0o700)
            output_dir.chmod(0o700)
            original_run = proot_cpuinfo.subprocess.run
            proot_cpuinfo.subprocess.run = lambda *a, **k: type("R", (), {"stdout": "# CPU,Model name\n0,Cortex-X4\n", "returncode": 0})()
            try:
                original_cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8")
                original_read_text = Path.read_text
                Path.read_text = lambda self, *a, **k: "processor : 0\n" if self == Path("/proc/cpuinfo") else original_read_text(self, *a, **k)
                try:
                    destination = output_dir / "cpuinfo"
                    proot_cpuinfo.prepare(destination)
                finally:
                    Path.read_text = original_read_text
                self.assertIn("model name\t: Cortex-X4", destination.read_text())
                self.assertEqual(os.stat(destination).st_mode & 0o777, 0o600)
            finally:
                proot_cpuinfo.subprocess.run = original_run


if __name__ == "__main__":
    unittest.main()
