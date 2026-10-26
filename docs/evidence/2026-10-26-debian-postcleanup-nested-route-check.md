# Debian XFCE nested route after desktop cleanup — 2026-10-26

At about 12:48 UTC, after removing failed/partial Debian desktop packages, I launched the retained XFCE profile with:

```sh
tx pgui start --mode nested --desktop xfce --alias debian
```

The launcher started Xephyr `:2` inside the already-running Native `:1` desktop and reported a Zink/Turnip Adreno 825 GLES context. That context line proves context creation only, not rendering or presentation.

## Results

- `xwininfo -display :2 -root -tree` exited 0. The live tree included `xfce4-session`, `xfwm4`, `xfce4-panel`, the `xfdesktop` Desktop window, and Thunar. This is a nested window-tree check; Android-level visibility was not independently observed.
- `glxinfo -B` from the Debian guest on `DISPLAY=:2` reported `llvmpipe (LLVM 19.1.7, 128 bits)`, `Accelerated: no`. No accelerated GLX draw is claimed.
- `vkcube --gpu_number 0 --c 120` selected Adreno 825 through XCB WSI, then failed with “No DRI3 support detected - required for presentation” and “Could not find both graphics and present queues”; exit status 1. Selecting the GPU did not produce a Vulkan presentation workload.
- Authenticated PulseAudio endpoint query succeeded when using Ternuxx's private cookie bind and `PULSE_SERVER=tcp:127.0.0.1:4713`. It reported PulseAudio 17.0-dirty and default sink `OpenSL_ES_sink`. The query did not play audio, so audible output remains unverified. Cookie output was excluded from the evidence.
- Sending Ctrl-C to the nested launcher closed that session only. Follow-up checks found Native `:1` available, Xephyr `:2` absent, standalone `:0` stopped, and the managed PRoot session registry empty.

Exact bounded commands used for the guest-side checks:

```sh
proot-distro login --user sobuj debian -- env DISPLAY=:2 glxinfo -B
proot-distro login --user sobuj debian -- sh -c 'DISPLAY=:2 timeout -s TERM 15s vkcube --gpu_number 0 --c 120'
# pulse_cookie is read as a path from proot_diagnostics; its contents are never printed.
proot-distro login --shared-tmp --bind "$pulse_cookie:/tmp/.ternuxx-pulse-cookie" \
  --user sobuj debian -- env DISPLAY=:2 PULSE_SERVER=tcp:127.0.0.1:4713 \
  PULSE_COOKIE=/tmp/.ternuxx-pulse-cookie pactl info | sed '/^Cookie:/d'
```

The route is therefore accepted for XFCE session/window-tree startup and authenticated PulseAudio endpoint access. Nested GPU-accelerated GLX and Vulkan presentation remain partial because Xephyr does not expose DRI3; GLES rendering and physical audio output remain unverified.
