# Nested Debian graphics recheck — 2026-10-25

The current Native XFCE was running on `:1`; standalone Debian GUI was stopped, and the nested `:2` socket was absent. The existing Debian Trixie guest (`sobuj`, passwordless sudo receipt) was left in place.

A read-only `proot-distro login` probe on Native display `:1`, with the guest's configured Zink/Turnip variables and KGSL/DRM binds, reported `OpenGL renderer string: zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))`, `Accelerated: yes`, Vulkan Adreno 825 Turnip devices, and the same renderer in `es2_info`. That checks a guest process on the Native X server, not a running guest desktop.

Then `tx pgui start --mode nested --desktop xfce` launched the actual Debian XFCE session through Xephyr `:2`, while Native XFCE remained running on `:1`. The guest startup line reported a GLES context renderer `zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))`. With `DISPLAY=:2`, `es2_info` reported the same GLES renderer; `vulkaninfo --summary` enumerated Adreno 825 / Turnip; and bounded `vkcube --c 120` selected `Adreno (TM) 825` and exited 0.

The same nested Xephyr display reported `DRI3 not available`, and `glxinfo -B` failed with `couldn't find RGB GLX visual or fbconfig`. Therefore this run verifies a GLES context and a Vulkan sample draw in the guest process, but does not verify an accelerated GLX renderer, the XFCE compositor, all desktop surfaces, or what XFCE's About screen displays. The native Termux/Bionic XFCE continues to report `llvmpipe`; the guest's Turnip route is separate.

The nested session was closed with Ctrl-C. Follow-up status found the nested display socket absent and no PRoot processes. The test-created private per-desktop XDG directory under `/home/sobuj/.local/share/ternuxx/proot-nested-gui/xfce` was removed after confirming it did not exist before the test. No guest packages, desktop selection, or saved Native graphics backend were changed. The test exposed and fixed two startup issues: nested XDG `config` was chmodded before creation, and compact Floating Termux:X11 dimensions (`280x403`) were rejected by the geometry guard.
