#!/usr/bin/env python3
"""Native-only reboot-test evidence store; it never starts services or resumes tasks."""

from __future__ import annotations

import hashlib
import argparse
from datetime import datetime, timezone
import fcntl
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time
import uuid

import continuity
import ssh_diagnostics


TEST_ID_RE = continuity.TEST_ID_RE
OBSERVER_READINESS_MAX_ATTEMPTS = 20
OBSERVER_READINESS_POLL_SECONDS = 1.0
AUTH_MODES = {"publickey", "password", "keyboard-interactive", "unknown"}
CHECKS = {
    "boot_id_changed", "termux_boot_observed", "native_sshd_ready",
    "ssh_socket_observed", "continuity_marker_matches",
    "db_preserved", "xgo_preserved", "wakelock_owner_checked",
}
# Preserve readability of pre-Native-only checkpoint evidence without making it
# a valid check for newly prepared Native reboot records.
HISTORICAL_CHECKS = {"proot_independent"}
STATES = {"prepared", "awaiting_reboot", "boot_observed", "verified", "failed", "inconclusive"}
ENUMS = {
    "sshd_process": {"present", "absent", "unknown"},
    "config_syntax": {"valid", "invalid", "unknown"},
    "socket_binding": {"verified_loopback", "verified_other", "unverified", "not_observed"},
    "boot_policy": {"enabled", "disabled", "not_configured", "unknown"},
    "boot_app": {"installed", "not_installed", "unknown"},
    "boot_directory": {"present", "absent", "unknown"},
    "wake_lock_ownership": {"scoped", "global_unscoped", "unknown"},
    "managed_service_status": {"running", "stopped", "unknown"},
    "managed_service_definition": {"verified", "mismatch", "unavailable", "unsafe", "unknown"},
    "managed_config_syntax": {"valid", "invalid_or_unavailable", "unknown"},
    "managed_loopback_probe": {"ssh_banner", "failed", "unknown"},
    "listener_daemon_correlation": {"verified", "not_verified", "unknown", "not_performed"},
}


