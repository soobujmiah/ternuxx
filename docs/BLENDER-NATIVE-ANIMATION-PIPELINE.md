# Native Blender animation pipeline

This guide records the Native Termux workflow now installed on the Redmi Turbo 4 Pro. Use the already-running Ternuxx Native XFCE/Termux:X11 desktop and the open Blender GUI for visible scene work. Blender GUI Python runs with full file authority as the Termux user; only run reviewed, task-scoped scripts in the bridge.

## Current verified setup

- Native package: `blender4` 4.5.14-2; executable `/data/data/com.termux/files/usr/bin/blender-4.5`.
- Display: Termux:X11 `:1`, Ternuxx XFCE desktop.
- Selected graphics path: experimental Native `kgsl-freedreno`; renderer Adreno 825, Mesa 26.3.0-devel.
- GUI bridge: `~/.cache/blender-agent-bridge/queue/*.py`, started by `~/skb/integrations/codex/restore/blender_gui_bridge.py`; see SKB's current environment guide for its status/results contract.
- Render engine used for the current project: EEVEE Next.
- Do not equate smooth Solid viewport orbit with correct Rendered preview or final output. On the 2026-10-28 Mithyar Mic check, Native KGSL rendered one frame successfully but the image had severe repeated black/colored tile artifacts and missing scene elements. Full animation rendering is therefore not qualified on this path yet.

## Start and author visibly

1. From `~/ternuxx`, run `./tx start` and use the requested Termux:X11 Activity on display `:1`.
2. Launch Blender 4.5.14 in the existing display with the Native KGSL candidate environment. Keep the Blender process attached to a live terminal session while authoring; a detached launch was not reliable in this session.
3. Confirm the bridge reports the live Blender PID, version, display and empty queue. Queue a small script first; check its retained `done/` result before continuing.
4. Open the source project and inspect it without saving over it. Author in `VIEW_3D`; leave the visible screen on the Solid camera view or another owner-reviewed viewport, not Console.
5. Save a new project under `/sdcard/Blender/<project>/`, with `scripts/`, `renders/`, a story/source copy and a manifest. Keep the original file intact.

For the current production, see the [Mithyar Mic report](testing/reports/2026-10-28-mithyar-mic-native-animation.md) and exact [scene/timeline script](evidence/2026-10-28-mithyar-mic-native45/production.py). The generated editable project is `/sdcard/Blender/bangla-short-films/mithyar-mic-native45-production-2026-10-28/mithyar_mic_native45_60s.blend`.

## Verify before a full render

Check Native graphics state with `./tx mng graphics status native`. A successful task render must also say `Vendor: freedreno` and `Renderer: Adreno (TM) 825` in Blender output. Render and inspect one representative frame from every distinct camera/lighting setup before spending time on the full sequence. In particular, inspect image pixels for missing geometry, black blocks, stripes, wrong materials and camera framing.

Native GPU is the requested production default. Software is a deliberately selected recovery/diagnostic path, never an automatic fallback. The Native MCP adapter supports an explicit `backend: "software"` request when that MCP is available; this does not satisfy a GPU-required final render. PRoot Zink/Turnip is a separately configured GPU route. Do not switch the project or render runtime silently: record Blender file-version compatibility and get task authorization for a route change.

The one-frame Native KGSL test and its artifact do **not** support rendering all 1,440 frames. Do not start the full job until the representative frames pass visual review. The existing `/sdcard` source remains preserved.

## Current limits

The current Native evidence verifies GUI authoring/build, Blender 4.5 loading/saving a new copy, Adreno-backed EEVEE initialization and completion of one still render. It does not verify animation continuity, a clean rendered frame, 1,440-frame completion, audio, MP4 assembly, long-run thermals, or final story quality. The source handoff also marks the phone placement and politician likeness as awaiting owner review; this run does not resolve those art-direction decisions. See the report for hashes, failures and next steps.
