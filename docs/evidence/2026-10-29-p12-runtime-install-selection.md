# P12 Native AI runtime install selection

Phase: `P12`

**Status:** source implementation and fixture checks pass; clean-device installer application is unverified.

## Selection behavior

The guided workstation installer presents a multi-select for CPU, Vulkan, and experimental HTP0 when the corresponding device choices are supported. The default is HTP0 on SM8735; otherwise Vulkan when the Native GPU probe passes; otherwise CPU. The user may select multiple runtimes or explicitly choose no AI runtime. Selecting HTP0 automatically adds the Termux `llama-cpp` package for the required CPU fallback. Vulkan selection includes both `llama-cpp` and `llama-cpp-backend-vulkan`.

If HTP0 is selected, the installer stores the exact pinned runtime preview in the combined workstation plan before the single approval. The preview records the b11849 upstream asset, SHA-256, MIT notice, archive size, extraction bound, and whether network download is required. The reviewed plan includes the retained archive and extracted-runtime storage estimate. Installation is applied only after the combined approval and re-verifies the exact preview. The current installer still fetches the pinned MIT upstream asset; the reproducible Ternuxx candidate remains internal-only and is not its source.

## Validation

- `tests.test_install_wizard`, `tests.test_install_master`, and `tests.test_npu_inference`: **46 passed**.
- The master-plan coordinator fixture proves the HTP exact preview is collected before approval, apply occurs only after approval, and rejection never downloads or installs HTP.
- `bash -n lib/install_wizard.sh lib/install_master.sh lib/phases.sh`, `python3 -m py_compile lib/install_master_plan.py lib/npu_inference.py`, and `git diff --check` passed.
- The first full repository run exposed one stale expected omitted-component list. After updating it, `bash scripts/repo_test.sh` passed **1,356 tests in 244.986 seconds**. The initial failure and correction are preserved here.
- No package transaction, runtime download, or fresh device install was performed by these fixture tests.

## Remaining gates

A fresh Native install must exercise each selected runtime combination and prove the actual Termux package transaction, HTP archive integrity, backend probes, and rollback/recovery behavior. Then run controlled model inference after two fresh thermal preflight samples. The internal Ternuxx HTP build candidate still needs device qualification; the owner has selected GPL-3.0-or-later for original project source; third-party runtime redistribution, provenance, and device qualification remain open.

## Evidence

- Bengali version: [2026-10-29-p12-runtime-install-selection.bn.md](2026-10-29-p12-runtime-install-selection.bn.md).
- Installer: `lib/install_wizard.sh`, `lib/install_master.sh`, `lib/install_master_plan.py`, and `lib/phases.sh`.
- Tests: `tests/test_install_wizard.py`, `tests/test_install_master.py`, and `tests/test_npu_inference.py`.
