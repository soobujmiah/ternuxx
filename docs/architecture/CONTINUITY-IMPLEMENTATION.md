# Native continuity, recovery and Wake Lock implementation

Native Termux owns persistent continuity evidence and service recovery. An Android reboot ends the old agent/process and never implies automatic task resumption. Debian PRoot is an optional workload provider; continuity storage and recovery remain Native-owned and do not silently resume guest work.

The earlier RB02/RB03 implementation narrative is preserved as [dated history](history/2026-10-22-continuity-implementation.md). It is not the current checkpoint, service count, authentication policy or client status. [Phase state](../../project/phase-state.json), [client coverage](CAPABILITY-MATRIX.md) and [the audit](../audit/REPOSITORY-AUDIT.md) own current qualification.

## Components and commands

- `lib/continuity.py`, `lib/reboot_recovery.py` and their shell adapters create/observe/verify private checkpoints. Records distinguish boot identity, matching observation, service readiness and pending work. Test IDs, nonces, boot identifiers and private runtime payloads stay outside Git.
- `tx checkpoint prepare|verify` and the TUI, Web, and GTK recovery guides support private checkpoint creation and verification. Both mutations show a read-only plan and require exact plan confirmation; verification binds that plan to the checkpoint record hash. Interactive CLI requires `CREATE CHECKPOINT` or `VERIFY CHECKPOINT`; JSON mode returns the plan, and automation applies it with `--yes --plan-id`. `tx reboot status|prepare|verify|resume-info` manages reboot qualification and remains CLI-only. These operations never reboot the device, start tasks, configure boot, or resume work; `automatic_resume` remains false.
- `lib/boot_helpers.py` manages exact service/recovery helper reconciliation. `lib/termux_boot_cron.py` separately manages the Cron boot helper. Plans, private snapshots, serialized writes, identity checks and rollback preserve current state.
- `lib/wakelock_manager.py` serializes owner leases, verifies process/boot identity and reconciles stale owners. It releases the app-global lock only after the final registered owner exits; observed platform holder state is separate.
- The shared management service exposes continuity, boot, SSH and lease diagnostics/controls according to each client's real action coverage. Loopback HTTP/Web and Native GTK exist; they are not absent as in the older snapshot.

## Source and installed boundaries

The source entrypoints are `scripts/termux-boot/00-ternuxx-services`, `ternuxx-recovery` and `20-ternuxx-cron`. Native Runit now has separate SSH, terminal-broker and GUI-monitor definitions. The monitor is opt-in and currently runs idle; installing a worker does not enable its policy.

[Entrypoint inventory](../evidence/2026-10-22-native-entrypoint-inventory.json) verifies all seven script targets (three Runit, three boot, tx shim), all three currently installed canonical Python recovery modules and their isolated import closure. These are exact comparisons, not a completed audit of packages, driver provenance, profile hooks or clean setup.

The installed boot recovery helper prefers `$PREFIX/lib/ternuxx`. New source, installed copies and already-running process imports are separate states; update/deploy and verify the component actually used. A source commit alone does not change a loaded Python process.

## Boot and readiness evidence

[RB08 exit evidence](../evidence/2026-10-22-p3-rb08-postboot-exit-audit.md) records a changed Android boot, matching Native observer and ready Native service log, Cron boot delivery, and separately observed managed-8023 authenticated readiness. Its private checkpoint remains NOT_READY with auto-resume disabled because managed health was not captured at its own observation time.

Do not replace that checkpoint result with later manual evidence. Current readiness, boot delivery and automated checkpoint readiness are separate claims. The canonical module copy was deployed after the observed boot; its next cold-boot execution remains unobserved. No new reboot is authorized as a way to stop the current workstation.

Android procfs/netlink limits can leave socket-to-process ownership unknown. A banner, a running supervisor, a valid config and authenticated access each establish different facts. Record their actual scope instead of merging them into an unconditional recovery pass.

## Preservation and remaining work

Preserve Native Termux, development SSH 8022, managed 8023, and the current desktop. No broad cleanup, rootfs replacement or unrelated file mutation. Legacy launcher observations in history do not authorize invoking their cleanup routines.

Per-service boot/Wake Lock controls, broader shared recovery actions, all-client Native workflow qualification and fully reproducible supported setup remain in the active audit. Fixtures and current source tests cannot substitute for physical boot or workload evidence. See [reboot qualification](../testing/REBOOT-RECOVERY-GUIDE.md) for evidence vocabulary and owner-operated boot handling.
