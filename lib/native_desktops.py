"""Provider-specific Native Termux desktop session inventory."""
from __future__ import annotations

import shutil


NATIVE_DESKTOPS = {
    "xfce": {"name": "XFCE", "command": "xfce4-session", "package": "xfce4-session", "default": True},
    "mate": {"name": "MATE", "command": "mate-session", "package": "mate-session-manager"},
    "plasma": {"name": "KDE Plasma", "command": "startplasma-x11", "package": "plasma-workspace"},
}


def list_desktops(which=shutil.which) -> list[dict[str, object]]:
    return [{"id": desktop_id, "name": item["name"], "command": item["command"],
             "package": item["package"], "installed": bool(which(item["command"])),
             "default": bool(item.get("default", False))}
            for desktop_id, item in NATIVE_DESKTOPS.items()]


def resolve(desktop_id: str, which=shutil.which) -> dict[str, str | bool]:
    item = NATIVE_DESKTOPS.get(desktop_id)
    if item is None:
        raise ValueError("unsupported Native desktop ID")
    command = which(item["command"])
    if not command:
        raise ValueError(f"{item['name']} is not installed in Native Termux ({item['package']})")
    return {"id": desktop_id, "name": item["name"], "command": command,
            "marker": item["command"], "default": bool(item.get("default", False))}
