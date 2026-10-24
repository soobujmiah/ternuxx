from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib import proot_gui_geometry


class ProotGuiGeometryTests(unittest.TestCase):
    def test_reads_portrait_native_display_geometry(self) -> None:
        self.assertEqual(proot_gui_geometry.parse_xdpyinfo_dimensions(
            "screen #0:\n  dimensions: 752x1124 pixels (190x284 millimeters)\n"), (752, 1124))

    def test_reads_landscape_native_display_geometry_after_rotation(self) -> None:
        self.assertEqual(proot_gui_geometry.parse_xdpyinfo_dimensions(
            "screen #0:\n  dimensions: 1124x752 pixels (284x190 millimeters)\n"), (1124, 752))

    def test_rejects_missing_or_unbounded_geometry(self) -> None:
        for output in ("screen #0:\n", "dimensions: 0x1124 pixels", "dimensions: 20000x1000 pixels",
                       "dimensions: 12000x9000 pixels"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                proot_gui_geometry.parse_xdpyinfo_dimensions(output)

    def test_queries_local_display_and_returns_xephyr_screen_value(self) -> None:
        def runner(command, **kwargs):
            self.assertEqual(command, ["/usr/bin/xdpyinfo", "-display", ":1"])
            self.assertEqual(kwargs["env"]["DISPLAY"], ":1")
            return SimpleNamespace(returncode=0, stdout="dimensions: 752x1124 pixels\n")

        with patch.object(proot_gui_geometry.shutil, "which", return_value="/usr/bin/xdpyinfo"):
            self.assertEqual(proot_gui_geometry.query_display_geometry(":1", runner=runner), "752x1124")

    def test_rejects_remote_or_unavailable_display(self) -> None:
        with self.assertRaises(ValueError):
            proot_gui_geometry.query_display_geometry("remote:1")
        with patch.object(proot_gui_geometry.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "xdpyinfo is unavailable"):
                proot_gui_geometry.query_display_geometry(":1")


if __name__ == "__main__":
    unittest.main()
