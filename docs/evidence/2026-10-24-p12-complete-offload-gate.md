# P12 complete accelerator offload gate — 2026-10-24

Phase: `P12`
Gate: PASS for full-layer enforcement; broader workload qualification remains open.

## Finding

CPU inference code selected Vulkan with `-ngl all` and checked that at least one layer was offloaded. HTP also checked only for a positive offload count. Both paths could report a successful accelerator run when the runtime assigned only part of the model, despite the docs and feature evidence requiring complete model-layer delegation.

## Correction

Vulkan and HTP now parse both offloaded and total layer counts and fail unless the counts are equal and positive. Vulkan results expose `gpu_layers` and `gpu_total_layers`; HTP results already expose both counts. CPU results report zero for both Vulkan-only fields. Partial offload cannot be silently treated as a qualified accelerator run.

Regression coverage rejects `22/29` Vulkan and `28/29` HTP delegation, while full `29/29` fixture output passes. Focused tests passed: 25 CPU-inference tests, 11 NPU-inference tests, and 51 management-service tests.

## Live bounded checks

On the Native Termux profile, `tx ai run --max-tokens 8` with the same prompt `2 + 2? Reply with one digit.` returned `2 + 2 = 4.` on all three explicit backends:

| Requested backend | Observed backend/device | Layer proof | Elapsed |
|---|---|---:|---:|
| CPU | CPU | GPU layers 0/0 | 2.426 s |
| Vulkan | Vulkan / `Vulkan0` | GPU 29/29 | 2.197 s |
| NPU | Hexagon HTP / `HTP0` | HTP 29/29 | 4.404 s |

Each command exited 0. No `llama-cli` process remained afterward. The three sequential smokes confirm the stricter gate accepts this device's exact current routes; they are not a comparable benchmark, and no sustained, thermal, or memory qualification is claimed. HTP remains experimental and the tested short prompt is slower than CPU.

## Evidence

- Source: `lib/cpu_inference.py`, `lib/npu_inference.py`.
- Regression tests: `tests/test_cpu_inference.py`, `tests/test_npu_inference.py`.
- Live command path: `tx ai run --backend cpu|vulkan|npu --max-tokens 8`, with the prompt supplied on stdin.
