# P12 Native Vulkan preflight blocked by SoC thermal guard

**Observed:** 2026-10-25 20:36 UTC (2026-10-26 02:36 Asia/Dhaka)
**Runtime:** Native Termux on Android 16, aarch64, PREFIX=/data/data/com.termux/files/usr
**Command:** python3 tools/native_accel_qualify.py --backend vulkan --runs 1 --max-tokens 4 --timeout 15 --idle-seconds 0

The bounded runner's preflight reported CPU 52.8°C, GPU 43.6°C, HTP 45.5°C, battery 41.32°C, SoC digital 72.0°C, and MemAvailable=4,395,632 KiB. The configured per-run SoC stop guard is 70°C. The runner returned exit code 2 with "preflight guard failed; no inference started"; zero of one cases ran.

This is a guard refusal, not a Vulkan pass or failure. No inference process was started by this command, no guard was changed or bypassed, and no PRoot/desktop workload was run. Native graphics status remains llvmpipe for OpenGL/GLES and Vulkan unavailable; this preflight does not test graphics rendering. Retest only after the runner's full preflight passes under the unchanged guards.
