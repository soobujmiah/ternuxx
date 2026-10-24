# P12 Mesa source-file license-header inventory — 2026-10-24

Phase: `P12` — in progress. Evidence class: pinned upstream source archive and file-header scan. Observed: 2026-10-24

## Evidence

### Source identity and method

The reviewed source is `lfdevs/mesa-for-android-container` commit [`98f3d6229d61452cef80f8563af7c56ae599dc14`](https://github.com/lfdevs/mesa-for-android-container/tree/98f3d6229d61452cef80f8563af7c56ae599dc14), the revision pinned by the Termux Mesa recipe reviewed in the [P12 build-scope record](2026-10-24-p12-mesa-build-scope.md). The downloaded codeload archive SHA-256 is `5211bd235658a0585740fb2dfbe64e7e8ca3085ad8e423fc333b4d5e0de6fd93`.

The reproducible scanner [tools/mesa_source_inventory.py](../../tools/mesa_source_inventory.py) hashes every candidate source file and looks for a comment-style `SPDX-License-Identifier` header in the first 80 lines. The complete per-file paths, SHA-256 values, and literal header identifiers are in the [machine-readable inventory](data/2026-10-24-p12-mesa-source-license-inventory.json). Three parser and scope tests pass in `tests.test_mesa_source_inventory`.

The scan covered 8,386 C, C++, Rust, assembly, shader, Python, and shell candidate files. It found SPDX header identifiers in 3,895 files and no recognized identifier in 4,491. Among headers, the observed expressions include MIT, SGI-B-2.0, GPL-2.0 variants, Apache-2.0, BSL-1.0, and dual-license expressions. Therefore the recipe's package-level `MIT` declaration cannot be treated as a source-wide MIT-only conclusion.

## Limits and next gate

`NOASSERTION` in the inventory means the scanner did not find a recognized SPDX header; it does **not** mean the file is unlicensed. Legacy notices, directory-level licensing, generated inputs, and build-time code generation need separate review. The source archive is not the configured Meson/Ninja build graph: this inventory does not identify which of these files were compiled into the five preserved package outputs, account for generated sources, associate object files with source sets, or establish which notices ship in each split package. The GitHub archive also omits two source-suffix symlinks present in the Git tree; the scanner does not follow symlinks.

The next P12 source gate is to obtain or reproduce the exact configured Termux Mesa build for the pinned recipe, map compiled and generated inputs to package outputs, and audit the applicable notices and license expressions. Keep package `licenseConcluded` at `NOASSERTION` and `filesAnalyzed=false` until that build-specific review is complete. This evidence does not approve redistribution, rehosting, a clean installer, or a release.

## Validation

- `python3 -m unittest tests.test_mesa_source_inventory -v`: 3 tests passed.
- `python3 tools/mesa_source_inventory.py --archive … --commit 98f3d6229d61452cef80f8563af7c56ae599dc14`: generated the inventory from the hashed archive.
- The source tree API reports 12,837 blobs with no truncation; all 8,386 archived source-candidate blobs match the corresponding Git blob hashes. The 32 other content-hash differences are CSV files normalized by codeload, and the 10 omitted tree entries are symlinks (including `.py`- and `.h`-suffix symlinks).
- `env -u LD_LIBRARY_PATH bash scripts/repo_test.sh`: 1,041 tests passed; CLI help contract passed.
- `python3 tools/audit_documents.py --check`, strict README bridge validation, `python3 -m tools.repo_knowledge verify`, and `git diff --check` passed.
