"""Preview-first reconciliation for the two repository-owned Termux:Boot helpers."""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile

HELPERS = {
    "services": ("00-ternuxx-services", "scripts/termux-boot/00-ternuxx-services"),
    "recovery": ("ternuxx-recovery", "scripts/termux-boot/ternuxx-recovery"),
}
KNOWN_LEGACY = {
    "services": "53b6745a930af57434cc046861f5df11d9a6aaf76529a857ab4c2cc978ac9b4e",
    "recovery": "4861f2145f58e3d21f0dd4619e30f4a09f555df9a78bfbe515757a567d417c26",
}
PLAN_TTL = 900


class BootHelperError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stamp(now: dt.datetime | None = None) -> str:
    value = now or dt.datetime.now(dt.timezone.utc)
    if value.tzinfo is None:
        raise BootHelperError("clock must include a timezone")
    return value.astimezone(dt.timezone.utc).isoformat()


def _parse_time(value: str) -> dt.datetime:
    try:
        result = dt.datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise BootHelperError("boot-helper plan timestamp is invalid") from exc
    if result.tzinfo is None:
        raise BootHelperError("boot-helper plan timestamp lacks a timezone")
    return result.astimezone(dt.timezone.utc)


def _root(home: str | os.PathLike[str], state_dir: str | os.PathLike[str], *, create: bool) -> Path:
    home_path = Path(home).expanduser().resolve()
    state = Path(os.path.abspath(Path(state_dir).expanduser()))
    if state == home_path or home_path not in state.parents:
        raise BootHelperError("boot-helper state must be inside Termux HOME")
    cursor = home_path
    for component in state.relative_to(home_path).parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise BootHelperError("boot-helper state path contains a symbolic link")
    if state.resolve() != state:
        raise BootHelperError("boot-helper state path contains a symbolic link")
    root = state / "boot" / "helpers"
    for item in (state, state / "boot", root):
        if item.is_symlink():
            raise BootHelperError("boot-helper state path contains a symbolic link")
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
    elif not root.exists():
        return root
    meta = root.lstat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) & 0o077:
        raise BootHelperError("boot-helper state directory has unsafe identity or permissions")
    return root


def _paths(home: str | os.PathLike[str], helper_id: str, source_root: str | os.PathLike[str]) -> tuple[Path, Path]:
    if helper_id not in HELPERS:
        raise BootHelperError("unknown managed boot helper")
    filename, source_rel = HELPERS[helper_id]
    home_path = Path(home).expanduser().resolve()
    termux = home_path / ".termux"
    boot = termux / "boot"
    for directory in (termux, boot):
        if directory.is_symlink():
            raise BootHelperError("Termux:Boot path contains a symbolic link")
        if directory.exists() and (not directory.is_dir() or directory.resolve() != directory):
            raise BootHelperError("Termux:Boot path has an unsafe directory")
    target = boot / filename
    source = Path(source_root).resolve() / source_rel
    if source.is_symlink() or not source.is_file():
        raise BootHelperError("repository helper source is missing or unsafe")
    return target, source


def _read(path: Path, *, allow_missing: bool = False) -> tuple[bytes | None, os.stat_result | None]:
    try:
        before = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return None, None
        raise BootHelperError("managed boot helper is missing")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid():
        raise BootHelperError("managed boot helper target is not a same-user regular file")
    if stat.S_IMODE(before.st_mode) & 0o022:
        raise BootHelperError("managed boot helper target is group/world writable")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise BootHelperError("managed boot helper changed while opening")
        if opened.st_size > 256 * 1024:
            raise BootHelperError("managed boot helper exceeds the size limit")
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        after = path.lstat()
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            raise BootHelperError("managed boot helper changed while reading")
        return b"".join(chunks), before
    finally:
        os.close(fd)


def _load_json(path: Path, default):
    data, meta = _read(path, allow_missing=True)
    if meta is None or data is None:
        return default
    if stat.S_IMODE(meta.st_mode) != 0o600:
        raise BootHelperError("boot-helper private state file has unsafe permissions")
    try:
        return json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BootHelperError("boot-helper private state is corrupt") from exc


def _atomic(path: Path, data: bytes, mode: int) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, mode)
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise OSError("short atomic write")
            view = view[count:]
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if fd >= 0:
            os.close(fd)
        tmp.unlink(missing_ok=True)


