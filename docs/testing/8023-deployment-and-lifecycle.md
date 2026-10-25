# 8023 managed SSH deployment and lifecycle qualification

## Reconciliation workflow

Use Native Termux. `tx ssh deploy` without confirmation produces a read-only plan with source/installed hashes, exact unified diff, effective SSH configuration hash, current Runit status, and an exact plan ID. Review it before applying with `tx ssh deploy --yes --plan-id <plan-id>`. Applying atomically replaces only the fixed run definition and records a private rollback snapshot. It does not restart or stop the running unit, touch SSH configuration, or affect external Native SSH configuration.

The fixed managed service also has `tx ssh start`, `tx ssh stop`, and `tx ssh restart`; each command first returns a read-only, exact-plan preview. Restart always requires explicit confirmation, sends down then up only to `$PREFIX/var/service/ternuxx-sshd`, and warns that active 8023 clients may disconnect. Recovery observes the expected final state and never repeats a restart. Native restart preview now passes; no restart apply was run. See [restart implementation evidence](../evidence/2026-10-22-ssh-service-restart.md).

To preview and apply a rollback, run `tx ssh deploy-rollback-preview --operation-id <id>`, then `tx ssh deploy-rollback --operation-id <id> --yes --plan-id <plan-id>`. A rollback plan shows its own diff. If automatic rollback after a partial write fails, the deployment journal stays `needs_recovery`; explicit recovery uses that operation's snapshot and resolves the same journal after verification. Never delete a recovery snapshot while its journal is unresolved.

Seven fixture regression tests are in `tests/test_runit_deployment.py`. They cover read-only preview/diff, exact-plan confirmation, apply and explicit rollback, partial write with automatic restore, failed automatic restore followed by recovery, partial explicit rollback recovery, symlinked snapshot refusal, source/config validation, and the absence of Runit up/down/restart actions. These tests do not replace device deployment verification.

## Current lifecycle qualification result (2026-10-18)

The lifecycle plan below has now been executed for the current boot. Exact-plan stop/start passed twice, repeated-start was an idempotent no-op, authenticated loopback SSH returned exit 0, and ADB socket inode ownership matched the managed sshd FD and Runit ancestry. The external recovery channel remained available. Fixture-only deployment failure, rollback, and recovery scenarios passed in the full suite. Reboot remains `UNVERIFIED`; no reboot was performed. See [dated gate evidence](../evidence/2026-10-18-8023-lifecycle-qualification.md) for exact PIDs, hashes, commands, and limits.

The historical state mismatch described above is resolved: the installed CLI shim invokes the checkout through `$PREFIX/bin/bash`, and the run definition exports only `TERNUXX_STATE_DIR`. A stale lease for PID 12951 was removed only after the kernel confirmed the PID absent; ambiguous identity remains fail-closed. Current service and SSH banner pass, and both CLI paths report one active `native.sshd` lease. The key-only BatchMode probe was denied; a subsequent owner-provided interactive SSH probe returned `authenticated-loopback-ok`. ADB mapped 8023 inode 2372520 to managed sshd PID 22443 FD 6 and Runit ancestry. Current authenticated readiness and listener ownership are VERIFIED; see the follow-up evidence. The installed CLI shebang was then changed to Android `/system/bin/sh` and direct `execve` via Python exited 0; see the same continuation evidence. Full continuation evidence: [CLI/state reconciliation](../evidence/2026-10-18-cli-entrypoint-state-reconciliation.md). Android global wakelock state remains unobservable.

## Separate 8023 lifecycle qualification plan

Run this only after a reviewed plan and preserve the independently managed recovery channel. Do not reboot without explicit owner approval.

1. **Start:** from stopped state, preview then confirm start; verify exactly one owned Runit process, authenticated loopback SSH readiness, and journal completion.
2. **Repeated start:** verify idempotent/no duplicate daemon behavior and stable ownership.
3. **Stop:** confirm the impact on active 8023 sessions; verify only the verified managed process stops and listener disappears. Keep the independently managed recovery channel available.
4. **Repeated stop:** verify no unrelated process is signaled and journal state remains consistent.
5. **Restart:** apply remains unqualified on-device. The exact preview passed read-only; fixture tests verify down/up ordering and observation-only recovery. A separately authorized apply test must verify readiness, disconnect impact, and failure recovery.
6. **Listener ownership:** correlate loopback socket inode to process FD and Runit ancestry; record exact commands and permissions. If `/proc/net/tcp*` or process FDs are denied, report `UNVERIFIED`.
7. **Duplicate instance:** safely inject only in a fixture; on device, inspect for duplicates without killing ambiguous processes.
8. **Failure recovery:** exercise startup timeout, stale state and rollback in fixtures first; on device use only a reviewed non-disruptive case and preserve journal/log evidence.
9. **Post-reboot:** remains `UNVERIFIED` until an explicitly approved reboot and authenticated post-boot readiness/ownership checks pass.

Each device result records commit, UTC timestamp, environment, command, expected/actual result, status, evidence path, and limitations. A config syntax pass or SSH banner alone does not prove process ownership or authenticated readiness.
