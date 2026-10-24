# ADR-0009: Provider-scoped optional software selection
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** Partial implementation — fresh Debian package groups are selectable in the CLI and were replayed on-device; Native optional workload selection and shared CLI/Web/GTK/TUI catalog parity remain open
- **Type:** installation-and-package-management

## Context

The owner wants installation-time selection of optional software for both Native Termux and the Debian PRoot side, manageable later from CLI, Web Visualizer, and X11 GUI. The existing Ternux installer provides a useful behavioral reference: its current `main` exposes named optional workload flags (`--with-dev`, `--with-llm`, `--with-network`, `--with-media`, `--with-blender`, and `--all`), and its `tnx_phase_extras` implementation installs those workloads through Debian `apt` inside `proot-distro login debian`. This is evidence of PRoot-scoped extras, not a native-Termux two-provider selector. Sources: [Ternux installer options](https://github.com/soobujmiah/ternux/blob/main/install.sh) and [Ternux optional workload phase](https://github.com/soobujmiah/ternux/blob/main/lib/phases.sh).

The current local Ternux checkout may be stale; this decision is based on the live GitHub `main` files inspected on 2026-10-17. No source code was copied. Native Termux and PRoot have distinct package managers, filesystem roots, dependencies, and failure modes. The existing independent Ternux rootfs and launcher are protected and must not become an implicit install target.

## Decision

Model optional software as catalogued, provider-scoped selections. Installation presents separate Native Termux and PRoot sections, each with named bundles and individually selectable entries. A shared installation-plan service validates the catalog, calculates dependency closure, checks provider availability, and previews exact package changes before a user confirms.

- Native entries resolve only through the approved Termux package adapter (`pkg`/APT-backed Termux repositories).
- PRoot entries resolve only inside the explicitly selected Ternuxx-managed guest by default. An adapter to the independent existing Ternux installation is a separate, read-only-first integration; package installation there requires a separately approved scope and a clearly identified target.
- A PRoot workload may declare a separate native-owned shared-service dependency only by registry ID. It is not a package dependency and cannot satisfy a Debian library requirement. The service owner, consumer, transport, readiness check, and fallback must be explicit; see [ADR-0012](ADR-0012-native-owned-shared-dependencies.md).
- If a selected shell is not installed, its prerequisite package is included in the same provider plan, clearly distinguished from optional software. Shell profile selection and optional workload selection remain separate user choices.
- A selected item is a catalog ID, never a caller-supplied shell command, package-manager command, URL, or arbitrary script.
- Interactive selection supports multiple entries and a clear core-only choice. `--all` means all compatible optional entries for the explicitly named provider(s), never all providers implicitly.
- Non-interactive runs install core only unless provider-specific selections are supplied. `--yes` confirms only the exact previewed plan; it does not silently opt into optional bundles.
- The CLI, Web Visualizer, and X11 GUI call the same planner and operation service. The saved profile records desired selections separately per provider; it is not proof of successful installation.
- Provider/package failure is reported against that provider and item. Do not silently retry the same package in the other provider. Continue unrelated selections only when the plan explicitly marks them independent and the operation can safely report partial completion.
- Show repository, package IDs, dependencies, and size only when queried metadata supplies reliable values. Unknown sizes are shown as unknown, not estimated as fact.
- Selection cancellation or invalid IDs cause no package changes. Reinstall/update behavior is idempotent and state is verified after each package operation.

## Consequences

The fresh Debian Trixie setup path supports package-group selection in its CLI preview and confirmed apply. A new plan defaults to `base` only; additional groups must be selected explicitly, and a failed-plan resume inherits its recorded group selection. The dated disposable replay selected all five groups and verified 50 requested packages on this device. This is not the shared provider-scoped optional catalog described above: Native optional workloads, saved desired profiles, and Web/GTK/TUI parity remain unimplemented. Existing-guest package migration remains separate and unimplemented. See the [2026-10-23 replay evidence](../../evidence/2026-10-23-disposable-debian-replay.md).

## Acceptance criteria

The implementation status below is evaluated against current source and dated evidence; the acceptance criteria remain open unless explicitly qualified here.

1. Install preview displays Native and PRoot changes separately, including repositories and dependency resolution where available.
2. Core-only is the non-interactive default; optional software is selected explicitly per provider. **PRoot fresh setup now defaults to `base` only**, but Native optional selection and cross-provider catalog selection remain open.
3. A catalog ID cannot cause execution of arbitrary shell text or cross-provider fallback.
4. Existing Ternux rootfs/launcher is never selected or modified implicitly.
5. CLI, Web, and X11 interfaces produce the same plan from the same provider selections.
6. Cancelling, invalid selection, provider unavailable, and one-item failure produce truthful operation status without claiming installation.
7. Package operations have fixture/integration tests and are only device-qualified after owner-operated acceptance.
