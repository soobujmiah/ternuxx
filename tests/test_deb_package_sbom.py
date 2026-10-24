import json
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch

from tools.deb_package_sbom import SbomError, build_spdx, inspect_deb, parse_control


class DebianPackageSbomTests(unittest.TestCase):
    def test_control_parser_joins_continuation_lines_and_preserves_missing_fields(self):
        fields = parse_control("Package: mesa\nVersion: 26.3.0\nDepends: libc++,\n libdrm\n")
        self.assertEqual(fields, {"Package": "mesa", "Version": "26.3.0",
                                  "Depends": "libc++, libdrm"})

    def test_control_parser_rejects_duplicate_fields(self):
        with self.assertRaisesRegex(SbomError, "duplicate"):
            parse_control("Package: mesa\nPackage: other\n")

    def test_inspection_hashes_a_regular_deb_and_reads_package_control(self):
        with tempfile.TemporaryDirectory() as directory:
            deb = Path(directory) / "mesa_26.3.0_aarch64.deb"
            deb.write_bytes(b"fixture deb bytes")
            completed = type("Completed", (), {"returncode": 0, "stdout":
                "Package: mesa\nVersion: 26.3.0\nArchitecture: aarch64\nDepends: libc++\n"})()
            with patch("tools.deb_package_sbom.subprocess.run", return_value=completed) as run:
                package = inspect_deb(deb, dpkg_deb="/mock/dpkg-deb")
            self.assertEqual(package["name"], "mesa")
            self.assertEqual(package["depends"], "libc++")
            self.assertEqual(package["control_license"], None)
            self.assertEqual(package["sha256"], hashlib.sha256(b"fixture deb bytes").hexdigest())
            self.assertEqual(run.call_args.args[0][:2], ["/mock/dpkg-deb", "--field"])

    def test_spdx_document_marks_package_level_scope_and_unknown_conclusions(self):
        package = {"name": "mesa", "version": "26.3.0", "architecture": "aarch64",
                   "depends": "libc++, libdrm", "source": None, "control_license": None,
                   "filename": "mesa_26.3.0_aarch64.deb", "sha256": "a" * 64}
        document = build_spdx([package], document_name="Mesa bundle",
            document_namespace="https://example.invalid/spdx/mesa-test",
            source_info="source commit abc123", bundle_sha256="b" * 64,
            declared_license="MIT", license_basis="package recipe states MIT",
            created="2026-10-24T00:00:00Z")
        self.assertEqual(document["spdxVersion"], "SPDX-2.3")
        self.assertEqual(document["creationInfo"]["created"], "2026-10-24T00:00:00Z")
        self.assertEqual(document["documentDescribes"], ["SPDXRef-Package-mesa"])
        self.assertEqual(document["relationships"][0]["relationshipType"], "DESCRIBES")
        item = document["packages"][0]
        self.assertFalse(item["filesAnalyzed"])
        self.assertEqual(item["licenseDeclared"], "MIT")
        self.assertEqual(item["licenseConcluded"], "NOASSERTION")
        self.assertIn("License field: not present", item["comment"])
        self.assertIn("file-level", item["licenseComments"].casefold())
        self.assertEqual(item["checksums"][0]["checksumValue"], "a" * 64)
        json.dumps(document)

    def test_spdx_generation_requires_evidence_for_nonunknown_declared_license(self):
        with self.assertRaisesRegex(SbomError, "evidence basis"):
            build_spdx([{"name": "mesa", "version": "26.3.0", "architecture": "aarch64",
                         "filename": "mesa.deb", "sha256": "a" * 64}],
                document_name="Mesa", document_namespace="https://example.invalid/spdx/mesa",
                source_info="source commit abc123", bundle_sha256="b" * 64,
                declared_license="MIT")


if __name__ == "__main__":
    unittest.main()
