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
    if len(set(selected)) != len(selected) or any(key not in items for key in selected):
        raise ValueError("choose known, unique guest app IDs")
    return list(dict.fromkeys(package for key in selected for package in items[key][1]))
