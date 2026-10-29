from pathlib import Path
import tempfile
import unittest

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
