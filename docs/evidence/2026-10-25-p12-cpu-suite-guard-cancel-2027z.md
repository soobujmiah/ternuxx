# P12 guarded CPU suite cancellation at 20:27 UTC

**Observed:** 2026-10-24 20:27:40 UTC (2026-10-25 02:27:40 Asia/Dhaka)  
Phase: `P12` — Native CPU/Vulkan/HTP workload qualification  
**Evidence class:** live Native Termux bounded-runner output

## Evidence

The command below printed a structured runner report directly in the active Native Termux session. Its guard settings, preflight readings, thermal samples, completion status, and post-run process snapshot are summarized here.

## Result

Ran `python3 tools/native_accel_qualify.py --backend cpu --runs 3` in Native Termux on Android 16, `aarch64`, with the runner's unchanged 60°C CPU/GPU/HTP guards, 45°C battery guard, 70°C SoC guard, and 2 GiB minimum-memory guard. Preflight passed, then the first addition case was cancelled when a sampled CPU-zone temperature reached 64.1°C. The suite completed 0 of 3 cases and verified no answer.

| Measurement | Result |
| --- | ---: |
| Preflight CPU / GPU / HTP | 50.1 / 45.9 / 47.1°C |
| Preflight battery / SoC | 41.86 / 68.0°C |
| Preflight `MemAvailable` | 4,202,012 KiB |
| Cancellation sample CPU / GPU / HTP | 64.1 / 47.1 / 49.1°C |
| Lowest sampled `MemAvailable` | 4,142,704 KiB |
| Workload elapsed | 5.476 s |
| Peak observed `llama-cli` RSS | 39,560 KiB |
| Post-cancellation CPU / GPU / HTP | 49.7 / 46.3 / 46.7°C |
| Completed cases / requested cases | 0 / 3 |
| Remaining `llama-cli` PIDs | none |

## Interpretation and limits

This is a guarded cancellation, not a correctness or sustained-qualification pass. A short CPU workload crossed the configured conservative test guard despite a lower preflight reading. No guard was changed or bypassed, and no unrelated process was targeted. The output does not establish why the device was warm or establish an OEM thermal limit. Do not treat the post-cancellation snapshot as sustained-load evidence.

## Command

```sh
python3 tools/native_accel_qualify.py --backend cpu --runs 3
```

The measurements above were transcribed from the live runner JSON printed in this Native Termux session; no model prompt output or private runtime data is included.
