# Desktop package cleanup and Native PulseAudio recovery

**Observed:** 2026-10-25 20:23 UTC (2026-10-26 02:23 Asia/Dhaka)
**Checkout:** `/data/data/com.termux/files/home/ternuxx`; branch `main`; origin `soobujmiah/ternuxx`
**Scope:** Reconcile the requested failed/partial desktop cleanup and restore the existing Native `:1` plus managed audio service without resetting the Debian guest.

## Desktop package state

The 2026-10-25 cleanup record did not match the package database on this recheck: GNOME/Cinnamon components remained installed. A fresh APT simulation targeted those components and their required removal closure with `--no-install-recommends` and no `--auto-remove`: 43 packages to remove, zero upgrades, and one 1.622 MB `sddm-theme-debian-elarun` dependency to install (the retained LXQt package set requires an SDDM theme or display-manager provider). APT reported 228 MB freed. The transaction removed the GNOME/Cinnamon branches. Its process was interrupted before returning; `dpkg --configure -a` completed the pending `man-db`, D-Bus, and GLib configuration/triggers.

A second exact simulation covered the remaining `muffin-common` and `nemo-data` packages: two removals, no installs/upgrades, 4,335 kB freed. That transaction completed. No autoremove was applied, so unused dependencies (including PipeWire packages) remain installed. Final checks returned no `dpkg --audit` findings and `apt-get check` exited 0. `proot_desktops.installed_desktops()` reports exactly `xfce`, `lxqt`, `lxde`, `mate`, and `plasma`; no GNOME/Cinnamon session is reported installed. The retained set matches the live-route evidence: XFCE/LXQt/LXDE/MATE pass standalone and nested, while Plasma passes standalone and remains failed on nested. Native inventory remains XFCE/MATE/Plasma installed, with LXQt/Cinnamon absent. The selectable catalogs now match verified routes: Debian exposes XFCE/LXQt/LXDE/MATE/Plasma (GNOME/Cinnamon removed), while Native exposes XFCE/MATE/Plasma (failed LXQt/Cinnamon removed). Package selection, inventory, install repair, and session resolution use these same allowlists; the launch commands now reject unsupported IDs.

The PRoot guest and its setup receipt were preserved. No PRoot desktop was started in this recheck; standalone `:0` and nested `:2` remain stopped. Prior route observations are recorded in [Debian desktop catalog evidence](2026-10-25-debian-desktop-catalog-extension.md).

## Native desktop and audio recovery

The managed Native `:1` session was stale on entry (its recorded supervisor and X11 process were absent). `tx start` reconciled only the recorded stale `:1` socket/lock pair and restored Native XFCE; `tx status` then reported its supervisor, Termux:X11, and XFCE live. Android Activity visibility remains unknown.

The first PulseAudio start exposed stale artifacts in the private Ternuxx runtime directory: an owner PID file referenced an absent process and its private `native` Unix socket refused connections. `lib/pulse_lifecycle.py` now removes only that exact private PID/socket pair after validating directory/file ownership, type, mode, PID absence, and socket refusal. It preserves live processes, accepting sockets, malformed records, and unowned sockets. Focused tests cover stale cleanup and refusal cases. `tx audio start` then returned `state=running`, `owner=ternuxx`, `default_sink=OpenSL_ES_sink`; `tx audio status` matched the process identity. Native `pactl info` returned PulseAudio 17.0-dirty on `tcp:127.0.0.1:4713`.

A read-only Debian PRoot user command bound only the Native PulseAudio cookie into the isolated guest and ran `pactl info` against that loopback endpoint. The authenticated handshake returned PulseAudio protocol 35 and the `OpenSL_ES_sink` default. This proves guest client authentication and endpoint reachability, not audio playback or audible output.

## Verification boundary

- `python3 -m unittest tests.test_pulse_lifecycle -v`: 16 tests passed after the final recovery guard change.
- `bash scripts/repo_test.sh`: 1,179 tests passed in 190.022 seconds after synchronizing the selectable catalogs with route evidence; CLI help contract passed. GitHub Actions run [40229311678](https://github.com/soobujmiah/ternuxx/actions/runs/40229311678) passed both validation and repository state synchronization after the CI-specific directory-metadata fix.
- Native and Debian package health: `dpkg --audit` clean; Debian `apt-get check` exit 0.
- Native XFCE `:1` is process-live; `xdotool getdisplaygeometry` returned `752x1155`; standalone `:0` and nested `:2` are stopped; managed guest-session inventory is empty.
- This catalog-only correction did not start or alter any desktop session. No graphics workload was run. Adreno/Zink application rendering, Android presentation, sustained thermal qualification, audible playback, and GUI visibility remain unverified.

## 2026-10-25 20:27 UTC route-aware desktop selection

The authoritative Debian route matrix shows XFCE, LXQt, LXDE, and MATE pass both standalone :0 and nested :2; Plasma passes standalone only. The shared catalog now encodes that matrix. tx pgui filters explicit-mode choices and performs a second route guard after resolving auto, so Plasma cannot start on nested :2. Generated Plasma shortcuts specify standalone mode; other passing desktop shortcuts remain automatic. Failed GNOME/Cinnamon cases were removed from launch wrappers and selectable catalogs. Failed Native LXQt/Cinnamon package groups were also removed from the custom installer, retaining Native XFCE/MATE/Plasma.

CLI, TUI, Web setup examples, and tx help now use the supported desktop IDs. Management shortcut payloads include route metadata and matching launch commands. No desktop session or package transaction was started for this source/catalog change.

- bash scripts/repo_test.sh: 1,180 tests passed in 171.265 seconds; CLI help contract passed.
- Focused PRoot desktop, GUI routing, shortcut, and Native package-profile tests passed.
- tools.audit_documents: zero broken links; repo_knowledge verify: zero findings; shell syntax and git diff --check passed.
- No live application rendering or Android visibility test was performed; route decisions are from the dated live matrix.
