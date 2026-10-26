# Debian XFCE standalone route after desktop cleanup — 2026-10-26

At about 12:52 UTC, after removing failed/partial Debian desktop packages, the Native XFCE supervisor was stopped under the owner's previously granted temporary-test authorization. Native PulseAudio remained running. I launched the retained Debian XFCE route with:

```sh
tx pgui start --mode standalone --desktop xfce --alias debian
```

Ternuxx reported the Debian shell, window manager, panel, and desktop process checks ready on `:0`. `tx pgui graphics verify` passed and reported GLES and GLX renderer `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`; Vulkan enumeration returned two Adreno 825 Turnip devices plus the llvmpipe CPU device. This command checks contexts and device enumeration, not rendered frames.

## Bounded workload checks

For each GPU workload, the PRoot command used `DISPLAY=:0`, the Ternuxx Zink/Turnip variables, and the same KGSL/DRI device binds as the standalone launcher:

- `timeout -s TERM 8s glxgears -info` printed the Zink/Turnip Adreno 825 renderer and `819 frames in 5.0 seconds = 163.664 FPS`. The outer timeout returned 124 as intended; frame output proves a bounded GLX draw.
- `timeout -s TERM 15s vkcube --gpu_number 0 --c 120` selected Adreno 825 through XCB WSI and exited 0. The command's output did not print a frame count; no numeric count is claimed.
- `timeout -s TERM 12s es2gears_x11 -info` ran until the timeout but printed no frame metrics. GLES drawing remains unverified.

An authenticated guest `pactl info` query using the Ternuxx Native PulseAudio cookie bind succeeded. It reported PulseAudio 17.0-dirty and default sink `OpenSL_ES_sink`; cookie output was filtered. No playback sample was sent, so physical audibility remains unverified. Android foreground visibility and the guest About dialog were not inspected.

## Restore check

`tx pgui stop` returned 0 and reported that only the verified guest GUI on `:0` was stopped. `tx start --desktop xfce` then returned success. Final checks showed Native XFCE running on `:1`, Ternuxx audio running, standalone `:0` stopped, nested `:2` absent, and no managed PRoot sessions.

This verifies post-cleanup standalone XFCE process readiness, accelerated GLX drawing, Adreno Vulkan selection with a bounded cube run, and authenticated PulseAudio endpoint access. GLES draw, audible output, and Android-visible state remain open.
