# ADR-0002: Report accelerators per workload and process context
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** accepted
- **Type:** cli-tool

## Context

This workstation spans native Termux, Debian PRoot, Windows compatibility runtimes, Android host APIs, and possible local AI runtimes. Hardware nodes and libraries may exist without being accessible to a workload. Native Vulkan on the recorded Adreno 825 setup returned `VK_ERROR_INCOMPATIBLE_DRIVER`; the existing Ternux PRoot Zink/Turnip configuration is a separate route. Android NNAPI is deprecated from Android 15, and no NPU bridge from Termux has been verified. Native Hangover packages are visible in the current index but are not installed or app-qualified.

## Decision

Treat CPU as the baseline. Report CPU/GPU/NPU capability per process context and named workload. Select hardware backends only when the exact runtime, device, backend, output correctness, and sustained workload have evidence. Native Wine/Hangover remains optional and per-app. Native DXVK is blocked for the recorded native Vulkan result. NPU routing requires an explicit Android-side runtime bridge and a named inference test. A failed backend may fall back only when the user can see the reason and chooses an available fallback.

## Alternatives considered

- **Infer capability from SoC/device nodes/library files/package presence:** rejected; these are not workload execution evidence.
- **Treat PRoot GPU evidence as native GPU evidence:** rejected; separate userspace and process contexts invalidate that inference.
- **Assume generic NPU support from Android NNAPI or a vendor SoC:** rejected; NNAPI is deprecated and process-level access/operator coverage is unverified.

## Rationale

Workstation decisions should be reproducible and not mislead the user about where code ran. Per-workload evidence distinguishes compatibility from acceleration and exposes the true fallback behavior.

## Trade-offs

Capability qualification takes device time and may produce an honest `unknown` or `unavailable` result for some paths. Performance tuning requires sustained runs and thermal/memory observations rather than one short benchmark.

## Consequences

Each compatibility record identifies device/OS, runtime and package versions, app/model architecture, provider, selected backend, correctness result, latency/throughput, memory, and thermal duration. No device-wide “GPU/NPU enabled” switch is presented as proof.

## Evidence

- Ternuxx `docs/RESEARCH.md` §§8, 11, 13 and `docs/WINE-NATIVE.md`.
- [Hangover upstream documentation](https://github.com/AndreRH/hangover).
- [Android NNAPI migration guide](https://developer.android.com/ndk/guides/neuralnetworks/migration-guide).
