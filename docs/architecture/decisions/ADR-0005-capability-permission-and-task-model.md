# ADR-0005: Capabilities, permissions and operations are explicit resources
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** proposed — owner review required
- **Type:** security-architecture

## Context

The product may integrate native Termux, Android APIs, Termux:Boot, Shizuku, Accessibility, the independent Debian PRoot, AI providers, local models, and future extensions. An installed companion APK, detected device node, or successful setup screen does not prove that a specific operation is authorized or works. Long package/model/runtime/benchmark tasks need consistent progress, cancellation and recovery semantics across management clients (CLI, TUI, Web, and GTK).

## Proposed decision

Represent capability, authorization and operation state as separate, versioned records. Check the permission at the operation boundary, not only in the UI.

Suggested capability states:

- `supported_available`
- `available_not_authorized`
- `authorized_operational`
- `temporarily_unavailable`
- `unsupported`
- `experimental`
- `revoked_or_disconnected`
- `failed_verification`

Each record carries a stable capability ID, provider/environment, required scope, last-check time, evidence source, limitations, and revocation/recovery guidance. Accelerator stages remain distinct: detected, initialized, workload-verified, release-qualified.

Suggested operation states: `planned`, `awaiting_confirmation`, `queued`, `running`, `cancelling`, `succeeded`, `failed`, `cancelled`, `needs_recovery`. Mutations use exact preview → deliberate confirmation → journaled operation → verified outcome. Cancellation is cooperative and must report partial effects truthfully.

Integration-specific boundaries:

- Termux:Boot is a boot trigger, not privilege elevation; every service checks dependencies and current authorization at runtime.
- Termux:API exposes only supported commands and permissions; the API app/CLI installation alone is not permission evidence.
- Shizuku is an optional provider for named supported operations, not root. Recheck running/authorized state per operation and fail clearly on revocation.
- Accessibility remains out of scope until a legitimate, specific user workflow requires it. It must never grant permissions, bypass security prompts, or provide general privilege escalation.
- Extensions declare version, dependencies, environment, data scopes and required capabilities; the shared authorization layer enforces them.

## Alternatives considered

- **Boolean `permission=true`:** rejected; cannot distinguish installed, authorized, operational, revoked or verified.
- **UI-only permission checks:** rejected; CLI/API/automation could bypass them.
- **Treat Shizuku/Accessibility as general elevated authority:** rejected; operation scopes are independent and user authorization cannot be inferred.
- **Start all services and models at boot:** rejected; startup is user-selected and resource-aware.

## Consequences

- Revocation and temporary failure become visible system states, not silent fallback.
- Each adapter needs capability discovery, operation-scoped authorization, structured errors and tests.
- Logs record non-sensitive authorization transitions but never secrets or pairing codes.
- Boot and extension systems depend on this model and must not be implemented first.

## Acceptance criteria before approval

- Define capability and operation schemas, owner/environment identity, migration and retention.
- Map each existing mutating CLI command to a capability and confirmation requirement.
- Define Shizuku operation allowlist only after a concrete need is identified; do not enable it by default.
- Add tests for missing, revoked, stale, unauthorized and failed capability states before physical-device workflows.
- Specify audit redaction and user-facing Android revocation instructions.

## Evidence

- [Master Phase 0 audit](../../evidence/PHASE-0-MASTER-AUDIT.md)
- [Unified workstation proposal](../UNIFIED-WORKSTATION.md)
- [Threat model](../../readiness/THREAT-MODEL.md)
- Device audit found Termux:Boot, Termux:API, Termux:X11 and Shizuku packages installed, but did not verify running/authorized state.
