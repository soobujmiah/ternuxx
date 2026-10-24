# ADR-0010: Native Termux autonomy and bounded PRoot integration
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Status:** Accepted owner requirement; legacy-alias preservation clauses superseded by [ADR-0016](ADR-0016-tx-db-and-legacy-entrypoints.md); current implementation/qualification tracked by the capability matrix and phase evidence
- **Date:** 2026-10-17
- **Decision owner:** Project owner

## Context

Ternuxx combines Native Termux with an existing, independently managed Debian PRoot environment. The native host must remain the primary workstation and must recover its own services without relying on the guest or an agent process running inside it. Existing Ternux workflows are part of the owner's established setup and are protected integration boundaries.

## Decision

1. Native Termux is the authoritative owner of native-side SSH, native services, boot orchestration, native lifecycle management, and persistent boot/continuity evidence. These functions must work when Debian PRoot is stopped, unavailable, or damaged.
2. Termux:Boot invokes the native startup orchestrator directly. It must not enter PRoot, wait for a PRoot agent, or make native service recovery conditional on a guest operation.
3. Persistent continuity/checkpoint records are stored in Ternuxx-owned Native Termux private storage. They contain only the minimum non-sensitive operation state needed to resume or verify work; they must not depend on an agent process surviving reboot.
4. The existing `db` command continues to enter the existing Debian PRoot without launching a GUI. The existing `xgo` graphical workflow remains unchanged. Ternuxx must use namespaced commands/adapters and must not shadow, overwrite, or repurpose these workflows without separate explicit authorization.
5. Cross-environment operations are explicit, bounded requests. They identify source and target providers, use an allowlisted operation/argument contract, enforce authorization at execution time, apply timeouts, return structured results, and record a non-sensitive operation ID. An SSH connection alone is not blanket authorization for arbitrary host commands.
6. Native services own only the processes and resources they started and recorded. Stopping PRoot must not terminate or release native-owned services/resources. Restarting native services must not reset, rewrite, or otherwise destroy PRoot state.
7. Wake locks are acquired only for a declared active workload that needs them, attributed to that workload/service owner, and released only by that owner after the workload ends or a verified cleanup path runs. One component must not release a lock owned by another active component.
8. After reboot, native services recover independently and write continuity evidence. PRoot-dependent work remains pending until a fresh PRoot session exists; an agent resumes only after that session is started and the owner requests verification or continuation.
9. PRoot remains an integrated but independently managed development/execution provider. Its absence is a scoped failure for PRoot-dependent operations, not a failure of native boot, SSH, continuity, or native workloads.

## Required architecture and evidence

The shared service/task model must persist provider, operation ID, bounded arguments, status, timestamps, cancellation/recovery state, and sanitized result metadata in native private storage. Secrets, SSH private keys, credentials, and unnecessary personal paths must not enter continuity records.

Do not claim independence or bidirectional integration until the applicable tests pass. Required acceptance evidence:

| ID | Acceptance test | Passing evidence |
|---|---|---|
| NTA-01 | Native SSH and continuity recording while PRoot is not running | Native-only test record shows both successful; no guest process/dependency in the call path. |
| NTA-02 | `db` compatibility | Superseded by ADR-0016: `tx db` is Ternuxx's first-party command; legacy `db` behavior is not a compatibility gate. |
| NTA-03 | `xgo` compatibility | Superseded by ADR-0016: legacy `xgo` behavior is not a Ternuxx acceptance gate. The separate Ternux source repository/launcher remains outside Ternuxx's change scope. |
| NTA-04 | Authorized PRoot-to-native diagnostic | A scoped diagnostic succeeds through configured SSH; audit record identifies operation and providers without secrets. |
| NTA-05 | Unauthorized cross-provider request | The same operation without the required authorization is denied at the native execution boundary. |
| NTA-06 | Stop PRoot | Independent native services remain alive and healthy; only PRoot-owned processes/resources are stopped. |
| NTA-07 | Restart native services | Native restart does not modify the PRoot rootfs, launcher, session, or state. |
| NTA-08 | Reboot preparation and verification | Native boot/checkpoint evidence is sufficient for later verification without assuming the agent survived; continuation waits for a fresh PRoot session and owner request. |
| NTA-09 | Wake-lock ownership | Acquire/release evidence is scoped to the owning workload; an unrelated service stop does not release it. |

Each test must state whether it is a mock, host integration, or owner-operated physical-device test. A reboot test must not be simulated by claiming the current agent survives reboot. No acceptance test is recorded as passed by this ADR.

## Consequences

- Native boot, SSH, health reporting, and continuity have a smaller failure domain than PRoot workloads.
- Cross-provider control requires a narrow adapter and explicit authorization instead of generic shell forwarding.
- Task recovery is checkpoint-based and owner-mediated for PRoot-dependent continuation.
- Service/process and wake-lock ownership must be recorded before implementing broad start/stop controls.
- The earlier `xgo`/`db` compatibility requirement is superseded by ADR-0016. That clarification does not authorize changes to the separate Ternux source repository/launcher, broad cleanup, or unpreviewed changes to the existing rootfs.

## Implementation status

This ADR defines requirements and does not itself qualify a runtime or acceptance test. Native services, boot/continuity, SSH and Wake Lock modules now exist. Current coverage and limits are in [the capability matrix](../CAPABILITY-MATRIX.md), [P3 exit evidence](../../evidence/2026-10-22-p3-rb08-postboot-exit-audit.md), and [the active audit](../../audit/REPOSITORY-AUDIT.md).

The owner's 2026-10-22 phase clarification removed legacy launcher compatibility as a P4 acceptance gate; it did not authorize destroying those files or stopping the working guest. Native no-PRoot runtime evidence and the current installed modules' next cold-boot observation remain distinct outstanding checks; do not stop the active Codex guest to manufacture them.
