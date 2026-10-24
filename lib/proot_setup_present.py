"""Human-readable presentation for bounded PRoot setup results."""
from __future__ import annotations

import json
import re
import sys


def summarize(result: object) -> list[str]:
    if not isinstance(result, dict):
        raise ValueError("setup result must be an object")
    status = result.get("status")
    if status not in {"preview", "adopted"}:
        raise ValueError("setup result status is unsupported")
    operation = result.get("operation", {})
    record = result.get("record", {})
    if not isinstance(operation, dict) or not isinstance(record, dict):
        raise ValueError("setup result details are malformed")
    details = operation if operation else record
    release = details.get("guest_release", {})
    if not isinstance(release, dict):
        raise ValueError("guest release details are malformed")
    version = release.get("VERSION_ID", "unknown")
    codename = release.get("VERSION_CODENAME", "unknown")
    user = details.get("guest_user", "unknown")
    rootfs = details.get("rootfs", "existing Debian rootfs")
    if not all(isinstance(value, str) and len(value) <= 1024
               and all(ord(char) >= 32 and ord(char) != 127 for char in value)
               for value in (version, codename, user, rootfs)):
        raise ValueError("setup result contains invalid presentation values")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user):
        raise ValueError("guest account name is invalid")
    lines = [
        "Existing Debian guest profile " + ("preview" if status == "preview" else "recorded"),
        f"Guest: Debian {version} ({codename}) · {user}",
        f"Target: {rootfs}",
    ]
    graphics = operation.get("observed_graphics_files", {})
    if graphics:
        if not isinstance(graphics, dict):
            raise ValueError("graphics inventory is malformed")
        driver_record = graphics.get("turnip_driver", {})
        icd_record = graphics.get("turnip_icd", {})
        if not isinstance(driver_record, dict) or not isinstance(icd_record, dict):
            raise ValueError("graphics file record is malformed")
        driver = driver_record.get("status", "unknown")
        icd = icd_record.get("status", "unknown")
        if driver not in {"present", "missing"} or icd not in {"present", "missing"}:
            raise ValueError("graphics file status is unsupported")
        lines.append(f"Ternuxx Turnip files: driver {driver}; ICD {icd} (file presence only)")
    other_icds = operation.get("observed_other_icd_configs", [])
    if not isinstance(other_icds, list) or len(other_icds) > 64:
        raise ValueError("other ICD inventory is malformed")
    safe_names = []
    for item in other_icds:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("other ICD record is malformed")
        name = item["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.+-]{1,128}\.json", name):
            raise ValueError("other ICD filename is invalid")
        safe_names.append(name)
    if safe_names:
        lines.append("Other ICD configs (not selected by Ternuxx): " + ", ".join(safe_names))
    package_groups = operation.get("observed_package_groups", {})
    if package_groups:
        if not isinstance(package_groups, dict) or len(package_groups) > 32:
            raise ValueError("package group inventory is malformed")
        labels = {"base": "base", "desktop-compat": "desktop compatibility",
                  "development": "development", "desktop-apps": "desktop apps", "fonts": "fonts"}
        summaries = []
        missing_names = []
        held_names = []
        for group, detail in package_groups.items():
            if (not isinstance(group, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", group)
                    or not isinstance(detail, dict)
                    or type(detail.get("requested")) is not int
                    or type(detail.get("installed")) is not int
                    or not isinstance(detail.get("missing"), list)
                    or not isinstance(detail.get("held"), list)
                    or not 0 <= detail["installed"] <= detail["requested"] <= 512):
                raise ValueError("package group state is invalid")
            summaries.append(f"{labels.get(group, group)} {detail['installed']}/{detail['requested']}")
            for name in detail["missing"] + detail["held"]:
                if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]{0,127}", name):
                    raise ValueError("package name in inventory is invalid")
            missing_names.extend(detail["missing"])
            held_names.extend(detail["held"])
        lines.append("Manifest packages: " + "; ".join(summaries))
        if missing_names:
            lines.append("Not installed: " + ", ".join(missing_names[:16])
                         + (f" (+{len(missing_names)-16} more)" if len(missing_names) > 16 else ""))
        if held_names:
            lines.append(f"APT-held manifest packages: {len(set(held_names))} (not upgraded)")
    changes = [
        operation.get("guest_mutations", []),
        operation.get("package_changes", []),
        operation.get("service_changes", []),
    ]
    if any(not isinstance(items, list) for items in changes):
        raise ValueError("setup change inventory is malformed")
    if not any(changes):
        lines.append("Guest files, packages, services: unchanged")
    plan_id = result.get("plan_id")
    if status == "preview":
        if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
            raise ValueError("setup preview plan ID is invalid")
        lines.append(f"Plan ID: {plan_id}")
        blocked = operation.get("apply_blocked_reason")
        if blocked is not None:
            if not isinstance(blocked, str) or len(blocked) > 512:
                raise ValueError("setup blocker is malformed")
            lines.append("Apply blocked: the saved record belongs to a different rootfs identity")
        else:
            if operation.get("refresh_existing_record"):
                lines.append("Native adoption record: refresh; exact prior bytes will be backed up")
            lines.append(f"Apply after review: tx install debian apply {plan_id} --yes")
    backup_id = record.get("rollback_backup_id")
    if status == "adopted" and backup_id is not None:
        if not isinstance(backup_id, str) or not re.fullmatch(r"[0-9a-f]{64}", backup_id):
            raise ValueError("adoption rollback backup ID is invalid")
        lines.append(f"Rollback backup ID: {backup_id}")
        lines.append(f"Rollback preview: tx proot setup adoption-rollback-preview --backup-id {backup_id}")
    return lines


def main() -> int:
    try:
        raw = sys.stdin.read(65537)
        if len(raw) > 65536:
            raise ValueError("setup result exceeds the presentation limit")
        result = json.loads(raw)
        print("\n".join(summarize(result)))
        return 0
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Could not format Debian setup result: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
