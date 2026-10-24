from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest

from tools.p12_mesa_build_evidence import EvidenceError, instrument_recipe, package_manifests


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
''', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_instrumentation_is_gated_and_captures_host_and_target(self) -> None:
        instrument_recipe(self.recipe)
        text = self.recipe.read_text(encoding="utf-8")
        self.assertIn('[[ "${TERNUXX_MESA_BUILD_CAPTURE:-0}" == "1" ]] || return 0', text)
        self.assertIn('_ternuxx_capture_meson "$TERMUX_PKG_HOSTBUILD_DIR/build" host', text)
        self.assertIn('_ternuxx_capture_meson "$TERMUX_PKG_BUILDDIR" target', text)
        self.assertIn('ninja -C "$build_dir" -t commands', text)
        self.assertIn('--targets > "$evidence_dir/meson-targets.json"', text)

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
            self.assertEqual(package["files"][1]["type"], "symlink")
            self.assertEqual(package["files"][1]["link_target"], "libmesa.so")


if __name__ == "__main__":
    unittest.main()
