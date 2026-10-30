# P12 Snapdragon HTP runtime build preparation

Phase: `P12`

**Status:** The pinned `b11849` Android ARM64 builder completed successfully in corrected Actions run [`40962919123`](https://github.com/soobujmiah/ternuxx/actions/runs/40962919123): two independent builds compiled, generated source/runtime SPDX SBOMs, and produced byte-identical deterministic archives. The verified candidate archive SHA-256 is `f1a6f9ade2dd6b31503bf9b12c87c92a63ef6b043ffb318bf4a4e10692156b29`, size 49,219,753 bytes, with 23 runtime files. It remains a 90-day internal Actions artifact (`ternuxx-p12-htp-reproducible-candidate-40962919123`, artifact ID `12936224523`), not a public release. The current pinned-model device qualification is recorded below and in the [P12 qualification summary](2026-10-30-p12-native-qualification.md). Actions run [`40972970801`](https://github.com/soobujmiah/ternuxx/actions/runs/40972970801) found two suite issues: a model fixture missing the required private mode and a Mesa instrumentation test timing out after 10 seconds. Both were fixed locally; the focused tests and full 1,362-test suite now pass, and the corrected changes await a fresh Actions run. No public release or candidate device install is claimed.

## Build contract

The manual workflow `.github/workflows/p12-htp-reproducible-build.yml` is restricted to the `main` ref and builds the Android ARM64 Snapdragon runtime twice on independent Ubuntu 24.04 runners. It fetches the upstream `b11849` tag and rejects it unless it resolves to commit `0ae0e1976670fac25f4e0ed864df30021accc764`. The source tag is shown as a verified signed commit on the [upstream release page](https://github.com/ggml-org/llama.cpp/releases/tag/b11849). The workflow follows the upstream Android Snapdragon CMake preset and relative install-RPATH settings from the pinned [upstream release workflow](https://github.com/ggml-org/llama.cpp/blob/b11849/.github/workflows/release.yml).

The Snapdragon Android toolchain is pinned to the GHCR OCI index digest `sha256:e39e5e9c0957550a92c0de756b7556d81196c7c7f7328ed80de252bfb4878adf`, resolved from `ghcr.io/snapdragon-toolchain/arm64-android:v0.8`. GitHub Actions and SBOM actions are pinned to full commits. The artifact packager creates a fixed-time tar archive using the upstream source commit epoch and includes only `llama-cli`, direct `.so` runtime files, and the upstream MIT `LICENSE`. It rejects symlinks, unexpected paths, missing HTP/OpenCL libraries, and packages that exceed the current installer extraction limit. A manifest records source/build inputs and each runtime file's size/hash. SPDX SBOMs are requested for both source and packaged runtime.

The verify job independently validates each archive and manifest, then requires byte-identical archive SHA-256 values. A successful run would upload a 90-day internal Actions candidate, not a GitHub Release. The runtime installer pin in `lib/npu_inference.py` is intentionally unchanged until a built candidate passes device tests and distribution review.

## Local validation and limits

- `python3 -m unittest tests.test_package_snapdragon_release`: **5 passed** (deterministic packaging, archive tamper rejection, file and directory symlink rejection, pinned-source manifest rejection).
- Initial clean-`main` suite: **1,339 tests, 4 stale installer/CLI-help assertion failures**. Updated only those assertions to match current help/output; the rerun passed **1,339 tests in 201.589 seconds**.
- The four focused stale tests passed; `bash tests/test_cli_help.sh` passed.
- GitHub suite run [`40962905557`](https://github.com/soobujmiah/ternuxx/actions/runs/40962905557) found one additional host-dependent assertion: a PRoot graphics test assumed the physical device had KGSL and always selected Zink. The test now mocks the intended Zink preference explicitly; a GitHub rerun is pending.
- `python3 -m py_compile tools/package_snapdragon_release.py tests/test_package_snapdragon_release.py`: passed.
- Workflow YAML parsed and its pinned image/matrix structure checked with PyYAML; `git diff --check` passed.
- GitHub run [`40962133386`](https://github.com/soobujmiah/ternuxx/actions/runs/40962133386) failed in the CMake configure step on both runners: it searched the Ternuxx workspace root for `CMakePresets.json`. Commit `c2a4a5903cab69c6417023d32f0b74fbc7bfc352` changes into `upstream` before invoking the pinned preset. GitHub listed no run artifacts. No runtime archive was produced. No cross-run reproducibility, Android install, model correctness, thermal/sustained qualification, license clearance, or public release is claimed.

## Current Native Termux status observation

Read-only checks against the current device session reported:

- `bash tx ai npu status`: HTP0 available on SM8735; runtime reports release `b11849`, and silent fallback is false.
- `bash tx ai status`: Termux `llama-cpp` 0.7.0 is available, but the configured Ternuxx Qwen3 model file is missing at its private model path, so no CPU inference was run.
- `bash tx ai devices`: Vulkan enumerates `Vulkan0`, Adreno 825, with 8,425 MiB total and 5,003 MiB free as reported by that probe. This is device enumeration only; no GPU inference workload was run.

These are current Native runtime observations, separate from the failed/retried CI build and from historical inference evidence. They do not qualify the newly built candidate or any sustained performance/thermal behavior.

Two new no-inference thermal/resource preflights then passed with default guards (`cpu/gpu/htp <60 C`, battery `<45 C`, SoCD `<70 C`, `MemAvailable >=2048 MiB`), with no active `llama-cli` process. Both reported `thermal_limits_ignored: false` and `will_start_inference: false`:

| Sample (UTC) | CPU C | GPU C | HTP C | Battery C | SoCD C | MemAvailable KiB | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| 2026-10-29 22:09:51.615 | 48.0 | 39.2 | 41.2 | 38.68 | 12.0 | 5,707,888 | PASS |
| 2026-10-29 22:10:03.465 | 48.8 | 39.6 | 40.8 | 38.69 | 12.0 | 5,704,104 | PASS |

These short samples satisfy the requested preflight count for beginning a controlled test; they are not inference, sustained-thermal, or OEM thermal-limit evidence. The controlled CPU/HTP workload remains pending because the configured Ternuxx-private Qwen3 model is absent.

## Follow-up device qualification — 2026-10-30

The earlier live observations above are dated snapshots. A newer Qwen2.5 1.5B Q4_K_M model was installed to Ternuxx private state and hash-verified. One guarded HTP b11849 inference passed full 29/29 layer offload; a second call after two passing preflights crossed the HTP 60°C test guard at 61.0°C and was cancelled. CPU and Vulkan calls also hit their unchanged thermal guards during the current-model qualification. No new runtime archive was downloaded from GitHub Actions, and the internal 90-day artifact was not retrieved by the agent. Current test data and model/runtime hashes are in the [P12 qualification summary](2026-10-30-p12-native-qualification.md) and [integrity snapshot](2026-10-30-p12-integrity-snapshot.json). These results do not qualify stability or authorize public release.

## Remaining release gates

The successful builder already recorded the source/runtime SPDX output and byte-identical two-build comparison. The remaining runtime gate is for the owner to retrieve the internal artifact into the approved incoming handoff path; then verify its archive and manifest and device-test that exact Ternuxx-owned candidate on the pinned model with correct output, complete HTP offload, failure/restart behavior and telemetry; qualify GPU/CPU fallback and setup selection; close Mesa and full dependency-license/provenance review; apply the owner-selected GPL-3.0-or-later scope to original Ternuxx source and complete clean-install/release acceptance. The QNN SD1.5 image route has its own independent oracle and Qualcomm license-acceptance gates; this chat runtime build does not close them.

## Evidence

- Workflow: `.github/workflows/p12-htp-reproducible-build.yml`.
- Deterministic package tool: `tools/package_snapdragon_release.py`.
- Local package tests: `tests/test_package_snapdragon_release.py`.
- The clean-worktree full-suite command is `python3 -m unittest discover -s tests`.
