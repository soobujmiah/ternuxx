# P12 owner-provided model routing integration

**Date:** 2026-10-30
**Phase:** `P12`
**Scope:** Native Ternuxx CPU, Vulkan, HTP, CLI, TUI, Web, and GTK model selection

## Change

The local inference allowlist now includes the existing Qwen2.5 1.5B Instruct Q4_0 GGUF at its owner-specified fixed path `/sdcard/LAI/models/qwen2.5-1.5b-instruct-q4-0.gguf`. The expected size is 1,066,227,232 bytes and expected SHA-256 is `dcd819ff094852c38faba6873d8ff0c9d51eadb2844539e52042ae5d647bbfdb`. The model is read-only and is not copied, downloaded, removed, or locked by writing beside it. Inference verifies the fixed path, regular-file type, exact size, and SHA-256 before use. The existing managed Qwen3 model remains the default.

`tx ai run --model qwen2.5-1.5b-instruct-q4_0` selects this model for CPU, Vulkan, NPU, or automatic routing. The shared service allowlists model IDs; TUI, Web, GTK, CLI, and desktop bridge pass the chosen ID through the same service. Automatic selection remains HTP, Vulkan, then CPU, and a selected backend failure is returned without a hidden retry. The management catalog describes the owner model as fixed-path and read-only.

## Verification in this worktree

- Focused cross-client AI/runtime/install group: `python3 -m unittest tests.test_ai_backend_selection tests.test_cpu_inference tests.test_management_service tests.test_terminal_ui tests.test_management_http_runtime tests.test_management_desktop_bridge tests.test_management_center_ui_contract tests.test_install_wizard tests.test_launch_commands`: 327 passed.
- Full repository suite: `bash scripts/repo_test.sh`: 1,370 passed in 249.553 seconds; CLI help contract passed.
- `bash tests/test_cli_help.sh`: passed.
- `python3 -m py_compile lib/cpu_inference.py lib/npu_inference.py lib/management_service.py lib/terminal_ui.py scripts/management_desktop_bridge.py`: passed.
- `python3 -m tools.repo_knowledge verify`: 0 findings. `python3 tools/doc_bridge.py check --strict --project-id ternuxx README.md`: passed. Document inventory refreshed and checked.
- `python3 -m py_compile ...` and `git diff --check`: passed.

These are fixture and source checks. This worktree did not inspect or read the shared-storage model and did not run inference. Device tests remain governed by the current thermal preflight gates in `CURRENT_STATE.md`; no backend is stable or release-qualified.

## Open gates

The branch is rebased onto current `origin/main` and the local full suite passes; hosted CI and review must pass before integration. Device qualification, including exact output, runtime/model integrity, telemetry, and controlled CPU/GPU/HTP comparisons, remains outstanding. Model distribution terms are unverified; this feature only references the owner's existing local file. Ternuxx project and transitive runtime licensing, installer multi-select, clean-install replay, signing, and release acceptance remain separate release gates.
