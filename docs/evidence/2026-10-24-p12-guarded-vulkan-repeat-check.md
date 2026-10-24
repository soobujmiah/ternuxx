# P12 guarded Native Vulkan repeat check — 2026-10-24

Phase: `P12` — in progress
Evidence class: live Native Termux device observation
Recorded: 2026-10-24 14:25 UTC

## Environment and method

The live shell reported Linux `6.6.77-android15`, `aarch64`, with `PREFIX=/data/data/com.termux/files/usr` and `HOME=/data/data/com.termux/files/home`. The pinned `qwen3-0.6b-q4_0` model and llama.cpp 0.7.0 runtime were available. Thermal-zone and `/proc/meminfo` reads were available. No pre-existing exact `llama-cli` process was found.

Command:

```sh
python3 tools/native_accel_qualify.py --backend vulkan --runs 3 --max-tokens 8 --idle-seconds 5
```

The runner used its default prompt, `2 + 2? Reply with one digit.`, sampled thermal and memory state during each invocation and between calls, and used its conservative 60°C CPU/GPU/HTP, 45°C battery, 70°C SoC, and 2048 MiB available-memory stop guards. These are test guards, not OEM-rated limits.

## Evidence

The runner exited 0 with `ok=true`; all three sequential calls passed on `Vulkan0` with the pinned model and **29/29 GPU layers**. The per-call wrapper times were 3.201s, 3.950s, and 3.615s. Peak visible `llama-cli` RSS was 242,504 KiB. Per-call minimum sampled `MemAvailable` was 4,639,832 KiB, 4,637,712 KiB, and 4,621,608 KiB (lowest: approximately 4.41 GiB). No new `llama-cli` process remained after any call.

At preflight, sampled maxima were CPU 44.6°C, GPU 39.6°C, HTP 40.4°C, battery 39.16°C, and SoC 69°C; `MemAvailable` was 5,251,344 KiB. Every call and guarded idle interval completed without triggering a stop guard.

## Limits and next gate

This verifies a short, repeated known-answer Vulkan path on this device under the listed observations. It does not establish sustained thermal stability, broad model/operator correctness, an upstream-supported clean ICD installation, clean-device setup, or release readiness. P12 remains open for sustained resource qualification, reproducible Adreno 825 ICD provenance, broader HTP correctness, and clean-install/replay evidence. See the [qualification procedure](../testing/NATIVE-ACCEL-QUALIFICATION.md) for the repeatable command and guard semantics.
