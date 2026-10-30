# Roadmap

Ternuxx uses Native Termux as its host/control plane and optional Ternuxx-managed PRoot workload providers. Debian Trixie and Ubuntu Noble currently have pinned profiles; support for additional upstream proot-distro images requires distro-specific package, graphics/audio, desktop, lifecycle, and recovery adapters plus live qualification. The owner reauthorized PRoot after an earlier retirement on 2026-10-24. P11 records the original Debian restoration; P12 tracks CPU/GPU/NPU acceleration qualification. The broader clean-room mandate continues across these phase boundaries.

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

**Next action:** Resume exact-candidate CPU/Vulkan/HTP inference only after two independent thermal preflight samples pass. Qualify the normal selected-runtime installation and rollback path. Resolve binary/source license conclusions, Snapdragon toolchain redistribution terms, and the Ternuxx project license before any public release.

Complete this item and update its evidence before moving to the next item or phase.
<!-- generated:active-work:end -->

## Current work

Follow the active P12 next action above while continuing the owner-authorized clean-room mandate: extend managed distro providers beyond the current Debian/Ubuntu pair, and close cross-client, graphics/audio, recovery, and clean-install acceptance. Current provider maturity and per-client implementation are in the [capability matrix](architecture/CAPABILITY-MATRIX.md); current runtime and release gates live in [CURRENT_STATE.md](../CURRENT_STATE.md) and [known limitations](testing/KNOWN-LIMITATIONS.md).

## Completion criteria

- Debian PRoot install preserves existing guests and requires preview-bound confirmation.
- Native Termux remains the host and product control plane.
- Every client exposes only implemented operations with the same authorization and preview/confirmation rules.
- CPU/GPU/NPU claims match exact backend and workload evidence.
- The full test harness, document/link audit, and Native live checks pass, with limitations recorded.

Public release additionally requires a selected license, provenance review, and owner acceptance of the release artifact.


## Owner-approved distribution and ecosystem follow-up

The current scope ships checkout bootstrap and consolidated operating guidance.
General product release artifact packaging remains planned: reproducible versioned archives,
checksums, provenance/SBOM, license resolution, compatibility matrix and CI/owner
acceptance before public publication. No release artifact is published by bootstrap.
The separate Ternux repository remains independent and unchanged.

Extend server templates and lifecycle through the existing shared management
service, with management tools available by default and each service activation an
explicit action. Broader server provisioning is planned, not implied by installation
of SSH/runit tools. Continue AI runtime/provider qualification against exact CPU,
Vulkan and experimental HTP workload evidence; installed drivers alone do not qualify
acceleration. Track clean-device installer acceptance and cross-client handoff before
claiming reproducible device installation.


On 2026-10-27 the owner explicitly expanded scope to publish a verified experimental
Native GPU bundle. That narrow third-party Mesa mirror has matching source, notices,
recipe/provenance and checksums; it does not select a license for Ternuxx code or
close the P12 transitive source/build-attribution gate. General application release
packaging and clean-device acceptance remain separately tracked.
