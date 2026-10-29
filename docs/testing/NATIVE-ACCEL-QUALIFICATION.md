# Native accelerator qualification

This guide describes a bounded, repeatable check for Ternuxx's Native Termux CPU, Vulkan, and experimental Hexagon HTP inference routes. It is intended for engineering qualification, not as a benchmark or a claim of sustained thermal stability.

## Preconditions

- Run from the Ternuxx repository on Native Termux. The tool identifies itself as `native-termux` and does not operate inside Debian PRoot.
- `tx ai status --json` must report the pinned local model and the expected llama.cpp runtime. GPU and HTP checks also require their corresponding runtime to be configured.
- Keep the phone under its normal system thermal controls. The tool reads available Linux thermal zones and `/proc/meminfo`; it does not change Android thermal policy or install packages.
- Do not start another `llama-cli` inference while the check is running. The tool refuses to start if one is already visible in `/proc`.

## Run a check

Start with a non-executing preview:

```sh
python3 tools/native_accel_qualify.py --backend vulkan --preview
```

Then run one backend at a time:

```sh
python3 tools/native_accel_qualify.py --backend cpu
python3 tools/native_accel_qualify.py --backend vulkan
python3 tools/native_accel_qualify.py --backend npu
```

Defaults are three sequential calls, eight generated tokens per call, a five-second monitored idle interval between calls, and a 90-second per-call timeout. The fixed, versioned `arithmetic-operators-v1` suite cycles through addition (`2 + 2`), subtraction (`9 - 4`), and multiplication (`3 * 2`) cases. Each run accepts only the exact digit or the exact expression followed by `=` and that digit, with optional terminal punctuation. The JSON report records each `case_id`, scheduled case IDs, and `answer_verified`; it goes to stdout. Redirect it to a private, access-controlled evidence location if it must be retained. Do not place runtime credentials or model output in committed evidence.
To record a standalone guarded thermal/resource sample without starting inference, use `--preflight-only`:

```sh
python3 tools/native_accel_qualify.py --backend npu --preflight-only
```

Each invocation returns one timestamped sample and exits 0 only when the required CPU/HTP sensors are readable, all observed temperatures remain below the configured guards, available memory meets the minimum, and no `llama-cli` process is present. Run it again for a second independent sample. The output states `will_start_inference: false`; this mode does not require the model file.

Useful bounded overrides include `--runs`, `--max-tokens`, `--timeout`, and `--idle-seconds`; the tool constrains each to a documented finite range. Its CPU/GPU/HTP/battery/SoC temperature and minimum-memory thresholds are conservative stop guards for that run, not OEM-rated limits or universal safety thresholds. By default, a missing CPU/backend sensor or `MemAvailable` reading blocks inference rather than silently weakening the guard. The owner-authorized `--ignore-thermal-limits` option makes temperature readings observational for that run and removes missing-temperature-sensor preflight blocking; the minimum-memory check, timeout, existing-process refusal, and orphan detection remain active. The JSON report records this override and all available temperature samples.

## Pass criteria and cancellation

A run passes only if `tx ai run` exits successfully, returns the exact known answer from the requested backend, and reports the expected layer counts: positive complete Vulkan offload, positive complete HTP offload with `silent_fallback=false`, or CPU with zero GPU layers. The report includes resource samples, minimum available memory, peak visible `llama-cli` RSS, and any new exact-name `llama-cli` processes remaining after the call.

If a guard is reached or a call times out, the tool sends SIGINT to the process group it started, waits for cleanup, and records a non-passing result. It does not kill unrelated process IDs. Review the JSON and confirm the exact-process inventory is empty before starting another inference. A cancellation or a short repeated pass is not evidence of long-duration stability, OEM thermal limits, or correctness across other models and operators.

## Evidence

The 2026-10-26 P12 follow-up records three-case and ten-call repeat, answer-verified CPU, Vulkan, and experimental HTP runs with the owner-authorized thermal override; Vulkan and HTP each proved 29/29 layer offload. See [Native Adreno 825 acceleration and inference evidence](../evidence/2026-10-26-p12-native-adreno825-acceleration-and-inference.md).

The first three-call Vulkan and HTP backend/offload observations are recorded in the [P12 guarded Vulkan repeat check](../evidence/2026-10-24-p12-guarded-vulkan-repeat-check.md) and [P12 guarded HTP repeat check](../evidence/2026-10-24-p12-guarded-htp-repeat-check.md); those initial runner revisions did not verify the answer. On 2026-10-26, the corrected runner passed all three CPU and all three Vulkan known-answer cases under the owner-requested `--ignore-thermal-limits` override; every Vulkan run proved complete 29/29-layer Adreno 825 offload. See [Native Adreno 825 acceleration and inference evidence](../evidence/2026-10-26-p12-native-adreno825-acceleration-and-inference.md). Earlier guard cancellations remain historical evidence, not the current state. Sustained performance, OEM thermal qualification, wider model/operator coverage, and release gates remain open; keep them tracked in [phase status](../PHASE-STATUS.md).

## Mesa source-to-package build audit

The pinned Mesa source-header scan does not identify which source files entered the configured host and aarch64 builds or which files landed in each split package. To collect that missing evidence, dispatch the repository's **P12 Mesa build provenance** workflow from GitHub Actions. It checks out the pinned Termux recipe commit and its pinned Mesa source commit, uses the package-builder OCI digest recorded in the workflow, and adds capture hooks that run only when the audit environment flag is set. The capture includes Meson target/options/dependency records, Ninja commands and targets for the host and target builds, and hashes and paths for each built `.deb` payload.

The pinned builder's restricted AppArmor profile denies writes below `/home/builder/termux-packages/` except for its package-output directory. Capture therefore goes to `/home/builder/p12-mesa-evidence` inside the builder container, then `docker cp` copies it into the workflow artifact directory after the build command exits. The workflow uploads metadata and build-graph files only; it does not upload the `.deb` archives or publish an installer. Review the artifact against its `build-metadata.json` and source/license inventory before changing any SPDX conclusion. A successful workflow run establishes build provenance inputs, not a complete component-license determination or redistribution approval.
