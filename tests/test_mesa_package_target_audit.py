from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.p12_mesa_build_evidence import MESA_SOURCE_ARCHIVE_SHA256, RECIPE_COMMIT
from tools.mesa_package_target_audit import PackageTargetAuditError, audit_packages


class MesaPackageTargetAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.packages = self.root / "packages.json"
        self.targets = self.root / "targets.json"
        self.source_map = self.root / "source-map.json"
        targets = [
            {"id": "libfoo", "name": "libfoo", "type": "shared library",
             "filename": ["/builder/build/libfoo.so"]},
            {"id": "amb-a", "name": "amb_a", "type": "shared library",
             "filename": ["/builder/build/ambiguous.so"]},
            {"id": "amb-b", "name": "amb_b", "type": "shared library",
             "filename": ["/builder/other/ambiguous.so"]},
            {"id": "multi-output", "name": "multi_output", "type": "shared library",
             "filename": ["/builder/one/repeated.so", "/builder/two/repeated.so"]},
            {"id": "tool", "name": "tool", "type": "executable",
             "filename": ["/builder/build/tool"]},
        ]
        self.targets.write_text(json.dumps(targets), encoding="utf-8")
        source_map = {
            "source_commit": RECIPE_COMMIT,
            "source_archive_sha256": MESA_SOURCE_ARCHIVE_SHA256,
            "meson_targets_sha256": hashlib.sha256(self.targets.read_bytes()).hexdigest(),
            "source_files": [{
                "path": "src/libfoo.c",
                "sha256": "a" * 64,
                "spdx_header_identifiers": ["MIT"],
                "header_license_status": "IDENTIFIER_PRESENT",
                "targets": [{"id": "libfoo", "language": "c"}],
            }],
            "outside_source_root": [{"path": "/dependency/input.xml", "target_ids": ["libfoo"]}],
            "generated_outputs": [{"path": "/build/generated.c", "target_ids": ["libfoo"]}],
        }
        self.source_map.write_text(json.dumps(source_map), encoding="utf-8")
        self.packages.write_text(json.dumps({"packages": [{
            "name": "mesa",
            "version": "26.3.0",
            "architecture": "aarch64",
            "archive_sha256": "b" * 64,
            "files": [
                {"path": "data/usr/lib/libfoo.so", "type": "file", "sha256": "c" * 64},
                {"path": "data/usr/lib/ambiguous.so", "type": "file", "sha256": "d" * 64},
                {"path": "data/usr/lib/repeated.so", "type": "file", "sha256": "f" * 64},
                {"path": "data/usr/bin/unrelated", "type": "file", "sha256": "e" * 64},
                {"path": "data/usr/lib/libfoo-link.so", "type": "symlink",
                 "link_target": "libfoo.so"},
            ],
        }]}), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_emits_unique_candidates_and_preserves_ambiguous_and_unmatched_entries(self) -> None:
        result = audit_packages(self.packages, self.targets, self.source_map)
        self.assertEqual(result["counts"], {
            "packages": 1,
            "payload_entries": 5,
            "payload_files": 4,
            "payload_symlinks": 1,
            "payload_directories": 0,
            "payload_other_types": 0,
            "unique_output_basename_candidates": 1,
            "symlinks_resolving_to_candidate_files": 1,
            "ambiguous_output_basenames": 2,
            "files_without_target_basename_match": 1,
            "target_outputs_without_payload_basename_match": 5,
        })
        entries = result["packages"][0]["payload_entries"]
        self.assertEqual(entries[0]["association"], "unique-output-basename-candidate")
        self.assertEqual(entries[0]["target"]["target_id"], "libfoo")
        self.assertEqual(entries[0]["target_source_membership"][0]["path"], "src/libfoo.c")
        self.assertEqual(entries[0]["external_inputs"], ["/dependency/input.xml"])
        self.assertEqual(entries[0]["generated_outputs"], ["/build/generated.c"])
        self.assertEqual(entries[1]["association"], "ambiguous-output-basename")
        self.assertEqual(entries[2]["association"], "ambiguous-output-basename")
        self.assertEqual(entries[3]["association"], "file-no-target-output-basename-match")
        self.assertEqual(entries[4]["association"], "symlink-resolves-to-payload-file-candidate")
        self.assertEqual(entries[4]["resolves_to_payload_path"], "data/usr/lib/libfoo.so")
        self.assertIn("candidates only", result["scope_limit"])

    def test_rejects_source_map_bound_to_a_different_target_graph(self) -> None:
        source_map = json.loads(self.source_map.read_text(encoding="utf-8"))
        source_map["meson_targets_sha256"] = "f" * 64
        self.source_map.write_text(json.dumps(source_map), encoding="utf-8")
        with self.assertRaisesRegex(PackageTargetAuditError, "does not match"):
            audit_packages(self.packages, self.targets, self.source_map)

    def test_rejects_unsafe_package_payload_path(self) -> None:
        manifest = json.loads(self.packages.read_text(encoding="utf-8"))
        manifest["packages"][0]["files"][0]["path"] = "../outside"
        self.packages.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(PackageTargetAuditError, "unsafe or duplicate"):
            audit_packages(self.packages, self.targets, self.source_map)


if __name__ == "__main__":
    unittest.main()