def _write_state(root: Path, filename: str, value) -> None:
    _atomic(root / filename, (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(), 0o600)


def _locked(root: Path):
    lock_path = root / ".lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    meta = os.fstat(fd)
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600:
        os.close(fd)
        raise BootHelperError("boot-helper lock identity or permissions are unsafe")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _plan_id(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:32]


def _identity(root: Path) -> dict:
    value = _load_json(root / "installed.json", {"schema_version": 1, "helpers": {}})
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("helpers"), dict):
        raise BootHelperError("boot-helper identity record is invalid")
    return value


def _snapshot_record(root: Path, helper_id: str, snapshot_id: object, record: object) -> tuple[Path, dict]:
    if not isinstance(snapshot_id, str) or not re.fullmatch(r"[0-9a-f]{32}", snapshot_id):
        raise BootHelperError("rollback snapshot ID is invalid")
    if not isinstance(record, dict) or record.get("helper_id") != helper_id:
        raise BootHelperError("rollback snapshot is unavailable for this helper")
    expected_file = f"snapshots/{helper_id}-{snapshot_id}.bin"
    if record.get("file") != expected_file:
        raise BootHelperError("rollback snapshot path is invalid")
    digest = record.get("sha256")
    mode = record.get("mode")
    if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or type(mode) is not int or mode < 0 or mode > 0o777):
        raise BootHelperError("rollback snapshot metadata is invalid")
    path = root / expected_file
    if path.parent.is_symlink() or path.parent.resolve() != path.parent:
        raise BootHelperError("rollback snapshot directory is unsafe")
    return path, record


def _snapshot_data(root: Path, helper_id: str, snapshot_id: object, record: object) -> tuple[bytes, dict]:
    path, snapshot = _snapshot_record(root, helper_id, snapshot_id, record)
    backup, meta = _read(path)
    if (backup is None or meta is None or stat.S_IMODE(meta.st_mode) != 0o600
            or _sha(backup) != snapshot["sha256"]):
        raise BootHelperError("rollback snapshot failed its integrity check")
    return backup, snapshot


def _valid_plans(value: object) -> bool:
    return (isinstance(value, dict) and value.get("schema_version") == 1
            and isinstance(value.get("items"), list)
            and all(isinstance(item, dict) and isinstance(item.get("plan_id"), str)
                    for item in value["items"]))


def status(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
           source_root: str | os.PathLike[str]) -> dict[str, object]:
    root = _root(home, state_dir, create=False)
    identity = _identity(root) if root.exists() else {"helpers": {}}
    snapshot_index = _load_json(root / "snapshots.json", {"schema_version": 1, "items": {}}) if root.exists() else {"schema_version": 1, "items": {}}
    if (not isinstance(snapshot_index, dict) or snapshot_index.get("schema_version") != 1
            or not isinstance(snapshot_index.get("items"), dict)):
        raise BootHelperError("boot-helper snapshot index is invalid")
    items = []
    for helper_id in HELPERS:
        target, source = _paths(home, helper_id, source_root)
        desired, _ = _read(source)
        current, meta = _read(target, allow_missing=True)
        expected = identity.get("helpers", {}).get(helper_id, {}).get("sha256")
        digest = _sha(current) if current is not None else None
        if current is None:
            state = "missing"
        elif digest == _sha(desired or b""):
            state = "match"
        elif digest == KNOWN_LEGACY[helper_id]:
            state = "known-legacy"
        elif digest == expected:
            state = "previously-managed"
        else:
            state = "unrecognized"
        items.append({"id": helper_id, "target": str(target), "source": str(source),
                      "installed_sha256": digest, "source_sha256": _sha(desired or b""),
                      "mode": format(stat.S_IMODE(meta.st_mode), "04o") if meta else None,
                      "identity": state})
    snapshots = []
    for snapshot_id, record in snapshot_index["items"].items():
        if not isinstance(snapshot_id, str) or not re.fullmatch(r"[0-9a-f]{32}", snapshot_id):
            continue
        helper_id = record.get("helper_id") if isinstance(record, dict) else None
        if helper_id not in HELPERS:
            continue
        try:
            _snapshot_record(root, helper_id, snapshot_id, record)
        except BootHelperError:
            continue
        snapshots.append({"snapshot_id": snapshot_id, "helper_id": helper_id,
                          "created_at": record.get("created_at"), "sha256": record.get("sha256"),
                          "mode": format(record["mode"], "04o")})
    snapshots.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"component": "boot_helpers", "helpers": items, "read_only": True,
            "snapshots": snapshots[:40], "snapshot_count": len(snapshots),
            "snapshots_truncated": len(snapshots) > 40,
            "boot_delivery": "not_qualified"}


