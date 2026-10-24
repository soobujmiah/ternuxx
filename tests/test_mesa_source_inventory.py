import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.mesa_source_inventory import InventoryError, _header_licenses, inventory_archive


COMMIT = "98f3d6229d61452cef80f8563af7c56ae599dc14"


def write_archive(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as bundle:
        for name, data in members.items():
            item = tarfile.TarInfo(name)
            item.size = len(data)
            bundle.addfile(item, io.BytesIO(data))


class MesaSourceInventoryTests(unittest.TestCase):
    def test_header_parser_accepts_comment_styles_and_ignores_later_code_strings(self):
        self.assertEqual(_header_licenses(
            b"/* SPDX-License-Identifier: MIT */\nint main(void) { return 0; }\n"
            b'const char *s = "SPDX-License-Identifier: GPL-3.0";\n'), ["MIT"])
        self.assertEqual(_header_licenses(b"// SPDX-License-Identifier: Apache-2.0\n"),
                         ["Apache-2.0"])

    def test_archive_inventory_hashes_candidate_files_and_leaves_missing_license_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "mesa.tar.gz"
            source = b"/* SPDX-License-Identifier: MIT */\nint x;\n"
            unknown = b"/* legacy copyright header */\nint y;\n"
            write_archive(archive, {
                f"mesa-for-android-container-{COMMIT}/src/a.c": source,
                f"mesa-for-android-container-{COMMIT}/src/b.h": unknown,
                f"mesa-for-android-container-{COMMIT}/src/c.xml": b"<!-- SPDX-License-Identifier: Apache-2.0 -->\n<api/>\n",
                f"mesa-for-android-container-{COMMIT}/src/d.y": b"/* SPDX-License-Identifier: MIT */\n%%\n",
                f"mesa-for-android-container-{COMMIT}/src/e.json": b"// SPDX-License-Identifier: BSD-2-Clause\n{}\n",
                f"mesa-for-android-container-{COMMIT}/README.md": b"not source\n",
            })

            result = inventory_archive(str(archive), COMMIT)

        self.assertEqual(result["candidate_source_file_count"], 5)
        self.assertEqual(result["files_with_spdx_header"], 4)
        self.assertEqual(result["files_without_spdx_header"], 1)
        self.assertEqual(result["spdx_header_file_counts"], {
            "Apache-2.0": 1, "BSD-2-Clause": 1, "MIT": 2,
        })
        files = {item["path"]: item for item in result["files"]}
        self.assertEqual(files["src/a.c"]["sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(files["src/b.h"]["header_license_status"], "NOASSERTION")
        self.assertEqual(files["src/c.xml"]["spdx_header_identifiers"], ["Apache-2.0"])
        self.assertEqual(files["src/d.y"]["spdx_header_identifiers"], ["MIT"])
        self.assertIn("does not mean unlicensed", result["scope_limit"])
        json.dumps(result)

    def test_archive_requires_exact_source_root_and_full_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "mesa.tar.gz"
            write_archive(archive, {"unexpected/src/a.c": b"int x;\n"})
            with self.assertRaisesRegex(InventoryError, "outside the pinned source root"):
                inventory_archive(str(archive), COMMIT)
            with self.assertRaisesRegex(InventoryError, "full lowercase Git SHA-1"):
                inventory_archive(str(archive), "bad")


if __name__ == "__main__":
    unittest.main()
