#!/usr/bin/env python3
"""Keyboard-first categorized client for the shared Ternuxx management service."""
from __future__ import annotations

import curses
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import textwrap
import uuid
from typing import Any

import management_service
import management_sessions
import management_presentation
import proot_desktops


BRANDING_TAGLINE = "Workstation in your pocket — by Sobuj Miah"
BRANDING_URL = "soobujmiah.github.io"


READ_WITHOUT_ARGUMENTS = {
    op for op, spec in management_service.OPERATIONS.items()
    if not spec["args"] and op in management_sessions.READ_ONLY_OPERATIONS
}


def _call(operation: str, args: dict[str, object] | None = None) -> dict[str, object]:
    request = {"api_version": management_service.API_VERSION, "request_id": uuid.uuid4().hex,
               "operation": operation, "args": args or {}}
    return management_service.dispatch(request, caller="local_cli", env=dict(os.environ))


def _prompt(screen: "curses._CursesWindow", label: str, limit: int = 2048) -> str:
    height, width = screen.getmaxyx()
    screen.erase()
    screen.addnstr(0, 0, label, max(width - 1, 0))
    screen.addnstr(2, 0, "Enter=submit  Esc=cancel", max(width - 1, 0))
    screen.move(1, 0)
    curses.echo()
    try:
        value = screen.getstr(1, 0, min(limit, max(width - 1, 1)))
    except curses.error:
        value = b""
    finally:
        curses.noecho()
    return value.decode("utf-8", errors="replace").strip()


def _choose(screen: "curses._CursesWindow", title: str, options: list[tuple[str, str]]) -> str:
    """Compact keyboard menu: arrows or number, Enter selects, Esc cancels."""
    if not options:
        return ""
    index = offset = 0
    while True:
        screen.erase()
        height, width = screen.getmaxyx()
        if height < 4 or width < 4:
            return ""
        visible = min(len(options), height - 3)
        offset = min(offset, max(0, len(options) - visible))
        if index < offset:
            offset = index
        elif index >= offset + visible:
            offset = index - visible + 1
        screen.addnstr(0, 0, title, width - 1)
        for row, item_index in enumerate(range(offset, offset + visible), 2):
            _value, label = options[item_index]
            marker = ">" if item_index == index else " "
            screen.addnstr(row, 0, f"{marker} {item_index + 1}. {label}", width - 1)
        screen.addnstr(height - 1, 0, "↑/↓ move · 1–9 shortcut · Enter choose · Esc cancel", width - 1)
        screen.refresh()
        key = screen.getch()
        if key in (27, ord("q"), ord("Q")):
            return ""
        if key in (curses.KEY_UP, ord("k")):
            index = (index - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord("j")):
            index = (index + 1) % len(options)
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[index][0]
        elif ord("1") <= key <= ord("9") and key - ord("1") < len(options):
            return options[key - ord("1")][0]



















def _software_action(screen: "curses._CursesWindow", resource: dict[str, Any]) -> dict[str, object]:
    operations = set(resource.get("supported_operations", []))
    if "software.apps.list" not in operations:
        return {"ok": False, "error": {"code": "action_unavailable"}}
    report = _call("software.apps.list")
    if not report.get("ok"):
        return report
    apps = report.get("data", {}).get("apps", [])
    _show_details(screen, report)
    choices = [(item["id"], f"{item['name']} · {item['package']} · {item['status']}")
               for item in apps if isinstance(item, dict) and item.get("id")]
    app_id = _choose(screen, "Curated Native Termux apps", choices)
    selected_app = next((item for item in apps if item.get("id") == app_id), None)
    if not selected_app:
        return {"ok": False, "error": {"code": "cancelled"}}
    status = selected_app.get("status")
    actions: list[tuple[str, str]] = []
    if app_id == "directory-tree" and selected_app.get("installed") is True:
        actions.append(("run", "Inspect a file/directory under Native HOME"))
    if status == "available":
        actions.append(("install", "Install from official Termux repository"))
    elif status == "update_available":
        actions.extend((("update", "Update the selected app"), ("remove", "Remove the selected app")))
    elif status == "installed":
        actions.append(("remove", "Remove the selected app"))
    action = _choose(screen, selected_app["name"], actions)
    if action == "run" and app_id == "directory-tree" and "software.app.run" in operations:
        path = _prompt(screen, "HOME-relative path (e.g. Documents or notes.txt)", limit=4096).strip()
        if not path:
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("software.app.run", {"app_id": app_id, "path": path})
    if not action or not {"software.app.preview", "software.app.apply"} <= operations:
        return {"ok": False, "error": {"code": "cancelled"}}
    report = _call("software.app.preview", {"app_id": app_id, "action": action})
    if not report.get("ok"):
        return report
    _show_details(screen, report)
    token = action.upper()
    if _prompt(screen, f"Type {token} to apply this exact APT plan").strip() != token:
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("software.app.apply", {"app_id": app_id, "action": action,
                  "plan_id": report["data"]["plan_id"], "confirmation": token})


def _gpu_inference_action(screen: "curses._CursesWindow", resource: dict[str, Any]) -> dict[str, object]:
    operations = set(resource.get("supported_operations", []))
    action = _choose(screen, "Native Vulkan inference", [
        ("status", "List runtime-reported Vulkan inference devices"),
        ("run", "Run a bounded Vulkan prompt (no CPU fallback)"),
    ])
    if action == "status" and "inference.gpu.status" in operations:
        return _call("inference.gpu.status")
    if action != "run" or "inference.gpu.run" not in operations:
        return {"ok": False, "error": {"code": "cancelled"}}
    inventory = _call("inference.gpu.status")
    devices = inventory.get("data", {}).get("devices", []) if inventory.get("ok") else []
    if not devices:
        return inventory if not inventory.get("ok") else {
            "ok": False, "error": {"code": "gpu_unavailable",
            "message": inventory.get("data", {}).get("reason", "No Vulkan inference device is available.")}}
    selected_device = devices[0]["id"]
    if len(devices) > 1:
        choices = [(item["id"], f"{item['id']} — {item['name']}") for item in devices]
        selected_device = _choose(screen, "Choose Vulkan inference device", choices)
        if not selected_device or not any(item["id"] == selected_device for item in devices):
            return {"ok": False, "error": {"code": "cancelled"}}
    prompt = _prompt(screen, "One-line local prompt (max 4096 UTF-8 bytes)")
    if not prompt or _prompt(screen, f"Run on {selected_device}; GPU offload must be verified. Type RUN").strip() != "RUN":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("inference.gpu.run", {"prompt": prompt, "max_tokens": 64,
                  "device_id": selected_device})


def _npu_inference_action(screen: "curses._CursesWindow", resource: dict[str, Any]) -> dict[str, object]:
    operations = set(resource.get("supported_operations", []))
    action = _choose(screen, "Native Hexagon HTP inference", [
        ("status", "Check HTP0 runtime and device"),
        ("install", "Preview or install pinned Snapdragon runtime"),
        ("run", "Run experimental bounded HTP prompt (no CPU fallback)"),
    ])
    if action == "status" and "inference.npu.status" in operations:
        return _call("inference.npu.status")
    if action == "install" and {"inference.npu.runtime.preview", "inference.npu.runtime.apply"} <= operations:
        preview = _call("inference.npu.runtime.preview")
        if not preview.get("ok"):
            return preview
        _show_details(screen, preview)
        if _prompt(screen, "Type INSTALL to download and verify this exact MIT release").strip() != "INSTALL":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("inference.npu.runtime.apply", {
            "plan_id": preview.get("data", {}).get("plan_id"), "confirmed": True})
    if action != "run" or "inference.npu.run" not in operations:
        return {"ok": False, "error": {"code": "cancelled"}}
    inventory = _call("inference.npu.status")
    if not inventory.get("ok") or not inventory.get("data", {}).get("available"):
        return inventory if not inventory.get("ok") else {
            "ok": False, "error": {"code": "npu_unavailable",
            "message": inventory.get("data", {}).get("reason", "HTP0 is unavailable.")}}
    prompt = _prompt(screen, "One-line local prompt (max 4096 UTF-8 bytes)")
    if not prompt or _prompt(screen, "Run experimentally on HTP0 with no CPU fallback? Type RUN").strip() != "RUN":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("inference.npu.run", {"prompt": prompt, "max_tokens": 64})


def _desktop_action(screen: "curses._CursesWindow", resource: dict[str, Any]) -> dict[str, object]:
    allowed = resource.get("supported_operations", [])
    action = _choose(screen, "Native desktop", [(name, f"{name.title()} desktop") for name in ("start", "stop")
                      if f"desktop.{name}" in allowed])
    operation = {"start": "desktop.start", "stop": "desktop.stop"}.get(action)
    if not operation or operation not in resource.get("supported_operations", []):
        return {"ok": False, "error": {"code": "action_unavailable"}}
    args: dict[str, object] = {}
    if action == "start":
        status = _call("desktop.status")
        options = status.get("data", {}).get("desktop_options", []) if status.get("ok") else []
        choices = [(str(item.get("id")), f"{item.get('name')} · {'installed' if item.get('installed') else 'install ' + str(item.get('package'))}")
                   for item in options if isinstance(item, dict) and item.get("id")]
        selected = _choose(screen, "Native desktop on :1", choices)
        if not selected:
            return {"ok": False, "error": {"code": "cancelled"}}
        args["desktop_id"] = selected
    if _prompt(screen, f"Confirm {action} native desktop? type yes").lower() != "yes":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call(operation, args)


def _public_key_catalog() -> list[dict[str, str]]:
    ssh_dir = Path.home() / ".ssh"
    try:
        metadata = ssh_dir.lstat()
        if ssh_dir.is_symlink() or not ssh_dir.is_dir() or metadata.st_uid != os.getuid():
            return []
        candidates = sorted(ssh_dir.glob("*.pub"), key=lambda item: item.name.casefold())[:64]
    except OSError:
        return []
    found: list[dict[str, str]] = []
    for path in candidates:
        try:
            item = path.lstat()
            if path.is_symlink() or not path.is_file() or item.st_uid != os.getuid() or item.st_size > 16_384:
                continue
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |
                         getattr(os, "O_CLOEXEC", 0))
            try:
                opened = os.fstat(fd)
                if (not stat.S_ISREG(opened.st_mode) or opened.st_ino != item.st_ino
                        or opened.st_dev != item.st_dev or opened.st_uid != os.getuid()
                        or opened.st_size > 16_384):
                    continue
                with os.fdopen(fd, "rb", closefd=False) as stream:
                    content = stream.read(16_385)
            finally:
                os.close(fd)
            if len(content) > 16_384:
                continue
            raw = content.decode("utf-8").splitlines()
            if len(raw) != 1:
                continue
            parsed = management_service.ssh_key_inventory._parse_line(raw[0])
            if parsed and parsed.get("status") == "valid":
                found.append({"name": path.name, "public_key": raw[0],
                              "fingerprint": parsed["fingerprint"], "key_type": parsed["key_type"]})
        except (OSError, UnicodeError):
            continue
    return found


