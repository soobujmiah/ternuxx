"""Provider-scoped catalog and safe preview/apply for PRoot X11 launchers."""
from __future__ import annotations

import hashlib
import base64
import fcntl
import json
import os
import re
from pathlib import Path
import subprocess
import shlex
import tempfile
import stat
import uuid
from typing import Any


CATALOG: dict[str, dict[str, str]] = {
    "terminal": {
        "name": "PRoot Terminal", "comment": "Open a Debian PRoot terminal in this desktop",
        "icon": "utilities-terminal", "program": "xfce4-terminal",
    },
    "files": {
        "name": "PRoot Files", "comment": "Browse Debian PRoot files in this desktop",
        "icon": "system-file-manager", "program": "thunar",
    },
    "firefox": {
        "name": "PRoot Firefox", "comment": "Browse the web with Debian PRoot Firefox",
        "icon": "firefox", "program": "firefox-esr",
    },
    "blender": {
        "name": "Blender (PRoot)", "comment": "Open Blender from Debian PRoot",
        "icon": "blender", "program": "blender",
    },
    "pavucontrol": {
        "name": "Volume Control (PRoot)", "comment": "Open Debian PulseAudio controls",
        "icon": "multimedia-volume-control", "program": "pavucontrol",
    },
    "system-config-printer": {
        "name": "Print Settings (PRoot)", "comment": "Open Debian printer settings",
        "icon": "printer", "program": "system-config-printer",
    },
    "thunar-bulk-rename": {
        "name": "Bulk Rename (PRoot)", "comment": "Open Debian Thunar bulk rename",
        "icon": "system-file-manager", "program": "thunar",
    },
    "thunar-settings": {
        "name": "Thunar Preferences (PRoot)", "comment": "Open Debian Thunar preferences",
        "icon": "system-file-manager", "program": "thunar-settings",
    },
    "thunar-volman-settings": {
        "name": "Removable Drives and Media (PRoot)", "comment": "Open Debian removable media settings",
        "icon": "drive-removable-media", "program": "thunar-volman-settings",
    },
    "vlc": {
        "name": "VLC media player (PRoot)", "comment": "Open VLC from Debian PRoot",
        "icon": "vlc", "program": "/usr/bin/vlc",
    },
    "xarchiver": {
        "name": "Xarchiver (PRoot)", "comment": "Open Debian archive manager",
        "icon": "package-x-generic", "program": "xarchiver",
    },
    "xfce4-appfinder": {
        "name": "Application Finder (PRoot)", "comment": "Open Debian application finder",
        "icon": "system-search", "program": "xfce4-appfinder",
    },
    "xfce4-terminal-settings": {
        "name": "Xfce Terminal Settings (PRoot)", "comment": "Open Debian terminal preferences",
        "icon": "utilities-terminal", "program": "xfce4-terminal",
    },
    "shortcut-manager": {
        "name": "Manage PRoot Shortcuts", "comment": "Add, remove, and view PRoot app shortcuts",
        "icon": "preferences-desktop", "program": "manager",
    },
}

APP_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "thunar-bulk-rename": ("--bulk-rename",),
    "vlc": ("--started-from-file",),
    "xfce4-terminal-settings": ("--preferences",),
}


class ShortcutError(RuntimeError):
    pass


def _paths(home: str, xdg_data_home: str | None) -> tuple[Path, Path]:
    home_path = Path(home).expanduser().resolve()
    root = Path(xdg_data_home).expanduser() if xdg_data_home else home_path / ".local" / "share"
    if not root.is_absolute():
        root = home_path / root
    root = root.resolve()
    try:
        root.relative_to(home_path)
    except ValueError as exc:
        raise ShortcutError("XDG data directory must remain inside the native home directory") from exc
    app_dir = (root / "applications").resolve()
    try:
        app_dir.relative_to(home_path)
    except ValueError as exc:
        raise ShortcutError("Applications menu directory must remain inside the native home directory") from exc
    return home_path, app_dir


def _target(app_dir: Path, app_id: str) -> Path:
    if app_id not in CATALOG:
        raise ShortcutError("unknown PRoot shortcut ID")
    return app_dir / f"ternuxx-proot-{app_id}.desktop"


def _file_bytes(path: Path) -> bytes | None:
    if path.is_symlink():
        raise ShortcutError("shortcut target is a symbolic link; refusing to follow it")
    if not path.exists():
        return None
    if not path.is_file():
        raise ShortcutError("shortcut target is not a regular file")
    return path.read_bytes()


def _desktop_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return f'"{escaped.replace("%", "%%")}"'


