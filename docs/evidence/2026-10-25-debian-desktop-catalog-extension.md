# Debian desktop catalog extension — 2026-10-25

The Debian Trixie desktop catalog supports XFCE, LXQt, LXDE, MATE, GNOME, KDE Plasma, and Cinnamon. The Debian guest uses the pinned `debian:trixie-20261005` image and recorded setup profile `ternuxx-debian-trixie-workstation`. GNOME (`gnome-core` 1:48+2), Plasma (`kde-plasma-desktop` 5:162), and Cinnamon (`cinnamon-desktop-environment` 6.4.1) were installed through a Ternuxx preview-bound transaction. The exact additional transaction covered 805 packages, with no upgrades or removals; the verified guest now has 1,526 installed packages. An interrupted earlier apply was recovered with an exact failed-plan-bound dpkg recovery preview, and `dpkg --audit` is clean.

The package planner filters unselected desktop meta-packages and retains the shared manifest receipt. Standalone and nested launch routing map each catalog ID to a fixed command argv. Shortcut sync preview/apply generated launchers for all four installed Debian sessions (XFCE, GNOME, Plasma, Cinnamon) and 52 discoverable guest application entries, with no conflicts. Desktop launch choices are exposed through the CLI, TUI, Web and GTK management center. The Native registry supports XFCE, LXQt, MATE, Cinnamon, and Plasma. Exact-preview custom components installed the full MATE, Cinnamon, and Plasma package sets on the Native host; Native XFCE remains the default.

Live acceptance on 2026-10-25: Native XFCE on `:1` was restored after tests. Debian XFCE passed standalone `:0` and nested Xephyr `:2` process/window-tree checks for `xfce4-session`, `xfce4-panel`, `xfdesktop`, and `xfwm4`; `xwininfo -root -tree` enumerated desktop windows on both routes. Nested XFCE was rerun after the private bus/session environment changes and still passed. Its GLES context reported `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`, which verifies a context/device string only, not rendered frames or accelerated application workloads.

Debian sessions now receive a per-session private D-Bus system-bus endpoint inside the guest; the Native host bus is not passed through. The session environment also sets the selected X11 desktop identity. GNOME on `:0`/`:2` reached the session manager but showed `gnome-session-failed`; nested logs reported no GTK GLES configurations for the pixel format and no `systemd1`/logind service. Plasma emitted unavailable DRI3 and GLX initialization errors and showed no verified panel/shell (the `:0` window tree stopped at `ksplash`). Cinnamon's session manager started, but `cinnamon` crashed (`GLib-CRITICAL: g_strsplit ... string != NULL`); `cinnamon-launcher` then could not find its `metacity` fallback, and no panel/window manager appeared. These three sessions are installed and shortcut-routed, but their live desktop acceptance fails and they must not be described as working.

The standalone `:0` XFCE test passed process/window-tree acceptance: using the recorded Debian user, `xwininfo -root -tree` showed `xfce4-panel`, `xfdesktop`, and `xfwm4`; the owned PRoot GUI was then stopped and Native XFCE restored on `:1`. The standalone `:0` GLX probe reported Zink/Vulkan on Adreno 825 Turnip with `Accelerated: yes`; the separate prior bounded GLX workload record is linked below. This live probe alone does not verify rendered app workload or visible presentation. `gui_visible` remains `unknown` because no Android screenshot/visibility interface is available in this runtime.

Standalone Debian GNOME on `:0` showed `gnome-session-failed`; Plasma remained at `ksplash` without a verified panel; Cinnamon exposed a shell process and desktop helper windows but no verified panel. These remain installed and routed, but are not accepted as working standalone desktops.

Other PRoot distribution providers and distro-specific clean system profiles are not implemented. Native LXQt installation is available through the exact-preview custom `lxqt` component. The session-only package and then the full LXQt meta-package were both installed via reviewed plans; repeated Native `:1` startup failed (LXQt lock-screen manager and Qt XCB display errors), so XFCE was restored. A later XDG session-identity setting did not resolve the failure. The custom installer exposes exact-preview `mate`, `cinnamon`, and `plasma` package components. Native MATE produced `marco` plus top/bottom panel windows on `:1`; Native Plasma produced KWin, `plasmashell`, desktop, and panel windows on `:1`. Native Cinnamon started the shell and applet manager, but no panel window was verified. Native LXQt still fails startup, and Native GNOME is not packaged by Termux. Native `:1` off-screen OpenGL drew through llvmpipe (`render_verified:true`, `accelerated:false`, score 98); Vulkan enumeration found no valid GPU. No Native Adreno-accelerated workload is verified. See [Native Freedreno runtime recheck](2026-10-25-native-freedreno-runtime-recheck.md).