def _wakelock_action(screen: "curses._CursesWindow") -> dict[str, object]:
    choice = _choose(screen, "Wake Lock", [
        ("status", "Check current Wake Lock status"),
        ("ssh-policy", "Set managed SSH keep-awake preference"),
    ])
    if choice != "ssh-policy":
        return _call("wakelock.status")
    current = _call("wakelock.ssh-policy.status")
    if not current.get("ok"):
        return current
    enabled = current.get("data", {}).get("persistent_lease_enabled") is True
    answer = _prompt(screen, "Keep managed SSH awake across idle? Current: "
                     + ("Yes" if enabled else "No") + "; enter yes or no").lower()
    if answer not in {"yes", "no"}:
        return {"ok": False, "error": {"code": "cancelled"}}
    desired = answer == "yes"
    preview = _call("wakelock.ssh-policy.preview", {"enabled": desired})
    if not preview.get("ok") or not preview.get("data", {}).get("changed"):
        return preview
    _show_details(screen, preview)
    if _prompt(screen, "This applies at the next managed SSH start; current lease stays unchanged. Type yes").lower() != "yes":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("wakelock.ssh-policy.apply", {"enabled": desired, "confirmed": True,
                                                  "plan_id": preview.get("data", {}).get("plan_id")})


def _managed_ssh_action(screen: "curses._CursesWindow", resource: dict[str, Any]) -> dict[str, object]:
    if resource.get("id") != "network.ssh.managed-8023":
        return {"ok": False, "error": {"code": "externally_managed_resource"}}
    operations = set(resource.get("supported_operations", []))
    choices = [(name, f"{name.title()} SSH service") for name in ("start", "stop", "restart")
               if f"ssh.service.{name}" in operations]
    if "ssh.client-key.create.preview" in operations:
        choices.append(("generate", "Create a Native SSH recovery key"))
    if "ssh.service.autostart.status" in operations:
        choices.append(("autostart", "Change SSH start-with-Termux-services setting"))
    if "ssh.keys.list" in operations:
        choices.append(("keys", "View authorized SSH key fingerprints"))
    if "ssh.keys.add.preview" in operations:
        choices.append(("enroll", "Enroll a public key from Native .ssh"))
    if "ssh.keys.remove.preview" in operations:
        choices.append(("revoke", "Remove an authorized key"))
    if "ssh.keys.rollback.list" in operations:
        choices.append(("rollback", "Restore a previous SSH key change"))
    if "ssh.service.deploy" in operations:
        choices.append(("deploy", "Set up or reconcile the managed SSH service"))
    if "ssh.service.deploy.rollback.preview" in operations:
        choices.append(("deploy-rollback", "Restore a previous SSH service definition"))
    action = _choose(screen, "Managed SSH · port 8023", choices)
    if action == "keys":
        return _call("ssh.keys.list")
    if action == "rollback":
        listed = _call("ssh.keys.rollback.list")
        if not listed.get("ok"):
            return listed
        entries = listed.get("data", {}).get("entries", [])
        eligible = [entry for entry in entries if isinstance(entry, dict)]
        if not eligible:
            _show_details(screen, {"message": "No saved SSH key changes are available to restore."})
            return listed
        selected = _choose(screen, "Select an SSH key change to restore",
            [(str(i), f"{entry.get('action', 'change').title()} - {entry.get('fingerprint', '')} - {entry.get('status', '')}")
             for i, entry in enumerate(eligible)])
        if not isinstance(selected, str) or not selected.isdigit() or int(selected) >= len(eligible):
            return {"ok": False, "error": {"code": "cancelled"}}
        rollback_id = eligible[int(selected)].get("rollback_id")
        preview = _call("ssh.keys.rollback.preview", {"rollback_id": rollback_id})
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        _show_details(screen, plan)
        if not plan.get("can_restore"):
            return preview
        confirm = _prompt(screen, "Restore the exact previous authorized-keys file affecting "
                           + ", ".join(plan.get("affects_services", [])) + "? Type yes")
        if confirm.lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        result = _call("ssh.keys.rollback.apply", {"rollback_id": rollback_id,
            "confirmed": True, "plan_id": plan.get("plan_id")})
        if result.get("ok"):
            _call("ssh.keys.list")
        return result
    if action == "deploy":
        preview = _call("ssh.service.deploy", {"confirmed": False, "plan_id": None})
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        _show_details(screen, plan)
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan, dict) or plan.get("requires_confirmation") is not True or not isinstance(plan_id, str):
            return preview
        answer = _prompt(screen, "Apply this exact managed SSH setup/reconciliation plan? Type yes")
        if answer.lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("ssh.service.deploy", {"confirmed": True, "plan_id": plan_id})
    if action == "deploy-rollback":
        history = _call("recovery.status")
        if not history.get("ok"):
            return history
        records = history.get("data", {}).get("operations", [])
        eligible = [record for record in records if isinstance(record, dict)
                    and record.get("kind") == "service.deploy"
                    and record.get("status") in {"complete", "needs_recovery"}
                    and isinstance(record.get("operation_id"), str)]
        if not eligible:
            _show_details(screen, {"message": "No completed SSH service-definition deployment is available to restore."})
            return history
        selected = _choose(screen, "Select an SSH service-definition deployment",
            [(str(i), f"{record.get('status')} · {record.get('updated_at', '')} · {record['operation_id']}")
             for i, record in enumerate(eligible)])
        if not isinstance(selected, str) or not selected.isdigit() or int(selected) >= len(eligible):
            return {"ok": False, "error": {"code": "cancelled"}}
        operation_id = eligible[int(selected)]["operation_id"]
        preview = _call("ssh.service.deploy.rollback.preview", {"operation_id": operation_id})
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        _show_details(screen, plan)
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan, dict) or plan.get("requires_confirmation") is not True or not isinstance(plan_id, str):
            return preview
        answer = _prompt(screen, "Restore the exact pre-deployment Runit definition? The running sshd will not restart; type yes")
        if answer.lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("ssh.service.deploy.rollback.apply", {
            "operation_id": operation_id, "confirmed": True, "plan_id": plan_id})
    if action == "autostart":
        current = _call("ssh.service.autostart.status")
        if not current.get("ok"):
            return current
        enabled = current.get("data", {}).get("enabled") is True
        requested = _prompt(screen, "Start SSH automatically with Termux services? Current: "
                             + ("Yes" if enabled else "No") + "; enter yes or no").lower()
        if requested not in {"yes", "no"}:
            return {"ok": False, "error": {"code": "cancelled"}}
        desired = requested == "yes"
        preview = _call("ssh.service.autostart.preview", {"enabled": desired})
        if not preview.get("ok") or not preview.get("data", {}).get("changed"):
            return preview
        _show_details(screen, preview)
        if _prompt(screen, "This changes next-supervisor startup only; current sshd stays as-is. Type yes").lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("ssh.service.autostart.apply", {"enabled": desired, "confirmed": True,
                                                       "plan_id": preview.get("data", {}).get("plan_id")})
    if action == "generate":
        name = _prompt(screen, "Recovery key name (lowercase, numbers, hyphen, underscore)")
        preview = _call("ssh.client-key.create.preview", {"name": name})
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        if not isinstance(plan, dict) or not plan.get("changed"):
            return preview
        _show_details(screen, plan)
        if _prompt(screen, "Private file is stored without passphrase, mode 0600. Type yes to create").lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        created = _call("ssh.client-key.create.apply", {
            "name": name, "confirmed": True, "plan_id": plan.get("plan_id")})
        if not created.get("ok"):
            return created
        data = created.get("data", {})
        public_key = data.get("public_key") if isinstance(data, dict) else None
        if not isinstance(public_key, str):
            return created
        key_preview = _call("ssh.keys.add.preview", {"public_key": public_key})
        if not key_preview.get("ok"):
            return {"ok": True, "data": {"key": data, "enrollment": key_preview}}
        key_plan = key_preview.get("data", {})
        if not isinstance(key_plan, dict) or not key_plan.get("changed"):
            return {"ok": True, "data": {"key": data, "enrollment": key_preview}}
        _show_details(screen, key_plan)
        if _prompt(screen, "Enroll this public key for "
                   + ", ".join(key_plan.get("affects_services", [])) + "? Type yes").lower() != "yes":
            return {"ok": True, "data": {"key": data, "enrollment": "not enrolled"}}
        enrolled = _call("ssh.keys.add.apply", {"public_key": public_key,
            "confirmed": True, "plan_id": key_plan.get("plan_id")})
        if enrolled.get("ok"):
            _call("ssh.keys.list")
        return {"ok": bool(enrolled.get("ok")), "data": {"key": data, "enrollment": enrolled}}
    if action in {"enroll", "revoke"}:
        if action == "enroll":
            keys = _public_key_catalog()
            selected = _choose(screen, "Select a Native public key",
                [(str(i), f"{item['name']} · {item['key_type']} · {item['fingerprint']}")
                 for i, item in enumerate(keys)])
            if not selected.isdigit() or int(selected) >= len(keys):
                return {"ok": False, "error": {"code": "cancelled"}}
            key = keys[int(selected)]
            operation = "ssh.keys.add.preview"
            args: dict[str, object] = {"public_key": key["public_key"]}
            title = f"Enroll {key['name']} ({key['fingerprint']})"
        else:
            listed = _call("ssh.keys.list")
            inventory = listed.get("data", {}) if listed.get("ok") else {}
            keys = inventory.get("keys", []) if isinstance(inventory, dict) else []
            selected = _choose(screen, "Select a Ternuxx SSH authorized key",
                [(str(i), f"{item.get('key_type')} · {item.get('fingerprint')} · {item.get('label')}")
                 for i, item in enumerate(keys) if isinstance(item, dict)])
            if not selected.isdigit() or int(selected) >= len(keys):
                return {"ok": False, "error": {"code": "cancelled"}}
            key = keys[int(selected)]
            operation = "ssh.keys.remove.preview"
            args = {"fingerprint": key["fingerprint"]}
            title = f"Remove {key.get('key_type')} · {key['fingerprint']}"
        preview = _call(operation, args)
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        if not isinstance(plan, dict) or not plan.get("changed"):
            return preview
        _show_details(screen, plan)
        confirm = _prompt(screen,
            f"{title}. Affects {', '.join(plan.get('affects_services', []))}. Type yes to confirm")
        if confirm.lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        apply_op = operation.replace(".preview", ".apply")
        args.update({"confirmed": True, "plan_id": plan.get("plan_id")})
        result = _call(apply_op, args)
        if result.get("ok"):
            _call("ssh.keys.list")
        return result
    operation = {"start": "ssh.service.start", "stop": "ssh.service.stop", "restart": "ssh.service.restart"}.get(action)
    if not operation or operation not in operations:
        return {"ok": False, "error": {"code": "action_unavailable"}}
    preview = _call(operation, {"confirmed": False, "plan_id": None})
    if not preview.get("ok"):
        return preview
    data = preview.get("data", {})
    if not isinstance(data, dict):
        return {"ok": False, "error": {"code": "invalid_service_preview"}}
    if not data.get("requires_confirmation"):
        return preview
    plan_id = data.get("plan_id")
    if not isinstance(plan_id, str):
        return {"ok": False, "error": {"code": "invalid_service_preview"}}
    impact = str(data.get("impact", "Only the Ternuxx-managed SSH service on 127.0.0.1:8023 will change."))
    confirm = _prompt(screen, f"Impact: {impact} other Native SSH configurations are excluded. Type yes to {action}").lower()
    if confirm != "yes":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call(operation, {"confirmed": True, "plan_id": plan_id})

