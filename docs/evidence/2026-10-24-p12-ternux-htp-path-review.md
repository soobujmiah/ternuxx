# P12 external HTP path review — 2026-10-24

Phase: `P12` (research snapshot captured before implementation; P11 has since closed)

**Current-state note:** The recommendation below was the next step at the time of this research snapshot. P12 later implemented an independent pinned Native llama.cpp HTP0 client in `lib/npu_inference.py`. Current implementation and qualification status are recorded in [NPU acceleration](../testing/NPU-ACCELERATION.md) and the [P12 live-check follow-up](2026-10-24-native-acceleration-live-check.md). This historical research did not import Ternux or LAI source or runtime artifacts.

## Evidence

No local Ternux or LAI checkout exists in the Native Termux home, so the owner-research check used the canonical GitHub repositories. `git ls-remote` verified Ternux `main` at `9fda63162426f77ee575b5f6729d8799a30f51b7` and LAI `main` at `aeeccb4fdd896b3a0560e1e8f69f84c61ebea492` on 2026-10-24. The Ternux revision matches the commit already cited in the repository's historical research.

Ternux's [experimental HTP guide](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/guides/llama-htp-experimental.md) and [accelerator release plan](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/docs/ACCELERATOR-RELEASE-PLAN.md) describe a Linux ARM64 llama.cpp package connected to a Ternux Binder/FastRPC broker. They report that workflow artifact `38560288558` installed into an isolated HOME, generated the known answer `4`, assigned all 31 layers to HTP0, exited successfully, and closed the HTP session; its bounded SIGINT check exited 130 after child shutdown and clean session close.

That same-device result is external research, not a Ternuxx run and not proof that an ordinary Native Termux process can open the HTP path. The owner records HMX `MUL_MAT` failures, reproducible flash-attention numerical failures, a broad HVX operator run with 45 numerical errors and a DSP queue abort, no automatic CPU/Vulkan fallback, and unqualified restart/sustained behavior. LAI's [device pass](https://github.com/soobujmiah/lai/blob/aeeccb4fdd896b3a0560e1e8f69f84c61ebea492/docs/device-results/2026-09-04-redmi-turbo-4-pro-hexagon-htp-qualify-pass.md) and [repeatability/quantization follow-up](https://github.com/soobujmiah/lai/blob/aeeccb4fdd896b3a0560e1e8f69f84c61ebea492/docs/device-results/2026-09-04-redmi-turbo-4-pro-hexagon-reproducibility-and-quant-limit.md) remain Android-app lifecycle results, separate from Ternuxx.

This review downloaded or installed no external artifact and copied no external code. It leaves Ternuxx NPU inference unimplemented and unavailable. It refines the next P12 experiment toward a separately implemented, least-privilege Android Binder/QAIRT or broker client, with only correctness-qualified HTP operations exposed behind an explicit experimental mode. The upstream Android `b11849` linker failure remains a separate, already tested route; repeating it is not a useful next step.

## Next action

After P11 closes, review public Android Binder/QAIRT interfaces and the exact app UID/session boundary; design the independent Ternuxx client; then test a compatible Q4_0 workload with HTP delegation logs, CPU-reference correctness, cancellation and restart, memory, thermal behavior, and repeats. Keep known-failing HMX/attention paths disabled. Finish sustained CPU/Vulkan qualification separately.