## 2026-10-25 live recheck — Native, standalone, nested

A Native full MATE/Cinnamon/Plasma transaction previewed 310 new packages with no upgrades/removals. APT initially returned nonzero because the Codex-launched process inherited a foreign `LD_LIBRARY_PATH`, so Termux `ffmpeg`/`libplacebo` loaded the wrong C++ runtime. Re-running `dpkg --configure -a` with that variable unset configured the transaction; Debian and Native `dpkg --audit` are clean. The Ternuxx package apply now unsets that foreign path for APT/dpkg, and Native desktop starts explicitly use `$PREFIX/lib` (or the selected Ternuxx graphics prefix followed by `$PREFIX/lib`).

Native `:1` checks: XFCE was restored as the live default; MATE window-tree showed `marco` and top/bottom panels; Plasma showed KWin, `plasmashell`, desktop, and panel windows after the loader-path fix. Cinnamon's shell and applet manager started, but its window tree did not show a panel; this is incomplete, not a pass. Native LXQt had failed earlier and remains unaccepted. `gui_visible` remains unknown because this runtime has no screenshot/Android visibility channel.

Debian standalone `:0`: XFCE window tree showed `xfwm4`, `xfdesktop`, and `xfce4-panel`; GLX reported Zink/Vulkan on Adreno 825 Turnip and `Accelerated: yes`. GNOME showed `gnome-session-failed`; Plasma stayed at `ksplash`; Cinnamon had no verified panel. Debian nested `:2`: XFCE window tree showed `xfwm4`, desktop, and panel through Xephyr while Native `:1` stayed up; the nested context string was Zink/Turnip Adreno 825. Nested session cleanup removed its display socket. GNOME/Plasma/Cinnamon have earlier failed nested attempts and are not accepted there.

Native graphics remains unaccelerated: `tx mng graphics verify native opengl --json` drew off-screen using `llvmpipe`, `accelerated:false`, score 98; Vulkan returned no valid GPU. PRoot renderer strings and the standalone `:0` GLX accelerated flag do not establish a currently presented full-desktop app workload.


Latest standalone `:0` rerun after the session-cleanup trap changes did not reproduce the earlier XFCE pass: the launcher returned, but state reconciliation recorded `status: stopped` with `xfce session exited with status 0`; `xwininfo` could not connect to `:0`, and no new window-tree acceptance was available. The older passing standalone run remains historical evidence, while repeatability of the current standalone launcher is unresolved. Native XFCE was confirmed running on `:1`, and nested `:2` was absent after its cleanup.

A second controlled standalone `:0` retry after restoring Native XFCE showed the same immediate exit (`xfce session exited with status 0`); the immediate status query found `stopped`. The host lacks `xwininfo`, so this retry could not inspect a root window tree. Native XFCE was restarted and verified running on `:1` afterward. This confirms the standalone acceptance is currently non-repeatable and unresolved.

A startup-integrity fix now keeps the supervisor state at `starting` until its exact owned launcher survives a two-second stabilization check. A short-lived launcher is recorded as `failed` and its owned X11 process group is cleaned up, rather than briefly advertising `running`. The regression is covered by `test_clean_exit_during_stabilization_is_not_reported_running`. On-device standalone XFCE `:0` now fails closed with `desktop launcher exited before startup stabilization`; this confirms the prior false-positive status was removed but the guest session's clean exit remains unresolved. Native XFCE was restored and verified running on `:1`.

## 2026-10-25 follow-up: nested `:2` and standalone `:0`

