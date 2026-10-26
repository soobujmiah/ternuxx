# Ubuntu Noble managed install and route qualification

## Install result

The exact pinned preview installed a new canonical `ubuntu` PRoot alias for `sobuj` using the Ternuxx Ubuntu Noble manifest and the `20261001T000000Z` signed package snapshot. It selected XFCE and installed the Ternuxx guest base, Mesa/Zink, Vulkan tools, PulseAudio client tools, and Xephyr. The install receipt records the package inventory and Turnip setup; runtime qualification is recorded separately below. Existing canonical Debian and the retained Debian replay alias were not modified.

The first apply completed the package phase but stopped at the post-install distro identity check because Ubuntu's standard `/etc/os-release -> ../usr/lib/os-release` symlink was rejected. The in-root target was inspected and matched `ID=ubuntu` and `VERSION_CODENAME=noble`. Source now resolves the target only when it remains within the verified rootfs and rejects an external symlink; regression tests cover both cases. The exact failed install journal was resumed, without replacing the rootfs, and completed. A second integration issue used an inconsistent Ubuntu profile ID in the receipt; new receipts use the stable manifest profile ID, while verification also accepts the short ID already present in this completed guest. The canonical Ubuntu install receipt supplies the guest username to the launcher, avoiding ambiguous account detection among Ubuntu's system accounts.

## Live display and graphics results

The Native XFCE desktop was running on `:1` before the Ubuntu tests and is running there again now. The Ubuntu XFCE nested session started on Xephyr `:2` while Native `:1` remained active. `xwininfo` listed `xfce4-session`, `xfce4-panel`, `xfdesktop`, `xfwm4`, and Thunar windows in the 752x1104 Xephyr root. `tx proot verify --distro ubuntu --guest-user-from rootfs --display :2 --backend zink` returned `partial`: X11 and Native PulseAudio were reachable, the GLES context identified Zink/Vulkan on Adreno 825, and a bounded Vulkan draw completed on Adreno 825. GLX draw failed because DRI3 is unavailable on this Xephyr route; a bounded `es2gears_x11` attempt also reported that DRI3 was unavailable. GLES drawing and Android foreground presentation were not verified.

For standalone `:0`, Native XFCE was stopped through its recorded Ternuxx lifecycle, Ubuntu XFCE was started with `tx pgui`, and the guest root window listed the XFCE session, panel, desktop, window manager, and Thunar. The guest verifier returned `complete`: 470 GLX frames rendered on Zink/Turnip Adreno 825, Vulkan drawing completed on Adreno 825, the GLES context identified the same renderer, and Native PulseAudio was reachable. Android foreground visibility and audible playback remain unknown. Ubuntu's guest verifier also returned `complete` while targeting Native display `:1` (498 GLX frames, Adreno 825 Vulkan draw, and reachable audio endpoint).

The standalone session was stopped through `tx pgui stop`, then Native XFCE was restarted and verified on `:1`. Final live state: Native XFCE `:1` running; Ubuntu standalone `:0` stopped; nested `:2` absent; no managed PRoot GUI session active. The existing Debian guest remains intact.

## Source checks and boundaries

Focused fresh-setup, diagnostics, PRoot-session, and launch tests passed (120 tests). Python compilation, shell syntax checks, and `git diff --check` passed. The source updates cover safe release identity handling, canonical guest user resolution, receipt profile IDs, and distro-neutral launcher text.

Ubuntu is live-qualified for standalone XFCE `:0` and guest workloads directed at Native `:1`. Nested XFCE `:2` starts and exposes its desktop windows, and its Vulkan workload is hardware-backed, but Xephyr GLX/DRI3 remains partial. No other distro is advertised as supported. These results do not establish Android Activity foreground visibility or audible playback.
