# ADR-0004: Management clients share one service layer
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** accepted by owner on 2026-10-18; implementation is incremental
- **Type:** application-architecture

## Context

Ternuxx must serve CLI users and people who prefer graphical workflows. The owner confirmed that CLI, interactive Terminal/TUI, local Web UI, and Graphical UI should perform the same management tasks through shared state and services, so users do not need to know CLI commands for routine setup or configuration. Native Termux and the existing Debian PRoot remain separate providers with distinct homes, permissions, package managers, and ownership. The user experience and Ternuxx-managed configuration should be unified without pretending the underlying environments are one filesystem or security boundary.

## Proposed decision

Create one shared management layer as the authority for configuration, capability state, permission checks, plans/confirmations, operation/task lifecycle, providers, diagnostics and recovery.

- CLI uses the application services directly and remains usable with all graphical services stopped.
- Web Visualizer is a thin client of a versioned local management API. Start the API on demand, loopback-only, when needed; do not require a permanent daemon for CLI use.
- Interactive Terminal/TUI is a terminal-native client of the same application services.
- Graphical UI is a thin client of the same application services/API; it may use the on-demand local API. It does not own system state and must report when X11 is unavailable.
- Automation uses named application-service operations, never a separate unrestricted shell path.
- All interfaces use the same schemas, capability registry, authorization rules, operation IDs and evidence records.

Implementation is incremental. CLI, TUI, the authenticated loopback Web client, and Native GTK now exist, with scoped writes and different per-client coverage. This decision defines the common service boundary; current implementation and remaining controls belong to [the capability matrix](../CAPABILITY-MATRIX.md), [management API](../MANAGEMENT-API.md), and [current handoff](../../../CURRENT_STATE.md). Historical decision-time implementation notes are not current availability claims.

## Alternatives considered

- **Separate CLI/Web/GUI logic:** rejected; behavior and permission checks would drift.
- **Always-on background management daemon:** defer; Android background limits and continuous memory cost are not justified before an on-demand API is measured.
- **Web-only product:** insufficient for the explicit X11 Desktop GUI product target; reusing the Web UI in a supported X11 browser remains a candidate, subject to dependency/resource evidence and owner decision.
- **GUI directly edits config and launches shell commands:** rejected; this bypasses shared validation and authorization.

## Consequences

- CLI operations use the shared service contract; operation coverage is still incomplete and must expand without bypassing typed validation.
- API and GUI work depends on stable schemas and security review.
- UI changes cannot bypass operation preview, confirmation, provider ownership, or recovery state.
- A backend outage must not disable the CLI; graphical clients show unavailable state and recovery guidance.
- A cross-interface contract test must prove the same request produces the same validated plan/result through CLI and API adapters.

## Acceptance criteria for implementation

- Define service/resource schemas, error codes, operation states and versioning.
- Define which commands remain direct read-only CLI paths and which mutations require plan/confirm.
- Threat-review localhost browser access, session bootstrap, CSRF, origin/host validation and cancellation behavior.
- Measure candidate API/UI dependencies against the approved download, installed-size, RAM and startup budgets.
- The same shared service operation is callable through CLI and authenticated local API, with matching plan, result, provider, and evidence semantics.
- The TUI, Web UI, and Graphical UI work through the same operation contract without separate business rules or direct filesystem/shell access.
- Routine setup and configuration can be completed without CLI knowledge, using clear preview, confirmation, progress, and recovery flows.
- Native Termux and PRoot resources are presented together but remain explicitly provider-scoped; actions cannot silently cross provider boundaries.
- Local browser bootstrap and authenticated API mutations are enabled only for individually reviewed scopes whose authentication, CSRF, idempotency, operation contract, and target acceptance have passed. The current loopback Web client supports one-use bootstrap and selected mutations; remaining mutation coverage, full four-client parity, and off-home transport remain separately gated.

## Evidence

- [Master Phase 0 audit](../../evidence/PHASE-0-MASTER-AUDIT.md)
- [Unified workstation proposal](../UNIFIED-WORKSTATION.md)
- [Management API proposal](../MANAGEMENT-API.md)
- [Current authenticated Web mutation scope](../MANAGEMENT-API.md) and [replay-guest Web lifecycle evidence](../../evidence/2026-10-22-web-replay-guest-retirement.md)
- Current source locations: `bin/tx`, `lib/management_service.py`, and the client modules linked by the capability matrix.
