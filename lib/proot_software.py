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
    "ai-codex": ("AI: Codex setup recipe + Node.js/npm (agent separate)", ("nodejs", "npm")),
    "ai-hermes": ("AI: Hermes Linux setup recipe (agent separate)", ("curl", "git", "ca-certificates", "libatomic1")),
    "ai-claude": ("AI: Claude Code Linux setup recipe (PRoot only)", ("curl", "ca-certificates")),
    "blender": ("Graphics: Blender 3D creation", ("blender",)),
    "gimp": ("Graphics: GIMP image editor", ("gimp",)),
    "inkscape": ("Graphics: Inkscape vector editor", ("inkscape",)),
    "krita": ("Graphics: Krita painting", ("krita",)),
    "darktable": ("Graphics: Darktable photos", ("darktable",)),
    "rawtherapee": ("Graphics: RawTherapee photos", ("rawtherapee",)),
    "openscad": ("CAD: OpenSCAD", ("openscad",)),
    "freecad": ("CAD: FreeCAD", ("freecad",)),
    "audacity": ("Media: Audacity audio editor", ("audacity",)),
    "kdenlive": ("Media: Kdenlive video editor", ("kdenlive",)),
    "ffmpeg": ("Media: FFmpeg CLI tools", ("ffmpeg",)),
    "mpv": ("Media: mpv video player", ("mpv",)),
    "calc": ("Office: LibreOffice Calc only", ("libreoffice-calc",)),
    "impress": ("Office: LibreOffice Impress only", ("libreoffice-impress",)),
    "abiword": ("Office: AbiWord word processor", ("abiword",)),
    "gnumeric": ("Office: Gnumeric spreadsheets", ("gnumeric",)),
    "geany": ("Development: Geany IDE", ("geany",)),
    "kate": ("Development: Kate editor", ("kate",)),
    "meld": ("Development: Meld diff", ("meld",)),
    "neovim": ("Development: Neovim", ("neovim",)),
    "nodejs": ("Development / AI: Node.js + npm prerequisites", ("nodejs", "npm")),
    "rust": ("Development: Rust and Cargo", ("rustc", "cargo")),
    "golang": ("Development: Go toolchain", ("golang",)),
    "jq": ("Development: jq JSON tools", ("jq",)),
    "sqlite": ("Development: SQLite CLI", ("sqlite3",)),
    "taskmanager": ("System: XFCE task manager", ("xfce4-taskmanager",)),
    "htop": ("System: htop", ("htop",)),
    "ncdu": ("System: ncdu disk usage", ("ncdu",)),
    "lsof": ("System: lsof open files", ("lsof",)),
    "strace": ("System: strace diagnostics", ("strace",)),
    "keepassxc": ("Security: KeePassXC", ("keepassxc",)),
    "rclone": ("Network: Rclone", ("rclone",)),
    "aria2": ("Network: aria2 downloads", ("aria2",)),
    "nmap": ("Network: Nmap diagnostics", ("nmap",)),
    "iperf3": ("Network: iperf3 tools", ("iperf3",)),
    "qbittorrent": ("Internet: qBittorrent", ("qbittorrent",)),
    "gnuplot": ("Science: Gnuplot", ("gnuplot",)),
    "octave": ("Science: GNU Octave", ("octave",)),
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
    runtime = ["libgl1-mesa-dri", "libvulkan1", "mesa-vulkan-drivers", "mesa-utils", "pulseaudio-utils", "vulkan-tools", "x11-utils"]
    if distro == "ubuntu": runtime += ["libegl-mesa0", "libgbm1", "libglx-mesa0"]
    items["account-tools"] = ("Ordinary account setup prerequisites", ("sudo", "passwd"))
    items["cpu-runtime"] = ("CPU rendering and audio runtime (preserve GPU files)", tuple(runtime))
    items["graphics-runtime"] = ("Managed graphics/CPU rendering and sound runtime", tuple(runtime))
    if len(set(selected)) != len(selected) or any(key not in items for key in selected):
        raise ValueError("choose known, unique guest app IDs")
    return list(dict.fromkeys(package for key in selected for package in items[key][1]))
