#!/data/data/com.termux/files/usr/bin/python
"""Typed local bridge for the GTK management client; delegates to the shared core."""
from __future__ import annotations

import json
import re
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import management_service  # noqa: E402
import management_sessions  # noqa: E402
import management_presentation  # noqa: E402


def call(operation: str, args: dict[str, object] | None = None) -> dict[str, object]:
    return management_service.dispatch({
        "api_version": management_service.API_VERSION,
        "request_id": uuid.uuid4().hex,
        "operation": operation,
        "args": args or {},
    }, caller="local_cli", env=dict(os.environ))


def clean(value: object) -> str:
    return str(value if value is not None else "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def main(argv: list[str]) -> int:
    if not os.environ.get("TERMUX_VERSION") or os.environ.get("PREFIX") != "/data/data/com.termux/files/usr":
        print("Native Termux is required.", file=sys.stderr)
        return 2
    os.environ.setdefault("TERNUXX_STATE_DIR", str(Path.home() / ".local/share/ternuxx"))
    if not argv:
        print("Typed management action required.", file=sys.stderr)
        return 2
    action = argv[0]
    if action == "terminal-service-status" and len(argv) == 1:
        service = call("terminal.broker.service.status")
        broker = call("terminal.broker.status")
        result = {"ok": service.get("ok") is True and broker.get("ok") is True,
                  "data": {**(service.get("data", {}) if isinstance(service.get("data"), dict) else {}),
                           "broker": broker.get("data", broker.get("error"))}}
        print(management_presentation.format_report(result))
        return 0 if result["ok"] else 1
    if action == "terminal-service-prepare" and len(argv) == 1:
        status = call("terminal.broker.service.status")
        if not status.get("ok"):
            print(management_presentation.format_report(status)); return 1
        current = status.get("data", {})
        if current.get("installed") is True and current.get("status") == "running":
            print("R\tTerminal broker is already running; no change was made.")
            return 0
        if current.get("installed") is True:
            operation = "terminal.broker.service.start.preview"
            action_name = "start"
        else:
            operation = "terminal.broker.service.install.preview"
            action_name = "install"
        preview = call(operation)
        if not preview.get("ok"):
            print(management_presentation.format_report(preview)); return 1
        plan = preview.get("data", {})
        plan_id = plan.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Terminal broker preview did not return an exact plan ID.", file=sys.stderr); return 1
        impact = clean(plan.get("impact") or "Changes only the fixed Ternuxx terminal broker service.")
        print("P\t" + plan_id + "\t" + action_name + "\t" + impact)
        return 0
    if action == "terminal-service-apply" and len(argv) == 4 and argv[1] == "confirmed" and argv[2] in {"install", "start"}:
        plan_id = argv[3]
        if not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("The terminal broker preview is invalid; create a fresh preview.", file=sys.stderr); return 2
        operation = "terminal.broker.service.install.apply" if argv[2] == "install" else "terminal.broker.service.start.apply"
        result = call(operation, {"confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "software-run" and len(argv) == 2:
        result = call("software.app.run", {"app_id": "directory-tree", "path": argv[1]})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "software-preview" and len(argv) == 3 and argv[1] in {"process-monitor", "terminal-multiplexer", "directory-tree"} and argv[2] in {"install", "update", "remove"}:
        result = call("software.app.preview", {"app_id": argv[1], "action": argv[2]})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Native app preview returned an invalid plan."); return 1
        print("P\t" + plan_id + "\t" + argv[1] + "\t" + argv[2] + "\t" + clean(json.dumps(data, sort_keys=True)))
        return 0
    if action == "software-apply" and len(argv) == 5 and argv[1] in {"process-monitor", "terminal-multiplexer", "directory-tree"} and argv[2] in {"install", "update", "remove"}:
        plan_id = argv[3]
        if not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Native app preview expired; create a new preview."); return 2
        result = call("software.app.apply", {"app_id": argv[1], "action": argv[2], "plan_id": plan_id,
                                             "confirmation": argv[4]})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "cpu-run" and len(argv) == 1:
        prompt = sys.stdin.read(management_service.cpu_inference.MAX_PROMPT_BYTES + 1)
        result = call("inference.cpu.run", {"prompt": prompt, "max_tokens": 64})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "gpu-run" and len(argv) in {1, 2}:
        device_id = argv[1] if len(argv) == 2 else ""
        if device_id and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", device_id):
            print("Invalid Vulkan inference device ID.", file=sys.stderr); return 2
        prompt = sys.stdin.read(management_service.cpu_inference.MAX_PROMPT_BYTES + 1)
        payload = {"prompt": prompt, "max_tokens": 64}
        if device_id: payload["device_id"] = device_id
        result = call("inference.gpu.run", payload)
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "gpu-status" and len(argv) == 1:
        result = call("inference.gpu.status")
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "npu-status" and len(argv) == 1:
        result = call("inference.npu.status")
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "npu-runtime-preview" and len(argv) == 1:
        result = call("inference.npu.runtime.preview")
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        print("P\t" + clean(data.get("plan_id")) + "\t" + clean(json.dumps(data, sort_keys=True)))
        return 0
    if action == "npu-runtime-apply" and len(argv) == 3 and re.fullmatch(r"[0-9a-f]{24}", argv[1]) and argv[2] == "INSTALL":
        result = call("inference.npu.runtime.apply", {"plan_id": argv[1], "confirmed": True})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "npu-run" and len(argv) == 1:
        prompt = sys.stdin.read(management_service.cpu_inference.MAX_PROMPT_BYTES + 1)
        inventory = call("inference.npu.status")
        if not inventory.get("ok") or not inventory.get("data", {}).get("available"):
            print(management_presentation.format_report(inventory))
            return 1
        result = call("inference.npu.run", {"prompt": prompt, "max_tokens": 64})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "cpu-model-preview" and len(argv) == 2 and argv[1] in {"install", "remove"}:
        result = call("inference.cpu.model.preview", {"action": argv[1]})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        print("P\t" + clean(data.get("plan_id")) + "\t" + clean(json.dumps(data, sort_keys=True)))
        return 0
    if action == "cpu-model-apply" and len(argv) == 4 and argv[3] == "confirmed" and argv[1] in {"install", "remove"}:
        plan_id = argv[2]
        if not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print("The CPU model preview is invalid; create a new preview.", file=sys.stderr); return 2
        result = call("inference.cpu.model.apply", {"action": argv[1], "plan_id": plan_id, "confirmed": True})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "graphics-select" and len(argv) == 2 and argv[1] in {"kgsl-freedreno", "termux-zink", "system"}:
        result = call("graphics.provider.select", {"provider": "native", "backend": argv[1], "confirmed": True})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "graphics-verify" and len(argv) == 3:
        provider, api = argv[1], argv[2]
        result = call("graphics.provider.verify", {"provider": provider, "api": api, "display": ":1"})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "catalog" and len(argv) == 1:
        result = call("management.catalog")
        if not result.get("ok"):
            print(management_presentation.format_report(result))
            return 1
        data = result["data"]
        categories = data["categories"]
        for item in categories:
            print("C\t" + "\t".join(clean(item.get(k)) for k in ("id", "name", "description", "status")))
        resources = sorted(data["resources"], key=lambda item: (str(item.get("category_id", "")), str(item.get("name", "")).casefold()))
        for item in resources:
            operation_names = [management_presentation.operation_label(op)
                               for op in item.get("supported_operations", [])]
            print("R\t" + "\t".join(clean(item.get(k)) for k in (
                "id", "category_id", "name", "status", "availability", "description"))
                  + "\t" + clean(", ".join(operation_names)))
        return 0
    if action == "proot-install-catalog" and len(argv) == 1:
        result = call("proot.setup.catalog")
        if not result.get("ok"):
            print(management_presentation.format_report(result))
            return 1
        profiles = result.get("data", {}).get("profiles", [])
        for profile in profiles:
            alias = clean(profile.get("distro"))
            label = clean(profile.get("label"))
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", alias) or not label:
                print("Invalid managed distro catalog entry.", file=sys.stderr)
                return 1
            print("D\t" + alias + "\t" + label)
            for desktop in profile.get("desktops", []):
                desktop_id = clean(desktop.get("id"))
                name = clean(desktop.get("name"))
                routes = ",".join(clean(route) for route in desktop.get("routes", [])) or "unverified"
                if (not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", desktop_id)
                        or not name):
                    print("Invalid managed desktop catalog entry.", file=sys.stderr)
                    return 1
                print("E\t" + alias + "\t" + desktop_id + "\t" + name + "\t" + routes)
        return 0
    if action == "ssh-autostart-status" and len(argv) == 1:
        result = call("ssh.service.autostart.status")
        if not result.get("ok"):
            print(management_presentation.format_report(result))
            return 1
        enabled = result.get("data", {}).get("enabled")
        if type(enabled) is not bool:
            print("Could not verify the SSH startup preference.")
            return 1
        print("S\t" + ("true" if enabled else "false"))
        return 0
    if action == "ssh-autostart-preview" and len(argv) == 2 and argv[1] in {"enabled", "disabled"}:
        enabled = argv[1] == "enabled"
        result = call("ssh.service.autostart.preview", {"enabled": enabled})
        if not result.get("ok"):
            print(management_presentation.format_report(result))
            return 1
        data = result.get("data", {})
        if data.get("changed") is not True:
            print(management_presentation.format_report(result))
            return 0
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{32}", plan_id):
            print("Could not verify the exact SSH startup preference plan.")
            return 1
        print("P\t" + plan_id + "\t" + ("true" if enabled else "false") + "\t"
              + clean(data.get("effect")))
        return 0
    if action == "ssh-autostart-apply" and len(argv) == 4 and argv[1] == "confirmed" and argv[2] in {"true", "false"}:
        enabled = argv[2] == "true"
        plan_id = argv[3]
        if not re.fullmatch(r"[0-9a-f]{32}", plan_id):
            print("SSH startup preference preview expired; create a new preview.")
            return 2
        result = call("ssh.service.autostart.apply", {
            "enabled": enabled, "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "boot-cron-status" and len(argv) == 1:
        result = call("boot.cron.status")
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "boot-cron-validate" and len(argv) == 1:
        result = call("boot.cron.validate")
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "boot-cron-preview" and len(argv) == 2 and argv[1] in {"enable", "disable"}:
        result = call("boot.cron.preview", {"action": argv[1]})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if (data.get("ready") is not True or data.get("requires_confirmation") is not True
                or not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id)):
            print(management_presentation.format_report(result)); return 0
        print("P\t" + plan_id + "\t" + argv[1] + "\t"
              + clean(json.dumps(data, ensure_ascii=False, sort_keys=True)))
        return 0
    if action == "boot-cron-apply" and len(argv) == 3 and argv[1] in {"enable", "disable"}:
        plan_id = argv[2]
        if not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Cron boot preview is invalid; create a fresh preview.", file=sys.stderr); return 2
        result = call(f"boot.cron.{argv[1]}", {"confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "boot-helpers-status" and len(argv) == 1:
        result = call("boot.helpers.status")
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        for item in data.get("helpers", []):
            print("H\t" + "\t".join(clean(item.get(key)) for key in ("id", "identity", "installed_sha256", "source_sha256", "mode")))
        for item in data.get("snapshots", []):
            print("S\t" + "\t".join(clean(item.get(key)) for key in ("snapshot_id", "helper_id", "created_at", "sha256", "mode")))
        return 0
    if action == "boot-helpers-snapshots" and len(argv) == 2 and argv[1] in {"services", "recovery"}:
        result = call("boot.helpers.status")
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        for item in result.get("data", {}).get("snapshots", []):
            if item.get("helper_id") == argv[1]:
                print("S\t" + "\t".join(clean(item.get(key)) for key in ("snapshot_id", "created_at", "sha256", "mode")))
        return 0
    if action == "boot-helpers-preview" and len(argv) == 4 and argv[1] in {"services", "recovery"} and argv[2] in {"deploy", "rollback"}:
        helper_id, helper_action, snapshot_id = argv[1], argv[2], argv[3]
        if ((helper_action == "deploy" and snapshot_id != "-")
                or (helper_action == "rollback" and not re.fullmatch(r"[0-9a-f]{32}", snapshot_id))):
            print("Boot-helper target or snapshot is invalid; no change was made.", file=sys.stderr); return 2
        args = {"helper_id": helper_id, "action": helper_action,
                "snapshot_id": None if snapshot_id == "-" else snapshot_id}
        result = call("boot.helpers.preview", args)
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {}); plan = data.get("plan", {})
        plan_id = plan.get("plan_id")
        if (data.get("confirmation_required") is not True or not isinstance(plan_id, str)
                or not re.fullmatch(r"[0-9a-f]{32}", plan_id)):
            print(management_presentation.format_report(result)); return 0
        print("P\t" + "\t".join((plan_id, helper_id, helper_action, snapshot_id,
              clean(json.dumps(data, ensure_ascii=False, sort_keys=True)))))
        return 0
    if action == "boot-helpers-apply" and len(argv) == 5 and argv[1] in {"services", "recovery"} and argv[2] in {"deploy", "rollback"}:
        helper_id, helper_action, plan_id, snapshot_id = argv[1], argv[2], argv[3], argv[4]
        if (not re.fullmatch(r"[0-9a-f]{32}", plan_id)
                or (helper_action == "deploy" and snapshot_id != "-")
                or (helper_action == "rollback" and not re.fullmatch(r"[0-9a-f]{32}", snapshot_id))):
            print("Boot-helper apply requires a fresh exact plan and valid target.", file=sys.stderr); return 2
        args = {"helper_id": helper_id, "action": helper_action, "confirmed": True, "plan_id": plan_id,
                "snapshot_id": None if snapshot_id == "-" else snapshot_id}
        result = call("boot.helpers.apply", args)
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "ssh-deploy-preview" and len(argv) == 1:
        result = call("ssh.service.deploy", {"confirmed": False, "plan_id": None})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if data.get("requires_confirmation") is not True or not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print(management_presentation.format_report(result)); return 0
        print("P\t" + plan_id + "\t" + clean(json.dumps(data, ensure_ascii=False, sort_keys=True)))
        return 0
    if action == "ssh-deploy-apply" and len(argv) == 3 and argv[1] == "confirmed":
        plan_id = argv[2]
        if not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("SSH definition preview expired; create a new preview."); return 2
        result = call("ssh.service.deploy", {"confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "ssh-deploy-rollback-list" and len(argv) == 1:
        result = call("recovery.status")
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        records = result.get("data", {}).get("operations", [])
        for record in records:
            if (isinstance(record, dict) and record.get("kind") == "service.deploy"
                    and record.get("status") in {"complete", "needs_recovery"}
                    and isinstance(record.get("operation_id"), str)
                    and re.fullmatch(r"[0-9a-f]{32}", record["operation_id"])):
                print("R\t" + record["operation_id"] + "\t" + clean(record.get("status"))
                      + "\t" + clean(record.get("updated_at")))
        return 0
    if action == "ssh-deploy-rollback-preview" and len(argv) == 2 and re.fullmatch(r"[0-9a-f]{32}", argv[1]):
        operation_id = argv[1]
        result = call("ssh.service.deploy.rollback.preview", {"operation_id": operation_id})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if data.get("requires_confirmation") is not True or not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print(management_presentation.format_report(result)); return 0
        print("P\t" + operation_id + "\t" + plan_id + "\t"
              + clean(json.dumps(data, ensure_ascii=False, sort_keys=True)))
        return 0
    if action == "ssh-deploy-rollback-apply" and len(argv) == 3:
        operation_id, plan_id = argv[1:]
        if not re.fullmatch(r"[0-9a-f]{32}", operation_id) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("SSH definition rollback preview expired; create a new preview."); return 2
        result = call("ssh.service.deploy.rollback.apply", {
            "operation_id": operation_id, "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "ssh-wakelock-status" and len(argv) == 1:
        result = call("wakelock.ssh-policy.status")
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        enabled = result.get("data", {}).get("persistent_lease_enabled")
        if type(enabled) is not bool:
            print("Could not verify the managed SSH Wake Lock preference."); return 1
        print("S\t" + ("true" if enabled else "false")); return 0
    if action == "ssh-wakelock-preview" and len(argv) == 2 and argv[1] in {"enabled", "disabled"}:
        enabled = argv[1] == "enabled"
        result = call("wakelock.ssh-policy.preview", {"enabled": enabled})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        if data.get("changed") is not True:
            print(management_presentation.format_report(result)); return 0
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{32}", plan_id):
            print("Could not verify the exact Wake Lock preference plan."); return 1
        print("P\t" + plan_id + "\t" + ("true" if enabled else "false") + "\t" + clean(data.get("effect")))
        return 0
    if action == "ssh-wakelock-apply" and len(argv) == 4 and argv[1] == "confirmed" and argv[2] in {"true", "false"}:
        enabled = argv[2] == "true"; plan_id = argv[3]
        if not re.fullmatch(r"[0-9a-f]{32}", plan_id):
            print("Wake Lock preference preview expired; create a new preview."); return 2
        result = call("wakelock.ssh-policy.apply", {"enabled": enabled, "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result)); return 0 if result.get("ok") else 1
    if action == "ssh-client-key-preview" and len(argv) == 2:
        result = call("ssh.client-key.create.preview", {"name": argv[1]})
        if not result.get("ok"):
            print(management_presentation.format_report(result))
            return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if data.get("changed") is not True:
            print(management_presentation.format_report(result))
            return 0
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{32}", plan_id):
            print("Could not verify the exact Native SSH recovery key plan.")
            return 1
        impact = "Creates a local Ed25519 private key (mode 0600); it is not enrolled yet."
        print("P\t" + plan_id + "\t" + clean(data.get("name")) + "\t"
              + clean(data.get("private_key_path")) + "\t" + impact)
        return 0
    if action == "ssh-client-key-apply" and len(argv) == 4 and argv[1] == "confirmed":
        name, plan_id = argv[2:]
        if not re.fullmatch(r"[0-9a-f]{32}", plan_id):
            print("The Native SSH key preview expired; create a new preview.")
            return 2
        result = call("ssh.client-key.create.apply", {
            "name": name, "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action in {"ssh-key-add-preview", "ssh-key-remove-preview"} and len(argv) == 2:
        operation = "ssh.keys.add.preview" if action == "ssh-key-add-preview" else "ssh.keys.remove.preview"
        args = {"public_key": argv[1]} if action == "ssh-key-add-preview" else {"fingerprint": argv[1]}
        result = call(operation, args)
        if not result.get("ok"):
            print(management_presentation.format_report(result))
            return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        fingerprint = data.get("fingerprint")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{24}", plan_id) or not isinstance(fingerprint, str):
            print("Could not verify the exact SSH key change preview.")
            return 1
        impact = "Shared authorized keys for owner-managed SSH 8022 and Ternuxx SSH 8023. "
        impact += ("Adds " if action == "ssh-key-add-preview" else "Removes ") + fingerprint
        print("P\t" + plan_id + "\t" + fingerprint + "\t" + clean(impact))
        return 0
    if action in {"ssh-key-add-apply", "ssh-key-remove-apply"} and len(argv) == 4 and argv[1] == "confirmed":
        subject, plan_id = argv[2:]
        if not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print("The SSH key change preview expired; create a new preview.")
            return 2
        is_add = action == "ssh-key-add-apply"
        operation = "ssh.keys.add.apply" if is_add else "ssh.keys.remove.apply"
        args = ({"public_key": subject} if is_add else {"fingerprint": subject})
        args.update({"confirmed": True, "plan_id": plan_id})
        result = call(operation, args)
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "ssh-key-rollback-list" and len(argv) == 1:
        result = call("ssh.keys.rollback.list")
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        entries = result.get("data", {}).get("entries", [])
        for entry in entries:
            print("R\t" + clean(entry.get("rollback_id")) + "\t" + clean(entry.get("fingerprint"))
                  + "\t" + clean(entry.get("action")) + "\t" + clean(entry.get("status")))
        if not entries: print("R\t-\t-\t-\t-")
        return 0
    if action == "ssh-key-rollback-preview" and len(argv) == 2:
        result = call("ssh.keys.rollback.preview", {"rollback_id": argv[1]})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {}); plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print("Could not verify the exact SSH recovery preview."); return 1
        print("P\t" + plan_id + "\t" + clean(data.get("rollback_id")) + "\t" + clean(data.get("effect")))
        return 0
    if action == "ssh-key-rollback-apply" and len(argv) == 3:
        rollback_id, plan_id = argv[1:]
        if not re.fullmatch(r"[0-9a-f]{32}", rollback_id) or not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print("The SSH recovery preview is invalid or expired."); return 2
        result = call("ssh.keys.rollback.apply", {"rollback_id": rollback_id,
            "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "ssh-keys-list" and len(argv) == 1:
        result = call("ssh.keys.list")
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "inspect" and len(argv) == 2:
        rid = argv[1]
        operation_args: dict[str, object] = {}
        if rid == "graphics.native":
            operation = "graphics.provider.status"
            operation_args = {"provider": "native"}
        elif rid == "network.ssh.external-native":
            operation = "ssh.inspect"
        elif rid == "native.acceleration.qualification":
            operation = "doctor.report"
            # Bounded, read-only probes inspect this process's current display;
            # they never launch a server, workload, or guest.
            operation_args = {"graphics": True}
        elif rid == "network.ssh.managed-8023":
            operation = "ssh.inspect"
        else:
            catalog = call("management.catalog")
            resource = next((r for r in catalog.get("data", {}).get("resources", []) if r["id"] == rid), None)
            if resource is None:
                print(management_presentation.format_report(
                    {"ok": False, "error": {"code": "unknown_resource"}}))
                return 2
            operation = next((op for op in resource["supported_operations"]
                              if op != "management.catalog"
                              and op in management_service.OPERATIONS
                              and (not management_service.OPERATIONS[op]["args"] or op == "doctor.report")
                              and op not in management_sessions.MUTATING_OPERATIONS), None)
            if operation == "doctor.report":
                operation_args = {"graphics": False}
            if operation is None:
                print(management_presentation.format_report(
                    {"ok": False, "error": {"code": "live_status_unavailable"}}))
                return 3
        result = call(operation, operation_args) if operation_args else call(operation)
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "cron-preview" and len(argv) in {3, 5, 7, 8}:
        kind = argv[1]
        if kind == "create" and len(argv) in {5, 7, 8}:
            if len(argv) == 5:
                name, action_id, expression = argv[2:]
                schedule_type, value, extra, timezone_name = "cron", expression, "", ""
            else:
                name, action_id, schedule_type, value, extra = argv[2:7]
                timezone_name = argv[7] if len(argv) == 8 else ""
            schedule: dict[str, object]
            if schedule_type == "cron" and not extra:
                schedule = {"expression": value}
                if timezone_name: schedule["timezone"] = timezone_name
            elif schedule_type == "interval" and extra and not timezone_name:
                if not value.isdigit():
                    print(json.dumps({"ok": False, "error": {"code": "invalid_interval"}}))
                    return 2
                schedule = {"interval_seconds": int(value), "anchor_at": extra}
            elif schedule_type == "calendar" and extra == "daily":
                schedule = {"mode": "daily", "time": value}
                if timezone_name: schedule["timezone"] = timezone_name
            elif schedule_type == "calendar" and extra == "specific" and not timezone_name:
                schedule = {"mode": "specific", "datetime": value}
            elif schedule_type == "one_time" and not timezone_name and not extra:
                schedule = {"at": value}
            else:
                print(json.dumps({"ok": False, "error": {"code": "invalid_schedule"}}))
                return 2
            args = {"action": "create", "name": name, "action_id": action_id,
                    "schedule_type": schedule_type, "schedule": schedule}
        elif kind == "update" and len(argv) == 5:
            job_id, field, value = argv[2:]
            if field not in {"name", "enabled"}:
                print(json.dumps({"ok": False, "error": {"code": "invalid_update_field"}}))
                return 2
            change = {"name": value} if field == "name" else {"enabled": value.lower() == "true"}
            if field == "enabled" and value.lower() not in {"true", "false"}:
                print(json.dumps({"ok": False, "error": {"code": "invalid_enabled_value"}}))
                return 2
            args = {"action": "update", "job_id": job_id, "changes": change}
        elif kind == "remove" and len(argv) == 3:
            args = {"action": "remove", "job_id": argv[2]}
        else:
            print(json.dumps({"ok": False, "error": {"code": "invalid_arguments"}}))
            return 2
        preview = call("cron.jobs.mutation.preview", args)
        if not preview.get("ok"):
            print(management_presentation.format_report(preview))
            return 1
        plan = preview.get("data", {}).get("plan", {})
        if not isinstance(plan.get("plan_id"), str):
            print(json.dumps({"ok": False, "error": {"code": "invalid_preview"}}))
            return 1
        print("P\t" + plan["plan_id"] + "\t" + clean(json.dumps(plan, ensure_ascii=False, sort_keys=True)))
        return 0
    if action == "cron-apply" and len(argv) == 2:
        plan_id = argv[1]
        if not re.fullmatch(r"[0-9a-f]{32}", plan_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_plan_id"}}))
            return 2
        result = call("cron.jobs.mutation.apply", {"plan_id": plan_id, "confirmed": True})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "cron-scheduler" and len(argv) in {2, 3}:
        choice = argv[1]
        if choice == "status" and len(argv) == 2:
            result = call("cron.status")
        elif choice == "start" and len(argv) == 3 and argv[2].isdigit() and 1 <= int(argv[2]) <= 60:
            result = call("cron.scheduler.start", {"poll_seconds": int(argv[2]), "confirmed": True})
        elif choice == "stop" and len(argv) == 2:
            result = call("cron.scheduler.stop", {"confirmed": True})
        else:
            print(json.dumps({"ok": False, "error": {"code": "invalid_arguments"}}))
            return 2
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "cron-jobs" and len(argv) == 1:
        result = call("cron.jobs.list")
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action in {"recovery-status", "backup-list", "continuity-status"} and len(argv) == 1:
        operation = {"recovery-status": "recovery.status", "backup-list": "backup.list",
                     "continuity-status": "continuity.status"}[action]
        result = call(operation)
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action in {"continuity-prepare-preview", "continuity-verify-preview"} and len(argv) == 2:
        if action == "continuity-prepare-preview" and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}", argv[1]):
            operation, args = "continuity.prepare.preview", {"test_id": argv[1]}
        elif action == "continuity-verify-preview" and re.fullmatch(r"[a-f0-9]{32}", argv[1]):
            operation, args = "continuity.verify.preview", {"checkpoint_id": argv[1]}
        else:
            print("Invalid continuity reference.", file=sys.stderr); return 2
        result = call(operation, args)
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {}); plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Continuity preview returned an invalid plan."); return 1
        print("P\t" + plan_id + "\t" + clean(json.dumps(data, sort_keys=True)))
        return 0
    if action in {"reboot-test-prepare-preview", "reboot-test-verify-preview"} and len(argv) == 2:
        if not management_service.reboot_recovery.TEST_ID_RE.fullmatch(argv[1]):
            print("Invalid reboot-test ID.", file=sys.stderr); return 2
        operation = ("continuity.prepare-reboot-test.preview" if action == "reboot-test-prepare-preview"
                     else "continuity.verify-reboot-test.preview")
        result = call(operation, {"test_id": argv[1]})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {}); plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Reboot-test preview returned an invalid plan."); return 1
        print("P\t" + plan_id + "\t" + clean(json.dumps(data, sort_keys=True)))
        return 0
    if action in {"reboot-test-prepare-apply", "reboot-test-verify-apply"} and len(argv) == 4 and argv[3] == "confirmed":
        test_id, plan_id = argv[1], argv[2]
        if not management_service.reboot_recovery.TEST_ID_RE.fullmatch(test_id) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Reboot-test preview is invalid; create a new preview.", file=sys.stderr); return 2
        operation = ("continuity.prepare-reboot-test" if action == "reboot-test-prepare-apply"
                     else "continuity.verify-reboot-test")
        result = call(operation, {"test_id": test_id, "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result)); return 0 if result.get("ok") else 1
    if action in {"continuity-prepare-apply", "continuity-verify-apply"} and len(argv) == 4 and argv[3] == "confirmed":
        reference, plan_id = argv[1], argv[2]
        is_prepare = action == "continuity-prepare-apply"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}" if is_prepare else r"[a-f0-9]{32}", reference) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Continuity preview expired or is invalid; create a new preview.", file=sys.stderr); return 2
        operation = "continuity.prepare" if is_prepare else "continuity.verify"
        args = ({"test_id": reference} if is_prepare else {"checkpoint_id": reference})
        args.update({"confirmed": True, "plan_id": plan_id})
        result = call(operation, args)
        print(management_presentation.format_report(result)); return 0 if result.get("ok") else 1
    if action == "backup-create-preview" and len(argv) == 2 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", argv[1]):
        result = call("backup.create", {"name": argv[1]})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {}); plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Backup preview returned an invalid plan."); return 1
        print("P\t" + plan_id + "\t" + clean(json.dumps(data, sort_keys=True)))
        return 0
    if action == "backup-create-apply" and len(argv) == 4 and argv[3] == "confirmed":
        name, plan_id = argv[1], argv[2]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Backup preview is invalid; create a new preview."); return 2
        result = call("backup.create", {"name": name, "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result)); return 0 if result.get("ok") else 1
    if action in {"restore-apply-preview", "restore-apply"} and len(argv) in {2, 4}:
        backup_id = argv[1]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", backup_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_backup_id"}})); return 2
        if action == "restore-apply-preview" and len(argv) == 2:
            result = call("restore.preview", {"backup_id": backup_id})
            if not result.get("ok"):
                print(management_presentation.format_report(result)); return 1
            data = result.get("data", {}); plan_id = data.get("plan_id")
            if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
                print("Restore preview returned an invalid plan."); return 1
            print("P\t" + plan_id + "\t" + clean(json.dumps(data, sort_keys=True))); return 0
        if action == "restore-apply" and len(argv) == 4 and argv[3] == "confirmed" and re.fullmatch(r"[0-9a-f]{64}", argv[2]):
            result = call("restore.apply", {"backup_id": backup_id, "confirmed": True, "plan_id": argv[2]})
            print(management_presentation.format_report(result)); return 0 if result.get("ok") else 1
    recovery_preview_actions = {"recovery-resolve-preview": "recovery.resolve",
                               "recovery-rollback-apply-preview": "recovery.rollback.preview"}
    if action in recovery_preview_actions and len(argv) == 2 and re.fullmatch(r"[0-9a-f]{32}", argv[1]):
        operation_id = argv[1]
        result = call(recovery_preview_actions[action], {"operation_id": operation_id})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {}); plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Recovery preview returned an invalid plan."); return 1
        print("P\t" + plan_id + "\t" + operation_id + "\t" + clean(json.dumps(data, sort_keys=True)))
        return 0
    if action in {"recovery-resolve-apply", "recovery-rollback-apply"} and len(argv) == 4 and argv[3] == "confirmed":
        operation_id, plan_id = argv[1], argv[2]
        if not re.fullmatch(r"[0-9a-f]{32}", operation_id) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print("Recovery plan is invalid; create a new preview."); return 2
        operation = "recovery.resolve" if action == "recovery-resolve-apply" else "recovery.rollback.apply"
        result = call(operation, {"operation_id": operation_id, "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result)); return 0 if result.get("ok") else 1
    if action in {"backup-inspect", "restore-preview"} and len(argv) == 2:
        backup_id = argv[1]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", backup_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_backup_id"}}))
            return 2
        operation = "backup.inspect" if action == "backup-inspect" else "restore.preview"
        result = call(operation, {"backup_id": backup_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action in {"recovery-inspect", "recovery-rollback-preview"} and len(argv) == 2:
        operation_id = argv[1]
        if not re.fullmatch(r"[A-Za-z0-9]{32}", operation_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_operation_id"}}))
            return 2
        operation = "recovery.inspect" if action == "recovery-inspect" else "recovery.rollback.preview"
        result = call(operation, {"operation_id": operation_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "cron-inspect" and len(argv) == 3:
        kind, item_id = argv[1:]
        if kind == "job" and re.fullmatch(r"job-[0-9a-f]{32}", item_id):
            operation, args = "cron.jobs.show", {"job_id": item_id}
        elif kind == "next" and re.fullmatch(r"job-[0-9a-f]{32}", item_id):
            operation, args = "cron.jobs.next_runs", {"job_id": item_id, "count": 5}
        elif kind == "execution" and re.fullmatch(r"exec-[0-9a-f]{32}", item_id):
            operation, args = "cron.executions.show", {"execution_id": item_id}
        else:
            print(json.dumps({"ok": False, "error": {"code": "invalid_cron_reference"}}))
            return 2
        result = call(operation, args)
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    proot_reads = {"proot-status": "proot.status", "proot-profile-list": "proot.profiles.list",
                   "proot-session-list": "proot.sessions.list"}
    if action in proot_reads and len(argv) == 1:
        result = call(proot_reads[action])
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "proot-replay-retire-preview" and len(argv) == 2:
        alias = argv[1]
        if not re.fullmatch(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", alias):
            print(json.dumps({"ok": False, "error": {"code": "invalid_replay_alias"}})); return 2
        result = call("proot.setup.retire.preview", {"alias": alias})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        operation = data.get("operation", {})
        if (not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id)
                or not isinstance(operation, dict)
                or operation.get("alias") != alias or operation.get("confirmation_required") is not True):
            print("Replay retirement preview did not identify the exact guest plan.", file=sys.stderr); return 1
        print("P\t" + plan_id + "\t" + alias + "\t" + clean(operation.get("impact")))
        return 0
    if action == "proot-replay-restore-preview" and len(argv) == 3:
        alias, backup_id = argv[1:]
        if (not re.fullmatch(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", alias)
                or not re.fullmatch(r"[0-9a-f]{32}", backup_id)):
            print(json.dumps({"ok": False, "error": {"code": "invalid_replay_restore_target"}})); return 2
        result = call("proot.setup.restore.preview", {"alias": alias, "backup_id": backup_id})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        operation = data.get("operation", {})
        if (not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id)
                or not isinstance(operation, dict)
                or operation.get("alias") != alias or operation.get("backup_id") != backup_id
                or operation.get("confirmation_required") is not True):
            print("Replay restore preview did not identify the exact guest plan.", file=sys.stderr); return 1
        print("P\t" + plan_id + "\t" + alias + "\t" + backup_id + "\t" + clean(operation.get("impact")))
        return 0
    if action == "proot-replay-retire-apply" and len(argv) == 3:
        alias, plan_id = argv[1:]
        if (not re.fullmatch(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", alias)
                or not re.fullmatch(r"[0-9a-f]{64}", plan_id)):
            print(json.dumps({"ok": False, "error": {"code": "invalid_replay_retirement_plan"}})); return 2
        result = call("proot.setup.retire.apply", {"alias": alias, "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "proot-replay-restore-apply" and len(argv) == 4:
        alias, backup_id, plan_id = argv[1:]
        if (not re.fullmatch(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", alias)
                or not re.fullmatch(r"[0-9a-f]{32}", backup_id)
                or not re.fullmatch(r"[0-9a-f]{64}", plan_id)):
            print(json.dumps({"ok": False, "error": {"code": "invalid_replay_restore_plan"}})); return 2
        result = call("proot.setup.restore.apply", {"alias": alias, "backup_id": backup_id,
            "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    # GTK guest controls stay thin: validate identifiers here and leave policy,
    # preview, and execution to the shared management service.
    if action == "proot-app-launch" and len(argv) == 2:
        app_id = argv[1]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", app_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_app_id"}})); return 2
        result = call("proot.app.launch", {"app_id": app_id, "display": ":1"})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "proot-shortcut-list" and len(argv) == 1:
        result = call("proot.shortcuts.list")
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "proot-shortcut-preview" and len(argv) == 3 and argv[1] in {"add", "remove"}:
        app_id = argv[2]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", app_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_app_id"}})); return 2
        result = call("proot.shortcuts.preview", {"action": argv[1], "app_id": app_id})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print("Shortcut preview did not return an exact plan ID."); return 1
        if data.get("changed") is not True:
            print("R\tShortcut is already in the requested state."); return 0
        affected = data.get("affected_resources", [])
        target = affected[0].get("path", "") if affected and isinstance(affected[0], dict) else ""
        print("P\t" + plan_id + "\t" + clean(data.get("name")) + "\t" + clean(target))
        return 0
    if action == "proot-shortcut-apply" and len(argv) == 4 and argv[1] in {"add", "remove"}:
        if (not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", argv[2])
                or not re.fullmatch(r"[0-9a-f]{24}", argv[3])):
            print(json.dumps({"ok": False, "error": {"code": "invalid_shortcut_plan"}})); return 2
        result = call("proot.shortcuts.apply", {"action": argv[1], "app_id": argv[2],
            "confirmed": True, "plan_id": argv[3]})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "proot-shortcut-sync-preview" and len(argv) == 1:
        result = call("proot.shortcuts.sync.preview")
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print("Shortcut sync preview did not return an exact plan ID."); return 1
        if data.get("changed") is not True:
            print("R\tShortcut sync is already current."); return 0
        print("P\t" + plan_id + "\t" + str(data.get("discovered", 0)) + "\t"
              + str(len(data.get("changes", []))) + "\t" + str(len(data.get("conflicts", []))))
        return 0
    if action == "proot-shortcut-sync-apply" and len(argv) == 3 and argv[1] == "confirmed":
        plan_id = argv[2]
        if not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_shortcut_sync_plan"}})); return 2
        result = call("proot.shortcuts.sync.apply", {"confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "proot-shortcut-rollback-list" and len(argv) == 1:
        result = call("proot.shortcuts.sync.rollback.list")
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        for item in result.get("data", {}).get("rollbacks", []):
            print("R\t" + clean(item.get("rollback_id")) + "\t" + clean(item.get("status"))
                  + "\t" + clean(item.get("integrity")) + "\t" + clean(item.get("entry_count", 0)))
        return 0
    if action == "proot-shortcut-rollback-preview" and len(argv) == 2:
        rollback_id = argv[1]
        if not re.fullmatch(r"[0-9a-f]{32}", rollback_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_shortcut_rollback_id"}})); return 2
        result = call("proot.shortcuts.sync.rollback.preview", {"rollback_id": rollback_id})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print("Shortcut rollback preview did not return an exact plan ID."); return 1
        if data.get("requires_confirmation") is not True:
            print("R\tShortcut sync has no changes to restore."); return 0
        print("Q\t" + plan_id + "\t" + rollback_id + "\t" + str(len(data.get("changes", []))))
        return 0
    if action == "proot-shortcut-rollback-apply" and len(argv) == 4 and argv[1] == "confirmed":
        rollback_id, plan_id = argv[2:]
        if not re.fullmatch(r"[0-9a-f]{32}", rollback_id) or not re.fullmatch(r"[0-9a-f]{24}", plan_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_shortcut_rollback_plan"}})); return 2
        result = call("proot.shortcuts.sync.rollback.apply", {"rollback_id": rollback_id,
            "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "proot-stop-preview" and len(argv) == 2:
        session_id = argv[1]
        if not re.fullmatch(r"proot-[a-f0-9]{32}", session_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_session_id"}})); return 2
        result = call("proot.stop.preview", {"session_id": session_id})
        if not result.get("ok"):
            print(management_presentation.format_report(result)); return 1
        data = result.get("data", {})
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"plan-[0-9a-f]{64}", plan_id):
            print("PRoot stop preview did not identify an exact owned session plan."); return 1
        print("P\t" + plan_id + "\t" + clean(data.get("impact")))
        return 0
    if action == "proot-stop-apply" and len(argv) == 3:
        if not re.fullmatch(r"proot-[a-f0-9]{32}", argv[1]) or not re.fullmatch(r"plan-[0-9a-f]{64}", argv[2]):
            print(json.dumps({"ok": False, "error": {"code": "invalid_session_plan"}})); return 2
        result = call("proot.stop", {"session_id": argv[1], "confirmed": True, "plan_id": argv[2]})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "proot-reconcile-preview" and len(argv) == 2:
        session_id = argv[1]
        if not re.fullmatch(r"proot-[a-f0-9]{32}", session_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_session_id"}})); return 2
        inspection = call("proot.recovery.inspect", {"session_id": session_id})
        if not inspection.get("ok"):
            print(management_presentation.format_report(inspection)); return 1
        preview = call("proot.recovery.reconcile.preview", {"session_id": session_id})
        if not preview.get("ok"):
            print(management_presentation.format_report(preview)); return 1
        data = preview.get("data", {})
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"plan-[0-9a-f]{64}", plan_id):
            print(management_presentation.format_report(preview)); return 0
        summary = "status={}; observed={}; evidence={}; action={}; signal_sent=false".format(
            clean(inspection.get("data", {}).get("status")), clean(data.get("observed_state")),
            clean(data.get("evidence")), clean(data.get("action")))
        print("P\t" + plan_id + "\t" + summary)
        return 0
    if action == "proot-reconcile-apply" and len(argv) == 3:
        session_id, plan_id = argv[1:]
        if (not re.fullmatch(r"proot-[a-f0-9]{32}", session_id)
                or not re.fullmatch(r"plan-[0-9a-f]{64}", plan_id)):
            print(json.dumps({"ok": False, "error": {"code": "invalid_session_plan"}})); return 2
        result = call("proot.recovery.reconcile", {"session_id": session_id,
            "confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action.startswith("proot-"):
        print(json.dumps({"ok": False, "error": {"code": "unsupported_typed_action",
            "message": "Use one of the listed PRoot status or session actions."}}))
        return 2
    if action == "timezone-set" and len(argv) == 2:
        result = call("timezone.set", {"timezone": argv[1]})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "cron-history" and len(argv) == 1:
        result = call("cron.executions.list", {"limit": 20})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "logs-read" and len(argv) == 2:
        source_id = argv[1]
        if source_id not in {"native-desktop", "cron-scheduler", "management-api"}:
            print(json.dumps({"ok": False, "error": {"code": "invalid_log_source"}}))
            return 2
        result = call("management.logs.read", {"source_id": source_id, "limit": 100})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "history" and len(argv) == 1:
        result = call("recovery.status")
        print(management_presentation.format_activity_history(result))
        return 0 if result.get("ok") else 1
    if action in {"ssh-preview-start", "ssh-preview-stop", "ssh-preview-restart"} and len(argv) == 1:
        operation = "ssh.service." + action.removeprefix("ssh-preview-")
        result = call(operation, {"confirmed": False, "plan_id": None})
        if not result.get("ok"):
            print(management_presentation.format_report(result))
            return 1
        data = result.get("data", {})
        fields = ("P", clean(data.get("plan_id")) or "-",
                  str(bool(data.get("requires_confirmation"))).lower(),
                  clean(data.get("impact")))
        print("\t".join(fields))
        return 0
    if action in {"ssh-apply-start", "ssh-apply-stop", "ssh-apply-restart"} and len(argv) == 3 and argv[1] == "confirmed":
        plan_id = argv[2]
        if not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            print(json.dumps({"ok": False, "error": {"code": "invalid_plan_id"}}))
            return 2
        operation = "ssh.service." + action.removeprefix("ssh-apply-")
        result = call(operation, {"confirmed": True, "plan_id": plan_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "start-desktop" and len(argv) == 3 and argv[1] == "confirmed":
        desktop_id = argv[2]
        if desktop_id not in {"xfce", "lxqt", "mate", "cinnamon", "plasma"}:
            print(json.dumps({"ok": False, "error": {"code": "invalid_desktop_id"}})); return 2
        result = call("desktop.start", {"desktop_id": desktop_id})
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action in {"start-desktop", "stop-desktop"} and len(argv) == 2 and argv[1] == "confirmed":
        result = call("desktop.start" if action == "start-desktop" else "desktop.stop")
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    if action == "monitor" and len(argv) == 1:
        result = call("desktop.monitor.status")
        if not result.get("ok"):
            print(management_presentation.format_report(result))
            return 1
        data = result["data"]
        print("M\t" + "\t".join(clean(data.get(k)) for k in (
            "enabled", "interval_seconds", "focus_check", "activity_launch")))
        return 0
    if action == "set-monitor" and len(argv) == 6:
        enabled, interval, unit, focus, launch = argv[1:]
        if (any(value not in {"true", "false"} for value in (enabled, focus, launch))
                or not interval.isdecimal() or unit not in {"seconds", "minutes", "hours"}):
            print(json.dumps({"ok": False, "error": {"code": "invalid_arguments"}}))
            return 2
        result = call("desktop.monitor.configure", {
            "enabled": enabled == "true", "interval_value": int(interval), "unit": unit,
            "focus_check": focus == "true", "activity_launch": launch == "true",
        })
        print(management_presentation.format_report(result))
        return 0 if result.get("ok") else 1
    print("Unsupported typed management action.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
