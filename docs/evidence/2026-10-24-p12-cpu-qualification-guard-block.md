# P12 CPU qualification preflight guard — 2026-10-24

Phase: `P12` — in progress
Evidence class: live Native Termux preflight observation
Recorded: 2026-10-24 14:37 UTC

## Evidence

The guarded qualification command was attempted on Native Termux:

```sh
python3 tools/native_accel_qualify.py --backend cpu --runs 3 --max-tokens 8 --idle-seconds 5
```

It returned exit code 2 before starting inference. Preflight reported CPU 44.2°C, GPU 38.8°C, HTP 39.6°C, battery 38.04°C, SoC (`socd`) 70.0°C, and `MemAvailable` 4,934,056 KiB. The configured SoC stop guard is 70°C, so equality correctly blocks the run. A separate read approximately 30 seconds later still reported `socd=70.0°C`; no threshold was raised and no CPU inference was started.

## Interpretation

After the repository suite completed at 14:41 UTC, a fresh read reported CPU 48.1°C, GPU 43.6°C, HTP 44.4°C, battery 40.49°C, and `socd=71.0°C` with `MemAvailable` 4,050,368 KiB. This remained above the stop guard, so no corrected inference rerun was attempted.

This is a safe preflight deferral, not a CPU inference failure and not a passing CPU qualification. Retry the corrected known-answer runner only after a fresh live preflight is below every configured guard. Existing CPU workload evidence remains in [CPU baseline](../testing/CPU-BASELINE.md); the qualification runner's CPU path has not yet been live-accepted.

## Follow-up — 2026-10-24 15:04 UTC

After the 1025-test repository suite completed successfully, a fresh read-only snapshot reported CPU 54.5°C, GPU 47.5°C, HTP 49.5°C, battery 42.57°C, `socd=77.0°C`, and `MemAvailable=3,977,032 KiB`. The SoC remains above the configured 70°C guard; no inference was started. This later observation supersedes the earlier temperature readings for current readiness, but does not change the qualification result.

At 15:06 UTC the bounded qualification command was then run for all three backends (`cpu`, `vulkan`, and `npu`) with the default guards and three requested runs. Each returned exit code 2 with `preflight guard failed; no inference started`, identifying only `socd=78.0°C` against the 70°C guard. The three snapshots had 3,976,192, 3,975,280, and 3,974,948 KiB available respectively. `completed_runs` was absent from each report because all three stopped before inference. No backend answer was measured.
