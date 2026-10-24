from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.mesa_build_source_audit import SourceAuditError, audit_graph


class MesaBuildSourceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.graph_path = self.root / "meson-targets.json"
        self.inventory_path = self.root / "inventory.json"
        self.source_root = "/builder/mesa/src"
        self.graph_path.write_text(json.dumps([
            {
                "id": "lib-a",
                "name": "liba",
                "type": "static library",
                "filename": ["/builder/mesa/build/liba.a"],
                "target_sources": [
                    {
                        "language": "c",
                        "sources": [f"{self.source_root}/src/a.c", "/opt/wayland/protocol.xml"],
                        "generated_sources": ["/builder/mesa/build/generated.c"],
                    },
                    {"language": "cpp", "sources": [f"{self.source_root}/src/a.c"]},
                ],
            },
        ]), encoding="utf-8")
        self.inventory_path.write_text(json.dumps({
            "source_repository": "https://example.invalid/mesa",
            "source_commit": "a" * 40,
            "source_archive_sha256": "b" * 64,
            "files": [{
                "path": "src/a.c",
                "sha256": "c" * 64,
                "spdx_header_identifiers": ["MIT"],
                "header_license_status": "IDENTIFIER_PRESENT",
            }],
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_maps_inventory_hashes_and_separates_external_and_generated_inputs(self) -> None:
        result = audit_graph(self.graph_path, self.inventory_path, self.source_root)

        self.assertEqual(result["counts"], {
            "meson_targets": 1,
            "unique_source_paths": 2,
            "source_root_paths": 1,
            "source_root_paths_with_spdx_header": 1,
            "source_root_paths_without_recognized_spdx_header": 0,
            "outside_source_root_paths": 1,
            "generated_source_paths": 1,
        })
        self.assertEqual(result["source_files"][0]["sha256"], "c" * 64)
        self.assertEqual(result["source_files"][0]["targets"][0]["language"], "c")
        self.assertEqual(result["source_files"][0]["targets"][1]["language"], "cpp")
        self.assertEqual(result["outside_source_root"][0]["path"], "/opt/wayland/protocol.xml")
        self.assertEqual(result["generated_outputs"][0]["path"], "/builder/mesa/build/generated.c")

    def test_unindexed_configured_source_fails_closed(self) -> None:
        graph = json.loads(self.graph_path.read_text())
        graph[0]["target_sources"][0]["sources"].append(f"{self.source_root}/src/missing.xml")
        self.graph_path.write_text(json.dumps(graph), encoding="utf-8")
        with self.assertRaisesRegex(SourceAuditError, "missing from inventory"):
            audit_graph(self.graph_path, self.inventory_path, self.source_root)

    def test_duplicate_meson_target_id_is_rejected(self) -> None:
        graph = json.loads(self.graph_path.read_text())
        graph.append(dict(graph[0]))
        self.graph_path.write_text(json.dumps(graph), encoding="utf-8")
        with self.assertRaisesRegex(SourceAuditError, "repeats target ID"):
            audit_graph(self.graph_path, self.inventory_path, self.source_root)


if __name__ == "__main__":
    unittest.main()