def _edit_monitor_policy(screen: "curses._CursesWindow") -> dict[str, object] | None:
    current = _call("desktop.monitor.status")
    if not current.get("ok"):
        return current
    data = current.get("data", {})
    enabled = _prompt(screen, f"Monitoring enabled [{str(data.get('enabled', False)).lower()}]? y/n")
    if enabled.lower() not in {"y", "n"}:
        return None
    interval = _prompt(screen, f"Interval value in seconds/minutes/hours (current {data.get('interval_seconds', 300)} seconds)")
    unit = _prompt(screen, "Interval unit: seconds, minutes, or hours (blank=seconds)").lower() or "seconds"
    if not interval.isdecimal() or unit not in {"seconds", "minutes", "hours"}:
        return {"ok": False, "error": {"code": "invalid_interval", "message": "Enter a whole interval and a supported unit."}}
    seconds = int(interval) * {"seconds": 1, "minutes": 60, "hours": 3600}[unit]
    if not 30 <= seconds <= 86400:
        return {"ok": False, "error": {"code": "invalid_interval", "message": "Use 30 seconds to 24 hours."}}
    focus = _prompt(screen, f"Check Android Activity focus [{str(data.get('focus_check', False)).lower()}]? y/n")
    launch = _prompt(screen, f"Request Activity when background [{str(data.get('activity_launch', False)).lower()}]? y/n")
    if focus.lower() not in {"y", "n"} or launch.lower() not in {"y", "n"}:
        return None
    if _prompt(screen, "Save monitoring policy? type yes").lower() != "yes":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("desktop.monitor.configure", {
        "enabled": enabled.lower() == "y", "interval_value": int(interval), "unit": unit,
        "focus_check": focus.lower() == "y", "activity_launch": launch.lower() == "y",
    })


def _resource_state(resource: dict[str, Any]) -> str:
    state = resource.get("state") or {}
    return management_presentation.status_label(state.get("current", "unknown"))


def _manage_logs(screen: "curses._CursesWindow") -> dict[str, object]:
    """Read a bounded exact-source log tail through the shared service."""
    inventory = _call("management.logs.list")
    if not inventory.get("ok"):
        return inventory
    sources = inventory.get("data", {}).get("sources", [])
    available = [item for item in sources if isinstance(item, dict) and item.get("status") == "available"]
    if not available:
        return {"ok": True, "operation": "management.logs.list",
                "data": {"sources": sources, "message": "No Ternuxx log files are present."}}
    choices = ", ".join(str(item.get("source_id")) for item in available)
    source_id = _prompt(screen, "Log source (" + choices + ")")
    if not any(item.get("source_id") == source_id for item in available):
        return {"ok": False, "error": {"code": "unknown_log_source"}}
    return _call("management.logs.read", {"source_id": source_id, "limit": 100})


def _boot_action(screen: "curses._CursesWindow") -> dict[str, object]:
    """Guide a preview-first Native Termux startup-profile change."""
    choice = _prompt(screen, "Startup: status, preview, enable, disable, helpers (blank cancels)").lower()
    if choice == "status":
        return _call("boot.profile.status")
    if choice == "preview":
        profile = _prompt(screen, "Profile: cli-only or native").lower()
        if profile not in {"cli-only", "native"}:
            return {"ok": False, "error": {"code": "unsupported_boot_profile"}}
        return _call("boot.profile.preview", {"profile": profile})
    if choice == "enable":
        profile = _prompt(screen, "Enable at Termux boot: cli-only or native").lower()
        if profile not in {"cli-only", "native"}:
            return {"ok": False, "error": {"code": "unsupported_boot_profile"}}
        preview = _call("boot.profile.preview", {"profile": profile})
        if not preview.get("ok") or preview.get("data", {}).get("ready") is not True:
            return preview
        _show_details(screen, preview)
        if _prompt(screen, "Review the startup profile and enable it? type yes").lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("boot.enable", {"profile": profile, "confirmed": True})
    if choice == "disable":
        current = _call("boot.profile.status")
        if not current.get("ok"):
            return current
        _show_details(screen, current)
        if _prompt(screen, "Disable only the Ternuxx-managed startup profile? type yes").lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("boot.disable", {"confirmed": True})
    if choice == "helpers":
        return _boot_helpers_action(screen)
    return {"ok": False, "error": {"code": "cancelled"}}


def _boot_cron_action(screen: "curses._CursesWindow") -> dict[str, object]:
    """Manage only the optional Termux:Boot Cron entrypoint, preview first."""
    choice = _prompt(screen, "Cron boot: status, validate, preview enable/disable, enable, disable (blank cancels)").lower()
    if choice == "status":
        return _call("boot.cron.status")
    if choice == "validate":
        return _call("boot.cron.validate")
    if choice not in {"preview enable", "preview disable", "enable", "disable"}:
        return {"ok": False, "error": {"code": "cancelled"}}
    action = choice.removeprefix("preview ")
    preview = _call("boot.cron.preview", {"action": action})
    if not preview.get("ok") or choice.startswith("preview "):
        return preview
    plan = preview.get("data", {})
    _show_details(screen, preview)
    if plan.get("ready") is not True:
        return preview
    if plan.get("requires_confirmation") is not True:
        return preview
    if _prompt(screen, f"Review this exact Termux:Boot Cron change and {action}? type yes").lower() != "yes":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call(f"boot.cron.{action}", {
        "confirmed": True, "plan_id": plan.get("plan_id")})


def _boot_helpers_action(screen: "curses._CursesWindow") -> dict[str, object]:
    """Inspect or reconcile only the two repository-owned boot helper files."""
    status = _call("boot.helpers.status")
    if not status.get("ok"):
        return status
    _show_details(screen, status)
    choice = _prompt(screen, "Boot helpers: status, deploy, rollback (blank cancels)").lower()
    if choice == "status":
        return status
    if choice not in {"deploy", "rollback"}:
        return {"ok": False, "error": {"code": "cancelled"}}
    helper_id = _prompt(screen, "Helper ID: services or recovery").lower()
    if helper_id not in {"services", "recovery"}:
        return {"ok": False, "error": {"code": "invalid_boot_helper"}}
    snapshot_id = None
    if choice == "rollback":
        available = [item for item in status.get("data", {}).get("snapshots", [])
                     if item.get("helper_id") == helper_id]
        if not available:
            return {"ok": False, "error": {"code": "boot_helper_snapshot_unavailable"}}
        choices = "\n".join(f"{item.get('snapshot_id')} · {item.get('created_at')} · {item.get('sha256')}"
                             for item in available)
        snapshot_id = _prompt(screen, "Snapshot ID for " + helper_id + ":\n" + choices)
        if not any(item.get("snapshot_id") == snapshot_id for item in available):
            return {"ok": False, "error": {"code": "invalid_boot_helper_snapshot"}}
    preview = _call("boot.helpers.preview", {"helper_id": helper_id, "action": choice,
                        "snapshot_id": snapshot_id})
    if not preview.get("ok"):
        return preview
    data = preview.get("data", {})
    plan = data.get("plan", {}) if isinstance(data, dict) else {}
    plan_id = plan.get("plan_id")
    if (data.get("confirmation_required") is not True or not isinstance(plan_id, str)
            or not re.fullmatch(r"[0-9a-f]{32}", plan_id)):
        return preview
    _show_details(screen, preview)
    word = choice.upper()
    if _prompt(screen, f"Apply this exact boot-helper {choice}? type {word}").strip().upper() != word:
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("boot.helpers.apply", {"helper_id": helper_id, "action": choice,
        "snapshot_id": snapshot_id, "confirmed": True, "plan_id": plan_id})


def _cron_scheduler_action(screen: "curses._CursesWindow") -> dict[str, object]:
    """Start or stop the Ternuxx scheduler only after an explicit review."""
    choice = _prompt(screen, "Cron service: status, start, stop (blank cancels)").lower()
    if choice == "status":
        return _call("cron.status")
    if choice == "start":
        raw_interval = _prompt(screen, "Check interval in seconds (1-60, default 5)") or "5"
        if not raw_interval.isdigit() or not 1 <= int(raw_interval) <= 60:
            return {"ok": False, "error": {"code": "invalid_poll_interval"}}
        interval = int(raw_interval)
        _show_details(screen, {"ok": True, "data": {
            "action": "Start the Ternuxx Cron scheduler", "interval_seconds": interval,
            "boot_start": "not enabled by this action",
        }})
        if _prompt(screen, "Start this Ternuxx service now? type yes").lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("cron.scheduler.start", {"poll_seconds": interval, "confirmed": True})
    if choice == "stop":
        _show_details(screen, {"ok": True, "data": {"action": "Stop only the Ternuxx Cron scheduler"}})
        if _prompt(screen, "Stop the Ternuxx Cron scheduler now? type yes").lower() != "yes":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("cron.scheduler.stop", {"confirmed": True})
    return {"ok": False, "error": {"code": "cancelled"}}


