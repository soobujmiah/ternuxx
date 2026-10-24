# P12 CPU repeated-suite guard cancellation

**Observed:** 2026-10-24 19:40:54 UTC  
**Host:** Native Termux, Android 16, aarch64  
**Command:** `python3 tools/native_accel_qualify.py --backend cpu --runs 3 --max-tokens 8 --timeout 90 --idle-seconds 5`

## Result

The preflight passed with CPU 51.3°C, GPU 46.3°C, HTP-related 48.3°C, battery 42.59°C, SoC-related 57.0°C, and `MemAvailable` 3,888,060 KiB. The first addition case reached the configured CPU stop guard at a sampled 60.0°C after 5.084 seconds. The runner cancelled the in-flight call; **zero of three cases completed**, so no answer was verified. The minimum sampled `MemAvailable` was 3,729,020 KiB, and the exact-name process check found no remaining `llama-cli` process.

The configured CPU/GPU/HTP, battery, SoC, and memory guards remained 60°C, 60°C, 60°C, 45°C, 70°C, and 2,048 MiB. They were not changed. This is a non-passing cancellation record, not a CPU workload result, OEM limit, or proof of sustained thermal behavior.
