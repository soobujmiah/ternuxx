#!/usr/bin/env python3
"""Preview-first deployment and rollback for the fixed Ternuxx Runit run file."""
from __future__ import annotations

import base64
import difflib
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from typing import Callable

import operation_journal
import runit_service

SERVICE_ID = "ternuxx-sshd"
MAX_FILE_BYTES = 256 * 1024


class DeploymentError(RuntimeError):
    """A safe precondition, deployment, or recovery step failed."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _paths(prefix: str | os.PathLike[str], source: str | os.PathLike[str] | None) -> tuple[Path, Path, Path]:
    prefix_path = Path(prefix)
    target = prefix_path / "var/service" / SERVICE_ID / "run"
    source_path = (Path(source) if source is not None else
                   Path(__file__).resolve().parents[1] / "scripts/termux-services" / SERVICE_ID / "run")
    return prefix_path, target, source_path


def _safe_owned_file(path: Path, *, executable: bool = False, max_bytes: int = MAX_FILE_BYTES) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise DeploymentError("service deployment path is unavailable") from exc
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid() or info.st_mode & 0o022
            or (executable and not info.st_mode & 0o100)):
        raise DeploymentError("service deployment path identity is unsafe")
    if info.st_size > max_bytes:
        raise DeploymentError("service definition exceeds the bounded deployment size")
    return info


def _safe_target(prefix: Path, target: Path) -> os.stat_result:
    service_root = prefix / "var/service"
    service_dir = service_root / SERVICE_ID
    for path in (prefix, prefix / "var", service_root, service_dir):
        try:
            info = path.lstat()
        except OSError as exc:
            raise DeploymentError("managed service directory is unavailable") from exc
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid() or info.st_mode & 0o022):
            raise DeploymentError("managed service directory identity is unsafe")
    return _safe_owned_file(target, executable=True)


def _config_identity(prefix: Path, home: Path, runner: Callable[..., subprocess.CompletedProcess[str]]) -> tuple[str, str]:
    config = home / ".config/ternuxx/sshd_recovery.conf"
    _safe_owned_file(config)
    if config.stat().st_mode & 0o077:
        raise DeploymentError("managed SSH configuration permissions are too broad")
    sshd = prefix / "bin/sshd"
    _safe_owned_file(sshd, executable=True, max_bytes=32 * 1024 * 1024)
    try:
        result = runner([str(sshd), "-t", "-f", str(config)], capture_output=True,
                        text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeploymentError("managed SSH configuration validation is unavailable") from exc
    if result.returncode != 0:
        raise DeploymentError("managed SSH configuration failed validation")
    return str(config), _sha(config.read_bytes())


def _backup_root(state_dir: str | os.PathLike[str], home: str | os.PathLike[str]) -> Path:
    # Reuse the operation journal's home-bound, symlink-free state path check.
    operation_journal._root(str(state_dir), home_dir=home)
    root = Path(state_dir).expanduser() / "service-deployments"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise DeploymentError("service deployment recovery directory is unsafe")
    return root


def _backup_path(state_dir: str | os.PathLike[str], home: str | os.PathLike[str], operation_id: str) -> Path:
    if not isinstance(operation_id, str) or not operation_id.isalnum() or len(operation_id) != 32:
        raise DeploymentError("invalid service deployment operation ID")
    return _backup_root(state_dir, home) / f"{operation_id}.json"


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".ternuxx-deploy.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _diff(old: bytes, new: bytes) -> list[str]:
    old_lines = old.decode("utf-8", errors="replace").splitlines(keepends=True)
    new_lines = new.decode("utf-8", errors="replace").splitlines(keepends=True)
    return list(difflib.unified_diff(old_lines, new_lines, fromfile="installed/run", tofile="source/run"))


def _plan_id(core: dict[str, object]) -> str:
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def preview(
    *, prefix: str | os.PathLike[str], home: str | os.PathLike[str],
    state_dir: str | os.PathLike[str], source: str | os.PathLike[str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, object]:
    prefix_path, target, source_path = _paths(prefix, source)
    source_info = _safe_owned_file(source_path, executable=True)
    target_info = _safe_target(prefix_path, target)
    try:
        syntax = runner(["bash", "-n", str(source_path)], capture_output=True, text=True,
                        timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeploymentError("source shell syntax validation is unavailable") from exc
    if syntax.returncode != 0:
        raise DeploymentError("source service definition failed shell syntax validation")
    config_path, config_hash = _config_identity(prefix_path, Path(home), runner)
    status = runit_service._status(prefix_path, runner=runner)
    installed = target.read_bytes()
    source_bytes = source_path.read_bytes()
    old_hash, new_hash = _sha(installed), _sha(source_bytes)
    diff = _diff(installed, source_bytes)
    core: dict[str, object] = {
        "service_id": SERVICE_ID, "target": str(target), "source": str(source_path),
        "installed_sha256": old_hash, "source_sha256": new_hash,
        "config_path": config_path, "config_sha256": config_hash,
        "service_status": status, "changed": old_hash != new_hash,
        "target_mode": stat.S_IMODE(target_info.st_mode),
        "source_mode": stat.S_IMODE(source_info.st_mode),
    }
    changed = old_hash != new_hash
    return {
        **core,
        "plan_id": _plan_id(core) if changed else None,
        "requires_confirmation": changed,
        "read_only": True,
        "diff": diff,
        "impact": ("Atomically replaces only the fixed Runit run definition. It does not stop or restart the running service, change SSH configuration, or alter external SSH configuration. The current process continues with its already-loaded definition; the replacement applies on a future supervisor start."),
    }


def apply(
    *, prefix: str | os.PathLike[str], home: str | os.PathLike[str],
    state_dir: str | os.PathLike[str], confirmed: bool, plan_id: str | None,
    source: str | os.PathLike[str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    writer: Callable[[Path, bytes, int], None] = _atomic_write,
) -> dict[str, object]:
    if type(confirmed) is not bool:
        raise DeploymentError("explicit confirmation is required")
    plan = preview(prefix=prefix, home=home, state_dir=state_dir, source=source, runner=runner)
    if not confirmed:
        return plan
    if not plan["requires_confirmation"] or not isinstance(plan_id, str) or plan_id != plan["plan_id"]:
        raise DeploymentError("deployment plan changed or the exact plan ID is missing")
    prefix_path, target, _source_path = _paths(prefix, source)
    target_info = _safe_target(prefix_path, target)
    original = target.read_bytes()
    desired = Path(str(plan["source"])).read_bytes()
    if _sha(original) != plan["installed_sha256"] or _sha(desired) != plan["source_sha256"]:
        raise DeploymentError("service definition changed after preview")
    before_status = str(plan["service_status"])
    backup_root = _backup_root(state_dir, home)
    operation_id = operation_journal.begin(
        str(state_dir), "service.deploy", f"deploy fixed {SERVICE_ID} run definition",
        home_dir=home,
    )
    backup_path = backup_root / f"{operation_id}.json"
    backup_record = {
        "schema_version": 1, "operation_id": operation_id,
        "service_id": SERVICE_ID, "target": f"var/service/{SERVICE_ID}/run",
        "original_sha256": _sha(original), "deployed_sha256": _sha(desired),
        "mode": stat.S_IMODE(target_info.st_mode),
        "original_b64": base64.b64encode(original).decode("ascii"),
    }
    try:
        _atomic_write(backup_path, (json.dumps(backup_record, sort_keys=True) + "\n").encode("utf-8"), 0o600)
    except OSError as exc:
        operation_journal.update(str(state_dir), operation_id, "failed", "recovery snapshot could not be saved", home_dir=home)
        raise DeploymentError("recovery snapshot could not be saved; service definition unchanged") from exc
    try:
        writer(target, desired, stat.S_IMODE(target_info.st_mode))
        if _sha(target.read_bytes()) != _sha(desired):
            raise DeploymentError("installed service definition did not verify")
        if runit_service._status(prefix_path, runner=runner) != before_status:
            raise DeploymentError("service status changed during definition deployment")
        operation_journal.update(str(state_dir), operation_id, "complete", f"definition deployed; rollback={operation_id}", home_dir=home)
        return {
            "service_id": SERVICE_ID, "status": "deployed", "operation_id": operation_id,
            "source_sha256": _sha(desired), "installed_sha256": _sha(target.read_bytes()),
            "service_status": before_status, "service_restarted": False,
            "rollback_available": True, "read_only": False,
        }
    except Exception as exc:
        try:
            writer(target, original, stat.S_IMODE(target_info.st_mode))
            restored = _sha(target.read_bytes()) == _sha(original)
        except Exception:
            restored = False
        state = "failed" if restored else "needs_recovery"
        detail = "deployment failed; prior definition restored" if restored else f"deployment failed; recovery snapshot={operation_id}"
        operation_journal.update(str(state_dir), operation_id, state, detail, home_dir=home)
        if not restored:
            raise DeploymentError(f"deployment failed and automatic rollback needs recovery; operation={operation_id}") from exc
        raise DeploymentError(f"deployment failed; automatic rollback restored the prior definition; operation={operation_id}") from exc


def preview_rollback(
    operation_id: str, *, prefix: str | os.PathLike[str], home: str | os.PathLike[str],
    state_dir: str | os.PathLike[str], runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    recovery_operation_id: str | None = None,
) -> dict[str, object]:
    record_path = _backup_path(state_dir, home, operation_id)
    try:
        metadata = record_path.lstat()
        if (stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_size > 2 * MAX_FILE_BYTES):
            raise DeploymentError("deployment recovery snapshot identity is unsafe")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        original = base64.b64decode(record["original_b64"], validate=True)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise DeploymentError("deployment recovery snapshot is unavailable or invalid") from exc
    if (record.get("operation_id") != operation_id or record.get("service_id") != SERVICE_ID
            or record.get("target") != f"var/service/{SERVICE_ID}/run"
            or _sha(original) != record.get("original_sha256")):
        raise DeploymentError("deployment recovery snapshot identity is invalid")
    prefix_path, target, _ = _paths(prefix, None)
    target_info = _safe_target(prefix_path, target)
    current = target.read_bytes()
    current_hash = _sha(current)
    journal = operation_journal.inspect_record(str(state_dir), operation_id, home_dir=home)
    if journal.get("kind") != "service.deploy":
        raise DeploymentError("recovery snapshot does not identify a service deployment")
    known_hashes = {record["deployed_sha256"], record["original_sha256"]}
    recovery_authorized = journal.get("status") == "needs_recovery"
    if recovery_operation_id is not None:
        recovery_record = operation_journal.inspect_record(str(state_dir), recovery_operation_id, home_dir=home)
        expected_detail = f"rollback of {operation_id} requires review"
        recovery_authorized = (recovery_record.get("kind") == "service.deploy.rollback"
                               and recovery_record.get("status") == "needs_recovery"
                               and recovery_record.get("detail") == expected_detail)
    if current_hash not in known_hashes and not recovery_authorized:
        raise DeploymentError("installed definition changed after deployment; refusing rollback")
    status = runit_service._status(prefix_path, runner=runner)
    core: dict[str, object] = {
        "operation_id": operation_id, "service_id": SERVICE_ID,
        "target": str(target), "current_sha256": current_hash,
        "restore_sha256": record["original_sha256"], "service_status": status,
        "target_mode": stat.S_IMODE(target_info.st_mode),
        "changed": current_hash != record["original_sha256"],
    }
    return {
        **core,
        "plan_id": _plan_id(core) if core["changed"] else None,
        "requires_confirmation": bool(core["changed"]), "read_only": True,
        "diff": _diff(current, original),
        "impact": "Atomically restores the exact pre-deployment run definition. It does not stop/restart the service or alter SSH configuration or external SSH configuration.",
    }


def apply_rollback(
    operation_id: str, *, prefix: str | os.PathLike[str], home: str | os.PathLike[str],
    state_dir: str | os.PathLike[str], confirmed: bool, plan_id: str | None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    writer: Callable[[Path, bytes, int], None] = _atomic_write,
    recovery_operation_id: str | None = None,
) -> dict[str, object]:
    if type(confirmed) is not bool:
        raise DeploymentError("explicit confirmation is required")
    plan = preview_rollback(operation_id, prefix=prefix, home=home, state_dir=state_dir,
                            runner=runner, recovery_operation_id=recovery_operation_id)
    if not confirmed:
        return plan
    if not plan["requires_confirmation"] or not isinstance(plan_id, str) or plan_id != plan["plan_id"]:
        raise DeploymentError("rollback plan changed or the exact plan ID is missing")
    record_path = _backup_path(state_dir, home, operation_id)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    original = base64.b64decode(record["original_b64"], validate=True)
    prefix_path, target, _ = _paths(prefix, None)
    current_info = _safe_target(prefix_path, target)
    current_hash = _sha(target.read_bytes())
    if current_hash != plan["current_sha256"]:
        raise DeploymentError("installed definition changed after rollback preview")
    deployment_journal = operation_journal.inspect_record(str(state_dir), operation_id, home_dir=home)
    recovering = deployment_journal.get("status") == "needs_recovery"
    if recovery_operation_id is not None:
        rollback_id = recovery_operation_id
    else:
        rollback_id = operation_id if recovering else operation_journal.begin(
            str(state_dir), "service.deploy.rollback", f"rollback service deployment {operation_id}",
            home_dir=home,
        )
    try:
        writer(target, original, stat.S_IMODE(current_info.st_mode))
        if _sha(target.read_bytes()) != record["original_sha256"]:
            raise DeploymentError("restored service definition did not verify")
        operation_journal.update(str(state_dir), rollback_id, "complete", f"restored deployment={operation_id}", home_dir=home)
        return {"status": "rolled_back", "operation_id": rollback_id,
                "deployment_id": operation_id, "installed_sha256": _sha(target.read_bytes()),
                "service_restarted": False, "rollback_available": False, "read_only": False}
    except Exception as exc:
        try:
            operation_journal.update(str(state_dir), rollback_id, "needs_recovery", f"rollback of {operation_id} requires review", home_dir=home)
        except Exception:
            pass
        raise DeploymentError(f"rollback did not verify; recovery snapshot={operation_id}") from exc