def _available_action_labels(resource: dict[str, Any]) -> list[str]:
    """Describe only guided controls implemented by this TUI for this resource."""
    resource_id = resource.get("id")
    operations = set(resource.get("supported_operations", []))
    labels: list[str] = []
    if _selected_status_operation(resource):
        labels.append("check status")
    if resource_id == "native.system.health" and "management.logs.list" in operations:
        labels.append("view bounded Ternuxx logs")
    if resource_id == "native.desktop.session":
        labels.extend(name for op, name in (("desktop.start", "start desktop"),
                                            ("desktop.stop", "stop desktop")) if op in operations)
    elif resource_id == "graphics.native":
        labels.extend(("check graphics status", "verify OpenGL", "verify GLES", "verify Vulkan"))
        if resource_id == "graphics.native" and "graphics.provider.select" in operations:
            labels.append("select backend (KGSL experimental)")
    elif resource_id == "inference.cpu.local":
        labels.extend(name for op, name in (("inference.cpu.status", "check CPU inference status"),
            ("inference.cpu.model.preview", "preview pinned model setup"),
            ("inference.cpu.run", "run a bounded CPU prompt")) if op in operations)
    elif resource_id == "inference.gpu.local":
        labels.extend(name for op, name in (("inference.gpu.status", "list Vulkan inference devices"),
            ("inference.gpu.run", "run a bounded Vulkan prompt")) if op in operations)
    elif resource_id == "inference.npu.local":
        labels.extend(name for op, name in (("inference.npu.status", "check HTP0 runtime and device"),
            ("inference.npu.runtime.preview", "preview Snapdragon runtime install"),
            ("inference.npu.run", "run a bounded experimental HTP prompt")) if op in operations)
    elif resource_id == "proot.interactive-terminal-broker":
        labels.extend(name for op, name in (("terminal.broker.service.status", "check terminal broker service"),
            ("terminal.start.preview", "preview interactive Debian start")) if op in operations)
    elif resource_id == "proot.replay-guests":
        if {"proot.setup.retire.preview", "proot.setup.retire.apply",
                "proot.setup.restore.preview", "proot.setup.restore.apply"} <= operations:
            labels.append("preview and retire or restore an exact replay guest")
    elif resource_id == "proot.debian.workloads":
        if {"proot.shortcuts.list", "proot.shortcuts.preview", "proot.shortcuts.apply"} <= operations:
            labels.append("preview and manage Debian app shortcuts")
        if {"proot.shortcuts.sync.preview", "proot.shortcuts.sync.apply"} <= operations:
            labels.append("preview and synchronize Debian app shortcuts")
        if {"proot.shortcuts.sync.rollback.list", "proot.shortcuts.sync.rollback.preview",
            "proot.shortcuts.sync.rollback.apply"} <= operations:
            labels.append("preview and restore a shortcut sync")
    elif resource_id == "software.curated-apps":
        if "software.apps.list" in operations:
            labels.append("browse curated Native apps")
        if {"software.app.preview", "software.app.apply"} <= operations:
            labels.append("preview and manage an app")
    elif resource_id == "native.gui.activity-monitor":
        labels.append("configure monitoring policy")
    elif resource_id == "native.timezone" and "timezone.set" in operations:
        labels.append("configure Ternuxx timezone preference")
    elif resource_id == "network.ssh.managed-8023":
        labels.extend(name for op, name in (("ssh.service.start", "start SSH 8023 (preview)"),
                                            ("ssh.service.stop", "stop SSH 8023 (preview)"),
                                            ("ssh.service.restart", "restart SSH 8023 (preview)")) if op in operations)
        if "ssh.client-key.create.preview" in operations:
            labels.append("create and optionally enroll a Native SSH recovery key")
        if "ssh.keys.add.preview" in operations:
            labels.append("enroll a public key from Native .ssh")
        if "ssh.keys.remove.preview" in operations:
            labels.append("remove an authorized key by fingerprint")
        labels.append("public-key login only; password login is disabled")
        if "ssh.service.autostart.status" in operations:
            labels.append("change SSH start-with-Termux-services preference")
    elif resource_id == "native.wakelock":
        labels.append("inspect Ternuxx-owned Wake Lock leases")
        if {"wakelock.acquire", "wakelock.release"} <= operations:
            labels.append("lease controls require a workload-bound owner and are not exposed in this TUI")
    elif resource_id == "boot.termux.profile":
        labels.extend(name for op, name in (("boot.profile.status", "check startup profile"),
                                            ("boot.profile.preview", "preview startup profile"),
                                            ("boot.enable", "enable startup profile"),
                                            ("boot.disable", "disable startup profile")) if op in operations)
    elif resource_id == "boot.termux.cron":
        labels.extend(name for op, name in (("boot.cron.status", "check Cron boot entrypoint"),
                                            ("boot.cron.validate", "validate Cron boot readiness"),
                                            ("boot.cron.preview", "preview Cron boot setup/removal"),
                                            ("boot.cron.enable", "enable Cron at device boot"),
                                            ("boot.cron.disable", "disable Cron device-boot entrypoint")) if op in operations)
    elif resource_id == "boot.termux.profile" and "boot.helpers.status" in operations:
        labels.append("inspect, deploy, or roll back the two Ternuxx-owned boot helpers")
    elif resource_id == "recovery.native-state" and "recovery.status" in operations:
        labels.extend(("view operation history", "list/inspect backups", "create backup", "preview/apply restore and rollback",
                       "reconcile unresolved operations", "check reboot continuity", "prepare and verify continuity checkpoints",
                       "prepare and verify detailed reboot qualifications"))
    elif resource_id == "automation.cron-registry":
        if {"cron.scheduler.start", "cron.scheduler.stop"} <= operations:
            labels.append("check, start, or stop Cron scheduler")
        if "cron.jobs.list" in operations:
            labels.append("list persisted job definitions")
        if "cron.jobs.show" in operations:
            labels.append("inspect a saved job")
        if "cron.jobs.next_runs" in operations:
            labels.append("preview upcoming job runs")
        if {"cron.jobs.mutation.preview", "cron.jobs.mutation.apply"} <= operations:
            labels.append("preview and apply Cron job changes")
        if "cron.executions.list" in operations:
            labels.append("view Cron execution history")
        if "cron.executions.show" in operations:
            labels.append("inspect an execution record")
    return labels


def _wrap_line(value: object, width: int) -> list[str]:
    return textwrap.wrap(str(value), max(1, width), break_long_words=True,
                         break_on_hyphens=False) or [""]


def _put_wrapped(screen: "curses._CursesWindow", row: int, col: int, value: object,
                 width: int, color: int | None = None) -> int:
    height, screen_width = screen.getmaxyx()
    lines = _wrap_line(value, min(width, max(1, screen_width - col - 1)))
    for line in lines:
        if row >= height:
            break
        if color is not None:
            screen.attron(curses.color_pair(color))
        screen.addnstr(row, col, line, max(0, screen_width - col - 1))
        if color is not None:
            screen.attroff(curses.color_pair(color))
        row += 1
    return row


def _put_fixed_line(screen: "curses._CursesWindow", row: int, col: int, value: object,
                    width: int, color: int | None = None) -> None:
    """Write a single clipped line so selection changes never move the list."""
    height, screen_width = screen.getmaxyx()
    if row < 0 or row >= height or col >= screen_width:
        return
    limit = max(0, min(width, screen_width - col - 1))
    text = str(value)
    if len(text) > limit:
        text = text[:max(0, limit - 1)] + ("…" if limit else "")
    if color is not None:
        screen.attron(curses.color_pair(color))
    screen.addnstr(row, col, text, limit)
    if color is not None:
        screen.attroff(curses.color_pair(color))


def _footer_layout(width: int) -> list[list[tuple[str, int]]]:
    limit = max(1, width - 2)
    groups = [
        ("←/→", "category", 2), ("↑/↓", "resource", 2), ("Enter", "status", 1),
        ("1–9/0", "jump", 2), ("PgUp/PgDn", "page", 2),
        ("H", "history", 3), ("v", "details", 4), ("a", "actions", 1),
        ("r", "refresh", 3), ("q", "quit", 6),
    ]
    rows: list[list[tuple[str, int]]] = [[]]
    used = 0
    for key, label, color in groups:
        pieces = _wrap_line(f"{key} {label}", limit)
        for piece in pieces:
            extra = len(piece) + (3 if rows[-1] else 0)
            if rows[-1] and used + extra > limit:
                rows.append([])
                used = 0
                extra = len(piece)
            if rows[-1]:
                rows[-1].append((" · ", 5))
                used += 3
            rows[-1].append((piece, color))
            used += len(piece)
    return rows


def _draw(screen: "curses._CursesWindow", categories: list[dict[str, Any]], category_index: int,
          resources: list[dict[str, Any]], selected: int, query: str,
          report: dict[str, object] | None, scroll: int = 0) -> int:
    screen.erase()
    height, width = screen.getmaxyx()
    content_width = max(1, width - 2)
    header = [
        ("Ternuxx Management Center", 1),
        (BRANDING_TAGLINE, 2),
        (BRANDING_URL, 4),
    ]
    row = 0
    for value, color in header:
        for line in _wrap_line(value, content_width):
            if row >= height:
                break
            col = max(0, (width - len(line)) // 2)
            screen.attron(curses.color_pair(color))
            screen.addnstr(row, col, line, max(0, width - col - 1))
            screen.attroff(curses.color_pair(color))
            row += 1
    category = categories[category_index] if categories else {"name": "Resources"}
    counts = {state: sum(1 for item in resources if item.get("status") == state)
              for state in ("implemented", "partial", "external", "unverified", "unavailable", "planned")}
    selected_resource = resources[selected] if resources and selected < len(resources) else None
    action_text = ", ".join(_available_action_labels(selected_resource)) if selected_resource else "none"

    def divider(at: int) -> int:
        if at < height:
            screen.attron(curses.color_pair(5))
            screen.addnstr(at, 1, "─" * content_width, max(0, width - 2))
            screen.attroff(curses.color_pair(5))
        return at + 1

    row = divider(row)
    row = _put_wrapped(screen, row, 1,
                       f"{category['name']}  ·  category {category_index + 1}/{len(categories)}  ·  {len(resources)} resources",
                       content_width, color=2)
    summary = (f"Available: {counts['implemented']} implemented · {counts['partial']} partial · "
               f"{counts['external']} external · {counts['planned']} planned")
    row = _put_wrapped(screen, row, 1, summary, content_width, color=3)
    row = _put_wrapped(screen, row, 1,
                       f"Search: {query or '—'}  ·  ←/→ category  / search  Enter status  H history  v details",
                       content_width, color=4)
    row = divider(row)
    _put_fixed_line(screen, row, 1, f"Actions · {action_text}", content_width, color=2)
    row += 1

    footer_rows = _footer_layout(width)
    footer_top = max(0, height - len(footer_rows))
    feedback_top = max(row, footer_top - 2)
    if report:
        error = report.get("error") if isinstance(report.get("error"), dict) else {}
        code = error.get("code")
        message = "Last action · " + ("Complete" if report.get("ok") else management_presentation.human_value(code or "failed"))
        formatted = management_presentation.format_report(report).splitlines()
        values = [line.strip() for line in formatted if line.strip() and not line.lstrip().startswith(("Ok:", "Error:"))][:2]
        _put_fixed_line(screen, feedback_top, 1, message, content_width,
                        color=6 if not report.get("ok") else 1)
        _put_fixed_line(screen, feedback_top + 1, 1, " · ".join(values), content_width, color=5)
    content_bottom = feedback_top

    item_lines = []
    for resource_index, resource in enumerate(resources, 1):
        status = management_presentation.status_label(resource.get("status", "unknown"))
        label = f"{resource_index:>2}. {resource.get('name', 'Resource')} · {status} · {_resource_state(resource)}"
        item_lines.append(_wrap_line(label, content_width))
    scroll = min(max(0, scroll), max(0, len(resources) - 1))
    while scroll < selected and sum(len(item_lines[index]) for index in range(scroll, selected + 1)) > max(0, content_bottom - row):
        scroll += 1
    cursor = row
    for index in range(scroll, len(resources)):
        lines = item_lines[index]
        if cursor + len(lines) > content_bottom:
            break
        resource = resources[index]
        state = resource.get("status", "unknown")
        color = 1 if state == "implemented" else (3 if state in ("partial", "external", "unverified") else 6)
        for line_index, line in enumerate(lines):
            shown = (">" if index == selected else " ") + line[1:] if line_index == 0 else line
            screen.attron(curses.color_pair(color))
            if index == selected:
                screen.attron(curses.A_REVERSE)
            screen.addnstr(cursor, 1, shown, max(0, width - 2))
            if index == selected:
                screen.attroff(curses.A_REVERSE)
            screen.attroff(curses.color_pair(color))
            cursor += 1
    if not resources and row < content_bottom:
        _put_wrapped(screen, row, 1, "No resources match this search.", content_width, color=5)
    if row >= content_bottom and height:
        _put_wrapped(screen, max(0, footer_top - 1), 1,
                     "Make the terminal wider or reduce zoom to see more.", content_width, color=3)

    for offset, segments in enumerate(footer_rows):
        footer_row = footer_top + offset
        col = 1
        for value, color in segments:
            if footer_row >= height:
                break
            screen.attron(curses.color_pair(color))
            screen.addnstr(footer_row, col, value, max(0, width - col - 1))
            screen.attroff(curses.color_pair(color))
            col += len(value)
    screen.refresh()
    return scroll


def _detail_lines(report: dict[str, object] | None, width: int) -> list[str]:
    if not report:
        return ["No operation details are available."]
    rendered = management_presentation.format_report(report)
    lines: list[str] = []
    for raw in rendered.splitlines():
        indent = len(raw) - len(raw.lstrip())
        prefix = " " * min(indent, max(0, width - 1))
        content = raw[indent:]
        lines.extend(textwrap.wrap(content, max(1, width - len(prefix)),
                                   subsequent_indent="") or [""])
        if prefix and lines:
            lines[-1] = prefix + lines[-1]
    return lines


def _show_details(screen: "curses._CursesWindow", report: dict[str, object] | None) -> None:
    offset = 0
    while True:
        screen.erase()
        height, width = screen.getmaxyx()
        title = " Operation details ".ljust(max(width - 1, 0))
        screen.attron(curses.color_pair(1))
        screen.addnstr(0, 0, title, max(width - 1, 0))
        screen.attroff(curses.color_pair(1))
        lines = _detail_lines(report, max(1, width - 3))
        page = max(1, height - 4)
        offset = min(max(0, offset), max(0, len(lines) - page))
        for row, line in enumerate(lines[offset:offset + page], 2):
            screen.addnstr(row, 1, line, max(0, width - 2))
        screen.addnstr(height - 1, 0, " ↑/↓ scroll · PgUp/PgDn · q back ".ljust(max(width - 1, 0)), max(width - 1, 0))
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), ord("Q"), 27):
            return
        if key in (curses.KEY_DOWN, ord("j")):
            offset += 1
        elif key in (curses.KEY_UP, ord("k")):
            offset -= 1
        elif key == curses.KEY_NPAGE:
            offset += page
        elif key == curses.KEY_PPAGE:
            offset -= page


