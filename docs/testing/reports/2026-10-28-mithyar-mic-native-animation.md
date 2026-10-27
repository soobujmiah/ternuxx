# Test report: Mithyar Mic Native Blender 4.5 animation pass

- Report ID: `TERN-TEST-2026-10-28-MITHYAR-NATIVE45-01`
- Generated UTC: 2026-10-27 (device local date 2026-10-28, Asia/Dhaka UTC+06)
- Ternuxx source commit before this report: `4fbb994`
- Release/version: unreleased project; Native Blender 4.5.14 LTS (`blender4` 4.5.14-2)
- Report owner/operator: Codex, acting under Sobuj's task instruction
- Test type: `owner_operated_device`
- Verdict: **PARTIAL / visual correctness FAIL** — editable one-minute scene copy was built and saved; a Native Adreno EEVEE frame completed, but the output is corrupted. No full animation render or movie was produced.
- Reproduced: one build/save; one representative GPU still render

## Device and runtime

- Device model / chipset / ABI: Redmi Turbo 4 Pro (`25053RT47C`), Adreno 825, `aarch64`
- Android/kernel: Android 16 / API 36; kernel `6.6.77-android15-8-g4a507830d890-ab13636293-4k`
- Execution context: Native Termux; existing Termux:X11/XFCE display `:1`
- Blender: Native binary `/data/data/com.termux/files/usr/bin/blender-4.5`, Blender 4.5.14 LTS
- GPU provider: Ternuxx experimental Native Mesa 26.3.0-devel KGSL/Freedreno; Blender render log reported vendor `freedreno`, renderer `Adreno (TM) 825`
- Scene authoring: visible GUI Python bridge in Blender; no software renderer used

## Workload and output

- Source project: `/sdcard/Blender/bangla-short-films/mithyar-mic-2026-10-14/mithyar_mic.blend`, 153 objects, Blender 4.3 file format (`BLENDER-v403`)
- Source story: `STORY.md`, a 60-second Bangla political satire with a broken water pipe, a leader turning up the microphone, a sagging banner, a youth recording on a phone, and a child's closing question
- Source project SHA-256: `68c46a93f72135f912cd53385279af832cd76d41437c362ab465516d708b8609`
- Timeline script SHA-256: `33339415b75a7a6c4cdb79f722f0614213a97737a13104cedc2da84a3a02706f`
- New editable output: `/sdcard/Blender/bangla-short-films/mithyar-mic-native45-production-2026-10-28/mithyar_mic_native45_60s.blend`
- Output project SHA-256: `1a4943e69c610c1b054cfa64fe6c31eeb7a9bf70eedae4f7ffcbfc7775a8ee59`; size 99 MiB. Original project hash remained the same.
- Timeline: frames 1–1440, 24 fps, 60 seconds; EEVEE Next; 1280×720; 16 samples. The scene has 153 objects, story-timed gestures/props, seven camera objects with story camera markers, and the packed Bengali moral end card.
- Dialogue audio: not included. Story dialogue remains in the copied `STORY.md`; no dialogue subtitles were added, consistent with the source handoff.

## Procedure

1. Verified `./tx status` and `./tx mng graphics status native`: Native desktop `:1` running and selected backend `kgsl-freedreno`; OpenGL state was accelerated on Adreno 825.
2. Opened the source `.blend` in Native Blender 4.5.14 through the live GUI bridge. Confirmed the expected story rigs, pipe, puddle and banner assets.
3. Ran the task-scoped [production script](../../evidence/2026-10-28-mithyar-mic-native45/production.py) in the GUI. It adds the 60-second camera/gesture timeline, packs resources and saves to a new directory. The source `.blend` was not saved over.
4. Reopened the new project in the visible GUI and set a Solid camera view. The GUI bridge reported Blender 4.5.14, the new file, `SHOT_WIDE`, frame 1 and 153 scene objects. The [captured GUI view](../../evidence/2026-10-28-mithyar-mic-native45/native-gui-solid-camera.png) shows that scene presentation/model visibility is still poor on this Native path.
5. Ran a one-frame background EEVEE render using the same Native KGSL provider with `DISPLAY=:1`. Blender returned exit code 0 and completed frame 1 in 25.77 seconds, but the image was visually corrupt. No full animation render was started after this failure.

