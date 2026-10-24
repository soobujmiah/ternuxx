# Known limitations

**Reviewed:** 2026-10-24. This document lists support and release limits; the live session state is recorded in [CURRENT_STATE.md](../../CURRENT_STATE.md), and phase gates in [PHASE-STATUS.md](../PHASE-STATUS.md).

## Device and workload coverage

- Direct device qualification covers one Redmi Turbo 4 Pro / SM8735 profile with Android 16 and Termux `0.119.0-beta.3`. It does not establish compatibility with other devices, Android releases, or Termux builds.
- CPU inference is implemented and bounded, but broader model correctness, clean installation, network isolation, and sustained memory/thermal behavior remain unqualified. See [CPU baseline](CPU-BASELINE.md).
- Vulkan inference passes short Adreno 825 workloads with full layer-offload proof using an experimental Mesa/Freedreno ICD. The ICD does not yet have an audited, repeatable clean-install path; the result does not qualify sustained performance or general GPU support. OpenCL has no usable platform in the observed Native session. See [GPU qualification](GPU-ACCELERATION.md).
- Experimental HTP0 inference is integrated for SM8735 using a pinned llama.cpp Snapdragon runtime. Tested short prompts are slower than CPU. Broader model/operator correctness, memory pressure, sustained thermal behavior, and clean-device installation remain open. See [NPU qualification](NPU-ACCELERATION.md).

## Lifecycle and recovery

- Debian PRoot support and the installed Trixie guest are present. Automated fixture coverage and the one-device live checks do not equal clean-device installation qualification. Fresh setup runs in an attached Native Termux terminal so guest passwords stay in hidden prompts.
- Native desktop cold-boot delivery and automatic recovery are not release-qualified; recorded reboot checkpoints remain `NOT_READY` and automatic resume stays disabled.
- Native SSH and the optional Debian terminal broker have separate ownership and security boundaries. The owner-managed development SSH endpoint must be reviewed independently; listener reachability and ownership are not inferred from its configuration file. The current security finding is in [SECURITY.md](../../SECURITY.md).
- A 2026-10-24 read-only audit saw five defunct `proot` children under the persistent TUI process while all Ternuxx session records were stopped. The bounded-probe launcher now double-forks so future processes are not children of long-lived clients; fixture coverage verifies reparenting and exact-plan stop. The five pre-existing zombies remain unverified under the still-running TUI and were left untouched. See [live state reconciliation evidence](../evidence/2026-10-24-live-state-reconciliation.md).

## Release readiness

- No project license has been selected. Do not redistribute source-derived binaries or artifacts until ownership, dependency licenses, and provenance have been reviewed.
- Public release still needs an approved license, build-specific SBOM, artifact signing and provenance, clean-device installation evidence, broader device support decisions, and the remaining workload and lifecycle gates.
- The automated full suite validates repository behavior and fixtures. It cannot prove GUI visibility, human usability, external network reachability, physical audio, sustained accelerator performance, or cold-boot delivery.

Use [CURRENT_STATE.md](../../CURRENT_STATE.md) for current runtime observations and the [current repository audit checkpoint](../audit/REPOSITORY-AUDIT.md) for its source and documentation review. The earlier pre-Native-only audit is preserved in [history](../history/REPOSITORY-AUDIT-pre-native-only-2026-10-24.md). Dated evidence remains a snapshot; recheck live behavior before operational decisions.
