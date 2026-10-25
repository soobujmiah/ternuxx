#!/usr/bin/env python3
"""Map configured Mesa generated outputs to their Ninja build-edge inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import re
import sys


class GeneratedAuditError(ValueError):
    """Invalid Ninja graph, generated-output map, or source inventory."""


_MARKERS = re.compile(r" (\|@|\|\||\|) ")


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GeneratedAuditError(f"cannot read JSON input {path.name}: {type(exc).__name__}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _edge_index(build_ninja: str) -> dict[str, dict[str, object]]:
    edges: dict[str, dict[str, object]] = {}
    for line_number, line in enumerate(build_ninja.splitlines(), 1):
        if not line.startswith("build "):
            continue
        output_text, separator, command = line[6:].partition(": ")
        if not separator or not output_text or not command:
            raise GeneratedAuditError(f"malformed Ninja build edge on line {line_number}")
        if "$ " in output_text or "$ " in command:
            raise GeneratedAuditError(f"escaped-space Ninja path is unsupported on line {line_number}")
        outputs = output_text.split()
        rule, separator, inputs_text = command.partition(" ")
        if not separator or not rule:
            raise GeneratedAuditError(f"Ninja edge has no rule or inputs on line {line_number}")
        sections: dict[str, list[str]] = {"explicit": [], "implicit": [],
                                          "order_only": [], "validation": []}
        pieces = _MARKERS.split(inputs_text)
        mode = "explicit"
        for index, piece in enumerate(pieces):
            if index % 2:
                mode = {"|": "implicit", "||": "order_only", "|@": "validation"}[piece]
            elif piece:
                sections[mode].extend(piece.split())
        edge = {"outputs": outputs, "rule": rule, "inputs": sections,
                "line": line_number}
        for output in outputs:
            if output in edges:
                raise GeneratedAuditError(f"duplicate Ninja output edge: {output}")
            edges[output] = edge
    return edges


def _classify_input(raw: str, *, build_root: str, source_root: str,
                    inventory: dict[str, dict[str, object]], generated_paths: set[str]) -> dict[str, object]:
    normalized = posixpath.normpath(raw if raw.startswith("/") else posixpath.join(build_root, raw))
    prefix = source_root.rstrip("/") + "/"
    if normalized.startswith(prefix):
        relative = normalized[len(prefix):]
        record = inventory.get(relative)
        if record is None:
            return {"path": normalized, "kind": "source-unindexed", "inventory_path": relative}
        return {"path": normalized, "kind": "source", "inventory_path": relative,
                "sha256": record["sha256"],
                "spdx_header_identifiers": record.get("spdx_header_identifiers", []),
                "header_license_status": record.get("header_license_status", "NOASSERTION")}
    if normalized in generated_paths:
        return {"path": normalized, "kind": "generated-output"}
    if raw.startswith("/"):
        suffix = Path(normalized).suffix.lower()
        kind = "external-source" if suffix in {".xml", ".json", ".py", ".rs", ".h", ".c", ".cc", ".cpp"} else "external-tool-or-input"
        return {"path": normalized, "kind": kind}
    return {"path": normalized, "kind": "build-intermediate"}


def audit_generated_outputs(build_ninja_path: Path, source_map_path: Path,
                            inventory_path: Path) -> dict[str, object]:
    graph = _read_json(source_map_path)
    inventory_doc = _read_json(inventory_path)
    if not isinstance(graph, dict) or not isinstance(graph.get("generated_outputs"), list):
        raise GeneratedAuditError("source map has no generated_outputs list")
    if not isinstance(inventory_doc, dict) or not isinstance(inventory_doc.get("files"), list):
        raise GeneratedAuditError("source inventory has no files array")
    source_root = graph.get("source_root")
    if not isinstance(source_root, str) or not source_root.startswith("/"):
        raise GeneratedAuditError("source map has no absolute source root")
    source_root = posixpath.normpath(source_root)
    build_root = posixpath.join(posixpath.dirname(source_root), "build")
    inventory: dict[str, dict[str, object]] = {}
    for item in inventory_doc["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise GeneratedAuditError("source inventory contains an invalid file record")
        if item["path"] in inventory:
            raise GeneratedAuditError(f"source inventory repeats path {item['path']}")
        if not isinstance(item.get("sha256"), str):
            raise GeneratedAuditError(f"source inventory has no hash for {item['path']}")
        inventory[item["path"]] = item
    try:
        text = build_ninja_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise GeneratedAuditError("cannot read target build.ninja") from exc
    edges = _edge_index(text)
    generated = graph["generated_outputs"]
    generated_absolute: set[str] = set()
    normalized_items: list[tuple[dict[str, object], str, str]] = []
    for item in generated:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise GeneratedAuditError("source map contains a malformed generated output")
        output = posixpath.normpath(item["path"])
        if not output.startswith(build_root.rstrip("/") + "/"):
            raise GeneratedAuditError(f"generated output is outside the target build root: {output}")
        relative = posixpath.relpath(output, build_root)
        normalized_items.append((item, output, relative))
        generated_absolute.add(output)
    if len(generated_absolute) != len(normalized_items):
        raise GeneratedAuditError("source map repeats a generated output")
    outside_items = graph.get("outside_source_root", [])
    if not isinstance(outside_items, list):
        raise GeneratedAuditError("source map outside_source_root must be a list")

    output_records: list[dict[str, object]] = []
    unmatched: list[str] = []
    external_inputs: set[str] = set()
    tool_inputs: set[str] = set()
    source_inputs: set[str] = set()
    unindexed_sources: set[str] = set()
    build_inputs: set[str] = set()
    for source_item, absolute, relative in normalized_items:
        edge = edges.get(relative)
        if edge is None:
            unmatched.append(absolute)
            continue
        input_records = []
        sections = edge["inputs"]
        assert isinstance(sections, dict)
        for role, paths in sections.items():
            for raw in paths:
                record = _classify_input(raw, build_root=build_root, source_root=source_root,
                                         inventory=inventory, generated_paths=generated_absolute)
                record["role"] = role
                input_records.append(record)
                kind = record["kind"]
                path = str(record["path"])
                if kind == "source": source_inputs.add(path)
                elif kind == "source-unindexed": unindexed_sources.add(path)
                elif kind.startswith("external-"):
                    external_inputs.add(path)
                    if "/bin/" in path or path.startswith("/usr/bin/"):
                        tool_inputs.add(path)
                elif kind in {"generated-output", "build-intermediate"}:
                    build_inputs.add(path)
        output_records.append({"path": absolute, "target_ids": source_item.get("target_ids", []),
                               "ninja_outputs": edge["outputs"], "rule": edge["rule"],
                               "ninja_line": edge["line"], "inputs": input_records})
    if unmatched:
        raise GeneratedAuditError(f"{len(unmatched)} generated outputs have no Ninja build edge")

    outside_records: list[dict[str, object]] = []
    unmatched_outside: list[str] = []
    for item in outside_items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise GeneratedAuditError("source map contains a malformed outside-root input")
        path = posixpath.normpath(item["path"])
        record: dict[str, object] = {"path": path, "target_ids": item.get("target_ids", [])}
        if path.startswith(build_root.rstrip("/") + "/"):
            relative = posixpath.relpath(path, build_root)
            edge = edges.get(relative)
            if edge is None:
                unmatched_outside.append(path)
                record["classification"] = "build-tree-source-without-generator-edge"
            else:
                record["classification"] = "build-tree-generated-source"
                record["ninja_outputs"] = edge["outputs"]
                record["rule"] = edge["rule"]
                record["ninja_line"] = edge["line"]
        else:
            references = []
            for edge in {id(value): value for value in edges.values()}.values():
                sections = edge["inputs"]
                assert isinstance(sections, dict)
                if any(posixpath.normpath(raw if raw.startswith("/") else
                       posixpath.join(build_root, raw)) == path
                       for paths in sections.values() for raw in paths):
                    references.append({"outputs": edge["outputs"], "rule": edge["rule"],
                                       "ninja_line": edge["line"]})
            record["classification"] = "external-input"
            record["ninja_references"] = references
            if not references:
                unmatched_outside.append(path)
        outside_records.append(record)
    if unmatched_outside:
        raise GeneratedAuditError(f"{len(unmatched_outside)} outside-source paths have no Ninja edge: "
                                  + ", ".join(unmatched_outside[:3]))
    return {
        "schema_version": 1,
        "source_commit": graph.get("source_commit"),
        "source_archive_sha256": graph.get("source_archive_sha256"),
        "source_inventory_commit": inventory_doc.get("source_commit"),
        "source_inventory_archive_sha256": inventory_doc.get("source_archive_sha256"),
        "target_build_ninja_sha256": _sha256(build_ninja_path),
        "source_map_sha256": _sha256(source_map_path),
        "scope_limit": "Direct Ninja build-edge inputs for configured generated outputs; this does not infer transitive link inputs or conclude licenses for generated code.",
        "counts": {"generated_outputs": len(output_records),
                   "outputs_with_ninja_edges": len(output_records),
                   "outside_source_root_paths": len(outside_records),
                   "outside_paths_mapped_to_ninja_edges": len(outside_records) - len(unmatched_outside),
                   "unique_source_inputs": len(source_inputs),
                   "unindexed_source_inputs": len(unindexed_sources),
                   "unique_external_inputs": len(external_inputs),
                   "unique_external_tool_or_input_paths": len(tool_inputs),
                   "unique_generated_or_intermediate_inputs": len(build_inputs)},
        "external_inputs": sorted(external_inputs),
        "unindexed_source_inputs": sorted(unindexed_sources),
        "outside_source_root": outside_records,
        "outputs": output_records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-ninja", type=Path, required=True)
    parser.add_argument("--source-map", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit_generated_outputs(args.build_ninja, args.source_map, args.inventory)
        encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
    except (GeneratedAuditError, OSError) as exc:
        print(f"mesa_generated_source_audit: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
