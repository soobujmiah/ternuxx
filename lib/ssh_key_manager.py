"""Preview-first enrollment and revocation for the shared Native Termux SSH account.

Only public authorized_keys records are handled. Private keys are never accepted.
The fixed file is selected only after verifying the effective authorized_keys path for the managed Ternuxx SSH service.
"""
from __future__ import annotations

import base64
import fcntl
import json
import hashlib
import os
import re
import secrets
from pathlib import Path
import stat
import subprocess
import tempfile
import shutil

import ssh_key_inventory


_MAX_FILE_BYTES = 256 * 1024
_MAX_LINES = 1000
_FINGERPRINT_RE = re.compile(r"^SHA256:[A-Za-z0-9+/]{43}$")


class SshKeyMutationError(RuntimeError):
    pass


def _read_fixed(home: str | os.PathLike[str], uid: int,
                authorized_keys_file: str = ".ssh/authorized_keys") -> tuple[Path, bytes, int, bool]:
    root = Path(home)
    if not root.is_absolute() or ".." in root.parts:
        raise SshKeyMutationError("Native home path is invalid")
    try:
        root_stat = root.lstat()
        ssh_dir = root / ".ssh"
        dir_stat = ssh_dir.lstat()
    except OSError as exc:
        raise SshKeyMutationError("the existing Native .ssh directory is unavailable") from exc
    if (stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != uid):
        raise SshKeyMutationError("Native home ownership or path is unverified")
    if (stat.S_ISLNK(dir_stat.st_mode) or not stat.S_ISDIR(dir_stat.st_mode)
            or dir_stat.st_uid != uid or stat.S_IMODE(dir_stat.st_mode) & 0o077):
        raise SshKeyMutationError("Native .ssh directory must be owned by this account and private")
    if authorized_keys_file not in {".ssh/authorized_keys", ".ssh/ternuxx-keys/authorized_keys"}:
        raise SshKeyMutationError("authorized_keys path is not in the fixed service allowlist")
    path = root / authorized_keys_file
    if authorized_keys_file == ".ssh/ternuxx-keys/authorized_keys":
        try:
            key_dir = path.parent
            key_info = key_dir.lstat()
        except OSError as exc:
            raise SshKeyMutationError("Ternuxx SSH key directory is unavailable") from exc
        if (stat.S_ISLNK(key_info.st_mode) or not stat.S_ISDIR(key_info.st_mode)
                or key_info.st_uid != uid or stat.S_IMODE(key_info.st_mode) & 0o077):
            raise SshKeyMutationError("Ternuxx SSH key directory identity is unsafe")
    try:
        before = path.lstat()
    except FileNotFoundError:
        return path, b"", 0o600, False
    except OSError as exc:
        raise SshKeyMutationError("authorized_keys cannot be inspected safely") from exc
    if (stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode)
            or before.st_uid != uid or before.st_size > _MAX_FILE_BYTES
            or stat.S_IMODE(before.st_mode) & 0o022):
        raise SshKeyMutationError("authorized_keys type, owner, permissions, or size is unsafe")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_ino != before.st_ino
                    or opened.st_dev != before.st_dev or opened.st_uid != uid
                    or opened.st_size > _MAX_FILE_BYTES):
                raise SshKeyMutationError("authorized_keys changed during inspection")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(_MAX_FILE_BYTES + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise SshKeyMutationError("authorized_keys cannot be read safely") from exc
    if len(raw) > _MAX_FILE_BYTES:
        raise SshKeyMutationError("authorized_keys exceeds the supported size")
    try:
        raw.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise SshKeyMutationError("authorized_keys is not valid UTF-8; no changes made") from exc
    if len(raw.splitlines()) > _MAX_LINES:
        raise SshKeyMutationError("authorized_keys exceeds the supported entry count")
    return path, raw, stat.S_IMODE(before.st_mode), True


def _records(raw: bytes) -> list[bytes]:
    return raw.splitlines(keepends=True)


def _read_wire_string(blob: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(blob):
        raise ValueError("truncated SSH key")
    length = int.from_bytes(blob[offset:offset + 4], "big")
    start = offset + 4
    end = start + length
    if length == 0 or end > len(blob):
        raise ValueError("invalid SSH key field")
    return blob[start:end], end


def _validate_key_blob(public_key: str, key_type: str) -> bool:
    import base64
    import shlex
    try:
        fields = shlex.split(public_key, comments=False, posix=True)
        if len(fields) < 2 or fields[0] != key_type:
            return False
        blob = base64.b64decode(fields[1].encode("ascii"), validate=True)
        embedded_type, offset = _read_wire_string(blob, 0)
        if embedded_type.decode("ascii") != key_type:
            return False
        if key_type == "ssh-ed25519":
            key, offset = _read_wire_string(blob, offset)
            return len(key) == 32 and offset == len(blob)
        if key_type == "ssh-rsa":
            exponent, offset = _read_wire_string(blob, offset)
            modulus, offset = _read_wire_string(blob, offset)
            return bool(exponent and modulus) and offset == len(blob)
        if key_type.startswith("ecdsa-sha2-"):
            curve, offset = _read_wire_string(blob, offset)
            point, offset = _read_wire_string(blob, offset)
            curve_name = key_type.removeprefix("ecdsa-sha2-")
            expected = {"nistp256": 65, "nistp384": 97, "nistp521": 133}.get(curve_name)
            return (expected is not None and curve == curve_name.encode("ascii")
                    and len(point) == expected and point[:1] == b"\x04" and offset == len(blob))
        if key_type == "sk-ssh-ed25519@openssh.com":
            key, offset = _read_wire_string(blob, offset)
            application, offset = _read_wire_string(blob, offset)
            return len(key) == 32 and application.startswith(b"ssh:") and offset == len(blob)
    except (ValueError, UnicodeError, IndexError):
        return False
    return False


def _validate_openssh_public_key(public_key: str, expected_fingerprint: str) -> bool:
    ssh_keygen = shutil.which("ssh-keygen")
    if not ssh_keygen:
        raise SshKeyMutationError("ssh-keygen is unavailable; public-key validation failed closed")
    try:
        result = subprocess.run(
            [ssh_keygen, "-lf", "-"], input=public_key + "\n",
            capture_output=True, text=True, timeout=3, check=False,
            env={"HOME": os.environ.get("HOME", ""), "LANG": "C", "LC_ALL": "C",
                 "PATH": os.environ.get("PATH", "")},
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SshKeyMutationError("ssh-keygen could not validate the public key")
    fields = result.stdout.split()
    return result.returncode == 0 and len(fields) >= 2 and fields[1] == expected_fingerprint


def _fingerprint_line(line: bytes) -> tuple[str, str] | None:
    try:
        value = line.decode("utf-8").rstrip("\r\n")
    except UnicodeError:
        return None
    parsed = ssh_key_inventory._parse_line(value)
    if not parsed or parsed.get("status") != "valid":
        return None
    return parsed["fingerprint"], parsed["key_type"]


def _payload(action: str, raw: bytes, replacement: bytes) -> bytes:
    if action == "add":
        if not raw:
            return replacement + b"\n"
        return raw + (b"" if raw.endswith(b"\n") else b"\n") + replacement + b"\n"
    return replacement


def preview(action: str, *, home: str | os.PathLike[str], uid: int,
            fingerprint: str | None = None, public_key: str | None = None,
            authorized_keys_file: str = ".ssh/authorized_keys") -> dict[str, object]:
    if action not in {"add", "remove"}:
        raise SshKeyMutationError("action must be add or remove")
    if action == "add":
        if (not isinstance(public_key, str) or len(public_key) > 16_384
                or any(ord(character) < 32 or ord(character) == 127 for character in public_key)):
            raise SshKeyMutationError("provide one bounded public-key line without control characters")
        parsed = ssh_key_inventory._parse_line(public_key)
        if (not parsed or parsed.get("status") != "valid"
                or (fingerprint is not None and parsed.get("fingerprint") != fingerprint)
                or not _validate_key_blob(public_key, parsed.get("key_type", ""))
                or not _validate_openssh_public_key(public_key, parsed.get("fingerprint", ""))):
            raise SshKeyMutationError("public key is malformed or its fingerprint does not match")
        fingerprint = parsed["fingerprint"]
        import shlex
        try:
            fields = shlex.split(public_key, comments=False, posix=True)
        except ValueError as exc:
            raise SshKeyMutationError("public key line is malformed") from exc
        if not fields or fields[0] != parsed.get("key_type"):
            raise SshKeyMutationError("authorized_keys options require an explicit advanced policy workflow")
        replacement = public_key.strip().encode("utf-8")
    else:
        replacement = b""
        if not isinstance(fingerprint, str) or not _FINGERPRINT_RE.fullmatch(fingerprint):
            raise SshKeyMutationError("a valid SHA256 key fingerprint is required")

    assert fingerprint is not None
    path, raw, _mode, before_exists = _read_fixed(home, uid, authorized_keys_file)
    records = _records(raw)
    found = []
    kept = []
    for record in records:
        item = _fingerprint_line(record)
        if item and item[0] == fingerprint:
            found.append(record)
        else:
            kept.append(record)
    if action == "add":
        exists = bool(found)
        desired = raw if exists else _payload("add", raw, replacement)
        changed = not exists
    else:
        exists = bool(found)
        if exists and not any(_fingerprint_line(record) and _fingerprint_line(record)[0] != fingerprint
                              for record in records):
            raise SshKeyMutationError(
                "cannot remove the last authorized key; enroll and verify a replacement key first")
        desired = b"".join(kept)
        changed = exists
    before_hash = hashlib.sha256(raw).hexdigest()
    after_hash = hashlib.sha256(desired).hexdigest()
    plan_material = "\0".join((action, fingerprint, before_hash, after_hash, str(uid), path.name, str(before_exists))).encode()
    plan_id = hashlib.sha256(plan_material).hexdigest()[:24]
    sample = ssh_key_inventory._parse_line(public_key) if action == "add" and public_key else None
    if not sample and found:
        try:
            sample = ssh_key_inventory._parse_line(found[0].decode("utf-8").rstrip("\r\n"))
        except UnicodeError:
            sample = None
    return {
        "status": "ready" if changed else "already_in_requested_state",
        "action": action,
        "fingerprint": fingerprint,
        "key_type": sample.get("key_type", "unknown") if sample else "unknown",
        "target": authorized_keys_file,
        "affects_services": (["Ternuxx managed SSH service"]
                             if authorized_keys_file == ".ssh/ternuxx-keys/authorized_keys"
                             else ["external Native SSH configurations using this file"]),
        "changed": changed,
        "requires_confirmation": changed,
        "plan_id": plan_id,
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "before_exists": before_exists,
        "matching_entries": len(found),
        "recovery": "re-enrollment of this public key restores its access",
        "secret_values_returned": False,
    }


def apply(action: str, *, home: str | os.PathLike[str], uid: int, fingerprint: str | None = None,
          confirmed: bool, plan_id: str, public_key: str | None = None,
          authorized_keys_file: str = ".ssh/authorized_keys") -> dict[str, object]:
    path, _raw, _mode, _exists = _read_fixed(home, uid, authorized_keys_file)
    lock_path = path.parent / ".ternuxx-authorized-keys.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise SshKeyMutationError("could not acquire the private SSH credential lock") from exc
    try:
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != uid:
            raise SshKeyMutationError("SSH credential lock ownership is unverified")
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        plan = preview(action, home=home, uid=uid, fingerprint=fingerprint, public_key=public_key,
                       authorized_keys_file=authorized_keys_file)
        if not plan["changed"]:
            return plan
        if not confirmed:
            return {**plan, "status": "confirmation_required"}
        if plan_id != plan["plan_id"]:
            return {**plan, "status": "stale_plan", "changed": False}
        fingerprint = str(plan["fingerprint"])
        _path, current, current_mode, current_exists = _read_fixed(home, uid, authorized_keys_file)
        if action == "add":
            assert public_key is not None
            desired = _payload("add", current, public_key.strip().encode("utf-8"))
        else:
            desired = b"".join(
                record for record in _records(current)
                if not ((_fingerprint_line(record) or ("", ""))[0] == fingerprint)
            )
        if hashlib.sha256(current).hexdigest() != plan["before_sha256"] or hashlib.sha256(desired).hexdigest() != plan["after_sha256"]:
            raise SshKeyMutationError("authorized_keys changed after preview; create a new preview")
        rollback_id = _write_rollback_snapshot(
            path.parent, uid, action, fingerprint, current, current_mode, current_exists,
            str(plan["after_sha256"]),
        )
        temp_fd, temp_name = tempfile.mkstemp(prefix=".ternuxx-authorized-keys-", dir=path.parent)
        try:
            os.fchmod(temp_fd, 0o600)
            os.fchown(temp_fd, uid, -1)
            with os.fdopen(temp_fd, "wb") as stream:
                stream.write(desired)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
            dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
        _set_rollback_snapshot_status(path.parent, uid, rollback_id, "applied")
        return {**plan, "status": "complete", "changed": True, "rollback_id": rollback_id}
    finally:
        os.close(lock_fd)


_ROLLBACK_DIR = ".ternuxx-key-recovery"
_ROLLBACK_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def _rollback_root(ssh_dir: Path, uid: int, *, create: bool) -> Path:
    root = ssh_dir / _ROLLBACK_DIR
    try:
        meta = root.lstat()
    except FileNotFoundError:
        if not create:
            return root
        try:
            root.mkdir(mode=0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise SshKeyMutationError("cannot create private SSH recovery storage") from exc
        meta = root.lstat()
    if (stat.S_ISLNK(meta.st_mode) or not stat.S_ISDIR(meta.st_mode)
            or meta.st_uid != uid or stat.S_IMODE(meta.st_mode) != 0o700):
        raise SshKeyMutationError("SSH recovery storage is not a private owned directory")
    return root


def _atomic_private_json(root: Path, name: str, value: dict[str, object], uid: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=root)
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, uid, -1)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / name)
        dir_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as exc:
        raise SshKeyMutationError("cannot persist private SSH recovery metadata") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _read_rollback_snapshot(ssh_dir: Path, uid: int, rollback_id: str) -> tuple[Path, dict[str, object]]:
    if not isinstance(rollback_id, str) or not _ROLLBACK_ID_RE.fullmatch(rollback_id):
        raise SshKeyMutationError("SSH recovery ID is invalid")
    root = _rollback_root(ssh_dir, uid, create=False)
    path = root / (rollback_id + ".json")
    try:
        meta = path.lstat()
        if (stat.S_ISLNK(meta.st_mode) or not stat.S_ISREG(meta.st_mode)
                or meta.st_uid != uid or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_size > _MAX_FILE_BYTES * 2):
            raise SshKeyMutationError("SSH recovery record identity or permissions are unsafe")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_dev != meta.st_dev
                    or opened.st_ino != meta.st_ino or opened.st_uid != uid
                    or stat.S_IMODE(opened.st_mode) != 0o600 or opened.st_size > _MAX_FILE_BYTES * 2):
                raise SshKeyMutationError("SSH recovery record changed during inspection")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(_MAX_FILE_BYTES * 2 + 1)
        finally:
            os.close(fd)
        if len(raw) > _MAX_FILE_BYTES * 2:
            raise SshKeyMutationError("SSH recovery record exceeds its size limit")
        value = json.loads(raw.decode("utf-8"))
    except FileNotFoundError as exc:
        raise SshKeyMutationError("SSH recovery record does not exist") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise SshKeyMutationError("SSH recovery record is unreadable or invalid") from exc
    fields = {"schema_version", "rollback_id", "status", "action", "fingerprint", "before_sha256",
              "after_sha256", "before_exists", "before_mode", "before_content_b64"}
    if (not isinstance(value, dict) or set(value) != fields or value.get("schema_version") != 1
            or value.get("rollback_id") != rollback_id or value.get("status") not in {"prepared", "applied", "rolled_back"}
            or value.get("action") not in {"add", "remove"} or not isinstance(value.get("fingerprint"), str)
            or not isinstance(value.get("before_exists"), bool) or type(value.get("before_mode")) is not int
            or not isinstance(value.get("before_content_b64"), str)
            or value.get("before_mode") < 0 or value.get("before_mode") > 0o777
            or value.get("before_mode") & 0o022
            or (not value.get("before_exists") and value.get("before_mode") != 0o600)):
        raise SshKeyMutationError("SSH recovery record schema is invalid")
    try:
        before = base64.b64decode(value["before_content_b64"], validate=True)
    except (ValueError, TypeError) as exc:
        raise SshKeyMutationError("SSH recovery snapshot data is invalid") from exc
    if (len(before) > _MAX_FILE_BYTES or hashlib.sha256(before).hexdigest() != value["before_sha256"]
            or (not value["before_exists"] and before)):
        raise SshKeyMutationError("SSH recovery snapshot integrity check failed")
    return path, value


def _write_rollback_snapshot(ssh_dir: Path, uid: int, action: str, fingerprint: str,
                             before: bytes, before_mode: int, before_exists: bool,
                             after_hash: str) -> str:
    rollback_id = secrets.token_hex(16)
    root = _rollback_root(ssh_dir, uid, create=True)
    value = {
        "schema_version": 1, "rollback_id": rollback_id, "status": "prepared",
        "action": action, "fingerprint": fingerprint,
        "before_sha256": hashlib.sha256(before).hexdigest(), "after_sha256": after_hash,
        "before_exists": before_exists, "before_mode": before_mode,
        "before_content_b64": base64.b64encode(before).decode("ascii"),
    }
    _atomic_private_json(root, rollback_id + ".json", value, uid)
    return rollback_id


def _set_rollback_snapshot_status(ssh_dir: Path, uid: int, rollback_id: str, status: str) -> None:
    root = _rollback_root(ssh_dir, uid, create=False)
    _path, value = _read_rollback_snapshot(ssh_dir, uid, rollback_id)
    value["status"] = status
    _atomic_private_json(root, rollback_id + ".json", value, uid)


def rollback_list(*, home: str | os.PathLike[str], uid: int,
                  authorized_keys_file: str = ".ssh/authorized_keys") -> dict[str, object]:
    _path, _raw, _mode, _exists = _read_fixed(home, uid, authorized_keys_file)
    ssh_dir = _path.parent
    root = _rollback_root(ssh_dir, uid, create=False)
    entries = []
    if root.exists():
        for path in sorted(root.glob("*.json")):
            _record_path, value = _read_rollback_snapshot(ssh_dir, uid, path.stem)
            entries.append({"rollback_id": value["rollback_id"], "status": value["status"],
                            "action": value["action"], "fingerprint": value["fingerprint"],
                            "before_sha256": value["before_sha256"], "after_sha256": value["after_sha256"]})
    return {"entries": entries, "count": len(entries), "contains_public_key_snapshot": bool(entries),
            "private_key_material_stored": False}


def rollback_preview(rollback_id: str, *, home: str | os.PathLike[str], uid: int,
                     authorized_keys_file: str = ".ssh/authorized_keys") -> dict[str, object]:
    path, current, current_mode, current_exists = _read_fixed(home, uid, authorized_keys_file)
    ssh_dir = path.parent
    _record_path, value = _read_rollback_snapshot(ssh_dir, uid, rollback_id)
    current_hash = hashlib.sha256(current).hexdigest()
    before_hash = str(value["before_sha256"])
    after_hash = str(value["after_sha256"])
    matches_before = (current_hash == before_hash and current_exists == value["before_exists"]
                      and (not current_exists or current_mode == value["before_mode"]))
    matches_after = current_exists and current_hash == after_hash and current_mode == 0o600
    can_restore = value["status"] != "rolled_back" and matches_after
    not_applied = value["status"] == "prepared" and matches_before
    conflict = not can_restore and not matches_before and not not_applied
    core = {"rollback_id": rollback_id, "action": value["action"], "fingerprint": value["fingerprint"],
            "target": authorized_keys_file, "current_sha256": current_hash,
            "before_sha256": before_hash, "after_sha256": after_hash,
            "can_restore": can_restore, "conflict": conflict,
            "affects_services": (["Ternuxx managed SSH service"]
                                 if authorized_keys_file == ".ssh/ternuxx-keys/authorized_keys"
                                 else ["external Native SSH configurations using this file"]),
            "private_key_material_stored": False}
    plan_id = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    status = "ready" if can_restore else ("conflict" if conflict else "not_applied" if not_applied else "already_restored")
    return {**core, "status": status,
            "requires_confirmation": can_restore, "changed": can_restore, "plan_id": plan_id,
            "effect": "Restore the exact previous authorized_keys bytes only if the current file still matches this mutation's recorded post-state."}


def rollback_apply(rollback_id: str, *, home: str | os.PathLike[str], uid: int,
                  confirmed: bool, plan_id: str,
                  authorized_keys_file: str = ".ssh/authorized_keys") -> dict[str, object]:
    path, _raw, _mode, _exists = _read_fixed(home, uid, authorized_keys_file)
    lock_path = path.parent / ".ternuxx-authorized-keys.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise SshKeyMutationError("could not acquire the private SSH credential lock") from exc
    try:
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != uid:
            raise SshKeyMutationError("SSH credential lock ownership is unverified")
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        current = rollback_preview(rollback_id, home=home, uid=uid,
                                   authorized_keys_file=authorized_keys_file)
        if not current["can_restore"]:
            return current
        if not confirmed:
            return {**current, "status": "confirmation_required"}
        if not isinstance(plan_id, str) or plan_id != current["plan_id"]:
            return {**current, "status": "stale_plan", "changed": False}
        ssh_dir = path.parent
        record_path, value = _read_rollback_snapshot(ssh_dir, uid, rollback_id)
        before = base64.b64decode(str(value["before_content_b64"]), validate=True)
        if value["before_exists"]:
            fd, temp = tempfile.mkstemp(prefix=".ternuxx-authorized-keys-rollback-", dir=ssh_dir)
            try:
                os.fchmod(fd, int(value["before_mode"]))
                os.fchown(fd, uid, -1)
                with os.fdopen(fd, "wb") as stream:
                    fd = -1
                    stream.write(before); stream.flush(); os.fsync(stream.fileno())
                os.replace(temp, path)
            finally:
                if fd >= 0: os.close(fd)
                try: os.unlink(temp)
                except FileNotFoundError: pass
        else:
            path.unlink()
        dir_fd = os.open(ssh_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try: os.fsync(dir_fd)
        finally: os.close(dir_fd)
        root = record_path.parent
        value["status"] = "rolled_back"
        _atomic_private_json(root, rollback_id + ".json", value, uid)
        return {**current, "status": "complete", "changed": True,
                "restored_sha256": hashlib.sha256(before).hexdigest()}
    finally:
        os.close(lock_fd)
