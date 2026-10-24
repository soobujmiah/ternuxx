# P12 single-case Native backend checks

**Observed:** 2026-10-24 19:24:52–19:25:12 UTC  
**Host:** Native Termux, Android 16, aarch64  
**Model:** pinned `qwen3-0.6b-q4_0`  
**Runner:** `tools/native_accel_qualify.py`, `arithmetic-operators-v1`

## Result

One guarded eight-token addition case passed on each backend. The runner parsed and verified the exact expected answer, sampled resource use during each call, and reported no new `llama-cli` process remaining after any run.

| Backend | Preflight CPU/GPU/HTP | Peak sampled CPU/GPU/HTP | Minimum `MemAvailable` | Inference | Verification |
| --- | --- | --- | ---: | --- | --- |
| CPU | 49.7/43.6/44.8°C | 59.7/47.1/50.7°C | 3,848,300 KiB | 2.34 s; 0 GPU layers | Exact answer passed |
| Vulkan0, Adreno 825 | 48.9/44.4/45.1°C | 54.5/53.5/48.7°C | 3,369,972 KiB | 2.70 s; 29/29 GPU layers | Exact answer passed |
| HTP0, SM8735 | 50.1/44.8/45.9°C | 56.9/48.7/56.3°C | 3,482,492 KiB | 4.574 s; 29/29 NPU layers; `silent_fallback=false` | Exact answer passed |

The unchanged runner guards were CPU/GPU/HTP 60°C, battery 45°C, SoC 70°C, and minimum available memory 2,048 MiB. Each run stayed within them. The CPU sample reached 59.7°C, close to its configured stop guard.

## Qualification boundary

These are three single-case checks, not the configured three-case addition/subtraction/multiplication suite, a repeated stability run, or a device safety/thermal-limit claim. The corrected multi-case runs remain pending. Do not infer general model/operator correctness or release readiness from these results.
