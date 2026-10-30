from pathlib import Path
import tempfile
import unittest

from tools.collect_snapdragon_notices import COMPONENTS, NoticeError, collect


class SnapdragonNoticeTests(unittest.TestCase):
    def _source(self, root: Path) -> Path:
        files = {
            "LICENSE": "MIT License\nCopyright (c) 2023-2026 The ggml authors\nPermission is hereby granted\n",
            "vendor/cpp-httplib/LICENSE": "The MIT License (MIT)\nCopyright (c) 2017 yhirose\n",
            "vendor/hash/xxhash/LICENSE": "BSD 2-Clause License\nCopyright Yann Collet\n",
            "vendor/hash/rotate-bits/LICENSE.md": "MIT License\nCopyright William Casarin\n",
            "vendor/hash/sha256/LICENSE": "Igor Pavlov : Public domain\n",
            "vendor/hash/sha1/sha1.c": "/*\nSHA-1 in C\n100% Public Domain\n*/\nint main(void) { return 0; }\n",
            "vendor/nlohmann/json.hpp": "header\n// SPDX-FileCopyrightText: 2013 - 2025 Niels Lohmann <https://nlohmann.me>\n// SPDX-License-Identifier: MIT\n",
            "vendor/sheredom/subprocess.h": "/*\nThis is free and unencumbered software released into the public domain.\n*/\n",
            "vendor/stb/stb_image.h": "/* implementation */\n/*\nThis software is available under 2 licenses\nMIT license and public domain\n*/\n",
            "vendor/miniaudio/miniaudio.h": "/* implementation */\n/*\nThis software is available as a choice of the following licenses\nUnlicense and MIT No Attribution\n*/\n",
        }
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def test_collects_all_linked_component_notices_deterministically(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_source = self._source(root / "source-one")
            second_source = self._source(root / "source-two")
            first = root / "first" / "THIRD_PARTY_NOTICES.txt"
            second = root / "second" / "THIRD_PARTY_NOTICES.txt"
            result = collect(first_source, first)
            collect(second_source, second)
            self.assertEqual(len(COMPONENTS), 9)
            self.assertEqual(result["component_count"], 9)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            contents = first.read_text(encoding="utf-8")
            for name, license_id, _, _ in COMPONENTS:
                self.assertIn(name, contents)
                self.assertIn(f"License: {license_id}", contents)
            self.assertIn("Copyright (c) 2013-2025 Niels Lohmann", contents)
            self.assertIn("BSD 2-Clause License", contents)
            self.assertIn("100% Public Domain", contents)

    def test_missing_or_changed_license_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._source(Path(temporary))
            (root / "vendor/hash/xxhash/LICENSE").unlink()
            with self.assertRaisesRegex(NoticeError, "missing a regular license source"):
                collect(root, root / "THIRD_PARTY_NOTICES.txt")

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._source(Path(temporary))
            output = root / "THIRD_PARTY_NOTICES.txt"
            output.write_text("owner data\n", encoding="utf-8")
            with self.assertRaisesRegex(NoticeError, "must not exist"):
                collect(root, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "owner data\n")


if __name__ == "__main__":
    unittest.main()
