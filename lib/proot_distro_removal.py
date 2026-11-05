"""Exact-alias preview and removal for one installed proot-distro guest."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

import proot_fresh_setup
import proot_guest_retirement

_ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_ID = re.compile(r"[0-9a-f]{64}\Z")


class RemovalError(ValueError):
    pass


def _hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _manager() -> tuple[str, os.stat_result]:
    path = shutil.which("proot-distro")
    if not path:
        raise RemovalError("proot-distro is unavailable")
    executable = Path(path).absolute()
    if executable.is_symlink() or not os.access(executable, os.X_OK):
        raise RemovalError("proot-distro executable identity is unsafe")
    return str(executable), executable.stat()


def _inventory(manager: str) -> set[str]:
    try:
        result = subprocess.run([manager, "list", "--quiet"], capture_output=True,
                                text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RemovalError("installed PRoot guest inventory is unavailable") from exc
    if result.returncode:
        raise RemovalError("installed PRoot guest inventory is unavailable")
    found = set()
    for row in result.stdout.splitlines():
        value = row.strip()
        if value.startswith("* "):
            value = value[2:].strip()
        if _ALIAS.fullmatch(value):
            found.add(value)
    return found


def _target(prefix: str, alias: str) -> tuple[Path, Path]:
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise RemovalError("guest alias must be one exact proot-distro name")
    base = Path(prefix).absolute()
    try:
        base_info = base.lstat()
        containers = base / "var/lib/proot-distro/containers"
        container = containers / alias
        rootfs = container / "rootfs"
        for path in (base / "var", base / "var/lib", base / "var/lib/proot-distro", containers, container, rootfs):
            info = path.lstat()
            if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                    or info.st_uid != os.getuid()):
                raise RemovalError("guest storage path identity is unsafe")
        if not stat.S_ISDIR(base_info.st_mode) or base_info.st_uid != os.getuid():
            raise RemovalError("Native Termux prefix identity is unsafe")
        if rootfs.resolve(strict=True) != rootfs.absolute():
            raise RemovalError("guest rootfs path resolves through a symbolic link")
        return container, rootfs
    except FileNotFoundError as exc:
        raise RemovalError("guest rootfs is missing") from exc
    except OSError as exc:
        raise RemovalError("guest storage path cannot be inspected") from exc


def _state(home: str, state_dir: str, *, create: bool) -> Path:
    try:
        root = proot_fresh_setup._state_root(home, state_dir, create=create)
    except (OSError, ValueError) as exc:
        raise RemovalError("private Ternuxx removal state is unavailable") from exc
    path = root / "removal-previews"
    if path.is_symlink():
        raise RemovalError("removal preview directory is unsafe")
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    try:
        proot_fresh_setup._directory(path, private=True)
    except (OSError, proot_fresh_setup.FreshSetupError) as exc:
        raise RemovalError("removal preview directory identity is unsafe") from exc
    return path


def _idle(home: str, state_dir: str, rootfs: Path) -> None:
    try:
        state_root = proot_fresh_setup._state_root(home, state_dir, create=True)
        proot_guest_retirement._assert_idle(state_root, rootfs)
    except (OSError, ValueError) as exc:
        raise RemovalError(str(exc)) from exc


def preview(*, prefix: str, home: str, state_dir: str, alias: str, check_idle: bool = True) -> dict:
    manager, manager_stat = _manager()
    if alias not in _inventory(manager):
        raise RemovalError("PRoot guest is not installed: " + str(alias))
    container, rootfs = _target(prefix, alias)
    if check_idle:
        _idle(home, state_dir, rootfs)
    info, root_info = container.stat(), rootfs.stat()
    plan = {
        "schema_version": 1, "operation": "remove-one-proot-distro-guest", "alias": alias,
        "manager": manager, "manager_device": manager_stat.st_dev, "manager_inode": manager_stat.st_ino,
        "container_device": info.st_dev, "container_inode": info.st_ino,
        "rootfs_device": root_info.st_dev, "rootfs_inode": root_info.st_ino,
        "container_path": str(container), "rootfs_path": str(rootfs),
    }
    plan_id = _hash(plan)
    plan["plan_id"] = plan_id
    previews = _state(home, state_dir, create=True)
    proot_fresh_setup._private_write(previews / f"{plan_id}.json", plan)
    return {"status": "preview", **plan,
            "warning": "Applying permanently deletes all files in this PRoot guest."}


def apply(*, prefix: str, home: str, state_dir: str, alias: str, plan_id: str,
          typed_alias: str, confirmed: bool) -> dict:
    if confirmed is not True or typed_alias != alias or not isinstance(plan_id, str) or not _ID.fullmatch(plan_id):
        raise RemovalError("removal requires the exact preview, typed guest name, and confirmation")
    previews = _state(home, state_dir, create=False)
    try:
        plan = proot_fresh_setup._read_private(previews / f"{plan_id}.json")
    except (OSError, ValueError) as exc:
        raise RemovalError("exact guest removal preview is unavailable") from exc
    identity = {key: value for key, value in plan.items() if key != "plan_id"}
    if (plan.get("plan_id") != plan_id or _hash(identity) != plan_id
            or plan.get("alias") != alias or plan.get("operation") != "remove-one-proot-distro-guest"):
        raise RemovalError("guest removal preview integrity check failed")
    lock_path = previews / f"remove-{alias}.lock"
    if lock_path.is_symlink():
        raise RemovalError("guest removal lock is unsafe")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600:
            raise RemovalError("guest removal lock identity is unsafe")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RemovalError("another removal operation is active") from exc
        manager, manager_stat = _manager()
        container, rootfs = _target(prefix, alias)
        _idle(home, state_dir, rootfs)
        current = container.stat(), rootfs.stat()
        if (manager != plan["manager"] or manager_stat.st_dev != plan["manager_device"]
                or manager_stat.st_ino != plan["manager_inode"]
                or (current[0].st_dev, current[0].st_ino) != (plan["container_device"], plan["container_inode"])
                or (current[1].st_dev, current[1].st_ino) != (plan["rootfs_device"], plan["rootfs_inode"])
                or alias not in _inventory(manager)):
            raise RemovalError("guest or manager identity changed after preview")
        try:
            result = subprocess.run([manager, "remove", alias], capture_output=True,
                                    text=True, check=False, timeout=1800)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RemovalError("proot-distro could not remove the selected guest") from exc
        if result.returncode or container.exists() or container.is_symlink():
            raise RemovalError("proot-distro removal did not remove the exact guest; inspect its state")
        return {"status": "removed", "alias": alias, "plan_id": plan_id,
                "deleted_path": str(container), "recoverable_backup": False}
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
