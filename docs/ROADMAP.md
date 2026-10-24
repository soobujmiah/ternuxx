# Roadmap

Ternuxx uses Native Termux as its host/control plane and supports optional Debian PRoot workloads. On 2026-10-24 the owner authorized restoring Debian PRoot after its earlier retirement. P11 tracks the provider and guest restoration; P12 tracks CPU/GPU/NPU acceleration qualification.

<!-- generated:phase-table:start -->
| ID | Phase | Status | Completed / skipped |
|---|---|---|---|
| P0 | Repository foundation and evidence baseline | completed | 2026-10-17 |
| P1 | Requirements and CPU/GPU/NPU compatibility research | completed | 2026-10-17 |
| P2 | Safe native desktop lifecycle | completed | 2026-10-18 |
| P3 | Doctor, management, and recovery | completed | 2026-10-21 |
| P4 | Owner-directed retirement of former PRoot provider | completed | 2026-10-23 |
| P5 | Native Termux profile compatibility | completed | 2026-10-23 |
| P6 | CPU/GPU/NPU capability, optimization, and fallback | completed | 2026-10-24 |
| P7 | Native apps and curated software catalog | completed | 2026-10-24 |
| P8 | Native workload and accelerator routing | completed | 2026-10-24 |
| P9 | Optional isolated workload profile | skipped | skipped 2026-10-24 |
| P10 | Hardening, release, and support | completed | 2026-10-24 |
| P11 | Restore Debian PRoot support on Native Termux | completed | 2026-10-24 |
| P12 | Qualify Native CPU, GPU and NPU acceleration | in_progress | — |
<!-- generated:phase-table:end -->

## Active work

<!-- generated:active-work:start -->
**Active phase:** P12 — Qualify Native CPU, GPU and NPU acceleration

**Next action:** Finish Mesa run 40125903141 and verify package manifests and source/license attribution. Resume repeated backend qualification only while the unchanged live guards pass; broaden HTP coverage and validate a reproducible experimental Vulkan install path.

Complete this item and update its evidence before moving to the next item or phase.
<!-- generated:active-work:end -->

## Current work

Follow the active P12 next action above. Per-client implementation and remaining acceptance live in the [capability matrix](architecture/CAPABILITY-MATRIX.md); current runtime and release gates live in [CURRENT_STATE.md](../CURRENT_STATE.md) and [known limitations](testing/KNOWN-LIMITATIONS.md).

## Completion criteria

- Debian PRoot install preserves existing guests and requires preview-bound confirmation.
- Native Termux remains the host and product control plane.
- Every client exposes only implemented operations with the same authorization and preview/confirmation rules.
- CPU/GPU/NPU claims match exact backend and workload evidence.
- The full test harness, document/link audit, and Native live checks pass, with limitations recorded.

Public release additionally requires a selected license, provenance review, and owner acceptance of the release artifact.