def preview(*, helper_id: str, action: str, home: str | os.PathLike[str],
            state_dir: str | os.PathLike[str], source_root: str | os.PathLike[str],
            snapshot_id: str | None = None, now: dt.datetime | None = None) -> dict[str, object]:
    if action not in {"deploy", "rollback"}:
        raise BootHelperError("action must be deploy or rollback")
    root = _root(home, state_dir, create=True)
    target, source = _paths(home, helper_id, source_root)
    lock_fd = _locked(root)
    try:
        current, meta = _read(target, allow_missing=True)
        source_data, _ = _read(source)
        identity = _identity(root)
        snapshots = _load_json(root / "snapshots.json", {"schema_version": 1, "items": {}})
        if not isinstance(snapshots, dict) or snapshots.get("schema_version") != 1 or not isinstance(snapshots.get("items"), dict):
            raise BootHelperError("boot-helper snapshot index is invalid")
        if action == "deploy":
            if current is None:
                raise BootHelperError("refusing to create missing service/recovery boot entries")
            old_hash = _sha(current)
            trusted = identity.get("helpers", {}).get(helper_id, {}).get("sha256")
            if old_hash not in {KNOWN_LEGACY[helper_id], _sha(source_data or b""), trusted}:
                raise BootHelperError("installed helper hash is unrecognized; refusing to replace it")
            after = source_data
            after_mode = stat.S_IMODE(meta.st_mode)
        else:
            snapshot = snapshots["items"].get(snapshot_id) if isinstance(snapshot_id, str) else None
            if current is None or _sha(current) != identity.get("helpers", {}).get(helper_id, {}).get("sha256"):
                raise BootHelperError("current helper does not match the recorded deployed identity")
            after, snapshot = _snapshot_data(root, helper_id, snapshot_id, snapshot)
            after_mode = snapshot["mode"]
        before_hash = _sha(current) if current is not None else None
        after_hash = _sha(after or b"")
        body = {"schema_version": 1, "helper_id": helper_id, "action": action,
                "target": str(target), "before_sha256": before_hash, "after_sha256": after_hash,
                "after_mode": after_mode,
                "snapshot_id": snapshot_id if action == "rollback" else None, "created_at": _stamp(now)}
        plan_id = _plan_id(body)
        plans = _load_json(root / "plans.json", {"schema_version": 1, "items": []})
        if not _valid_plans(plans):
            raise BootHelperError("boot-helper plan store is invalid")
        current_time = now or dt.datetime.now(dt.timezone.utc)
        plans["items"] = [p for p in plans["items"] if isinstance(p, dict)
                          and isinstance(p.get("expires_at"), str)
                          and _parse_time(p["expires_at"]) >= current_time.astimezone(dt.timezone.utc)]
        plans["items"] = plans["items"][-63:]
        plan = {**body, "plan_id": plan_id,
                "expires_at": _stamp(current_time + dt.timedelta(seconds=PLAN_TTL))}
        plans["items"].append(plan)
        _write_state(root, "plans.json", plans)
        return {"plan": plan, "before": current.decode("utf-8", "replace") if current is not None else None,
                "after": after.decode("utf-8", "replace") if after is not None else None,
                "snapshot_id": snapshot_id if action == "rollback" else None,
                "confirmation_required": True, "read_only": False}
    finally:
        os.close(lock_fd)


