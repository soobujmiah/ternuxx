"""Ternuxx-owned desktop environment catalog for supported PRoot adapters."""
from __future__ import annotations

import re
from pathlib import Path


# Debian Trixie package and session mappings are allowlisted here. Display
# commands are never accepted from caller input or passed through a shell.
DEBIAN_DESKTOPS = {
    "xfce": {"name": "XFCE", "packages": ("xfce4", "xfce4-terminal"), "session": "startxfce4"},
    "lxqt": {"name": "LXQt", "packages": ("lxqt", "openbox"), "session": "startlxqt"},
    "lxde": {"name": "LXDE", "packages": ("lxde-core",), "session": "startlxde"},
    "mate": {"name": "MATE", "packages": ("mate-desktop-environment-core",), "session": "mate-session"},
    "gnome": {"name": "GNOME", "packages": ("gnome-core",), "session": "gnome-session"},
    "plasma": {"name": "KDE Plasma", "packages": ("kde-plasma-desktop", "kwin-x11"), "session": "startplasma-x11"},
    "cinnamon": {"name": "Cinnamon", "packages": ("cinnamon-desktop-environment",), "session": "cinnamon-session"},
}
DEFAULT_DESKTOPS = ("xfce",)


class DesktopError(ValueError):
    pass


def validate_selection(provider: str, selected: list[str] | tuple[str, ...] | None = None) -> tuple[str, ...]:
    if provider != "debian-trixie":
        raise DesktopError("desktop selection is not implemented for this PRoot provider")
    selected = DEFAULT_DESKTOPS if selected is None else selected
    if (not isinstance(selected, (list, tuple)) or not selected
            or any(not isinstance(item, str) or item not in DEBIAN_DESKTOPS for item in selected)
            or len(set(selected)) != len(selected)):
        raise DesktopError("choose one or more supported Debian desktop IDs: " + ", ".join(DEBIAN_DESKTOPS))
    return tuple(item for item in DEBIAN_DESKTOPS if item in selected)


def catalog(provider: str) -> tuple[str, ...]:
    if provider != "debian-trixie":
        raise DesktopError("desktop catalog is not implemented for this PRoot provider")
    return tuple(DEBIAN_DESKTOPS)


def packages_for(provider: str, selected: list[str] | tuple[str, ...] | None = None) -> list[str]:
    choices = validate_selection(provider, selected)
    return list(dict.fromkeys(package for item in choices for package in DEBIAN_DESKTOPS[item]["packages"]))


def session_argv(provider: str, selected: str) -> tuple[str, ...]:
    if provider != "debian-trixie" or selected not in DEBIAN_DESKTOPS:
        raise DesktopError("unsupported PRoot desktop selection")
    if selected == "gnome":
        return ("gnome-session", "--session=gnome")
    return (str(DEBIAN_DESKTOPS[selected]["session"]),)


def session_command(provider: str, selected: str) -> str:
    """Return the validated entry executable (legacy display label helper)."""
    return session_argv(provider, selected)[0]


def desktop_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", value):
        raise DesktopError("invalid desktop ID")
    if value not in DEBIAN_DESKTOPS:
        raise DesktopError("unsupported Debian desktop ID")
    return value


def installed_desktops(rootfs: str | Path, provider: str = "debian-trixie") -> list[str]:
    if provider != "debian-trixie":
        raise DesktopError("desktop inventory is not implemented for this PRoot provider")
    root = Path(rootfs)
    status = root / "var/lib/dpkg/status"
    try:
        raw = status.read_text(encoding="utf-8")
    except OSError as exc:
        raise DesktopError("guest package inventory is unavailable") from exc
    installed: set[str] = set()
    for paragraph in raw.split("\n\n"):
        fields = {}
        for line in paragraph.splitlines():
            if line and not line[0].isspace() and ":" in line:
                key, value = line.split(":", 1)
                fields[key] = value.strip()
        if fields.get("Status") == "install ok installed":
            installed.add(fields.get("Package", "").split(":", 1)[0])
    return [desktop for desktop, spec in DEBIAN_DESKTOPS.items()
            if all(package in installed for package in spec["packages"])]