The latest standalone Debian XFCE `:0` run passed after fixing the inline guest-shell signal-trap quoting: the session stayed alive, the same-user guest `xwininfo -root -tree` showed XFCE session, window manager, panel and desktop windows, and `tx pgui graphics verify` reported a Zink/Vulkan GLX renderer on Adreno 825 Turnip plus GLES context and Vulkan device enumeration. These probes establish a live X11 window tree and renderer/device selection; they do not establish Android presentation or a rendered application workload. The standalone session was stopped and Native XFCE was restored on `:1`.

A fresh nested Debian XFCE run on Xephyr `:2` also exposed `xfce4-session`, `xfwm4`, `xfce4-panel`, `xfdesktop`, and Thunar in the guest-user `xwininfo -root -tree` output. The Native `:1` supervisor and XFCE remained live. The nested startup command's terminal handle was unavailable for an orderly attached-session interrupt, so its exact Ternuxx-owned process group received SIGTERM; `DISPLAY=:2 xdpyinfo` then failed and no Xephyr/guest desktop process remained. A stale `:2` socket artifact remains, and status correctly reports only socket presence rather than claiming an owned live display. No GPU probe was captured during this particular nested run; the prior dated nested graphics probe above remains separate evidence. `gui_visible` remains unknown without Android screen inspection.

### Standalone `:0` all-installed-desktop recheck after the launcher fix

Native XFCE was temporarily stopped for the standalone route tests and restored on `:1` afterward. On `:0`, XFCE again exposed its complete session/window-manager/panel/desktop tree. GNOME again displayed `gnome-session-failed`; Plasma exposed only `ksplash` without a shell/panel; Cinnamon kept its session manager and settings daemons alive but had no Cinnamon shell, panel, or window manager in the X11 tree. These sessions are process-live but fail full-desktop acceptance. GNOME and Plasma graphics verification still created Zink/Turnip contexts and enumerated Adreno 825; this does not alter their desktop failure or prove presented frames/application acceleration. The four launchers present inside the Debian guest were XFCE, GNOME, Plasma, and Cinnamon; LXQt, LXDE, and MATE launchers are absent from this guest and were not tested on `:0`. Native XFCE is restored and live on `:1`; standalone `:0` is stopped.

### Delayed standalone desktop readiness recheck

The `tx pgui start --mode standalone` command returns once the managed PRoot session process group is live, before every desktop shell is ready. I therefore waited for the window tree to settle before classifying the selected desktop. Plasma needed about 40 seconds before `plasmashell` created its desktop surface and a 752x56 panel window under KWin; the full shell/panel process tree then appeared. Its `tx pgui graphics verify` probe reported Zink/Vulkan GLX and GLES contexts on Adreno 825 Turnip, plus Vulkan device enumeration; this still is not a drawn app workload or Android presentation proof. GNOME continued to show `gnome-session-failed` after a 25-second wait. Cinnamon's `cinnamon` shell/Muffin, Nemo desktop surface, and applet manager became active after a longer wait, but no panel window appeared in `xwininfo`; classify Cinnamon as partial, not a full desktop pass. XFCE again passed its session/WM/panel/desktop tree. These observations cover the four Debian launchers installed in this guest; LXQt, LXDE and MATE launchers are absent. Native XFCE was restored and verified live on `:1`; standalone `:0` is stopped. `gui_visible` remains unknown without a screenshot/Android visibility channel.

## 2026-10-25 17:10 UTC route recheck: Native `:1`, nested `:2`, standalone `:0`

The Debian guest still has exactly four launchers under `/usr/bin`: XFCE (`startxfce4`), GNOME (`gnome-session`), Plasma (`startplasma-x11`), and Cinnamon (`cinnamon-session`). LXQt, LXDE, and MATE are not installed in this guest and were not included in the `:0` desktop run.

Native XFCE was live on `:1` before and after the standalone run. `DISPLAY=:1 ./tx mng graphics status native --json` reported OpenGL and GLES context renderer `llvmpipe (LLVM 21.1.8, 128 bits)`, OpenGL `accelerated: false`, and Vulkan unavailable. `DISPLAY=:1 ./tx mng graphics verify native opengl :1 --json` completed a bounded off-screen draw through llvmpipe (`render_verified: true`, `accelerated: false`, score 126). This verifies the software draw path, not Adreno acceleration. `gui_visible` remains `unknown` because no Android screenshot/visibility interface is available in this runtime.

