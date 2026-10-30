from pathlib import Path
import json
import shutil
import tempfile
import unittest
from types import SimpleNamespace

from tools import package_snapdragon_release as packager


BUILDER_IMAGE = packager.PINNED_BUILDER_IMAGE
SOURCE_COMMIT = packager.PINNED_SOURCE_COMMIT
PACKAGER_SHA = "b" * 64


class SnapdragonPackageTests(unittest.TestCase):
    def _prefix(self, base: Path) -> Path:
        prefix = base / "install"
        (prefix / "bin").mkdir(parents=True)
        (prefix / "lib").mkdir()
        (prefix / "bin/llama-cli").write_bytes(b"fake executable")
        (prefix / "LICENSE").write_text("MIT test fixture\n", encoding="utf-8")
        for name in ("libggml-hexagon.so", "libggml-htp-v73.so", "libggml-opencl.so", "libggml-base.so"):
            (prefix / "lib" / name).write_bytes(name.encode("ascii"))
        return prefix

    def _package(self, prefix: Path, output: Path) -> dict[str, object]:
        args = type("Args", (), {
            "install_prefix": prefix,
            "output_dir": output,
            "source_tag": "b11849",
            "source_commit": SOURCE_COMMIT,
            "source_epoch": 1_760_000_000,
            "builder_image": BUILDER_IMAGE,
            "packager_sha256": PACKAGER_SHA,
            "workflow_commit": "c" * 40,
        })()
        return packager.package(args)

    def test_package_is_byte_reproducible_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = self._prefix(root)
            first = self._package(prefix, root / "first")
            second = self._package(prefix, root / "second")
            self.assertEqual(first["artifact_sha256"], second["artifact_sha256"])
            archive = root / "first" / first["artifact"]
            result = packager.verify(type("Args", (), {
                "archive": archive, "manifest": root / "first/manifest.json"})())
            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["runtime_file_count"], 6)

    def _candidate(self, base: Path) -> Path:
        prefix = self._prefix(base)
        output = base / "candidate"
        manifest = self._package(prefix, output)
        archive = output / manifest["artifact"]
        (output / "upstream-source.spdx.json").write_text(json.dumps({
            "spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT", "name": "upstream",
            "documentNamespace": "https://example.invalid/source",
            "packages": [{"SPDXID": "SPDXRef-Package", "name": "llama.cpp",
                          "licenseDeclared": "MIT", "licenseConcluded": "MIT"}],
            "files": []}), encoding="utf-8")
        (output / "runtime.spdx.json").write_text(json.dumps({
            "spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT", "name": "runtime",
            "documentNamespace": "https://example.invalid/runtime",
            "packages": [{"SPDXID": "SPDXRef-Package", "name": "llama.cpp-runtime",
                          "licenseDeclared": "NOASSERTION", "licenseConcluded": "NOASSERTION"}],
            "files": [{"SPDXID": "SPDXRef-File", "fileName": "libggml.so",
                       "licenseConcluded": "NOASSERTION", "licenseInfoInFiles": ["NOASSERTION"]}]}),
            encoding="utf-8")
        (output / "toolchain-versions.txt").write_text("clang: test\n", encoding="utf-8")
        (output / "cmake-user-preset.sha256").write_text("a" * 64 + "  preset.json\n", encoding="ascii")
        (output / "packager.sha256").write_text("b" * 64 + "  packager.py\n", encoding="ascii")
        (output / "submodules.txt").write_text(" " + "d" * 40 + " ggml\n", encoding="ascii")
        (output / "upstream-LICENSE.txt").write_text("MIT\n", encoding="utf-8")
        (output / "reproducibility-verification.json").write_text(json.dumps({
            "schema_version": 1,
            "status": "two independent clean builds produced byte-identical package archives",
            "workflow_run_id": "40962919123",
            "ternuxx_workflow_commit": "c" * 40,
            "source_commit": SOURCE_COMMIT,
            "builder_image": BUILDER_IMAGE,
            "artifact_sha256_attempt_1": manifest["artifact_sha256"],
            "artifact_sha256_attempt_2": manifest["artifact_sha256"],
            "identical": True,
            "license_and_device_release_gates_closed": False,
            "publication": "not published; internal Actions candidate only",
        }), encoding="utf-8")
        checksum_names = sorted(packager.CANDIDATE_FILES - {"CANDIDATE.SHA256SUMS"})
        lines = [f"{packager._sha256(output / name)[1]}  {name}" for name in checksum_names]
        (output / "CANDIDATE.SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")
        return output

    def _reseal_candidate(self, candidate: Path) -> None:
        names = sorted(packager.CANDIDATE_FILES - {"CANDIDATE.SHA256SUMS"})
        lines = [f"{packager._sha256(candidate / name)[1]}  {name}" for name in names]
        (candidate / "CANDIDATE.SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")

    def test_candidate_verifier_checks_integrity_and_keeps_distribution_uncleared(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = self._candidate(Path(temporary))
            result = packager.verify_candidate(SimpleNamespace(candidate_dir=candidate))
            self.assertEqual(result["candidate_status"], "integrity_verified_internal_candidate")
            self.assertEqual(result["runtime_file_count"], 6)
            self.assertFalse(result["distribution_cleared"])
            self.assertEqual(result["unresolved_package_license_assertions"], 2)
            self.assertEqual(result["sbom"][1]["unresolved_file_license_assertions"], 2)

    def test_candidate_verifier_rejects_missing_or_unexpected_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = self._candidate(Path(temporary))
            (candidate / "runtime.spdx.json").unlink()
            with self.assertRaisesRegex(packager.PackageError, "exact"):
                packager.verify_candidate(SimpleNamespace(candidate_dir=candidate))
        with tempfile.TemporaryDirectory() as temporary:
            candidate = self._candidate(Path(temporary))
            (candidate / "unreviewed.txt").write_text("extra", encoding="utf-8")
            with self.assertRaisesRegex(packager.PackageError, "exact"):
                packager.verify_candidate(SimpleNamespace(candidate_dir=candidate))

    def test_candidate_verifier_rejects_changed_reproducibility_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = self._candidate(Path(temporary))
            record_path = candidate / "reproducibility-verification.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["license_and_device_release_gates_closed"] = True
            record_path.write_text(json.dumps(record), encoding="utf-8")
            self._reseal_candidate(candidate)
            with self.assertRaisesRegex(packager.PackageError, "reproducibility record"):
                packager.verify_candidate(SimpleNamespace(candidate_dir=candidate))

    def test_candidate_verifier_rejects_invalid_spdx(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = self._candidate(Path(temporary))
            (candidate / "runtime.spdx.json").write_text("{}", encoding="utf-8")
            self._reseal_candidate(candidate)
            with self.assertRaisesRegex(packager.PackageError, "SPDX"):
                packager.verify_candidate(SimpleNamespace(candidate_dir=candidate))

    def test_candidate_verifier_rejects_mismatched_checksum_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = self._candidate(Path(temporary))
            (candidate / "SHA256SUMS").write_text("0" * 64 + "  archive.tar.gz\n", encoding="ascii")
            with self.assertRaisesRegex(packager.PackageError, "SHA256SUMS"):
                packager.verify_candidate(SimpleNamespace(candidate_dir=candidate))

    def test_verifier_rejects_corrupted_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = self._prefix(root)
            manifest = self._package(prefix, root / "bundle")
            archive = root / "bundle" / manifest["artifact"]
            with archive.open("ab") as output:
                output.write(b"corrupt")
            with self.assertRaises(packager.PackageError):
                packager.verify(type("Args", (), {
                    "archive": archive, "manifest": root / "bundle/manifest.json"})())

    def test_packager_rejects_symlinked_bin_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = self._prefix(root)
            real_bin = root / "real-bin"
            (prefix / "bin").rename(real_bin)
            (prefix / "bin").symlink_to(real_bin, target_is_directory=True)
            with self.assertRaisesRegex(packager.PackageError, "regular bin directory"):
                self._package(prefix, root / "bundle")

    def test_verifier_rejects_unpinned_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = self._prefix(root)
            manifest = self._package(prefix, root / "bundle")
            manifest_path = root / "bundle/manifest.json"
            manifest["source_commit"] = "d" * 40
            manifest_path.write_text(__import__("json").dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(packager.PackageError, "pinned b11849 source"):
                packager.verify(type("Args", (), {
                    "archive": root / "bundle" / manifest["artifact"],
                    "manifest": manifest_path})())

    def test_packager_rejects_runtime_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = self._prefix(root)
            link = prefix / "lib/libbad.so"
            link.symlink_to(prefix / "lib/libggml-base.so")
            with self.assertRaises(packager.PackageError):
                self._package(prefix, root / "bundle")


if __name__ == "__main__":
    unittest.main()
