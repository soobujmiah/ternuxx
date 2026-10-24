#!/usr/bin/env python3
"""Inventory source-file hashes and SPDX header identifiers in a pinned Mesa archive.

This reports identifiers present in source headers. It does not infer licenses
for files without a header or claim that every inventoried file is compiled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import PurePosixPath
import re
import sys
import tarfile
from typing import BinaryIO


SOURCE_SUFFIXES = {
    ".c", ".h", ".cc", ".hh", ".cpp", ".hpp", ".cxx", ".hxx", ".inc",
    ".inl", ".S", ".s", ".py", ".sh", ".m", ".mm", ".rs", ".cl",
    ".glsl", ".vert", ".frag", ".comp",
}
_SPDX_HEADER = re.compile(
    rb"^\s*(?:(?:/\*+|\*|//|#|<!--|;|--)\s*)?"
    rb"SPDX-License-Identifier:\s*(.*?)(?:\s*\*/|\s*-->)?\s*$"
)


class InventoryError(ValueError):
    """Invalid source archive or provenance input."""


def _sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _header_licenses(data: bytes) -> list[str]:
    found = set()
    for line in data.splitlines()[:80]:
        match = _SPDX_HEADER.match(line)
        if match:
            value = match.group(1).decode("utf-8", "replace").strip()
            if value:
                found.add(value)
    return sorted(found)


def inventory_archive(archive: str, commit: str) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise InventoryError("commit must be a full lowercase Git SHA-1")
    archive_digest = hashlib.sha256()
    with open(archive, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            archive_digest.update(chunk)
    prefix = f"mesa-for-android-container-{commit}/"
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    try:
        with tarfile.open(archive, mode="r:gz") as bundle:
            for member in bundle:
                if not member.isfile():
                    continue
                if not member.name.startswith(prefix):
                    raise InventoryError("archive contains a path outside the pinned source root")
                relative = member.name[len(prefix):]
                path = PurePosixPath(relative)
                if path.is_absolute() or ".." in path.parts or not relative:
                    raise InventoryError("archive contains an unsafe source path")
                if relative in seen:
                    raise InventoryError(f"duplicate archive path: {relative}")
                seen.add(relative)
                if path.suffix not in SOURCE_SUFFIXES:
                    continue
                source = bundle.extractfile(member)
                if source is None:
                    raise InventoryError(f"cannot read archive member: {relative}")
                data = source.read()
                identifiers = _header_licenses(data)
                entries.append({
                    "path": relative,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "spdx_header_identifiers": identifiers,
                    "header_license_status": "IDENTIFIER_PRESENT" if identifiers else "NOASSERTION",
                })
    except (OSError, tarfile.TarError) as exc:
        raise InventoryError(f"cannot read source archive: {type(exc).__name__}") from exc

    entries.sort(key=lambda item: str(item["path"]))
    identifier_counts: dict[str, int] = {}
    for item in entries:
        for identifier in item["spdx_header_identifiers"]:
            identifier_counts[identifier] = identifier_counts.get(identifier, 0) + 1
    return {
        "schema_version": 1,
        "source_repository": "https://github.com/lfdevs/mesa-for-android-container",
        "source_commit": commit,
        "source_archive_sha256": archive_digest.hexdigest(),
        "method": "Hash every candidate source file; inspect only the first 80 lines for comment-style SPDX-License-Identifier headers.",
        "scope_limit": "A candidate-source inventory, not a configured-build source map or license conclusion. NOASSERTION means no recognized header was found; it does not mean unlicensed.",
        "candidate_source_file_count": len(entries),
        "files_with_spdx_header": sum(bool(item["spdx_header_identifiers"]) for item in entries),
        "files_without_spdx_header": sum(not item["spdx_header_identifiers"] for item in entries),
        "spdx_header_file_counts": dict(sorted(identifier_counts.items())),
        "files": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="codeload tar.gz for the pinned source commit")
    parser.add_argument("--commit", required=True, help="full source commit SHA")
    args = parser.parse_args(argv)
    try:
        result = inventory_archive(args.archive, args.commit)
    except InventoryError as exc:
        print(f"mesa_source_inventory: {exc}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
