"""Curated optional guest packages, bound into the pinned install plan."""
from __future__ import annotations

APPS = {
    "browser": ("Web browser", ("firefox-esr",)),
    "music": ("Audacious music player", ("audacious",)),
    "writer": ("LibreOffice Writer only", ("libreoffice-writer",)),
    "images": ("Ristretto image viewer", ("ristretto",)),
    "pdf": ("Evince PDF viewer", ("evince",)),
    "editor": ("Mousepad text editor", ("mousepad",)),
    "archive": ("Xarchiver archive manager", ("xarchiver",)),
    "video": ("VLC media player", ("vlc",)),
}


def catalog(distro: str) -> dict:
    if distro not in {"debian", "ubuntu"}:
        raise ValueError("unsupported managed software provider")
    items = dict(APPS)
    if distro == "ubuntu":
        # Noble's Firefox package delegates to Snap, unavailable in PRoot.
        items["browser"] = ("Epiphany browser (APT; no Snap)", ("epiphany-browser",))
    return items


def packages(distro: str, selected: list[str]) -> list[str]:
    items = catalog(distro)
    runtime = ["libgl1-mesa-dri", "libvulkan1", "mesa-vulkan-drivers", "mesa-utils", "vulkan-tools", "pulseaudio-utils"]
    if distro == "ubuntu": runtime += ["libegl-mesa0", "libgbm1", "libglx-mesa0"]
    items["cpu-runtime"] = ("CPU rendering and audio runtime (preserve GPU files)", tuple(runtime))
    items["graphics-runtime"] = ("Managed graphics/CPU rendering and sound runtime", tuple(runtime))
    if len(set(selected)) != len(selected) or any(key not in items for key in selected):
        raise ValueError("choose known, unique guest app IDs")
    return list(dict.fromkeys(package for key in selected for package in items[key][1]))
