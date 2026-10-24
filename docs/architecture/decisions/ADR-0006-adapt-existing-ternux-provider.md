# ADR-0006: Integrate the independent Ternux environment through a narrow provider
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** superseded by owner direction on 2026-10-20
- **Type:** provider-integration

## Context

Ternuxx must preserve the existing independently managed Debian PRoot and avoid duplicating runtimes where the existing environment already has evidence. Ternux's live public `main` at `9fda63162426f77ee575b5f6729d8799a30f51b7` documents CPU/Vulkan llama.cpp workloads and experimental Hexagon HTP and QNN routes. Ternuxx itself has no PRoot adapter or AI runtime. Ternux's generic lifecycle paths include broad X11/PulseAudio termination and wildcard socket cleanup, so calling them as an implicit service API could disrupt unrelated sessions.

## Proposed decision

Treat Ternux as a separate execution provider. Prefer an explicit, versioned, supported Ternux CLI/API or extension interface. Begin with read-only provider discovery/status. Add workload dispatch only after the provider contract identifies exact operation ownership, argv/input scope, result reporting, lifecycle behavior and failure boundaries.

- Do not copy Ternux source into Ternuxx.
- Do not modify, rebuild, prune, upgrade, reinstall or migrate its rootfs, launcher, graphics setup or workloads.
- Do not invoke generic cleanup/start/reset flows from Ternuxx.
- Do not assume its display/audio lifecycle belongs to Ternuxx.
- Keep Ternux graphics evidence separate from AI inference evidence, and keep HTP/QNN experimental statuses visible.
- Review Ternux license metadata, artifact notices, transitive/runtime terms and model licenses before distributing or bundling anything.

## Alternatives considered

- **Build/ship a duplicate llama.cpp/GPU/NPU runtime first:** defer; existing PRoot routes are a better integration candidate, subject to API/license/safety review.
- **Call `~/x.sh` or generic Ternux cleanup:** rejected; the inspected Ternux main lifecycle includes broad process/socket cleanup.
- **Mount all Termux home/config/credentials into PRoot:** rejected; use narrowly selected workspaces and explicit environment allowlists.
- **Treat Ternux-reported CPU/Vulkan/HTP/QNN results as Ternuxx release evidence:** rejected; evidence remains attributed to the external repository and its exact version/workload.

## Consequences

- Ternux owns its PRoot state and lifecycle; Ternuxx owns only its adapter process and request records.
- Provider status and workloads must expose provider/version and actual backend.
- The adapter needs noninterference tests covering unrelated X11/audio sessions and no rootfs mutations.
- If no stable supported interface exists, keep the provider manually operated and report it as external rather than duplicating or shelling into unsafe paths.

## Acceptance criteria before approval

- Identify a stable documented Ternux interface and the exact safe subset of commands.
- Verify license and third-party distribution implications with current authoritative files.
- Define argv-safe requests, selected input/output paths, environment allowlist, timeout/cancellation and error schema.
- Prove read-only status does not launch cleanup, mutate package state, access shared storage or signal unrelated processes.
- Owner-operated testing must confirm existing Ternux GUI/audio/workloads remain intact.

## Evidence

- [Master Phase 0 audit](../../evidence/PHASE-0-MASTER-AUDIT.md)
- [Ternux accelerator release plan](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/docs/ACCELERATOR-RELEASE-PLAN.md)
- [Ternux benchmarks](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/docs/BENCHMARKS.md)
- [Ternux HTP qualification](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/guides/llama-htp-experimental.md)
- GitHub currently reports Apache-2.0 metadata for Ternux `main`; this is not a complete third-party/artifact license review.
- [Live installed Ternux CLI interface recheck (2026-10-18)](../../evidence/2026-10-18-p4-installed-ternux-interface-recheck-0600.json) — v1.4.0 help exposes no generic workload dispatch; backend status reports Zink/Vulkan available but renderer unknown.

## Superseding owner direction — 2026-10-20

Ternuxx is the independent final workstation product. The separate Ternux repository and its CLI are reference-only; they are not a required provider or install/runtime dependency. Ternuxx owns its Native host controls and its own explicit Debian PRoot handoff. Preserve the existing PRoot rootfs and compatible guest libraries/settings, adapting only Ternuxx-owned launch/config paths or a guest file after exact impact assessment and a verified rollback. Never copy Native Bionic libraries into Debian glibc paths. Existing Ternux accelerator claims remain attributed to Ternux and are not Ternuxx workload evidence. Current Ternuxx PRoot verification must not execute or query the Ternux CLI. This owner direction supersedes the proposed Ternux CLI/API adapter above; historical Ternux evidence may still inform research with attribution and licensing review.
