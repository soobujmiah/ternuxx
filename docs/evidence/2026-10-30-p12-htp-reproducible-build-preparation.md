# P12 Snapdragon HTP runtime build preparation

Phase: `P12`

**Status:** first GitHub Actions attempt reached pinned source checkout and source SPDX generation, then failed because CMake was invoked from the Ternuxx workspace instead of the upstream `llama.cpp` directory. No runtime artifact or reproducibility result was produced; the working-directory fix is prepared for a rerun. No public release was created.

## Build contract

The manual workflow `.github/workflows/p12-htp-reproducible-build.yml` is restricted to the `main` ref and builds the Android ARM64 Snapdragon runtime twice on independent Ubuntu 24.04 runners. It fetches the upstream `b11849` tag and rejects it unless it resolves to commit `0ae0e1976670fac25f4e0ed864df30021accc764`. The source tag is shown as a verified signed commit on the [upstream release page](https://github.com/ggml-org/llama.cpp/releases/tag/b11849). The workflow follows the upstream Android Snapdragon CMake preset and relative install-RPATH settings from the pinned [upstream release workflow](https://github.com/ggml-org/llama.cpp/blob/b11849/.github/workflows/release.yml).

The Snapdragon Android toolchain is pinned to the GHCR OCI index digest `sha256:e39e5e9c0957550a92c0de756b7556d81196c7c7f7328ed80de252bfb4878adf`, resolved from `ghcr.io/snapdragon-toolchain/arm64-android:v0.8`. GitHub Actions and SBOM actions are pinned to full commits. The artifact packager creates a fixed-time tar archive using the upstream source commit epoch and includes only `llama-cli`, direct `.so` runtime files, and the upstream MIT `LICENSE`. It rejects symlinks, unexpected paths, missing HTP/OpenCL libraries, and packages that exceed the current installer extraction limit. A manifest records source/build inputs and each runtime file's size/hash. SPDX SBOMs are requested for both source and packaged runtime.

The verify job independently validates each archive and manifest, then requires byte-identical archive SHA-256 values. A successful run would upload a 90-day internal Actions candidate, not a GitHub Release. The runtime installer pin in `lib/npu_inference.py` is intentionally unchanged until a built candidate passes device tests and distribution review.

## Local validation and limits

- `python3 -m unittest tests.test_package_snapdragon_release`: **5 passed** (deterministic packaging, archive tamper rejection, file and directory symlink rejection, pinned-source manifest rejection).
- Initial clean-`main` suite: **1,339 tests, 4 stale installer/CLI-help assertion failures**. Updated only those assertions to match current help/output; the rerun passed **1,339 tests in 201.589 seconds**.
- The four focused stale tests passed; `bash tests/test_cli_help.sh` passed.
- `python3 -m py_compile tools/package_snapdragon_release.py tests/test_package_snapdragon_release.py`: passed.
- Workflow YAML parsed and its pinned image/matrix structure checked with PyYAML; `git diff --check` passed.
- GitHub run [`40962133386`](https://github.com/soobujmiah/ternuxx/actions/runs/40962133386) failed in the CMake configure step on both runners: it searched the Ternuxx workspace root for `CMakePresets.json`. The follow-up now changes into `upstream` before invoking the pinned preset. GitHub listed no run artifacts. No runtime archive was produced. No cross-run reproducibility, Android install, model correctness, thermal/sustained qualification, license clearance, or public release is claimed.

## Remaining release gates

First run the manual workflow and inspect the source/runtime SPDX output and two-build comparison. Then device-test the Ternuxx-owned candidate on the pinned model with correct output, complete HTP offload, failure/restart behavior and telemetry; qualify GPU/CPU fallback and setup selection; close Mesa and full dependency-license/provenance review; resolve the Ternuxx project license and clean-install/release acceptance. The QNN SD1.5 image route has its own independent oracle and Qualcomm license-acceptance gates; this chat runtime build does not close them.

## Evidence

- Workflow: `.github/workflows/p12-htp-reproducible-build.yml`.
- Deterministic package tool: `tools/package_snapdragon_release.py`.
- Local package tests: `tests/test_package_snapdragon_release.py`.
- The clean-worktree full-suite command is `python3 -m unittest discover -s tests`.
