# P12 automatic inference backend routing

Phase: `P12`

**Observed:** 2026-10-29 22:27 UTC
**Scope:** Native Termux `tx ai run` automatic backend choice
**Status:** implementation and selection path observed; model inference remains unqualified

## Required routing

The owner requires automatic runtime priority `SM8735 HTP0 → Vulkan GPU → CPU fallback`, with CPU not the default. Explicit `--backend cpu|vulkan|npu` continues to force one backend. Hardware selection is resolved before inference. Once an inference attempt starts, an error is returned with the selected backend and is not silently retried elsewhere; this keeps offload failures and repeated work visible.

The shared Ternuxx service now implements `inference.auto.run`. It probes HTP0 first and only probes Vulkan if HTP0 is unavailable. It chooses the first valid Vulkan device reported by llama.cpp, otherwise CPU. Successful output includes `backend_selection`, including probe errors and the no-retry policy. CLI, TUI, Web, and GTK expose this action.

## Live Native observation

At 2026-10-29 22:27:12 UTC, read-only status reported SM8735 HTP0 available with runtime `b11849`, and Termux `llama-cpp` 0.7.0 available. Ternuxx's pinned Qwen3 0.6B Q4_0 model was missing at its app-private model path.

The default command `printf '2 + 2 = ? reply with one digit' | bash tx ai run --max-tokens 1` returned `inference_failed` with `Automatic routing selected npu; inference failed (InferenceError) and was not retried on another backend`. The subsequent exact `pgrep -x llama-cli` check found no process. Therefore routing selected NPU, but no inference started and no output, latency, offload, token rate, memory, or thermal result was produced. This was a model-absence guard check, not an HTP workload test.

## Verification

- `tests/test_ai_backend_selection.py`: priority order, unusable device values, and CPU fallback fixtures.
- `tests/test_management_service.py`: NPU/Vulkan/CPU dispatch and no retry after a selected NPU failure.
- `tests/test_terminal_ui.py`: TUI preferred-backend action.
- `tests/test_management_desktop_bridge.py`: GTK bridge route.
- `tests/test_management_http_runtime.py`: Web action and authorization contract.
- Focused cross-client routing run after the Web script correction: **260 tests passed**, including the inline Web JavaScript syntax check; `bash tests/test_cli_help.sh`, `py_compile`, and `git diff --check` passed.
- The first full suite run completed **1,351 tests with one error**: the newly added Web action had an extra closing brace. That defect was corrected.
- Corrected full repository run: `bash scripts/repo_test.sh` passed **1,351 tests in 216.919 seconds**. `python3 -m tools.repo_knowledge verify` reported 0 findings; `python3 tools/doc_bridge.py check --strict --project-id ternuxx README.md` passed.

## Remaining gates

The model must be available through an owner-approved Ternuxx private model path before controlled CPU/HTP comparisons can run. The project instruction forbids Ternuxx from traversing shared `/sdcard` storage, so no LAI model there was accessed. Two fresh thermal preflight samples are required before any inference sequence; subsequent runs must record answer correctness, exact layer offload, model SHA-256, backend, token counts, elapsed time, process cleanup, and sampled thermal/memory telemetry.

The guided installer now has a CPU/Vulkan/HTP multi-select, with choices gated by device probing: HTP on SM8735, Vulkan when its Native probe is supported, and CPU fallback. Defaults are HTP on SM8735, otherwise Vulkan when supported, otherwise CPU. Selecting HTP also selects the CPU fallback package. The installer uses the pinned upstream b11849 archive; it does not install the Ternuxx-built internal candidate. See the [runtime install selection report](2026-10-29-p12-runtime-install-selection.md). A fresh-device install and rollback remain unverified. The internal candidate still needs device qualification and distribution clearance; Mesa provenance and public release remain open. Image-generation/QNN qualification is a separate workload and is not covered by this chat inference route.

## Installer selection status update — 2026-10-30

A current source/fixture recheck confirms the guided installer selection implementation: `tests.test_install_wizard`, `tests.test_install_master`, and `tests.test_npu_inference` passed **50 tests** on 2026-10-30. This validates selection and install-plan fixture contracts, not a fresh-device package transaction, runtime download, or HTP workload.

## Evidence

Bangla version: [2026-10-29-p12-auto-backend-routing.bn.md](2026-10-29-p12-auto-backend-routing.bn.md).

- Implementation: `lib/ai_backend_selection.py`, `lib/management_service.py`, and `lib/ai.sh`.
- Client integration: `lib/terminal_ui.py`, `lib/management_web_ui.html`, `apps/management-center/management-center.c`, and `scripts/management_desktop_bridge.py`.
- Tests: `tests/test_ai_backend_selection.py`, `tests/test_management_service.py`, `tests/test_terminal_ui.py`, `tests/test_management_http_runtime.py`, `tests/test_management_desktop_bridge.py`, `tests/test_management_center_ui_contract.py`, and `tests/test_cli_help.sh`.
- Live observation is limited to Native HTP0/runtime status and the missing-model refusal described above; no live workload was run.
