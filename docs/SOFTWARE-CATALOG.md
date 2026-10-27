# Native software catalog and installation

Ternuxx manages Native Termux packages and optional pinned Debian/Ubuntu guest packages through separate reviewed plans. Native remains the host/control plane. Android companion apps such as Termux:X11 are installed and updated through their publisher; Ternuxx does not sideload APKs.

## Workstation installer selections

`tx install` offers keyboard-selected optional apps. Up/Down and Space select;
Home/End and PageUp/PageDown navigate long lists. `none` excludes other choices.
The Native Audacious choice installs both `audacious` and `audacious-plugins` so its
output backend is present. Audacity is a separate optional audio editor. VLC uses
the GUI-enabled `vlc-qt` package. Blender 4.5 is available as the Native optional
`blender4` package from the community TUR repository; choosing it explicitly asks
Ternuxx to install `tur-repo` and refresh signed indexes before planning. TUR-origin
packages are permitted only in that Blender-selected transaction. When the
CLI-only `vlc` package is already installed, its exact reviewed plan replaces that
package and refuses unrelated removals. Native definitions live in
`lib/install_catalog.sh`; guest definitions live in `lib/proot_software.py`. The
existing package engines bind every selected package and dependency to a reviewed
exact plan. The guest CPU/graphics runtime includes `x11-utils` for display
inspection and `xserver-xephyr` for nested PRoot desktops. A missing candidate
stops preview rather than adding another package source, except the explicitly selected
Blender option which enables the signed TUR source with consent.

| Category | Examples in Native | Additional guest selections |
|---|---|---|
| Graphics/photos | Blender 4.5 (TUR), GIMP, Inkscape, Krita, Darktable, RawTherapee, ImageMagick, Flameshot | Blender, FreeCAD |
| CAD | OpenSCAD | OpenSCAD, FreeCAD, Blender |
| Media | Audacity, Kdenlive, HandBrake, FFmpeg, mpv, VLC (`vlc-qt`), Audacious | Audacity, Kdenlive, FFmpeg, mpv, VLC |
| Office | AbiWord, Gnumeric, Qalculate, TeXstudio, Evince | LibreOffice Writer/Calc/Impress as separate choices |
| Development | Geany, Kate, Meld, QGit, Neovim, Lazygit, Node.js LTS, Rust, Go, jq, SQLite | Guest-native editor/language tools |
| System | XFCE task manager, ncdu, duf, lsof, strace | htop, ncdu, lsof, strace |
| Security/network | KeePassXC, Rclone, Syncthing, aria2, Nmap, iperf3, qBittorrent | Corresponding available APT choices |
| Science | Gnuplot, GNU Octave | Gnuplot, GNU Octave |
| AI setup recipes | Codex Termux `@next`, experimental Hermes canary | Upstream Codex, Hermes and Claude Code |

AI entries install only labeled prerequisites and show [explicit setup recipes](AI-TOOLS.md).
They do not claim an installed agent. Native Claude is not offered. Blender is an
optional TUR package and is not included in default workstation selections.
Native Writer-only remains unavailable; AbiWord is a separate alternative and is
never silently substituted. Guest browser defaults remain Debian Firefox ESR and
Ubuntu Epiphany (no Snap).

Package availability is not workload qualification. Graphics-heavy programs need
separate CPU/GPU/display acceptance; installing network tools does not start a
service. No package source is added implicitly; the explicitly selected Blender
choice asks before enabling the signed TUR repository and scopes its packages to that
reviewed transaction. Other Native package candidates are checked against configured
signed Termux indexes.

## What is implemented

- `tx install preview` reviews the Native Termux packages required by the selected base desktop profile.
- `tx install update preview` reviews updates to Ternuxx-managed core packages.
- `tx app list` shows status for three curated app IDs: `process-monitor` (`htop`), `terminal-multiplexer` (`tmux`), and `directory-tree` (`tree`).
- `tx app preview APP_ID install|update|remove` simulates an exact per-app package transaction; `tx app apply ... --plan-id ID --confirm ACTION` rechecks and applies only that saved plan.
- tx app run directory-tree HOME_PATH passes one selected regular file or directory under Native HOME to the fixed tree executable. It is read-only, bounded to two directory levels and 32 entries per directory, and returns names only; it never reads file contents or follows a selected symlink.
- The same shared operations are exposed in the TUI, authenticated Web management, and GTK Management Center. All clients use the shared typed service and authorization policy.
- `tx mng catalog list` shows the shared management resource catalog. Catalog status distinguishes implemented Native operations from partial and planned work.
- `tx guides` routes to Native package preview, Doctor, status, desktop start, pinned CPU-model setup, CPU/GPU/NPU status, Debian inventory and fresh-guest preview, TUI, authenticated Web management, GTK management, and the installation/operations guides.

The separate `tx app` lifecycle catalog remains limited to those three IDs; the wider workstation installer catalog above uses `tx install`. Arbitrary package names, third-party repositories, APK sideloading, shared-storage paths, and symlink traversal are outside that per-app lifecycle workflow.

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
