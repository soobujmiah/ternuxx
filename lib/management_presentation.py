"""Shared human-facing vocabulary for Ternuxx management clients.

The resource catalog remains authoritative for category and resource identity.
This module supplies presentation labels only; it never decides lifecycle state
or authorizes an operation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Final


FIELD_LABELS: Final[dict[str, str]] = {
    "status": "Status", "state": "State", "current": "Current state",
    "ready": "Ready for startup", "blockers": "What must be fixed", "actions": "Startup actions",
    "readiness": "Readiness", "availability": "Availability",
    "ownership": "Ownership", "authority": "Managed by",
    "provider": "Provider", "environment": "Environment",
    "scheduler": "Background checker", "enabled": "Enabled", "running": "Running", "healthy": "Health",
    "interval_seconds": "Check interval (seconds)", "interval_value": "Check interval",
    "activity_launch": "Request Activity launch when missing",
    "focus_check": "Check Activity focus", "boot": "Boot startup",
    "boot_status": "Boot status", "persistent": "Keep active in background",
    "wakelock": "Wake Lock", "last_checked": "Last checked",
    "message": "Details", "impact": "Change impact", "action": "Action",
    "operation_id": "Action", "id": "Reference", "code": "Reference", "rollback_id": "Recovery reference",
    "profile": "Profile", "endpoint": "Connection address",
    "port": "Port", "bind_address": "Bind address", "auth_methods": "Login methods",
    "password_authentication": "Password login", "public_key_authentication": "Key login",
    "key_fingerprint": "Key fingerprint", "fingerprint": "Fingerprint",
    "private_key_path": "Private key file", "public_key_path": "Public key file",
    "private_key_mode": "Private key permissions", "public_key_mode": "Public key permissions",
    "enrollment_required": "Enroll public key for login", "shared_account_impact": "SSH account impact",
    "listener": "Listener", "service": "Service", "operation": "Operation",
    "category": "Category", "name": "Name", "description": "Description",
    "count": "Count", "key_count": "Authorized keys", "invalid_entries": "Invalid entries",
    "key_type": "Key type", "label": "Key label", "permissions": "File permissions",
    "unresolved_count": "Items needing attention",
    "read_only": "Read-only check", "reason": "Reason", "error": "Problem",
    'boot_id_relation': 'Boot ID check',
    'configured_profile': 'Selected startup profile',
    'desired': 'Target state',
    'last_verified_at': 'Last verified',
    'source_operation': 'Checked by',
    'gui_visible': 'Visible on screen',
    'x11': 'X11 display',
    'xfce4_session': 'XFCE desktop',
    'supervisor': 'Session manager',
    'listen_address': 'Listen address',
    'pid': 'Process ID',
    'process_start': 'Process start identity',
    'owner_count': 'Active Wake Lock owners',
    'platform_lock_state': 'Android Wake Lock state',
    'phase': 'Phase', 'app_id': 'App',
}

HIDDEN_FIELDS: Final[frozenset[str]] = frozenset({
    "password", "private_key", "secret", "token", "bootstrap_secret",
    "api_version", "request_id", "plan_id", "idempotency_key",
})

VALUE_LABELS: Final[dict[str, str]] = {
    "running_idle": "Ready; monitoring is off",
    "configuration-managed": "Policy managed by Ternuxx",
    "ternuxx_verified": "Verified as managed by Ternuxx",
    "configuration-managed-scheduler-not-installed": "Policy saved; background checker is not installed",
    "scheduler-not-installed": "Background checker is not installed",
    "source-scheduler-not-installed": "Background checker is not installed",
    "disabled-by-default": "Off by default",
    "native-termux": "Native Termux",
    "android-host-via-termux": "Android host through Termux",
    "loopback": "This device only (127.0.0.1)",
    "service.stop": "Service stop",
    "service.start": "Service start",
    "service.restart": "Service restart",
    'not-queried': 'Not checked yet',
    'not_configured': 'Not configured',
    'query-required': 'Check status to confirm',
    'query_required': 'Check status to confirm',
    'cold-boot-unverified': 'Boot startup not verified',
    'definition-verified-listener-pid-unverified': 'Service file verified; live listener ownership unknown',
    'read-only-evidence': 'Read-only diagnostic',
    'not_running': 'Not running',
    'not_connected': 'Not connected',
    'connected': 'Connected',
    'available': 'Available',
    'unavailable': 'Unavailable',
    'true': 'Yes',
    'false': 'No', 'UTC': 'UTC', 'X11': 'Termux:X11',
}

STATUS_LABELS: Final[dict[str, str]] = {
    "healthy": "Healthy",
    "running": "Running",
    "ready": "Ready",
    "starting": "Starting",
    "stopping": "Stopping",
    "stopped": "Stopped",
    "failed": "Failed",
    "stale": "Stale",
    "unknown": "Unknown",
    "unsafe": "Unsafe",
    "partial": "Partial",
    "implemented": "Implemented",
    "external": "Externally managed",
    "unverified": "Unverified",
    "unavailable": "Unavailable",
    "planned": "Planned",
    "not-queried": "Not checked",
}

STATUS_TONES: Final[dict[str, str]] = {
    "healthy": "good", "running": "good", "ready": "good",
    "implemented": "good", "starting": "pending", "stopping": "pending",
    "partial": "pending", "stale": "warning", "failed": "danger",
    "unsafe": "danger", "unknown": "muted", "stopped": "muted",
    "external": "muted", "unverified": "muted", "unavailable": "muted",
    "planned": "muted", "not-queried": "muted",
}

OPERATION_LABELS: Final[dict[str, str]] = {
    "ssh.keys.list": "Authorized SSH key fingerprints",
    "ssh.keys.add.preview": "Preview SSH key enrollment",
    "ssh.keys.add.apply": "Enroll SSH public key",
    "ssh.keys.remove.preview": "Preview SSH key removal",
    "ssh.keys.remove.apply": "Remove SSH public key",
    "ssh.client-key.create.preview": "Preview Native SSH recovery key creation",
    "ssh.client-key.create.apply": "Create Native SSH recovery key",
    "ssh.service.autostart.status": "SSH automatic-start preference",
    "ssh.service.autostart.preview": "Preview SSH automatic-start preference",
    "ssh.service.autostart.apply": "Change SSH automatic-start preference",
    "management.catalog": "Browse resources",
    "desktop.status": "Desktop status",
    "desktop.monitor.status": "Activity monitoring policy",
    "desktop.monitor.configure": "Update monitoring policy",
    "doctor.report": "System health report",
    "ssh.inspect": "SSH listener inspection",
    "ssh.service.start": "Start managed SSH",
    "ssh.service.stop": "Stop managed SSH",
    "ssh.service.restart": "Restart managed SSH",
    "boot.profile.status": "Boot profile status",
    "boot.profile.preview": "Preview boot profile",
    "boot.cron.status": "Cron boot integration status",
    "boot.cron.validate": "Validate Cron boot integration",
    "boot.cron.preview": "Preview Cron boot integration change",
    "boot.cron.enable": "Enable Cron at Termux boot",
    "boot.cron.disable": "Disable Cron at Termux boot",
    "recovery.status": "Recovery status",
    "continuity.status": "Reboot continuity status",
    "continuity.prepare.preview": "Preview continuity checkpoint creation",
    "continuity.prepare": "Create continuity checkpoint",
    "continuity.verify.preview": "Preview checkpoint verification",
    "continuity.verify": "Record checkpoint verification",
    "backup.list": "Available backups",
    "ssh.inspect": "SSH connection status",
    "boot.status": "Termux boot readiness",
    "boot.enable": "Enable startup profile",
    "boot.disable": "Disable startup profile",
    "wakelock.status": "Wake Lock status",
    "wakelock.ssh-policy.status": "Managed SSH keep-awake preference",
    "wakelock.ssh-policy.preview": "Preview managed SSH keep-awake preference",
    "wakelock.ssh-policy.apply": "Change managed SSH keep-awake preference",
    "wakelock.acquire": "Keep selected service awake",
    "wakelock.release": "Release selected service Wake Lock",
    "cron.status": "Scheduled task service status",
    "management.logs.list": "Available Ternuxx logs",
    "management.logs.read": "Read recent Ternuxx log entries",
    "service.deploy": "Deploy service definition",
    "desktop.start": "Start desktop",
    "desktop.stop": "Stop desktop",
    "desktop.restart": "Restart desktop",
    "recovery.backup.create": "Create recovery backup",
    "recovery.restore.apply": "Restore recovery backup",
    "recovery.restore.rollback": "Roll back recovery restore",
}

ERROR_MESSAGES: Final[dict[str, str]] = {
    "live_status_unavailable": "No live status check is available for this item.",
    "unknown_resource": "This item is no longer in the management catalog.",
    "invalid_action": "That action is not available.",
    "invalid_arguments": "The action details are incomplete or invalid.",
    "cancelled": "The action was cancelled.",
}


def status_label(value: object) -> str:
    """Translate known status values while preserving unknown values safely."""
    if not isinstance(value, str):
        return "Unknown"
    return STATUS_LABELS.get(value, value.replace("_", " ").capitalize())


def operation_label(operation: str) -> str:
    """Return a friendly operation label without hiding unknown operations."""
    return OPERATION_LABELS.get(operation, operation.replace(".", " ").replace("_", " ").capitalize())


def human_value(value: object) -> str:
    """Render common machine states as readable prose without changing data."""
    if isinstance(value, bool):
        return "On" if value else "Off"
    if value is None:
        return "Not reported"
    if isinstance(value, str):
        if value in {"SIGHUP", "SIGTERM", "SIGINT", "SIGKILL"}:
            return value
        if "/" in value:
            return value  # Paths and URLs are identifiers, not state tokens.
        if value in VALUE_LABELS:
            return VALUE_LABELS[value]
        if value in STATUS_LABELS:
            return STATUS_LABELS[value]
        return value.replace("_", " ").replace("-", " ").strip().capitalize()
    return str(value)


def format_report(value: object) -> str:
    """Format shared-service responses for people; omit credentials and IDs."""
    if isinstance(value, dict) and value.get("ok") is True:
        data = value.get("data")
        if isinstance(data, dict) and data.get("resource_id") == "proot.x11.shortcuts":
            return _format_proot_shortcuts(data)
    lines: list[str] = []
    if isinstance(value, dict):
        if value.get("ok") is True:
            lines.append("Result: Completed")
        elif value.get("ok") is False:
            lines.append("Result: Needs attention")
        error = value.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            if isinstance(code, str):
                message = ERROR_MESSAGES.get(
                    code, code.replace("_", " ").replace("-", " ").capitalize()
                )
                lines.append("Issue: " + message)
            detail = error.get("message") or error.get("detail")
            if isinstance(detail, str) and detail:
                lines.append("Details: " + detail)

    def visit(item: object, depth: int = 0, label: str | None = None) -> None:
        indent = "  " * depth
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = str(key).lower()
                if depth == 0 and normalized in {"ok", "error"}:
                    continue
                if normalized in HIDDEN_FIELDS or any(x in normalized for x in ("private_key", "password", "secret", "token")):
                    continue
                if normalized in {"request_id", "plan_id", "idempotency_key", "session_id", "journal_id"}:
                    continue
                title = FIELD_LABELS.get(normalized, str(key).replace("_", " ").replace(".", " ").capitalize())
                visit(child, depth + (1 if label else 0), title)
        elif isinstance(item, (list, tuple)):
            if label:
                lines.append(f"{indent}{label}:" if item else f"{indent}{label}: None")
            for index, child in enumerate(item, 1):
                if isinstance(child, (dict, list, tuple)):
                    lines.append(f"{indent}{index}.")
                    visit(child, depth + 1)
                else:
                    lines.append(f"{indent}{index}. {human_value(child)}")
        else:
            rendered = (operation_label(item) if label == "Operation" and isinstance(item, str)
                        else str(item) if label in {"Reference", "Action"} else human_value(item))
            lines.append(f"{indent}{label + ': ' if label else ''}{rendered}")

    visit(value)
    return "\n".join(lines) if lines else "No readable details were returned."


def _format_proot_shortcuts(data: dict[str, object]) -> str:
    """Keep guest launcher inventory readable without dumping localized desktop metadata."""
    fixed = data.get("items")
    fixed_items = [item for item in fixed if isinstance(item, dict)] if isinstance(fixed, list) else []
    dynamic = data.get("desktop_applications")
    dynamic_items = dynamic.get("items", []) if isinstance(dynamic, dict) else []
    dynamic_items = [item for item in dynamic_items if isinstance(item, dict)] if isinstance(dynamic_items, list) else []
    lines = [f"Debian shortcuts - {len(fixed_items)} fixed, {len(dynamic_items)} discovered app launchers"]
    for title, items in (("Fixed shortcuts", fixed_items), ("Discovered Debian apps", dynamic_items)):
        if not items:
            continue
        lines.append(title + ":")
        for item in items:
            identifier = item.get("id") or item.get("desktop_id")
            name = item.get("name")
            state = item.get("shortcut_state", item.get("status", "unknown"))
            if not isinstance(identifier, str) or not isinstance(state, str):
                continue
            label = f"{identifier} — {name}" if isinstance(name, str) and name else identifier
            availability = item.get("application_availability")
            suffix = f"; app {availability}" if isinstance(availability, str) and availability != "unknown" else ""
            lines.append(f"  {label}: {state}{suffix}")
    diagnostics = dynamic.get("diagnostics") if isinstance(dynamic, dict) else None
    if isinstance(diagnostics, list) and diagnostics:
        lines.append(f"Discovery diagnostics: {len(diagnostics)} (details omitted; use --json for structured output)")
    return "\n".join(lines)


def _history_time(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        local = instant.astimezone()
    except (ValueError, OverflowError):
        return None
    hour = local.hour % 12 or 12
    return f"{local:%b} {local.day}, {hour}:{local:%M} {local:%p}"


def _history_detail(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    detail = " ".join(value.split())
    detail = re.sub(
        r"(?i)\b(rollback|backup|plan|operation|journal)(?:[_ -]?id)?\s*[=:]\s*[a-f0-9-]{12,}",
        r"\1 reference hidden", detail,
    )
    detail = re.sub(r"\b[0-9a-f]{32,}\b", "internal reference hidden", detail, flags=re.I)
    detail = detail.strip(" ;,.")
    if not detail:
        return None
    return detail[:180].rstrip() + ("…" if len(detail) > 180 else "")


def format_activity_history(value: object, *, limit: int = 8) -> str:
    """Show a compact, readable operation history without opaque journal IDs."""
    if not isinstance(value, dict) or value.get("ok") is not True:
        return format_report(value)
    data = value.get("data")
    if not isinstance(data, dict):
        return "Recent management activity is unavailable."
    operations = data.get("operations")
    if not isinstance(operations, list):
        return "Recent management activity is unavailable."
    rows = [item for item in operations if isinstance(item, dict)]
    lines = [f"Recent management activity - {len(rows)} recorded actions"]
    unresolved = data.get("unresolved_count")
    if isinstance(unresolved, int) and not isinstance(unresolved, bool):
        lines.append(f"Items needing attention: {unresolved}")
    if not rows:
        lines.append("No management actions have been recorded yet.")
        return "\n".join(lines)
    count = max(1, limit)
    for index, item in enumerate(rows[:count], 1):
        kind = item.get("kind")
        action = operation_label(kind) if isinstance(kind, str) else "Management action"
        status = status_label(item.get("status"))
        lines.append(f"{index}. {action} - {status}")
        updated = _history_time(item.get("updated_at") or item.get("created_at"))
        if updated:
            lines.append(f"   {updated}")
        detail = _history_detail(item.get("detail"))
        if detail:
            lines.append(f"   {detail}")
    if len(rows) > count:
        lines.append(f"Showing the latest {count} of {len(rows)} actions.")
    return "\n".join(lines)
