# ADR-0016: `tx db` and legacy PRoot entrypoints
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Status:** accepted by owner direction in the active master execution prompt, 2026-10-22
- **Scope:** command identity, compatibility claims, and safe retirement of legacy shell entrypoints
- **Supersedes:** legacy-alias preservation clauses in ADR-0007, ADR-0010, and ADR-0015; it does not supersede existing-rootfs, user-data, process-ownership, or rollback safeguards.

## Context

Ternuxx is the independent Native Termux-first product. Its public command is `tx`, and `tx db` is a first-party Ternuxx operation that opens the selected Debian guest with Ternuxx's validated display, audio, and environment handoff. A bare shell command named `db` may be an unrelated alias and must not be treated as synonymous with `tx db`.

Older recommendations treated preservation of every Ternux-era alias as a product requirement. The owner has since clarified that `db`, `droot`, `x.sh`, `xgo`, and `killx` need not be retained for Ternuxx acceptance. This removes the blanket preservation requirement; it does not authorize broad cleanup, deletion of user files, or mutation of the existing Debian rootfs.

## Initial read-only inventory — 2026-10-22

On the Native Termux host, the relevant interactive shell block currently defines:

- `db` and `droot` as direct `proot-distro login debian` aliases, without Ternuxx's managed provider handoff;
- `x` and `xgo` as wrappers that invoke `~/x.sh`;
- `killx` as an informational message that sends no signal.

The current `~/x.sh` is a 112-byte executable wrapper that invokes the repository's `scripts/proot-x11-app.sh`. That helper requires the existing Ternuxx Native display, checks guest X11 reachability, starts/reuses Ternuxx Native audio, and launches a guest application. It does not call the separate Ternux CLI or stop desktop processes. The earlier broad-cleanup description of `~/x.sh` is historical and does not describe this observed file. The Debian rootfs and active guest were not entered or changed for this inventory.

Machine-readable/current evidence: [entrypoint inventory](../../evidence/2026-10-22-legacy-entrypoint-inventory.md).

## Owner-authorized alias migration — 2026-10-23

The active full-repository task explicitly authorized adapting task-relevant Native and Debian integration configuration. A bounded preview identified two Native shell aliases that bypassed Ternuxx; the exact changes route the regular-user alias through tx db with its existing account selection and route the root alias through tx db --root. The existing x/xgo wrapper and the unrelated cache-cleanup function were left unchanged. No guest login, package/config mutation, process stop, or rootfs change was performed.

The original mode-0600 shell startup file is retained in the Native user's private Ternuxx configuration-backup area with its exact pre-change hash. The replacement passed bash -n, both tx db help paths, post-write hash checks, and a disposable rollback fixture that restored the exact pre-state hash and mode. Already-open shells may retain their prior aliases until they reload the startup file or are restarted. The exact Native and Debian legacy CLI retirement previews then found their fixed command targets absent; no CLI file mutation was needed. See [alias migration evidence](../../evidence/2026-10-23-native-legacy-alias-migration.md) and [legacy CLI inspection](../../evidence/2026-10-23-legacy-cli-absence.md).

## Decision

1. `tx db` remains canonical, first-party, and distinct from bare shell `db`. Help, tests, installation docs, and migration guidance must state this clearly.
2. Ternuxx has no blanket compatibility obligation to preserve `db`, `droot`, `x.sh`, `xgo`, or `killx`.
3. Do not edit user shell configuration, delete a launcher, or alter guest state merely to remove a legacy name. First inventory real callers, dependencies, active workloads, and the exact target. Keep any useful entrypoint external until a replacement is verified.
4. A future retirement may touch only the exact Ternuxx-owned integration through a preview that shows target, content diff, backup and rollback. User-owned shell configuration and the existing guest require a separate exact operation and explicit confirmation; the 2026-10-23 migration above is the owner-authorized bounded example. Never run Ternux cleanup or terminate unknown processes.
5. Historical reports retain the names and behavior observed at their dates. Current docs must point to the live inventory instead of presenting historical behavior as current.

## Acceptance

- Native `tx db --help` identifies the first-party command and distinguishes bare `db`.
- Help contract tests fail if the distinction disappears.
- Product code and boot helpers do not invoke bare `db`, `droot`, `xgo`, `killx`, or the separate Ternux CLI as hidden dependencies.
- Any alias/launcher migration proves replacement behavior, exact ownership, active-workload compatibility, backup, and rollback before apply.
- The active Codex PRoot session, existing Debian rootfs/data, Native Termux, and SSH channels remain outside automatic cleanup.