def _entry(app_id: str, *, repo_root: str) -> bytes:
    item = CATALOG[app_id]
    cli = Path(repo_root) / "tx"
    command = f"{_desktop_quote(str(cli))} management app launch {app_id}"
    lines = [
        "[Desktop Entry]", "Version=1.0", "Type=Application",
        f"Name={item['name']}", f"Comment={item['comment']}",
        f"Exec={command}", f"Icon={item['icon']}", "Terminal=false",
        "StartupNotify=true", "Categories=System;X-Ternuxx;",
        "X-Ternuxx-Managed=true", f"X-Ternuxx-App-ID={app_id}",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _legacy_entry(app_id: str, *, prefix: str, repo_root: str) -> bytes:
    """Exact old helper output, recognized for safe migration without overwriting edits."""
    item = CATALOG[app_id]
    if item["program"] == "manager":
        name = "Manage PRoot Shortcuts"
    else:
        name = f"{item['name']} (Ternux)"
    launcher = Path(repo_root) / "scripts" / (
        "proot-x11-shortcut-manager.sh" if item["program"] == "manager" else "proot-x11-app.sh"
    )
    command = f"{prefix}/bin/bash {launcher}"
    if item["program"] != "manager":
        command += f" {item['program']}"
    lines = ["[Desktop Entry]", "Version=1.0", "Type=Application", f"Name={name}",
             f"Comment={item['comment']}", f"Exec={command}", f"Icon={item['icon']}",
             "Terminal=false", "StartupNotify=true", "Categories=System;X-Ternuxx;"]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _managed(existing: bytes | None, app_id: str, *, prefix: str, repo_root: str) -> bool:
    if existing is None:
        return False
    return existing in {
        _entry(app_id, repo_root=repo_root),
        _legacy_entry(app_id, prefix=prefix, repo_root=repo_root),
    }


def _available(app_id: str, *, prefix: str, home: str, path: str, repo_root: str) -> bool:
    if CATALOG[app_id]["program"] == "manager":
        return (Path(repo_root) / "scripts" / "proot-x11-shortcut-manager.sh").is_file()
    try:
        from proot_diagnostics import resolve_proot_guest_user
        user = resolve_proot_guest_user(distro="debian", prefix=prefix)
        probe_env = {key: value for key, value in os.environ.items()
                     if key not in {"ANDROID_ART_ROOT", "ANDROID_DATA", "ANDROID_I18N_ROOT",
                                    "ANDROID_ROOT", "ANDROID_RUNTIME_ROOT", "ANDROID_TZDATA_ROOT",
                                    "BOOTCLASSPATH", "DEX2OATBOOTCLASSPATH", "EXTERNAL_STORAGE"}}
        result = subprocess.run(
            [
                f"{prefix}/bin/proot-distro", "login", "debian", "--shared-tmp",
                "--user", user, "--", "sh", "-c",
                'command -v "$1" >/dev/null 2>&1', "sh", CATALOG[app_id]["program"],
            ],
            env=probe_env, check=False, capture_output=True, timeout=20,
        )
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0



# Keep generated guest launchers out of XFCE's generic Utility/Accessories
# menu. They belong only in the explicit PRoot Apps menu below.
DESKTOP_APP_CATEGORIES = "X-Ternuxx-PRoot;"
_DESKTOP_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\.desktop\Z")


def _guest_app_dir(prefix: str) -> Path:
    root = Path(prefix) / "var/lib/proot-distro/containers/debian/rootfs"
    if root.is_symlink() or not root.is_dir():
        raise ShortcutError("installed Debian rootfs is unavailable or not a regular directory")
    app_dir = root / "usr/share/applications"
    if app_dir.is_symlink() or not app_dir.is_dir():
        raise ShortcutError("Debian application directory is unavailable")
    return app_dir


def _desktop_group(path: Path) -> dict[str, str]:
    import configparser
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
        return dict(parser["Desktop Entry"])
    except (OSError, UnicodeError, KeyError, configparser.Error):
        return {}


def _guest_executable_available(prefix: str, command: str) -> bool:
    if not isinstance(command, str) or not command or "\x00" in command:
        return False
    rootfs = (Path(prefix) / "var/lib/proot-distro/containers/debian/rootfs").resolve()
    if command.startswith("/"):
        candidates = [rootfs / command.lstrip("/")]
    elif "/" in command:
        return False
    else:
        candidates = [rootfs / directory.lstrip("/") / command for directory in
                      ("/usr/local/bin", "/usr/bin", "/bin", "/usr/local/sbin",
                       "/usr/sbin", "/sbin", "/usr/games")]
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(rootfs)
            info = resolved.stat()
        except (OSError, RuntimeError, ValueError):
            continue
        if stat.S_ISREG(info.st_mode) and info.st_mode & 0o111:
            return True
    return False


def inspect_desktop_apps(*, prefix: str) -> dict[str, Any]:
    # Read safe desktop metadata and report visible unsupported entries.
    try:
        app_dir = _guest_app_dir(prefix)
    except ShortcutError as exc:
        return {"status": "unavailable", "items": [],
                "diagnostics": [{"status": "unavailable", "reason": str(exc)}],
                "read_only": True}
    items: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    for path in sorted(app_dir.glob("*.desktop")):
        desktop_id = path.name
        if path.is_symlink() or not path.is_file() or not _DESKTOP_ID.fullmatch(desktop_id):
            diagnostics.append({"desktop_id": desktop_id, "status": "unsupported",
                                "reason": "Desktop entry is not a regular safe file."})
            continue
        entry = _desktop_group(path)
        localized_names = {
            key[5:-1]: value for key, value in entry.items()
            if key.startswith("Name[") and key.endswith("]") and key[5:-1]
        }
        name = entry.get("Name") or next(iter(localized_names.values()), desktop_id)
        hidden = entry.get("Hidden", "false").strip().lower() == "true"
        no_display = entry.get("NoDisplay", "false").strip().lower() == "true"
        if hidden or no_display:
            diagnostics.append({"desktop_id": desktop_id, "name": name,
                                "status": "hidden",
                                "reason": "Desktop entry is intentionally hidden from application menus."})
            continue
        try:
            argv, parsed = _desktop_app_argv(desktop_id, prefix=prefix)
        except ShortcutError as exc:
            diagnostics.append({"desktop_id": desktop_id, "name": name,
                                "status": "unsupported", "reason": str(exc)})
            continue
        try_exec = parsed.get("TryExec", "").strip()
        executable = try_exec or argv[0]
        available = _guest_executable_available(prefix, executable)
        categories = [value for value in parsed.get("Categories", "").split(";") if value]
        item = {
            "desktop_id": desktop_id,
            "name": name,
            "localized_names": localized_names,
            "comment": parsed.get("Comment", ""),
            "localized_comments": {
                key[8:-1]: value for key, value in parsed.items()
                if key.startswith("Comment[") and key.endswith("]") and key[8:-1]
            },
            "icon": parsed.get("Icon", "applications-other"),
            "categories": categories,
            "try_exec": try_exec,
            "executable_available": available,
            "working_directory": parsed.get("Path", ""),
            "terminal_required": parsed.get("Terminal", "false").strip().lower() == "true",
            "status": "available" if available else "unavailable",
            "diagnostic": "" if available else "The desktop command or TryExec target is not an executable in the Debian rootfs.",
            "read_only": True,
        }
        items.append(item)
    return {"status": "available", "items": items, "diagnostics": diagnostics, "read_only": True}


def discover_desktop_apps(*, prefix: str) -> list[dict[str, str]]:
    # Return only visible supported entries safe for generated shortcuts.
    inventory = inspect_desktop_apps(prefix=prefix)
    found: list[dict[str, str]] = []
    for item in inventory["items"]:
        if item["status"] != "available":
            continue
        found.append({
            "desktop_id": item["desktop_id"], "name": item["name"],
            "comment": item["comment"], "icon": item["icon"],
        })
    return found

def _desktop_app_argv(desktop_id: str, *, prefix: str) -> tuple[list[str], dict[str, str]]:
    if not _DESKTOP_ID.fullmatch(desktop_id):
        raise ShortcutError("invalid Debian desktop application ID")
    app_dir = _guest_app_dir(prefix)
    path = app_dir / desktop_id
    if path.is_symlink() or not path.is_file():
        raise ShortcutError("Debian desktop application is no longer installed")
    entry = _desktop_group(path)
    if (entry.get("Type") != "Application" or not entry.get("Exec")
            or entry.get("Hidden", "false").lower() == "true"
            or entry.get("NoDisplay", "false").lower() == "true"
            or entry.get("Terminal", "false").lower() == "true"
            or desktop_id == "xfce4-session-logout.desktop"):
        raise ShortcutError("Debian desktop entry is not an allowed visible GUI application")
    only = {item for item in entry.get("OnlyShowIn", "").split(";") if item}
    excluded = {item for item in entry.get("NotShowIn", "").split(";") if item}
    if (only and "XFCE" not in only) or "XFCE" in excluded:
        raise ShortcutError("Debian desktop entry is not available in XFCE")
    try:
        argv = shlex.split(entry["Exec"], posix=True)
    except ValueError as exc:
        raise ShortcutError("Debian desktop entry has invalid Exec quoting") from exc
    if not argv or not argv[0] or len(argv) > 128:
        raise ShortcutError("Debian desktop entry has an invalid launch command")
    expanded: list[str] = []
    field = re.compile(r"%(.)")
    for token in argv:
        if token in {"%f", "%F", "%u", "%U"}:
            continue
        if token == "%i":
            icon = entry.get("Icon", "")
            if icon:
                expanded.extend(["--icon", icon])
            continue
        def replace(match: re.Match[str]) -> str:
            code = match.group(1)
            if code == "%":
                return "%"
            if code == "c":
                return entry.get("Name", "")
            if code == "k":
                return f"/usr/share/applications/{desktop_id}"
            if code in {"f", "F", "u", "U", "d", "D", "n", "N", "v", "m"}:
                return ""
            raise ShortcutError("Debian desktop entry uses an unsupported field code")
        expanded.append(field.sub(replace, token))
    expanded = [part for part in expanded if part != ""]
    if not expanded:
        raise ShortcutError("Debian desktop entry has no launchable command")
    interpreters = {"sh", "bash", "dash", "zsh", "fish", "busybox", "python", "python2",
                    "python3", "perl", "ruby", "node"}
    for index, token in enumerate(expanded[:-1]):
        if Path(token).name.lower() in interpreters and "-c" in expanded[index + 1:index + 4]:
            raise ShortcutError("shell or interpreter command desktop entries are not launched from shortcuts")
    return expanded, entry


def _safe_desktop_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", " ").replace("\r", " ").replace("\t", " ").replace("\x00", "")


def _dynamic_entry(desktop_id: str, item: dict[str, str], *, cli: str) -> bytes:
    command = f"{_desktop_quote(cli)} mng app launch --desktop-id {_desktop_quote(desktop_id)}"
    lines = [
        "[Desktop Entry]", "Version=1.0", "Type=Application",
        f"Name={_safe_desktop_value(item['name'])} (PRoot)",
        f"Comment={_safe_desktop_value(item.get('comment', ''))}",
        f"Exec={command}", f"Icon={_safe_desktop_value(item.get('icon', 'applications-other'))}",
        "Terminal=false", "StartupNotify=true", f"Categories={DESKTOP_APP_CATEGORIES}",
        "X-Ternuxx-Generated=proot-app-v2", f"X-Ternuxx-Desktop-ID={desktop_id}",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ternuxx-proot-apps-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _sync_desktop_applications_mutate(*, home: str, prefix: str, repo_root: str,
                               xdg_data_home: str | None = None,
                               xdg_config_home: str | None = None) -> dict[str, Any]:
    home_path, app_dir = _paths(home, xdg_data_home)
    config_home = Path(xdg_config_home).expanduser() if xdg_config_home else home_path / ".config"
    if not config_home.is_absolute():
        config_home = home_path / config_home
    config_home = config_home.resolve()
    try:
        config_home.relative_to(home_path)
    except ValueError as exc:
        raise ShortcutError("XDG config directory must remain inside the native home directory") from exc
    items = discover_desktop_apps(prefix=prefix)
    installed_cli = Path(prefix) / "bin" / "tx"
    cli = str(installed_cli if installed_cli.is_file() and os.access(installed_cli, os.X_OK)
              else Path(repo_root) / "tx")
    desired: dict[str, bytes] = {}
    for item in items:
        desktop_id = item["desktop_id"]
        filename = "ternuxx-proot-app-" + desktop_id
        desired[filename] = _dynamic_entry(desktop_id, item, cli=cli)
    app_dir.mkdir(parents=True, exist_ok=True)
    written, conflicts, removed = [], [], []
    for filename, payload in desired.items():
        target = app_dir / filename
        existing = _file_bytes(target)
        if existing == payload:
            continue
        if existing is not None and b"X-Ternuxx-Generated=proot-app" not in existing and b"X-Ternuxx-Generated=proot-app-v2" not in existing:
            conflicts.append(filename)
            continue
        _atomic_write(target, payload)
        written.append(filename)
    for target in app_dir.glob("ternuxx-proot-app-*.desktop"):
        if target.name in desired:
            continue
        raw = _file_bytes(target)
        if raw is not None and (b"X-Ternuxx-Generated=proot-app" in raw or b"X-Ternuxx-Generated=proot-app-v2" in raw):
            target.unlink()
            removed.append(target.name)

    menus = config_home / "menus"
    menu_file = menus / "xfce-applications.menu"
    menu_payload = ('''<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN"
  "http://www.freedesktop.org/standards/menu-spec/1.0/menu.dtd">
<Menu>
  <Name>Xfce</Name>
  <MergeFile type="parent">xfce-applications.menu</MergeFile>
  <Menu>
    <Name>Accessories</Name>
    <Exclude><Category>X-Ternuxx-PRoot</Category></Exclude>
  </Menu>
  <Menu>
    <Name>Accessibility</Name>
    <Exclude><Category>X-Ternuxx-PRoot</Category></Exclude>
  </Menu>
  <Menu>
    <Name>PRoot Apps</Name>
    <Directory>ternuxx-proot-apps.directory</Directory>
    <Include><Category>X-Ternuxx-PRoot</Category></Include>
  </Menu>
</Menu>
''').encode("utf-8")
    directory_file = app_dir.parent / "desktop-directories" / "ternuxx-proot-apps.directory"
    directory_payload = (b"[Desktop Entry]\nType=Directory\nName=PRoot Apps\n"
                         b"Icon=applications-system\nX-Ternuxx-Generated=true\n")
    legacy_directory_payload = (b"[Desktop Entry]\nType=Directory\nName=PRoot Apps\n"
                                b"Icon=applications-system\n")
    menu_status = "unchanged"
    for target, payload in ((menu_file, menu_payload), (directory_file, directory_payload)):
        old = _file_bytes(target)
        if old == payload:
            continue
        owned = (b"X-Ternuxx-PRoot" in old if target == menu_file and old is not None else
                 b"X-Ternuxx-Generated=true" in old if old is not None else False)
        if old is not None and not owned and not (target == directory_file and old == legacy_directory_payload):
            conflicts.append(str(target.relative_to(home_path)))
            continue
        _atomic_write(target, payload)
        menu_status = "updated"
    return {"status": "complete", "discovered": len(items), "written": written,
            "removed": removed, "conflicts": conflicts, "menu": menu_status,
            "desktop_ids": [item["desktop_id"] for item in items], "read_only": False}



def _sync_roots(home: str, xdg_data_home: str | None,
                xdg_config_home: str | None) -> tuple[Path, Path, Path]:
    home_path, app_dir = _paths(home, xdg_data_home)
    config_home = Path(xdg_config_home).expanduser() if xdg_config_home else home_path / ".config"
    if not config_home.is_absolute():
        config_home = home_path / config_home
    config_home = config_home.resolve()
    try:
        config_home.relative_to(home_path)
    except ValueError as exc:
        raise ShortcutError("XDG config directory must remain inside the native home directory") from exc
    return home_path, app_dir, config_home


def _sync_stage(*, home: str, prefix: str, repo_root: str,
                xdg_data_home: str | None, xdg_config_home: str | None
                ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run the existing sync against a private copy and return an exact file plan."""
    import shutil
    actual_home, actual_apps, actual_config = _sync_roots(home, xdg_data_home, xdg_config_home)
    actual_menu = actual_config / "menus" / "xfce-applications.menu"
    actual_directory = actual_apps.parent / "desktop-directories" / "ternuxx-proot-apps.directory"

    def mapped(stage_home: Path, actual: Path) -> Path:
        try:
            relative = actual.relative_to(actual_home)
        except ValueError as exc:
            raise ShortcutError("shortcut sync target escaped the native home directory") from exc
        return stage_home / relative

    with tempfile.TemporaryDirectory(prefix=".ternuxx-shortcut-preview-", dir=actual_home) as temp:
        stage_home = Path(temp) / "home"
        stage_home.mkdir(mode=0o700)
        stage_apps = mapped(stage_home, actual_apps)
        stage_config = mapped(stage_home, actual_config)
        stage_menu = mapped(stage_home, actual_menu)
        stage_directory = mapped(stage_home, actual_directory)

        def copy_target(source: Path, destination: Path) -> None:
            if source.is_symlink():
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(os.readlink(source), destination)
            elif source.exists():
                if not source.is_file():
                    raise ShortcutError("shortcut sync target is not a regular file")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)

        if actual_apps.exists():
            if actual_apps.is_symlink() or not actual_apps.is_dir():
                raise ShortcutError("applications menu directory is not a regular directory")
            for source in actual_apps.glob("ternuxx-proot-app-*.desktop"):
                copy_target(source, stage_apps / source.name)
        copy_target(actual_menu, stage_menu)
        copy_target(actual_directory, stage_directory)

        stage_result = _sync_desktop_applications_mutate(
            home=str(stage_home), prefix=prefix, repo_root=repo_root,
            xdg_data_home=str(mapped(stage_home, actual_apps.parent)),
            xdg_config_home=str(mapped(stage_home, actual_config)),
        )

        staged_files: set[Path] = set()
        if stage_apps.exists():
            staged_files.update(stage_apps.glob("ternuxx-proot-app-*.desktop"))
        for candidate in (stage_menu, stage_directory):
            if candidate.exists() or candidate.is_symlink():
                staged_files.add(candidate)
        actual_files: set[Path] = set()
        if actual_apps.exists():
            actual_files.update(actual_apps.glob("ternuxx-proot-app-*.desktop"))
        for candidate in (actual_menu, actual_directory):
            if candidate.exists() or candidate.is_symlink():
                actual_files.add(candidate)

        pairs: list[dict[str, Any]] = []
        for staged in staged_files | {mapped(stage_home, path) for path in actual_files}:
            actual = actual_home / staged.relative_to(stage_home)
            before = _file_bytes(actual)
            after = _file_bytes(staged)
            if before == after:
                continue
            pairs.append({
                "path": str(actual.relative_to(actual_home)),
                "before_bytes": before,
                "after_bytes": after,
                "before_mode": (actual.stat().st_mode & 0o777) if before is not None else None,
            })
        pairs.sort(key=lambda item: item["path"])
        return stage_result, pairs


def preview_desktop_application_sync(*, home: str, prefix: str, repo_root: str,
                                     xdg_data_home: str | None = None,
                                     xdg_config_home: str | None = None) -> dict[str, Any]:
    stage, pairs = _sync_stage(
        home=home, prefix=prefix, repo_root=repo_root,
        xdg_data_home=xdg_data_home, xdg_config_home=xdg_config_home,
    )
    changes = []
    for item in pairs:
        before, after = item["before_bytes"], item["after_bytes"]
        changes.append({
            "path": item["path"],
            "action": "remove" if after is None else ("create" if before is None else "update"),
            "before": hashlib.sha256(before).hexdigest() if before is not None else "absent",
            "after": hashlib.sha256(after).hexdigest() if after is not None else "absent",
        })
    plan = {"provider": "native_termux", "guest_provider": "proot_debian", "changes": changes}
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    plan_id = hashlib.sha256(canonical).hexdigest()[:24]
    return {
        "resource_id": "proot.x11.shortcut-sync",
        "provider": "proot_debian",
        "storage_provider": "native_termux",
        "status": "preview",
        "discovered": stage.get("discovered", 0),
        "desktop_ids": stage.get("desktop_ids", []),
        "conflicts": stage.get("conflicts", []),
        "changes": changes,
        "changed": bool(changes),
        "requires_confirmation": bool(changes),
        "plan_id": plan_id,
        "read_only": True,
    }




_SYNC_ROLLBACK_MAX_BYTES = 8 * 1024 * 1024
_SYNC_ROLLBACK_MAX_ENTRIES = 512


def _sync_state_root(home: str, state_dir: str | None, *, create: bool) -> Path:
    home_path = Path(home).expanduser().resolve()
    raw = Path(state_dir).expanduser() if state_dir else home_path / ".local/share/ternuxx"
    if not raw.is_absolute():
        raw = home_path / raw
    root = Path(os.path.abspath(raw))
    try:
        relative = root.relative_to(home_path)
    except ValueError as exc:
        raise ShortcutError("shortcut rollback state must remain inside HOME") from exc
    if not relative.parts:
        raise ShortcutError("shortcut rollback state cannot be HOME")
    cursor = home_path
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ShortcutError("shortcut rollback state contains a symbolic link")
        if cursor.exists():
            info = cursor.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise ShortcutError("shortcut rollback state path is not an owned directory")
            if cursor == root and stat.S_IMODE(info.st_mode) != 0o700:
                raise ShortcutError("shortcut rollback state directory is not private")
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
    state = root / "shortcut-sync"
    if create:
        state.mkdir(mode=0o700, exist_ok=True)
        os.chmod(state, 0o700)
    if state.exists():
        info = state.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ShortcutError("shortcut sync journal is not private and owned")
    elif create:
        raise ShortcutError("shortcut sync journal could not be created")
    return state


def _sync_record_path(state: Path, rollback_id: str) -> Path:
    if not isinstance(rollback_id, str) or not re.fullmatch(r"[0-9a-f]{32}", rollback_id):
        raise ShortcutError("invalid shortcut rollback ID")
    return state / (rollback_id + ".json")


def _sync_private_write(path: Path, value: dict[str, Any]) -> None:
    fd, name = tempfile.mkstemp(prefix=".shortcut-sync-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _sync_private_read(path: Path) -> dict[str, Any]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > _SYNC_ROLLBACK_MAX_BYTES * 2):
            raise ShortcutError("shortcut rollback record is unsafe")
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ShortcutError("shortcut rollback record is invalid")
    return value


def _sync_record_changes(record: dict[str, Any], rollback_id: str) -> list[dict[str, Any]]:
    keys = {"schema_version", "rollback_id", "status", "action", "plan_id", "created_at", "changes"}
    if (set(record) != keys or record.get("schema_version") != 1
            or record.get("rollback_id") != rollback_id
            or record.get("status") not in {"prepared", "applied", "rolled_back", "failed", "needs_recovery"}
            or record.get("action") != "bulk_sync" or not isinstance(record.get("plan_id"), str)
            or not isinstance(record.get("created_at"), str) or not isinstance(record.get("changes"), list)
            or len(record["changes"]) > _SYNC_ROLLBACK_MAX_ENTRIES):
        raise ShortcutError("shortcut rollback record fields are invalid")
    total = 0
    fields = {"path", "before_present", "before_b64", "before_sha256", "before_mode", "after_sha256"}
    for item in record["changes"]:
        if not isinstance(item, dict) or set(item) != fields:
            raise ShortcutError("shortcut rollback entry is malformed")
        rel = Path(item["path"]) if isinstance(item["path"], str) else Path("/")
        if (rel.is_absolute() or not rel.parts or any(part in {"", ".", ".."} for part in rel.parts)
                or not (rel.name.startswith("ternuxx-proot-app-") and rel.name.endswith(".desktop")
                        or rel.name in {"xfce-applications.menu", "ternuxx-proot-apps.directory"})):
            raise ShortcutError("shortcut rollback target is outside the managed launcher set")
        if type(item["before_present"]) is not bool or type(item["before_mode"]) is not int:
            raise ShortcutError("shortcut rollback file metadata is invalid")
        if not 0 <= item["before_mode"] <= 0o777 or (not item["before_present"] and item["before_mode"] != 0):
            raise ShortcutError("shortcut rollback file mode is invalid")
        if item["before_sha256"] != "absent" and not re.fullmatch(r"[0-9a-f]{64}", item["before_sha256"]):
            raise ShortcutError("shortcut rollback before-hash is malformed")
        try:
            data = base64.b64decode(item["before_b64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ShortcutError("shortcut rollback snapshot is malformed") from exc
        total += len(data)
        digest = hashlib.sha256(data).hexdigest()
        expected = digest if item["before_present"] else "absent"
        if item["before_sha256"] != expected or (not item["before_present"] and data):
            raise ShortcutError("shortcut rollback snapshot checksum mismatch")
        if item["after_sha256"] != "absent" and not re.fullmatch(r"[0-9a-f]{64}", item["after_sha256"]):
            raise ShortcutError("shortcut rollback after-hash is malformed")
    if total > _SYNC_ROLLBACK_MAX_BYTES:
        raise ShortcutError("shortcut rollback snapshot exceeds the size limit")
    return record["changes"]


def _sync_target(home_path: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(part in {"", ".", ".."} for part in rel.parts):
        raise ShortcutError("shortcut rollback path is invalid")
    target = home_path / rel
    if not target.is_relative_to(home_path):
        raise ShortcutError("shortcut rollback path escaped HOME")
    cursor = home_path
    for part in rel.parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ShortcutError("shortcut rollback parent contains a symbolic link")
        if cursor.exists():
            info = cursor.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise ShortcutError("shortcut rollback parent is not an owned directory")
    if target.is_symlink():
        raise ShortcutError("shortcut rollback target is a symbolic link")
    return target


def _sync_lock(state: Path) -> int:
    lock_path = state / ".lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600):
        os.close(fd)
        raise ShortcutError("shortcut sync lock is unsafe")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def list_desktop_application_sync_rollbacks(*, home: str,
                                            state_dir: str | None = None) -> dict[str, Any]:
    state = _sync_state_root(home, state_dir, create=False)
    if not state.exists():
        return {"resource_id": "proot.x11.shortcut-sync-rollbacks", "rollbacks": [], "read_only": True}
    rows = []
    for path in sorted(state.glob("*.json")):
        if not re.fullmatch(r"[0-9a-f]{32}\.json", path.name):
            continue
        rollback_id = path.stem
        try:
            record = _sync_private_read(path)
            changes = _sync_record_changes(record, rollback_id)
            rows.append({"rollback_id": rollback_id, "status": record["status"],
                         "created_at": record["created_at"], "entry_count": len(changes),
                         "integrity": "valid"})
        except (OSError, ValueError, ShortcutError):
            rows.append({"rollback_id": rollback_id, "integrity": "invalid"})
    return {"resource_id": "proot.x11.shortcut-sync-rollbacks", "rollbacks": rows, "read_only": True}


def preview_desktop_application_sync_rollback(rollback_id: str, *, home: str,
                                               state_dir: str | None = None) -> dict[str, Any]:
    state = _sync_state_root(home, state_dir, create=False)
    record = _sync_private_read(_sync_record_path(state, rollback_id))
    changes = _sync_record_changes(record, rollback_id)
    if record["status"] != "applied":
        raise ShortcutError("only an applied shortcut sync can be restored")
    home_path = Path(home).expanduser().resolve()
    entries = []
    for item in changes:
        target = _sync_target(home_path, item["path"])
        current = _file_bytes(target)
        current_hash = hashlib.sha256(current).hexdigest() if current is not None else "absent"
        if current_hash != item["after_sha256"]:
            raise ShortcutError("shortcut changed after sync; refusing to overwrite it")
        before = base64.b64decode(item["before_b64"], validate=True)
        entries.append({"path": item["path"],
                        "action": "restore" if item["before_present"] else "remove",
                        "current": current_hash,
                        "restore": hashlib.sha256(before).hexdigest() if item["before_present"] else "absent"})
    core = {"rollback_id": rollback_id, "changes": entries}
    plan_id = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    return {"resource_id": "proot.x11.shortcut-sync.rollback", "rollback_id": rollback_id,
            "status": "preview", "changes": entries, "plan_id": plan_id,
            "requires_confirmation": bool(entries), "read_only": True}


def apply_desktop_application_sync_rollback(rollback_id: str, *, home: str, state_dir: str | None = None,
                                            confirmed: bool, plan_id: str | None) -> dict[str, Any]:
    state = _sync_state_root(home, state_dir, create=False)
    fd = _sync_lock(state)
    try:
        preview = preview_desktop_application_sync_rollback(rollback_id, home=home, state_dir=state_dir)
        if not confirmed or not isinstance(plan_id, str):
            return {**preview, "status": "confirmation_required"}
        if plan_id != preview["plan_id"]:
            raise ShortcutError("shortcut rollback target changed or plan ID does not match")
        record_path = _sync_record_path(state, rollback_id)
        record = _sync_private_read(record_path)
        changes = _sync_record_changes(record, rollback_id)
        home_path = Path(home).expanduser().resolve()
        snapshots = []
        for item in changes:
            target = _sync_target(home_path, item["path"])
            current = _file_bytes(target)
            snapshots.append((target, current, target.stat().st_mode & 0o777 if current is not None else None))
        try:
            for item in changes:
                target = _sync_target(home_path, item["path"])
                before = base64.b64decode(item["before_b64"], validate=True)
                if item["before_present"]:
                    _atomic_write(target, before)
                    os.chmod(target, item["before_mode"])
                else:
                    target.unlink(missing_ok=True)
            record["status"] = "rolled_back"
            _sync_private_write(record_path, record)
        except Exception:
            rollback_errors = []
            for target, current, mode in reversed(snapshots):
                try:
                    if current is None:
                        target.unlink(missing_ok=True)
                    else:
                        _atomic_write(target, current)
                        if mode is not None:
                            os.chmod(target, mode)
                except OSError:
                    rollback_errors.append(str(target))
            if rollback_errors:
                record["status"] = "needs_recovery"
                _sync_private_write(record_path, record)
                raise ShortcutError("shortcut rollback failed and needs recovery")
            raise
        return {**preview, "status": "complete", "changed": True, "read_only": False}
    finally:
        os.close(fd)


def apply_desktop_application_sync(*, home: str, prefix: str, repo_root: str,
                                   confirmed: bool, plan_id: str | None,
                                   xdg_data_home: str | None = None,
                                   xdg_config_home: str | None = None,
                                   state_dir: str | None = None) -> dict[str, Any]:
    preview = preview_desktop_application_sync(
        home=home, prefix=prefix, repo_root=repo_root,
        xdg_data_home=xdg_data_home, xdg_config_home=xdg_config_home,
    )
    if not preview["changed"]:
        return {**preview, "status": "already_in_requested_state"}
    if not confirmed or not isinstance(plan_id, str):
        return {**preview, "status": "confirmation_required"}
    if plan_id != preview["plan_id"]:
        raise ShortcutError("shortcut sync state changed or plan ID does not match the current preview")

    state = _sync_state_root(home, state_dir, create=True)
    lock_fd = _sync_lock(state)
    try:
        current = preview_desktop_application_sync(
            home=home, prefix=prefix, repo_root=repo_root,
            xdg_data_home=xdg_data_home, xdg_config_home=xdg_config_home,
        )
        if current["plan_id"] != plan_id:
            raise ShortcutError("shortcut sync state changed or plan ID does not match the current preview")
        _stage, pairs = _sync_stage(
            home=home, prefix=prefix, repo_root=repo_root,
            xdg_data_home=xdg_data_home, xdg_config_home=xdg_config_home,
        )
        changes = []
        total = 0
        for item in pairs:
            before, after = item["before_bytes"], item["after_bytes"]
            total += len(before or b"")
            changes.append({
                "path": item["path"], "before_present": before is not None,
                "before_b64": base64.b64encode(before or b"").decode("ascii"),
                "before_sha256": hashlib.sha256(before).hexdigest() if before is not None else "absent",
                "before_mode": item["before_mode"] if before is not None else 0,
                "after_sha256": hashlib.sha256(after).hexdigest() if after is not None else "absent",
            })
        if len(changes) > _SYNC_ROLLBACK_MAX_ENTRIES or total > _SYNC_ROLLBACK_MAX_BYTES:
            raise ShortcutError("shortcut sync exceeds the durable rollback limits")
        rollback_id = uuid.uuid4().hex
        from datetime import datetime, timezone
        record = {"schema_version": 1, "rollback_id": rollback_id, "status": "prepared",
                  "action": "bulk_sync", "plan_id": plan_id,
                  "created_at": datetime.now(timezone.utc).isoformat(), "changes": changes}
        record_path = _sync_record_path(state, rollback_id)
        _sync_record_changes(record, rollback_id)
        _sync_private_write(record_path, record)
        try:
            result = _sync_desktop_applications_mutate(
                home=home, prefix=prefix, repo_root=repo_root,
                xdg_data_home=xdg_data_home, xdg_config_home=xdg_config_home,
            )
            for item in changes:
                target = _sync_target(Path(home).expanduser().resolve(), item["path"])
                current_bytes = _file_bytes(target)
                current_hash = hashlib.sha256(current_bytes).hexdigest() if current_bytes is not None else "absent"
                if current_hash != item["after_sha256"]:
                    raise ShortcutError("shortcut sync result differs from the journaled plan")
            record["status"] = "applied"
            _sync_private_write(record_path, record)
        except Exception:
            restore_errors = []
            for item in reversed(changes):
                try:
                    target = _sync_target(Path(home).expanduser().resolve(), item["path"])
                    before = base64.b64decode(item["before_b64"], validate=True)
                    if item["before_present"]:
                        _atomic_write(target, before)
                        os.chmod(target, item["before_mode"])
                    else:
                        target.unlink(missing_ok=True)
                except OSError as exc:
                    restore_errors.append(str(exc))
            record["status"] = "needs_recovery" if restore_errors else "failed"
            _sync_private_write(record_path, record)
            if restore_errors:
                raise ShortcutError("shortcut sync failed and durable rollback needs recovery")
            raise
        return {**preview, "status": "complete", "changed": True, "rollback_id": rollback_id,
                "written": result.get("written", []), "removed": result.get("removed", []),
                "conflicts": result.get("conflicts", []), "menu": result.get("menu"),
                "read_only": False}
    finally:
        os.close(lock_fd)

def launch_desktop_application(desktop_id: str, *, prefix: str, repo_root: str,
                               env: dict[str, str], display: str | None = None) -> dict[str, Any]:
    argv, _entry_data = _desktop_app_argv(desktop_id, prefix=prefix)
    if display is not None and not re.fullmatch(r":[0-9]{1,2}", display):
        raise ShortcutError("unsupported X11 display")
    script = Path(repo_root) / "scripts" / "proot-x11-app.sh"
    command = [f"{prefix}/bin/bash", str(script)]
    if display is not None:
        command += ["--display", display]
    command += ["--", *argv]
    result = subprocess.run(command, env=env, check=False)
    if result.returncode != 0:
        raise ShortcutError("the PRoot GUI application did not complete successfully")
    return {"resource_id": f"proot.x11.app.{desktop_id}", "provider": "proot_debian",
            "status": "process_exited", "exit_status": result.returncode,
            "gui_visible": "unknown", "read_only": False}

def list_shortcuts(*, home: str, prefix: str, xdg_data_home: str | None = None,
                   repo_root: str | None = None) -> dict[str, Any]:
    _, app_dir = _paths(home, xdg_data_home)
    repo_root = repo_root or str(Path(__file__).resolve().parents[1])
    items = []
    for app_id, item in CATALOG.items():
        path = _target(app_dir, app_id)
        raw = _file_bytes(path)
        if raw is None:
            state = "absent"
        elif _managed(raw, app_id, prefix=prefix, repo_root=repo_root):
            state = "installed"
        else:
            state = "conflict"
        items.append({
            "id": app_id, "name": item["name"], "provider": "proot_debian",
            "shortcut_owner": "native_termux", "shortcut_state": state,
            "application_availability": "unknown", "read_only": True,
        })
    dynamic = inspect_desktop_apps(prefix=prefix)
    if dynamic["status"] == "available":
        cli = str(Path(prefix) / "bin" / "tx")
        if not (Path(cli).is_file() and os.access(cli, os.X_OK)):
            cli = str(Path(repo_root) / "tx")
        for item in dynamic["items"]:
            target = app_dir / ("ternuxx-proot-app-" + item["desktop_id"])
            try:
                raw = _file_bytes(target)
            except ShortcutError:
                item["shortcut_state"] = "conflict"
                item["shortcut_owner"] = "unknown"
                item["shortcut_diagnostic"] = "A symbolic link or non-file occupies this shortcut name."
                continue
            expected = _dynamic_entry(item["desktop_id"], item, cli=cli)
            owned = (raw is not None
                     and b"X-Ternuxx-Generated=proot-app-v2" in raw
                     and f"X-Ternuxx-Desktop-ID={item['desktop_id']}".encode() in raw)
            item["shortcut_state"] = ("absent" if raw is None else
                                      "installed" if raw == expected else
                                      "modified" if owned else "conflict")
            item["shortcut_owner"] = "ternuxx" if owned else ("none" if raw is None else "unknown")
    return {"resource_id": "proot.x11.shortcuts", "items": items,
            "desktop_applications": dynamic, "read_only": True}


def _dynamic_shortcut_details(desktop_id: str, *, home: str, prefix: str,
                              repo_root: str, xdg_data_home: str | None,
                              allow_unavailable: bool = False) -> tuple[Path, Path, dict[str, Any], bytes]:
    if not isinstance(desktop_id, str) or not _DESKTOP_ID.fullmatch(desktop_id):
        raise ShortcutError("invalid Debian desktop application ID")
    inventory = inspect_desktop_apps(prefix=prefix)
    allowed_states = {"available", "unavailable"} if allow_unavailable else {"available"}
    item = next((row for row in inventory.get("items", [])
                 if row.get("desktop_id") == desktop_id and row.get("status") in allowed_states), None)
    if item is None:
        raise ShortcutError("Debian desktop application is no longer available")
    home_path, app_dir = _paths(home, xdg_data_home)
    target = app_dir / ("ternuxx-proot-app-" + desktop_id)
    cli = str(Path(prefix) / "bin" / "tx")
    if not (Path(cli).is_file() and os.access(cli, os.X_OK)):
        cli = str(Path(repo_root) / "tx")
    return home_path, target, item, _dynamic_entry(desktop_id, item, cli=cli)


def preview(action: str, app_id: str | None = None, *, home: str, prefix: str, repo_root: str,
            xdg_data_home: str | None = None, path: str = "",
            desktop_id: str | None = None) -> dict[str, Any]:
    if (action not in {"add", "remove"}
            or (app_id is None) == (desktop_id is None)
            or (app_id is not None and not isinstance(app_id, str))):
        raise ShortcutError("shortcut action and exactly one app ID are required")
    dynamic = desktop_id is not None
    if dynamic:
        home_path, target, item, desired = _dynamic_shortcut_details(
            desktop_id, home=home, prefix=prefix, repo_root=repo_root,
            xdg_data_home=xdg_data_home, allow_unavailable=(action == "remove"))
        app_id = desktop_id
        existing = _file_bytes(target)
        managed = existing == desired
        # Never replace or remove a user-edited/unowned desktop file.
        if existing is not None and not managed:
            raise ShortcutError("the existing launcher is modified or not Ternuxx-owned; it was preserved")
    else:
        if app_id not in CATALOG:
            raise ShortcutError("shortcut action or ID is unsupported")
        home_path, app_dir = _paths(home, xdg_data_home)
        target = _target(app_dir, app_id)
        existing = _file_bytes(target)
        desired = _entry(app_id, repo_root=repo_root)
        managed = _managed(existing, app_id, prefix=prefix, repo_root=repo_root)
    if existing is not None and action == "add" and existing != desired and not managed:
        raise ShortcutError("a non-Ternuxx launcher already uses this shortcut ID; it was preserved")
    if existing is not None and action == "remove" and not managed:
        raise ShortcutError("the target is not a Ternuxx-managed launcher; it was preserved")
    if action == "add" and existing is None and not dynamic and not _available(
        app_id, prefix=prefix, home=str(home_path), path=path, repo_root=repo_root,
    ):
        raise ShortcutError("the PRoot application or launcher manager is unavailable")
    changed = (action == "add" and existing != desired) or (action == "remove" and existing is not None)
    before = hashlib.sha256(existing).hexdigest() if existing is not None else "absent"
    plan = {"provider": "proot_debian", "action": action,
            ("desktop_id" if dynamic else "app_id"): app_id,
            "target": str(target.relative_to(home_path)), "before": before,
            "after": hashlib.sha256(desired).hexdigest() if action == "add" else "absent"}
    canonical_plan = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    plan_id = hashlib.sha256(canonical_plan).hexdigest()[:24]
    return {"resource_id": f"proot.x11.shortcut.{app_id}", "provider": "proot_debian",
            "storage_provider": "native_termux", "action": action,
            ("desktop_id" if dynamic else "app_id"): app_id,
            "name": item["name"] if dynamic else CATALOG[app_id]["name"],
            "changed": changed, "requires_confirmation": changed, "plan_id": plan_id,
            "affected_resources": [{"provider": "native_termux", "path": str(target.relative_to(home_path)),
                                     "before": "absent" if existing is None else "present",
                                     "after": "present" if action == "add" else "absent"}],
            "safety": {"read_only": True, "running_apps_stopped": False}}


def apply(action: str, app_id: str | None = None, *, home: str, prefix: str, repo_root: str,
          confirmed: bool, plan_id: str | None, xdg_data_home: str | None = None,
          path: str = "", state_dir: str | None = None,
          desktop_id: str | None = None) -> dict[str, Any]:
    initial = preview(action, app_id, home=home, prefix=prefix, repo_root=repo_root,
                      xdg_data_home=xdg_data_home, path=path, desktop_id=desktop_id)
    if not initial["changed"]:
        return {**initial, "status": "already_in_requested_state"}
    if not confirmed or not isinstance(plan_id, str):
        return {**initial, "status": "confirmation_required"}
    if plan_id != initial["plan_id"]:
        raise ShortcutError("shortcut state changed or plan ID does not match the current preview")

    # Individual add/remove and bulk sync/rollback share one inter-process lock.
    state = _sync_state_root(home, state_dir, create=True)
    lock_fd = _sync_lock(state)
    try:
        current = preview(action, app_id, home=home, prefix=prefix, repo_root=repo_root,
                          xdg_data_home=xdg_data_home, path=path, desktop_id=desktop_id)
        if not current["changed"]:
            return {**current, "status": "already_in_requested_state"}
        if plan_id != current["plan_id"]:
            raise ShortcutError("shortcut state changed or plan ID does not match the current preview")
        _, app_dir = _paths(home, xdg_data_home)
        if desktop_id is not None:
            _, target, _item, dynamic_payload = _dynamic_shortcut_details(
                desktop_id, home=home, prefix=prefix, repo_root=repo_root,
                xdg_data_home=xdg_data_home, allow_unavailable=(action == "remove"))
            payload = dynamic_payload
        else:
            target = _target(app_dir, app_id)
            payload = _entry(app_id, repo_root=repo_root)
        app_dir.mkdir(parents=True, exist_ok=True)
        if action == "remove":
            target.unlink()
        else:
            fd, temporary = tempfile.mkstemp(prefix=".ternuxx-shortcut-", dir=app_dir)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, 0o644)
                os.replace(temporary, target)
            finally:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
        return {**current, "status": "complete", "changed": True,
                "safety": {"read_only": False, "running_apps_stopped": False}}
    finally:
        os.close(lock_fd)

def launch(app_id: str, *, prefix: str, repo_root: str, env: dict[str, str],
           display: str | None = None) -> dict[str, Any]:
    if app_id not in CATALOG:
        raise ShortcutError("unknown PRoot application ID")
    if display is not None and not re.fullmatch(r":[0-9]{1,2}", display):
        raise ShortcutError("unsupported X11 display")
    if CATALOG[app_id]["program"] == "manager":
        script = Path(repo_root) / "scripts" / "proot-x11-shortcut-manager.sh"
        command = [f"{prefix}/bin/bash", str(script)]
    else:
        script = Path(repo_root) / "scripts" / "proot-x11-app.sh"
        command = [f"{prefix}/bin/bash", str(script)]
        if display is not None:
            command += ["--display", display]
        command += [CATALOG[app_id]["program"], *APP_ARGUMENTS.get(app_id, ())]
    result = subprocess.run(command, env=env, check=False)
    if result.returncode != 0:
        raise ShortcutError("the PRoot GUI application did not complete successfully")
    return {"resource_id": f"proot.x11.app.{app_id}", "provider": "proot_debian",
            "status": "process_exited", "exit_status": result.returncode,
            "gui_visible": "unknown", "read_only": False}