The current nested `:2` check could not start safely. `DISPLAY=:2 xdpyinfo` failed, the display helper reported `busy`, and `tx pgui start --mode nested --desktop xfce` refused with `Nested Xephyr display :2 is unknown; refusing startup because existing display ownership cannot be verified.` The X2 socket remains present, but no exact live owner could be established; `/proc/net/unix` access was denied. The socket was preserved and no nested process was started or signaled. Prior nested XFCE window-tree acceptance remains historical evidence, not a fresh pass for this recheck.

On standalone `:0`, all four installed desktop launchers started and `tx pgui graphics verify` created GLES/GLX contexts reporting `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`; Vulkan enumeration reported Adreno 825 Turnip and llvmpipe. These probes do not show that each desktop rendered an application workload or that Android presented the frame.

- XFCE: after 40 seconds, `xwininfo -root -tree` showed `xfce4-session`, `xfwm4`, `xfce4-panel`, and the `xfdesktop` Desktop surface; full process/window-tree acceptance passed.
- GNOME: after 40 seconds, the X tree showed `gnome-session-failed`; full desktop acceptance failed despite a live `gnome-session` process and successful renderer-context probes.
- Plasma: the first 40-second capture had KWin and `plasmashell` processes but no panel/desktop surface. A fresh run waited 75 seconds; its tree then showed KWin, `plasmashell`, a 752x56 panel, and a 752x1630 desktop surface. Full process/window-tree acceptance passed only after this longer startup delay.
- Cinnamon: after 40 seconds, the tree showed Cinnamon/Muffin, Nemo's Desktop surface, and Cinnamon helpers, but no panel window. This remains partial, not a full desktop pass.

All standalone `:0` sessions were stopped after inspection, and Native XFCE was restored and verified running on `:1`; standalone `:0` remained stopped. The initial test harness cleanup tried to redirect logs into an unwritable `/tmp` path and did not run its restore command; after detecting that, Native XFCE was started manually and its live status was verified before continuing. No guest was deleted or reconfigured, no password was used, and the `:2` socket was untouched.

## 2026-10-25 17:19 UTC nested `:2` stale-lock recovery and live recheck

The previously blocked nested route was traced to an exact PRoot `--link2symlink` lock chain: Native `$PREFIX/tmp/.X2-lock` pointed into the installed Debian rootfs `.l2s` directory, the two generated symlink names led to one regular lock file containing PID `7301`, `/proc/7301` was absent, and connecting to the X2 socket returned `ECONNREFUSED`. No matching process held the socket inode, and no Xephyr/guest desktop process was running. A narrow helper now recognizes and reclaims only this exact dead-PID chain when the entire path remains under that Debian `.l2s` directory and the X socket still refuses connections. It leaves active PIDs, listening sockets, unrecognized chains, and files outside the guest untouched. Unit fixtures cover each refusal boundary.

`tx pgui start --mode nested --desktop xfce` recovered the stale lock/socket artifacts without signaling a process, then started Xephyr `:2` at `752x1630` while Native XFCE remained live on `:1`. The Native `:1` X root tree showed the Xephyr window. Inside Debian, `xwininfo -root -tree` showed `xfce4-session`, `xfwm4`, `xfce4-panel`, `xfdesktop`, and Thunar; full nested XFCE process/window-tree acceptance passed.

With the same `GALLIUM_DRIVER=zink`, `MESA_LOADER_DRIVER_OVERRIDE=zink`, `TU_DEBUG=sysmem,noconform`, and `MESA_VK_WSI_DEBUG=sw` environment passed to the nested session, GLES context creation reported `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`. Vulkan enumeration listed Adreno 825 Turnip and llvmpipe; `vkcube --gpu_number 0 --c 120` selected Adreno 825 and exited 0. This is a bounded Vulkan draw on the selected Adreno device in the nested X session. It does not establish sustained performance or Android frame presentation. With no explicit Zink override, a separate diagnostic instead reported llvmpipe, confirming that the environment handoff changes the selected GLES renderer.

