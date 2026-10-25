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
    "plasma": {"name": "KDE Plasma", "packages": ("kde-plasma-desktop", "kwin-x11"), "session": "startplasma-x11"},
    "gnome": {"name": "GNOME", "packages": ("gnome-core",), "session": "gnome-session"},
    "cinnamon": {"name": "Cinnamon", "packages": ("cinnamon-desktop-environment",), "session": "cinnamon-session"},
}
DEFAULT_DESKTOPS = ("xfce",)
DESKTOP_ROUTES = {
    "xfce": frozenset({"standalone", "nested"}),
    "lxqt": frozenset({"standalone", "nested"}),
    "lxde": frozenset({"standalone", "nested"}),
    "mate": frozenset({"standalone", "nested"}),
    # Plasma is accepted on standalone :0 only. GNOME and Cinnamon remain
    # install-catalog entries, without an accepted live route in this profile.
    "plasma": frozenset({"standalone"}),
    "gnome": frozenset(),
    "cinnamon": frozenset(),
}


class DesktopError(ValueError):
    pass


def validate_selection(provider: str, selected: list[str] | tuple[str, ...] | None = None, *, route: str | None = None) -> tuple[str, ...]:
    if provider != "debian-trixie":
        raise DesktopError("desktop selection is not implemented for this PRoot provider")
    if route not in {None, "standalone", "nested"}:
        raise DesktopError("desktop route must be standalone or nested")
    available = catalog(provider, route=route)
    selected = DEFAULT_DESKTOPS if selected is None else selected
    if (not isinstance(selected, (list, tuple)) or not selected
            or any(not isinstance(item, str) or item not in available for item in selected)
            or len(set(selected)) != len(selected)):
        raise DesktopError("choose one or more route-verified Debian desktop IDs: " + ", ".join(available))
    return tuple(item for item in DEBIAN_DESKTOPS if item in selected)


def catalog(provider: str, *, route: str | None = None) -> tuple[str, ...]:
    if provider != "debian-trixie":
        raise DesktopError("desktop catalog is not implemented for this PRoot provider")
    if route not in {None, "standalone", "nested"}:
        raise DesktopError("desktop route must be standalone or nested")
    return tuple(item for item in DEBIAN_DESKTOPS
                 if route is None or route in DESKTOP_ROUTES[item])


def packages_for(provider: str, selected: list[str] | tuple[str, ...] | None = None) -> list[str]:
    choices = validate_selection(provider, selected)
    return list(dict.fromkeys(package for item in choices for package in DEBIAN_DESKTOPS[item]["packages"]))


def session_argv(provider: str, selected: str, *, route: str | None = None) -> tuple[str, ...]:
    if provider != "debian-trixie" or selected not in catalog(provider, route=route):
        raise DesktopError("unsupported PRoot desktop selection for this route")
    if selected == "gnome":
        return ("gnome-session", "--session=gnome")
    return (str(DEBIAN_DESKTOPS[selected]["session"]),)


def session_command(provider: str, selected: str, *, route: str | None = None) -> str:
    """Return the validated entry executable (legacy display label helper)."""
    return session_argv(provider, selected, route=route)[0]


def desktop_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", value):
        raise DesktopError("invalid desktop ID")
    if value not in DEBIAN_DESKTOPS:
        raise DesktopError("unsupported Debian desktop catalog ID")
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


def launchable_desktops(installed: list[str] | tuple[str, ...], *, route: str | None = None) -> list[str]:
    """Return only installed desktop entries with a live-accepted display route."""
    if route not in {None, "standalone", "nested"}:
        raise DesktopError("desktop route must be standalone or nested")
    accepted = set(catalog("debian-trixie", route=route))
    return [item for item in installed if item in accepted and DESKTOP_ROUTES.get(item)]
