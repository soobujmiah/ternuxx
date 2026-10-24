# Native software catalog and installation

Ternuxx supports Native Termux packages only. It does not install or manage a Linux guest, distribution, or second package provider. Android companion apps such as Termux:X11 are installed and updated through their publisher; Ternuxx does not sideload APKs.

## What is implemented

- `tx install preview` reviews the Native Termux packages required by the selected base desktop profile.
- `tx install update preview` reviews updates to Ternuxx-managed core packages.
- `tx app list` shows status for three curated app IDs: `process-monitor` (`htop`), `terminal-multiplexer` (`tmux`), and `directory-tree` (`tree`).
- `tx app preview APP_ID install|update|remove` simulates an exact per-app package transaction; `tx app apply ... --plan-id ID --confirm ACTION` rechecks and applies only that saved plan.
- tx app run directory-tree HOME_PATH passes one selected regular file or directory under Native HOME to the fixed tree executable. It is read-only, bounded to two directory levels and 32 entries per directory, and returns names only; it never reads file contents or follows a selected symlink.
- The same shared operations are exposed in the TUI, authenticated Web management, and GTK Management Center. All clients use the shared typed service and authorization policy.
- `tx mng catalog list` shows the shared management resource catalog. Catalog status distinguishes implemented Native operations from partial and planned work.
- `tx guides` routes to Native package preview, Doctor, status, desktop start, pinned CPU-model setup, CPU/GPU/NPU status, Debian inventory and fresh-guest preview, TUI, authenticated Web management, GTK management, and the installation/operations guides.

The curated app IDs are deliberately limited. Arbitrary package names, third-party repositories, guest distributions, APK sideloading, shared-storage paths, and symlink traversal are outside this workflow.

## Safe package workflow

1. Run `tx guides`, `tx app list`, or `tx install preview` in Native Termux.
2. For an optional app, preview its exact transaction and review repository origin, package/dependency changes, and plan identifier.
3. Apply only with the matching app action and plan ID after reviewing it. Curated app apply requires exact `INSTALL`, `UPDATE`, or `REMOVE` confirmation; base-profile apply uses `tx install apply --yes --plan-id ID`.
4. Run `tx doctor` and inspect the package manager result. Package installation does not prove the desktop is visible or that graphics/audio acceleration works.

Ternuxx does not silently change package providers, fetch arbitrary install scripts, or claim support because a package appears in an index. Package metadata and candidates can change; saved app previews expire after 15 minutes, and apply re-simulates before execution. Fresh signed Termux indexes, configured official repository origins, and an unchanged dependency closure are required. App removal disables autoremove and refuses dependency/removal drift. Package commands are bounded and results are recorded in private Ternuxx state. An interrupted operation marked as applying requires checking `dpkg` and APT state before attempting a new preview.

## Support labels

| Status | Meaning |
|---|---|
| `implemented` | The named Native operation exists in the shared service/client contract. |
| `partial` | Some operations exist; listed gaps remain. |
| `planned` | No install or management action is available yet. |
| `unavailable` | A checked prerequisite or workload cannot currently be used in the observed profile. |

The [Ternuxx feature matrix](testing/FEATURE-MATRIX.yaml) and [device profile](testing/DEVICE-COMPATIBILITY.md) are the current status sources. The former broad multi-provider app/distro catalog is preserved as a [dated planning snapshot](history/SOFTWARE-CATALOG-pre-native-only-2026-10-24.md); it is not an install guide or support promise.
