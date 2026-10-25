# PRoot desktop route requalification — 2026-10-26

## Accepted route matrix

The live Debian guest is the pinned Trixie installation for `sobuj`. Native Termux XFCE is the host/control plane on `:1`; PRoot standalone sessions use `:0`, and nested sessions use Xephyr `:2` inside `:1`. A route pass here means the selected session manager, window manager, and panel/desktop process appeared on the target X server. It does not claim Android Activity visibility, audible output, or full application acceptance.

| Debian desktop | Standalone `:0` | Nested `:2` | Current launch policy |
|---|---|---|---|
| XFCE | Pass | Pass | `auto`, standalone or nested |
| LXQt | Pass | Pass | `auto`, standalone or nested |
| LXDE | Pass | Pass | `auto`, standalone or nested |
| MATE | Pass | Pass | `auto`, standalone or nested |
| KDE Plasma | Pass; delayed startup, verified KWin and panel | Failed in prior nested checks | standalone only |
| GNOME | Failed | Failed | Install-catalog metadata only; no accepted launch route |
| Cinnamon | Failed/partial | Failed | Install-catalog metadata only; no accepted launch route |

For XFCE, LXQt, LXDE and MATE, both route checks observed the session manager, window manager and panel/desktop process, plus `_NET_SUPPORTING_WM_CHECK` on the display. Nested Xephyr printed DRI3 warnings; LXQt reported its lock-screen manager unavailable, and MATE reported missing systemd/logind and acceleration-check services. Their desktop session, window manager and panel still started. Plasma standalone was rechecked after its exact package reinstall: at 40 seconds, `startplasma-x11`, `kwin_x11`, `ksmserver` and `plasmashell` were live; `_NET_SUPPORTING_WM_CHECK` identified KWin and `xwininfo -root -tree` showed the 752x56 Plasma panel and desktop windows.

## Graphics checks

Standalone XFCE `:0` and Plasma `:0` reported GLES 3.2 and GLX Zink on `Adreno (TM) 825 (MESA_TURNIP)`; GLX reported direct rendering. Vulkan enumeration found Adreno 825 through Turnip (two loader entries) plus CPU llvmpipe. On `:0`, the bounded `vkcube --gpu_number 0 --c 120` XCB run selected Adreno 825 and exited 0. Nested XFCE `:2` reported the same Zink/Turnip Adreno GLES context; its bounded `vkcube --gpu_number 0 --c 120` XCB run also selected Adreno 825 and exited 0. The context and cube checks do not prove visible Android presentation or a sustained workload. Xephyr lacks DRI3, so nested guest GLX is not qualified.

After both temporary GUI routes were stopped, Native XFCE was restored on `:1`. The Native manager then rendered 617 GLES shader frames in five seconds on Adreno 825 and completed a 120-frame Vulkan X11 draw on Adreno 825. Native `gui_visible` remains unknown.

## Cleanup and retained package state

GNOME and Cinnamon packages were absent from the installed desktop inventory before cleanup; `gnome-shell` remained only in `config-files` state. The failed Debian Plasma package was temporarily purged while reconciling conflicting historical evidence, then restored after the later 2026-10-26 record confirmed its standalone route passed. The exact Ternuxx desktop preview installed 38 packages with no upgrades/removals (8,704 kB download, 57.2 MB disk); the final accepted Plasma route is standalone-only. The final package inventory reports XFCE, LXQt, LXDE, MATE, and Plasma. No GNOME/Cinnamon desktop is installed.

After the failed desktop roots were removed, a repeated APT simulation matched byte-for-byte before apply and purged 226 now-unused packages (459 MB freed, no install/upgrade). The Plasma exact-plan reinstall restored its 38 required packages afterward. `dpkg --audit` returned no findings, `apt-get check` exited successfully, and `tx proot setup status` still reports `fresh_installed` with the original guest identity and manifest receipt.

A preview-bound shortcut sync removed 28 obsolete GNOME/Cinnamon/KDE app launchers and created launchers for installed LXQt/MATE apps plus LXDE/LXQt/MATE desktop starts. After Plasma restoration, a second exact preview created the Dolphin app entry and standalone-only Plasma launcher. The final sync preview reports no changes and lists XFCE/LXQt/LXDE/MATE/Plasma only. Native Termux currently lists XFCE, MATE and Plasma as installed; its failed LXQt/Cinnamon packages are absent.

## Limitations and source changes

No screenshot or Android-side capture was available, so presentation/visibility is unknown. No audible audio test was performed in this check. PRoot providers other than Debian and their distro-specific package/session profiles remain unimplemented. GNOME and Cinnamon remain package catalog options for install experiments, but source now rejects launch routing and shortcut generation for them. Plasma is routed only to standalone `:0`; XFCE/LXQt/LXDE/MATE use `auto`.

Focused desktop, shortcut, route, setup, and fresh-setup tests passed 92/92 after the catalog and route changes. Full repository tests, CLI help checks, document audit, and GitHub CI remain part of the source-change validation.