def _cron_jobs() -> dict[str, object]:
    """Read persisted Cron definitions via the shared management service."""
    return _call("cron.jobs.list")


def _timezone_action(screen: "curses._CursesWindow") -> dict[str, object]:
    current = _call("timezone.status")
    if not current.get("ok"):
        return current
    current_zone = str(current.get("data", {}).get("timezone", "unknown"))
    zones = _call("timezone.list")
    if not zones.get("ok"):
        return zones
    available = zones.get("data", {}).get("timezones", [])
    selected = _prompt(screen, f"IANA timezone (current {current_zone}; available zones via tx mng timezone list)")
    if not selected:
        return {"ok": False, "error": {"code": "cancelled"}}
    if selected not in available:
        return {"ok": False, "error": {"code": "timezone_unavailable"}}
    if _prompt(screen, f"Set Ternuxx preference to {selected}? type yes").lower() != "yes":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("timezone.set", {"timezone": selected})


def _cron_mutation(screen: "curses._CursesWindow") -> dict[str, object]:
    """Preview one typed Cron definition change, then apply that saved plan."""
    action = _prompt(screen, "Cron change: create, update, remove (blank cancels)").lower()
    if action not in {"create", "update", "remove"}:
        return {"ok": False, "error": {"code": "cancelled"}}
    if action == "create":
        name = _prompt(screen, "Job name")
        action_id = _prompt(screen, "Registered safe action ID (doctor, catalog refresh, Hermes status, self-test)")
        schedule_type = _prompt(screen, "Schedule type: cron, interval, calendar, one_time").lower()
        if not name or schedule_type not in {"cron", "interval", "calendar", "one_time"}:
            return {"ok": False, "error": {"code": "invalid_cron_input"}}
        schedule: dict[str, object]
        if schedule_type == "cron":
            expression = _prompt(screen, "Five-field Cron expression (minute hour day month weekday)")
            if not expression: return {"ok": False, "error": {"code": "invalid_cron_input"}}
            schedule = {"expression": expression}
            timezone_name = _prompt(screen, "IANA timezone (blank uses Ternuxx preference)")
            if timezone_name: schedule["timezone"] = timezone_name
        elif schedule_type == "interval":
            raw_interval = _prompt(screen, "Interval seconds (1–31536000)")
            anchor = _prompt(screen, "Anchor ISO-8601 datetime with UTC offset")
            if not raw_interval.isdigit() or not anchor:
                return {"ok": False, "error": {"code": "invalid_cron_input"}}
            schedule = {"interval_seconds": int(raw_interval), "anchor_at": anchor}
        elif schedule_type == "calendar":
            mode = _prompt(screen, "Calendar mode: daily or specific").lower()
            if mode == "daily":
                value = _prompt(screen, "Local time HH:MM (24-hour)")
                timezone_name = _prompt(screen, "IANA timezone (blank uses Ternuxx preference)")
                if not value: return {"ok": False, "error": {"code": "invalid_cron_input"}}
                schedule = {"mode": "daily", "time": value}
                if timezone_name: schedule["timezone"] = timezone_name
            elif mode == "specific":
                value = _prompt(screen, "Future ISO-8601 datetime with UTC offset")
                if not value: return {"ok": False, "error": {"code": "invalid_cron_input"}}
                schedule = {"mode": "specific", "datetime": value}
            else:
                return {"ok": False, "error": {"code": "invalid_cron_input"}}
        else:
            value = _prompt(screen, "Future ISO-8601 datetime with UTC offset")
            if not value: return {"ok": False, "error": {"code": "invalid_cron_input"}}
            schedule = {"at": value}
        args = {"action": "create", "name": name, "action_id": action_id,
                "schedule_type": schedule_type, "schedule": schedule}
    else:
        listing = _cron_jobs()
        if not listing.get("ok"):
            return listing
        jobs = listing.get("data", {}).get("jobs", [])
        if not jobs:
            return {"ok": False, "error": {"code": "no_cron_jobs"}}
        choices = ", ".join(f"{j.get('job_id')} ({j.get('name')})" for j in jobs if isinstance(j, dict))
        job_id = _prompt(screen, "Job ID from saved jobs: " + choices)
        if not any(isinstance(j, dict) and j.get("job_id") == job_id for j in jobs):
            return {"ok": False, "error": {"code": "unknown_job_id"}}
        if action == "remove":
            args = {"action": action, "job_id": job_id}
        else:
            field = _prompt(screen, "Update field: name or enabled").lower()
            if field == "name":
                value = _prompt(screen, "New job name")
                changes: dict[str, object] = {"name": value}
            elif field == "enabled":
                value = _prompt(screen, "Set enabled? yes or no").lower()
                if value not in {"yes", "no"}:
                    return {"ok": False, "error": {"code": "invalid_enabled_value"}}
                changes = {"enabled": value == "yes"}
            else:
                return {"ok": False, "error": {"code": "invalid_update_field"}}
            args = {"action": action, "job_id": job_id, "changes": changes}
    preview = _call("cron.jobs.mutation.preview", args)
    if not preview.get("ok"):
        return preview
    plan = preview.get("data", {}).get("plan", {})
    plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
    if not isinstance(plan_id, str):
        return {"ok": False, "error": {"code": "invalid_cron_preview"}}
    _show_details(screen, preview)
    if _prompt(screen, f"Apply this exact saved Cron plan {plan_id}? type yes").lower() != "yes":
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("cron.jobs.mutation.apply", {"plan_id": plan_id, "confirmed": True})


def _cron_executions() -> dict[str, object]:
    """Read bounded Cron execution history via the shared management service."""
    return _call("cron.executions.list", {"limit": 20})


def _cron_inspect(screen: "curses._CursesWindow", *, executions: bool = False) -> dict[str, object]:
    """Choose a saved Cron item and inspect it through the shared service."""
    if executions:
        listing = _cron_executions()
        entries = listing.get("data", {}).get("executions", []) if listing.get("ok") else []
        id_field, operation, label = "execution_id", "cron.executions.show", "execution"
    else:
        listing = _cron_jobs()
        entries = listing.get("data", {}).get("jobs", []) if listing.get("ok") else []
        id_field, operation, label = "job_id", "cron.jobs.show", "job"
    if not listing.get("ok"):
        return listing
    choices = [(str(item.get(id_field)), f"{item.get('name', item.get('status', 'Cron item'))} · {item.get(id_field)}")
               for item in entries if isinstance(item, dict) and isinstance(item.get(id_field), str)]
    if not choices:
        return {"ok": False, "error": {"code": "no_cron_executions" if executions else "no_cron_jobs"}}
    selected = _choose(screen, f"Select a Cron {label} to inspect", choices)
    if not selected:
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call(operation, {id_field: selected})


def _cron_next_runs(screen: "curses._CursesWindow") -> dict[str, object]:
    listing = _cron_jobs()
    if not listing.get("ok"):
        return listing
    jobs = listing.get("data", {}).get("jobs", [])
    choices = [(str(item.get("job_id")), f"{item.get('name', 'Cron job')} · {item.get('job_id')}")
               for item in jobs if isinstance(item, dict) and isinstance(item.get("job_id"), str)]
    if not choices:
        return {"ok": False, "error": {"code": "no_cron_jobs"}}
    selected = _choose(screen, "Select a Cron job to preview upcoming runs", choices)
    if not selected:
        return {"ok": False, "error": {"code": "cancelled"}}
    return _call("cron.jobs.next_runs", {"job_id": selected, "count": 5})


