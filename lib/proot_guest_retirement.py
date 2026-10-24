#!/usr/bin/env python3
"""Reversibly retire a Ternuxx-created replay guest by atomic rename."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_fresh_setup
import proot_sessions

_ALIAS = re.compile(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}\Z")
_ID = re.compile(r"[0-9a-f]{64}\Z")
_ACTIVE = {"starting", "running", "stopping", "unverified"}
_RENAME_SUPPORTS_DIR_FD = os.rename in os.supports_dir_fd


class RetirementError(ValueError):
    pass


def _hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _private_dir(path: Path, root: Path, *, create: bool = False) -> Path:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RetirementError("retirement path escaped Ternuxx state") from exc
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            raise RetirementError("retirement path contains a symbolic link")
        if not current.exists() and create:
            current.mkdir(mode=0o700)
        if current.exists():
            try:
                proot_fresh_setup._directory(current, private=True)
            except (OSError, proot_fresh_setup.FreshSetupError) as exc:
                raise RetirementError("retirement directory identity is unsafe") from exc
    return path


def _load_target(prefix: str, home: str, state_dir: str, alias: str):
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise RetirementError("only an explicit ternuxx-replay-NAME guest can be retired")
    state = proot_fresh_setup._state_root(home, state_dir, create=False)
    try:
        receipt = proot_fresh_setup._read_private(state / f"fresh-provider-{alias}.json")
        container, rootfs = proot_fresh_setup._target_paths(prefix, alias)
    except (OSError, proot_fresh_setup.FreshSetupError) as exc:
        raise RetirementError("replay guest or its exact ownership receipt is unavailable") from exc
    try:
        verified = proot_fresh_setup._verify_owned_target(
            prefix, alias, receipt.get("rootfs_identity"))
    except proot_fresh_setup.FreshSetupError as exc:
        raise RetirementError("replay guest identity no longer matches its ownership receipt") from exc
    if (receipt.get("alias") != alias
            or receipt.get("origin") != "fresh-preview-confirmed-install"
            or receipt.get("package_versions_recorded") is not True
            or receipt.get("requested_packages_verified_installed") is not True
            or verified != rootfs):
        raise RetirementError("target is not a completed Ternuxx-owned replay guest")
    return state, receipt, container, rootfs


def _assert_idle(state: Path, rootfs: Path, proc_root: Path = Path("/proc")) -> None:
    try:
        records = proot_sessions.list_sessions(state.parent)
    except (OSError, ValueError) as exc:
        raise RetirementError("managed-session inventory is unavailable") from exc
    for item in records:
        if (Path(str(item.get("rootfs", ""))) == rootfs
                and item.get("state") in _ACTIVE):
            raise RetirementError("a managed terminal still owns this replay guest")
    needle = os.fsencode(str(rootfs))
    try:
        entries = list(proc_root.iterdir())
    except OSError as exc:
        raise RetirementError("Native process inventory is unavailable") from exc
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if argv and argv[0] and os.fsdecode(argv[0]).rsplit("/", 1)[-1] == "proot" and needle in argv:
            raise RetirementError("a PRoot process still uses this replay guest")


@contextmanager
def _container_lock(alias: str):
    try:
        from proot_distro.locking import ContainerLock
    except ImportError as exc:
        raise RetirementError("proot-distro container lock is unavailable") from exc
    try:
        with ContainerLock(alias, exclusive=True, command="Ternuxx replay retirement"):
            yield
    except SystemExit as exc:
        raise RetirementError("could not lock the exact replay guest") from exc


def _local_lock(state: Path, alias: str) -> int:
    path = state / f"retire-{alias}.lock"
    if path.is_symlink():
        raise RetirementError("retirement lock is a symbolic link")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600):
        os.close(fd)
        raise RetirementError("retirement lock identity is unsafe")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise RetirementError("another retirement operation is active") from exc
    return fd


def _rename_exact(source: Path, destination: Path, expected: tuple[int, int]) -> os.stat_result:
    if not _RENAME_SUPPORTS_DIR_FD:
        raise RetirementError("atomic directory rename with directory handles is unavailable")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    source_fd = os.open(source.parent, flags)
    try:
        destination_fd = os.open(destination.parent, flags)
        try:
            source_info = os.stat(source.name, dir_fd=source_fd, follow_symlinks=False)
            if (not stat.S_ISDIR(source_info.st_mode)
                    or (source_info.st_dev, source_info.st_ino) != expected):
                raise RetirementError("rename source identity changed")
            try:
                os.stat(destination.name, dir_fd=destination_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise RetirementError("rename destination already exists; refusing overwrite")
            os.rename(source.name, destination.name, src_dir_fd=source_fd,
                      dst_dir_fd=destination_fd)
            moved = os.stat(destination.name, dir_fd=destination_fd, follow_symlinks=False)
            if (not stat.S_ISDIR(moved.st_mode)
                    or (moved.st_dev, moved.st_ino) != expected):
                raise RetirementError("atomic rename changed directory identity")
            return moved
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)


def _backup_dir(state: Path, alias: str, operation_id: str, *, create: bool = False) -> Path:
    base = _private_dir(state / "retired", state, create=create)
    per_alias = _private_dir(base / alias, state, create=create)
    return _private_dir(per_alias / operation_id, state, create=create)


def retire_preview(*, prefix: str, home: str, state_dir: str, alias: str) -> dict:
    state, receipt, container, rootfs = _load_target(prefix, home, state_dir, alias)
    _assert_idle(state, rootfs)
    container_info, parent_info = container.stat(), container.parent.stat()
    if state.stat().st_dev != container_info.st_dev:
        raise RetirementError("guest and private backup must share a filesystem for atomic retirement")
    operation_id = uuid.uuid4().hex
    backup = _backup_dir(state, alias, operation_id) / "container"
    payload = {
        "schema_version": 1, "operation": "retire-ternuxx-replay-guest",
        "alias": alias, "operation_id": operation_id,
        "container": str(container), "container_device": container_info.st_dev,
        "container_inode": container_info.st_ino,
        "rootfs": str(rootfs), "rootfs_identity": receipt["rootfs_identity"],
        "containers_device": parent_info.st_dev, "containers_inode": parent_info.st_ino,
        "backup": str(backup), "backup_device": state.stat().st_dev,
        "confirmation_required": True,
        "impact": "Atomically moves this receipt-verified replay guest into private Ternuxx state. No guest files are deleted; restore moves the same directory back.",
    }
    plan_id = _hash(payload)
    plan = {**payload, "plan_id": plan_id}
    proot_fresh_setup._private_write(state / "previews" / f"retire-{plan_id}.json", plan)
    return {"status": "preview", "plan_id": plan_id, "operation": plan}


def _load_plan(state: Path, plan_id: str, kind: str) -> dict:
    if not isinstance(plan_id, str) or not _ID.fullmatch(plan_id):
        raise RetirementError("a valid exact preview plan ID is required")
    try:
        plan = proot_fresh_setup._read_private(state / "previews" / f"{kind}-{plan_id}.json")
    except (OSError, ValueError) as exc:
        raise RetirementError("matching private retirement preview is unavailable") from exc
    payload = {key: value for key, value in plan.items() if key != "plan_id"}
    if plan.get("plan_id") != plan_id or _hash(payload) != plan_id:
        raise RetirementError("retirement preview integrity check failed")
    return plan


def _metadata(state: Path, alias: str, operation_id: str) -> tuple[Path, dict]:
    if not isinstance(operation_id, str) or not re.fullmatch(r"[0-9a-f]{32}", operation_id):
        raise RetirementError("backup ID must be a 32-character lowercase hexadecimal ID")
    operation_dir = _backup_dir(state, alias, operation_id)
    try:
        record = proot_fresh_setup._read_private(operation_dir / "metadata.json")
    except (OSError, ValueError) as exc:
        raise RetirementError("retirement metadata is unavailable or unsafe") from exc
    if record.get("operation_id") != operation_id or record.get("alias") != alias:
        raise RetirementError("retirement metadata targets another guest")
    return operation_dir, record


def retire_apply(*, prefix: str, home: str, state_dir: str, alias: str,
                 plan_id: str, confirmed: bool) -> dict:
    if confirmed is not True:
        raise RetirementError("replay retirement requires exact preview confirmation")
    state = proot_fresh_setup._state_root(home, state_dir, create=False)
    plan = _load_plan(state, plan_id, "retire")
    if plan.get("alias") != alias or plan.get("operation") != "retire-ternuxx-replay-guest":
        raise RetirementError("retirement plan targets another guest")
    fd = _local_lock(state, alias)
    try:
        with _container_lock(alias):
            state, receipt, container, rootfs = _load_target(prefix, home, state_dir, alias)
            _assert_idle(state, rootfs)
            info, parent = container.stat(), container.parent.stat()
            if ((info.st_dev, info.st_ino) != (plan["container_device"], plan["container_inode"])
                    or receipt.get("rootfs_identity") != plan["rootfs_identity"]
                    or (parent.st_dev, parent.st_ino) != (plan["containers_device"], plan["containers_inode"])
                    or state.stat().st_dev != plan["backup_device"]):
                raise RetirementError("replay guest identity changed after preview")
            operation_dir = _backup_dir(state, alias, plan["operation_id"], create=True)
            backup = operation_dir / "container"
            metadata_path = operation_dir / "metadata.json"
            if metadata_path.exists():
                record = proot_fresh_setup._read_private(metadata_path)
                if record.get("plan_id") != plan_id:
                    raise RetirementError("backup metadata belongs to another plan")
            else:
                record = {**plan, "state": "retiring"}
                proot_fresh_setup._private_write(metadata_path, record)
            if backup.exists() or backup.is_symlink():
                moved = backup.stat()
                if (container.exists() or container.is_symlink()
                        or (moved.st_dev, moved.st_ino) != (info.st_dev, info.st_ino)):
                    raise RetirementError("retirement source or backup conflicts with the exact plan")
            else:
                moved = _rename_exact(container, backup, (info.st_dev, info.st_ino))
            if (moved.st_dev, moved.st_ino) != (info.st_dev, info.st_ino):
                raise RetirementError("atomic retirement changed the container identity")
            record["state"] = "retired"
            proot_fresh_setup._private_write(metadata_path, record)
            return {"status": "retired", "alias": alias,
                    "backup_id": plan["operation_id"], "backup_path": str(backup),
                    "container_inode": moved.st_ino, "files_deleted": False}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def restore_preview(*, prefix: str, home: str, state_dir: str,
                    alias: str, backup_id: str) -> dict:
    if not _ALIAS.fullmatch(alias):
        raise RetirementError("only an explicit ternuxx-replay-NAME guest can be restored")
    state = proot_fresh_setup._state_root(home, state_dir, create=False)
    operation_dir, record = _metadata(state, alias, backup_id)
    if record.get("state") not in {"retiring", "retired", "restoring"}:
        raise RetirementError("backup is not a retired replay guest")
    backup = operation_dir / "container"
    container = Path(record["container"])
    _assert_idle(state, backup / "rootfs")
    if container != Path(prefix) / "var/lib/proot-distro/containers" / alias:
        raise RetirementError("rollback target path failed its exact alias check")
    if container.exists() or container.is_symlink() or not backup.is_dir():
        raise RetirementError("guest target conflicts with the exact retirement backup")
    info = backup.stat()
    if (info.st_dev, info.st_ino) != (record["container_device"], record["container_inode"]):
        raise RetirementError("retirement backup identity differs from its journal")
    if proot_fresh_setup._root_identity(backup, backup / "rootfs") != record["rootfs_identity"]:
        raise RetirementError("retirement backup rootfs identity differs from its receipt")
    payload = {
        "schema_version": 1, "operation": "restore-ternuxx-replay-guest",
        "alias": alias, "backup_id": backup_id, "backup": str(backup),
        "container": str(container), "container_device": info.st_dev,
        "container_inode": info.st_ino, "rootfs_identity": record["rootfs_identity"],
        "confirmation_required": True,
        "impact": "Atomically restores the same private replay guest directory to its original PRoot-Distro alias.",
    }
    plan_id = _hash(payload)
    plan = {**payload, "plan_id": plan_id}
    proot_fresh_setup._private_write(state / "previews" / f"restore-{plan_id}.json", plan)
    return {"status": "preview", "plan_id": plan_id, "operation": plan}


def restore_apply(*, prefix: str, home: str, state_dir: str, alias: str,
                  backup_id: str, plan_id: str, confirmed: bool) -> dict:
    if confirmed is not True:
        raise RetirementError("replay restore requires exact preview confirmation")
    state = proot_fresh_setup._state_root(home, state_dir, create=False)
    plan = _load_plan(state, plan_id, "restore")
    if plan.get("alias") != alias or plan.get("backup_id") != backup_id:
        raise RetirementError("restore plan targets another guest or backup")
    fd = _local_lock(state, alias)
    try:
        with _container_lock(alias):
            operation_dir, record = _metadata(state, alias, backup_id)
            backup = operation_dir / "container"
            container = Path(record["container"])
            expected_container = Path(prefix) / "var/lib/proot-distro/containers" / alias
            if container != expected_container:
                raise RetirementError("restore target path failed its exact alias check")
            _assert_idle(state, backup / "rootfs" if backup.exists() else container / "rootfs")
            if (record.get("rootfs_identity") != plan.get("rootfs_identity")
                    or record.get("state") not in {"retiring", "retired", "restoring"}):
                raise RetirementError("backup is no longer available for restoration")
            if record.get("state") == "restoring" and container.is_dir() and not backup.exists():
                restored = container.stat()
                if (restored.st_dev, restored.st_ino) != (plan["container_device"], plan["container_inode"]):
                    raise RetirementError("interrupted restore target has a different identity")
                record["state"] = "restored"
                proot_fresh_setup._private_write(operation_dir / "metadata.json", record)
                return {"status": "restored", "alias": alias, "backup_id": backup_id,
                        "container_inode": restored.st_ino, "files_deleted": False,
                        "reconciled_interrupted_apply": True}
            if (container.exists() or container.is_symlink()
                    or (backup.stat().st_dev, backup.stat().st_ino)
                    != (plan["container_device"], plan["container_inode"])):
                raise RetirementError("restore source or destination changed after preview")
            record["state"] = "restoring"
            proot_fresh_setup._private_write(operation_dir / "metadata.json", record)
            restored = _rename_exact(backup, container,
                                     (plan["container_device"], plan["container_inode"]))
            if (restored.st_dev, restored.st_ino) != (
                    plan["container_device"], plan["container_inode"]):
                raise RetirementError("restored guest identity differs from preview")
            record["state"] = "restored"
            proot_fresh_setup._private_write(operation_dir / "metadata.json", record)
            return {"status": "restored", "alias": alias, "backup_id": backup_id,
                    "container_inode": restored.st_ino, "files_deleted": False}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "apply", "restore-preview", "restore"))
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--plan-id")
    parser.add_argument("--backup-id")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "preview":
            result = retire_preview(prefix=args.prefix, home=args.home,
                                    state_dir=args.state_dir, alias=args.alias)
        elif args.action == "apply":
            result = retire_apply(prefix=args.prefix, home=args.home, state_dir=args.state_dir,
                                  alias=args.alias, plan_id=args.plan_id, confirmed=args.yes)
        elif args.action == "restore-preview":
            result = restore_preview(prefix=args.prefix, home=args.home, state_dir=args.state_dir,
                                     alias=args.alias, backup_id=args.backup_id)
        else:
            result = restore_apply(prefix=args.prefix, home=args.home, state_dir=args.state_dir,
                                   alias=args.alias, backup_id=args.backup_id,
                                   plan_id=args.plan_id, confirmed=args.yes)
    except (OSError, ValueError, proot_fresh_setup.FreshSetupError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
