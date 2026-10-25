# Nested Debian Vulkan smoke recheck

**Observed:** 2026-10-25 19:43 UTC  
**Device/runtime:** Native Termux on Android 16, aarch64; Debian Trixie guest; Native XFCE `:1`; Xephyr nested display `:2`.

## Procedure and result

Preflight Native thermal sensors were CPU 58.9°C, GPU 48.7°C, HTP 51.5°C, battery 42.01°C, and SoC 61.0°C. The battery API separately reported 42.0°C. Ternuxx started the existing Debian XFCE nested route with `tx pgui start --mode nested --desktop xfce`; Xephyr reported GLES Zink/Vulkan Adreno 825 Turnip context creation. DRI3-unavailable warnings were printed for the Xephyr GLX path.

A bounded guest command ran through the existing shared X11 socket with the Ternuxx Zink/Turnip environment:

```sh
proot-distro login debian --shared-tmp --user "$guest_user" \
  --env DISPLAY=:2 --env GALLIUM_DRIVER=zink \
  --env MESA_LOADER_DRIVER_OVERRIDE=zink \
  --env TU_DEBUG=sysmem,noconform --env MESA_VK_WSI_DEBUG=sw -- \
  /usr/bin/vkcube --gpu_number 0 --c 120
```

`vkcube` selected XCB WSI and `Adreno (TM) 825`, then exited 0 at its 120-frame cap. This is stronger evidence than a context string alone that a Vulkan workload can select the guest Turnip device. No screenshot or Android frame capture was made; visual presentation is not established.

## Thermal qualification boundary and cleanup

Immediately after the command, Native thermal sensors read CPU 62.8°C, GPU 50.7°C, HTP 54.7°C, battery 42.21°C, and SoC 61.0°C. The CPU sample crossed Ternuxx's 60°C conservative workload guard from a 58.9°C preflight. A later read-only sample after the nested session was closed showed CPU 63.3°C, GPU 48.7°C, HTP 52.7°C, battery 42.35°C, and SoC 62.0°C. Therefore this run is **not a thermally qualified GPU result** and is not evidence for sustained acceleration. No guard was changed, and no further hardware workload was run.

Ctrl-C closed only the nested test. Final `tx status` reported Native XFCE and Termux:X11 live on `:1`; `tx pgui status` reported standalone `:0` stopped and nested `:2` socket absent; PRoot inventory reported no active guest sessions or PRoot processes. Debian `dpkg --audit` returned no findings and `apt-get check` succeeded.
