#!/usr/bin/env python3
"""Atomic, private reboot-continuity checkpoints for native Termux."""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile
import uuid


TEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")
COMMIT_RE = re.compile(r"^(?:unknown|[a-fA-F0-9]{7,64})$")
NEXT_ACTIONS = {
    "owner_verify_after_reboot",
    "inspect_native_services",
    "review_pending_tests",
    "manual_review",
}
TASK_STATES = {"prepared", "pending", "blocked", "verified"}


class CheckpointError(Exception):
    """Expected, safe-to-report checkpoint failure."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_boot_id() -> str | None:
    """Read the kernel boot identifier when Android exposes it."""
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip().lower()
    except (OSError, UnicodeError):
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        return None


def _private_root(home: str | os.PathLike[str], state_dir: str | os.PathLike[str]) -> Path:
    home_path = Path(home).resolve(strict=True)
    raw = Path(state_dir)
    if not raw.is_absolute():
        raw = home_path / raw
    raw = Path(os.path.abspath(raw))
    try:
        relative = raw.relative_to(home_path)
    except ValueError as exc:
        raise CheckpointError("state directory must resolve inside Termux HOME") from exc
    if not relative.parts:
        raise CheckpointError("state directory cannot be Termux HOME itself")

    cursor = home_path
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise CheckpointError("state directory contains a symbolic link")
    root = raw.resolve(strict=False)
    try:
        root.relative_to(home_path)
    except ValueError as exc:
        raise CheckpointError("state directory must resolve inside Termux HOME") from exc
    return root


def _ensure_private_dir(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise CheckpointError(f"cannot create private checkpoint directory ({exc.__class__.__name__})") from exc
    try:
        mode = stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
    except OSError as exc:
        raise CheckpointError("cannot inspect checkpoint directory") from exc
    if not path.is_dir() or path.is_symlink() or mode & 0o077:
        raise CheckpointError("checkpoint directory is not a private, owned directory")


def _atomic_write(path: Path, payload: dict[str, object], *, exclusive: bool) -> None:
    _ensure_private_dir(path.parent)
    lock_path = path.parent / ".checkpoint-store.lock"
    lock_fd = -1
    fd = -1
    temporary = ""
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or stat.S_IMODE(lock_stat.st_mode) & 0o077:
            raise CheckpointError("checkpoint store lock is not a private regular file")
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if exclusive and path.exists():
            raise CheckpointError("checkpoint ID already exists; refusing to overwrite it")
        fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            # Cooperating writers serialize through the private store lock;
            # same-directory replace is atomic on Termux even where os.link()
            # is unavailable in its Python build.
            os.replace(temporary, path)
            temporary = ""
        else:
            os.replace(temporary, path)
            temporary = ""
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except CheckpointError:
        raise
    except OSError as exc:
        raise CheckpointError(f"cannot persist checkpoint ({exc.__class__.__name__})") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        if lock_fd >= 0:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)


def prepare(
    *,
    home: str | os.PathLike[str],
    state_dir: str | os.PathLike[str],
    test_id: str,
    repository: str = "soobujmiah/ternuxx",
    commit: str = "unknown",
    worktree_state: str = "unknown",
    task_state: str = "prepared",
    pending_tests: list[str] | None = None,
    next_safe_action: str = "owner_verify_after_reboot",
    boot_id: str | None = None,
) -> dict[str, object]:
    if not TEST_ID_RE.fullmatch(test_id):
        raise CheckpointError("test ID must contain only letters, digits, dot, underscore, colon, or hyphen")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}/[A-Za-z0-9_.-]{1,128}", repository):
        raise CheckpointError("repository must be an owner/repository identifier")
    if not COMMIT_RE.fullmatch(commit):
        raise CheckpointError("commit must be a hexadecimal Git ID or 'unknown'")
    if worktree_state not in {"clean", "dirty", "unknown"}:
        raise CheckpointError("worktree state must be clean, dirty, or unknown")
    if task_state not in TASK_STATES:
        raise CheckpointError("unsupported task state")
    if next_safe_action not in NEXT_ACTIONS:
        raise CheckpointError("unsupported next safe action")
    pending = pending_tests or []
    if len(pending) > 128 or any(not TEST_ID_RE.fullmatch(item) for item in pending):
        raise CheckpointError("pending tests must be at most 128 valid test IDs")
    if len(set(pending)) != len(pending):
        raise CheckpointError("pending test IDs must be unique")

    normalized_boot_id = None
    if boot_id is not None:
        try:
            normalized_boot_id = str(uuid.UUID(boot_id))
        except ValueError as exc:
            raise CheckpointError("boot identifier is malformed") from exc
    else:
        normalized_boot_id = read_boot_id()

    root = _private_root(home, state_dir)
    checkpoints = root / "continuity" / "checkpoints"
    _ensure_private_dir(checkpoints)
    checkpoint_id = uuid.uuid4().hex
    record: dict[str, object] = {
        "schema_version": 1,
        "checkpoint_id": checkpoint_id,
        "test_id": test_id,
        "nonce": secrets.token_urlsafe(32),
        "previous_boot_id": normalized_boot_id,
        "prepared_at": _utc_now(),
        "repository": {
            "id": repository,
            "commit": commit.lower() if commit != "unknown" else commit,
            "worktree_state": worktree_state,
        },
        "task": {
            "state": task_state,
            "pending_tests": list(pending),
            "next_safe_action": next_safe_action,
            "automatic_resume": False,
        },
    }
    _atomic_write(checkpoints / f"{checkpoint_id}.json", record, exclusive=True)
    return {"checkpoint_id": checkpoint_id, "test_id": test_id, "state": "prepared"}


def verify(
    *,
    home: str | os.PathLike[str],
    state_dir: str | os.PathLike[str],
    checkpoint_id: str,
    current_boot_id: str | None = None,
    expected_record_sha256: str | None = None,
) -> dict[str, object]:
    if not re.fullmatch(r"[a-f0-9]{32}", checkpoint_id):
        raise CheckpointError("invalid checkpoint ID")
    root = _private_root(home, state_dir)
    checkpoints = root / "continuity" / "checkpoints"
    checkpoint_path = checkpoints / f"{checkpoint_id}.json"
    try:
        mode = stat.S_IMODE(checkpoint_path.stat(follow_symlinks=False).st_mode)
        if checkpoint_path.is_symlink() or mode & 0o077:
            raise CheckpointError("checkpoint file is not private")
        if checkpoint_path.stat().st_size > 128 * 1024:
            raise CheckpointError("checkpoint exceeds the size limit")
        record = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except CheckpointError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise CheckpointError("checkpoint is unavailable or invalid") from exc
    if not isinstance(record, dict) or record.get("schema_version") != 1 or record.get("checkpoint_id") != checkpoint_id:
        raise CheckpointError("checkpoint identity or schema is invalid")
    required = {"schema_version", "checkpoint_id", "test_id", "nonce", "previous_boot_id", "prepared_at", "repository", "task"}
    if set(record) != required or not TEST_ID_RE.fullmatch(str(record.get("test_id", ""))):
        raise CheckpointError("checkpoint fields do not match the supported schema")
    if not isinstance(record.get("nonce"), str) or len(record["nonce"]) < 32:
        raise CheckpointError("checkpoint nonce is invalid")
    task = record.get("task")
    repository = record.get("repository")
    if not isinstance(task, dict) or set(task) != {"state", "pending_tests", "next_safe_action", "automatic_resume"}:
        raise CheckpointError("checkpoint task record is invalid")
    if task.get("state") not in TASK_STATES or task.get("next_safe_action") not in NEXT_ACTIONS or task.get("automatic_resume") is not False:
        raise CheckpointError("checkpoint task policy is invalid")
    if not isinstance(task.get("pending_tests"), list) or len(task["pending_tests"]) > 128:
        raise CheckpointError("checkpoint pending test list is invalid")
    if not isinstance(repository, dict) or set(repository) != {"id", "commit", "worktree_state"}:
        raise CheckpointError("checkpoint repository record is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}/[A-Za-z0-9_.-]{1,128}", str(repository.get("id", ""))):
        raise CheckpointError("checkpoint repository ID is invalid")
    if not COMMIT_RE.fullmatch(str(repository.get("commit", ""))) or repository.get("worktree_state") not in {"clean", "dirty", "unknown"}:
        raise CheckpointError("checkpoint repository metadata is invalid")
    if any(not isinstance(item, str) or not TEST_ID_RE.fullmatch(item) for item in task["pending_tests"]):
        raise CheckpointError("checkpoint contains an invalid pending test ID")
    if len(set(task["pending_tests"])) != len(task["pending_tests"]):
        raise CheckpointError("checkpoint contains duplicate pending test IDs")
    record_digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if expected_record_sha256 is not None and not secrets.compare_digest(record_digest, expected_record_sha256):
        raise CheckpointError("checkpoint changed after preview; create a new verification preview")
    previous = record.get("previous_boot_id")
    if current_boot_id is None:
        current_boot_id = read_boot_id()
    if current_boot_id is not None:
        try:
            current_boot_id = str(uuid.UUID(current_boot_id))
        except ValueError as exc:
            raise CheckpointError("current boot identifier is malformed") from exc

    if previous is None or current_boot_id is None:
        outcome = "boot_id_unavailable"
    elif previous == current_boot_id:
        outcome = "same_boot"
    else:
        outcome = "reboot_detected"
    verification: dict[str, object] = {
        "schema_version": 1,
        "checkpoint_id": checkpoint_id,
        "test_id": record.get("test_id"),
        "verified_at": _utc_now(),
        "previous_boot_id": previous,
        "current_boot_id": current_boot_id,
        "outcome": outcome,
        "task_state": (record.get("task") or {}).get("state") if isinstance(record.get("task"), dict) else "unknown",
        "pending_tests": (record.get("task") or {}).get("pending_tests", []) if isinstance(record.get("task"), dict) else [],
        "record_sha256": record_digest,
        "service_readiness": "not_collected",
        "automatic_resume": False,
    }
    report_dir = checkpoints / "verification"
    _ensure_private_dir(report_dir)
    evidence_key = current_boot_id or uuid.uuid4().hex
    report_path = report_dir / f"{checkpoint_id}.{evidence_key}.json"
    if not report_path.exists():
        _atomic_write(report_path, verification, exclusive=True)
    return {"checkpoint_id": checkpoint_id, "test_id": record.get("test_id"), "outcome": outcome, "automatic_resume": False}



def _plan_id(action: str, payload: dict[str, object]) -> str:
    encoded = json.dumps({"action": action, "payload": payload}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def prepare_preview(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str], test_id: str,
                    repository: str = "soobujmiah/ternuxx", commit: str = "unknown",
                    worktree_state: str = "unknown", task_state: str = "prepared",
                    pending_tests: list[str] | None = None,
                    next_safe_action: str = "owner_verify_after_reboot", boot_id: str | None = None) -> dict[str, object]:
    """Validate checkpoint inputs and return a stable, non-writing plan."""
    if not TEST_ID_RE.fullmatch(test_id):
        raise CheckpointError("invalid test ID")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}/[A-Za-z0-9_.-]{1,128}", repository):
        raise CheckpointError("repository must be an owner/repository identifier")
    if not COMMIT_RE.fullmatch(commit) or worktree_state not in {"clean", "dirty", "unknown"}:
        raise CheckpointError("repository metadata is invalid")
    if task_state not in TASK_STATES or next_safe_action not in NEXT_ACTIONS:
        raise CheckpointError("task state or next safe action is invalid")
    pending = pending_tests or []
    if len(pending) > 128 or any(not isinstance(item, str) or not TEST_ID_RE.fullmatch(item) for item in pending) or len(set(pending)) != len(pending):
        raise CheckpointError("pending test list is invalid")
    if boot_id is None:
        boot_id = read_boot_id()
    if boot_id is not None:
        try:
            boot_id = str(uuid.UUID(boot_id))
        except (ValueError, TypeError) as exc:
            raise CheckpointError("boot identifier is malformed") from exc
    root = _private_root(home, state_dir)
    details = {"test_id": test_id, "repository": repository, "commit": commit.lower() if commit != "unknown" else commit,
               "worktree_state": worktree_state, "task_state": task_state, "pending_tests": list(pending),
               "next_safe_action": next_safe_action, "boot_id": boot_id,
               "checkpoint_directory": str(root / "continuity" / "checkpoints"), "automatic_resume": False}
    return {"plan_id": _plan_id("continuity.prepare", details), "action": "create_private_checkpoint",
            "details": details, "read_only": True, "automatic_resume": False,
            "warning": "Creates a private checkpoint record; it does not reboot or resume work."}


def verify_preview(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
                   checkpoint_id: str, current_boot_id: str | None = None) -> dict[str, object]:
    """Validate a checkpoint and preview its evidence-only verification."""
    if not re.fullmatch(r"[a-f0-9]{32}", checkpoint_id):
        raise CheckpointError("invalid checkpoint ID")
    root = _private_root(home, state_dir)
    path = root / "continuity" / "checkpoints" / f"{checkpoint_id}.json"
    try:
        info = path.stat(follow_symlinks=False)
        if path.is_symlink() or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 128 * 1024:
            raise CheckpointError("checkpoint file is not private or exceeds the size limit")
        record = json.loads(path.read_text(encoding="utf-8"))
    except CheckpointError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise CheckpointError("checkpoint is unavailable or invalid") from exc
    if not isinstance(record, dict) or record.get("schema_version") != 1 or record.get("checkpoint_id") != checkpoint_id or not TEST_ID_RE.fullmatch(str(record.get("test_id", ""))):
        raise CheckpointError("checkpoint identity or schema is invalid")
    required = {"schema_version", "checkpoint_id", "test_id", "nonce", "previous_boot_id", "prepared_at", "repository", "task"}
    task, repository = record.get("task"), record.get("repository")
    if set(record) != required or not isinstance(record.get("nonce"), str) or len(record["nonce"]) < 32:
        raise CheckpointError("checkpoint fields or nonce are invalid")
    if not isinstance(task, dict) or set(task) != {"state", "pending_tests", "next_safe_action", "automatic_resume"} or task.get("state") not in TASK_STATES or task.get("next_safe_action") not in NEXT_ACTIONS or task.get("automatic_resume") is not False:
        raise CheckpointError("checkpoint task record is invalid")
    if (not isinstance(task.get("pending_tests"), list) or len(task["pending_tests"]) > 128
            or any(not isinstance(item, str) or not TEST_ID_RE.fullmatch(item) for item in task["pending_tests"])
            or len(set(task["pending_tests"])) != len(task["pending_tests"])):
        raise CheckpointError("checkpoint pending tests are invalid")
    if (not isinstance(repository, dict) or set(repository) != {"id", "commit", "worktree_state"}
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}/[A-Za-z0-9_.-]{1,128}", str(repository.get("id", "")))
            or not COMMIT_RE.fullmatch(str(repository.get("commit", "")))
            or repository.get("worktree_state") not in {"clean", "dirty", "unknown"}):
        raise CheckpointError("checkpoint repository metadata is invalid")
    previous = record.get("previous_boot_id")
    observed = current_boot_id if current_boot_id is not None else read_boot_id()
    for value, label in ((previous, "checkpoint"), (observed, "current")):
        if value is not None:
            try:
                uuid.UUID(value)
            except (ValueError, TypeError) as exc:
                raise CheckpointError(f"{label} boot identifier is malformed") from exc
    outcome = "boot_id_unavailable" if previous is None or observed is None else ("same_boot" if previous == observed else "reboot_detected")
    record_digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    details = {"checkpoint_id": checkpoint_id, "test_id": record["test_id"], "previous_boot_id": previous,
               "current_boot_id": observed, "outcome": outcome, "record_sha256": record_digest}
    return {"plan_id": _plan_id("continuity.verify", details), "action": "record_continuity_observation",
            "details": details, "read_only": True, "automatic_resume": False,
            "warning": "Writes a verification report only; it does not reboot or resume work."}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tx cp")
    parser.add_argument("--home", default=os.environ.get("HOME", ""), help=argparse.SUPPRESS)
    parser.add_argument("--state-dir", default=os.environ.get("TERNUXX_STATE_DIR", ""), help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--test-id", required=True)
    prep.add_argument("--repository", default="soobujmiah/ternuxx")
    prep.add_argument("--commit", default="unknown")
    prep.add_argument("--worktree-state", choices=("clean", "dirty", "unknown"), default="unknown")
    prep.add_argument("--task-state", choices=tuple(sorted(TASK_STATES)), default="prepared")
    prep.add_argument("--pending-test", action="append", default=[])
    prep.add_argument("--next-safe-action", choices=tuple(sorted(NEXT_ACTIONS)), default="owner_verify_after_reboot")
    ver = commands.add_parser("verify")
    ver.add_argument("checkpoint_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not args.home or not args.state_dir:
            raise CheckpointError("HOME and Ternuxx state directory must be configured")
        if args.command == "prepare":
            result = prepare(
                home=args.home,
                state_dir=args.state_dir,
                test_id=args.test_id,
                repository=args.repository,
                commit=args.commit,
                worktree_state=args.worktree_state,
                task_state=args.task_state,
                pending_tests=args.pending_test,
                next_safe_action=args.next_safe_action,
            )
        else:
            result = verify(home=args.home, state_dir=args.state_dir, checkpoint_id=args.checkpoint_id)
    except CheckpointError as exc:
        result = {"error": {"code": "checkpoint_error", "message": str(exc)}}
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"Checkpoint failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"Checkpoint {result['checkpoint_id']}: {result.get('state', result.get('outcome'))}")
        print("Pending operations are never executed automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
