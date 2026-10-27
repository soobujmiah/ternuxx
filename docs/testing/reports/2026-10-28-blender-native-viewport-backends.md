# Native Blender viewport backend comparison — 2026-10-28

## Result

The same `mithyar_mic.blend` file was opened in Blender 5.2.2 LTS under both Native GPU paths. In the **Rendered** camera viewport, Zink/Turnip showed the full scene and cast; direct KGSL showed severe display artifacts, missing character bodies and black blocks. The owner reports Zink is usable for preview with some remaining rendering issues. The screenshots support using Zink/Turnip for visible Blender work on this scene; the direct KGSL result is not visually acceptable here.

The bounded redraw timings alone do not explain the visual defect. In Solid mode, direct KGSL was faster. In Rendered mode after warm-up, direct KGSL also had lower redraw time, but the image was corrupted. The task is therefore correctness first: keep the currently open Zink/Turnip GUI for preview, and do not use the direct KGSL viewport for scene review until its artifacts are resolved. No persistent graphics backend selection was changed.

## Controlled setup

- Ternuxx source revision before this report: `a2550df35d18415876a23f398ef0af5cc333719f`.
- Device: Redmi Turbo 4 Pro; Adreno 825; Native Termux; X11 display `:1.0`.
- Project: `/sdcard/Blender/bangla-short-films/mithyar-mic-2026-10-14/mithyar_mic.blend`.
- Scene: `Mithyar Mic | Character Workshop`; 153 objects; camera `SHOT_WIDE`.
- Both runs used Blender 5.2.2 LTS, Mesa `26.3.0-devel (git-98f3d6229d)`, same project, camera, `RENDERED` viewport mode and overlays off. The blend stayed clean (`bpy.data.is_dirty == false`); viewport settings were temporary and not saved.
- Direct route: Native KGSL/Freedreno OpenGL (`Adreno (TM) 825`). Zink route: the already-extracted isolated Native Mesa candidate and Freedreno ICD (`zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`). Both were confirmed accelerated.
- For redraw timing, each GUI waited 15 seconds after startup, discarded 5 warm-up redraws, then measured 3 batches of 10 `DRAW_WIN_SWAP` iterations. A separate Solid-mode run used 30 warm-ups plus 3 batches of 60.
- The Native GUI currently left open is Zink/Turnip, with the project in camera `RENDERED` preview. Its bridge is active. The Native X11 desktop stayed running throughout.

## Measured redraws

| Viewport mode | Native route | Batch times (ms per redraw) | Median |
|---|---|---:|---:|
| Solid | Direct KGSL | 16.73, 17.54, 17.93 | 17.54 ms |
| Solid | Zink/Turnip | 42.32, 40.69, 42.37 | 42.32 ms |
| Rendered | Direct KGSL | 24.76, 22.97, 20.78 | 22.97 ms |
| Rendered | Zink/Turnip | 78.47, 46.88, 28.55 | 46.88 ms |

Zink's Rendered redraw time fell across the three batches as its preview warmed. These are Blender window redraw timings, not mouse-input latency or a sustained frame-rate qualification. In the Rendered screenshots, visual correctness differed substantially even though the direct route had the lower median redraw time.

## Screenshot evidence

- [Direct KGSL — Rendered camera view](../../evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/kgsl-rendered-clean.png), SHA-256 `f4dc32638b4944cd92c0272ed3f8e733da22ca3dda052e7deeab4b3bd34be299`.
- [Zink/Turnip — Rendered camera view](../../evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-rendered-clean.png), SHA-256 `ad9d4a73dd36a78e0103aefa497340dd65e8c5bc649fb01514ba06552005be95`.
- [Direct KGSL redraw JSON](../../evidence/2026-10-28-blender-60s-ternux-benchmark/gui-rendered-redraw-kgsl-direct.json), SHA-256 `c482263783925dc777816b2bbb4b6c931a3b6b66bb6805c49692c0dcd328d634`.
- [Zink/Turnip redraw JSON](../../evidence/2026-10-28-blender-60s-ternux-benchmark/gui-rendered-redraw-zink-turnip.json), SHA-256 `55dfc0b1f426931a43dd9fc4118e814a898aff8395b6524bb99f96eea75a0bd7`.
- [Solid-mode redraw JSON: KGSL](../../evidence/2026-10-28-blender-60s-ternux-benchmark/gui-redraw-kgsl-direct.json), [Zink](../../evidence/2026-10-28-blender-60s-ternux-benchmark/gui-redraw-zink.json).