The current Codex session did not expose the Blender MCP tools. The Blender Python bridge and the Native GPU runtime were used directly. PRoot was not started in this run.

## Acceptance results

| Criterion | Expected | Observed | Status | Evidence |
|---|---|---|---|---|
| Native GUI authoring | Scene and timeline editable in visible Blender 4.5 | Script completed in the GUI bridge; new project saved and reopened; owner reports orbit feels smooth | PASS for interaction/build only | GUI bridge state, `native-gui-solid-camera.png` |
| Story/timeline setup | 60 seconds, 24 fps, 1,440 frames, intended story cuts | 1–1440, 24 fps; markers and keyframed gestures created | PASS (structural; no motion review across the full timeline) | `production.py`, output manifest |
| Native GPU selected | Adreno accelerated render | Blender logged `freedreno`, `Adreno (TM) 825`; render exited 0 | PASS for backend/workload initialization | `native-kgsl-frame-0001.log` |
| Representative image correctness | Full scene, readable cast, no graphics corruption | Repeated horizontal/vertical block artifacts, missing characters and props, poor framing/readability | FAIL | `native-kgsl-frame-0001.png`, SHA-256 `d3d40c87baeec5c06f085c0cdfcd92e4bb183ca67b5e5771c774aa1d41263931` |
| Full 1,440-frame render | Complete clean sequence and MP4 | Not started after the frame-1 correctness failure | BLOCKED | This report |
| Audio and final mix | Story dialogue and designed sound | Not included | NOT RUN | Source `STORY.md` only |

## Result files and hashes

- Native frame 1 log: [`native-kgsl-frame-0001.log`](../../evidence/2026-10-28-mithyar-mic-native45/native-kgsl-frame-0001.log), SHA-256 `a1828a5a8e7d639e03f52e20fd5a59b90d4db21fda4e152682ba31a8b26be487`.
- Native frame 1 PNG: [`native-kgsl-frame-0001.png`](../../evidence/2026-10-28-mithyar-mic-native45/native-kgsl-frame-0001.png), SHA-256 `d3d40c87baeec5c06f085c0cdfcd92e4bb183ca67b5e5771c774aa1d41263931`.
- GUI Solid camera view: [`native-gui-solid-camera.png`](../../evidence/2026-10-28-mithyar-mic-native45/native-gui-solid-camera.png), SHA-256 `653437d31963a6abe3d16d7a1d52eced13619b190224d8fc0125c6563ba00154`.
- Reproducible task script: [`production.py`](../../evidence/2026-10-28-mithyar-mic-native45/production.py), SHA-256 `3e0090bcfa5b6a3ff1a60b1ce798ae15eafe9078cff58b9ee7aca73e13b0b8a5`.

## Limits and follow-up

This report demonstrates smooth GUI orbit and confirms that a Native Adreno-backed EEVEE invocation can execute a frame. It does **not** demonstrate that the scene was generated cleanly or that the rendered result is usable. The Native KGSL image is visibly broken, so 1,440-frame rendering would spend substantial time producing an unacceptable sequence. The previous Native Zink/Turnip attempt with Blender 4.5 crashed opening this workload; the PRoot Zink path is separately configured and its earlier viewport evidence is not a same-version full-render qualification. The Ternuxx runbook therefore requires representative frames to pass before full rendering and prohibits a silent backend/runtime switch.

The source handoff records unresolved art-review items for the phone placement and the politician likeness. This task did not claim those models as owner-approved. The next decision is whether to keep debugging Native KGSL for this scene or authorize a separately reported PRoot Zink/Turnip render path. Audio/dialogue and final MP4 assembly also remain unproduced.
