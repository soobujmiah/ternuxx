"""Bounded Native X11 geometry discovery for the nested Debian Xephyr display."""
from __future__ import annotations

import os
import re
import shutil
import subprocess


_DIMENSIONS = re.compile(r"^\s*dimensions:\s*(\d+)x(\d+)\s+pixels(?:\s|$)", re.MULTILINE)
_MIN_DIMENSION = 240
_MAX_DIMENSION = 16384
_MAX_PIXELS = 100_000_000


def parse_xdpyinfo_dimensions(output: str) -> tuple[int, int]:
    match = _DIMENSIONS.search(output)
    if not match:
        raise ValueError("Native X11 display dimensions were not reported")
    width, height = (int(match.group(1)), int(match.group(2)))
    if (not _MIN_DIMENSION <= width <= _MAX_DIMENSION
            or not _MIN_DIMENSION <= height <= _MAX_DIMENSION
            or width * height > _MAX_PIXELS):
        raise ValueError("Native X11 display dimensions are outside the supported range")
    return width, height


def query_display_geometry(display: str, *, runner=subprocess.run) -> str:
    if not isinstance(display, str) or not re.fullmatch(r":[0-9]{1,3}(?:\.[0-9]{1,3})?", display):
        raise ValueError("a local X11 display is required")
    tool = shutil.which("xdpyinfo")
    if not tool:
        raise ValueError("xdpyinfo is unavailable in the Debian guest")
    result = runner([tool, "-display", display], env={**os.environ, "DISPLAY": display},
                    capture_output=True, text=True, timeout=10, check=False)
    if result.returncode != 0:
        raise ValueError("Native X11 display geometry could not be queried")
    width, height = parse_xdpyinfo_dimensions(result.stdout)
    return f"{width}x{height}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("usage: proot_gui_geometry.py DISPLAY")
    try:
        print(query_display_geometry(sys.argv[1]))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"proot GUI geometry: {exc}", file=sys.stderr)
        raise SystemExit(1)