## Fresh scene and standalone PRoot comparison — 2026-10-28

Ternuxx source revision at the time: `a46a98d`. A new 16-object EEVEE scene was built so the previous 153-object project could not be the only explanation for the Native KGSL artifacts. Blender 5.2.2 under direct KGSL again showed repeated black/cyan tile corruption in Rendered mode. Native Zink/Turnip showed the scene without those tile artifacts. The owner also reports that Native Zink still jitters and behaves oddly while orbiting.

The same Blender 5.2.2 `.blend` could not be opened by PRoot Blender 4.3.2 (`incomplete header, may be from a newer version`). To compare on the PRoot version, the same procedural scene recipe was adapted for Blender 4.3.2 / EEVEE Next and run in the **standalone** managed Debian XFCE desktop on `:0`; Native `:1` was stopped through `tx stop` first, as requested. The PRoot process reported `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`; the session graphics check reported Zink GL 25.0.7 and Turnip on Adreno 825. After a single 120×90-pixel MMB orbit drag in the visible Rendered viewport, the captured frame still showed the complete scene without the KGSL tile corruption. The owner then manually rotated the live PRoot view and confirmed that it felt smooth. The owner’s interaction report is qualitative; it is not a measured input-latency or sustained FPS result. PRoot GUI redraw timing on the same scene settled at 35.4–36.6 ms per `DRAW_WIN_SWAP` in the last two batches; the first two batches were 108.4 and 65.2 ms per redraw. This window redraw probe is not a mouse-input latency or sustained FPS test.

The PRoot and Native routes differ in both Blender (4.3.2 vs 5.2.2) and Zink GL userspace (Debian Mesa 25.0.7 vs Native experimental Mesa 26.3.0-devel), so this comparison cannot attribute the reported Native orbit jitter to Blender or Mesa alone. The experimental Native Zink route was also tried with Ternuxx's PRoot `TU_DEBUG=sysmem,noconform` setting; a static frame remained coherent, but an equivalent Native orbit replay was not completed. Native `:1` remains stopped and the standalone PRoot `:0` Blender GUI remains open.

Fresh-scene artifacts and reproduction material: [KGSL Rendered frame](../../evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl/kgsl-rendered.png), [Native Zink with sysmem Rendered frame](../../evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl/zink-sysmem-rendered.png), [standalone PRoot frame after orbit](../../evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl/proot4-orbit-x11.png), [PRoot Blender 4.3.2 project](../../evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl/proot4-fresh-gpu-test.blend), [PRoot scene builder](../../evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl/proot4-build-scene.py), [PRoot GPU/version and redraw record](../../evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl/proot4-gui-probe.json), and [PRoot post-orbit state](../../evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl/proot4-orbit.json). SHA-256: KGSL screenshot `13743dc0cfe2023ad178fdcd1154e7abb509251cc7323ef8e707b87f18228341`; Native Zink screenshot `a7a33d1d8f367462cf08a948652f450ad37a0c565c68b6102cff7f41da93bd96`; PRoot post-orbit screenshot `ffc952f24996fd722bdafa884382988fc2f83636d09b9233bf57277a48f843db`; PRoot `.blend` `70f9a68509ad7c37504664321cd14882471fc9b1555687f329321b7a7597dfef`.

## Comparison limits and follow-up

The historical PRoot experience used Blender 4.3.2 with Zink/Turnip, while this A/B kept Blender 5.2.2 fixed. It does not isolate Blender 4.3.2 versus 5.2.2, and it does not establish whether the remaining Zink preview defects occur in final frame renders. The rendered screenshots are viewport previews, not final production renders. Next, render the same deterministic still through both accelerated routes and compare image correctness before choosing the rendering backend for the 60-second run.
