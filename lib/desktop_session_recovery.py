#!/usr/bin/env python3
"""Preview-first reconciliation for interrupted native desktop journal entries."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

import operation_journal
import native_desktops


class DesktopRecoveryError(RuntimeError):
    """A desktop session cannot be safely reconciled from its recorded state."""


_MARKERS = {"supervisor": "desktop-supervisor.sh", "x11": "termux-x11", "desktop": "xfce4-session"}


def _process_state(role: str, value: object, *, proc_root: Path, expected_desktop: str = "xfce4-session") -> str:
    if not isinstance(value, dict):
        raise DesktopRecoveryError(f"Recorded {role} process identity is invalid")
    pid = value.get("pid")
    if pid is None and role in {"x11", "desktop"}:
        return "absent"
    ticks = value.get("start_ticks")
    marker = value.get("command_marker")
    if (type(pid) is not int or pid < 1 or not isinstance(ticks, str) or not re.fullmatch(r"[0-9]+", ticks)
            or marker != (expected_desktop if role == "desktop" else _MARKERS[role])):
        raise DesktopRecoveryError(f"Recorded {role} process identity is incomplete or unexpected")
    if role != "supervisor" and (type(value.get("pgid")) is not int or type(value.get("sid")) is not int
            or value["pgid"] != pid or value["sid"] != pid):
        raise DesktopRecoveryError(f"Recorded {role} process group/session identity is unsafe")
    try:
        raw_stat = (proc_root / str(pid) / "stat").read_text(encoding="ascii")
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        raise DesktopRecoveryError(f"Cannot verify recorded {role} process identity") from exc
    _comm, separator, tail = raw_stat.rpartition(")")
    fields = tail.strip().split() if separator else []
    if len(fields) < 20:
        raise DesktopRecoveryError(f"Recorded {role} process stat is malformed")
    try:
        cmdline = (proc_root / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError as exc:
        raise DesktopRecoveryError(f"Cannot verify recorded {role} command line") from exc
    # /proc stat field 22 is index 19 after removing fields 1 and 2.
    actual_ticks = fields[19]
    actual_pgid, actual_sid = fields[2], fields[3]
    if actual_ticks != ticks or marker not in cmdline:
        return "absent"
    if value.get("pgid") is not None and str(value.get("pgid")) != actual_pgid:
        return "absent"
    if value.get("sid") is not None and str(value.get("sid")) != actual_sid:
        return "absent"
    return "live"


def _snapshot(operation_id: str, *, home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
              proc_root: Path = Path("/proc")) -> dict[str, object]:
    if not isinstance(operation_id, str) or not re.fullmatch(r"[a-f0-9]{32}", operation_id):
        raise DesktopRecoveryError("Operation ID is invalid")
    try:
        record = operation_journal.inspect_record(str(state_dir), operation_id, home_dir=home)
        root = Path(home).expanduser().resolve(strict=True)
        state_root = Path(state_dir).expanduser()
        resolved_state_root = state_root.resolve(strict=True)
        resolved_state_root.relative_to(root)
    except (OSError, ValueError, RuntimeError) as exc:
        raise DesktopRecoveryError("Operation or state path is unavailable or unsafe") from exc
    kind, status = record.get("kind"), record.get("status")
    initial = "starting" if kind == "desktop.start" else "stopping"
    if kind not in {"desktop.start", "desktop.stop"} or status not in {initial, "needs_recovery"}:
        raise DesktopRecoveryError("Only an interrupted desktop start/stop can be resolved")
    requested_display = None
    if kind == "desktop.start":
        detail = record.get("detail")
        match = re.fullmatch(r"display (:[0-9]{1,2})", detail) if isinstance(detail, str) else None
        if not match:
            raise DesktopRecoveryError("Interrupted desktop start does not contain a valid display intent")
        requested_display = match.group(1)
    try:
        root_metadata = state_root.lstat()
    except OSError as exc:
        raise DesktopRecoveryError("Desktop state directory cannot be inspected") from exc
    if (stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode)
            or root_metadata.st_uid != os.getuid() or stat.S_IMODE(root_metadata.st_mode) != 0o700):
        raise DesktopRecoveryError("Desktop state directory ownership or mode is unsafe")
    try:
        if not proc_root.is_dir():
            raise DesktopRecoveryError("Process inventory is unavailable")
    except OSError as exc:
        raise DesktopRecoveryError("Process inventory is unavailable") from exc
    lock = state_root / ".session.lock"
    if lock.exists() or lock.is_symlink():
        raise DesktopRecoveryError("A desktop lifecycle lock exists; wait for the operation or review the lock manually")

    session_path = state_root / "session.json"
    try:
        metadata = session_path.lstat()
    except FileNotFoundError:
        session = None
        session_bytes = b""
    except OSError as exc:
        raise DesktopRecoveryError("Session record cannot be inspected") from exc
    else:
        if (stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise DesktopRecoveryError("Session record ownership or mode is unsafe")
        try:
            session_bytes = session_path.read_bytes()
            session = json.loads(session_bytes)
        except (OSError, ValueError) as exc:
            raise DesktopRecoveryError("Session record is unreadable or invalid JSON") from exc
        if (not isinstance(session, dict) or session.get("schema") != 2
                or session.get("owner") != "ternuxx" or session.get("provider") != "native"
                or session.get("status") not in {"running", "starting", "failed", "stopped", "stop_incomplete"}
                or not isinstance(session.get("display"), str)
                or not re.fullmatch(r":[0-9]{1,2}", session["display"])):
            raise DesktopRecoveryError("Session record is not a recognized Ternuxx native session")
        if kind == "desktop.start" and session["display"] != requested_display:
            raise DesktopRecoveryError("Recorded session display does not match the interrupted start intent")

    if session is None:
        states = {role: "absent" for role in _MARKERS}
        observed = "absent"
    else:
        desktop_id = session.get("desktop_id", "xfce")
        native_item = native_desktops.NATIVE_DESKTOPS.get(desktop_id)
        expected_desktop = (native_item["command"] if native_item else None) if session.get("provider", "native") == "native" else ("proot-display0" if session.get("provider") == "proot" else None)
        if not expected_desktop:
            raise DesktopRecoveryError("Recorded desktop provider or environment is not supported")
        states = {role: _process_state(role, session.get(role), proc_root=proc_root, expected_desktop=expected_desktop) for role in _MARKERS}
        observed = str(session["status"])

    if kind == "desktop.start":
        if observed == "running" and all(states[role] == "live" for role in _MARKERS):
            resolution = "complete"
        elif observed in {"absent", "failed", "stopped"} and all(value == "absent" for value in states.values()):
            resolution = "failed"
        else:
            raise DesktopRecoveryError("Desktop start outcome is still active or ambiguous; preserve the journal for review")
    else:
        if observed == "stopped" and all(value == "absent" for value in states.values()):
            resolution = "complete"
        elif observed == "stop_incomplete":
            # This is an explicit supervisor failure result. Reconcile the
            # journal as failed even if an owned child remains; the next
            # bounded stop attempt can inspect and act on its recorded identity.
            resolution = "failed"
        else:
            raise DesktopRecoveryError("Desktop stop outcome is still active or ambiguous; preserve the journal for review")

    core: dict[str, object] = {
        "operation_id": operation_id,
        "record_kind": kind,
        "record_updated_at": record["updated_at"],
        "requested_display": requested_display,
        "affected_paths": [str(operation_journal.record_path(str(state_dir), operation_id, home_dir=home))],
        "observed_session_status": observed,
        "process_states": states,
        "session_sha256": hashlib.sha256(session_bytes).hexdigest() if session is not None else None,
        "resolution": resolution,
    }
    plan_id = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**core, "plan_id": plan_id, "requires_confirmation": True, "changed": False,
            "read_only": True,
            "impact": "Updates only the listed journal path; it does not signal processes or edit the inspected session record."}


def preview(operation_id: str, *, home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
            proc_root: Path = Path("/proc")) -> dict[str, object]:
    return _snapshot(operation_id, home=home, state_dir=state_dir, proc_root=proc_root)


def resolve(operation_id: str, *, home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
            confirmed: bool, plan_id: str | None, proc_root: Path = Path("/proc")) -> dict[str, object]:
    if type(confirmed) is not bool:
        raise DesktopRecoveryError("Explicit confirmation is required")
    current = preview(operation_id, home=home, state_dir=state_dir, proc_root=proc_root)
    if not confirmed:
        return current
    if not isinstance(plan_id, str) or plan_id != current["plan_id"]:
        raise DesktopRecoveryError("Recovery state changed or the exact preview plan ID is missing")
    verified = preview(operation_id, home=home, state_dir=state_dir, proc_root=proc_root)
    if verified["plan_id"] != plan_id:
        raise DesktopRecoveryError("Desktop session or journal changed after preview")
    operation_journal.resolve_desktop_record(
        str(state_dir), operation_id, expected_kind=str(current["record_kind"]),
        expected_updated_at=str(current["record_updated_at"]), result=str(current["resolution"]),
        observed_session_status=str(current["observed_session_status"]), home_dir=home,
    )
    return {"operation_id": operation_id, "resolution": current["resolution"],
            "observed_session_status": current["observed_session_status"], "changed": True,
            "read_only": False, "affected_paths": current["affected_paths"],
            "desktop_processes_signaled": False, "session_file_changed": False}
