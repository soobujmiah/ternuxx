# ADR-0011: Unified Native SSH connection and lifecycle management
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Status:** Accepted owner requirement; implementation partial (current status reviewed 2026-10-24)
- **Date:** 2026-10-17
- **Type:** native-service-management

## Context

Native Termux owns native SSH connectivity and must recover it without Debian PRoot or a guest agent. The owner also requires guided first-time setup, compatible migration from the existing manual SSH setup, secure identity/authentication handling, boot recovery, Wake Lock ownership, continuity evidence, and consistent CLI/Web/X11 management. At decision time (2026-10-17), the repository had SSH proposals but no shared SSH service implementation or management UI. The active manual server's configuration and ownership were unknown pending a redacted read-only inspection; this is historical context, not current implementation status.

## Decision

Use one `native_ssh` application service as the authority for discovery, config plans, authentication policy, service lifecycle, Termux:Boot, Wake Lock leases, connectivity tests, and recovery. CLI calls the service directly; Web and X11 GUI call the same versioned API. Keep desired config, secret/key references, and observed runtime/continuity state separate. Preserve the current Termux principal, manual keys, auth policy, listener, and session until a replacement is staged, validated, explicitly approved, and has a verified rollback path. Do not create a Linux OS user implicitly.

PRoot is an independent optional provider. Native SSH, boot, and continuity work without it. PRoot may use named bounded native diagnostics over configured SSH after separate authorization; connectivity is not blanket permission. The interface, state machine, schema, setup/migration, security, and test contracts are in [SSH-LIFECYCLE.md](../SSH-LIFECYCLE.md).

## Consequences

- SSH management cannot be independently reimplemented in CLI, Web, or X11 clients.
- A setup wizard validates before persisting active desired configuration and never overwrites unknown/manual config or keys.
- Web management authentication is distinct from SSH client authentication and the Android Termux login principal.
- Termux:Boot is native-only and optional; Wake Locks default off and use per-owner leases.
- Public docs and reports contain no secrets, key bytes, raw config, or private paths.
- Full acceptance remains partial: password-recovery scope, post-repair authenticated access, Android cold-boot delivery, and remaining GTK interaction review are still open; see the current status below.

## Alternatives rejected

- **Direct `sshd_config` writes from each UI:** bypasses shared validation, authorization, migration, and rollback.
- **Stop the current `sshd` then test a replacement:** can interrupt the working session before the replacement is known to work.
- **Use PRoot/systemd/agent for native recovery:** violates native ownership and reboot independence.
- **Treat SSH authentication as management authorization:** grants more authority than the connection requires.
- **Create arbitrary Termux OS users:** Android/Termux process identity is not a general Debian user-management facility.

## Evidence status

This ADR records the architecture and owner requirements; it is not runtime acceptance evidence. As of 2026-10-24, the shared Native service and CLI/TUI/authenticated Web/GTK clients provide SSH inspection and scoped lifecycle/deployment, key inventory/enrollment/removal with exact rollback, recovery-key creation, autostart preference, and next-start Wake Lock preference. Disposable authentication qualification passed before the 2026-10-23 service-wrapper repair; authenticated access after that repair remains unverified. Password-recovery scope, GTK key-dialog/small-viewport interaction, and Android cold-boot delivery remain open. See [the capability matrix](../CAPABILITY-MATRIX.md), [SSH lifecycle contract](../SSH-LIFECYCLE.md), and [the active audit](../../audit/REPOSITORY-AUDIT.md).
