# P12 Mesa build and package scope — 2026-10-24

Phase: `P12` — in progress

Evidence class: read-only review of the pinned Termux recipe, split-package manifests, source license guidance, and Native backend preflights

Observed: 2026-10-24 15:44 UTC

## Evidence — pinned build scope

Read-only GitHub API recheck at 15:45 UTC reports [lfdevs/termux-packages PR #25](https://github.com/lfdevs/termux-packages/pull/25) still open and draft at commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e`. Its [`packages/mesa/build.sh`](https://github.com/lfdevs/termux-packages/blob/0219ff84b372c9d38aad4e40f448c20ec3d1588e/packages/mesa/build.sh) pins Mesa source commit [`98f3d6229d61452cef80f8563af7c56ae599dc14`](https://github.com/lfdevs/mesa-for-android-container/tree/98f3d6229d61452cef80f8563af7c56ae599dc14).

The recipe enables these relevant build options:

- Gallium drivers: `swrast`, `llvmpipe`, `softpipe`, `virgl`, `zink`, and `freedreno` on aarch64.
- Vulkan drivers: `swrast` and `freedreno` on aarch64.
- `freedreno-kmds=msm,kgsl`, LLVM/shared LLVM, Rusticl, GBM, OpenGL, EGL with X11 native platform, GLES2, GLX DRI, X11 and Wayland platforms, and GLVND.
- GLES1 and Mesa XML configuration are disabled.

The four split-package manifests assign these paths to separate packages:

| Package | Manifest paths |
|---|---|
| [`mesa-opencl-icd-rusticl`](https://github.com/lfdevs/termux-packages/blob/0219ff84b372c9d38aad4e40f448c20ec3d1588e/packages/mesa/mesa-opencl-icd-rusticl.subpackage.sh) | Rusticl OpenCL ICD descriptor and `libRusticlOpenCL.so` |
| [`mesa-vulkan-icd-freedreno`](https://github.com/lfdevs/termux-packages/blob/0219ff84b372c9d38aad4e40f448c20ec3d1588e/packages/mesa/mesa-vulkan-icd-freedreno.subpackage.sh) | `libvulkan_freedreno.so` and its Vulkan ICD descriptor |
| [`mesa-vulkan-icd-swrast`](https://github.com/lfdevs/termux-packages/blob/0219ff84b372c9d38aad4e40f448c20ec3d1588e/packages/mesa/mesa-vulkan-icd-swrast.subpackage.sh) | `libvulkan_lvp.so` and its Vulkan ICD descriptor |
| [`mesa-dev`](https://github.com/lfdevs/termux-packages/blob/0219ff84b372c9d38aad4e40f448c20ec3d1588e/packages/mesa/mesa-dev.subpackage.sh) | EGL/GL headers and `gbm.h` |

The base `mesa` package receives the remaining package files. Exact archive hashes and control metadata are in the [package-level SPDX inventory](2026-10-24-p12-native-mesa-package-sbom.spdx.json); the earlier [package inspection](2026-10-24-p12-native-mesa-package-inventory.md) records what was found inside those archives.

## License boundary

The pinned source [`docs/license.rst`](https://github.com/lfdevs/mesa-for-android-container/blob/98f3d6229d61452cef80f8563af7c56ae599dc14/docs/license.rst) says Mesa contains components with different copyrights and licenses, and directs reviewers to each source file's SPDX identifier and the source `licenses/` directory. The recipe's `TERMUX_PKG_LICENSE="MIT"` is therefore a package recipe declaration, not proof that every enabled target and file is MIT-only.

This review maps enabled build targets and package split rules. It does **not** inspect the configured Meson/Ninja build graph, enumerate every compiled source file, associate each resulting binary with its full source set, or audit per-file SPDX identifiers and shipped notices. Consequently the package SBOM correctly remains `filesAnalyzed=false` and `licenseConcluded=NOASSERTION`; no redistribution, rehosting, or clean-installer approval follows from this scope map.

## Native qualification recheck

The corrected three-case qualification runner was invoked for CPU, Vulkan, and HTP on Native Termux:

```sh
python3 tools/native_accel_qualify.py --backend cpu --runs 3 --max-tokens 8 --idle-seconds 5
python3 tools/native_accel_qualify.py --backend vulkan --runs 3 --max-tokens 8 --idle-seconds 5
python3 tools/native_accel_qualify.py --backend npu --runs 3 --max-tokens 8 --idle-seconds 5
```

All three returned exit code `2` before inference with `preflight guard failed; no inference started`, `completed_runs=0`, and an empty `runs` list. Each reported `socd=84.0°C` against the `70°C` guard. Available memory was about 3.93 GiB. The other temperatures remained below their guards. No known answer was measured.

Separate read-only status calls reported the pinned local model and llama.cpp `0.7.0`, Vulkan0 Adreno 825, and experimental HTP0/b11849 for SM8735. These status results establish backend enumeration only; they do not qualify inference, complete offload, or sustained stability. The three preflight JSON reports were emitted to stdout and were not retained as files.

## Next gate

Build a reproducible source-file/license inventory from this exact source commit and tie it to the actual configured build outputs and notices. Keep package conclusions open until that review is complete. Re-run the corrected CPU, Vulkan, and HTP answer suite only when every required live sensor is below its guard; then continue sustained HTP and clean-install replay from durable audited Bionic build inputs.

## Validation

- `bash scripts/repo_test.sh`: all 1033 tests passed; the CLI help contract passed.
- `python3 -m unittest tests.test_phase_docs tests.test_feature_matrix -q`: 13 tests passed.
- `python3 tools/audit_documents.py --check`: inventory covers 520 documents, records 160 as read, and reports zero broken local links. The inventory is not a claim that every document has been reviewed.
- `python3 tools/doc_bridge.py check --strict --project-id ternuxx README.md`: passed.
- `python3 -m tools.repo_knowledge verify`: 0 findings; `git diff --check`: passed.

## Follow-up — package artifact and build-graph availability

Observed again at 2026-10-24 16:54 UTC. The pinned upstream packaging PR remained open and draft at `0219ff84b372c9d38aad4e40f448c20ec3d1588e`. Its successful aarch64 Actions run (`36377469447`, job `108786144977`) and preserved local artifact were inspected read-only. The artifact contains the five split `.deb` files, their checksums, and `built_termux-main_packages.txt`; that list names the same five packages. It does not contain a Meson build directory, `build.ninja`, `compile_commands.json`, or a per-output source manifest.

The public aarch64 job log reports the package-build step and Ninja entering the Mesa host-build directory, but does not expose the configured graph or object-to-source compile commands. The candidate base package's `libgallium-26.3.0-devel.so` is a stripped aarch64 ELF (NDK r30, Build ID `28fa5f69c96e892da7146b66e1167e2090a45da0`). Thus the retained packages and public log substantiate artifact identity and package contents, but do not recover a build-specific source map. Source-file inventory and split-package path manifests remain separate evidence; neither is a substitute for configured target-to-object-to-package provenance.

Next source-provenance action: obtain a build of the pinned recipe that preserves Meson introspection data, Ninja command metadata, generated-source records, and package staging manifests, then reproduce and hash that evidence before changing the package SPDX conclusions. No upstream workflow was modified or rerun, and no candidate package was installed.
