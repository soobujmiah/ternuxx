# Debian guest workload on Native display `:1` after cleanup — 2026-10-26

At about 12:59 UTC, with Native XFCE and Native PulseAudio running, the bounded guest verifier ran:

```sh
tx proot verify --distro debian --guest-user sobuj --display :1 --backend zink
```

It returned `status=complete`, `blockers=[]`, and:

- X11 reachable on `:1`.
- Zink/Turnip GLES context: `OpenGL ES 3.2 Mesa 25.0.7-2+deb13u1`, renderer `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`; `gles_draw_verified=false`.
- GLX draw verified: 837 frames; renderer Zink/Turnip Adreno 825.
- Vulkan draw verified on `Adreno (TM) 825, type: IntegratedGpu`.
- Authenticated Native PulseAudio endpoint available; server `pulseaudio`, default sink `OpenSL_ES_sink`.

The result reports `probe_payload_read_only=true` but overall `read_only=false`, with `launcher_profile_write_possible=true` and `profile_owner=unverified`. Its observed safety fields say no guest write command, package change, service start/stop, or host lifecycle start/stop occurred. Do not treat this diagnostic as proof that proot-distro launcher-profile state was unchanged or that the guest is owned by Ternuxx.

Follow-up lifecycle checks found Native XFCE live on `:1`, Native audio running, PRoot standalone `:0` stopped, nested `:2` absent, and no managed PRoot sessions. Android window visibility, GLES drawing, audible playback, and profile ownership remain unverified.