def apply(*, helper_id: str, action: str, home: str | os.PathLike[str],
          state_dir: str | os.PathLike[str], source_root: str | os.PathLike[str],
          confirmed: bool, plan_id: str, snapshot_id: str | None = None,
          now: dt.datetime | None = None) -> dict[str, object]:
    if not confirmed:
        raise BootHelperError("explicit confirmation is required")
    root = _root(home, state_dir, create=False)
    lock_fd = _locked(root)
    try:
        data, _ = _read(root / "plans.json")
        try:
            plans = json.loads(data or b"{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BootHelperError("boot-helper plan store is corrupt") from exc
        if not _valid_plans(plans):
            raise BootHelperError("boot-helper plan store is invalid")
        plan = next((p for p in plans["items"] if p.get("plan_id") == plan_id), None)
        if not isinstance(plan, dict):
            raise BootHelperError("preview plan is missing; create a fresh preview")
        if _parse_time(plan.get("expires_at", "")) <= (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc):
            raise BootHelperError("preview plan expired")
        target, source = _paths(home, helper_id, source_root)
        current, meta = _read(target, allow_missing=True)
        current_hash = _sha(current) if current is not None else None
        if (plan.get("helper_id") != helper_id or plan.get("action") != action
                or plan.get("snapshot_id") != (snapshot_id if action == "rollback" else None)
                or plan.get("target") != str(target) or plan.get("before_sha256") != current_hash):
            raise BootHelperError("target changed after preview; refusing to write")
        source_data, _ = _read(source)
        if action == "deploy":
            desired = source_data
            if _sha(desired or b"") != plan.get("after_sha256"):
                raise BootHelperError("repository helper changed after preview")
            if current is None or meta is None:
                raise BootHelperError("target disappeared after preview")
            snap_id = secrets.token_hex(16)
            snap_dir = root / "snapshots"
            snap_dir.mkdir(mode=0o700, exist_ok=True)
            os.chmod(snap_dir, 0o700)
            backup_name = helper_id + "-" + snap_id + ".bin"
            _atomic(snap_dir / backup_name, current, 0o600)
            index = _load_json(root / "snapshots.json", {"schema_version": 1, "items": {}})
            if not isinstance(index, dict) or index.get("schema_version") != 1 or not isinstance(index.get("items"), dict):
                raise BootHelperError("boot-helper snapshot index is invalid")
            index["items"][snap_id] = {"helper_id": helper_id, "file": "snapshots/" + backup_name,
                "sha256": current_hash, "mode": stat.S_IMODE(meta.st_mode), "created_at": _stamp(now)}
            _write_state(root, "snapshots.json", index)
            after = desired
        elif action == "rollback":
            index = _load_json(root / "snapshots.json", {"schema_version": 1, "items": {}})
            if not isinstance(index, dict) or index.get("schema_version") != 1 or not isinstance(index.get("items"), dict):
                raise BootHelperError("boot-helper snapshot index is invalid")
            snapshot = index["items"].get(snapshot_id)
            after, snapshot = _snapshot_data(root, helper_id, snapshot_id, snapshot)
            if _sha(after) != plan.get("after_sha256") or snapshot.get("mode") != plan.get("after_mode"):
                raise BootHelperError("rollback snapshot changed after preview")
            snap_id = snapshot_id
        else:
            raise BootHelperError("unsupported boot-helper action")
        # Recheck exact path identity immediately before atomic replacement.
        again, latest_meta = _read(target)
        if (latest_meta is None or meta is None or (latest_meta.st_dev, latest_meta.st_ino) != (meta.st_dev, meta.st_ino)
                or _sha(again or b"") != current_hash):
            raise BootHelperError("target identity changed before replacement")
        mode = plan.get("after_mode")
        if type(mode) is not int or mode < 0 or mode > 0o777:
            raise BootHelperError("preview plan has an invalid target mode")
        _atomic(target, after or b"", mode)
        identity = _identity(root)
        identity.setdefault("helpers", {})[helper_id] = {
            "sha256": _sha(after or b""), "source_sha256": _sha(source_data or b""),
            "snapshot_id": snap_id, "updated_at": _stamp(now), "last_action": action,
        }
        _write_state(root, "installed.json", identity)
        plans["items"] = [p for p in plans["items"] if p.get("plan_id") != plan_id]
        _write_state(root, "plans.json", plans)
        return {"helper_id": helper_id, "action": action, "target": str(target),
                "sha256": _sha(after or b""), "snapshot_id": snap_id, "changed": True,
                "boot_delivery": "not_qualified"}
    finally:
        os.close(lock_fd)
