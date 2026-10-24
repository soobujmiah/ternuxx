#!/usr/bin/env python3
"""Build a cautious payload-to-Meson-target candidate map for pinned Mesa."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.p12_mesa_build_evidence import (
    MESA_SOURCE_ARCHIVE_SHA256,
    RECIPE_COMMIT,
    _sha256_file,
)


class PackageTargetAuditError(ValueError):
    """Invalid package manifest, configured graph, or source map."""


def _read_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file():
        raise PackageTargetAuditError(f"input is missing or unsafe: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageTargetAuditError(f"invalid JSON input: {path.name}") from exc


def audit_packages(packages_path: Path, targets_path: Path, source_map_path: Path) -> dict[str, object]:
    packages_doc = _read_json(packages_path)
    targets = _read_json(targets_path)
    source_map = _read_json(source_map_path)
    if not isinstance(packages_doc, dict) or not isinstance(packages_doc.get("packages"), list):
        raise PackageTargetAuditError("package manifest has no packages array")
    if not isinstance(targets, list) or not targets:
        raise PackageTargetAuditError("Meson target graph must be a nonempty array")
    if not isinstance(source_map, dict) or not isinstance(source_map.get("source_files"), list):
        raise PackageTargetAuditError("configured source map has no source_files array")
    if source_map.get("source_commit") != RECIPE_COMMIT \
            or source_map.get("source_archive_sha256") != MESA_SOURCE_ARCHIVE_SHA256 \
            or source_map.get("meson_targets_sha256") != _sha256_file(targets_path):
        raise PackageTargetAuditError("source map does not match the pinned source and target graph")

    target_by_id: dict[str, dict[str, object]] = {}
    output_by_basename: dict[str, list[dict[str, str]]] = {}
    for target in targets:
        if not isinstance(target, dict) or not all(
                isinstance(target.get(key), str) for key in ("id", "name", "type")):
            raise PackageTargetAuditError("Meson graph contains a malformed target")
        target_id = target["id"]
        if target_id in target_by_id:
            raise PackageTargetAuditError(f"Meson graph repeats target ID {target_id}")
        target_by_id[target_id] = target
        filenames = target.get("filename", [])
        if isinstance(filenames, str):
            filenames = [filenames]
        if not isinstance(filenames, list) or any(not isinstance(path, str) for path in filenames):
            raise PackageTargetAuditError(f"target {target_id} has malformed output filenames")
        for filename in filenames:
            basename = PurePosixPath(filename).name
            if not basename:
                continue
            output_by_basename.setdefault(basename, []).append({
                "target_id": target_id,
                "target_name": target["name"],
                "target_type": target["type"],
                "filename": filename,
            })

    target_sources: dict[str, list[dict[str, object]]] = {key: [] for key in target_by_id}
    for source in source_map["source_files"]:
        if not isinstance(source, dict) or not isinstance(source.get("targets"), list):
            raise PackageTargetAuditError("source map contains malformed source membership")
        for membership in source["targets"]:
            if not isinstance(membership, dict) or not isinstance(membership.get("id"), str):
                raise PackageTargetAuditError("source map contains malformed target membership")
            target_id = membership["id"]
            if target_id not in target_sources:
                raise PackageTargetAuditError(f"source map refers to unknown target {target_id}")
            target_sources[target_id].append({
                "path": source.get("path"),
                "sha256": source.get("sha256"),
                "spdx_header_identifiers": source.get("spdx_header_identifiers", []),
                "header_license_status": source.get("header_license_status", "NOASSERTION"),
                "language": membership.get("language"),
            })

    external_by_target: dict[str, list[str]] = {key: [] for key in target_by_id}
    for item in source_map.get("outside_source_root", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) \
                or not isinstance(item.get("target_ids"), list):
            raise PackageTargetAuditError("source map contains malformed outside-root inputs")
        for target_id in item["target_ids"]:
            if target_id not in external_by_target:
                raise PackageTargetAuditError(f"source map refers to unknown target {target_id}")
            external_by_target[target_id].append(item["path"])

    generated_by_target: dict[str, list[str]] = {key: [] for key in target_by_id}
    for item in source_map.get("generated_outputs", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) \
                or not isinstance(item.get("target_ids"), list):
            raise PackageTargetAuditError("source map contains malformed generated outputs")
        for target_id in item["target_ids"]:
            if target_id not in generated_by_target:
                raise PackageTargetAuditError(f"source map refers to unknown target {target_id}")
            generated_by_target[target_id].append(item["path"])

    package_rows: list[dict[str, object]] = []
    matched_outputs: set[tuple[str, str]] = set()
    candidate_count = ambiguous_count = unmatched_file_count = 0
    symlink_candidate_count = 0
    file_count = symlink_count = directory_count = other_type_count = 0
    for package in packages_doc["packages"]:
        if not isinstance(package, dict) or not isinstance(package.get("files"), list):
            raise PackageTargetAuditError("package record has no payload file list")
        entries: list[dict[str, object]] = []
        seen_paths: set[str] = set()
        payload_by_path = {item.get("path"): item for item in package["files"]
                           if isinstance(item, dict) and isinstance(item.get("path"), str)}
        candidate_by_path: dict[str, dict[str, object]] = {}
        ambiguous_by_path: dict[str, list[dict[str, str]]] = {}
        for item in package["files"]:
            if not isinstance(item, dict) or item.get("type") != "file" \
                    or not isinstance(item.get("path"), str):
                continue
            basename = PurePosixPath(item["path"]).name
            output_candidates = output_by_basename.get(basename, [])
            unique_output_identities = {
                (candidate["target_id"], candidate["filename"])
                for candidate in output_candidates
            }
            if len(unique_output_identities) == 1:
                target_id, output_filename = next(iter(unique_output_identities))
                target_output = next(candidate for candidate in output_candidates
                                     if candidate["target_id"] == target_id
                                     and candidate["filename"] == output_filename)
                candidate_by_path[item["path"]] = {
                    "target_id": target_id,
                    "target_output": target_output,
                    "target_source_membership": target_sources[target_id],
                    "external_inputs": sorted(set(external_by_target[target_id])),
                    "generated_outputs": sorted(set(generated_by_target[target_id])),
                }
            elif unique_output_identities:
                ambiguous_by_path[item["path"]] = sorted(
                    output_candidates, key=lambda candidate: candidate["target_id"])
        for payload in package["files"]:
            if not isinstance(payload, dict) or not isinstance(payload.get("path"), str):
                raise PackageTargetAuditError("package contains a malformed payload entry")
            path = payload["path"]
            pure_path = PurePosixPath(path)
            if pure_path.is_absolute() or ".." in pure_path.parts or path in seen_paths:
                raise PackageTargetAuditError(f"package contains unsafe or duplicate payload path: {path}")
            seen_paths.add(path)
            payload_type = payload.get("type")
            if payload_type == "file":
                file_count += 1
            elif payload_type == "symlink":
                symlink_count += 1
            elif payload_type == "directory":
                directory_count += 1
            else:
                other_type_count += 1
            if payload_type == "file" and path in candidate_by_path:
                candidate = candidate_by_path[path]
                target_id = candidate["target_id"]
                chosen = candidate["target_output"]
                matched_outputs.add((target_id, chosen["filename"]))
                candidate_count += 1
                entries.append({
                    "payload": payload,
                    "association": "unique-output-basename-candidate",
                    "target": chosen,
                    "target_source_membership": candidate["target_source_membership"],
                    "external_inputs": candidate["external_inputs"],
                    "generated_outputs": candidate["generated_outputs"],
                })
            elif payload_type == "file" and path in ambiguous_by_path:
                ambiguous_count += 1
                entries.append({
                    "payload": payload,
                    "association": "ambiguous-output-basename",
                    "candidate_targets": ambiguous_by_path[path],
                })
            elif payload_type == "symlink":
                link_target = payload.get("link_target")
                if not isinstance(link_target, str):
                    raise PackageTargetAuditError(f"package symlink has invalid target: {path}")
                pure_target = PurePosixPath(link_target)
                if pure_target.is_absolute() or ".." in pure_target.parts:
                    entries.append({
                        "payload": payload,
                        "association": "symlink-target-outside-package-path-scope",
                    })
                    continue
                resolved_name = (pure_path.parent / pure_target).as_posix()
                resolved_entry = payload_by_path.get(resolved_name)
                resolved_candidate = candidate_by_path.get(resolved_name)
                if resolved_entry is not None and resolved_entry.get("type") == "file" \
                        and resolved_candidate is not None:
                    symlink_candidate_count += 1
                    entries.append({
                        "payload": payload,
                        "association": "symlink-resolves-to-payload-file-candidate",
                        "resolves_to_payload_path": resolved_name,
                        "target": resolved_candidate["target_output"],
                        "target_source_membership": resolved_candidate["target_source_membership"],
                        "external_inputs": resolved_candidate["external_inputs"],
                        "generated_outputs": resolved_candidate["generated_outputs"],
                    })
                else:
                    entries.append({"payload": payload, "association": "symlink-not-mapped-to-target"})
            else:
                if payload_type == "file":
                    unmatched_file_count += 1
                    association = "file-no-target-output-basename-match"
                elif payload_type == "symlink":
                    association = "symlink-not-mapped-to-target"
                elif payload_type == "directory":
                    association = "directory-not-target-output"
                else:
                    association = "non-file-payload-not-mapped"
                entries.append({"payload": payload, "association": association})
        package_rows.append({
            "name": package.get("name"),
            "version": package.get("version"),
            "architecture": package.get("architecture"),
            "archive_sha256": package.get("archive_sha256"),
            "payload_entries": entries,
        })

    unmatched_outputs = []
    for basename_items in output_by_basename.values():
        for output in basename_items:
            key = (output["target_id"], output["filename"])
            if key not in matched_outputs:
                unmatched_outputs.append(output)
    return {
        "schema_version": 1,
        "source_commit": RECIPE_COMMIT,
        "source_archive_sha256": MESA_SOURCE_ARCHIVE_SHA256,
        "package_manifest_sha256": _sha256_file(packages_path),
        "meson_targets_sha256": _sha256_file(targets_path),
        "configured_target_source_map_sha256": _sha256_file(source_map_path),
        "scope_limit": "Unique output-basename matches are candidates only; Meson target membership is direct configuration evidence. This does not prove install rules, transitive object/source membership, runtime loading, or package license conclusions.",
        "counts": {
            "packages": len(package_rows),
            "payload_entries": sum(len(package["payload_entries"]) for package in package_rows),
            "payload_files": file_count,
            "payload_symlinks": symlink_count,
            "payload_directories": directory_count,
            "payload_other_types": other_type_count,
            "unique_output_basename_candidates": candidate_count,
            "symlinks_resolving_to_candidate_files": symlink_candidate_count,
            "ambiguous_output_basenames": ambiguous_count,
            "files_without_target_basename_match": unmatched_file_count,
            "target_outputs_without_payload_basename_match": len(unmatched_outputs),
        },
        "packages": package_rows,
        "target_outputs_without_payload_basename_match": sorted(
            unmatched_outputs, key=lambda item: (item["target_id"], item["filename"])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", type=Path, required=True, help="package-staging-manifests.json")
    parser.add_argument("--targets", type=Path, required=True, help="target Meson introspection JSON")
    parser.add_argument("--source-map", type=Path, required=True, help="configured target-source map JSON")
    parser.add_argument("--output", type=Path, help="write JSON to this path instead of stdout")
    args = parser.parse_args(argv)
    try:
        result = audit_packages(args.packages, args.targets, args.source_map)
        encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
    except (PackageTargetAuditError, OSError) as exc:
        print(f"mesa_package_target_audit: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
