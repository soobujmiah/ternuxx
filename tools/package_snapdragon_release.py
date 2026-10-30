#!/usr/bin/env python3
"""Create and verify a deterministic, minimal Android Snapdragon runtime archive."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

ROOT_NAME = "llama-b11849"
PINNED_SOURCE_COMMIT = "0ae0e1976670fac25f4e0ed864df30021accc764"
PINNED_BUILDER_IMAGE = (
    "ghcr.io/snapdragon-toolchain/arm64-android@sha256:"
    "e39e5e9c0957550a92c0de756b7556d81196c7c7f7328ed80de252bfb4878adf"
)
REQUIRED = {
    "bin/llama-cli",
    "lib/libggml-hexagon.so",
    "lib/libggml-htp-v73.so",
    "lib/libggml-opencl.so",
    "LICENSE",
}
MAX_EXTRACTED_BYTES = 260_000_000
PINNED_BUILD_FLAGS = [
    "CMAKE_INSTALL_RPATH=$ORIGIN;$ORIGIN/../lib",
    "CMAKE_BUILD_WITH_INSTALL_RPATH=ON",
    "LLAMA_BUILD_SERVER=ON",
    "LLAMA_BUILD_TESTS=OFF",
    "LLAMA_BUILD_EXAMPLES=OFF",
    "LLAMA_BUILD_APP=OFF",
    "LLAMA_BUILD_UI=OFF",
    "LLAMA_USE_PREBUILT_UI=OFF",
]


class PackageError(ValueError):
    pass


def _sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _selected_files(prefix: Path) -> list[tuple[Path, str, int, str]]:
    if not prefix.is_dir() or prefix.is_symlink():
        raise PackageError("install prefix must be a real directory")
    bindir = prefix / "bin"
    if not bindir.is_dir() or bindir.is_symlink():
        raise PackageError("install prefix is missing a regular bin directory")
    candidates = [bindir / "llama-cli", prefix / "LICENSE"]
    libdir = prefix / "lib"
    if not libdir.is_dir() or libdir.is_symlink():
        raise PackageError("install prefix is missing a regular lib directory")
    candidates.extend(sorted(libdir.glob("*.so"), key=lambda path: path.name))
    rows = []
    total = 0
    for path in candidates:
        relative = path.relative_to(prefix).as_posix()
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise PackageError(f"runtime file must be regular and not a symlink: {relative}")
        if relative not in REQUIRED and not (relative.startswith("lib/") and relative.endswith(".so")):
            raise PackageError(f"unexpected runtime file: {relative}")
        size, digest = _sha256(path)
        total += size
        mode = 0o755 if relative == "bin/llama-cli" else 0o644
        rows.append((path, relative, mode, digest))
    names = {row[1] for row in rows}
    missing = sorted(REQUIRED - names)
    if missing:
        raise PackageError("missing required runtime file(s): " + ", ".join(missing))
    if total > MAX_EXTRACTED_BYTES:
        raise PackageError(f"selected runtime exceeds extraction policy ({total} bytes)")
    return rows


def _write_tar(path: Path, rows: list[tuple[Path, str, int, str]], epoch: int) -> None:
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for source, relative, mode, _digest in rows:
                    info = tarfile.TarInfo(f"{ROOT_NAME}/{relative}")
                    info.size = source.stat().st_size
                    info.mode = mode
                    info.mtime = epoch
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    with source.open("rb") as stream:
                        archive.addfile(info, stream)


def _archive_inventory(path: Path) -> dict[str, dict[str, object]]:
    inventory = {}
    total = 0
    try:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                rel = PurePosixPath(member.name)
                if (rel.is_absolute() or ".." in rel.parts or not rel.parts
                        or rel.parts[0] != ROOT_NAME or not member.isfile()):
                    raise PackageError("archive contains an unsafe or non-regular entry")
                relative = rel.relative_to(ROOT_NAME).as_posix()
                if relative in inventory:
                    raise PackageError(f"archive contains duplicate entry: {relative}")
                total += member.size
                if total > MAX_EXTRACTED_BYTES:
                    raise PackageError("archive exceeds installer extraction policy")
                if relative not in REQUIRED and not (relative.startswith("lib/") and relative.endswith(".so")):
                    raise PackageError(f"archive contains unexpected entry: {relative}")
                stream = archive.extractfile(member)
                if stream is None:
                    raise PackageError(f"archive entry is unreadable: {relative}")
                digest = hashlib.sha256()
                size = 0
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                if size != member.size:
                    raise PackageError(f"archive entry size mismatch: {relative}")
                inventory[relative] = {"size_bytes": size, "sha256": digest.hexdigest()}
    except (OSError, tarfile.TarError) as exc:
        raise PackageError(f"cannot read package archive: {exc}") from exc
    missing = sorted(REQUIRED - inventory.keys())
    if missing:
        raise PackageError("archive is missing required file(s): " + ", ".join(missing))
    if sum(item["size_bytes"] for item in inventory.values()) > MAX_EXTRACTED_BYTES:
        raise PackageError("archive exceeds installer extraction policy")
    return inventory


def package(args: argparse.Namespace) -> dict[str, object]:
    if args.source_commit != PINNED_SOURCE_COMMIT:
        raise PackageError("source commit does not match the pinned b11849 release")
    if not re.fullmatch(r"[0-9a-f]{64}", args.packager_sha256):
        raise PackageError("packager SHA-256 must be 64 lowercase hexadecimal characters")
    if not re.fullmatch(r"[0-9a-f]{40}", args.workflow_commit):
        raise PackageError("workflow commit must be a full 40-character lowercase SHA")
    if args.builder_image != PINNED_BUILDER_IMAGE:
        raise PackageError("builder image does not match the pinned Snapdragon toolchain digest")
    if args.source_tag != "b11849":
        raise PackageError("this package contract is pinned to llama.cpp tag b11849")
    if args.source_epoch < 0:
        raise PackageError("source epoch must be non-negative")
    output = args.output_dir
    if output.is_symlink():
        raise PackageError("output directory must not be a symlink")
    output.mkdir(parents=True, exist_ok=True)
    if not output.is_dir():
        raise PackageError("output path must be a directory")
    archive_path = output / f"llama-{args.source_tag}-bin-android-arm64-snapdragon.tar.gz"
    manifest_path = output / "manifest.json"
    checksum_path = output / "SHA256SUMS"
    if any(path.exists() for path in (archive_path, manifest_path, checksum_path)):
        raise PackageError("output package files already exist; refusing to overwrite")
    rows = _selected_files(args.install_prefix)
    _write_tar(archive_path, rows, args.source_epoch)
    try:
        inventory = _archive_inventory(archive_path)
        package_size, package_hash = _sha256(archive_path)
        expected_inventory = {relative: {"size_bytes": path.stat().st_size, "sha256": digest}
                              for path, relative, _mode, digest in rows}
        if inventory != expected_inventory:
            raise PackageError("packaged archive contents do not match selected runtime inputs")
        manifest = {
            "schema_version": 1,
            "artifact": archive_path.name,
            "artifact_size_bytes": package_size,
            "artifact_sha256": package_hash,
            "source_repository": "https://github.com/ggml-org/llama.cpp",
            "source_tag": args.source_tag,
            "source_commit": args.source_commit,
            "source_date_epoch": args.source_epoch,
            "ternuxx_workflow_commit": args.workflow_commit,
            "build_system": "CMake arm64-android-snapdragon-release",
            "build_flags": PINNED_BUILD_FLAGS,
            "builder_image": args.builder_image,
            "packager_sha256": args.packager_sha256,
            "runtime_files": inventory,
            "distribution_state": "internal CI candidate; not a public release asset",
        }
        with manifest_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        with checksum_path.open("x", encoding="ascii") as stream:
            stream.write(f"{package_hash}  {archive_path.name}\n")
        return manifest
    except Exception:
        archive_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        checksum_path.unlink(missing_ok=True)
        raise


def verify(args: argparse.Namespace) -> dict[str, object]:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise PackageError("unsupported package manifest")
    if manifest.get("source_tag") != "b11849" or manifest.get("source_commit") != PINNED_SOURCE_COMMIT:
        raise PackageError("package manifest does not identify the pinned b11849 source")
    if manifest.get("builder_image") != PINNED_BUILDER_IMAGE:
        raise PackageError("package manifest does not identify the pinned Snapdragon toolchain")
    if manifest.get("build_flags") != PINNED_BUILD_FLAGS:
        raise PackageError("package manifest does not identify the pinned CLI-only build")
    if args.archive.name != manifest.get("artifact"):
        raise PackageError("archive filename does not match manifest")
    size, digest = _sha256(args.archive)
    if size != manifest.get("artifact_size_bytes") or digest != manifest.get("artifact_sha256"):
        raise PackageError("archive size or SHA-256 does not match manifest")
    inventory = _archive_inventory(args.archive)
    if inventory != manifest.get("runtime_files"):
        raise PackageError("archive contents do not match manifest runtime inventory")
    return {"status": "verified", "artifact": args.archive.name,
            "artifact_size_bytes": size, "artifact_sha256": digest,
            "runtime_file_count": len(inventory), "source_commit": manifest.get("source_commit"),
            "builder_image": manifest.get("builder_image")}



CANDIDATE_FILES = {
    f"llama-b11849-bin-android-arm64-snapdragon.tar.gz",
    "SHA256SUMS",
    "manifest.json",
    "upstream-source.spdx.json",
    "runtime.spdx.json",
    "toolchain-versions.txt",
    "cmake-user-preset.sha256",
    "packager.sha256",
    "submodules.txt",
    "upstream-LICENSE.txt",
    "reproducibility-verification.json",
    "CANDIDATE.SHA256SUMS",
}


def _spdx_summary(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot read SPDX document {path.name}: {exc}") from exc
    if (not isinstance(data, dict) or data.get("spdxVersion") not in {"SPDX-2.2", "SPDX-2.3"}
            or data.get("dataLicense") != "CC0-1.0"
            or not isinstance(data.get("documentNamespace"), str)
            or not isinstance(data.get("packages"), list) or not data["packages"]):
        raise PackageError(f"{path.name} is not a populated SPDX 2.2/2.3 document")
    identifiers: set[str] = set()
    unresolved_packages = unresolved_files = 0
    for package in data["packages"]:
        if not isinstance(package, dict):
            raise PackageError(f"{path.name} has a malformed package record")
        for field in ("licenseDeclared", "licenseConcluded"):
            value = package.get(field)
            if isinstance(value, str):
                identifiers.add(value)
                if value in {"NOASSERTION", "NONE"}:
                    unresolved_packages += 1
    files = data.get("files", [])
    if not isinstance(files, list):
        raise PackageError(f"{path.name} has a malformed file inventory")
    for file_record in files:
        if not isinstance(file_record, dict):
            raise PackageError(f"{path.name} has a malformed file record")
        values = file_record.get("licenseInfoInFiles", [])
        if not isinstance(values, list):
            raise PackageError(f"{path.name} has malformed per-file license data")
        concluded = file_record.get("licenseConcluded")
        for value in values + ([concluded] if isinstance(concluded, str) else []):
            if isinstance(value, str):
                identifiers.add(value)
                if value in {"NOASSERTION", "NONE"}:
                    unresolved_files += 1
    return {"document": path.name, "package_count": len(data["packages"]),
            "file_count": len(files), "license_identifiers": sorted(identifiers),
            "unresolved_package_license_assertions": unresolved_packages,
            "unresolved_file_license_assertions": unresolved_files}


def verify_candidate(args: argparse.Namespace) -> dict[str, object]:
    """Verify a complete owner-handed-off candidate bundle without changing it."""
    directory = args.candidate_dir
    if directory.is_symlink() or not directory.is_dir():
        raise PackageError("candidate directory must be a real directory")
    members = list(directory.iterdir())
    names = {path.name for path in members}
    if names != CANDIDATE_FILES:
        missing, unexpected = sorted(CANDIDATE_FILES - names), sorted(names - CANDIDATE_FILES)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected: " + ", ".join(unexpected))
        raise PackageError("candidate file set is not exact (" + "; ".join(details) + ")")
    for path in members:
        info = path.lstat()
        empty_submodule_inventory = path.name == "submodules.txt" and info.st_size == 0
        if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
                or info.st_size <= 0 and not empty_submodule_inventory):
            raise PackageError(f"candidate entry must be a regular file with required content: {path.name}")
    checkfile = directory / "CANDIDATE.SHA256SUMS"
    try:
        lines = checkfile.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise PackageError(f"candidate checksum envelope is unreadable: {exc}") from exc
    checksums: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\\x00]+)", line)
        if not match or match.group(2) in checksums:
            raise PackageError("candidate checksum envelope is malformed or duplicated")
        checksums[match.group(2)] = match.group(1)
    expected_names = CANDIDATE_FILES - {"CANDIDATE.SHA256SUMS"}
    if set(checksums) != expected_names:
        raise PackageError("candidate checksum envelope does not cover the exact sidecar set")
    for name, expected_hash in checksums.items():
        _size, actual_hash = _sha256(directory / name)
        if actual_hash != expected_hash:
            raise PackageError(f"candidate checksum mismatch: {name}")

    archive = directory / f"llama-b11849-bin-android-arm64-snapdragon.tar.gz"
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = verify(argparse.Namespace(archive=archive, manifest=manifest_path))
    if (not isinstance(manifest.get("ternuxx_workflow_commit"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", manifest["ternuxx_workflow_commit"])
            or manifest.get("distribution_state") != "internal CI candidate; not a public release asset"):
        raise PackageError("manifest does not identify a pinned internal candidate")

    sums = (directory / "SHA256SUMS").read_text(encoding="ascii")
    expected_sums = f"{result['artifact_sha256']}  {archive.name}\n"
    if sums != expected_sums:
        raise PackageError("SHA256SUMS does not exactly match the verified archive")

    record = json.loads((directory / "reproducibility-verification.json").read_text(encoding="utf-8"))
    if (not isinstance(record, dict) or record.get("schema_version") != 1
            or record.get("status") != "two independent clean builds produced byte-identical package archives"
            or record.get("identical") is not True
            or record.get("license_and_device_release_gates_closed") is not False
            or record.get("publication") != "not published; internal Actions candidate only"
            or record.get("artifact_sha256_attempt_1") != result["artifact_sha256"]
            or record.get("artifact_sha256_attempt_2") != result["artifact_sha256"]
            or record.get("source_commit") != result["source_commit"]
            or record.get("builder_image") != result["builder_image"]
            or record.get("ternuxx_workflow_commit") != manifest["ternuxx_workflow_commit"]):
        raise PackageError("reproducibility record does not match the verified candidate manifest")
    run_id = record.get("workflow_run_id")
    if not (type(run_id) is int and run_id > 0 or isinstance(run_id, str) and re.fullmatch(r"[1-9][0-9]*", run_id)):
        raise PackageError("reproducibility record has an invalid Actions run ID")

    preset_line = (directory / "cmake-user-preset.sha256").read_text(encoding="ascii").strip()
    packager_line = (directory / "packager.sha256").read_text(encoding="ascii").strip()
    digest_line = re.compile(r"^[0-9a-f]{64}  \S.*$")
    if not digest_line.fullmatch(preset_line) or not digest_line.fullmatch(packager_line):
        raise PackageError("candidate source-input checksum sidecar is malformed")
    submodules = (directory / "submodules.txt").read_text(encoding="utf-8").splitlines()
    if any(not re.match(r"^ [0-9a-f]{40}(?: .+)?$", line) for line in submodules):
        raise PackageError("candidate submodule inventory has entries not at the recorded commits")
    if not (directory / "toolchain-versions.txt").read_text(encoding="utf-8").strip():
        raise PackageError("candidate toolchain inventory is empty")
    if not (directory / "upstream-LICENSE.txt").read_text(encoding="utf-8").strip():
        raise PackageError("candidate upstream license text is empty")

    sbom = [_spdx_summary(directory / name)
            for name in ("upstream-source.spdx.json", "runtime.spdx.json")]
    result.update({"candidate_status": "integrity_verified_internal_candidate",
                   "actions_run_id": str(run_id),
                   "sbom": sbom,
                   "unresolved_package_license_assertions": sum(
                       int(item["unresolved_package_license_assertions"]) for item in sbom),
                   "distribution_cleared": False,
                   "distribution_note": "This verifier checks integrity and build records only; owner/legal review, exact candidate device qualification, and release acceptance remain open."})
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("package")
    build.add_argument("--install-prefix", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--source-tag", required=True)
    build.add_argument("--source-commit", required=True)
    build.add_argument("--source-epoch", type=int, required=True)
    build.add_argument("--builder-image", required=True)
    build.add_argument("--packager-sha256", required=True)
    build.add_argument("--workflow-commit", required=True)
    check = commands.add_parser("verify")
    check.add_argument("--archive", type=Path, required=True)
    check.add_argument("--manifest", type=Path, required=True)
    candidate = commands.add_parser("verify-candidate")
    candidate.add_argument("--candidate-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "package":
            result = package(args)
        elif args.command == "verify":
            result = verify(args)
        else:
            result = verify_candidate(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
