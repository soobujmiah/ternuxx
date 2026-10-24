# ADR-0017: Native Termux-only product and PRoot retirement

> **Historical decision:** This temporary direction was later reversed on 2026-10-24 when the owner reauthorized Debian PRoot support. P11 is the current restoration and acceptance phase. This ADR records the earlier removal authorization and completed snapshot; it is not the current product direction.

- **Date:** 2026-10-24
- **Status:** Reversed by later owner direction; retained as a historical record
- **Supersedes:** Current product choices in ADR-0001, ADR-0010, ADR-0015, and PRoot/hybrid portions of the roadmap
- **Reversed by:** Owner reauthorization of Debian PRoot support, tracked in P11

## Decision

Ternuxx is a Native Termux-only Android workstation manager. Remove PRoot launch/setup/guest-management workflows, Debian package and graphics handoff, PRoot-specific client controls, and the Native `proot`/`proot-distro` package dependencies. Retire every installed PRoot-Distro container on the owner's Native Termux installation, including the adopted Debian guest and replay guests. The owner explicitly confirmed the removal scope and that a backup exists.

Preserve Native boot/recovery, SSH, CLI, management service, status/diagnostics, desktop, Native graphics/audio paths, and supported CLI/TUI/Web/GTK guidance. Keep old PRoot evidence as dated historical records unless a separate retention review removes it. Do not modify the separate `soobujmiah/ternux` repository or launcher.

## Safety and execution boundary

- Native Termux owns the product runtime; no Debian/PRoot execution path is allowed after migration.
- Keep the Termux app, Native desktop, managed SSH, and other Native services open and running.
- Use the installed PRoot-Distro manager for exact, named guest removal after checking inventory. Its current 5.9.0 implementation removes a directory by descriptor and unlinks symlinks without following their targets.
- Do not inspect or traverse shared/external storage. Never allow rootfs cleanup to follow a symlink outside the named container tree.
- Remove `proot-distro` and `proot` only after all containers are absent and the Native package plan no longer depends on either.
- The owner-reported backup was not accessed or independently verified; record that limit.

## Migration and acceptance

1. Remove PRoot controls and dependencies from the shared service, permissions, catalog, CLI, interactive clients, package manifest, schemas, and current user documentation.
2. Keep Native interactive guidance and ensure removed PRoot commands return a clear migration hint instead of a traceback or dead UI action.
3. Retire all six audited aliases: `debian`, `ternuxx-replay-audit-20261023`, `ternuxx-replay-p4`, `ternuxx-replay-p4-coldboot`, `ternuxx-replay-p4-retry`, and `ternuxx-replay-repro`.
4. Remove the two Native packages after guest retirement and verify they are absent.
5. Pass the full test suite, help/CLI contract, document/link checks, Native installation preview, and live Native smoke checks. Confirm the Native desktop and services remain available and PRoot inventory is absent/unavailable.
