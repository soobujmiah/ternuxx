# Debian standalone render follow-up — 2026-10-26

At 11:24 UTC, Native XFCE was live on `:1`; standalone `:0` and nested `:2` were stopped, and the installed Debian guest was present. With the owner's approval, `tx stop` stopped the recorded Native desktop, then `tx pgui start --mode standalone --desktop xfce` launched the existing Debian XFCE process group on `:0`.

`tx pgui graphics verify` reported GLES 3.2 Zink/Vulkan on `Adreno (TM) 825 (MESA_TURNIP)`, direct GLX rendering with the same renderer, and Vulkan enumeration of Adreno 825 Turnip plus llvmpipe. The shared guest verifier reached X11 and Native PulseAudio (`tcp:127.0.0.1:4713`, `OpenSL_ES_sink`); its bounded Vulkan XCB draw selected Adreno 825 and passed. GLES drawing was not verified, and the bounded GLX draw failed with zero frames, so the result was `partial`. `tx pgui status` confirmed a live process group but did not verify the XFCE panel/window tree or Android visibility.

Cleanup stopped only the verified standalone session and restarted Native XFCE. Final status showed Native `:1` running, standalone `:0` stopped, nested `:2` absent, and no managed PRoot sessions. Native audio remained available. No package, guest, or saved graphics configuration changed.

## Delayed standalone rerun (about 11:31 UTC)

A second approved run stopped Native `:1`, launched Debian XFCE on `:0`, and waited 20 seconds before probing. `tx proot verify --distro debian --guest-user sobuj --display :0 --backend zink` returned `complete`: X11 and Native PulseAudio endpoint were reachable; GLX drew 623 frames on Zink/Turnip Adreno 825; Vulkan XCB drawing selected Adreno 825. GLES context creation succeeded, but GLES drawing remained unverified. `tx pgui graphics verify` confirmed the GLES/GLX renderer and enumerated Adreno 825 Turnip plus llvmpipe; it does not itself draw frames. Native-host `xwininfo` was unavailable, so this rerun did not inspect the desktop window tree or panel. The earlier immediate probe's zero-frame GLX result and this delayed pass suggest startup timing may affect the verifier, but the cause was not isolated. Android visibility and audible playback remain unverified.

Afterward, only the verified standalone `:0` session was stopped and Native XFCE was restored on `:1`. Final status showed `:1` running, `:0` stopped, `:2` absent, no managed PRoot sessions, and Native audio still available.
