#!/usr/bin/env python3
"""Create a package-level SPDX 2.3 inventory from local Debian archives.

The output deliberately does not infer licenses for files or source components.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PACKAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")


class SbomError(RuntimeError):
    pass


def parse_control(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith((" ", "\t")):
            if current is not None:
                fields[current] += " " + line.strip()
            continue
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        current = key.strip()
        if current in fields:
            raise SbomError(f"duplicate Debian control field: {current}")
        fields[current] = value.strip()
    return fields


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_deb(path: Path, *, dpkg_deb: str | None = None) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or path.suffix != ".deb":
        raise SbomError(f"not a regular Debian archive: {path.name}")
    executable = dpkg_deb or shutil.which("dpkg-deb")
    if not executable:
        raise SbomError("dpkg-deb is required to read package control metadata")
    try:
        result = subprocess.run([executable, "--field", str(path)], check=False,
                                capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SbomError(f"cannot inspect {path.name}: {type(exc).__name__}") from exc
    if result.returncode != 0:
        raise SbomError(f"dpkg-deb could not read {path.name}")
    fields = parse_control(result.stdout)
    name, version, architecture = (fields.get(key, "") for key in ("Package", "Version", "Architecture"))
    if not _PACKAGE_NAME.fullmatch(name):
        raise SbomError(f"{path.name} has no valid Package field")
    if not version or any(ord(char) < 32 for char in version):
        raise SbomError(f"{path.name} has no valid Version field")
    if not architecture or any(ord(char) < 32 for char in architecture):
        raise SbomError(f"{path.name} has no valid Architecture field")
    return {
        "name": name,
        "version": version,
        "architecture": architecture,
        "depends": fields.get("Depends"),
        "source": fields.get("Source"),
        "control_license": fields.get("License"),
        "filename": path.name,
        "sha256": _sha256(path),
    }


def build_spdx(packages: list[dict[str, object]], *, document_name: str,
               document_namespace: str, source_info: str, bundle_sha256: str,
               declared_license: str = "NOASSERTION", license_basis: str = "",
               created: str | None = None) -> dict[str, object]:
    if not packages:
        raise SbomError("at least one Debian package is required")
    if not _SHA256.fullmatch(bundle_sha256):
        raise SbomError("bundle SHA-256 must be 64 lowercase hexadecimal characters")
    if not document_name.strip() or not document_namespace.startswith(("https://", "http://")):
        raise SbomError("document name and absolute HTTP(S) namespace are required")
    if not source_info.strip():
        raise SbomError("source provenance is required")
    if declared_license != "NOASSERTION" and not license_basis.strip():
        raise SbomError("a declared license requires its evidence basis")

    package_records: list[dict[str, object]] = []
    relationships: list[dict[str, str]] = []
    seen: set[str] = set()
    for package in sorted(packages, key=lambda item: (str(item["name"]), str(item["architecture"]))):
        name = str(package["name"])
        version = str(package["version"])
        architecture = str(package["architecture"])
        checksum = str(package["sha256"])
        if not _PACKAGE_NAME.fullmatch(name) or not version or not _SHA256.fullmatch(checksum):
            raise SbomError("package metadata contains an invalid name, version, or SHA-256")
        spdx_id = "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]", "-", name)
        if spdx_id in seen:
            raise SbomError(f"duplicate package identity: {name}")
        seen.add(spdx_id)
        control_license = package.get("control_license")
        depends = package.get("depends") or "not present"
        comments = [f"Debian architecture: {architecture}.",
                    f"Debian Depends field: {depends}.",
                    f"Debian Source field: {package.get('source') or 'not present'}.",
                    f"Debian License field: {control_license or 'not present'}."]
        license_comment = "File-level and source-component license analysis was not performed; no package license conclusion is asserted."
        if license_basis:
            license_comment += " Declared-license basis: " + license_basis.strip()
        package_records.append({
            "SPDXID": spdx_id,
            "name": name,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": declared_license,
            "licenseComments": license_comment,
            "copyrightText": "NOASSERTION",
            "packageFileName": str(package["filename"]),
            "sourceInfo": source_info,
            "comment": " ".join(comments),
            "checksums": [{"algorithm": "SHA256", "checksumValue": checksum}],
        })
        relationships.append({"spdxElementId": "SPDXRef-DOCUMENT",
                              "relationshipType": "DESCRIBES", "relatedSpdxElement": spdx_id})

    timestamp = created or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": document_name,
        "documentNamespace": document_namespace,
        "creationInfo": {"creators": ["Tool: Ternuxx Debian package SBOM generator 1.0"],
                         "created": timestamp},
        "comment": (f"Package-level inventory only. Source bundle SHA-256: {bundle_sha256}. "
                    "Package files and transitive source components were not analyzed; "
                    "see per-package licenseConcluded and licenseComments."),
        "documentDescribes": [package["SPDXID"] for package in package_records],
        "packages": package_records,
        "relationships": relationships,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--packages-dir", type=Path, required=True)
    result.add_argument("--document-name", required=True)
    result.add_argument("--document-namespace", required=True)
    result.add_argument("--source-info", required=True)
    result.add_argument("--bundle-sha256", required=True)
    result.add_argument("--declared-license", default="NOASSERTION")
    result.add_argument("--license-basis", default="")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.packages_dir
    if root.is_symlink() or not root.is_dir():
        parser().error("--packages-dir must be an existing non-symlink directory")
    try:
        paths = sorted(root.glob("*.deb"))
        if not paths:
            raise SbomError("--packages-dir contains no .deb files")
        packages = [inspect_deb(path) for path in paths]
        document = build_spdx(packages, document_name=args.document_name,
                              document_namespace=args.document_namespace,
                              source_info=args.source_info, bundle_sha256=args.bundle_sha256,
                              declared_license=args.declared_license,
                              license_basis=args.license_basis)
    except SbomError as exc:
        print(f"deb_package_sbom: {exc}", file=sys.stderr)
        return 2
    json.dump(document, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
