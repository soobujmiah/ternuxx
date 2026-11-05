"""Preview and apply a complete Ternuxx checkout, state, and PRoot uninstall."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

import proot_distro_removal
import proot_fresh_setup

_CONFIRMATION = "UNINSTALL TERNUXX"
EXPECTED_PREFIX = "/data/data/com.termux/files/usr"
_ID = re.compile(r"[0-9a-f]{64}\Z")
_ORIGINS = {"https://github.com/soobujmiah/ternuxx", "https://github.com/soobujmiah/ternuxx.git",
            "git@github.com:soobujmiah/ternuxx.git"}
_STATE_OMIT = ("uninstall-previews", "proot-setup/removal-previews", "proot-display0", "audio/runtime", "xfce/runtime")


class UninstallError(ValueError):
    pass


def _hash(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _file_record(path: Path) -> dict | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid() or info.st_size > 16 * 1024 * 1024):
        raise UninstallError("Ternuxx-owned file is unsafe or has unexpected contents: " + str(path))
    raw = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "device": info.st_dev, "inode": info.st_ino, "size": info.st_size,
            "mode": stat.S_IMODE(info.st_mode)}


def _checkout_fingerprint(root: Path) -> dict:
    """Fingerprint the complete checkout, including ignored and untracked files."""
    root_info = root.lstat()
    entries: list[tuple] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        before = directory.lstat()
        if (not stat.S_ISDIR(before.st_mode) or before.st_dev != root_info.st_dev
                or before.st_uid != os.getuid()):
            raise UninstallError("the Ternuxx checkout contains an unsafe directory: " + str(directory))
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise UninstallError("the Ternuxx checkout could not be completely inspected") from exc
        for child in children:
            path = Path(child.path)
            info = child.stat(follow_symlinks=False)
            relative = str(path.relative_to(root))
            if info.st_uid != os.getuid() or info.st_dev != root_info.st_dev:
                raise UninstallError("the Ternuxx checkout contains a foreign-owned or mounted path: " + relative)
            common = (relative, info.st_mode, info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            if stat.S_ISDIR(info.st_mode):
                entries.append((*common, "directory"))
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                digest = hashlib.sha256()
                try:
                    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                    with os.fdopen(fd, "rb") as stream:
                        opened = os.fstat(stream.fileno())
                        if (opened.st_dev, opened.st_ino, opened.st_uid) != (info.st_dev, info.st_ino, info.st_uid):
                            raise UninstallError("the Ternuxx checkout changed during inspection")
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                except OSError as exc:
                    raise UninstallError("a Ternuxx checkout file could not be verified: " + relative) from exc
                entries.append((*common, "file", digest.hexdigest()))
            elif stat.S_ISLNK(info.st_mode):
                entries.append((*common, "symlink", os.readlink(path)))
            else:
                raise UninstallError("the Ternuxx checkout contains an unsupported file: " + relative)
    payload = json.dumps(sorted(entries), separators=(",", ":"), ensure_ascii=True).encode()
    return {"entry_count": len(entries), "entries_sha256": hashlib.sha256(payload).hexdigest()}


def _tree_fingerprint(root: Path, *, omit: tuple[str, ...] = (), allow_supervise_runtime: bool = False) -> dict:
    try:
        root_info = root.lstat()
    except FileNotFoundError:
        return {"exists": False}
    if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode) or root_info.st_uid != os.getuid():
        raise UninstallError("Ternuxx data directory identity is unsafe: " + str(root))
    entries = []
    for directory, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(name for name in dirs if str((base / name).relative_to(root)) not in omit)
        for name in [*dirs, *sorted(files)]:
            path = base / name
            info = path.lstat()
            if info.st_uid != os.getuid():
                raise UninstallError("Ternuxx data tree contains a foreign-owned path: " + str(path))
            relative = str(path.relative_to(root))
            allowed_runtime = (allow_supervise_runtime and relative.startswith("supervise/")
                               and (stat.S_ISFIFO(info.st_mode) or stat.S_ISSOCK(info.st_mode)))
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
                    or stat.S_ISLNK(info.st_mode) or allowed_runtime):
                raise UninstallError("Ternuxx data tree contains an unsupported file: " + str(path))
            entry = (str(path.relative_to(root)), info.st_mode, info.st_dev, info.st_ino,
                     info.st_size, info.st_mtime_ns)
            if stat.S_ISLNK(info.st_mode):
                entries.append((*entry, os.readlink(path)))
            else:
                entries.append(entry)
    return {"exists": True, "device": root_info.st_dev, "inode": root_info.st_ino,
            "entries_sha256": hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest(),
            "entry_count": len(entries)}


def _checkout(home: Path) -> dict | None:
    value = Path(os.environ.get("TERNUXX_CHECKOUT", str(home / "ternuxx"))).expanduser().absolute()
    try:
        value.relative_to(home)
    except ValueError as exc:
        raise UninstallError("the Ternuxx checkout must be inside HOME") from exc
    try:
        info = value.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
        raise UninstallError("the Ternuxx checkout path is not a safe owned directory")
    if not (value / ".git").is_dir() or (value / ".git").is_symlink():
        raise UninstallError("the checkout does not have a regular Git metadata directory; preserving it")
    def git(*args: str) -> str:
        try:
            result = subprocess.run(["git", "-C", str(value), *args], capture_output=True,
                                    text=True, check=False, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UninstallError("the checkout origin and contents could not be verified") from exc
        if result.returncode:
            raise UninstallError("the checkout origin and contents could not be verified")
        return result.stdout.strip()
    if git("remote", "get-url", "origin") not in _ORIGINS:
        raise UninstallError("the checkout origin is not the canonical Ternuxx repository; preserving it")
    dirty = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching")
    records = [record for record in dirty.split("\0") if record]
    local_count = sum(record[:2] not in {"??", "!!"} for record in records)
    untracked_ignored_count = sum(record[:2] in {"??", "!!"} for record in records)
    return {"path": str(value), "device": info.st_dev, "inode": info.st_ino,
            "head": git("rev-parse", "HEAD"), "origin": git("remote", "get-url", "origin"),
            "tree": _checkout_fingerprint(value), "local_change_count": local_count,
            "untracked_or_ignored_count": untracked_ignored_count}


def _managed_files(prefix: Path, checkout: Path | None, home: Path) -> list[dict]:
    items = []
    entry = prefix / "bin/tx"
    if entry.exists() or entry.is_symlink():
        if checkout is None or _file_record(entry) is None or (checkout / "scripts/tx-installed").read_bytes() != entry.read_bytes():
            raise UninstallError("PREFIX/bin/tx is not the exact Ternuxx entrypoint; preserving it")
        items.append(_file_record(entry))
    if checkout is None:
        return items
    for relative in ("00-ternuxx-services", "20-ternuxx-cron", "ternuxx-recovery"):
        target = home / ".termux/boot" / relative
        source = checkout / "scripts/termux-boot" / relative
        if target.exists() or target.is_symlink():
            record = _file_record(target)
            if source.is_file() and target.read_bytes() == source.read_bytes():
                items.append(record)
            else:
                raise UninstallError("Termux:Boot file differs from the Ternuxx template; preserving it: " + str(target))
    for source_dir in sorted((checkout / "scripts/termux-services").iterdir()):
        if not source_dir.is_dir() or source_dir.is_symlink():
            continue
        target_dir = prefix / "var/service" / source_dir.name
        if not target_dir.exists() and not target_dir.is_symlink():
            continue
        if target_dir.is_symlink() or not target_dir.is_dir():
            raise UninstallError("Ternuxx service path is unsafe: " + str(target_dir))
        for source in source_dir.rglob("*"):
            if source.is_dir():
                continue
            relative = source.relative_to(source_dir)
            target = target_dir / relative
            expected = source.read_bytes()
            if not target.is_file() or target.is_symlink() or target.read_bytes() != expected:
                raise UninstallError("Ternuxx service differs from its template; preserving it: " + str(target))
            items.append(_file_record(target))
        tree = _tree_fingerprint(target_dir, allow_supervise_runtime=True)
        items.append({"directory": str(target_dir), "device": target_dir.stat().st_dev,
                      "inode": target_dir.stat().st_ino, "tree": tree})
    # Remove the optional GTK center only when its identity record verifies every installed artifact.
    identity = prefix / "libexec/ternuxx/management-center.identity"
    if identity.exists() or identity.is_symlink():
        if identity.is_symlink() or not identity.is_file():
            raise UninstallError("GTK management-center identity file is unsafe")
        fields = dict(line.split("=", 1) for line in identity.read_text().splitlines() if "=" in line)
        targets = ((prefix / "libexec/ternuxx/management-center", "installed_binary"),
                   (prefix / "bin/tx-management-center", "installed_launcher"),
                   (prefix / "share/applications/ternuxx-management-center.desktop", "installed_desktop"))
        for target, field in targets:
            record = _file_record(target)
            if record is None or record["sha256"] != fields.get(field):
                raise UninstallError("GTK management-center artifact differs from its install receipt; preserving it")
            items.append(record)
        items.append(_file_record(identity))
        items.append({"directory": str(prefix / "libexec/ternuxx"),
                      "device": (prefix / "libexec/ternuxx").stat().st_dev,
                      "inode": (prefix / "libexec/ternuxx").stat().st_ino, "remove_if_empty": True})
    return items


def _state_paths(home: Path, state_dir: str) -> tuple[Path, Path]:
    state = Path(state_dir).absolute()
    expected = home / ".local/share/ternuxx"
    if state != expected:
        raise UninstallError("tx uninstall only removes the default Ternuxx state path; custom TERNUXX_STATE_DIR is preserved")
    preview_dir = state / "uninstall-previews"
    return state, preview_dir


def preview(*, prefix: str, home: str, state_dir: str) -> dict:
    home_path = Path(home).resolve()
    prefix_path = Path(prefix).absolute()
    if str(prefix_path) != EXPECTED_PREFIX:
        raise UninstallError("complete uninstall is supported only for the fixed Native Termux PREFIX")
    state, preview_dir = _state_paths(home_path, state_dir)
    try:
        proot_fresh_setup._state_root(str(home_path), str(state), create=True)
        preview_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        proot_fresh_setup._directory(preview_dir, private=True)
    except (OSError, ValueError) as exc:
        raise UninstallError("private uninstall preview storage is unsafe") from exc
    checkout_record = _checkout(home_path)
    checkout_path = Path(checkout_record["path"]) if checkout_record else None
    files = _managed_files(prefix_path, checkout_path, home_path)
    guests = []
    manager = shutil.which("proot-distro")
    if manager:
        for alias in sorted(proot_distro_removal._inventory(manager)):
            guests.append(proot_distro_removal.preview(prefix=prefix, home=home,
                state_dir=state_dir, alias=alias, check_idle=False))
    state_record = _tree_fingerprint(state, omit=_STATE_OMIT)
    plan = {"schema_version": 1, "operation": "complete-ternuxx-uninstall",
            "checkout": checkout_record, "state_dir": str(state), "state": state_record,
            "files": files, "guests": guests,
            "native_package_dependencies_removed": False,
            "warning": "Deletes the complete Ternuxx checkout, including modified, untracked and ignored files, verified Ternuxx entrypoints, private Ternuxx state/backups, Termux:Boot/service files listed above, and every installed PRoot guest. Shared Termux packages remain installed."}
    plan_id = _hash(plan)
    plan["plan_id"] = plan_id
    proot_fresh_setup._private_write(preview_dir / f"{plan_id}.json", plan)
    return {"status": "preview", **plan, "confirmation_phrase": _CONFIRMATION}


def _verify(plan: dict, *, prefix: str, home: str, state_dir: str) -> None:
    current = preview(prefix=prefix, home=home, state_dir=state_dir)
    if current["plan_id"] != plan.get("plan_id"):
        raise UninstallError("Native files, private state, or PRoot guest list changed after preview")


def apply(*, prefix: str, home: str, state_dir: str, plan_id: str,
          confirmation: str, confirmed: bool) -> dict:
    if confirmed is not True or confirmation != _CONFIRMATION or not isinstance(plan_id, str) or not _ID.fullmatch(plan_id):
        raise UninstallError("type UNINSTALL TERNUXX and confirm the exact full-uninstall preview")
    _state, preview_dir = _state_paths(Path(home).resolve(), state_dir)
    try:
        plan = proot_fresh_setup._read_private(preview_dir / f"{plan_id}.json")
    except (OSError, ValueError) as exc:
        raise UninstallError("the exact full-uninstall preview is unavailable") from exc
    identity = {key: value for key, value in plan.items() if key != "plan_id"}
    if plan.get("plan_id") != plan_id or _hash(identity) != plan_id:
        raise UninstallError("full-uninstall preview integrity check failed")
    # Revalidate every owned object before the first removal.
    _verify(plan, prefix=prefix, home=home, state_dir=state_dir)
    root = Path(plan["checkout"]["path"]) if plan.get("checkout") else None
    if root is not None:
        pgui_stop = root / "scripts/proot-gui0.sh"
        if not pgui_stop.is_file() or pgui_stop.is_symlink():
            raise UninstallError("the managed PRoot GUI stop command is unavailable; preserving the uninstall targets")
        try:
            stopped = subprocess.run([str(pgui_stop), "stop"], capture_output=True,
                                     text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UninstallError("the managed PRoot GUI could not be stopped; preserving the uninstall targets") from exc
        if stopped.returncode:
            raise UninstallError("the managed PRoot GUI could not be stopped; preserving the uninstall targets")
    service_dirs = [item for item in plan["files"] if "directory" in item and "tree" in item]
    empty_dirs = [item for item in plan["files"] if item.get("remove_if_empty") is True]
    supervisor = Path(prefix) / "bin/sv"
    for item in service_dirs:
        path = Path(item["directory"])
        info = path.stat()
        if (info.st_ino, info.st_dev) != (item["inode"], item["device"]):
            raise UninstallError("a Ternuxx service directory changed during uninstall")
        if not supervisor.is_file():
            raise UninstallError("Runit control is unavailable; preserving managed services")
        subprocess.run([str(supervisor), "down", str(path)], capture_output=True, timeout=30, check=False)
        status = subprocess.run([str(supervisor), "status", str(path)], capture_output=True,
                                text=True, timeout=30, check=False)
        if "run:" in status.stdout:
            raise UninstallError("a Ternuxx service is still running; preserving the uninstall targets")
    removed_guests = []
    for guest in plan["guests"]:
        alias = guest["alias"]
        proot_distro_removal.apply(prefix=prefix, home=home, state_dir=state_dir,
            alias=alias, plan_id=guest["plan_id"], typed_alias=alias, confirmed=True)
        removed_guests.append(alias)
    # Remove only receipt/hash-verified files and exact service directories.
    for item in plan["files"]:
        if "path" in item:
            path = Path(item["path"])
            record = _file_record(path)
            if record is None or record["sha256"] != item["sha256"] or record["inode"] != item["inode"]:
                raise UninstallError("a verified Ternuxx file changed during uninstall: " + str(path))
            path.unlink()
    for item in service_dirs:
        path = Path(item["directory"])
        shutil.rmtree(path)
    for item in empty_dirs:
        path = Path(item["directory"])
        if path.exists():
            info = path.stat()
            if (info.st_ino, info.st_dev) != (item["inode"], item["device"]):
                raise UninstallError("a Native Ternuxx parent directory changed during uninstall")
            path.rmdir()
    if plan["state"]["exists"]:
        current = _tree_fingerprint(Path(plan["state_dir"]), omit=_STATE_OMIT)
        if current != plan["state"]:
            raise UninstallError("Ternuxx private state changed during uninstall; preserving remaining state")
        shutil.rmtree(plan["state_dir"])
    if root is not None:
        current_checkout = _checkout(Path(home).resolve())
        if current_checkout != plan["checkout"]:
            raise UninstallError("Ternuxx checkout changed during uninstall")
        info = root.lstat()
        if (info.st_dev, info.st_ino) != (plan["checkout"]["device"], plan["checkout"]["inode"]):
            raise UninstallError("Ternuxx checkout changed during uninstall")
        shutil.rmtree(root)
    return {"status": "uninstalled", "removed_guests": removed_guests,
            "checkout_removed": root is not None, "state_removed": bool(plan["state"]["exists"]),
            "native_package_dependencies_removed": False}