def _recovery_action(screen: "curses._CursesWindow") -> dict[str, object]:
    """Guide read-only backup, recovery and continuity inspection."""
    choice = _choose(screen, "Native backup & recovery", [
        ("status", "View operation history and unresolved count"),
        ("backups", "List verified configuration backups"),
        ("backup", "Inspect a backup"), ("create", "Create configuration backup"),
        ("restore", "Preview a restore"), ("apply-restore", "Restore from a backup"),
        ("operation", "Inspect a recovery operation"), ("rollback", "Preview restore rollback"),
        ("apply-rollback", "Apply restore rollback"), ("resolve", "Reconcile unresolved operation"),
        ("continuity", "Check reboot-continuity status"),
        ("checkpoint-prepare", "Prepare a continuity checkpoint"),
        ("checkpoint-verify", "Verify a saved checkpoint"),
        ("reboot-test-prepare", "Prepare a detailed reboot qualification"),
        ("reboot-test-verify", "Verify a reboot qualification"),
    ])
    if choice == "status":
        return _call("recovery.status")
    if choice == "backups":
        return _call("backup.list")
    if choice == "continuity":
        return _call("continuity.status")
    if choice == "checkpoint-prepare":
        test_id = _prompt(screen, "Checkpoint test ID (letters, numbers, dot, underscore, colon, hyphen)")
        if not test_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        args = {"test_id": test_id}
        preview = _call("continuity.prepare.preview", args)
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str):
            return {"ok": False, "error": {"code": "invalid_continuity_preview"}}
        _show_details(screen, preview)
        if _prompt(screen, "Type CREATE CHECKPOINT to write this private record").strip() != "CREATE CHECKPOINT":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("continuity.prepare", {**args, "confirmed": True, "plan_id": plan_id})
    if choice == "checkpoint-verify":
        checkpoint_id = _prompt(screen, "Paste the 32-character checkpoint ID")
        if not checkpoint_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        args = {"checkpoint_id": checkpoint_id}
        preview = _call("continuity.verify.preview", args)
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str):
            return {"ok": False, "error": {"code": "invalid_continuity_preview"}}
        _show_details(screen, preview)
        if _prompt(screen, "Type VERIFY CHECKPOINT to record this observation").strip() != "VERIFY CHECKPOINT":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("continuity.verify", {**args, "confirmed": True, "plan_id": plan_id})
    if choice == "reboot-test-prepare":
        test_id = _prompt(screen, "Unique reboot-test ID (letters, numbers, dot, underscore, colon, hyphen)")
        if not test_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        args = {"test_id": test_id.strip()}
        preview = _call("continuity.prepare-reboot-test.preview", args)
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str):
            return {"ok": False, "error": {"code": "invalid_reboot_test_preview"}}
        _show_details(screen, preview)
        if _prompt(screen, "Type CREATE REBOOT TEST RECORD to write this private NOT_READY record").strip() != "CREATE REBOOT TEST RECORD":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("continuity.prepare-reboot-test", {**args, "confirmed": True, "plan_id": plan_id})
    if choice == "reboot-test-verify":
        test_id = _prompt(screen, "Reboot-test ID to verify")
        if not test_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        args = {"test_id": test_id.strip()}
        preview = _call("continuity.verify-reboot-test.preview", args)
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str):
            return {"ok": False, "error": {"code": "invalid_reboot_test_preview"}}
        _show_details(screen, preview)
        if _prompt(screen, "Type VERIFY REBOOT TEST to record this evidence-only check").strip() != "VERIFY REBOOT TEST":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("continuity.verify-reboot-test", {**args, "confirmed": True, "plan_id": plan_id})
    if choice == "create":
        name = _prompt(screen, "Backup name (letters, numbers, dot, dash, underscore; max 64)")
        if not name:
            return {"ok": False, "error": {"code": "cancelled"}}
        preview = _call("backup.create", {"name": name})
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str):
            return {"ok": False, "error": {"code": "invalid_backup_preview"}}
        _show_details(screen, preview)
        if _prompt(screen, "Type CREATE to save this exact backup plan").strip() != "CREATE":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("backup.create", {"name": name, "confirmed": True, "plan_id": plan_id})
    if choice in {"backup", "restore", "apply-restore"}:
        listed = _call("backup.list")
        if not listed.get("ok"):
            return listed
        rows = listed.get("data", {}).get("backups", [])
        choices = [(str(item.get("backup_id")), f"{item.get('backup_id')} · {item.get('integrity', 'unknown')} · {item.get('created_at_utc', '')}")
                   for item in rows if isinstance(item, dict) and isinstance(item.get("backup_id"), str)]
        if not choices:
            return {"ok": False, "error": {"code": "no_backups"}}
        backup_id = _choose(screen, "Select a backup", choices)
        if not backup_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        if choice == "backup":
            return _call("backup.inspect", {"backup_id": backup_id})
        preview = _call("restore.preview", {"backup_id": backup_id})
        if not preview.get("ok") or choice == "restore":
            return preview
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str):
            return {"ok": False, "error": {"code": "invalid_restore_preview"}}
        _show_details(screen, preview)
        if _prompt(screen, "Type RESTORE to apply this exact profile restore").strip() != "RESTORE":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("restore.apply", {"backup_id": backup_id, "confirmed": True, "plan_id": plan_id})
    if choice in {"operation", "rollback", "apply-rollback", "resolve"}:
        status = _call("recovery.status")
        if not status.get("ok"):
            return status
        records = status.get("data", {}).get("operations", [])
        candidates = [item for item in records if isinstance(item, dict)
                      and isinstance(item.get("operation_id"), str)
                      and (choice != "resolve" or item.get("status") in {"starting", "stopping", "needs_recovery"})]
        choices = [(str(item.get("operation_id")), f"{item.get('kind')} · {item.get('status')} · {item.get('operation_id')}")
                   for item in candidates]
        if not choices:
            return {"ok": False, "error": {"code": "no_recovery_operations"}}
        operation_id = _choose(screen, "Select a recovery operation", choices)
        if not operation_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        if choice == "operation":
            return _call("recovery.inspect", {"operation_id": operation_id})
        if choice == "rollback":
            return _call("recovery.rollback.preview", {"operation_id": operation_id})
        operation = "recovery.resolve" if choice == "resolve" else "recovery.rollback.apply"
        preview = _call(operation, {"operation_id": operation_id})
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str):
            return {"ok": False, "error": {"code": "invalid_recovery_preview"}}
        _show_details(screen, preview)
        confirmation = "RESOLVE" if choice == "resolve" else "ROLLBACK"
        if _prompt(screen, f"Type {confirmation} to apply this exact recovery plan").strip() != confirmation:
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call(operation, {"operation_id": operation_id, "confirmed": True, "plan_id": plan_id})
    return {"ok": False, "error": {"code": "cancelled"}}


def _operation_history(resource: dict[str, Any]) -> dict[str, object]:
    if resource.get("id") != "recovery.native-state" or "recovery.status" not in resource.get("supported_operations", []):
        return {"ok": False, "error": {"code": "history_unavailable"}}
    return _call("recovery.status")


def _selected_status_operation(resource: dict[str, Any]) -> str | None:
    for operation in resource.get("supported_operations", []):
        if operation in READ_WITHOUT_ARGUMENTS and operation != "management.catalog":
            return operation
    return None


def _manage_replay_guest(screen: "curses._CursesWindow") -> dict[str, object]:
    """Retire or restore only a receipt-verified replay guest through exact plans."""
    action = _choose(screen, "Ternuxx replay guest", [
        ("retire", "Retire an idle replay guest (keep exact backup)"),
        ("restore", "Restore a retired replay guest"),
    ])
    if action not in {"retire", "restore"}:
        return {"ok": False, "error": {"code": "cancelled"}}
    alias = _prompt(screen, "Exact alias (ternuxx-replay-NAME)").strip()
    if not re.fullmatch(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", alias):
        return {"ok": False, "error": {"code": "invalid_replay_alias"}}
    backup_id = ""
    if action == "retire":
        preview = _call("proot.setup.retire.preview", {"alias": alias})
    else:
        backup_id = _prompt(screen, "Backup ID (32 lowercase hex characters)", 32).strip()
        if not re.fullmatch(r"[0-9a-f]{32}", backup_id):
            return {"ok": False, "error": {"code": "invalid_backup_id"}}
        preview = _call("proot.setup.restore.preview", {"alias": alias, "backup_id": backup_id})
    if not preview.get("ok"):
        return preview
    data = preview.get("data", {})
    plan_id = data.get("plan_id") if isinstance(data, dict) else None
    operation = data.get("operation", {}) if isinstance(data, dict) else {}
    if (not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id)
            or not isinstance(operation, dict) or operation.get("alias") != alias
            or operation.get("confirmation_required") is not True
            or (action == "restore" and operation.get("backup_id") != backup_id)):
        return {"ok": False, "error": {"code": "invalid_guest_lifecycle_preview"}}
    _show_details(screen, preview)
    verb = "RETIRE" if action == "retire" else "RESTORE"
    if _prompt(screen, f"Apply this exact replay guest plan? Type {verb}").strip() != verb:
        return {"ok": False, "error": {"code": "cancelled"}}
    if action == "retire":
        return _call("proot.setup.retire.apply", {"alias": alias, "confirmed": True, "plan_id": plan_id})
    return _call("proot.setup.restore.apply", {"alias": alias, "backup_id": backup_id,
        "confirmed": True, "plan_id": plan_id})



