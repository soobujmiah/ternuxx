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
	cp "$build_dir/build.ninja" "$evidence_dir/build.ninja"
	if [[ -f "$build_dir/meson-logs/meson-log.txt" ]]; then
		cp "$build_dir/meson-logs/meson-log.txt" "$evidence_dir/meson-log.txt"
	fi
	git -C "$TERMUX_PKG_SRCDIR" rev-parse HEAD > "$evidence_dir/source-commit.txt"
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
        if text.count(MARKER) != 1 or "_ternuxx_capture_meson \"$TERMUX_PKG_HOSTBUILD_DIR/build\" host" not in text or "_ternuxx_capture_meson \"$TERMUX_PKG_BUILDDIR\" target" not in text:
            raise EvidenceError("existing instrumentation is incomplete or duplicated")
        return

    helper_anchor = "termux_step_host_build() {\n"
    host_anchor = "\t$TERMUX_MESON install -C build\n"
    target_anchor = '\trm -f "$_WRAPPER_BIN/cmake"\n'
    if any(text.count(anchor) != 1 for anchor in (helper_anchor, host_anchor, target_anchor)):
        raise EvidenceError("pinned Mesa recipe structure changed; refusing to patch it")
    text = text.replace(helper_anchor, _HELPER + "\n" + helper_anchor, 1)
    text = text.replace(host_anchor, host_anchor + '\t_ternuxx_capture_meson "$TERMUX_PKG_HOSTBUILD_DIR/build" host\n', 1)
    text = text.replace(target_anchor, target_anchor + '\t_ternuxx_capture_meson "$TERMUX_PKG_BUILDDIR" target\n', 1)
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
                        record["sha256"] = _sha256_stream(source)
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
    manifest: dict[str, object] = {"schema_version": 1, "packages": [],
                                   "other_staging_packages": other_staging_packages}
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


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    instrument = commands.add_parser("instrument", help="add gated capture to the exact pinned recipe")
    instrument.add_argument("--recipe", type=Path, required=True)
    manifests = commands.add_parser("package-manifests", help="hash files in built Debian package payloads")
    manifests.add_argument("--packages-dir", type=Path, required=True)
    manifests.add_argument("--output-dir", type=Path, required=True)
    manifests.add_argument("--expected-packages", nargs="+")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "instrument":
            instrument_recipe(args.recipe)
            print(f"instrumented pinned Mesa recipe: {args.recipe}")
        else:
            count = package_manifests(args.packages_dir, args.output_dir,
                                      expected_packages=set(args.expected_packages) if args.expected_packages else None)
            print(f"hashed package staging manifests for {count} archives")
    except (EvidenceError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"p12_mesa_build_evidence: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
