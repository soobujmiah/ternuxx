# Native graphics qualification

**Scope:** Native Termux graphics only. OpenGL, OpenGL ES, Vulkan, and inference are separate capabilities. A result applies to the exact device, driver path, API, and workload in its report.

## Current device result

The stock Termux package result and latest selected experimental-candidate result are separated below and in the [stock Mesa recheck](../evidence/2026-10-24-native-stock-mesa-recheck.md), [experimental graphics recheck](../evidence/2026-10-24-native-graphics-fallback-recheck.md), and [2026-10-26 Native Adreno recovery](../evidence/2026-10-26-p12-native-adreno825-acceleration-and-inference.md).

| Path | Observed result | Supported claim |
|---|---|---|
| Installed Termux Mesa 26.2.5, OpenGL | `llvmpipe`, off-screen draw passed, score 81 | CPU software rendering only |
| Installed Termux Mesa, GLES | Verification runner unavailable, exit 127 | No GLES draw claim |
| Installed Termux Mesa, Vulkan | No valid GPU detected; no draw attempted | No stock Vulkan workload claim |
| Termux `mesa-vulkan-icd-freedreno` 26.2.5, privately extracted and selected in isolation | Loader rejects Adreno 825 (`gpu_id = 6830`, `VK_ERROR_INCOMPATIBLE_DRIVER`) | Not a usable clean-install path for this device |
| Experimental Mesa 26.3.0-devel candidate, Native `:1` OpenGL/GLES/Vulkan | Live XFCE inherits private candidate paths; GLES rendered 1,049 frames/5 sec and Vulkan rendered 120 X11 frames on Adreno 825 | Device-specific experimental evidence; no supported clean installer |

The official Termux Mesa recipe builds Gallium `llvmpipe`, `softpipe`, `virgl`, and `zink`; its aarch64 build separately enables the Freedreno Vulkan ICD with KGSL. The installed 26.2.5 Freedreno package rejects this Adreno 825; see the [device check](../evidence/2026-10-24-official-freedreno-icd-adreno825-check.md). The selected private Mesa 26.3.0-devel candidate from community draft PR #25 passes actual GLES and Vulkan draws on this device, including after restarting the managed Native `:1` XFCE. The candidate remains outside release support: it has an incomplete source/license audit and no repeatable fresh-install path.

## Run the bounded checks

```sh
./tx mng graphics status native
DISPLAY=:1 ./tx mng graphics verify native opengl :1
DISPLAY=:1 ./tx mng graphics verify native gles :1
DISPLAY=:1 ./tx mng graphics verify native vulkan :1
```

The OpenGL verification attempts the configured renderer, then tests `llvmpipe` and `softpipe` in order if the primary draw fails. It reports CPU fallback only when the exact software renderer and draw both pass. GLES verification compiles/runs a bounded shader pbuffer draw and removes its temporary binary. Vulkan verification requires enumeration and a bounded `vkcube` draw on the same selected device; enumeration failure returns a bounded diagnostic and does not attempt a draw.

The selected candidate is an experimental extracted Mesa build from the community draft [PR #25](https://github.com/lfdevs/termux-packages/pull/25); its successful [GitHub Actions run](https://github.com/lfdevs/termux-packages/actions/runs/36377469447), source commit, artifact digest, and local package checksums are recorded in the [2026-10-24 recheck](../evidence/2026-10-24-native-graphics-fallback-recheck.md). The aarch64 Termux package remains an expiring Actions artifact from that open draft PR; the author's separate [Mesa GitHub release](https://github.com/lfdevs/mesa-for-android-container/releases/tag/mesa-26.3.0-devel-20260824) publishes Linux distribution archives, not a Native Termux package. Current artifact status and license-notice limits are in the [Native artifact provenance recheck](../evidence/2026-10-24-p12-native-artifact-release-recheck.md); package checksums and control metadata are captured in the [package-level SPDX inventory](../evidence/2026-10-24-p12-native-mesa-package-sbom.spdx.json) and [inventory review](../evidence/2026-10-24-p12-native-mesa-package-inventory.md). That inventory does not analyze source components or conclude redistribution rights. The candidate's aarch64 Actions bundle was re-downloaded and checksum-verified on 2026-10-26, then extracted into `$HOME/.local/share/ternuxx/graphics/providers/native-mesa-0219ff84/`; the saved KGSL selection applies to future Native desktop starts. This is private app state, not a Termux package install or public Ternuxx release. The selected provider remains experimental and has no fresh-install workflow.

## Qualification boundary

OpenGL/GLES off-screen draws, one bounded on-screen Vulkan `vkcube` draw, and the explicit software fallback are verified for this exact device snapshot. A fresh run on 2026-10-24 rendered OpenGL (Adreno 825, score 768), GLES (1,141 frames at 228.03 FPS), and Vulkan (120 Adreno 825 frames); results are in the [live check](../evidence/2026-10-24-native-acceleration-live-check.md). Other application rendering, broad Android compatibility, and clean installation from a stable upstream source are not release-qualified. Ternuxx has a cross-client Vulkan inference route with live device discovery. A run succeeds only when the runtime log proves every model layer was offloaded (`offloaded == total`); partial or absent GPU offload fails closed. The response reports both layer counts. The Termux `llama-cpp-backend-vulkan` 0.7.0 package is installed in live `$PREFIX`; `tx ai devices` enumerates Adreno 825. The Ternuxx-managed inference API selects only its pinned Qwen3 0.6B model. Separately, direct Termux `llama-cli` compatibility probes ran three owner-provided LAI GGUFs with 29/29 layers offloaded using the selected experimental Mesa/Freedreno ICD; these probes do not add model selection to the Ternuxx API. The installed backend is Termux-package-managed; the Mesa ICD remains an experimental private candidate. The matching OpenCL backend artifact was also checked; it reports no OpenCL platforms in this Native session, so OpenCL inference is not exposed or qualified. These short runs do not qualify sustained thermals, general app performance, or a clean package install. Experimental Native Hexagon HTP0 inference is integrated separately; tested short prompts are slower than CPU, with sustained qualification open. Keep CPU inference and software rendering as explicit fallbacks; device/library detection alone never establishes workload acceleration.

Ten repeated 64-token calls through the pinned-model Vulkan API also completed with 29/29 layers and bounded per-run resource sampling; the [repeat report](../evidence/2026-10-24-p12-native-repeated-resource-check.md) records the exact profile and limits. This remains repeated bounded evidence rather than continuous burn-in. The current indexed Termux Freedreno ICD 26.2.5 was rejected by this Adreno 825, so a stable clean-install path remains unresolved.
