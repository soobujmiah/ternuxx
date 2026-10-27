"""Seed managed guest XFCE/VLC defaults while preserving existing user choices."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
import xml.etree.ElementTree as ET

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
XFCE_REL = Path("xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml")
ROUTES = ("proot-display0", "proot-nested-gui")


def _regular(path: Path, root: Path | None = None, limit: int = 2 * 1024 * 1024) -> Path | None:
    try:
        if path.is_symlink():
            return None
        resolved = path.resolve(strict=True)
        if root is not None:
            resolved.relative_to(root.resolve(strict=True))
        info = resolved.stat()
        return resolved if stat.S_ISREG(info.st_mode) and info.st_size <= limit else None
    except (OSError, ValueError):
        return None


def _write(path: Path, content: bytes) -> None:
    if path.is_symlink():
        raise ValueError("refusing to replace a symbolic-link desktop preference")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise ValueError("desktop preference directory is a symbolic link")
    fd, tmp = tempfile.mkstemp(prefix=".ternuxx-", dir=path.parent)
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _ensure_vlc(config_home: Path) -> None:
    path = config_home / "vlc/vlcrc"
    current = _regular(path, limit=8 * 1024 * 1024)
    text = current.read_text(encoding="utf-8", errors="replace") if current else ""
    if re.search(r"(?m)^\s*vout\s*=[^#\s].*$", text):
        return
    _write(path, (text.rstrip("\n") + ("\n" if text.strip() else "") + "vout=xcb_x11\n").encode())


def _image_candidates(config: Path, home: Path) -> tuple[list[Path], int]:
    xml = _regular(config / XFCE_REL, root=home)
    if xml is None:
        return [], 5
    try:
        root = ET.parse(xml).getroot()
    except (OSError, ET.ParseError):
        return [], 5
    paths, style = [], 5
    for node in root.iter("property"):
        name, value = node.get("name"), node.get("value", "")
        if name == "image-style":
            try:
                style = int(value)
            except ValueError:
                style = 5
        if name in {"image-path", "last-image"} and value:
            paths.append(Path(value).expanduser())
    return paths, style if 0 <= style <= 8 else 5


def _wallpaper(configs: list[Path], home: Path, guest_root: Path | None = None) -> tuple[Path | None, int]:
    for config in configs:
        paths, style = _image_candidates(config, home)
        for path in paths:
            if guest_root is not None and path.is_absolute():
                try:
                    path.relative_to(guest_root)
                except ValueError:
                    path = guest_root / path.as_posix().lstrip("/")
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            image = _regular(path, root=home, limit=64 * 1024 * 1024)
            if image is not None:
                return image, style
    return None, 5


def _native_wallpaper(home: Path) -> tuple[Path | None, int]:
    return _wallpaper([home / ".local/share/ternuxx/xfce/config"], home)


def _save_wallpaper(source: Path, home: Path) -> Path:
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:16]
    folder = home / "Pictures/Ternuxx"
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise ValueError("guest wallpaper directory is a symbolic link")
    destination = folder / f"wallpaper-{digest}{source.suffix.lower()}"
    old = _regular(destination, root=home, limit=64 * 1024 * 1024)
    if old is None or hashlib.sha256(old.read_bytes()).hexdigest() != hashlib.sha256(data).hexdigest():
        _write(destination, data)
    return destination


def _prop(parent: ET.Element, name: str, kind: str, value: str) -> ET.Element:
    node = next((item for item in parent.findall("property") if item.get("name") == name), None)
    if node is None:
        node = ET.SubElement(parent, "property", {"name": name, "type": kind})
    node.set("type", kind)
    if kind == "empty":
        node.attrib.pop("value", None)
    else:
        node.set("value", value)
    return node


def _write_wallpaper_config(config: Path, image_value: str, style: int, home: Path) -> None:
    path = config / XFCE_REL
    old = _regular(path, root=home)
    try:
        root = ET.parse(old).getroot() if old else ET.Element("channel", {"name": "xfce4-desktop", "version": "1.0"})
        if root.tag != "channel" or root.get("name") != "xfce4-desktop":
            raise ET.ParseError("invalid xfconf channel")
    except (OSError, ET.ParseError):
        root = ET.Element("channel", {"name": "xfce4-desktop", "version": "1.0"})
    backdrop = _prop(root, "backdrop", "empty", "")
    screen = _prop(backdrop, "screen0", "empty", "")
    for monitor_name in ("monitorbuiltin", "monitor0"):
        monitor = _prop(screen, monitor_name, "empty", "")
        _prop(monitor, "image-path", "string", image_value)
        _prop(monitor, "image-show", "bool", "true")
        _prop(monitor, "image-style", "int", str(style))
        workspace = _prop(monitor, "workspace0", "empty", "")
        _prop(workspace, "last-image", "string", image_value)
        _prop(workspace, "image-style", "int", str(style))
    _write(path, ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n")


def configure_user(home: Path, config_homes: list[Path], *, native_home: Path | None = None,
                   enable_xfce: bool = True, guest_root: Path | None = None) -> dict[str, object]:
    home = home.resolve(strict=True)
    configs = [home / ".config", *config_homes]
    for config in configs:
        try:
            config.resolve(strict=False).relative_to(home)
        except ValueError as exc:
            raise ValueError("guest desktop config path escaped the selected home") from exc
        _ensure_vlc(config)
    wallpaper, style = _wallpaper([*config_homes, home / ".config"], home, guest_root) if enable_xfce else (None, 5)
    if enable_xfce and wallpaper is None and native_home is not None:
        wallpaper, style = _native_wallpaper(native_home)
    if wallpaper is not None:
        copied = _save_wallpaper(wallpaper, home)
        image_value = ("/" + copied.relative_to(guest_root).as_posix()
                       if guest_root is not None else str(copied))
        for config in configs:
            _write_wallpaper_config(config, image_value, style, home)
    return {"vlc_video_output": "xcb_x11", "wallpaper_configured": wallpaper is not None}


def _users(root: Path) -> list[tuple[str, Path]]:
    passwd = _regular(root / "etc/passwd", root=root)
    if passwd is None:
        return []
    found = []
    for line in passwd.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split(":")
        if len(fields) != 7 or not fields[2].isdigit() or not 1000 <= int(fields[2]) < 60000:
            continue
        name, _pw, _uid, _gid, _gecos, raw_home, shell = fields
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", name) or not raw_home.startswith("/home/"):
            continue
        if shell.rsplit("/", 1)[-1] in {"false", "nologin"}:
            continue
        home = root / raw_home.lstrip("/")
        if home.is_symlink() or not home.is_dir():
            continue
        try:
            home.resolve(strict=True).relative_to(root.resolve(strict=True))
        except (OSError, ValueError):
            continue
        found.append((name, home))
    return found


def configure_rootfs(rootfs: str | Path, native_home: str | Path | None = None,
                     user: str | None = None, enable_xfce: bool = True) -> dict[str, object]:
    root = Path(rootfs).resolve(strict=True)
    native = Path(native_home).resolve(strict=True) if native_home else None
    configured = []
    for name, home in _users(root):
        if user is not None and name != user:
            continue
        configs = [home / f".local/share/ternuxx/{route}/xfce/config" for route in ROUTES]
        configured.append({"user": name, **configure_user(home, configs, native_home=native,
                                                       enable_xfce=enable_xfce, guest_root=root)})
    _ensure_vlc(root / "etc/skel/.config")
    return {"configured_user_count": len(configured), "users": configured}


def configure_runtime(home: str, config_home: str) -> dict[str, object]:
    return configure_user(Path(home), [Path(config_home)])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-home", required=True)
    parser.add_argument("--config-home", required=True)
    args = parser.parse_args()
    print(configure_runtime(args.runtime_home, args.config_home))
