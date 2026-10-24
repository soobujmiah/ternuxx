# ADR-0015: Ternuxx owns the existing Debian PRoot setup
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-20
- **Status:** accepted by owner; implementation partial (current status reviewed 2026-10-24)
- **Alias-preservation clauses:** superseded by [ADR-0016](ADR-0016-tx-db-and-legacy-entrypoints.md); existing-rootfs preservation and scoped adaptation remain active
- **Type:** provider-integration and install-reproducibility

## Decision

Ternuxx becomes the sole product control and setup layer for the existing Debian PRoot. It must not require, invoke, or install the separate Ternux CLI. The Ternux CLI can be removed from the current device only after Ternuxx's replacement path is verified and a hash-bound removal preview and rollback snapshot exist.

On this device, Ternuxx adopts the existing Debian rootfs in place. It must not replace, reinstall, reset, upgrade, prune, or broadly clean that rootfs. On a fresh Ternuxx installation with no Debian rootfs, a separate preview-confirmed Ternuxx setup creates Debian and applies the versioned Ternuxx guest profile. Existing and fresh-install paths are separate; an existing rootfs is never treated as a blank install target.

The baseline setup contract is in config/proot/debian-trixie.json. It records Debian Trixie, package groups, the pinned Turnip input, guest install paths, launch environment, native authenticated audio handoff, and explicit library ABI boundaries. Current rootfs user data and user-specific values remain local inputs; the repository does not copy private state or credentials.

## Safety rules

- Keep Native Termux as the single owner of Termux:X11, PulseAudio, and PRoot launch environment.
- Do not modify Debian startup files or package-managed Mesa files as a shortcut. Ternuxx-owned overlays use exact, recorded paths and validated rollback.
- Use the Debian/glibc Turnip artifact only inside Debian. Never put Native/Bionic libraries in the guest.
- Preserve existing user data, account, and packages while adapting the management boundary. Legacy entrypoints are audited and retired only when an exact owner-scoped plan proves the replacement; the alias-preservation portion of this earlier requirement is superseded by ADR-0016.
- Ternuxx does not invoke legacy broad cleanup, desktop restart, or service lifecycle commands from the Ternux CLI.
- New rootfs, guest packages, graphics files, and legacy CLI removal each require a scoped preview and explicit apply. Package plans include the guest APT dependency closure.

## Acceptance

1. The current rootfs device/inode and protected user/config/package baseline are recorded before adaptation.
2. Ternuxx status, launch, diagnostics, graphics, and audio use Ternuxx-owned contracts without calling the legacy CLI.
3. Fresh setup follows repository-owned manifests and pinned external inputs, creates the same supported Debian workstation profile, and verifies the actual GL renderer and audio handoff.
4. Existing Debian and Native sessions remain live throughout migration; no duplicate X11/PulseAudio owner is started.
5. Legacy host and guest CLI removal is previewed by exact path and identity, backed up, and reversible.

## Current implementation state

The versioned profile and Native-side current-rootfs adoption record exist. Ternuxx calls proot-distro directly for bounded guest sessions and graphics operations; status and inventory are read-only, while explicit guest verification may write proot-distro-generated login-profile settings. A separately named Debian Trixie replay completed pinned image/snapshot package setup and verified all 50 requested packages on the recorded Native device on 2026-10-23; the pinned Turnip artifact installed, but its runtime did not qualify. This is not clean-device or full-workstation reproducibility. Existing-guest configuration migration, complete setup rollback, visible GUI/audio/Turnip workload acceptance, and broader Native/PRoot configuration parity remain open. Fixed legacy Ternux CLI paths were absent in the 2026-10-23 read-only check, so no removal operation ran; see [legacy CLI absence evidence](../../evidence/2026-10-23-legacy-cli-absence.md). Guest verification may trigger generated login-profile writes; see [PRoot verification boundaries](../../PROOT-GPU.md). See also the [completed replay evidence](../../evidence/2026-10-23-disposable-debian-replay.md) and [current audit](../../audit/REPOSITORY-AUDIT.md). This ADR or manifest alone does not prove fresh-install readiness.
