# Known limitations

**Reviewed:** 2026-10-30. This document lists support and release limits; the live session state is recorded in [CURRENT_STATE.md](../../CURRENT_STATE.md), and phase gates in [PHASE-STATUS.md](../PHASE-STATUS.md).

## Device and workload coverage

- Direct device qualification covers one Redmi Turbo 4 Pro / SM8735 profile with Android 16 and Termux `0.119.0-beta.3`. It does not establish compatibility with other devices, Android releases, or Termux builds.
- Two pinned Qwen2.5 1.5B Q4_K_M CPU attempts were cancelled before accepting output: the initial call at CPU 61.2°C and a fresh repeat at CPU 67.6°C after 4.585 seconds. It is not a baseline. Broader model correctness, clean installation, network isolation, and sustained memory/thermal behavior remain unqualified. See the [CPU baseline](CPU-BASELINE.md) and [P12 result](../evidence/2026-10-30-p12-native-qualification.md).
- The pinned Qwen2.5 model passed one Vulkan0 run with 29/29 layers, then a repeat was cancelled at CPU 60.4°C. The experimental Mesa/Freedreno ICD does not have an audited, repeatable clean-install path; sustained performance and general GPU support remain unqualified. OpenCL has no usable platform in the observed Native session. See [GPU qualification](GPU-ACCELERATION.md) and [P12 result](../evidence/2026-10-30-p12-native-qualification.md).
- The pinned Qwen2.5 model passed one HTP0 b11849 call with 29/29 layers, then two repeat attempts were cancelled, first at HTP 61.0°C and later at CPU 60.8°C. This exact model has no repeated/sustained qualification or same-model CPU speed comparison. Broader model/operator correctness, memory pressure, and clean-device installation remain open. See [NPU qualification](NPU-ACCELERATION.md) and [P12 result](../evidence/2026-10-30-p12-native-qualification.md).

## Qualification launch headroom

The native accelerator qualification runner now requires empirical start margins below its in-run stop guards: CPU launch at or below 40°C, Vulkan CPU/GPU at or below 45°C/50°C, and HTP CPU/HTP at or below 50°C/40°C. These values are derived from observed short-run sensor increases and are test policy, not OEM limits. A 2026-10-29 preflight at CPU 52.8°C was refused before inference. Do not bypass this gate with `--ignore-thermal-limits`.

## Lifecycle and recovery

- Debian PRoot support and the installed Trixie guest are present. Automated fixture coverage and the one-device live checks do not equal clean-device installation qualification. Fresh setup runs in an attached Native Termux terminal; it supports hidden-password and guest-only passwordless sudo modes.
- Native desktop cold-boot delivery and automatic recovery are not release-qualified; recorded reboot checkpoints remain `NOT_READY` and automatic resume stays disabled.
- Native SSH and the optional Debian terminal broker have separate ownership and security boundaries. The owner-managed development SSH endpoint must be reviewed independently; listener reachability and ownership are not inferred from its configuration file. The current security finding is in [SECURITY.md](../../SECURITY.md).
- A 2026-10-24 read-only audit saw five defunct `proot` children under the persistent TUI process while all Ternuxx session records were stopped. The bounded-probe launcher now double-forks so future processes are not children of long-lived clients; fixture coverage verifies reparenting and exact-plan stop. The five pre-existing zombies remain unverified under the still-running TUI and were left untouched. See [live state reconciliation evidence](../evidence/2026-10-24-live-state-reconciliation.md).

## Release readiness

- No project license has been selected. Do not redistribute source-derived binaries or artifacts until ownership, dependency licenses, and provenance have been reviewed.
- Public release still needs an approved license, build-specific SBOM, artifact signing and provenance, clean-device installation evidence, broader device support decisions, and the remaining workload and lifecycle gates.
- The automated full suite validates repository behavior and fixtures. It cannot prove GUI visibility, human usability, external network reachability, physical audio, sustained accelerator performance, or cold-boot delivery.

Use [CURRENT_STATE.md](../../CURRENT_STATE.md) for current runtime observations and the [current repository audit checkpoint](../audit/REPOSITORY-AUDIT.md) for its source and documentation review. The earlier pre-Native-only audit is preserved in [history](../history/REPOSITORY-AUDIT-pre-native-only-2026-10-24.md). Dated evidence remains a snapshot; recheck live behavior before operational decisions.
