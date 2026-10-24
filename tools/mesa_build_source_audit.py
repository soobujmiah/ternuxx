#!/usr/bin/env python3
"""Map Meson target source membership to the pinned Mesa source inventory.

This records configured target-source membership. It does not infer transitive
link inputs, final object contents, or package-to-target attribution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


class SourceAuditError(ValueError):
    """Invalid graph, source inventory, or source-root coverage."""


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceAuditError(f"cannot read JSON input {path.name}: {type(exc).__name__}") from exc


def audit_graph(targets_path: Path, inventory_path: Path, source_root: str) -> dict[str, object]:
    root = PurePosixPath(source_root)
    if not root.is_absolute() or ".." in root.parts:
        raise SourceAuditError("source root must be a normalized absolute POSIX path")
    root_prefix = root.as_posix().rstrip("/") + "/"

    graph = _read_json(targets_path)
    inventory = _read_json(inventory_path)
    if not isinstance(graph, list):
        raise SourceAuditError("Meson target graph must be an array")
    if not isinstance(inventory, dict) or not isinstance(inventory.get("files"), list):
        raise SourceAuditError("source inventory has no files array")

    indexed: dict[str, dict[str, object]] = {}
    for item in inventory["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise SourceAuditError("source inventory contains an invalid file record")
        path = item["path"]
        if path in indexed:
            raise SourceAuditError(f"source inventory repeats path {path}")
        if (not isinstance(item.get("sha256"), str)
                or not isinstance(item.get("spdx_header_identifiers"), list)):
            raise SourceAuditError(f"source inventory record is incomplete for {path}")
        indexed[path] = item

    sources: dict[str, dict[str, object]] = {}
    external: dict[str, set[str]] = {}
    generated: dict[str, set[str]] = {}
    target_ids: set[str] = set()
    for target in graph:
        if not isinstance(target, dict) or not all(isinstance(target.get(key), str)
                                                   for key in ("id", "name", "type")):
            raise SourceAuditError("Meson graph contains a malformed target")
        target_id = target["id"]
        if target_id in target_ids:
            raise SourceAuditError(f"Meson graph repeats target ID {target_id}")
        target_ids.add(target_id)
        membership = {"id": target_id, "name": target["name"], "type": target["type"],
                      "filename": target.get("filename", [])}
        groups = target.get("target_sources")
        if not isinstance(groups, list):
            raise SourceAuditError(f"target {target_id} has no target_sources array")
        for group in groups:
            if not isinstance(group, dict):
                raise SourceAuditError(f"target {target_id} has malformed source metadata")
            language = group.get("language")
            for key, destination in (("sources", sources), ("generated_sources", generated)):
                paths = group.get(key, [])
                if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
                    raise SourceAuditError(f"target {target_id} has malformed {key}")
                for path in paths:
                    if key == "generated_sources":
                        generated.setdefault(path, set()).add(target_id)
                        continue
                    if path.startswith(root_prefix):
                        relative = path[len(root_prefix):]
                        item = indexed.get(relative)
                        if item is None:
                            raise SourceAuditError(f"configured source is missing from inventory: {relative}")
                        record = destination.setdefault(path, {
                            "path": relative,
                            "sha256": item["sha256"],
                            "spdx_header_identifiers": item["spdx_header_identifiers"],
                            "header_license_status": item.get("header_license_status", "NOASSERTION"),
                            "targets": [],
                        })
                        record["targets"].append({**membership, "language": language})
                    else:
                        external.setdefault(path, set()).add(target_id)

    targets_hash = hashlib.sha256(targets_path.read_bytes()).hexdigest()
    source_inventory_sha = inventory.get("source_archive_sha256")
    status_counts: dict[str, int] = {}
    for record in sources.values():
        status = str(record["header_license_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema_version": 1,
        "source_repository": inventory.get("source_repository"),
        "source_commit": inventory.get("source_commit"),
        "source_archive_sha256": source_inventory_sha,
        "meson_targets_sha256": targets_hash,
        "source_root": root_prefix[:-1],
        "scope_limit": "Configured Meson target-source membership only; generated outputs, external inputs, transitive object/link membership, package mapping, and license conclusions require separate evidence.",
        "counts": {
            "meson_targets": len(graph),
            "unique_source_paths": len(sources) + len(external),
            "source_root_paths": len(sources),
            "source_root_paths_with_spdx_header": status_counts.get("IDENTIFIER_PRESENT", 0),
            "source_root_paths_without_recognized_spdx_header": status_counts.get("NOASSERTION", 0),
            "outside_source_root_paths": len(external),
            "generated_source_paths": len(generated),
        },
        "source_files": [sources[path] for path in sorted(sources)],
        "outside_source_root": [
            {"path": path, "target_ids": sorted(ids)} for path, ids in sorted(external.items())
        ],
        "generated_outputs": [
            {"path": path, "target_ids": sorted(ids)} for path, ids in sorted(generated.items())
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True, help="Meson introspection --targets JSON")
    parser.add_argument("--inventory", type=Path, required=True, help="pinned source inventory JSON")
    parser.add_argument("--source-root", required=True, help="absolute source checkout path recorded in Meson JSON")
    parser.add_argument("--output", type=Path, help="write JSON to this path instead of stdout")
    args = parser.parse_args(argv)
    try:
        result = audit_graph(args.targets, args.inventory, args.source_root)
        encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
    except (SourceAuditError, OSError) as exc:
        print(f"mesa_build_source_audit: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
