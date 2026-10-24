# ADR-0008: Per-provider shell profiles and managed configuration
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** Owner requirements recorded; implementation and provider tests pending
- **Type:** install-and-configuration-architecture

## Context

The owner requires shell choice during installation and shell management from the CLI, X11 GUI, and Web Visualizer. This applies independently to Native Termux and the existing Debian PRoot provider. Bash, Zsh, and Fish must be selectable where available. Users must be able to choose themes and edit Ternuxx-managed shell configuration through all interfaces.

These environments have separate package managers, homes, executable paths, permissions, and shell startup rules. Bash uses different startup files for interactive login and non-login sessions; Zsh honors `ZDOTDIR` and uses `.zshrc` for interactive shells; Fish supports `conf.d` snippets under its configured data directory. Treating all three as a `.bashrc`-style text edit would be incorrect. Sources: [Bash startup files](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files), [Zsh startup files](https://zsh.sourceforge.io/Doc/Release/Files.html), [Fish configuration](https://fishshell.com/docs/current/language.html#configuration-files).

## Decision

Represent shell selection as a per-provider profile in one shared configuration service. Native Termux and Debian PRoot may select different shells. Installation detects the current interactive shell to provide a preselection, but the user can choose Bash, Zsh, or Fish separately for each enabled provider. A missing shell is shown in the install plan; it is installed only after explicit package-change confirmation.

Use adapters for shell-specific discovery, managed snippet generation, completion, theme application, validation, and startup integration. The adapter must distinguish the active process from `$SHELL`, which may describe only the login shell. If detection is ambiguous, ask the user to choose rather than silently changing a shell.

Themes are versioned Ternuxx-managed overlays. Built-in themes must avoid requiring third-party prompt/plugin frameworks. A theme change updates only its owned overlay and reports the resulting prompt/configuration preview. Custom/community themes require separate source, license, and security review before inclusion.

The configuration editor edits a Ternuxx-owned layer, not arbitrary startup files. Shell-neutral settings (theme, completion, and supported history preferences) are the canonical source; adapters render them for Bash, Zsh, or Fish. On shell change, migrate these canonical settings and Ternuxx-managed overlays to the target adapter. Do not copy and execute the old shell's raw RC file as a migration method. An optional user-selected import may parse a narrowly defined allowlist without executing source code; unsupported/custom entries are reported for manual handling.

Shell migration is transactional: stage a target overlay separately; show a mapping report and unified diff; verify that the package and target adapter are available; validate target syntax and profile; preserve the old shell, config, and selected-shell pointer until the new profile is accepted; then switch the pointer and retain a rollback revision. If any stage fails, keep the previous profile active. Never remove the old shell automatically.

The editor provides a draft, syntax/format validation by the selected shell, a unified diff, backup/revision, explicit apply, and rollback. Startup files are left intact by default. If activation requires a startup hook, show the exact additive change, preserve a backup, detect conflicts, and request explicit confirmation. Never overwrite a user's RC file or Ternux/legacy aliases.

The CLI, X11 GUI, and Web Visualizer call the same provider-aware shell configuration service. The web client never writes files directly. The PRoot adapter must use a narrowly scoped, owner-approved Ternuxx config path and must not edit the independent Ternux launcher, rootfs, or unrelated user configuration. Native and PRoot operations are always labeled and planned separately.

The canonical contracts are [`shell-profile.schema.json`](../../../schemas/shell-profile.schema.json) for per-provider shell choices and [`shell-settings.schema.json`](../../../schemas/shell-settings.schema.json) for shell-neutral settings. Neither accepts arbitrary shell commands, secrets, or mutable filesystem paths.

## Initial operation contract

- Install wizard: detect and preselect independently for native and PRoot; expose explicit Bash/Zsh/Fish choices and package changes before apply.
- CLI: `ternuxx shell list|status|select|theme|config` with an explicit `--provider native|proot` for mutations.
- GUI/Web: shell profile, theme catalog, configuration editor, validation output, diff, apply, and rollback backed by the same operations.
- Every mutating operation returns a plan/task ID and requires confirmation; package installation and configuration application are distinct operations.
- First-class theme controls include list, preview, apply, and reset. Theme assets/config must be local, small, and explicitly licensed; do not download third-party prompt code in the core path.
- Configuration editing supports structured Ternuxx settings in all clients. Advanced edits are limited to the managed overlay and go through the target shell's syntax checker before a diff/confirmation. It is not a general-purpose editor for arbitrary guest or host files.
- If a shell or provider adapter is unavailable, preserve the current profile and report a manual next step.

## Consequences

- Native and PRoot can use different shells without conflating their state.
- Shell-specific config behavior stays behind adapters and can be tested without changing a live shell.
- Managed overlays reduce conflict risk but require a carefully validated activation mechanism per shell and provider.
- Zsh/Fish package presence, active-process detection, startup integration, and theme rendering still need native and PRoot validation; documentation is not runtime evidence.
- No shell package was installed and no device or PRoot configuration was changed during this design update.

## Acceptance criteria

1. Install planning independently lists native and PRoot shell choices and exact missing-package changes.
2. Bash, Zsh, and Fish detection handles nested shells and stale `$SHELL`, with an explicit manual-choice path for ambiguity.
3. CLI, Web, and X11 clients read/write the same provider profile through one service.
4. Theme/config edits are isolated to Ternuxx-managed overlays, validated by the target shell, previewed as a diff, backed up, and reversible.
5. Existing startup files, aliases, Ternux files, and unrelated configuration survive repeated install/update/uninstall tests unchanged except for an explicitly approved additive hook.
6. Provider-specific tests cover missing shell, missing home/config path, unsupported shell, syntax failure, hook conflict, repeated apply, rollback, and PRoot unavailability.
7. Missing shell/package, adapter failure, or invalid theme/config leaves the last working shell and validated configuration usable; the portable CLI remains available.
8. Switching shells migrates supported Ternuxx settings through the neutral profile, reports unsupported entries, and preserves the source shell/config for rollback until target-shell validation succeeds.