Nested GLX did not initialize: `glxinfo -B` returned `Error: couldn't find RGB GLX visual or fbconfig`, and Xephyr logged DRI3 unavailable. Therefore no nested GLX/XFCE-wide acceleration is claimed. The attached nested command was closed with Ctrl-C (exit 130); afterward `tx pgui status` reported `:2` socket absent, the X2 lock/socket were absent, no nested process remained, Native `:1` was still live, and standalone `:0` was stopped. Android visual presentation remains unverified.

## 2026-10-25 17:36 UTC fresh route matrix: standalone `:0`, nested `:2`

Native XFCE was running on `:1` at entry. I temporarily stopped only the recorded Native desktop to run Debian standalone tests on `:0`, then restored Native XFCE. The guest has four installed launchers: XFCE, GNOME, Plasma, Cinnamon; LXQt, LXDE, MATE are absent.

Standalone `:0`: XFCE passed after the delayed check; the guest-user X tree showed `xfce4-panel` windows (752x27 top and 306x49 bottom), a 752x1104 `xfdesktop` surface and `xfwm4`. `tx pgui graphics verify --json` created GLES and GLX contexts reporting Zink/Vulkan on Adreno 825 Turnip and enumerated Adreno 825 plus llvmpipe; this run did not draw an app workload. GNOME showed the full-screen `gnome-session-failed` window after 25 seconds. Plasma started `startplasma-x11`/`plasma_session` and created `plasmashell` desktop surfaces, but no panel window was verified during this run; classify partial. Cinnamon started its session, Cinnamon/Muffin and Nemo desktop surface, but no panel window appeared; classify partial. These are desktop-tree observations, not Android presentation proof.

Nested `:2` through Native `:1`: XFCE passed after a delayed check; `xwininfo` showed top/bottom panel windows, the desktop surface, and `xfwm4`. The startup GLES context reported Zink/Vulkan Adreno 825 Turnip. With that session's configured Zink environment, `timeout 20s vkcube --gpu_number 0 --c 120` selected Adreno 825 and exited 0. Xephyr reports DRI3 unavailable; nested GLX is not verified. GNOME showed `gnome-session-failed` after 18 seconds. Plasma remained in `startplasma-x11`/`plasma_session` waiting for KSplash; KWin and plasmashell desktop surfaces did not appear, and logs reported GLX initialization failure. Cinnamon's session manager/settings daemons started, but `cinnamon.desktop` failed to register; its launcher reported a missing fallback and PRoot later reported `fork: Function not implemented` while the test was being interrupted. No nested Cinnamon desktop was accepted. After the test, the exact Debian `.l2s` stale `:2` lock/socket chain left by the interrupted process was recovered by the guarded launcher; it did not signal any process. A final nested XFCE run passed and Ctrl-C removed its socket/lock cleanly.

Final live state: Native XFCE on `:1` running; standalone `:0` stopped; nested `:2` absent; `tx proot sessions list` empty. `gui_visible` remains unknown because this runtime has no Android screenshot/visibility channel. No password was used.


## 2026-10-25 18:04 UTC follow-up: all installed desktops on nested `:2` and standalone `:0`

I repeated the desktop checks against the current Debian guest and current launcher code. Its supported, fully installed desktop set is XFCE, GNOME, Plasma, and Cinnamon; LXQt, LXDE, and MATE are not installed in this guest. The guest-only `PATH` in both the nested and standalone launchers was active during these tests (`/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`), so missing guest programs could not silently fall through to Termux host binaries.

Nested `:2`, with Native XFCE kept live on `:1`:

- XFCE passed: after startup, the guest-user `xwininfo -root -tree` showed `xfce4-session`, `xfwm4`, both `xfce4-panel` windows, and the `xfdesktop` surface. GLES startup context reported Zink/Vulkan on Adreno 825 Turnip. Xephyr continued to report DRI3 unavailable; nested GLX is not accepted.
- GNOME failed: the root tree showed the full-screen `gnome-session-failed` window; its log reported no hardware 3D support from GNOME's acceleration check.
- Plasma failed full-session acceptance: `startplasma-x11` and `plasma_session` remained alive, but KWin and `plasmashell` did not appear in the process tree after 45 seconds. Logs reported GLX configuration failure and `Could not initialize GLX`, even with the X11 `kwin-x11` package installed and the nested no-compositor environment setting.
- Cinnamon failed: the root tree showed `Cinnamon just crashed`; the session manager stayed alive, but the Cinnamon shell did not. `cinnamon-launcher`'s fallback executable was absent from the isolated Debian guest PATH.

