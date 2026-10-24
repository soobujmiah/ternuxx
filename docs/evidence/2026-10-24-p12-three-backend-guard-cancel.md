# P12 CPU, Vulkan, and HTP one-call guarded cancellations — 2026-10-24

Phase: `P12` — in progress  
Evidence class: live Native Termux bounded qualification attempts  
Observed: 2026-10-24 18:31–18:32 UTC

## Evidence

One corrected eight-token addition case was attempted on each backend with the configured 60°C CPU guard, 60°C GPU/HTP guards, 45°C battery guard, 70°C SoC guard, and 2 GiB minimum-memory guard. All three preflights passed, but each in-flight call was cancelled within 0.46–0.47 seconds when a CPU-zone sample crossed 60°C: CPU 61.3°C, Vulkan 60.5°C, and HTP 62.1°C. Each run completed zero cases and verified no answer. Minimum `MemAvailable` was 3,918,252 KiB (CPU), 3,925,584 KiB (Vulkan), and 3,917,384 KiB (HTP), above the configured 2 GiB guard. All reports listed no remaining `llama-cli` processes.

The complete per-run sensor samples, commands, thresholds, timings, cancellation results, and process inventories are preserved in [`data/2026-10-24-p12-three-backend-guard-cancel-1832z.json`](data/2026-10-24-p12-three-backend-guard-cancel-1832z.json).

## Qualification boundary

These are in-flight guarded cancellations, not preflight blocks or passing correctness results. They do not show a sustained sensor temperature, identify what caused the readings, or establish an OEM thermal limit. The owner noted that normal use can include MLBB, YouTube, and phone calls; timing/correlation with these samples was not established. No guard was raised. Corrected CPU, Vulkan, and HTP answers remain unverified, as do sustained qualification and broader workload coverage.

## Validation

- Commands: `python3 tools/native_accel_qualify.py --backend {cpu,vulkan,npu} --runs 1 --max-tokens 8 --timeout 90 --idle-seconds 0` (run separately for each backend).
- Each structured report returned `completed_runs=0`, `ok=false`, and `status=guard_cancelled`.
- Each report recorded `new_llama_cli_pids_remaining=[]`.
