"""Ternuxx-owned desktop environment catalog for supported PRoot adapters."""
from __future__ import annotations

import re
from pathlib import Path

import proot_packages


# Provider package/session mappings are allowlisted here. Display commands are
# never accepted from caller input or passed through a shell.
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
UBUNTU_DESKTOPS = {
    "xfce": {"name": "XFCE", "packages": ("xfce4", "xfce4-terminal"), "session": "startxfce4"},
}
PROVIDERS = {"debian-trixie": DEBIAN_DESKTOPS, "ubuntu-noble": UBUNTU_DESKTOPS}
PACKAGE_DATABASES = {"debian-trixie": "dpkg-status", "ubuntu-noble": "dpkg-status"}
# Required processes for a usable managed session. These are scoped to the
# Ternuxx-owned desktop process group; their presence is not Android visibility.
DESKTOP_READY_PROCESSES = {
    "xfce": ("xfce4-session", "xfwm4", "xfce4-panel", "xfdesktop"),
    "lxqt": ("lxqt-session", "openbox", "lxqt-panel", "pcmanfm-qt"),
    "lxde": ("lxsession", "openbox", "lxpanel", "pcmanfm"),
    "mate": ("mate-session", "marco", "mate-panel", "caja"),
    "plasma": ("startplasma-x11", "kwin_x11", "ksmserver", "plasmashell"),
}


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
    desktops = PROVIDERS.get(provider)
    if desktops is None:
        raise DesktopError("desktop selection is not implemented for this PRoot provider")
    if route not in {None, "standalone", "nested"}:
        raise DesktopError("desktop route must be standalone or nested")
    available = catalog(provider, route=route)
    selected = DEFAULT_DESKTOPS if selected is None else selected
    if (not isinstance(selected, (list, tuple)) or not selected
            or any(not isinstance(item, str) or item not in available for item in selected)
            or len(set(selected)) != len(selected)):
        raise DesktopError("choose one or more route-verified desktop IDs: " + ", ".join(available))
    return tuple(item for item in desktops if item in selected)


def catalog(provider: str, *, route: str | None = None) -> tuple[str, ...]:
    desktops = PROVIDERS.get(provider)
    if desktops is None:
        raise DesktopError("desktop catalog is not implemented for this PRoot provider")
    if route not in {None, "standalone", "nested"}:
        raise DesktopError("desktop route must be standalone or nested")
    return tuple(item for item in desktops
                 if route is None or route in DESKTOP_ROUTES.get(item, frozenset({"standalone", "nested"})))


def packages_for(provider: str, selected: list[str] | tuple[str, ...] | None = None) -> list[str]:
    choices = validate_selection(provider, selected)
    desktops = PROVIDERS[provider]
    # Fresh profiles already include dbus-x11 in their base manifest. Include
    # it here too so adding a desktop to an existing guest installs the same
    # required dbus-launch helper used by the managed session launcher.
    return list(dict.fromkeys(("dbus-x11", "xdotool", "x11-utils", "x11-xserver-utils",
                               *(package for item in choices for package in desktops[item]["packages"]))))


def session_argv(provider: str, selected: str, *, route: str | None = None) -> tuple[str, ...]:
    desktops = PROVIDERS.get(provider, {})
    if selected not in catalog(provider, route=route):
        raise DesktopError("unsupported PRoot desktop selection for this route")
    if provider == "debian-trixie" and selected == "gnome":
        return ("gnome-session", "--session=gnome")
    return (str(desktops[selected]["session"]),)


def session_command(provider: str, selected: str, *, route: str | None = None) -> str:
    """Return the validated entry executable (legacy display label helper)."""
    return session_argv(provider, selected, route=route)[0]


def desktop_id(value: str, provider: str = "debian-trixie") -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", value):
        raise DesktopError("invalid desktop ID")
    if value not in PROVIDERS.get(provider, {}):
        raise DesktopError("unsupported desktop catalog ID")
    return value


def installed_desktops(rootfs: str | Path, provider: str = "debian-trixie") -> list[str]:
    desktops = PROVIDERS.get(provider)
    database = PACKAGE_DATABASES.get(provider)
    if desktops is None or database is None:
        raise DesktopError("desktop inventory is not implemented for this PRoot provider")
    try:
        installed = proot_packages.installed_names(rootfs, database)
    except proot_packages.PackageInventoryError as exc:
        raise DesktopError("guest package inventory is unavailable") from exc
    return [desktop for desktop, spec in desktops.items()
            if all(package in installed for package in spec["packages"])]


def launchable_desktops(installed: list[str] | tuple[str, ...], *, route: str | None = None,
                        provider: str = "debian-trixie") -> list[str]:
    """Return only installed desktop entries with a live-accepted display route."""
    if route not in {None, "standalone", "nested"}:
        raise DesktopError("desktop route must be standalone or nested")
    accepted = set(catalog(provider, route=route))
    return [item for item in installed if item in accepted and DESKTOP_ROUTES.get(item)]
