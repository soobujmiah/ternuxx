"""Keep oversized X11 app windows usable across portrait/landscape changes."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          timeout=3).stdout


def _run_on(display: str, *args: str) -> str:
    environment = os.environ.copy()
    environment["DISPLAY"] = display
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          timeout=3, env=environment).stdout


def _numbers(value: str) -> list[int]:
    return [int(item) for item in re.findall(r"-?\d+", value)]


def _display_size(display: str | None = None) -> tuple[int, int]:
    output = (_run_on(display, "xdotool", "getdisplaygeometry") if display
              else _run("xdotool", "getdisplaygeometry"))
    values = _numbers(output)
    if len(values) < 2 or min(values[:2]) <= 0:
        raise ValueError("X11 display geometry is unavailable")
    return values[0], values[1]


def _workarea(width: int, height: int) -> tuple[int, int, int, int]:
    try:
        values = _numbers(_run("xprop", "-root", "_NET_WORKAREA"))
        if len(values) >= 4 and values[2] > 0 and values[3] > 0:
            return values[0], values[1], values[2], values[3]
    except (OSError, subprocess.SubprocessError):
        pass
    inset_x, inset_top, inset_bottom = 8, 44, 12
    return (inset_x, inset_top, max(1, width - inset_x * 2),
            max(1, height - inset_top - inset_bottom))


def _window_ids() -> list[str]:
    try:
        return [item for item in _run("xdotool", "search", "--onlyvisible",
                                      "--class", ".").splitlines()
                if item.isdecimal()]
    except (OSError, subprocess.SubprocessError):
        return []


def _geometry(window: str) -> dict[str, int] | None:
    try:
        raw = _run("xdotool", "getwindowgeometry", "--shell", window)
    except (OSError, subprocess.SubprocessError):
        return None
    values: dict[str, int] = {}
    for line in raw.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"X", "Y", "WIDTH", "HEIGHT"}:
            try:
                values[key] = int(value)
            except ValueError:
                return None
    return values if len(values) == 4 else None


def _properties(window: str) -> str:
    try:
        return _run("xprop", "-id", window, "_NET_WM_STATE",
                    "_NET_WM_WINDOW_TYPE", "_NET_FRAME_EXTENTS",
                    "WM_TRANSIENT_FOR")
    except (OSError, subprocess.SubprocessError):
        return ""


def _state(props: str) -> str:
    match = re.search(r"_NET_WM_STATE\([^)]*\)\s*=\s*([^\n]*)", props)
    return match.group(1) if match else ""


def _window_frame(props: str, geometry: dict[str, int]) -> tuple[int, int, int, int, int, int]:
    match = re.search(r"_NET_FRAME_EXTENTS\([^)]*\)\s*=\s*([^\n]+)", props)
    extents = _numbers(match.group(1)) if match else [0, 0, 0, 0]
    if len(extents) < 4:
        extents = [0, 0, 0, 0]
    left, right, top, bottom = extents[:4]
    return (geometry["X"] - left, geometry["Y"] - top,
            geometry["WIDTH"] + left + right,
            geometry["HEIGHT"] + top + bottom,
            left, top)


def _action(*args: str) -> None:
    try:
        _run("xdotool", *args)
    except (OSError, subprocess.SubprocessError):
        pass


def _fit_windows(attempted: dict[str, tuple[int, ...]],
                 managed: dict[str, tuple[int, int, int, int]], *,
                 parent_display: str | None = None,
                 resize_display: str | None = None,
                 last_frame: tuple[int, int] | None = None) -> tuple[int, int] | None:
    width, height = _display_size()
    if parent_display and resize_display:
        try:
            parent_size = _display_size(parent_display)
        except (OSError, ValueError, subprocess.SubprocessError):
            parent_size = None
        if parent_size and parent_size != last_frame:
            try:
                _run_on(resize_display, "xrandr", "--fb",
                        f"{parent_size[0]}x{parent_size[1]}")
                child_size = _display_size(resize_display)
                width, height = child_size
                last_frame = parent_size if child_size == parent_size else None
            except (OSError, ValueError, subprocess.SubprocessError):
                last_frame = None
    left, top, work_width, work_height = _workarea(width, height)
    right, bottom = left + work_width, top + work_height
    for window in _window_ids():
        geometry = _geometry(window)
        if geometry is None:
            continue
        props = _properties(window)
        if any(kind in props for kind in ("_NET_WM_WINDOW_TYPE_DOCK",
                                           "_NET_WM_WINDOW_TYPE_DESKTOP",
                                           "_NET_WM_WINDOW_TYPE_NOTIFICATION")):
            continue
        x, y = geometry["X"], geometry["Y"]
        window_width, window_height = geometry["WIDTH"], geometry["HEIGHT"]
        frame_x, frame_y, frame_width, frame_height, frame_left, frame_top = _window_frame(props, geometry)
        extents_match = re.search(r"_NET_FRAME_EXTENTS\([^)]*\)\s*=\s*([^\n]+)", props)
        extents = _numbers(extents_match.group(1)) if extents_match else [0, 0, 0, 0]
        if len(extents) < 4:
            extents = [0, 0, 0, 0]
        frame_right, frame_bottom = extents[1], extents[3]
        overflow = (frame_x < left or frame_y < top or
                    frame_x + frame_width > right or frame_y + frame_height > bottom)
        state = _state(props)
        maximized = ("_NET_WM_STATE_MAXIMIZED_VERT" in state and
                     "_NET_WM_STATE_MAXIMIZED_HORZ" in state)
        fullscreen = "_NET_WM_STATE_FULLSCREEN" in state
        if not overflow:
            attempted.pop(window, None)
            original = managed.get(window)
            if original and maximized:
                ox, oy, ow, oh = original
                original_left, original_top = ox - extents[0], oy - extents[2]
                original_fits = (
                    ow + extents[0] + frame_right <= work_width and
                    oh + extents[2] + frame_bottom <= work_height and
                    original_left >= left and original_top >= top and
                    original_left + ow + extents[0] + frame_right <= right and
                    original_top + oh + extents[2] + frame_bottom <= bottom)
                if original_fits:
                    for atom in ("MAXIMIZED_VERT", "MAXIMIZED_HORZ"):
                        _action("windowstate", "--remove", atom, window)
                    _action("windowsize", "--sync", window, str(ow), str(oh))
                    _action("windowmove", "--sync", window, str(ox), str(oy))
                    managed.pop(window, None)
            elif original:
                # The user restored or resized this window manually.
                managed.pop(window, None)
            continue
        signature = (x, y, window_width, window_height, width, height,
                     left, top, work_width, work_height)
        if attempted.get(window) == signature:
            continue
        attempted[window] = signature
        transient = bool(re.search(r"WM_TRANSIENT_FOR\(WINDOW\):\s*window id", props))
        too_large = frame_width > work_width or frame_height > work_height
        if too_large and not transient and not fullscreen:
            if not maximized:
                managed.setdefault(window, (x, y, window_width, window_height))
                _action("windowstate", "--add", "MAXIMIZED_VERT", window)
                _action("windowstate", "--add", "MAXIMIZED_HORZ", window)
        if fullscreen:
            continue
        # Preserve window size when possible; otherwise keep its title bar reachable.
        client_x = (min(max(x, left + frame_left), right - frame_right - window_width)
                    if frame_width <= work_width else left + frame_left)
        client_y = (min(max(y, top + frame_top), bottom - frame_bottom - window_height)
                    if frame_height <= work_height else top + frame_top)
        if client_x != x or client_y != y:
            _action("windowmove", "--sync", window, str(client_x), str(client_y))
    return last_frame


def watch(parent_display: str | None, resize_display: str | None) -> int:
    if not shutil.which("xdotool"):
        print("window fitting unavailable; missing xdotool", file=sys.stderr)
        return 1
    if resize_display and not shutil.which("xrandr"):
        print("nested display resizing unavailable; missing xrandr; fitting visible windows only",
              file=sys.stderr)
        parent_display = resize_display = None
    attempted: dict[str, tuple[int, ...]] = {}
    managed: dict[str, tuple[int, int, int, int]] = {}
    last_frame = None
    while True:
        try:
            last_frame = _fit_windows(attempted, managed,
                                      parent_display=parent_display,
                                      resize_display=resize_display,
                                      last_frame=last_frame)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        time.sleep(1.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--parent-display")
    parser.add_argument("--resize-display")
    args = parser.parse_args()
    if not args.watch or bool(args.parent_display) != bool(args.resize_display):
        parser.error("use --watch and optionally provide both --parent-display and --resize-display")
    raise SystemExit(watch(args.parent_display, args.resize_display))
