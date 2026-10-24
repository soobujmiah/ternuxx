# ADR-0007: Launch Manager owns named profiles, not existing Ternux sessions
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** proposed — owner review required; alias compatibility clauses superseded by [ADR-0016](ADR-0016-tx-db-and-legacy-entrypoints.md)
- **Current host behavior:** see [2026-10-22 live inventory](../../evidence/2026-10-22-legacy-entrypoint-inventory.md); historical broad-cleanup claims do not describe the current `~/x.sh` wrapper
- **Type:** lifecycle-and-display-architecture

## Context

Ternuxx needs one launch registry shared by CLI, Web Visualizer, X11 GUI and optional Termux:Boot entry points. The proposed aliases overlap with commands that the independent Ternux project already installs. Static source review also found that the existing Ternux launcher assumes display `:0` and performs broad process/socket cleanup. On the owner's current target, the existing Ternux PRoot is assigned `:0` and native Ternuxx is assigned `:1`; Ternuxx default allocation now searches `:1` through `:10` and preserves occupied sockets/locks. The new tx pgui qualification now verifies the exclusive standalone :0 route while Native :1 is stopped, and a Debian Xephyr :2 session nested inside the running Native :1 server. This does not test two independent Termux:X11 servers concurrently, Android activity/window routing, or independent physical displays; those remain unqualified.

## Proposed decision

Define a Launch Manager as a shared application service. A launch target is data in a validated registry, not an arbitrary command string. It declares an ID, user-facing aliases, provider (`native_termux`, `existing_ternux_proot`, or `shared_service`), executable/argument schema, prerequisites, scoped capabilities, display/audio needs, startup policy, health check, ownership record, stop/restart contract, and bounded recovery instructions.

Every run produces a tracked operation/session with provider, requested profile, allocated display/session identity, exact owned process identities, health state, logs, and teardown policy. Start is idempotent only when the recorded session is verifiably healthy. Ambiguous or stale state fails closed; never infer ownership by a broad process-name match. Stop can signal only processes and resources verifiably owned by that record.

The Launch Manager also provides shell-aware integration for the active interactive shell. It must identify the user's real shell before generating completions or convenience functions; `$SHELL` alone may be stale or refer to a login shell different from the current interactive shell. Start with explicit adapters for shells that have been audited and tested (initial candidates: Bash and Zsh; Fish only after confirming the Termux package/runtime and adapter). Keep a portable `ternuxx launch ...` CLI path for every shell. Do not install short aliases that collide with Ternux (`x`, `xgo`, `killx`, `db`, `droot`) or shadow `ternux`.

Shell setup must be previewable, idempotent, and reversible. Write Ternuxx-owned completion/config snippets to a dedicated Ternuxx path; do not replace or reformat user RC files. If the selected shell requires a source hook in an RC file, show the exact additive line and resulting diff, preserve a backup, and require confirmation before adding it. Unknown or ambiguous shells receive a clear manual setup result, not a guessed edit. Uninstall removes only the exact Ternuxx-owned snippet/hook after preview and confirmation.

Profiles are declarative allowlists of launch targets. `full_workstation` starts only selected and authorized components; it does not imply every model, agent, service, or GUI. `services_only` contains no graphical target. Boot is a separate opt-in profile invoking the same manager, with runtime capability/dependency checks and no implicit privilege escalation.

The aliases `x`, `xgo`, `xn`, `xa`, and `xstop` were proposal-time ideas; the compatibility requirement to preserve or migrate legacy aliases was superseded by [ADR-0016](ADR-0016-tx-db-and-legacy-entrypoints.md). No legacy short alias is required for Ternuxx. Prefer namespaced commands (`ternuxx launch ...`) as the stable interface. This ADR does not authorize edits to the separate Ternux source repository or its launcher; those boundaries remain governed by the current owner decision and project instructions.

Display ownership must be allocated across providers under one lock/registry before launch. A display number such as `:0` or `:1` identifies an X server display endpoint; it does not by itself select a distinct Android physical/virtual display. Termux:X11 documentation demonstrates invocation with `:1`, but that does not verify two concurrent servers, two independent Android activities, window placement, or dual-session stability on this device. Until device testing proves otherwise, permit one managed Termux:X11 server and offer separate native/PRoot sessions sequentially or as windows in that session. Do not hard-code the proposed two-display mapping.

Ternux's `~/x.sh`, aliases, `ternux start/stop`, audio behavior, display behavior, and boot hooks remain owned by Ternux. Ternuxx may integrate only through an explicit safe provider interface approved for this purpose. It must not call generic Ternux stop/cleanup or manipulate its socket/process state. A parallel Ternuxx native session may not share display/audio resources until conflict behavior is verified.

## Proposed launch registry record

The draft machine-readable contract is [the launch registry JSON Schema](../../../schemas/launch-registry.schema.json). Targets and profiles are keyed maps so identifiers are unique by construction. Launch aliases must be in the `ternuxx.*` namespace; legacy short names are intentionally not represented as installable aliases. The schema describes metadata only: a target marked `available` still requires a real registered handler, capability checks, operation ownership, and accepted tests before release.

