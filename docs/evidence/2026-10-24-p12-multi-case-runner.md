# P12 multi-case CPU/GPU/HTP qualification runner — 2026-10-24

Phase: `P12` — in progress
Evidence class: source change, fixture tests, and live guarded preflight
Observed: 2026-10-24 15:22 UTC

## Change

The Native qualification runner now uses a fixed, versioned three-case arithmetic suite: addition (`2 + 2`), subtraction (`9 - 4`), and multiplication (`3 * 2`). Its default three calls therefore test distinct expected answers on every backend while keeping the existing token, timeout, memory, thermal, and process-cleanup bounds. Each report identifies the scheduled suite and each run's case ID. A pass accepts only the exact digit or the exact expression followed by `=` and that digit, with optional terminal punctuation. CPU passes additionally require `gpu_layers` to be an actual integer zero; missing, Boolean, or nonzero values fail closed.

## Evidence

- `python3 -m unittest tests.test_native_accel_qualify -v`: 10 tests passed, including each arithmetic case against CPU, Vulkan, and HTP-shaped results, full offload checks, HTP fallback rejection, strict CPU layer typing, and a structured guard report.
- `python3 -m unittest discover -s tests -p 'test_*.py' -q`: 1028 tests passed in 141.530 seconds.
- `python3 tools/native_accel_qualify.py --backend cpu|vulkan|npu --preview`: each preview reported `arithmetic-operators-v1`, the expected three case IDs, and `will_start_inference=false`.
- At 15:22 UTC the bounded runner was invoked once per backend without `--preview`. Each returned exit 2 with `preflight guard failed; no inference started` and `socd=79.0°C` against the 70°C guard. Each structured report contained the suite ID and three scheduled cases, `completed_runs=0`, and `runs=[]`.

| Backend | CPU / GPU / HTP / battery (°C) | SoC (°C) | `MemAvailable` (KiB) |
|---|---:|---:|---:|
| CPU | 45.0 / 42.0 / 43.6 / 40.54 | 79.0 | 4,021,180 |
| Vulkan | 45.3 / 42.4 / 43.2 / 40.53 | 79.0 | 4,020,228 |
| HTP | 45.3 / 42.0 / 43.2 / 40.52 | 79.0 | 4,016,904 |

## Qualification boundary

The suite and validators are fixture-tested, not live answer-tested in this update. Previous short one-prompt accelerator observations do not verify the newly added subtraction and multiplication cases. Run the full suite separately on CPU, Vulkan, and HTP after every configured guard is below its threshold; then continue sustained resource and clean-install qualification. Do not raise guards to force a run.
