from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.mesa_generated_source_audit import GeneratedAuditError, audit_generated_outputs  # noqa: E402


class MesaGeneratedSourceAuditTests(unittest.TestCase):
    def _inputs(self, root: Path, *, output: str = "src/generated.c"):
        build_ninja = root / "build.ninja"
        source_map = root / "source-map.json"
        inventory = root / "inventory.json"
        build_ninja.write_text(
            "build src/generated.c src/generated.h: CUSTOM_COMMAND ../src/src/generator.py "
            "../src/src/input.xml | /data/protocols/demo.xml /usr/bin/python3\n"
            "build src/rust_bindings.rs: CUSTOM_COMMAND_DEP ../src/src/rust/bindings.h | /usr/bin/bindgen\n"
            "build src/consumer.o: c_COMPILER src/generated.c\n",
            encoding="utf-8")
        source_map.write_text(json.dumps({
            "source_root": "/builder/mesa/src", "source_commit": "a" * 40,
            "source_archive_sha256": "b" * 64,
            "generated_outputs": [{"path": f"/builder/mesa/build/{output}", "target_ids": ["gen@custom"]}],
            "outside_source_root": [
                {"path": "/builder/mesa/build/src/rust_bindings.rs", "target_ids": ["rust@custom"]},
                {"path": "/data/protocols/demo.xml", "target_ids": ["wayland@custom"]},
            ],
            "source_files": [],
        }), encoding="utf-8")
        inventory.write_text(json.dumps({
            "source_commit": "a" * 40, "source_archive_sha256": "b" * 64,
            "files": [
                {"path": "src/generator.py", "sha256": "c" * 64,
                 "spdx_header_identifiers": ["MIT"], "header_license_status": "IDENTIFIER_PRESENT"},
                {"path": "src/input.xml", "sha256": "d" * 64,
                 "spdx_header_identifiers": [], "header_license_status": "NOASSERTION"},
            ],
        }), encoding="utf-8")
        return build_ninja, source_map, inventory

    def test_maps_generated_outputs_to_source_external_and_tool_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._inputs(Path(temp))
            result = audit_generated_outputs(*paths)
        self.assertEqual(result["counts"]["generated_outputs"], 1)
        self.assertEqual(result["counts"]["unique_source_inputs"], 2)
        self.assertEqual(result["counts"]["unique_external_inputs"], 2)
        self.assertEqual(result["counts"]["outside_paths_mapped_to_ninja_edges"], 2)
        outside = {item["path"]: item for item in result["outside_source_root"]}
        self.assertEqual(outside["/builder/mesa/build/src/rust_bindings.rs"]["classification"],
                         "build-tree-generated-source")
        self.assertEqual(outside["/data/protocols/demo.xml"]["classification"], "external-input")
        self.assertEqual(outside["/data/protocols/demo.xml"]["ninja_references"][0]["rule"],
                         "CUSTOM_COMMAND")
        edge = result["outputs"][0]
        self.assertEqual(edge["ninja_outputs"], ["src/generated.c", "src/generated.h"])
        indexed = {item["path"]: item for item in edge["inputs"]}
        self.assertEqual(indexed["/builder/mesa/src/src/generator.py"]["spdx_header_identifiers"], ["MIT"])
        self.assertEqual(indexed["/builder/mesa/src/src/input.xml"]["header_license_status"], "NOASSERTION")
        self.assertEqual(indexed["/data/protocols/demo.xml"]["kind"], "external-source")
        self.assertEqual(indexed["/usr/bin/python3"]["kind"], "external-tool-or-input")

    def test_unmapped_generated_output_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._inputs(Path(temp), output="src/missing.c")
            with self.assertRaisesRegex(GeneratedAuditError, "no Ninja build edge"):
                audit_generated_outputs(*paths)


if __name__ == "__main__":
    unittest.main()
