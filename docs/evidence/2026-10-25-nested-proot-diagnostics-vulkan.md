# Nested PRoot diagnostic workload recheck — 2026-10-25 UTC

At 2026-10-25 23:37 UTC, Native XFCE was running on `:1`, standalone PRoot `:0` was stopped, and nested `:2` was absent. `tx pgui start --mode nested --desktop xfce` started the existing Debian guest in Xephyr `:2`; the Native `:1` desktop remained active.

The updated shared verifier ran its bounded Vulkan probe as part of:

```sh
./tx proot verify --distro debian --guest-user sobuj --display :2 --backend zink
```

The probe selected `Adreno (TM) 825, type: IntegratedGpu` and returned `vulkan_draw: verified`. X11 and the Native PulseAudio endpoint were reachable (`tcp:127.0.0.1:4713`, sink `OpenSL_ES_sink`). The same report returned `glx_draw: failed`, zero GLX frames, `dri3_extension: unavailable`, and `gles_draw_verified: false`; overall status correctly remained `partial`. This verifies a bounded Vulkan draw/presentation workload for `vkcube` in the nested guest, not GLX/GLES rendering, XFCE compositing, visible-window contents, audio playback, sustained stability, or inference.

The diagnostic declares `probe_payload_read_only: true`, but also `read_only: false` and `launcher_profile_write_possible: true` because guest login may touch startup/profile state. It reported no guest write command, package change, or service lifecycle action. Ctrl-C closed only this test's nested session. A follow-up `tx pgui status` showed Native `:1` still running, `:2` absent, and standalone `:0` stopped. No guest packages, rootfs data, desktop selection, Native graphics preference, Android setting, or owner-managed service was changed.