```yaml
id: native.management_gui
name_key: launch.native_management_gui.name
description_key: launch.native_management_gui.description
provider: native_termux
status: planned
entrypoint_id: null
aliases: []
dependencies: []
capabilities: []
display:
  mode: managed_server
  readiness_check_id: desktop.x11_ready
audio:
  mode: none
startup_policy: manual
health_check:
  check_id: desktop.xfce_ready
  timeout_seconds: 30
stop_policy:
  mode: owned_process_group
  owner_record_required: true
recovery:
  guide_key: recovery.inspect_session_report
  rollback_scope: ternuxx_owned_state
```

The sample is a schema sketch, not an implemented launch record. A Native GTK management center exists; its presence does not establish a generic launch registry or prove that this proposed target is registered or launchable.

## Alternatives considered

- **Keep aliases as independent shell scripts:** rejected as the long-term design; lifecycle, status and permission behavior would diverge across CLI and graphical clients.
- **Replace `x`/`xgo`/`killx` immediately:** rejected; they are established Ternux controls and have destructive cleanup semantics. Migration needs compatibility tests and explicit owner approval.
- **Hard-code a universal `:0` PRoot / `:1` Native GUI mapping without target testing:** rejected as a universal rule; the owner has assigned those displays on the current target, but simultaneous server/activity/window support and resource isolation remain unqualified.
- **Let Ternuxx stop every process matching X11/audio names:** rejected; ownership cannot be established this way and it can disrupt Ternux or unrelated sessions.
- **Start all launch targets at Android boot:** rejected; Android background restrictions, workload/resource costs and permissions require an opt-in bounded profile.

## Consequences

- Launch Manager depends on the shared application, capability, task and operation models proposed in [ADR-0004](ADR-0004-three-interfaces-shared-management.md) and [ADR-0005](ADR-0005-capability-permission-and-task-model.md).
- Native session ownership and the existing Ternux provider are separate. A shared display allocator is only a coordination service; it does not transfer lifecycle ownership.
- The Launch Manager must report Android activity visibility separately from X server/session readiness.
- Boot, service and profile configuration must be consumed by the same launch registry used by CLI and graphical clients.
- Process-group behavior, child cleanup, port/socket ownership, audio reuse and display release need fixture tests before device trials.

## Acceptance criteria before implementation

1. Read-only audit resolves actual native Termux aliases, `~/x.sh`, installed Ternux lifecycle source, standard Termux:Boot path, companion package version, and a point-in-time owned-process/socket snapshot without starting or stopping anything. **Completed for this device on 2026-10-17**, except the Android Termux:X11 APK version and any nonstandard boot location remain unknown; no boot scripts were present in the standard directory.
2. Existing `x`, `xgo`, `killx`, `db`, `droot`, and `ternux start/stop` behavior is recorded, including exact cleanup scope and command collisions.
3. Registry/profile schema validates provider, argv, capabilities, display/audio resources, start policy, health, stop ownership, and recovery fields; no shell command strings are accepted.
4. Contract tests cover duplicate launch, concurrent start lock, stale PID reuse, startup failure, cancellation, stop/restart, boot idempotence, and unrelated-session preservation.
5. Owner-operated device testing verifies missing dependency/permission/display errors, existing Ternux workload preservation, and GUI activity visibility separately from X-server readiness.
6. Dual display/session behavior is tested on the target Termux:X11 APK/package pair, including `:0`/`:1`, Android activity selection, input/window placement, audio reuse, GPU/render behavior and resource contention. Otherwise the product explicitly supports a single-server model.
7. Any alias migration has a reversible mapping and explicit approval; installation never overwrites the existing Ternux aliases or launcher.
8. Shell detection is verified for interactive Bash, Zsh, Fish where supported, nested shells, stale `$SHELL`, and unknown shell; setup preview is exact, repeat setup makes no duplicate hook, and removal preserves unrelated RC content.

## Evidence and unresolved facts

- [Phase 0 master audit](../../evidence/PHASE-0-MASTER-AUDIT.md)
- [Unified workstation proposal](../UNIFIED-WORKSTATION.md)
- [Ternux launcher and aliases at audited public-main commit](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/lib/phases.sh#L598-L650)
- [Ternux start/stop implementation at audited public-main commit](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/lib/desktop.sh#L12-L95)
- The project records display identifiers including `:1` and treats X server process state separately from Android Activity visibility. This does not establish concurrent multi-server behavior on the target device.
- The Phase 0 report records static and live Termux evidence from the authorized read-only session: `~/x.sh`, `.bashrc`, installed Ternux lifecycle module, `termux-x11-nightly` package version, absent standard boot directory, and no active X11 process/socket at the sampled time. The installed Android APK version and concurrent display/Activity behavior remain unresolved.