Standalone `:0` (Native `:1` was stopped only for these checks and restored afterward):

- XFCE passed: the guest-user root tree showed `xfce4-session`, `xfwm4`, top and bottom panel windows, and the desktop surface.
- GNOME failed: the full-screen `gnome-session-failed` window remained after 30 seconds, alongside the same acceleration-check warning.
- Plasma was partial: after 55 seconds, KWin, `ksmserver`, and `plasmashell` processes were live, but the root tree showed a full-screen `kscreenlocker_greet` and no panel or desktop surface. This is not a usable full-desktop pass.
- Cinnamon was partial: Cinnamon/Muffin and Nemo's desktop surface were live, but no panel window appeared. The log showed Cinnamon applet errors; no usable full-desktop pass is claimed.

Each standalone `tx pgui graphics verify` run created GLES and GLX contexts reporting Zink/Vulkan Adreno 825 Turnip and enumerated Adreno 825/llvmpipe devices. These are context/device probes only; no per-desktop application draw or Android frame presentation was verified. The focused GUI/catalog/setup suite passed 25/25 tests; `git diff --check` passed. Native XFCE was restored and verified live on `:1`; standalone `:0` and nested `:2` are stopped, `tx proot sessions list` is empty, and `gui_visible` remains unknown.

## 2026-10-25 18:24 UTC: Plasma nested-startup isolation

A focused nested Plasma investigation ran only on `:2` inside the live Native XFCE `:1`. A temporary trial changed only the Plasma bus launcher from `dbus-launch` to `dbus-run-session`; it produced the same result and was reverted. Another temporary pre-start of `kded6` plus `KDEWM=/usr/bin/xfwm4` failed because `kded6` aborted before registering, so that workaround was also removed. No temporary launcher or package changes remain.

The `dbus-run-session` run logged repeated failures to activate `org.freedesktop.systemd1`; `startplasma-x11` then launched the legacy `plasma_session` path. `kcminit_startup` exited 0, but after 35 seconds the only Plasma session processes were `startplasma-x11` and `plasma_session`; there was no KWin, KSMServer, Plasma shell, or panel/desktop surface. In a separate guest process, `kded6` did acquire `org.kde.kded6` on that same session bus, but Plasma still did not advance. Therefore the missing systemd service is confirmed as an unavailable capability and the session hang is confirmed, while the exact internal blocking step remains unresolved.

