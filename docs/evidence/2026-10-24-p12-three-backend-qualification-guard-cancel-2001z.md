# P12 three-backend qualification guard cancellations at 20:00 UTC

**Observed:** 2026-10-24 20:00:42–20:01:06 UTC
Phase: `P12` — Native CPU/Vulkan/HTP workload qualification
**Evidence class:** live Native Termux bounded-runner output

## Evidence

Observed the native_accel_qualify runner output directly in Native Termux. The complete measurements are summarized below.

## Result

The corrected `arithmetic-operators-v1` runner was invoked sequentially for CPU, Vulkan, and HTP, requesting three cases per backend with the runner's unchanged 60°C CPU/GPU/HTP guards, 45°C battery guard, 70°C SoC guard, and 2 GiB minimum-memory guard. Each preflight passed. Each first addition case was then cancelled when a sampled CPU-zone value reached or exceeded 60°C. No case completed, no answer was verified, and all three reports listed an empty `new_llama_cli_pids_remaining` array.

| Backend | Preflight CPU / GPU / HTP | Cancellation | Elapsed | Minimum `MemAvailable` | Peak `llama-cli` RSS |
| --- | --- | --- | ---: | ---: | ---: |
| CPU | 52.9 / 48.3 / 49.9°C | CPU 63.3°C | 3.557 s | 4,064,684 KiB | 551,808 KiB |
| Vulkan | 52.9 / 47.5 / 49.5°C | CPU 62.5°C; GPU peak 57.4°C | 4.255 s | 3,659,788 KiB | 243,208 KiB |
| HTP | 59.2 / 51.1 / 52.3°C | CPU 60.1°C | 8.044 s | 4,135,024 KiB | 97,856 KiB |

All three preflight `MemAvailable` readings exceeded 4 GiB. Battery remained below 45°C and the SoC sensor read 62°C, below the configured guard. After each cancellation the runner recorded an empty leftover-process list. The CPU suite reached zero completed cases; the same was true for Vulkan and HTP.

## Interpretation and limits

These are guarded cancellations, not correctness, backend-offload, or sustained qualification passes. A CPU-zone reading crossed the runner's conservative test guard in each run. The readings do not establish why the device was warm, establish an OEM thermal limit, or show sustained behavior. Ordinary concurrent phone use may contribute workload, but this test did not measure causality. No guard was changed or bypassed, and no unrelated process was targeted.

## Commands

```sh
python3 tools/native_accel_qualify.py --backend cpu --runs 3
python3 tools/native_accel_qualify.py --backend vulkan --runs 3
python3 tools/native_accel_qualify.py --backend npu --runs 3
```

The JSON reports were observed directly in the Native Termux session and are summarized here; no prompt output or private runtime data is committed.
