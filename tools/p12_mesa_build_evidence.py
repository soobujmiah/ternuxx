#!/usr/bin/env python3
"""Capture build-graph and package-staging evidence for the pinned Mesa recipe."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
from typing import BinaryIO

RECIPE_COMMIT = "98f3d6229d61452cef80f8563af7c56ae599dc14"
MESA_SOURCE_ARCHIVE_SHA256 = "5211bd235658a0585740fb2dfbe64e7e8ca3085ad8e423fc333b4d5e0de6fd93"
TERMUX_PACKAGES_COMMIT = "0219ff84b372c9d38aad4e40f448c20ec3d1588e"
BUILDER_IMAGE = "ghcr.io/termux/package-builder@sha256:e2de051a518d8b188c59c4a1ecf357d373b9ccf48d6c06d7681fdc3f61a77287"
EXPECTED_PACKAGE_ARCHITECTURES = {
    "mesa": "aarch64",
    "mesa-dev": "all",
    "mesa-opencl-icd-rusticl": "aarch64",
    "mesa-vulkan-icd-freedreno": "aarch64",
    "mesa-vulkan-icd-swrast": "aarch64",
}
MARKER = "# TERNUXX P12 build-evidence capture (audit only)"
_HELPER = r'''# TERNUXX P12 build-evidence capture (audit only)
_ternuxx_capture_meson() {
	[[ "${TERNUXX_MESA_BUILD_CAPTURE:-0}" == "1" ]] || return 0
	local build_dir="$1" role="$2"
	local evidence_root="${TERNUXX_MESA_EVIDENCE_DIR:-$HOME/p12-mesa-evidence}"
	local evidence_dir="$evidence_root/${TERMUX_ARCH}/${role}"
	local -a meson_command=()
	read -r -a meson_command <<< "$TERMUX_MESON"
	if [[ ${#meson_command[@]} -eq 0 ]]; then
		echo "TERMUX_MESON is empty; cannot capture Meson evidence" >&2
		return 1
	fi
	mkdir -p "$evidence_dir"
	"${meson_command[@]}" introspect "$build_dir" --projectinfo > "$evidence_dir/meson-projectinfo.json"
	"${meson_command[@]}" introspect "$build_dir" --targets > "$evidence_dir/meson-targets.json"
	"${meson_command[@]}" introspect "$build_dir" --buildoptions > "$evidence_dir/meson-buildoptions.json"
	"${meson_command[@]}" introspect "$build_dir" --dependencies > "$evidence_dir/meson-dependencies.json"
	"${meson_command[@]}" introspect "$build_dir" --tests > "$evidence_dir/meson-tests.json"
	ninja -C "$build_dir" -t commands > "$evidence_dir/ninja-commands.txt"
	ninja -C "$build_dir" -t targets all > "$evidence_dir/ninja-targets.txt"
	if ! "${meson_command[@]}" install --dry-run --no-rebuild -C "$build_dir" > "$evidence_dir/meson-install-plan.txt" 2>&1; then
		echo "Meson install dry-run failed; refusing an incomplete package-provenance capture" >&2
		return 1
	fi
	cp "$build_dir/build.ninja" "$evidence_dir/build.ninja"
	if [[ -f "$build_dir/meson-logs/meson-log.txt" ]]; then
		cp "$build_dir/meson-logs/meson-log.txt" "$evidence_dir/meson-log.txt"
	fi
	git -C "$TERMUX_PKG_SRCDIR" rev-parse HEAD > "$evidence_dir/source-commit.txt"
	python3 - "$build_dir" "$TERMUX_PKG_SRCDIR" "$evidence_dir" <<'PY_CAPTURE'
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

build_dir, source_dir, evidence_dir = map(Path, sys.argv[1:])
build_root = build_dir.resolve()
source_root = source_dir.resolve()
targets = json.loads((evidence_dir / "meson-targets.json").read_text(encoding="utf-8"))
text_suffixes = {".c", ".cc", ".cpp", ".h", ".hpp", ".inc", ".py", ".rs", ".xml"}
generated = set()
for target in targets if isinstance(targets, list) else []:
    if not isinstance(target, dict):
        continue
    candidates = target.get("filename", [])
    if isinstance(candidates, str):
        candidates = [candidates]
    for source in target.get("target_sources", []):
        if isinstance(source, dict):
            generated_sources = source.get("generated_sources", [])
            if isinstance(generated_sources, list):
                candidates += generated_sources
    for item in candidates:
        if isinstance(item, str):
            path = Path(item)
            if not path.is_absolute():
                path = build_root / path
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(build_root)
            except (OSError, ValueError):
                continue
            if resolved.is_file() and resolved.suffix.lower() in text_suffixes:
                generated.add(resolved)
for path in build_root.rglob("*.rs"):
    if not path.is_file() or not ("rusticl_" in path.name or path.name == "lib.rs"):
        continue
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(build_root)
    except (OSError, ValueError):
        continue
    generated.add(resolved)

def file_record(path, root, kind):
    data = path.read_bytes()
    binary = b"\0" in data[:4096]
    head = "" if binary else data[:65536].decode("utf-8", "replace")
    identifiers = sorted(set(re.findall(r"SPDX-License-Identifier:\s*([^\s*]+)", head)))
    copyrights = sorted(set(re.findall(r"Copyright[^\n]{0,240}", head, re.IGNORECASE)))[:16]
    return {"path": path.relative_to(root).as_posix(), "kind": kind,
            "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "spdx_header_identifiers": identifiers,
            "header_license_status": "BINARY_NOT_SCANNED" if binary else ("IDENTIFIER_PRESENT" if identifiers else "NOASSERTION"),
            "copyright_header_lines": copyrights}

generated_records = [file_record(path, build_root, "generated-build-output")
                     for path in sorted(generated)]
rusticl_root = source_root / "src/gallium/frontends/rusticl"
rust_inputs = []
if rusticl_root.is_dir():
    for path in sorted(rusticl_root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(source_root)
        except (OSError, ValueError):
            continue
        rust_inputs.append(file_record(resolved, source_root, "rusticl-source-input"))
registry_archives = []
cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))).resolve()
registry = cargo_home / "registry/cache"
if registry.is_dir():
    for path in sorted(registry.rglob("*.crate")):
        if path.is_file() and not path.is_symlink():
            registry_archives.append({"path": path.relative_to(cargo_home).as_posix(),
                                      "size": path.stat().st_size,
                                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
rust_versions = {}
for executable in ("cargo", "rustc"):
    try:
        rust_versions[executable] = subprocess.check_output([executable, "--version"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        rust_versions[executable] = "unavailable"
external_paths = set()
for line in (build_root / "build.ninja").read_text(encoding="utf-8").splitlines():
    if not line.startswith("build "):
        continue
    _, separator, edge = line[6:].partition(": ")
    if not separator:
        continue
    _, separator, inputs = edge.partition(" ")
    if not separator:
        continue
    mode = "explicit"
    for section in re.split(r" (\|@|\|\||\|) ", inputs):
        if section in {"|", "||", "|@"}:
            mode = section
        elif mode and section:
            for raw in section.split():
                if not raw.startswith("/"):
                    continue
                path = Path("/" + raw.lstrip("/"))
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(source_root)
                    continue
                except ValueError:
                    pass
                except OSError:
                    continue
                try:
                    resolved.relative_to(build_root)
                    continue
                except ValueError:
                    pass
                if resolved.is_file():
                    external_paths.add(resolved)
def package_owner(path):
    query_tool = shutil.which("dpkg-query")
    if not query_tool:
        return "unresolved", "unresolved", None
    admin_dirs = []
    for variable in ("TERMUX_PREFIX", "PREFIX"):
        value = os.environ.get(variable)
        if value:
            candidate = Path(value) / "var/lib/dpkg"
            if candidate.is_dir() and candidate not in admin_dirs:
                admin_dirs.append(candidate)
    hostbuild = os.environ.get("TERMUX_PKG_HOSTBUILD_DIR")
    if hostbuild:
        candidate = Path(hostbuild) / "ubuntu_packages/var/lib/dpkg"
        if candidate.is_dir() and candidate not in admin_dirs:
            admin_dirs.append(candidate)
    for admin in [*admin_dirs, None]:
        base = [query_tool]
        if admin is not None:
            base.extend(["--admindir", str(admin)])
        try:
            lines = subprocess.check_output([*base, "-S", str(path)], text=True,
                                            stderr=subprocess.DEVNULL).splitlines()
            match = next((line for line in lines if ": " in line), "")
            package = match.partition(": ")[0].strip()
            if not package:
                continue
            version = subprocess.check_output([*base, "-W", "-f=${Version}", package],
                                              text=True, stderr=subprocess.DEVNULL).strip()
            return package, version or "unresolved", str(admin) if admin is not None else None
        except (OSError, subprocess.CalledProcessError, StopIteration):
            continue
    return "unresolved", "unresolved", None

external_inputs = []
for path in sorted(external_paths):
    owner, version, package_db = package_owner(path)
    record = file_record(path, Path("/"), "external-build-input")
    record["absolute_path"] = str(path)
    record["package"] = owner
    record["package_version"] = version
    if package_db is not None:
        record["package_database"] = package_db
    external_inputs.append(record)
report = {"schema_version": 2, "generated_text_outputs": generated_records,
          "rust_generated_outputs": [item for item in generated_records if item["path"].endswith(".rs")],
          "rust_source_inputs": rust_inputs, "cargo_registry_archives": registry_archives,
          "external_build_inputs": external_inputs, "rust_tool_versions": rust_versions,
          "scope_limit": "Hashes and leading notice metadata for generated text outputs, Rusticl source inputs, Cargo archives, external build inputs and package-owner/version candidates; hashes all staged .deb archives and captures small shipped license/notice text. This is provenance evidence, not a complete license conclusion."}
(evidence_dir / "generated-output-and-rust-provenance.json").write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY_CAPTURE
}
'''


class EvidenceError(RuntimeError):
    pass


def instrument_recipe(recipe: Path) -> None:
    if recipe.is_symlink() or not recipe.is_file():
        raise EvidenceError("recipe must be an existing regular file")
    text = recipe.read_text(encoding="utf-8")
    if f"_COMMIT={RECIPE_COMMIT}" not in text:
        raise EvidenceError("recipe does not pin the expected Mesa source commit")
    if MARKER in text:
        if (text.count(MARKER) != 1
                or "_ternuxx_capture_meson \"$TERMUX_PKG_HOSTBUILD_DIR/build\" host" not in text
                or "unset BINDGEN_EXTRA_CLANG_ARGS LLVM_CONFIG\n\t_ternuxx_capture_meson \"$TERMUX_PKG_BUILDDIR\" target" not in text):
            raise EvidenceError("existing instrumentation is incomplete or duplicated")
        return

    helper_anchor = "termux_step_host_build() {\n"
    host_anchor = "\t$TERMUX_MESON install -C build\n"
    target_anchor = '\tunset BINDGEN_EXTRA_CLANG_ARGS LLVM_CONFIG\n}'
    if any(text.count(anchor) != 1 for anchor in (helper_anchor, host_anchor, target_anchor)):
        raise EvidenceError("pinned Mesa recipe structure changed; refusing to patch it")
    text = text.replace(helper_anchor, _HELPER + "\n" + helper_anchor, 1)
    text = text.replace(host_anchor, host_anchor + '\t_ternuxx_capture_meson "$TERMUX_PKG_HOSTBUILD_DIR/build" host\n', 1)
    text = text.replace(target_anchor, '\tunset BINDGEN_EXTRA_CLANG_ARGS LLVM_CONFIG\n\t_ternuxx_capture_meson "$TERMUX_PKG_BUILDDIR" target\n}', 1)
    recipe.write_text(text, encoding="utf-8")


def _sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _payload_manifest(package: Path, dpkg_deb: str) -> list[dict[str, object]]:
    process = subprocess.Popen([dpkg_deb, "--fsys-tarfile", str(package)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    assert process.stdout is not None
    records: list[dict[str, object]] = []
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|*") as archive:
            for member in archive:
                raw_name = member.name
                while raw_name.startswith("./"):
                    raw_name = raw_name[2:]
                path = PurePosixPath(raw_name)
                if path.is_absolute() or ".." in path.parts:
                    raise EvidenceError(f"unsafe package path in {package.name}")
                record: dict[str, object] = {
                    "path": path.as_posix() if raw_name else ".",
                    "mode": member.mode,
                    "size": member.size,
                }
                if member.isfile():
                    source = archive.extractfile(member)
                    if source is None:
                        raise EvidenceError(f"cannot read package payload in {package.name}")
                    with source:
                        record["type"] = "file"
                        is_notice = (path.name.lower() in {"copyright", "license", "licence", "copying", "notice"}
                                     or path.name.lower().startswith(("license.", "licence.", "notice.")))
                        if is_notice and member.size <= 1024 * 1024:
                            content = source.read(1024 * 1024 + 1)
                            record["sha256"] = hashlib.sha256(content).hexdigest()
                            record["notice_text_sha256"] = record["sha256"]
                            record["notice_text"] = content.decode("utf-8", "replace")
                        else:
                            record["sha256"] = _sha256_stream(source)
                            if is_notice:
                                record["notice_text_status"] = "oversize-not-captured"
                elif member.issym():
                    record["type"] = "symlink"
                    record["link_target"] = member.linkname
                elif member.islnk():
                    record["type"] = "hardlink"
                    record["link_target"] = member.linkname
                elif member.isdir():
                    record["type"] = "directory"
                else:
                    record["type"] = "other"
                records.append(record)
    except (tarfile.TarError, OSError) as exc:
        process.kill()
        process.wait()
        raise EvidenceError(f"cannot inspect payload in {package.name}: {type(exc).__name__}") from exc
    process.stdout.close()
    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    if process.stderr:
        process.stderr.close()
    status = process.wait()
    if status != 0:
        raise EvidenceError(f"dpkg-deb could not read {package.name}: {stderr[-500:]}")
    return records


def package_manifests(packages_dir: Path, output_dir: Path, *, dpkg_deb: str | None = None,
                      expected_packages: set[str] | None = None) -> int:
    if packages_dir.is_symlink() or not packages_dir.is_dir():
        raise EvidenceError("packages directory must be an existing non-symlink directory")
    if output_dir.is_symlink():
        raise EvidenceError("output directory must not be a symlink")
    executable = dpkg_deb or shutil.which("dpkg-deb")
    if not executable:
        raise EvidenceError("dpkg-deb is required")
    staged_packages = sorted(path for path in packages_dir.glob("*.deb") if path.is_file() and not path.is_symlink())
    if not staged_packages:
        raise EvidenceError("no regular .deb packages found")
    other_staging_packages: list[str] = []
    packages = staged_packages
    if expected_packages is not None:
        selected = [path for path in staged_packages if path.name.split("_", 1)[0] in expected_packages]
        actual_names = {path.name.split("_", 1)[0] for path in selected}
        if actual_names != expected_packages or len(actual_names) != len(selected):
            raise EvidenceError(
                f"requested package set mismatch: expected {sorted(expected_packages)}, "
                f"found {sorted(actual_names)} in {len(selected)} matching archives")
        packages = selected
        other_staging_packages = sorted(path.name for path in staged_packages if path not in selected)
    output_dir.mkdir(parents=True, exist_ok=True)
    staging_archives: list[dict[str, object]] = []
    for archive_path in staged_packages:
        result = subprocess.run([executable, "--field", str(archive_path)], capture_output=True,
                                text=True, timeout=30, check=False)
        if result.returncode:
            raise EvidenceError(f"dpkg-deb could not read staging metadata for {archive_path.name}")
        fields: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if line and not line[0].isspace() and ":" in line:
                key, value = line.split(":", 1)
                fields[key] = value.strip()
        if not all(fields.get(key) for key in ("Package", "Version", "Architecture")):
            raise EvidenceError(f"staging package metadata incomplete for {archive_path.name}")
        staging_archives.append({
            "filename": archive_path.name, "name": fields["Package"],
            "version": fields["Version"], "architecture": fields["Architecture"],
            "size": archive_path.stat().st_size, "archive_sha256": _sha256_file(archive_path),
        })
    manifest: dict[str, object] = {"schema_version": 2, "packages": [],
                                   "other_staging_packages": other_staging_packages,
                                   "staging_archives": staging_archives}
    for package in packages:
        result = subprocess.run([executable, "--field", str(package)], capture_output=True,
                                text=True, timeout=30, check=False)
        if result.returncode:
            raise EvidenceError(f"dpkg-deb could not read control metadata for {package.name}")
        fields: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if line and not line[0].isspace() and ":" in line:
                key, value = line.split(":", 1)
                fields[key] = value.strip()
        if not all(fields.get(key) for key in ("Package", "Version", "Architecture")):
            raise EvidenceError(f"package metadata incomplete for {package.name}")
        if expected_packages is not None and fields["Package"] not in expected_packages:
            raise EvidenceError(f"package control name does not match requested staging archive {package.name}")
        with package.open("rb") as stream:
            package_hash = _sha256_stream(stream)
        package_record = {
            "name": fields["Package"],
            "version": fields["Version"],
            "architecture": fields["Architecture"],
            "filename": package.name,
            "archive_sha256": package_hash,
            "control": {key: fields[key] for key in sorted(fields)},
            "files": _payload_manifest(package, executable),
        }
        manifest["packages"].append(package_record)  # type: ignore[union-attr]
    if expected_packages is not None:
        recorded_names = [record["name"] for record in manifest["packages"]]  # type: ignore[index]
        if set(recorded_names) != expected_packages or len(recorded_names) != len(expected_packages):
            raise EvidenceError("requested package control records are missing or duplicated")
    (output_dir / "package-staging-manifests.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(packages)


def validate_capture(evidence_dir: Path) -> None:
    """Validate provenance metadata, configured graphs, and expected split packages."""
    if evidence_dir.is_symlink() or not evidence_dir.is_dir():
        raise EvidenceError("evidence directory must be an existing non-symlink directory")

    def read_json(path: Path) -> object:
        if path.is_symlink() or not path.is_file():
            raise EvidenceError(f"required evidence file is missing or unsafe: {path.name}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceError(f"invalid JSON evidence file: {path.name}") from exc

    metadata = read_json(evidence_dir / "build-metadata.json")
    if not isinstance(metadata, dict):
        raise EvidenceError("build metadata must be an object")
    expected_metadata = {
        "termux_packages_commit": TERMUX_PACKAGES_COMMIT,
        "mesa_source_commit": RECIPE_COMMIT,
        "builder_image": BUILDER_IMAGE,
        "target_architecture": "aarch64",
    }
    for key, expected in expected_metadata.items():
        if metadata.get(key) != expected:
            raise EvidenceError(f"build metadata {key} does not match the pinned build")
    commit = metadata.get("ternuxx_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise EvidenceError("build metadata has an invalid Ternuxx commit")
    workflow_run = metadata.get("workflow_run")
    if not isinstance(workflow_run, str) or not re.fullmatch(
            r"https://github\.com/soobujmiah/ternuxx/actions/runs/[0-9]+", workflow_run):
        raise EvidenceError("build metadata has an invalid workflow run URL")

    for role in ("host", "target"):
        role_dir = evidence_dir / "aarch64" / role
        if role_dir.is_symlink() or not role_dir.is_dir():
            raise EvidenceError(f"{role} build evidence directory is missing or unsafe")
        source_commit = role_dir / "source-commit.txt"
        if source_commit.is_symlink() or not source_commit.is_file() \
                or source_commit.read_text(encoding="utf-8").strip() != RECIPE_COMMIT:
            raise EvidenceError(f"{role} build source commit does not match the pinned Mesa commit")
        targets_path = role_dir / "meson-targets.json"
        targets = read_json(targets_path)
        if not isinstance(targets, list) or not targets:
            raise EvidenceError(f"{role} Meson target inventory is empty or malformed")
        for name in ("ninja-commands.txt", "ninja-targets.txt", "build.ninja",
                     "meson-install-plan.txt", "generated-output-and-rust-provenance.json"):
            artifact = role_dir / name
            if artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size == 0:
                raise EvidenceError(f"{role} build graph/provenance evidence is missing or empty: {name}")
        provenance = read_json(role_dir / "generated-output-and-rust-provenance.json")
        if not isinstance(provenance, dict) or provenance.get("schema_version") != 2:
            raise EvidenceError(f"{role} generated-output provenance schema is unsupported")
        for key in ("generated_text_outputs", "rust_generated_outputs", "rust_source_inputs",
                    "cargo_registry_archives", "external_build_inputs"):
            if not isinstance(provenance.get(key), list):
                raise EvidenceError(f"{role} generated-output provenance is missing {key}")
        if not isinstance(provenance.get("rust_tool_versions"), dict):
            raise EvidenceError(f"{role} generated-output provenance is missing Rust tool versions")
        for record in provenance["generated_text_outputs"] + provenance["rust_source_inputs"] + provenance["external_build_inputs"]:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str) \
                    or not isinstance(record.get("sha256"), str) \
                    or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
                raise EvidenceError(f"{role} generated-output provenance has an invalid file record")
        for record in provenance["cargo_registry_archives"]:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str) \
                    or not isinstance(record.get("sha256"), str) \
                    or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
                raise EvidenceError(f"{role} Cargo archive inventory has an invalid record")
        if role == "target" and len(provenance["rust_generated_outputs"]) < 5:
            raise EvidenceError("target provenance does not include all five known Rusticl generated outputs")
        if role == "target" and not provenance["rust_source_inputs"]:
            raise EvidenceError("target provenance does not include Rusticl source inputs")

    target_graph_path = evidence_dir / "aarch64" / "target" / "meson-targets.json"
    target_graph = read_json(target_graph_path)
    source_map = read_json(evidence_dir / "configured-target-source-map.json")
    if not isinstance(source_map, dict) or not isinstance(source_map.get("counts"), dict):
        raise EvidenceError("configured target-source map is malformed")
    counts = source_map["counts"]
    try:
        target_count = len(target_graph) if isinstance(target_graph, list) else 0
        source_root_count = counts["source_root_paths"]
        external_count = counts["outside_source_root_paths"]
        unique_source_count = counts["unique_source_paths"]
        with_spdx_count = counts["source_root_paths_with_spdx_header"]
        without_spdx_count = counts["source_root_paths_without_recognized_spdx_header"]
        generated_count = counts["generated_source_paths"]
    except KeyError as exc:
        raise EvidenceError("configured target-source map is missing count fields") from exc
    numeric_counts = (counts.get("meson_targets"), source_root_count, external_count,
                      unique_source_count, with_spdx_count, without_spdx_count, generated_count)
    if any(type(value) is not int or value < 0 for value in numeric_counts):
        raise EvidenceError("configured target-source map has invalid counts")
    if source_map.get("source_commit") != RECIPE_COMMIT \
            or source_map.get("source_archive_sha256") != MESA_SOURCE_ARCHIVE_SHA256 \
            or source_map.get("meson_targets_sha256") != _sha256_file(target_graph_path):
        raise EvidenceError("configured target-source map does not match the pinned target graph")
    if (counts.get("meson_targets") != target_count or source_root_count <= 0
            or source_root_count + external_count != unique_source_count
            or with_spdx_count + without_spdx_count != source_root_count
            or generated_count < 0):
        raise EvidenceError("configured target-source map counts are inconsistent")

    manifest = read_json(evidence_dir / "package-staging-manifests.json")
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 2
            or not isinstance(manifest.get("packages"), list)
            or not isinstance(manifest.get("staging_archives"), list)
            or not manifest["staging_archives"]):
        raise EvidenceError("package staging manifest or staged archive inventory is malformed")
    staged_archives = {}
    for archive in manifest["staging_archives"]:
        if (not isinstance(archive, dict) or not isinstance(archive.get("name"), str)
                or not isinstance(archive.get("version"), str)
                or not isinstance(archive.get("architecture"), str)
                or not isinstance(archive.get("filename"), str)
                or not archive["filename"].endswith(".deb")
                or type(archive.get("size")) is not int or archive["size"] <= 0
                or not isinstance(archive.get("archive_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", archive["archive_sha256"])):
            raise EvidenceError("staged dependency archive identity/hash is invalid")
        if archive["filename"] in staged_archives:
            raise EvidenceError("staged package archive inventory has duplicate filenames")
        staged_archives[archive["filename"]] = archive
    packages = manifest["packages"]
    names = [item.get("name") for item in packages if isinstance(item, dict)]
    if any(not isinstance(name, str) for name in names) \
            or len(names) != len(packages) or len(names) != len(set(names)) \
            or set(names) != set(EXPECTED_PACKAGE_ARCHITECTURES):
        raise EvidenceError("package staging manifest does not contain the exact five Mesa splits")
    expected_other = sorted(item["filename"] for item in manifest["staging_archives"]
                            if item["name"] not in EXPECTED_PACKAGE_ARCHITECTURES)
    if manifest.get("other_staging_packages") != expected_other:
        raise EvidenceError("other staged archive list does not match the hashed dependency inventory")
    notice_text_found = False
    for package in packages:
        assert isinstance(package, dict)
        name = package["name"]
        architecture = EXPECTED_PACKAGE_ARCHITECTURES[name]
        control = package.get("control")
        if package.get("architecture") != architecture:
            raise EvidenceError(f"package {name} has unexpected architecture {package.get('architecture')!r}")
        if not isinstance(control, dict) or control.get("Package") != name \
                or control.get("Architecture") != architecture \
                or package.get("version") != control.get("Version"):
            raise EvidenceError(f"package {name} control metadata does not match its manifest")
        filename = package.get("filename")
        if not isinstance(filename, str) or filename != f"{name}_{package.get('version')}_{architecture}.deb":
            raise EvidenceError(f"package {name} filename does not match its control metadata")
        if not isinstance(package.get("archive_sha256"), str) \
                or not re.fullmatch(r"[0-9a-f]{64}", package["archive_sha256"]):
            raise EvidenceError(f"package {name} archive hash is invalid")
        staged = staged_archives.get(filename)
        if (not isinstance(staged, dict) or staged.get("name") != name
                or staged.get("version") != package.get("version")
                or staged.get("architecture") != architecture
                or staged.get("archive_sha256") != package["archive_sha256"]):
            raise EvidenceError(f"package {name} does not match its exact staged archive record")
        if not isinstance(package.get("files"), list) or not package["files"]:
            raise EvidenceError(f"package {name} payload manifest is empty or malformed")
        payload_paths: set[str] = set()
        for item in package["files"]:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise EvidenceError(f"package {name} has a malformed payload entry")
            payload_path = PurePosixPath(item["path"])
            if payload_path.is_absolute() or ".." in payload_path.parts \
                    or item["path"] in payload_paths:
                raise EvidenceError(f"package {name} has an unsafe or duplicate payload path")
            payload_paths.add(item["path"])
            if item.get("type") == "file" and (not isinstance(item.get("sha256"), str)
                                                  or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                raise EvidenceError(f"package {name} has an invalid payload file hash")
            if "notice_text" in item:
                if (not isinstance(item["notice_text"], str)
                        or item.get("notice_text_sha256") != item.get("sha256")):
                    raise EvidenceError(f"package {name} has an invalid captured notice text")
                if name == "mesa":
                    notice_text_found = True
    if not notice_text_found:
        raise EvidenceError("mesa package payload does not include captured license/notice text")


def _sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return _sha256_stream(stream)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    instrument = commands.add_parser("instrument", help="add gated capture to the exact pinned recipe")
    instrument.add_argument("--recipe", type=Path, required=True)
    manifests = commands.add_parser("package-manifests", help="hash files in built Debian package payloads")
    manifests.add_argument("--packages-dir", type=Path, required=True)
    manifests.add_argument("--output-dir", type=Path, required=True)
    manifests.add_argument("--expected-packages", nargs="+")
    validate = commands.add_parser("validate-capture", help="validate the complete pinned Mesa capture")
    validate.add_argument("--evidence-dir", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "instrument":
            instrument_recipe(args.recipe)
            print(f"instrumented pinned Mesa recipe: {args.recipe}")
        elif args.command == "package-manifests":
            count = package_manifests(args.packages_dir, args.output_dir,
                                      expected_packages=set(args.expected_packages) if args.expected_packages else None)
            print(f"hashed package staging manifests for {count} archives")
        else:
            validate_capture(args.evidence_dir)
            print("Pinned recipe metadata, host/target build graphs, and five split-package manifests verified.")
    except (EvidenceError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"p12_mesa_build_evidence: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
