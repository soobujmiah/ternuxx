# Nested Debian desktop render follow-up — 2026-10-25 UTC

This check used the existing installed Debian Trixie guest and preserved the Native XFCE session on `:1`. Before launch, `tx proot status --json` showed only the existing `debian` alias and no managed PRoot sessions; `tx pgui status` showed standalone `:0` stopped and nested `:2` absent.

`tx pgui start --mode nested --desktop xfce` launched the existing guest's XFCE inside Xephyr `:2`, with Native display `:1` left running. The guest startup reported a GLES context renderer `zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))`. The shared read-only guest diagnostic (`tx proot verify --distro debian --guest-user sobuj --display :2 --backend zink`) reported X11 reachable, GLES context verified with that renderer, and Native PulseAudio reachable at `tcp:127.0.0.1:4713` with default sink `OpenSL_ES_sink`. It reported `DRI3 unavailable`, GLX draw failed with zero frames, and `gles_draw_verified: false`; the result was `partial` with blocker `GLX renderer unavailable; GLES context does not verify a draw`.

While that exact nested display was live, a bounded guest workload ran:

```sh
env -u LD_LIBRARY_PATH -u LD_PRELOAD "$PREFIX/bin/proot-distro" login debian --shared-tmp --user sobuj --env DISPLAY=:2 --env GALLIUM_DRIVER=zink --env MESA_LOADER_DRIVER_OVERRIDE=zink --env TU_DEBUG=sysmem,noconform --env MESA_VK_WSI_DEBUG=sw -- /usr/bin/vkcube --c 120
```

It selected WSI platform `xcb`, selected `Adreno (TM) 825` as GPU 0 (`IntegratedGpu`), and exited 0. This is bounded Vulkan swapchain/draw evidence for the nested guest process on this run. It does not establish GLX acceleration, GLES draw acceleration, XFCE compositor acceleration, every application's rendering, sustained stability, inference offload, or visual visibility in the Android X11 window. The device UI was not captured.

Ctrl-C closed only the nested session started by this check. Follow-up status showed Native XFCE still running on `:1`, nested socket absent, standalone `:0` stopped, and `tx proot sessions list --json` empty. No package, rootfs, desktop selection, Native graphics preference, Android setting, or owner service was changed. The XDG session directory is Ternuxx-managed runtime state under the guest user's home.