def _proot_workload_action(screen: "curses._CursesWindow", resource: dict[str, Any]) -> dict[str, object]:
    operations = set(resource.get("supported_operations", []))
    choices = [("status", "Check installed Debian and host PRoot processes"),
               ("profiles", "List bounded guest session profiles"),
               ("sessions", "Inspect owned guest sessions"),
               ("probe", "Start bounded headless Debian probe"),
               ("login", "Read interactive Debian login instructions")]
    choices.append(("install", "Install an optional managed Debian or Ubuntu guest"))
    if "proot.shortcuts.list" in operations:
        choices.append(("apps", "Browse and launch an allowlisted Debian app"))
    if {"proot.shortcuts.list", "proot.shortcuts.preview", "proot.shortcuts.apply"} <= operations:
        choices.append(("shortcuts", "Preview and manage Debian app shortcuts"))
    if {"proot.shortcuts.sync.preview", "proot.shortcuts.sync.apply"} <= operations:
        choices.append(("shortcut-sync", "Synchronize Debian app and desktop shortcuts"))
    if {"proot.shortcuts.sync.rollback.list", "proot.shortcuts.sync.rollback.preview",
        "proot.shortcuts.sync.rollback.apply"} <= operations:
        choices.append(("shortcut-rollback", "Review or restore a shortcut sync"))
    if {"proot.stop.preview", "proot.stop"} <= operations:
        choices.append(("stop", "Preview and stop a verified managed guest session"))
    if {"proot.recovery.inspect", "proot.recovery.reconcile.preview", "proot.recovery.reconcile"} <= operations:
        choices.append(("reconcile", "Inspect or reconcile an exited guest session record"))
    action = _choose(screen, "Debian PRoot workloads", choices)
    if action == "status":
        return _call("proot.status")
    if action == "profiles":
        return _call("proot.profiles.list")
    if action == "sessions":
        return _call("proot.sessions.list")
    if action == "install":
        prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        executable = Path(prefix) / "bin" / "tx"
        if prefix != "/data/data/com.termux/files/usr" or not executable.is_file():
            return {"ok": False, "error": {"code": "native_tx_unavailable",
                    "message": "The fixed Native Termux tx command is unavailable."}}
        distro = _choose(screen, "Choose a managed guest distro", [
            ("debian", "Debian Trixie"), ("ubuntu", "Ubuntu Noble")])
        profile = "debian-trixie" if distro == "debian" else "ubuntu-noble"
        available = proot_desktops.catalog(profile)
        selection = _prompt(screen, f"{distro.title()} desktop IDs ({', '.join(available)}; default xfce): ").strip()
        desktops = [item.strip() for item in selection.split(",") if item.strip()] if selection else ["xfce"]
        try:
            validated = proot_desktops.validate_selection(profile, desktops)
        except ValueError as exc:
            return {"ok": False, "error": {"code": "invalid_desktop_selection", "message": str(exc)}}
        if any(item not in available for item in desktops):
            return {"ok": False, "error": {"code": "invalid_desktop_selection",
                    "message": f"Choose from the listed {distro.title()} desktop IDs."}}
        screen.erase(); screen.refresh()
        curses.def_prog_mode(); curses.endwin()
        try:
            result = subprocess.run([str(executable), "install", distro, "--desktops", ",".join(validated)], check=False)
        except OSError as exc:
            return {"ok": False, "error": {"code": "guest_install_launch_failed", "message": str(exc)}}
        finally:
            curses.reset_prog_mode(); screen.clear(); screen.refresh()
        label = "Debian" if distro == "debian" else "Ubuntu"
        return {"ok": result.returncode == 0,
                "data": {"guest_status": "setup_finished" if result.returncode == 0 else "setup_failed",
                         "exit_code": result.returncode,
                         "message": f"The guided {label} installer finished; existing guests remain preserved."}}
    if action == "login":
        status = _call("proot.status")
        if not status.get("ok"):
            return status
        installed = "debian" in status.get("data", {}).get("installed_distributions", [])
        if installed:
            return {"ok": True, "data": {"guest_status": "installed",
                "next_step": "Debian is installed. Exit TUI and run `tx db` in an attached Native Termux terminal."}}
        return {"ok": True, "data": {"guest_status": "missing",
            "next_step": "Choose Install an optional managed Debian or Ubuntu guest, select its supported desktop environments, and start the guided installer here. It asks for the guest username, shows the pinned target, and asks before installing Ternuxx graphics/audio configuration. Existing guests are preserved."}}
    if action == "stop" and {"proot.stop.preview", "proot.stop"} <= operations:
        inventory = _call("proot.sessions.list")
        if not inventory.get("ok"):
            return inventory
        sessions = inventory.get("data", {}).get("sessions", [])
        running = [item for item in sessions if isinstance(item, dict)
                   and item.get("ownership") == "ternuxx_verified" and item.get("state") == "running"
                   and isinstance(item.get("session_id"), str)]
        if not running:
            return {"ok": True, "data": {"sessions": [],
                "message": "No verified running Ternuxx guest session is available to stop."}}
        session_id = _choose(screen, "Choose a verified running guest session", [
            (item["session_id"], f"{item.get('profile', 'guest')} · {item['session_id']}")
            for item in running])
        if not session_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        preview = _call("proot.stop.preview", {"session_id": session_id})
        if not preview.get("ok"):
            return preview
        _show_details(screen, preview)
        plan_id = preview.get("data", {}).get("plan_id")
        if not isinstance(plan_id, str):
            return {"ok": False, "error": {"code": "invalid_stop_preview"}}
        if _prompt(screen, "Review this exact session plan, then type STOP to end only this managed session").strip() != "STOP":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("proot.stop", {"session_id": session_id, "confirmed": True, "plan_id": plan_id})
    if action == "reconcile" and {"proot.recovery.inspect", "proot.recovery.reconcile.preview",
                                    "proot.recovery.reconcile"} <= operations:
        inventory = _call("proot.sessions.list")
        if not inventory.get("ok"):
            return inventory
        sessions = inventory.get("data", {}).get("sessions", [])
        candidates = [item for item in sessions if isinstance(item, dict)
                      and item.get("state") != "stopped" and isinstance(item.get("session_id"), str)]
        if not candidates:
            return {"ok": True, "data": {"sessions": [],
                "message": "No unfinished Ternuxx guest session record needs inspection."}}
        session_id = _choose(screen, "Inspect an unfinished guest session", [
            (item["session_id"], f"{item.get('profile', 'guest')} · {item.get('state', 'unknown')} · {item['session_id']}")
            for item in candidates])
        if not session_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        inspection = _call("proot.recovery.inspect", {"session_id": session_id})
        if not inspection.get("ok"):
            return inspection
        _show_details(screen, inspection)
        preview = _call("proot.recovery.reconcile.preview", {"session_id": session_id})
        if not preview.get("ok"):
            return preview
        _show_details(screen, preview)
        plan_id = preview.get("data", {}).get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"plan-[0-9a-f]{64}", plan_id):
            return preview
        if _prompt(screen, "This plan only updates the record after process exit is proven. Type RECONCILE").strip() != "RECONCILE":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("proot.recovery.reconcile", {"session_id": session_id,
            "confirmed": True, "plan_id": plan_id})
    if action == "probe" and {"proot.start.preview", "proot.start"} <= operations:
        preview = _call("proot.start.preview", {"profile": "isolated-probe"})
        if not preview.get("ok"):
            return preview
        plan = preview.get("data", {})
        _show_details(screen, preview)
        if _prompt(screen, "Start this bounded headless Debian probe? type RUN").strip() != "RUN":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("proot.start", {"profile": "isolated-probe", "confirmed": True,
                                     "plan_id": plan.get("plan_id"), "timeout_seconds": 300})
    if action == "apps":
        inventory = _call("proot.shortcuts.list")
        if not inventory.get("ok"):
            return inventory
        items = inventory.get("data", {}).get("items", [])
        choices = [(item["id"], item["name"]) for item in items
                   if isinstance(item, dict) and item.get("id") and item.get("application_availability") != "unavailable"]
        app_id = _choose(screen, "Allowlisted Debian apps", choices)
        if not app_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("proot.app.launch", {"app_id": app_id})
    if action == "shortcuts":
        inventory = _call("proot.shortcuts.list")
        if not inventory.get("ok"):
            return inventory
        items = inventory.get("data", {}).get("items", [])
        if not isinstance(items, list):
            return {"ok": False, "error": {"code": "invalid_shortcut_inventory"}}
        choices = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            state = item.get("shortcut_state")
            if state == "absent":
                choices.append((item["id"], f"Add · {item.get('name', item['id'])}"))
            elif state == "installed":
                choices.append((item["id"], f"Remove · {item.get('name', item['id'])}"))
        if not choices:
            return {"ok": True, "data": {"message": "No safe add/remove shortcut changes are available."}}
        app_id = _choose(screen, "Choose an absent or managed Debian shortcut", choices)
        if not app_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        selected = next((item for item in items if isinstance(item, dict) and item.get("id") == app_id), None)
        if not selected:
            return {"ok": False, "error": {"code": "invalid_shortcut_selection"}}
        action_name = "add" if selected.get("shortcut_state") == "absent" else "remove"
        preview = _call("proot.shortcuts.preview", {"action": action_name, "app_id": app_id})
        if not preview.get("ok"):
            return preview
        _show_details(screen, preview)
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str) or plan.get("changed") is not True:
            return preview
        token = "ADD SHORTCUT" if action_name == "add" else "REMOVE SHORTCUT"
        if _prompt(screen, f"Type {token} to apply this exact Native launcher change").strip() != token:
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("proot.shortcuts.apply", {"action": action_name, "app_id": app_id,
            "confirmed": True, "plan_id": plan_id})
    if action == "shortcut-sync":
        preview = _call("proot.shortcuts.sync.preview")
        if not preview.get("ok"):
            return preview
        _show_details(screen, preview)
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str) or plan.get("changed") is not True:
            return preview
        if _prompt(screen, "Review all listed launcher changes. Type SYNC SHORTCUTS to apply this exact plan").strip() != "SYNC SHORTCUTS":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("proot.shortcuts.sync.apply", {"confirmed": True, "plan_id": plan_id})
    if action == "shortcut-rollback":
        inventory = _call("proot.shortcuts.sync.rollback.list")
        if not inventory.get("ok"):
            return inventory
        entries = inventory.get("data", {}).get("rollbacks", [])
        candidates = [item for item in entries if isinstance(item, dict)
                      and item.get("integrity") == "valid" and item.get("status") == "applied"
                      and isinstance(item.get("rollback_id"), str)]
        if not candidates:
            return {"ok": True, "data": {"message": "No valid applied shortcut sync can be restored."}}
        rollback_id = _choose(screen, "Choose a valid applied shortcut sync", [
            (item["rollback_id"], f"{item.get('created_at', 'unknown time')} · {item.get('entry_count', 0)} launchers · {item['rollback_id']}")
            for item in candidates])
        if not rollback_id:
            return {"ok": False, "error": {"code": "cancelled"}}
        preview = _call("proot.shortcuts.sync.rollback.preview", {"rollback_id": rollback_id})
        if not preview.get("ok"):
            return preview
        _show_details(screen, preview)
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id") if isinstance(plan, dict) else None
        if not isinstance(plan_id, str) or plan.get("requires_confirmation") is not True:
            return preview
        if _prompt(screen, "Review these exact restore changes. Type ROLLBACK SHORTCUTS").strip() != "ROLLBACK SHORTCUTS":
            return {"ok": False, "error": {"code": "cancelled"}}
        return _call("proot.shortcuts.sync.rollback.apply", {"rollback_id": rollback_id,
            "confirmed": True, "plan_id": plan_id})
    return {"ok": False, "error": {"code": "cancelled"}}


def _terminal_broker_action(screen: "curses._CursesWindow", resource: dict[str, Any]) -> dict[str, object]:
    operations = set(resource.get("supported_operations", []))
    choices = []
    if "terminal.broker.service.status" in operations:
        choices.append(("status", "Check broker service and live broker status"))
    if {"terminal.broker.service.install.preview", "terminal.broker.service.install.apply",
        "terminal.broker.service.start.preview", "terminal.broker.service.start.apply"} <= operations:
        choices.append(("service", "Preview and confirm broker service setup/start"))
    if {"terminal.start.preview", "terminal.start"} <= operations:
        choices.append(("open", "Open fixed interactive Debian terminal"))
    action = _choose(screen, "Optional Debian terminal", choices)
    if action == "status":
        service = _call("terminal.broker.service.status")
        broker = _call("terminal.broker.status")
        return {"ok": service.get("ok", False) and broker.get("ok", False),
                "data": {"service": service.get("data", service.get("error")),
                         "broker": broker.get("data", broker.get("error"))}}
    if action == "service":
        state = _call("terminal.broker.service.status")
        if not state.get("ok"):
            return state
        current = state.get("data", {})
        if current.get("installed") is True and current.get("status") == "running":
            return _call("terminal.broker.status")
        start = current.get("installed") is True
        kind = "start" if start else "install"
        operation = "terminal.broker.service.start.preview" if start else "terminal.broker.service.install.preview"
        preview = _call(operation)
        if not preview.get("ok"):
            return preview
        _show_details(screen, preview)
        token = "START" if start else "INSTALL"
        if _prompt(screen, f"Type {token} to apply this exact broker service plan").strip() != token:
            return {"ok": False, "error": {"code": "cancelled"}}
        operation = "terminal.broker.service.start.apply" if start else "terminal.broker.service.install.apply"
        applied = _call(operation, {"confirmed": True, "plan_id": preview.get("data", {}).get("plan_id")})
        if applied.get("ok"):
            _call("terminal.broker.status")
        return applied
    if action == "open":
        prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        executable = Path(prefix) / "bin" / "tx"
        if prefix != "/data/data/com.termux/files/usr" or not executable.is_file():
            return {"ok": False, "error": {"code": "native_tx_unavailable",
                    "message": "The fixed Native Termux tx command is unavailable."}}
        screen.erase(); screen.refresh()
        curses.def_prog_mode(); curses.endwin()
        try:
            result = subprocess.run([str(executable), "terminal", "start"], check=False)
        except OSError as exc:
            return {"ok": False, "error": {"code": "terminal_launch_failed", "message": str(exc)}}
        finally:
            curses.reset_prog_mode(); screen.clear(); screen.refresh()
        return {"ok": result.returncode == 0, "data": {"exit_code": result.returncode,
                "guest_stopped": False, "message": "Terminal detached; the guest session remains running."}}
    return {"ok": False, "error": {"code": "cancelled"}}


