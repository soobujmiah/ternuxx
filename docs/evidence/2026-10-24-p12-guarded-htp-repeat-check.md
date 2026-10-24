# P12 guarded Native HTP repeat check — 2026-10-24

Phase: `P12` — in progress
Evidence class: live Native Termux device observation
Recorded: 2026-10-24 14:34 UTC

## Environment and method

The live shell was Native Termux on Linux `6.6.77-android15`, `aarch64`. The pinned `qwen3-0.6b-q4_0` model and experimental b11849 HTP0 runtime were available for SM8735. The guarded runner sampled CPU, GPU, HTP, battery, SoC and available memory during each call and between calls. Its 60°C CPU/GPU/HTP, 45°C battery, 70°C SoC and 2048 MiB available-memory thresholds are conservative test guards, not OEM-rated limits.

Command:

```sh
python3 tools/native_accel_qualify.py --backend npu --runs 3 --max-tokens 8 --idle-seconds 5
```

The default known-answer prompt was `2 + 2? Reply with one digit.`. The runner was configured to interrupt its own process group if a guard or timeout was reached.

## Evidence

The runner exited 0 with `ok=true`; all three calls passed on `HTP0`, each reporting **29/29 HTP layers**, `silent_fallback=false`, and a 319.96 MiB HTP model buffer. Per-call wrapper times were 5.971s, 5.960s and 6.029s. Peak visible `llama-cli` RSS was 177,588 KiB. Per-call minimum sampled `MemAvailable` was 4,469,232 KiB, 4,465,120 KiB and 4,484,836 KiB (lowest: approximately 4.26 GiB). No new `llama-cli` process remained after any call.

Preflight sampled CPU 46.1°C, GPU 40.8°C, HTP 41.2°C, battery 39.66°C, SoC 69°C and `MemAvailable` 5,113,600 KiB. All calls and guarded idle intervals completed without triggering a stop guard.

## Limits and next gate

This is a short repeated check of one pinned model on one device. The HTP path remains experimental. It does not establish sustained thermal stability, broad model/operator correctness, OEM thermal limits, clean-install reproducibility, or release readiness. P12 remains open; see the [qualification procedure](../testing/NATIVE-ACCEL-QUALIFICATION.md) and [Vulkan repeat result](2026-10-24-p12-guarded-vulkan-repeat-check.md).
