# Native graphics qualification

**Scope:** Native Termux graphics only. OpenGL, OpenGL ES, Vulkan, and inference are separate capabilities. A result applies to the exact device, driver path, API, and workload in its report.

## Current device result

Latest exact stock-package and experimental-candidate results are separated in the [stock Mesa recheck](../evidence/2026-10-24-native-stock-mesa-recheck.md) and [experimental graphics recheck](../evidence/2026-10-24-native-graphics-fallback-recheck.md).

| Path | Observed result | Supported claim |
|---|---|---|
| Installed Termux Mesa 26.2.5, OpenGL | `llvmpipe`, off-screen draw passed, score 81 | CPU software rendering only |
| Installed Termux Mesa, GLES | Verification runner unavailable, exit 127 | No GLES draw claim |
| Installed Termux Mesa, Vulkan | No valid GPU detected; no draw attempted | No stock Vulkan workload claim |
| Experimental Mesa 26.3.0-devel candidate, OpenGL/GLES/Vulkan | Bounded draws passed on Adreno 825 after fresh package extraction | Device-specific experimental evidence only; no supported clean installer |

The official Termux Mesa recipe currently builds Gallium `llvmpipe`, `softpipe`, `virgl`, and `zink`; its aarch64 build separately enables the Freedreno Vulkan ICD with KGSL. Neither package configuration nor status enumeration proves a draw. The current live manager status sees a saved experimental candidate; its Adreno renderer/context/device fields are not workload verification. Keep the candidate outside release support until it has an audited source, repeatable installation path, and workload evidence.

## Run the bounded checks

```sh
./tx mng graphics status native
DISPLAY=:1 ./tx mng graphics verify native opengl :1
DISPLAY=:1 ./tx mng graphics verify native gles :1
DISPLAY=:1 ./tx mng graphics verify native vulkan :1
```

The OpenGL verification attempts the configured renderer, then tests `llvmpipe` and `softpipe` in order if the primary draw fails. It reports CPU fallback only when the exact software renderer and draw both pass. GLES verification compiles/runs a bounded shader pbuffer draw and removes its temporary binary. Vulkan verification requires enumeration and a bounded `vkcube` draw on the same selected device; enumeration failure returns a bounded diagnostic and does not attempt a draw.

The selected candidate is an experimental extracted Mesa build from the community draft [PR #25](https://github.com/lfdevs/termux-packages/pull/25); its successful [GitHub Actions run](https://github.com/lfdevs/termux-packages/actions/runs/36377469447), source commit, artifact digest, and local package checksums are recorded in the [2026-10-24 recheck](../evidence/2026-10-24-native-graphics-fallback-recheck.md). The aarch64 Actions bundle and matching Vulkan backend package are retained in the app-private local artifact cache at `$HOME/.local/share/ternuxx/artifacts/`, with hashes and provenance in `manifest.json`. This avoids rebuilding/re-downloading in this Termux home, but is not a public Ternuxx release or a supported clean-install path. No package upgrade or persistent backend change was made.

## Qualification boundary

OpenGL/GLES off-screen draws, one bounded on-screen Vulkan `vkcube` draw, and the explicit software fallback are verified for this exact device snapshot. A fresh run on 2026-10-24 rendered OpenGL (Adreno 825, score 768), GLES (1,141 frames at 228.03 FPS), and Vulkan (120 Adreno 825 frames); results are in the [live check](../evidence/2026-10-24-native-acceleration-live-check.md). Other application rendering, broad Android compatibility, and clean installation from a stable upstream source are not release-qualified. Ternuxx has a cross-client Vulkan inference route with live device discovery. A run succeeds only when the runtime log proves every model layer was offloaded (`offloaded == total`); partial or absent GPU offload fails closed. The response reports both layer counts. The Termux `llama-cpp-backend-vulkan` 0.7.0 package is installed in live `$PREFIX`; `tx ai devices` enumerates Adreno 825. The pinned-model Ternuxx API path and three owner-provided LAI GGUFs passed bounded Vulkan inference with 29/29 layers offloaded using the selected experimental Mesa/Freedreno ICD. The installed backend is Termux-package-managed; the Mesa ICD remains an experimental private candidate. The matching OpenCL backend artifact was also checked; it reports no OpenCL platforms in this Native session, so OpenCL inference is not exposed or qualified. These short runs do not qualify sustained thermals, general app performance, or a clean package install. Experimental Native Hexagon HTP0 inference is integrated separately; tested short prompts are slower than CPU, with sustained qualification open. Keep CPU inference and software rendering as explicit fallbacks; device/library detection alone never establishes workload acceleration.
