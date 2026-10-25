from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest

from tools.p12_mesa_build_evidence import (
    BUILDER_IMAGE,
    EXPECTED_PACKAGE_ARCHITECTURES,
    MESA_SOURCE_ARCHIVE_SHA256,
    RECIPE_COMMIT,
    TERMUX_PACKAGES_COMMIT,
    EvidenceError,
    instrument_recipe,
    package_manifests,
    validate_capture,
)


class MesaRecipeInstrumentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.recipe = self.root / "build.sh"
        self.recipe.write_text('''_COMMIT=98f3d6229d61452cef80f8563af7c56ae599dc14
termux_step_host_build() {
\t$TERMUX_MESON compile -C build
\t$TERMUX_MESON install -C build
}
termux_step_post_configure() {
\trm -f "$_WRAPPER_BIN/cmake"
}
termux_step_post_make_install() {
\tunset BINDGEN_EXTRA_CLANG_ARGS LLVM_CONFIG
}
''', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_instrumentation_is_gated_and_captures_host_and_target(self) -> None:
        instrument_recipe(self.recipe)
        text = self.recipe.read_text(encoding="utf-8")
        self.assertIn('[[ "${TERNUXX_MESA_BUILD_CAPTURE:-0}" == "1" ]] || return 0', text)
        self.assertIn('_ternuxx_capture_meson "$TERMUX_PKG_HOSTBUILD_DIR/build" host', text)
        self.assertIn('unset BINDGEN_EXTRA_CLANG_ARGS LLVM_CONFIG\n\t_ternuxx_capture_meson "$TERMUX_PKG_BUILDDIR" target', text)
        self.assertNotIn('termux_step_post_configure() {\n\trm -f "$_WRAPPER_BIN/cmake"\n\t_ternuxx_capture_meson', text)
        self.assertIn('local evidence_root="${TERNUXX_MESA_EVIDENCE_DIR:-$HOME/p12-mesa-evidence}"', text)
        self.assertIn('"$evidence_root/${TERMUX_ARCH}/${role}"', text)
        self.assertNotIn('.ternuxx-mesa-evidence', text)
        self.assertIn('ninja -C "$build_dir" -t commands', text)
        self.assertIn('install --dry-run --no-rebuild -C "$build_dir"', text)
        self.assertIn('generated-output-and-rust-provenance.json', text)
        self.assertIn('--targets > "$evidence_dir/meson-targets.json"', text)
        self.assertIn('read -r -a meson_command <<< "$TERMUX_MESON"', text)

    def test_capture_executes_termux_meson_command_and_arguments_as_words(self) -> None:
        instrument_recipe(self.recipe)
        build = self.root / "build"
        build.mkdir()
        generated_source = build / "rusticl_generated.rs"
        generated_source.write_text("// generated fixture\n", encoding="utf-8")
        termux_prefix = self.root / "termux-prefix"
        external_input = termux_prefix / "lib/protocol.xml"
        external_input.parent.mkdir(parents=True)
        external_input.write_text("<protocol/>\n", encoding="utf-8")
        binary_input = self.root / "libfixture.so"
        binary_input.write_bytes(b"\x7fELF\0Copyright fake binary bytes")
        (build / "build.ninja").write_text(
            f"build generated.o: custom {external_input} {binary_input}\n", encoding="utf-8")
        source_root = self.root / "mesa-source"
        rusticl = source_root / "src/gallium/frontends/rusticl"
        rusticl.mkdir(parents=True)
        (rusticl / "Cargo.toml").write_text("[package]\nname='rusticl'\n", encoding="utf-8")
        (rusticl / "meson.build").write_text("project('rusticl')\n", encoding="utf-8")
        (rusticl / "kernel.rs").write_text("// SPDX-License-Identifier: MIT\n", encoding="utf-8")
        (rusticl / "bindings.h").write_text("/* SPDX-License-Identifier: MIT */\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(source_root)], check=True)
        subprocess.run(["git", "-C", str(source_root), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(source_root), "config", "user.email", "fixture@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(source_root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(source_root), "commit", "-qm", "fixture"], check=True)
        dpkg_info = termux_prefix / "var/lib/dpkg/info"
        dpkg_info.mkdir(parents=True)
        (dpkg_info / "fixture-termux-dep.list").write_text(
            "lib/protocol.xml\n", encoding="utf-8")
        fake_meson = self.root / "fake_meson.py"
        fake_meson.write_text(
            "import json, os, sys\n"
            "with open(os.environ['MESON_CALLS'], 'a', encoding='utf-8') as out:\n"
            " out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[-1] == '--targets':\n"
            " print(json.dumps([{'filename': [os.environ['GENERATED_SOURCE']]}]))\n"
            "else:\n"
            " print('{}')\n", encoding="utf-8",
        )
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        fake_ninja = fake_bin / "ninja"
        fake_ninja.write_text("#!/bin/sh\necho fixture\n", encoding="utf-8")
        fake_ninja.chmod(0o700)
        fake_query = fake_bin / "dpkg-query"
        fake_query.write_text("""#!/usr/bin/env python3
import sys
args=sys.argv[1:]
if '-W' in args and args[-1] == 'fixture-termux-dep':
 print('1.2.3')
else:
 raise SystemExit(1)
""", encoding="utf-8")
        fake_query.chmod(0o700)
        calls = self.root / "meson-calls.jsonl"
        env = {
            **os.environ,
            "TERNUXX_MESA_BUILD_CAPTURE": "1",
            "TERNUXX_MESA_EVIDENCE_DIR": str(self.root / "evidence"),
            "TERMUX_MESON": f"{sys.executable} {fake_meson}",
            "TERMUX_ARCH": "aarch64",
            "TERMUX_PKG_SRCDIR": str(source_root),
            "TERMUX_PREFIX": str(termux_prefix),
            "MESON_CALLS": str(calls),
            "GENERATED_SOURCE": str(generated_source),
            "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
            "CARGO_HOME": str(self.root / "cargo-home"),
            "BUILD_DIR": str(build),
        }
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; _ternuxx_capture_meson "$BUILD_DIR" target', "bash", str(self.recipe)],
            env=env, text=True, capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        invocations = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(invocations), 6)
        self.assertEqual(invocations[0][:2], ["introspect", str(build)])
        self.assertEqual(invocations[1][-1], "--targets")
        self.assertIn("--dry-run", invocations[5])
        provenance = json.loads((self.root / "evidence/aarch64/target/generated-output-and-rust-provenance.json").read_text())
        generated = provenance["generated_text_outputs"][0]
        self.assertEqual(generated["sha256"], hashlib.sha256(generated_source.read_bytes()).hexdigest())
        rust_names = {item["path"] for item in provenance["rust_source_inputs"]}
        self.assertEqual(rust_names, {
            "src/gallium/frontends/rusticl/Cargo.toml",
            "src/gallium/frontends/rusticl/bindings.h",
            "src/gallium/frontends/rusticl/kernel.rs",
            "src/gallium/frontends/rusticl/meson.build",
        })
        protocol = next(item for item in provenance["external_build_inputs"]
                        if item["absolute_path"] == str(external_input))
        self.assertEqual(protocol["package"], "fixture-termux-dep")
        self.assertEqual(protocol["package_version"], "1.2.3")
        self.assertEqual(protocol["package_database"], str(termux_prefix / "var/lib/dpkg"))
        self.assertEqual(protocol["package_candidates"], [{
            "name": "fixture-termux-dep", "version": "1.2.3",
            "package_database": str(termux_prefix / "var/lib/dpkg"),
        }])
        binary = next(item for item in provenance["external_build_inputs"]
                      if item["absolute_path"] == str(binary_input))
        self.assertEqual(binary["header_license_status"], "BINARY_NOT_SCANNED")
        self.assertEqual(binary["copyright_header_lines"], [])

    def test_instrumentation_is_idempotent(self) -> None:
        instrument_recipe(self.recipe)
        once = self.recipe.read_text(encoding="utf-8")
        instrument_recipe(self.recipe)
        self.assertEqual(self.recipe.read_text(encoding="utf-8"), once)

    def test_refuses_unpinned_or_changed_recipe(self) -> None:
        self.recipe.write_text(self.recipe.read_text().replace("98f3d6229d61452cef80f8563af7c56ae599dc14", "0" * 40))
        with self.assertRaises(EvidenceError):
            instrument_recipe(self.recipe)


class PackageStagingManifestTests(unittest.TestCase):
    def test_records_package_and_payload_hashes_without_extracting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packages = root / "debs"
            packages.mkdir()
            archive = packages / "mesa_1_aarch64.deb"
            archive.write_bytes(b"fixture deb bytes")
            payload = io.BytesIO()
            with tarfile.open(fileobj=payload, mode="w") as tar:
                data = b"payload bytes"
                info = tarfile.TarInfo("./data/usr/lib/libmesa.so")
                info.size = len(data)
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(data))
                link = tarfile.TarInfo("./data/usr/lib/libmesa-link.so")
                link.type = tarfile.SYMTYPE
                link.linkname = "libmesa.so"
                tar.addfile(link)
                notice = b"Mesa license notice fixture\n"
                notice_info = tarfile.TarInfo("./data/data/com.termux/files/usr/share/doc/mesa/license.rst")
                notice_info.size = len(notice)
                tar.addfile(notice_info, io.BytesIO(notice))
            encoded_tar = base64.b64encode(payload.getvalue()).decode("ascii")
            fake = root / "dpkg-deb-fixture"
            fake.write_text(
                "#!" + Path("/usr/bin/env").as_posix() + " python3\n"
                "import base64, sys\n"
                "if sys.argv[1] == '--field':\n"
                " print('Package: mesa\\nVersion: 1\\nArchitecture: aarch64')\n"
                "elif sys.argv[1] == '--fsys-tarfile':\n"
                f" sys.stdout.buffer.write(base64.b64decode('{encoded_tar}'))\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            output = root / "evidence"
            self.assertEqual(package_manifests(packages, output, dpkg_deb=str(fake)), 1)
            manifest = json.loads((output / "package-staging-manifests.json").read_text())
            package = manifest["packages"][0]
            self.assertEqual(package["name"], "mesa")
            self.assertEqual(package["files"][0]["path"], "data/usr/lib/libmesa.so")
            self.assertEqual(package["files"][0]["sha256"], __import__("hashlib").sha256(b"payload bytes").hexdigest())
            link_record = next(item for item in package["files"] if item["path"].endswith("libmesa-link.so"))
            self.assertEqual(link_record["type"], "symlink")
            self.assertEqual(link_record["link_target"], "libmesa.so")
            notice_record = next(item for item in package["files"] if item["path"].endswith("license.rst"))
            self.assertEqual(notice_record["notice_text"], "Mesa license notice fixture\n")
            self.assertEqual(notice_record["notice_text_sha256"], notice_record["sha256"])

    def test_selects_expected_packages_and_records_other_staging_archives(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packages = root / "debs"
            packages.mkdir()
            (packages / "mesa_1_aarch64.deb").write_bytes(b"mesa archive")
            (packages / "openssl_1_aarch64.deb").write_bytes(b"dependency archive")
            payload = io.BytesIO()
            with tarfile.open(fileobj=payload, mode="w"):
                pass
            encoded_tar = base64.b64encode(payload.getvalue()).decode("ascii")
            fake = root / "dpkg-deb-fixture"
            fake.write_text(
                "#!/" + Path("usr/bin/env").as_posix() + " python3\n"
                "from pathlib import Path\n"
                "import base64, sys\n"
                "name = Path(sys.argv[-1]).name.split('_', 1)[0]\n"
                "if sys.argv[1] == '--field':\n"
                " print(f'Package: {name}\\nVersion: 1\\nArchitecture: aarch64')\n"
                "else:\n"
                f" sys.stdout.buffer.write(base64.b64decode('{encoded_tar}'))\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            output = root / "evidence"

            self.assertEqual(package_manifests(packages, output, dpkg_deb=str(fake),
                                               expected_packages={"mesa"}), 1)
            manifest = json.loads((output / "package-staging-manifests.json").read_text())
            self.assertEqual([item["name"] for item in manifest["packages"]], ["mesa"])
            self.assertEqual(manifest["other_staging_packages"], ["openssl_1_aarch64.deb"])
            dependency_archive = next(item for item in manifest["staging_archives"]
                                      if item["name"] == "openssl")
            self.assertEqual(dependency_archive["archive_sha256"], hashlib.sha256(b"dependency archive").hexdigest())
            with self.assertRaisesRegex(EvidenceError, "requested package set mismatch"):
                package_manifests(packages, output, dpkg_deb=str(fake),
                                  expected_packages={"mesa", "mesa-dev"})
            (packages / "mesa_2_aarch64.deb").write_bytes(b"duplicate mesa archive")
            with self.assertRaisesRegex(EvidenceError, "requested package set mismatch"):
                package_manifests(packages, output, dpkg_deb=str(fake), expected_packages={"mesa"})


class MesaCaptureValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "evidence"
        self.root.mkdir()
        metadata = {
            "termux_packages_commit": TERMUX_PACKAGES_COMMIT,
            "mesa_source_commit": RECIPE_COMMIT,
            "builder_image": BUILDER_IMAGE,
            "target_architecture": "aarch64",
            "ternuxx_commit": "a" * 40,
            "workflow_run": "https://github.com/soobujmiah/ternuxx/actions/runs/123456",
        }
        (self.root / "build-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        for role in ("host", "target"):
            role_dir = self.root / "aarch64" / role
            role_dir.mkdir(parents=True)
            (role_dir / "source-commit.txt").write_text(RECIPE_COMMIT + "\n", encoding="utf-8")
            (role_dir / "meson-targets.json").write_text('[{"name":"mesa"}]\n', encoding="utf-8")
            (role_dir / "ninja-commands.txt").write_text("cc -c mesa.c\n", encoding="utf-8")
            (role_dir / "ninja-targets.txt").write_text("libmesa.so\n", encoding="utf-8")
            (role_dir / "build.ninja").write_text("build libmesa.so\n", encoding="utf-8")
            (role_dir / "meson-install-plan.txt").write_text("dry-run install plan\n", encoding="utf-8")
            rust_records = [{"path": f"rusticl/generated-{index}.rs", "sha256": str(index) * 64}
                            for index in range(1, 6)] if role == "target" else []
            provenance = {
                "schema_version": 2,
                "generated_text_outputs": rust_records,
                "rust_generated_outputs": rust_records,
                "rust_source_inputs": ([{"path": "src/gallium/frontends/rusticl/kernel.rs",
                                         "sha256": "d" * 64}] if role == "target" else []),
                "cargo_registry_archives": [],
                "external_build_inputs": ([{
                    "path": "data/data/com.termux/files/usr/lib/libfixture.so",
                    "absolute_path": "/data/data/com.termux/files/usr/lib/libfixture.so",
                    "sha256": "e" * 64, "package": "fixture-termux-dep",
                    "package_version": "1.2.3",
                    "package_database": "/data/data/com.termux/files/usr/var/lib/dpkg",
                    "package_candidates": [{"name": "fixture-termux-dep", "version": "1.2.3",
                                             "package_database": "/data/data/com.termux/files/usr/var/lib/dpkg"}],
                }] if role == "target" else []),
                "rust_tool_versions": {"cargo": "cargo 1.0", "rustc": "rustc 1.0"},
            }
            (role_dir / "generated-output-and-rust-provenance.json").write_text(
                json.dumps(provenance), encoding="utf-8")
        target_graph_path = self.root / "aarch64" / "target" / "meson-targets.json"
        (self.root / "configured-target-source-map.json").write_text(json.dumps({
            "source_commit": RECIPE_COMMIT,
            "source_archive_sha256": MESA_SOURCE_ARCHIVE_SHA256,
            "meson_targets_sha256": hashlib.sha256(target_graph_path.read_bytes()).hexdigest(),
            "counts": {
                "meson_targets": 1,
                "source_root_paths": 1,
                "outside_source_root_paths": 1,
                "unique_source_paths": 2,
                "source_root_paths_with_spdx_header": 1,
                "source_root_paths_without_recognized_spdx_header": 0,
                "generated_source_paths": 1,
            },
        }), encoding="utf-8")
        packages = []
        for name, architecture in EXPECTED_PACKAGE_ARCHITECTURES.items():
            version = "26.3.0"
            packages.append({
                "name": name,
                "version": version,
                "architecture": architecture,
                "filename": f"{name}_{version}_{architecture}.deb",
                "archive_sha256": "b" * 64,
                "control": {
                    "Package": name,
                    "Version": version,
                    "Architecture": architecture,
                },
                "files": [{"path": "data/usr/lib/libmesa.so", "type": "file",
                           "sha256": "c" * 64}],
            })
        staging_archives = [{"name": item["name"], "version": item["version"],
                             "architecture": item["architecture"], "filename": item["filename"],
                             "size": 1, "archive_sha256": item["archive_sha256"]} for item in packages]
        staging_archives.append({"name": "openssl", "version": "1", "architecture": "aarch64",
                                 "filename": "openssl_1_aarch64.deb", "size": 1,
                                 "archive_sha256": "e" * 64})
        mesa = next(item for item in packages if item["name"] == "mesa")
        mesa["files"].append({"path": "data/share/doc/mesa/license.rst", "type": "file",
                              "sha256": "f" * 64, "notice_text_sha256": "f" * 64,
                              "notice_text": "MIT notice fixture\n"})
        (self.root / "package-staging-manifests.json").write_text(
            json.dumps({"schema_version": 2, "packages": packages,
                        "staging_archives": staging_archives,
                        "other_staging_packages": ["openssl_1_aarch64.deb"]}), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_validates_pinned_graphs_and_split_package_architectures(self) -> None:
        validate_capture(self.root)

    def test_rejects_external_input_with_hidden_multiple_package_owners(self) -> None:
        path = self.root / "aarch64/target/generated-output-and-rust-provenance.json"
        provenance = json.loads(path.read_text(encoding="utf-8"))
        record = provenance["external_build_inputs"][0]
        record["package_candidates"].append({"name": "other-owner", "version": "9",
                                             "package_database": "/other/dpkg"})
        path.write_text(json.dumps(provenance), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "hides multiple package owners"):
            validate_capture(self.root)

    def test_rejects_missing_rust_generated_output_provenance(self) -> None:
        path = self.root / "aarch64/target/generated-output-and-rust-provenance.json"
        provenance = json.loads(path.read_text(encoding="utf-8"))
        provenance["rust_generated_outputs"] = provenance["rust_generated_outputs"][:4]
        path.write_text(json.dumps(provenance), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "all five known Rusticl"):
            validate_capture(self.root)

    def test_rejects_wrong_split_package_architecture(self) -> None:
        path = self.root / "package-staging-manifests.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        package = next(item for item in manifest["packages"] if item["name"] == "mesa-dev")
        package["architecture"] = "aarch64"
        package["control"]["Architecture"] = "aarch64"
        package["filename"] = "mesa-dev_26.3.0_aarch64.deb"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "unexpected architecture"):
            validate_capture(self.root)

    def test_rejects_unpinned_source_commit(self) -> None:
        path = self.root / "aarch64" / "host" / "source-commit.txt"
        path.write_text("0" * 40 + "\n", encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "source commit"):
            validate_capture(self.root)

    def test_rejects_target_source_map_for_a_different_graph(self) -> None:
        path = self.root / "configured-target-source-map.json"
        source_map = json.loads(path.read_text(encoding="utf-8"))
        source_map["meson_targets_sha256"] = "c" * 64
        path.write_text(json.dumps(source_map), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "does not match the pinned target graph"):
            validate_capture(self.root)


if __name__ == "__main__":
    unittest.main()
