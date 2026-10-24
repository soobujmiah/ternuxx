# P12 corrected CPU suite guarded cancellation — 2026-10-24

Phase: `P12` — in progress  
Evidence class: live Native Termux bounded qualification attempt  
Observed: 2026-10-24 16:55 UTC

## Evidence

The corrected `arithmetic-operators-v1` CPU suite was invoked with three runs, eight output tokens, and a five-second guarded interval between runs. Preflight passed: CPU 55.3°C, GPU 45.9°C, HTP 48.7°C, battery 39.73°C, `socd` 64.0°C, and `MemAvailable` 5,093,740 KiB. The configured CPU guard was 60°C; the `socd` guard was 70°C.

The first addition case started but was cancelled by the runner after a sampled CPU temperature reached 71.2°C. It ran for 3.126 seconds; no case completed successfully and no answer was verified. The final sample reported CPU 58.1°C and GPU 47.9°C. The post-run inventory found no remaining `llama-cli` process. No Vulkan or HTP inference was started after the CPU guard cancellation.

## Qualification boundary

This is a guarded cancellation, not a passing CPU result and not a preflight-only block. It demonstrates that the runtime guard can stop an in-flight call and leave no visible inference process. It does not establish whether the 71.2°C sample represents a sustained temperature or an isolated sensor excursion, and it is not an OEM-rated thermal limit. Do not raise the guard to force a pass. Correctness remains unverified for this run; Vulkan and HTP corrected-suite reruns remain open.

## Validation

- `python3 tools/native_accel_qualify.py --backend cpu --runs 3 --max-tokens 8 --idle-seconds 5`: structured report returned one `guard_cancelled` run, `completed_runs=0`, and `ok=false`.
- Post-run process inventory in the report: `new_llama_cli_pids_remaining=[]`.

## Follow-up preflight — 17:50 UTC

A later invocation of `python3 tools/native_accel_qualify.py --backend cpu` stopped before inference because the single preflight sample reported `socd=74.0°C`, above the configured 70°C guard. CPU was 48.5°C, GPU 42.8°C, HTP 43.6°C, battery 39.18°C, and `MemAvailable` 4,573,860 KiB. It completed zero runs and returned `preflight guard failed; no inference started`; the structured report is in [`data/2026-10-24-p12-cpu-preflight-1750z.json`](data/2026-10-24-p12-cpu-preflight-1750z.json).

The owner clarified that ordinary use can include MLBB, YouTube, and phone calls, which can warm the device. That is context, not a timestamped workload trace or proof that any one activity caused this sensor reading; the qualification guard was left unchanged. The preflight itself started no model call, so it did not add inference load.