def _run(screen: "curses._CursesWindow") -> int:
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        palette = (
            (1, curses.COLOR_GREEN), (2, curses.COLOR_CYAN), (3, curses.COLOR_YELLOW),
            (4, curses.COLOR_BLUE), (5, curses.COLOR_WHITE), (6, curses.COLOR_RED),
        )
        for pair, color in palette:
            try:
                curses.init_pair(pair, color, -1)
            except curses.error:
                pass
    catalog_result = _call("management.catalog")
    if not catalog_result.get("ok"):
        raise RuntimeError("Could not load the shared resource catalog")
    catalog = catalog_result["data"]
    categories: list[dict[str, Any]] = list(catalog["categories"])
    all_resources: list[dict[str, Any]] = sorted(catalog["resources"], key=lambda item: (item["category_id"], item["name"].casefold()))
    category_index = selected = scroll = 0
    query = ""
    report: dict[str, object] | None = None

    while True:
        category = categories[category_index]
        resources = [r for r in all_resources if r["category_id"] == category["id"]
                     and (not query or query.casefold() in (r["name"] + " " + r["description"]).casefold())]
        if resources:
            selected = min(selected, len(resources) - 1)
        else:
            selected = scroll = 0
        scroll = _draw(screen, categories, category_index, resources, selected, query, report, scroll)
        key = screen.getch()
        if key in (ord("q"), ord("Q"), 27):
            return 0
        if key == curses.KEY_RESIZE:
            try:
                curses.update_lines_cols()
                screen.clearok(True)
            except curses.error:
                pass
        elif key in (curses.KEY_LEFT, ord("h")):
            category_index = (category_index - 1) % len(categories)
            selected = scroll = 0
        elif key in (curses.KEY_RIGHT, ord("l")):
            category_index = (category_index + 1) % len(categories)
            selected = scroll = 0
        elif key in (curses.KEY_DOWN, ord("j")) and resources:
            selected = min(len(resources) - 1, selected + 1)
            if selected >= scroll + max(1, screen.getmaxyx()[0] - 7):
                scroll += 1
        elif key in (curses.KEY_UP, ord("k")) and resources:
            selected = max(0, selected - 1)
            scroll = min(scroll, selected)
        elif key in (curses.KEY_NPAGE, ord("}")) and resources:
            page_size = max(1, screen.getmaxyx()[0] - 9)
            selected = min(len(resources) - 1, selected + page_size)
            scroll = min(max(0, selected - page_size + 1), max(0, len(resources) - 1))
        elif key in (curses.KEY_PPAGE, ord("{")) and resources:
            page_size = max(1, screen.getmaxyx()[0] - 9)
            selected = max(0, selected - page_size)
            scroll = max(0, min(scroll, selected))
        elif ord("0") <= key <= ord("9") and resources:
            target = 9 if key == ord("0") else key - ord("1")
            if target < len(resources):
                selected = target
                scroll = max(0, min(scroll, selected))
        elif key in (ord("/"),):
            query = _prompt(screen, "Search resources (blank clears)")[:120]
            selected = scroll = 0
        elif key in (curses.KEY_ENTER, 10, 13) and resources:
            resource = resources[selected]
            operation = _selected_status_operation(resource)
            if operation:
                report = _call(operation)
            else:
                report = {"ok": False, "error": {"code": "live_status_unavailable"}}
        elif key in (ord("h"), ord("H")) and resources:
            resource = resources[selected]
            if resource.get("id") == "recovery.native-state":
                report = _operation_history(resource)
            elif resource.get("id") == "automation.cron-registry" and "cron.executions.list" in resource.get("supported_operations", []):
                report = _cron_executions()
        elif key in (ord("v"), ord("V")):
            _show_details(screen, report)
        elif key in (ord("r"), ord("R")):
            report = _call("management.catalog")
            if report.get("ok"):
                catalog = report["data"]
                categories = list(catalog["categories"])
                all_resources = sorted(catalog["resources"], key=lambda item: (item["category_id"], item["name"].casefold()))
                category_index = min(category_index, len(categories) - 1)
        elif key in (ord("a"), ord("A")) and resources:
            resource = resources[selected]
            if resource["id"] == "graphics.native":
                action = _choose(screen, "Native graphics verification", [
                    ("status", "Check provider status"), ("opengl", "Verify OpenGL"),
                    ("gles", "Verify OpenGL ES"), ("vulkan", "Verify Vulkan"),
                    ("select", "Select backend (KGSL experimental)"),
                ]).lower()
                if action == "status":
                    report = _call("graphics.provider.status", {"provider": "native"})
                elif action == "select":
                    backend = _prompt(screen, "Choose: termux-zink, experimental KGSL (files already present), or system")
                    if backend not in {"termux-zink", "kgsl-freedreno", "system"}:
                        report = {"ok": False, "error": {"code": "invalid_backend"}}
                    elif _prompt(screen, f"Save {backend} for future starts? termux-zink requires the graphical profile Freedreno ICD; KGSL is experimental and must already be extracted; this does not change the running desktop. type yes").lower() == "yes":
                        report = _call("graphics.provider.select", {"provider": "native", "backend": backend, "confirmed": True})
                    else:
                        report = {"ok": False, "error": {"code": "cancelled"}}
                elif action in {"opengl", "gles", "vulkan"}:
                    report = _call("graphics.provider.verify", {"provider": "native", "api": action})
                else:
                    report = {"ok": False, "error": {"code": "cancelled"}}
            elif resource["id"] == "software.curated-apps":
                report = _software_action(screen, resource)
            elif resource["id"] == "inference.gpu.local":
                report = _gpu_inference_action(screen, resource)
            elif resource["id"] == "inference.npu.local":
                report = _npu_inference_action(screen, resource)
            elif resource["id"] == "inference.cpu.local":
                action = _choose(screen, "Native CPU inference", [
                    ("status", "Check runtime and model status"),
                    ("install", "Preview or install pinned model"),
                    ("remove", "Preview model removal"),
                    ("run", "Run a bounded CPU prompt"),
                ])
                if action == "status":
                    report = _call("inference.cpu.status")
                elif action in {"install", "remove"}:
                    model_action = action
                    report = _call("inference.cpu.model.preview", {"action": model_action})
                    if report.get("ok"):
                        _show_details(screen, report)
                        token = "DOWNLOAD" if action == "install" else "REMOVE"
                        if _prompt(screen, f"Type {token} to apply this exact model plan").strip() == token:
                            report = _call("inference.cpu.model.apply", {
                                "action": model_action, "plan_id": report["data"]["plan_id"],
                                "confirmed": True})
                        else:
                            report = {"ok": False, "error": {"code": "cancelled"}}
                elif action == "run":
                    prompt = _prompt(screen, "One-line local prompt (max 4096 UTF-8 bytes)")
                    if prompt:
                        _show_details(screen, {"ok": True, "data": {
                            "backend": "CPU", "model_id": "qwen3-0.6b-q4_0",
                            "max_output_tokens": 64, "resource_limit": "4 CPU threads, 512-token context"}})
                        if _prompt(screen, "Run this prompt locally? type RUN").strip() == "RUN":
                            report = _call("inference.cpu.run", {"prompt": prompt, "max_tokens": 64})
                        else:
                            report = {"ok": False, "error": {"code": "cancelled"}}
                    else:
                        report = {"ok": False, "error": {"code": "cancelled"}}
                else:
                    report = {"ok": False, "error": {"code": "cancelled"}}
            elif resource["id"] == "proot.debian.workloads":
                report = _proot_workload_action(screen, resource)
            elif resource["id"] == "proot.replay-guests":
                report = _manage_replay_guest(screen)
            elif resource["id"] == "proot.interactive-terminal-broker":
                report = _terminal_broker_action(screen, resource)
            elif resource["id"] == "native.gui.activity-monitor":
                report = _edit_monitor_policy(screen)
            elif resource["id"] == "native.system.health":
                report = _manage_logs(screen)
            elif resource["id"] == "native.desktop.session":
                report = _desktop_action(screen, resource)
            elif resource["id"] == "network.ssh.managed-8023":
                report = _managed_ssh_action(screen, resource)
            elif resource["id"] == "native.timezone":
                report = _timezone_action(screen)
            elif resource["id"] == "automation.cron-registry":
                choice = _choose(screen, "Cron automation", [("status", "Check scheduler status"),
                    ("service", "Start or stop scheduler"), ("jobs", "List saved jobs"),
                    ("change", "Create, edit, or remove a job"), ("inspect", "Inspect a saved job"),
                    ("next", "Preview upcoming runs"), ("history", "View recent runs"),
                    ("execution", "Inspect an execution record")]).lower()
                report = (_call("cron.status") if choice == "status" else
                          _cron_jobs() if choice == "jobs" else
                          _cron_mutation(screen) if choice == "change" else
                          _cron_executions() if choice == "history" else
                          _cron_inspect(screen) if choice == "inspect" else
                          _cron_next_runs(screen) if choice == "next" else
                          _cron_inspect(screen, executions=True) if choice == "execution" else
                          _cron_scheduler_action(screen) if choice == "service" else
                          {"ok": False, "error": {"code": "cancelled"}})
            elif resource["id"] == "boot.termux.profile":
                report = _boot_action(screen)
            elif resource["id"] == "boot.termux.cron":
                report = _boot_cron_action(screen)
            elif resource["id"] == "native.wakelock":
                report = _wakelock_action(screen)
            elif resource["id"] == "recovery.native-state":
                report = _recovery_action(screen)
            else:
                report = {"ok": False, "error": {"code": "guided_action_unavailable"}}


def main() -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("tx tui needs an interactive terminal.", file=sys.stderr)
        return 2
    try:
        return curses.wrapper(_run)
    except (curses.error, RuntimeError) as exc:
        print(f"tx tui could not start: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
