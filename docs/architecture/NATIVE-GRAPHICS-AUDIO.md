# Native graphics, desktop, and audio ownership

## Ownership

Native Termux owns the host executables, Termux:X11 integration, XFCE session, and PulseAudio endpoint. Ternuxx manages its identity-checked Native desktop session and audio lifecycle. Android Activity visibility is separate from X11/XFCE process health; status checks do not request an Activity or stop an unrelated session.

Audio and desktop lifecycle are independent. Audio failure must not terminate or block the desktop; stopping the desktop must not stop an active audio service. Readiness requires an authenticated loopback endpoint, not merely a process or socket.

## Current observed profile

The latest direct device state is recorded in the [Native profile observation](../testing/reports/2026-10-24-native-profile-25053RT47C.md): Native X11/XFCE live on `:1`, and the authenticated PulseAudio endpoint is ready with `OpenSL_ES_sink`. Physical audibility has not been verified.

Native OpenGL/GLES off-screen draws, one bounded Vulkan X11 `vkcube` draw on Adreno 825, and an explicit llvmpipe fallback were directly rechecked. Exact renderers, workload results, loader-path cause/fix, and candidate provenance are in the [P6 graphics report](../evidence/2026-10-24-native-graphics-fallback-recheck.md). The experimental candidate now has an owner-authorized checksum-pinned release acquisition/private-extraction path; its fresh-device acceptance and byte-reproducible source-build gate remain open. See the [installation guide](../INSTALLATION.md#pinned-native-gpu-release-and-repeated-installation). Do not infer application or inference acceleration from the off-screen result.

## Implemented controls

- `tx status` reports ownership-scoped desktop state without stopping processes.
- `tx audio status|start|stop` manages the Native loopback audio endpoint with its own identity checks.
- `tx mng graphics status native` reports the selected Native graphics state.
- `tx mng graphics verify native {opengl|gles|vulkan} :1` runs the bounded API-specific workload and reports its exact outcome.
- CLI, TUI, Web, and GTK graphics actions dispatch through the shared management service; API/session authorization is authoritative.

These controls do not expose arbitrary environment variables or guest mounts. Unsupported providers are rejected.

## Remaining limits

Termux:X11 companion APK version is not readable to the app UID used in this observation. Android GUI visibility and physical audio output remain separately unverified. The accelerated Mesa candidate retains the open P12 transitive provenance/license-attribution review and clean-device workload gate; Vulkan needs a compatible `vulkaninfo`/libc++ toolchain; on-screen application behavior and workload-specific performance/thermal stability need separate evidence. Bounded CPU and Vulkan inference are implemented; Vulkan runs on the selected experimental ICD with explicit GPU-offload proof. A separate pinned Snapdragon HTP0 path passes short SM8735 inference checks with full layer delegation and no CPU fallback; tested prompts are slower than CPU, and sustained qualification remains open. See [GPU qualification](../testing/GPU-ACCELERATION.md) and [NPU qualification](../testing/NPU-ACCELERATION.md).
