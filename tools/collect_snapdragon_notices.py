#!/usr/bin/env python3
"""Collect notices for third-party components linked into the b11849 Android runtime."""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED_SOURCE_COMMIT = "0ae0e1976670fac25f4e0ed864df30021accc764"
COMPONENTS = (
    ("cpp-httplib", "MIT", "vendor/cpp-httplib/LICENSE", "file"),
    ("xxHash", "BSD-2-Clause", "vendor/hash/xxhash/LICENSE", "file"),
    ("rotate-bits", "MIT", "vendor/hash/rotate-bits/LICENSE.md", "file"),
    ("SHA-256", "LicenseRef-Public-Domain", "vendor/hash/sha256/LICENSE", "file"),
    ("SHA-1 in C", "LicenseRef-Public-Domain", "vendor/hash/sha1/sha1.c", "first-comment"),
    ("nlohmann/json", "MIT", "vendor/nlohmann/json.hpp", "nlohmann"),
    ("sheredom/subprocess.h", "Unlicense", "vendor/sheredom/subprocess.h", "first-comment"),
    ("stb_image", "MIT OR Unlicense", "vendor/stb/stb_image.h", "license-tail:This software is available under 2 licenses"),
    ("miniaudio", "MIT-0 OR Unlicense", "vendor/miniaudio/miniaudio.h", "license-tail:This software is available as a choice of the following licenses"),
)


class NoticeError(ValueError):
    pass


def _first_comment(text: str, name: str) -> str:
    start = text.find("/*")
    end = text.find("*/", start + 2)
    if start < 0 or end < 0:
        raise NoticeError(f"{name} has no leading license comment")
    return text[start:end + 2]


def _license_tail(text: str, marker: str, name: str) -> str:
    marker_at = text.rfind(marker)
    start = text.rfind("/*", 0, marker_at)
    end = text.find("*/", marker_at)
    if marker_at < 0 or start < 0 or end < 0:
        raise NoticeError(f"{name} license block is missing or malformed")
    return text[start:end + 2]


def _notice(source_dir: Path, name: str, license_id: str,
            relative: str, extractor: str) -> str:
    path = source_dir / relative
    if path.is_symlink() or not path.is_file():
        raise NoticeError(f"pinned source is missing a regular license source: {relative}")
    text = path.read_text(encoding="utf-8")
    if extractor == "file":
        body = text.strip()
    elif extractor == "first-comment":
        body = _first_comment(text, name)
    elif extractor == "nlohmann":
        header = "\n".join(line.strip() for line in text.splitlines()[:16]
                            if "SPDX-FileCopyrightText:" in line or "SPDX-License-Identifier:" in line)
        if "SPDX-FileCopyrightText: 2013 - 2025 Niels Lohmann" not in header or "SPDX-License-Identifier: MIT" not in header:
            raise NoticeError("nlohmann/json SPDX copyright or MIT identifier changed")
        root_license = (source_dir / "LICENSE").read_text(encoding="utf-8")
        if root_license.count("Copyright (c) 2023-2026 The ggml authors") != 1:
            raise NoticeError("upstream MIT license copyright line changed")
        body = (header + "\n\n" + root_license.replace(
            "Copyright (c) 2023-2026 The ggml authors",
            "Copyright (c) 2013-2025 Niels Lohmann").strip())
    elif extractor.startswith("license-tail:"):
        body = _license_tail(text, extractor.removeprefix("license-tail:"), name)
    else:
        raise NoticeError(f"unsupported license extraction rule for {name}")
    if not body:
        raise NoticeError(f"license text is empty for {name}")
    return f"{name}\nLicense: {license_id}\nSource: {relative}\n\n{body}\n"


def collect(source_dir: Path, output: Path) -> dict[str, object]:
    if source_dir.is_symlink() or not source_dir.is_dir():
        raise NoticeError("source directory must be a real directory")
    if output.is_symlink() or output.exists():
        raise NoticeError("notice output must not exist or be a symlink")
    sections = [
        "Third-party license notices for the Android ARM64 llama.cpp Snapdragon runtime.",
        f"Pinned source commit: {PINNED_SOURCE_COMMIT}",
        "These components are linked into the packaged runtime libraries. Preserve this notice with redistributed copies.",
        "",
    ]
    for name, license_id, relative, extractor in COMPONENTS:
        sections.extend(["=" * 72, _notice(source_dir, name, license_id, relative, extractor), ""])
    payload = "\n".join(sections).rstrip() + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8", newline="\n")
    return {"notice_file": str(output), "component_count": len(COMPONENTS),
            "components": [{"name": name, "license": license_id, "source": relative}
                           for name, license_id, relative, _ in COMPONENTS]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        import json
        result = collect(args.source_dir, args.output)
    except (OSError, UnicodeError, NoticeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