class RecoveryError(Exception):
    """Safe-to-report validation or persistence failure."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _root(home: str | os.PathLike[str], state_dir: str | os.PathLike[str]) -> Path:
    return continuity._private_root(home, state_dir) / "continuity" / "reboot-tests"


def _plan_id(action: str, details: dict[str, object], private_identity: str) -> str:
    payload = {"action": action, "details": details, "private_identity": private_identity}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _normalized_boot_id(boot_id: str | None) -> str | None:
    if boot_id is None:
        boot_id = continuity.read_boot_id()
    if boot_id is not None:
        try:
            return str(uuid.UUID(boot_id))
        except (ValueError, TypeError) as exc:
            raise RecoveryError("boot ID is malformed") from exc
    return None


def prepare_preview(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
                    test_id: str, evidence: dict[str, object], boot_id: str | None = None) -> dict[str, object]:
    """Validate reboot-test input and return a stable, non-writing preview."""
    if not isinstance(test_id, str) or not TEST_ID_RE.fullmatch(test_id):
        raise RecoveryError("test ID is invalid")
    baseline = _check_evidence(evidence)
    current_boot_id = _normalized_boot_id(boot_id)
    root = _root(home, state_dir)
    target = root / f"{test_id}.json"
    if target.exists() or target.is_symlink():
        raise RecoveryError("reboot-test ID already exists; choose a new unique ID")
    baseline_digest = hashlib.sha256(
        json.dumps(baseline, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    details: dict[str, object] = {
        "test_id": test_id,
        "baseline_sha256": baseline_digest,
        "record_path": str(target),
        "readiness": "NOT_READY",
        "automatic_resume": False,
    }
    return {
        "plan_id": _plan_id("prepare_reboot_test", details, current_boot_id or "boot-id-unavailable"),
        "action": "create_private_reboot_test_record",
        "details": details,
        "read_only": True,
        "warning": "Writes a private NOT_READY record only; it does not reboot or resume work.",
    }


def verify_preview(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
                   test_id: str, current_boot_id: str | None = None) -> dict[str, object]:
    """Validate a reboot-test record and preview its evidence-only verification."""
    if not isinstance(test_id, str) or not TEST_ID_RE.fullmatch(test_id):
        raise RecoveryError("test ID is invalid")
    root = _root(home, state_dir)
    record = _read_record(root / f"{test_id}.json")
    current_boot_id = _normalized_boot_id(current_boot_id)
    previous_boot_id = record.get("previous_boot_id")
    if previous_boot_id is None or current_boot_id is None:
        transition = "unknown"
    else:
        transition = "changed" if previous_boot_id != current_boot_id else "same"
    observations = record.get("boot_observations")
    latest = observations[-1] if isinstance(observations, list) and observations else None
    observation_matches = isinstance(latest, dict) and latest.get("current_boot_id") == current_boot_id
    if transition == "changed" and observation_matches and latest.get("termux_boot_invoked") is True:
        outcome = "verified_reboot_partial" if latest.get("sshd_process") != "present" else "verified_reboot_service_unqualified"
    elif transition == "same":
        outcome = "same_boot"
    else:
        outcome = "inconclusive"
    record_digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    details: dict[str, object] = {
        "test_id": test_id,
        "record_sha256": record_digest,
        "state": record["state"],
        "boot_id_transition": transition,
        "boot_observation_matches": observation_matches,
        "expected_outcome": outcome,
        "automatic_resume": False,
    }
    return {
        "plan_id": _plan_id("verify_reboot_test", details, current_boot_id or "boot-id-unavailable"),
        "action": "record_reboot_test_verification",
        "details": details,
        "read_only": True,
        "warning": "Writes verification evidence only; it does not reboot or resume work.",
    }


def _check_evidence(evidence: object, *, allow_historical: bool = False) -> dict[str, object]:
    if not isinstance(evidence, dict) or set(evidence) != {
        "native", "repository", "stage", "references", "ssh", "termux_boot",
        "wake_lock", "required_postboot_checks", "recovery_instructions", "rollback_instructions", "next_action",
    }:
        raise RecoveryError("baseline evidence fields do not match the reboot-test schema")
    native = evidence["native"]
    repository = evidence["repository"]
    ssh = evidence["ssh"]
    boot = evidence["termux_boot"]
    wake = evidence["wake_lock"]
    if not isinstance(native, dict) or set(native) != {"termux_version"} or not isinstance(native["termux_version"], str):
        raise RecoveryError("native environment metadata is invalid")
    if not isinstance(repository, dict) or set(repository) != {"id", "branch", "commit", "modified_paths", "untracked_paths"}:
        raise RecoveryError("repository evidence is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}/[A-Za-z0-9_.-]{1,128}", str(repository["id"])):
        raise RecoveryError("repository identity is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(repository["branch"])):
        raise RecoveryError("repository branch is invalid")
    if not continuity.COMMIT_RE.fullmatch(str(repository["commit"])):
        raise RecoveryError("repository commit is invalid")
    if any(type(repository[key]) is not int or repository[key] < 0 for key in ("modified_paths", "untracked_paths")):
        raise RecoveryError("repository path counts are invalid")
    if not isinstance(evidence["stage"], str) or not evidence["stage"] or len(evidence["stage"]) > 160:
        raise RecoveryError("verified stage label is invalid")
    references = evidence["references"]
    if not isinstance(references, list) or len(references) > 64 or any(
        not isinstance(item, str) or not item or item.startswith("/") or ".." in Path(item).parts or len(item) > 240
        for item in references
    ):
        raise RecoveryError("source references must be bounded repository-relative paths")
    if not isinstance(ssh, dict) or set(ssh) != {"sshd_process", "auth_modes", "config_syntax", "socket_binding", "boot_policy"}:
        raise RecoveryError("SSH state metadata is invalid")
    if any(ssh[field] not in ENUMS[field] for field in ("sshd_process", "config_syntax", "socket_binding", "boot_policy")):
        raise RecoveryError("SSH state contains an unsupported value")
    if not isinstance(ssh["auth_modes"], list) or any(item not in AUTH_MODES for item in ssh["auth_modes"]):
        raise RecoveryError("SSH authentication metadata is invalid")
    if not isinstance(boot, dict) or set(boot) != {"app", "script_directory", "startup_policy"}:
        raise RecoveryError("Termux:Boot metadata is invalid")
    if boot["app"] not in ENUMS["boot_app"] or boot["script_directory"] not in ENUMS["boot_directory"] or boot["startup_policy"] not in ENUMS["boot_policy"]:
        raise RecoveryError("Termux:Boot metadata contains an unsupported value")
    if not isinstance(wake, dict) or set(wake) != {"cli_available", "launcher_acquire_request", "launcher_global_release_request", "ownership"}:
        raise RecoveryError("Wake Lock metadata is invalid")
    if any(type(wake[key]) is not bool for key in ("cli_available", "launcher_acquire_request", "launcher_global_release_request")) or wake["ownership"] not in ENUMS["wake_lock_ownership"]:
        raise RecoveryError("Wake Lock evidence contains an unsupported value")
    required = evidence["required_postboot_checks"]
    accepted_checks = CHECKS | (HISTORICAL_CHECKS if allow_historical else set())
    if not isinstance(required, list) or len(required) > 32 or any(item not in accepted_checks for item in required) or len(set(required)) != len(required):
        raise RecoveryError("post-boot check list is invalid")
    instructions = evidence["recovery_instructions"]
    if not isinstance(instructions, list) or not 1 <= len(instructions) <= 24 or any(not isinstance(i, str) or not i or len(i) > 500 for i in instructions):
        raise RecoveryError("recovery instructions are invalid")
    rollback = evidence["rollback_instructions"]
    if not isinstance(rollback, list) or not 1 <= len(rollback) <= 24 or any(not isinstance(i, str) or not i or len(i) > 500 for i in rollback):
        raise RecoveryError("rollback instructions are invalid")
    if not isinstance(evidence["next_action"], str) or not evidence["next_action"] or len(evidence["next_action"]) > 160:
        raise RecoveryError("next action is invalid")
    return evidence


def _read_record(path: Path) -> dict[str, object]:
    try:
        if path.is_symlink() or stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) & 0o077 or path.stat().st_size > 256 * 1024:
            raise RecoveryError("reboot-test checkpoint is not private or exceeds its size limit")
        value = json.loads(path.read_text(encoding="utf-8"))
    except RecoveryError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise RecoveryError("reboot-test checkpoint is unavailable or invalid") from exc
    required = {"schema_version", "test_id", "nonce", "state", "readiness", "prepared_at", "previous_boot_id", "baseline", "boot_observations", "verification_history", "automatic_resume"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema_version") != 1:
        raise RecoveryError("reboot-test checkpoint schema is unsupported")
    if not isinstance(value.get("test_id"), str) or not TEST_ID_RE.fullmatch(value["test_id"]) or path.stem != value["test_id"]:
        raise RecoveryError("reboot-test identity is invalid")
    if not isinstance(value.get("nonce"), str) or not 32 <= len(value["nonce"]) <= 128:
        raise RecoveryError("reboot-test nonce is invalid")
    if value.get("state") not in STATES:
        raise RecoveryError("reboot-test checkpoint state is invalid")
    if value.get("readiness") not in {"READY", "NOT_READY"} or value.get("automatic_resume") is not False:
        raise RecoveryError("reboot-test policy is invalid")
    if not isinstance(value.get("boot_observations"), list) or len(value["boot_observations"]) > 64:
        raise RecoveryError("boot observation history is invalid")
    if not isinstance(value.get("verification_history"), list) or len(value["verification_history"]) > 64:
        raise RecoveryError("verification history is invalid")
    observation_fields = {
        "managed_service_status": "managed_service_status",
        "managed_service_definition": "managed_service_definition",
        "managed_config_syntax": "managed_config_syntax",
        "managed_loopback_probe": "managed_loopback_probe",
        "listener_daemon_correlation": "listener_daemon_correlation",
    }
    for observation in value["boot_observations"]:
        if not isinstance(observation, dict):
            raise RecoveryError("boot observation is invalid")
        for field, enum_name in observation_fields.items():
            if field in observation and (not isinstance(observation[field], str) or observation[field] not in ENUMS[enum_name]):
                raise RecoveryError("boot observation contains unsupported managed-service evidence")
    _check_evidence(value.get("baseline"), allow_historical=True)
    return value


def prepare(
    *, home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
    test_id: str, evidence: dict[str, object],
    boot_id: str | None = None,
) -> dict[str, object]:
    if not TEST_ID_RE.fullmatch(test_id):
        raise RecoveryError("test ID is invalid")
    baseline = _check_evidence(evidence)
    if boot_id is None:
        boot_id = continuity.read_boot_id()
    if boot_id is not None:
        try:
            boot_id = str(uuid.UUID(boot_id))
        except ValueError as exc:
            raise RecoveryError("boot ID is malformed") from exc
    root = _root(home, state_dir)
    continuity._ensure_private_dir(root)
    path = root / f"{test_id}.json"
    record = {
        "schema_version": 1,
        "test_id": test_id,
        "nonce": secrets.token_urlsafe(32),
        "state": "prepared",
        "readiness": "NOT_READY",
        "prepared_at": _now(),
        "previous_boot_id": boot_id,
        "baseline": baseline,
        "boot_observations": [],
        "verification_history": [],
        "automatic_resume": False,
    }
    try:
        continuity._atomic_write(path, record, exclusive=True)
    except continuity.CheckpointError as exc:
        raise RecoveryError(str(exc)) from exc
    return {"test_id": test_id, "nonce": record["nonce"], "state": record["state"], "readiness": "NOT_READY"}


def status(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str], test_id: str | None = None) -> dict[str, object]:
    if test_id is not None and not TEST_ID_RE.fullmatch(test_id):
        raise RecoveryError("test ID is invalid")
    root = _root(home, state_dir)
    if not root.exists():
        return {"pending_tests": [], "state": "none"}
    paths = [root / f"{test_id}.json"] if test_id else sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    records = []
    for path in paths[:16]:
        record = _read_record(path)
        records.append({"test_id": record["test_id"], "state": record["state"], "readiness": record["readiness"],
                        "prepared_at": record["prepared_at"], "previous_boot_id": record["previous_boot_id"],
                        "automatic_resume": False})
    return {"pending_tests": records, "state": records[0]["state"] if records else "none"}


def record_boot_observation(
    *, home: str | os.PathLike[str], state_dir: str | os.PathLike[str], test_id: str,
    nonce: str, termux_version: str, sshd_process: str, config_syntax: str,
    termux_boot_invoked: bool = True, current_boot_id: str | None = None,
    managed_service_status: str = "unknown", managed_service_definition: str = "unknown",
    managed_config_syntax: str = "unknown", managed_loopback_probe: str = "unknown",
    listener_daemon_correlation: str = "unknown",
) -> dict[str, object]:
    if not TEST_ID_RE.fullmatch(test_id) or not isinstance(nonce, str) or not 32 <= len(nonce) <= 128:
        raise RecoveryError("test identity is invalid")
    if sshd_process not in ENUMS["sshd_process"] or config_syntax not in ENUMS["config_syntax"]:
        raise RecoveryError("boot service evidence is invalid")
    managed_values = {
        "managed_service_status": managed_service_status,
        "managed_service_definition": managed_service_definition,
        "managed_config_syntax": managed_config_syntax,
        "managed_loopback_probe": managed_loopback_probe,
        "listener_daemon_correlation": listener_daemon_correlation,
    }
    if any(not isinstance(value, str) or value not in ENUMS[field] for field, value in managed_values.items()):
        raise RecoveryError("managed service evidence is invalid")
    root = _root(home, state_dir)
    record_path = root / f"{test_id}.json"
    record = _read_record(record_path)
    if not hmac.compare_digest(str(record.get("nonce", "")), nonce):
        raise RecoveryError("test nonce does not match the pending checkpoint")
    if current_boot_id is None:
        current_boot_id = continuity.read_boot_id()
    if current_boot_id is not None:
        try:
            current_boot_id = str(uuid.UUID(current_boot_id))
        except ValueError as exc:
            raise RecoveryError("current boot ID is malformed") from exc
    previous = record.get("previous_boot_id")
    transition = "unknown" if previous is None or current_boot_id is None else "changed" if previous != current_boot_id else "same"
    errors = []
    if transition == "unknown":
        errors.append("boot_id_unavailable")
    if not termux_boot_invoked:
        errors.append("termux_boot_invocation_not_proven")
    if sshd_process == "absent":
        errors.append("sshd_process_absent")
    if config_syntax != "valid":
        errors.append("sshd_config_not_validated")
    managed_ready = (managed_service_status == "running" and managed_service_definition == "verified"
                     and managed_config_syntax == "valid" and managed_loopback_probe == "ssh_banner")
    managed_bad = (managed_service_status == "stopped" or managed_service_definition in {"mismatch", "unsafe"}
                   or managed_config_syntax == "invalid_or_unavailable" or managed_loopback_probe == "failed")
    health = "ready_unqualified" if managed_ready else "degraded" if managed_bad else "unknown"
    if health == "degraded":
        errors.append("managed_service_not_ready")
    elif health == "unknown":
        errors.append("managed_service_health_unverified")
    observations = record.get("boot_observations", [])
    if current_boot_id is not None and isinstance(observations, list):
        for existing in observations:
            if isinstance(existing, dict) and existing.get("current_boot_id") == current_boot_id and existing.get("termux_boot_invoked") is termux_boot_invoked:
                return {"test_id": test_id, "state": record["state"], "boot_id_transition": existing.get("boot_id_transition"),
                        "sshd_process": existing.get("sshd_process"), "automatic_resume": False, "duplicate_observation": True}
    observation = {
        "observed_at": _now(), "current_boot_id": current_boot_id, "boot_id_transition": transition,
        "genuine_android_reboot": True if transition == "changed" else False if transition == "same" else None,
        "termux_version": termux_version[:80], "termux_boot_invoked": bool(termux_boot_invoked),
        "sshd_process": sshd_process, "config_syntax": config_syntax, "native_service_health": health,
        **managed_values,
        "sshd_authenticated_connectivity": "not_tested", "errors": errors,
        "socket_binding": "not_observed", "wakelock_state": "unknown",
        "automatic_resume": False,
    }
    record["boot_observations"].append(observation)
    record["state"] = "boot_observed" if transition == "changed" else "inconclusive"
    try:
        continuity._atomic_write(record_path, record, exclusive=False)
    except continuity.CheckpointError as exc:
        raise RecoveryError(str(exc)) from exc
    return {"test_id": test_id, "state": record["state"], "boot_id_transition": transition,
            "sshd_process": sshd_process, "automatic_resume": False}


def verify(
    *, home: str | os.PathLike[str], state_dir: str | os.PathLike[str], test_id: str,
    nonce: str, current_boot_id: str | None = None, expected_record_sha256: str | None = None,
) -> dict[str, object]:
    if not TEST_ID_RE.fullmatch(test_id):
        raise RecoveryError("test ID is invalid")
    if current_boot_id is None:
        current_boot_id = continuity.read_boot_id()
    if current_boot_id is not None:
        try:
            current_boot_id = str(uuid.UUID(current_boot_id))
        except ValueError as exc:
            raise RecoveryError("current boot ID is malformed") from exc
    root = _root(home, state_dir)
    record_path = root / f"{test_id}.json"
    record = _read_record(record_path)
    if expected_record_sha256 is not None:
        record_digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if not hmac.compare_digest(record_digest, expected_record_sha256):
            raise RecoveryError("reboot-test record changed after preview; preview it again")
    if not isinstance(nonce, str) or not hmac.compare_digest(str(record.get("nonce", "")), nonce):
        raise RecoveryError("test nonce does not match the pending checkpoint")
    previous = record.get("previous_boot_id")
    observations = record.get("boot_observations")
    latest = observations[-1] if isinstance(observations, list) and observations else None
    if previous is None or current_boot_id is None:
        transition = "unknown"
    else:
        transition = "changed" if previous != current_boot_id else "same"
    matching_observation = isinstance(latest, dict) and latest.get("current_boot_id") == current_boot_id
    if transition == "changed" and matching_observation and latest.get("termux_boot_invoked") is True:
        outcome = "verified_reboot_partial" if latest.get("sshd_process") != "present" else "verified_reboot_service_unqualified"
    elif transition == "same":
        outcome = "same_boot"
    else:
        outcome = "inconclusive"
    result = {
        "verified_at": _now(), "outcome": outcome, "previous_boot_id": previous,
        "current_boot_id": current_boot_id, "boot_observation_matches": matching_observation,
        "sshd_process": latest.get("sshd_process") if isinstance(latest, dict) else "unknown",
        "native_service_health": latest.get("native_service_health") if isinstance(latest, dict) else "unknown",
        "sshd_authenticated_connectivity": latest.get("sshd_authenticated_connectivity") if isinstance(latest, dict) else "not_tested",
        "errors": latest.get("errors", []) if isinstance(latest, dict) else ["boot_observation_missing"],
        "socket_binding": "not_observed", "test_id": test_id,
        "automatic_resume": False,
    }
    record["verification_history"].append(result)
    record["state"] = "boot_observed" if outcome.startswith("verified_reboot") else "inconclusive" if outcome == "inconclusive" else "prepared"
    try:
        continuity._atomic_write(record_path, record, exclusive=False)
    except continuity.CheckpointError as exc:
        raise RecoveryError(str(exc)) from exc
    return result


def verify_pending(
    *, home: str | os.PathLike[str], state_dir: str | os.PathLike[str], test_id: str,
    current_boot_id: str | None = None, expected_record_sha256: str | None = None,
) -> dict[str, object]:
    """Verify a private checkpoint without exposing its nonce in process arguments."""
    if not TEST_ID_RE.fullmatch(test_id):
        raise RecoveryError("test ID is invalid")
    record = _read_record(_root(home, state_dir) / f"{test_id}.json")
    return verify(home=home, state_dir=state_dir, test_id=test_id,
                  nonce=str(record["nonce"]), current_boot_id=current_boot_id,
                  expected_record_sha256=expected_record_sha256)


def resume_info(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str], test_id: str) -> dict[str, object]:
    if not TEST_ID_RE.fullmatch(test_id):
        raise RecoveryError("test ID is invalid")
    root = _root(home, state_dir)
    record = _read_record(root / f"{test_id}.json")
    state = record["state"]
    next_action = str(record["baseline"]["next_action"])
    if state == "boot_observed":
        history = record.get("verification_history", [])
        latest = history[-1] if isinstance(history, list) and history else None
        if isinstance(latest, dict):
            outcome = latest.get("outcome", "unknown")
            next_action = (
                f"Review reboot verification outcome {outcome}; manually verify required service and "
                "connection evidence before continuing. Tasks will not resume automatically."
            )
        else:
            next_action = (
                "Review the recorded boot observation with `tx reboot verify`; "
                "tasks will not resume automatically."
            )
    elif state == "inconclusive":
        next_action = (
            "Review the inconclusive reboot observation and its evidence before preparing another "
            "owner-authorized test. Tasks will not resume automatically."
        )
    return {"test_id": test_id, "state": record["state"], "readiness": record["readiness"],
            "next_action": next_action, "automatic_resume": False}


def _managed_service_ready_for_observation(report: dict[str, object]) -> bool:
    checks = report.get("checks", {})
    if not isinstance(checks, dict):
        return False
    managed = checks.get("managed_service", {})
    if not isinstance(managed, dict):
        return False
    identity = managed.get("definition_identity", {})
    identity_status = identity.get("status") if isinstance(identity, dict) else None
    probe = managed.get("loopback_ssh_probe", {})
    probe_status = probe.get("status") if isinstance(probe, dict) else None
    return (managed.get("status") == "running" and identity_status == "verified"
            and managed.get("config_syntax") == "valid"
            and probe_status == "ssh_banner")


def _managed_service_failure_is_terminal(report: dict[str, object]) -> bool:
    checks = report.get("checks", {})
    if not isinstance(checks, dict):
        return True
    managed = checks.get("managed_service")
    if not isinstance(managed, dict) or not managed:
        return True
    identity = managed.get("definition_identity", {})
    identity_status = identity.get("status") if isinstance(identity, dict) else None
    if identity_status is None:
        return True
    return (identity_status in {"mismatch", "unsafe", "unavailable"}
            or managed.get("config_syntax") in {"invalid", "unavailable"})


def _observe_latest_pending_unlocked(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str], prefix: str,
                                     termux_version: str, dry_run: bool) -> dict[str, object]:
    root = _root(home, state_dir)
    if not root.is_dir():
        return {"state": "no_pending_test", "automatic_resume": False}
    candidates = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in candidates:
        record = _read_record(path)
        if record["state"] not in {"prepared", "awaiting_reboot", "boot_observed", "inconclusive"}:
            continue
        report = ssh_diagnostics.inspect_native(prefix=prefix, home=home)
        if not dry_run:
            for _ in range(OBSERVER_READINESS_MAX_ATTEMPTS - 1):
                if (_managed_service_ready_for_observation(report)
                        or _managed_service_failure_is_terminal(report)):
                    break
                time.sleep(OBSERVER_READINESS_POLL_SECONDS)
                report = ssh_diagnostics.inspect_native(prefix=prefix, home=home)
        checks = report.get("checks", {})
        process = checks.get("daemon_process_present") if isinstance(checks, dict) else None
        sshd_process = "present" if process is True else "absent" if process is False else "unknown"
        syntax = checks.get("config_syntax") if isinstance(checks, dict) else "unknown"
        config_syntax = "valid" if syntax == "valid" else "invalid" if syntax == "invalid" else "unknown"
        managed = checks.get("managed_service", {}) if isinstance(checks, dict) else {}
        managed = managed if isinstance(managed, dict) else {}
        service_status = managed.get("status")
        managed_service_status = service_status if isinstance(service_status, str) and service_status in {"running", "stopped"} else "unknown"
        identity = managed.get("definition_identity", {})
        identity_status = identity.get("status") if isinstance(identity, dict) else None
        managed_service_definition = identity_status if isinstance(identity_status, str) and identity_status in {"verified", "mismatch", "unavailable", "unsafe"} else "unknown"
        managed_syntax = managed.get("config_syntax")
        managed_config_syntax = "valid" if managed_syntax == "valid" else "invalid_or_unavailable" if isinstance(managed_syntax, str) and managed_syntax in {"invalid", "unavailable"} else "unknown"
        probe = managed.get("loopback_ssh_probe", {})
        probe_status = probe.get("status") if isinstance(probe, dict) else None
        managed_loopback_probe = "ssh_banner" if probe_status == "ssh_banner" else "failed" if isinstance(probe_status, str) and probe_status in {"failed", "connection_refused", "unreachable", "wrong_banner"} else "unknown"
        correlation = checks.get("listener_daemon_correlation") if isinstance(checks, dict) else None
        listener_daemon_correlation = correlation if isinstance(correlation, str) and correlation in {"verified", "not_verified", "unknown"} else "unknown"
        if dry_run:
            previous = record.get("previous_boot_id")
            current = continuity.read_boot_id()
            transition = "unknown" if previous is None or current is None else "changed" if previous != current else "same"
            return {"test_id": record["test_id"], "state": "dry_run", "boot_id_transition": transition,
                    "sshd_process": sshd_process, "config_syntax": config_syntax,
                    "managed_service_status": managed_service_status,
                    "managed_service_definition": managed_service_definition,
                    "managed_config_syntax": managed_config_syntax,
                    "managed_loopback_probe": managed_loopback_probe,
                    "listener_daemon_correlation": listener_daemon_correlation,
                    "termux_boot_invoked": False, "state_written": False, "automatic_resume": False}
        return record_boot_observation(
            home=home, state_dir=state_dir, test_id=str(record["test_id"]), nonce=str(record["nonce"]),
            termux_version=termux_version, sshd_process=sshd_process, config_syntax=config_syntax,
            managed_service_status=managed_service_status,
            managed_service_definition=managed_service_definition,
            managed_config_syntax=managed_config_syntax,
            managed_loopback_probe=managed_loopback_probe,
            listener_daemon_correlation=listener_daemon_correlation,
            termux_boot_invoked=True,
        )
    return {"state": "no_pending_test", "automatic_resume": False}


def observe_latest_pending(*, home: str | os.PathLike[str], state_dir: str | os.PathLike[str], prefix: str,
                          termux_version: str, dry_run: bool = False) -> dict[str, object]:
    root = _root(home, state_dir)
    if not root.is_dir():
        return {"state": "no_pending_test", "automatic_resume": False}
    lock_path = root / ".boot-observer.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "observer_already_running", "automatic_resume": False}
        return _observe_latest_pending_unlocked(home=home, state_dir=state_dir, prefix=prefix,
                                                termux_version=termux_version, dry_run=dry_run)
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tx reboot-recovery")
    parser.add_argument("--home", default=os.environ.get("HOME", ""), help=argparse.SUPPRESS)
    parser.add_argument("--state-dir", default=os.environ.get("TERNUXX_STATE_DIR", ""), help=argparse.SUPPRESS)
    parser.add_argument("command", choices=("status", "boot-observe"))
    parser.add_argument("--test-id")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if os.environ.get("TERMUX_VERSION") is None or os.environ.get("PREFIX") != "/data/data/com.termux/files/usr":
        print("reboot recovery operations require native Termux", file=sys.stderr)
        return 2
    if not args.home or not args.state_dir:
        print("HOME and Ternuxx state directory must be configured", file=sys.stderr)
        return 2
    try:
        if args.command == "status":
            result = status(home=args.home, state_dir=args.state_dir, test_id=args.test_id)
        else:
            result = observe_latest_pending(home=args.home, state_dir=args.state_dir,
                                            prefix=os.environ["PREFIX"], termux_version=os.environ["TERMUX_VERSION"],
                                            dry_run=args.dry_run)
    except (RecoveryError, continuity.CheckpointError, OSError) as exc:
        print(json.dumps({"error": {"code": "recovery_error", "message": str(exc)}}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