The installed Debian Plasma source documents `plasma_session` as the non-systemd fallback and sequences KCM init, `kded6`, the X11 window manager, and KSMServer in order: [Plasma startup notes](https://sources.debian.org/src/plasma-workspace/4%3A6.3.6-2/startkde/README.md/) and [startup.cpp](https://sources.debian.org/src/plasma-workspace/4%3A6.3.6-2/startkde/plasma-session/startup.cpp/). This source matches the observed transition from completed KCM init to the absent window-manager process, but does not alone identify why that job stalls in this PRoot session. No Plasma pass is claimed.

The experiment was stopped cleanly. Final state: Native XFCE `:1` running; nested `:2` absent; standalone `:0` stopped; managed PRoot sessions empty.

## 2026-10-25 18:32 UTC fresh live matrix: nested `:2` and standalone `:0`

I retested all four desktop launchers installed in the Debian guest. Nested sessions ran through Xephyr `:2` while Native XFCE stayed live on `:1`. For the standalone matrix, I stopped only the Ternuxx-owned Native desktop, ran each managed PRoot desktop on `:0`, then stopped the guest session and restored Native XFCE. I waited for slow desktop startup before classifying it and queried the Debian user's X root tree.

Nested `:2` results:

- XFCE passed on the final delayed recheck: `xfce4-session`, `xfwm4`, `xfce4-panel`, and `xfdesktop` were live; the X tree showed the 752x27 top panel, 306x49 bottom panel, and 752x1579 desktop surface. Xephyr startup reported a Zink/Vulkan GLES context on Adreno 825 Turnip. DRI3 remained unavailable; nested GLX is not established.
- GNOME failed: the full-screen `gnome-session-failed` window remained after startup; no usable GNOME shell was verified.
- Plasma failed: after about 35 seconds, only `startplasma-x11` and `plasma_session` remained. KWin, KSMServer, `plasmashell`, panel, and desktop surfaces did not appear; logs again showed GLX setup failures.
- Cinnamon failed: the X tree showed the `Cinnamon just crashed` dialog; no Cinnamon shell or panel was present.

Standalone `:0` results:

- XFCE passed: `xfce4-session`, `xfwm4`, `xfce4-panel`, and `xfdesktop` were live; the X tree showed the 752x27 top panel, 306x49 bottom panel, and 752x1630 desktop surface.
- GNOME failed: the full-screen `gnome-session-failed` window remained after 18 seconds; no usable GNOME shell was verified.
- Plasma passed after a slow startup (about 45 seconds): KWin, KSMServer, and `plasmashell` were live; the X tree showed a 752x56 panel and 752x1630 desktop surface.
- Cinnamon remained partial: Cinnamon and Nemo were live and the X tree showed Nemo's 752x1590 desktop surface, but no panel appeared.

The nested launcher printed a Zink/Vulkan Adreno 825 Turnip GLES context string. This confirms context/device selection only; this run did not measure application rendering or Android frame presentation. `gui_visible` remains unknown. Native XFCE was restored and verified running on `:1`; `:0` and `:2` were stopped/absent afterward, and `tx proot sessions list` was empty. No package install, guest reset, or password entry occurred.

## 2026-10-25 18:53 UTC complete Debian catalog matrix: nested `:2` and standalone `:0`

I installed the three remaining catalog environments on the existing Debian guest from an exact preview. The preview for `lxqt,lxde,mate` listed 133 new packages, 87.7 MB download and 378 MB installed size, with no upgrades/removals. The APT run was interrupted after several minutes without terminal progress; its exact failed-plan journal was retained. An exact `desktop-resume-preview`/apply configured 119 pending packages and repaired one archive, after which `dpkg --audit` was clean. A fresh preview then offered the remaining 21 packages for `lxqt,mate` (198 MB installed size, zero upgrades/removals); that apply completed. `lxde` was already fully installed by the recovery. The final guest inventory reports all seven catalog environments installed, and `dpkg --audit` is clean.

All seven environments were tested on both routes. “Pass” means the selected session, window manager, panel, and desktop surface appeared in the X window tree; partial does not count as usable full-desktop acceptance.

| Debian desktop | Nested through Native `:1` to Xephyr `:2` | Standalone `:0` |
|---|---|---|
| XFCE | Pass: XFCE session, WM, top/bottom panels, desktop | Pass: XFCE session, WM, top/bottom panels, desktop |
| LXQt | Fail: `lxqt-session` plus Welcome dialog only; `LockScreenManager` could not start | Fail: same Welcome-only state; no verified WM/panel/desktop |
| LXDE | Pass: LXSession, Openbox, 752x26 panel, PCManFM desktop | Pass: same complete session tree and desktop surface |
| MATE | Pass: MATE session, Marco, top/bottom panels, Caja desktop | Pass: same complete session tree and desktop surface |
| GNOME | Fail: full-screen `gnome-session-failed` | Fail: full-screen `gnome-session-failed` |
| KDE Plasma | Fail: after 35 seconds, only `startplasma-x11`/`plasma_session`; no KWin or shell | Pass after about 45 seconds: KWin, KSMServer, `plasmashell`, 752x56 panel, desktop surface |
| Cinnamon | Fail: `Cinnamon just crashed`; no shell/panel | Partial: Cinnamon/Muffin and Nemo desktop surface, no panel |

Nested sessions continued to report Zink/Vulkan Adreno 825 Turnip GLES context selection. This is not proof of rendered application frames or Android presentation. Standalone graphics probes were not repeated in this added three-desktop run. `gui_visible` remains unknown. Final state was verified: Native XFCE running on `:1`, standalone `:0` stopped, nested `:2` socket absent, managed guest-session list empty, and Debian `dpkg --audit` clean. No guest reset or password entry occurred.
