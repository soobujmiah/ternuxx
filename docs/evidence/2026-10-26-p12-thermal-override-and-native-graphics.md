# P12 thermal override and Native graphics recheck

The owner requested that conservative temperature thresholds not hold up the current qualification work. Added `--ignore-thermal-limits` to the bounded Native inference runner. This explicit per-run override retains temperature readings in the report but does not block or cancel on them; minimum available memory, per-call timeout, existing `llama-cli` refusal, and orphan-process checks remain enforced. The default guarded behavior is unchanged.

Validation:

- Focused runner and graphics tests passed: 34 tests.
- On Native Android 16/aarch64, one Vulkan qualification case started with SoC at 73.0°C while the override was active. It failed before inference because `llama-cli` is unavailable; zero cases passed and no inference process remained.
- Native `:1` OpenGL off-screen workload rendered successfully on `llvmpipe (LLVM 21.1.8, 128 bits)`, score 142. This confirms software rendering only, not GPU acceleration.
- Native `:1` GLES workload was unavailable (`exit_code=127`); no GLES draw was verified.
- Native Vulkan verification reported no valid GPUs in the current loader configuration; no draw was attempted.

These results are route-specific snapshots. They do not qualify Native GPU acceleration or inference. The runner JSON observed time was `2026-10-25T20:41:17Z`; repository documentation date follows the local Asia/Dhaka date (2026-10-26).
