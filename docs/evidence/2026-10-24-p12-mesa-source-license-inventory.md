# P12 Mesa source-file license-header inventory — 2026-10-24

Phase: `P12` — in progress. Evidence class: pinned upstream source archive and file-header scan. Observed: 2026-10-24

## Evidence

### Source identity and method

The reviewed source is `lfdevs/mesa-for-android-container` commit [`98f3d6229d61452cef80f8563af7c56ae599dc14`](https://github.com/lfdevs/mesa-for-android-container/tree/98f3d6229d61452cef80f8563af7c56ae599dc14), the revision pinned by the Termux Mesa recipe reviewed in the [P12 build-scope record](2026-10-24-p12-mesa-build-scope.md). The downloaded codeload archive SHA-256 is `5211bd235658a0585740fb2dfbe64e7e8ca3085ad8e423fc333b4d5e0de6fd93`.

The reproducible scanner [tools/mesa_source_inventory.py](../../tools/mesa_source_inventory.py) hashes candidate source and build-input files and looks for a comment-style `SPDX-License-Identifier` header in the first 80 lines. The complete per-file paths, SHA-256 values, and literal header identifiers are in the [machine-readable inventory](data/2026-10-24-p12-mesa-source-license-inventory.json). The scanner now includes the generator-input formats observed in the configured Mesa graph.

The expanded scan covers 9,376 candidate source/build-input files. It found SPDX header identifiers in 3,965 files and no recognized identifier in 5,411. Among headers, the observed expressions include MIT, SGI-B-2.0, GPL-2.0 variants, Apache-2.0, BSL-1.0, and dual-license expressions. Therefore the recipe's package-level `MIT` declaration cannot be treated as a source-wide MIT-only conclusion.

## Limits and next gate

`NOASSERTION` in the inventory means the scanner did not find a recognized SPDX header; it does **not** mean the file is unlicensed. Legacy notices, directory-level licensing, and build-time code generation need separate review. The GitHub archive also omits two source-suffix symlinks present in the Git tree; the scanner does not follow symlinks.

## Configured source-graph recheck

The earlier [workflow run 40123636196](https://github.com/soobujmiah/ternuxx/actions/runs/40123636196) captured the host and target graphs but stopped at package-staging validation because dependency archives shared the output directory. The corrected package filter was exercised by [run 40125903141](https://github.com/soobujmiah/ternuxx/actions/runs/40125903141): Mesa built successfully, host/target graphs were captured, and manifests were generated for the five expected split packages. Its final workflow check then failed on an incorrect assumption that all five package architectures must be `aarch64`.

The produced manifest records `mesa-dev` as architecture `all`; `mesa`, `mesa-opencl-icd-rusticl`, `mesa-vulkan-icd-freedreno`, and `mesa-vulkan-icd-swrast` are `aarch64`. The manifest and its package/payload hashes are preserved in the [machine-readable package records](data/2026-10-24-p12-mesa-package-staging-manifests-40125903141.json). Pinned builder, recipe-source, target-architecture, and workflow-run metadata is in the [build metadata record](data/2026-10-24-p12-mesa-build-metadata-40125903141.json).

The target graph records 322 Meson targets, 1,579 unique source paths, and 75 generated-source entries. Of the source paths, 1,567 are under the pinned Mesa source root and all match a path and hash in the expanded inventory; 12 are outside it (seven Wayland protocol XML inputs and five build-generated Rust bindings). The [configured target-source map](data/2026-10-24-p12-mesa-configured-target-source-map-40125903141.json) records per-target membership, source hashes and headers, outside-root inputs, and generated outputs. Its Meson graph hash matches the captured run 40125903141 graph.

Among the 1,567 unique source-root paths listed by the configured target graph, 402 have a recognized SPDX header and 1,165 remain `NOASSERTION`. This is configured target-source membership, not proof that every listed file is compiled into a shipped binary. The map also does not associate package payload paths with transitive object/source sets or establish which notices ship.

A separate [package-to-target candidate map](data/2026-10-24-p12-mesa-package-target-candidates-40125903141.json) compares captured package payload basenames with configured Meson output basenames. It records 11 unique regular-file candidates and 46 package symlinks resolving to those candidate files; 10 regular files have no unique basename match, and 341 configured target outputs have no matching payload basename. These are candidate associations only: basename matching does not prove install-rule identity, transitive object/source membership, runtime loading, or package license conclusions. Within the matched target memberships, `EGL_mesa` has 22 unique source-path entries with `NOASSERTION`, while `vulkan_freedreno` has 35 unique source-path entries (one `NOASSERTION`) and three generated-output entries. These are configured-graph inputs associated with candidate targets; they do not establish the contents of the packaged binaries.

The local `validate-capture` command now checks the pinned recipe/build metadata, host/target graph files, graph-bound source map, exact five package names, and package-specific control architectures, hashes, and payload paths. It passes against the downloaded run 40125903141 artifact after generating the graph-bound map locally. The workflow now generates that map itself and uses the same validator; corrected run [40128850286](https://github.com/soobujiah/ternuxx/actions/runs/40128850286) is currently building Mesa, with package validation and evidence upload still pending. Keep package `licenseConcluded` at `NOASSERTION` and `filesAnalyzed=false` until generated inputs, package-to-target/source mapping, external dependency provenance, applicable notices, and license expressions are reviewed. This evidence does not approve redistribution, rehosting, a clean installer, or a release.

The next P12 source gate is to pass the corrected workflow, then associate compiled/generated and external inputs with package payloads and audit applicable notices and license expressions. Keep package `licenseConcluded` at `NOASSERTION` and `filesAnalyzed=false` until that build-specific review is complete. This evidence does not approve redistribution, rehosting, a clean installer, or a release.

## Validation

- `python3 -m unittest tests.test_mesa_source_inventory -v`: 3 tests passed.
- `python3 -m pytest -q tests/test_mesa_build_source_audit.py`: 3 tests passed; all 1,567 target-source paths under the pinned Mesa root matched the inventory and the 12 external/build-generated source paths were preserved separately.
- The run-specific configured target-source map records 322 Meson targets, 75 generated-source entries, 402 source-root paths with SPDX headers, and 1,165 with `NOASSERTION`; its Meson targets hash matches the run 40125903141 capture.
- `python3 tools/mesa_source_inventory.py --archive … --commit 98f3d6229d61452cef80f8563af7c56ae599dc14`: generated the inventory from the hashed archive.
- The source tree API reports 12,837 blobs with no truncation. The archive SHA-256 matches the earlier verified download. The expanded inventory includes source/build-input suffixes; its configured target-source coverage was compared with the captured Meson graph as described above.
- `python3 -m pytest -q`: 1,087 tests and 402 subtests passed (2026-10-25), including the package-to-target candidate audit tests.
- `python3 -m pytest -q tests/test_p12_mesa_build_evidence.py tests/test_mesa_build_source_audit.py`: 13 tests passed. `python3 -m pytest -q tests/test_mesa_package_target_audit.py`: 3 tests passed. `validate-capture` also passed against the downloaded run 40125903141 evidence after locally deriving its graph-bound source map. Workflow YAML parsing, `git diff --check`, `python3 tools/audit_documents.py --check`, `python3 -m tools.repo_knowledge verify`, and `bash tests/test_cli_help.sh` passed.
