# Native Blender GPU and software fallback MCP smoke report — 2026-10-28

- Report ID: `TERN-TEST-2026-10-28-BLENDER-NATIVE-MCP-01`
- Generated UTC: 2026-10-27 (device local date 2026-10-28, Asia/Dhaka UTC+06)
- Ternuxx source commit: `1d9346a0c339fe9e82ab677ba392f73f34e17673` (`main`, unchanged during this report)
- Adapter and bridge source: SKB commit `ac1093d84c51bc92f32c1a582e199e42db3f1d79`, files `integrations/codex/restore/native_blender_gpu_mcp.py` and `blender_gui_bridge.py`
- Release/version: unreleased local MCP adapter; Blender 5.2.2 LTS, build hash `d13f752e3b9c`
- Report owner/operator: Codex, direct Native Termux process execution under Sobuj's task instruction
- Test type: `owner_operated_device` (agent-executed on the owner's physical device)
- Verdict: **PARTIAL** — both one-frame paths work; this is a smoke check, not animation-pipeline or release qualification
- Reproduced: yes; one successful GPU call and one successful software call after one corrected failed attempt

## Device and runtime

- Device model / chipset / ABI: Redmi Turbo 4 Pro (`25053RT47C`), Adreno 825, Android Linux `aarch64`
- Android build/API: Android 16 / API 36; kernel `6.6.77-android15-8-g4a507830d890-ab13636293-4k`
- Termux version and app source/signing context: app version not queried in this run; Termux tools package `1.46.0+really1.45.0-1`
- Execution context: Native Termux; existing Termux:X11/XFCE display `:1`
- Runtime version/commit/build flags: Native Termux Blender binary `blender-5.2`; MCP uses the upstream Ternux Blender MCP server through a Native adapter
- Driver/delegate/SDK versions: experimental Mesa `26.3.0-devel` KGSL/Freedreno candidate from Ternuxx private state; GPU renderer `Adreno (TM) 825`. Software mode explicitly forces `llvmpipe (LLVM 21.1.8, 128 bits)`.

## Workload and artifacts

- Workload ID and source: procedural single-frame Blender EEVEE smoke scene in [`smoke.py`](../../evidence/2026-10-28-blender-native-gpu/smoke.py)
- Workload SHA-256: `c7dbe2a22014b27288cc9b34a99f50e48401c0a2be03cea9eaa98cfe66e55d3a`
- License and redistribution terms: original procedural test scene; no third-party assets
- Backend requested: GPU by default; software fallback only when `backend: "software"` is explicitly supplied
- Backend observed and evidence: `gpu_check` returned Adreno 825, accelerated `true`, GPU path ready; Blender render stdout also identified vendor `freedreno` and renderer `Adreno (TM) 825`. Software render was forced by `LIBGL_ALWAYS_SOFTWARE=1`, `GALLIUM_DRIVER=llvmpipe`; `gpu_check` identified the llvmpipe renderer.
- Fallback/partial delegation: no automatic fallback. The test was repeated as two separate MCP calls and each rendered on its selected backend.
- GUI authoring: Native startup bridge at `~/.config/blender/5.2/scripts/startup/blender_agent_bridge.py`; it was manually activated in the existing Blender PID `31438`, display `:1.0`. `gui_submit_script` created a temporary cube visible in the frontmost 3D viewport, then a second queued script removed it. Both jobs were retained as `OK`; final `gui_status` reported active, idle, zero queued jobs. The viewport was returned to 3D View after the one-time Console activation.
- Project output target: `test -w /sdcard/Blender` returned true. No project directory or user file was created or read during this smoke check.

## Procedure

The adapter requires the existing `:1` X11 socket; it does not start or stop a desktop. Registration and exact restore instructions live in SKB's `integrations/claude-code/restore/MCP_SERVERS.md`. In a Codex session with the MCP registered:

1. Call `gpu_check` with `display: ":1"`.
2. Call `render_script` with `script` set to the absolute `smoke.py` path, `script_args` containing an absolute PNG output path, and `display: ":1"`. Omit `backend` or set `backend: "gpu"` for the default Adreno path.
3. To deliberately use the fallback, repeat with another absolute output path and `backend: "software"`. This forces llvmpipe; it is never selected automatically.

The raw JSON-RPC responses for the failed first attempt, corrected GPU/software renders, and visible GUI queue test are stored in [`mcp-results-initial-failure.json`](../../evidence/2026-10-28-blender-native-gpu/mcp-results-initial-failure.json), [`mcp-results.json`](../../evidence/2026-10-28-blender-native-gpu/mcp-results.json), and [`gui-bridge-mcp-results.json`](../../evidence/2026-10-28-blender-native-gpu/gui-bridge-mcp-results.json). The GUI test scripts are [`gui-smoke.py`](../../evidence/2026-10-28-blender-native-gpu/gui-smoke.py) and [`gui-cleanup.py`](../../evidence/2026-10-28-blender-native-gpu/gui-cleanup.py). The first script version requested the nonexistent `BLENDER_EEVEE_NEXT` enum in this Blender 5.2 build, wrote no frame, and was corrected to `BLENDER_EEVEE`. Both later calls used the same 64×64 EEVEE sphere, area light, camera and PNG settings. One run per backend; no warmup, repeated sampling, thermal start/end measurement, charging-state control, or sustained run was performed.

## Acceptance criteria and results

| Criterion | Expected | Observed | Status | Evidence |
|---|---|---|---|---|
| MCP initialization and tool discovery | Server initializes and exposes GUI and render tools | stdio JSON-RPC initialized as `blender-native-gpu`; all five tools listed, including `gui_status` and `gui_submit_script` | PASS | Raw JSON files above |
| Visible GUI authoring | Queued Blender Python updates the open viewport and completes | On PID 31438 / display `:1.0`, a temporary cube appeared in the 3D viewport; cleanup removed it; both queued jobs were `OK`, final queue empty | PASS | `gui-bridge-mcp-results.json`, GUI job scripts, live viewport inspection |
| Project path availability | Requested project folder writable | `/sdcard/Blender` passed a write-permission check; no project file written in this test | PASS | Procedure result recorded above |
| Backend actually selected — GPU | Adreno acceleration verified before rendering | `gpu_check`: Adreno 825, accelerated `true`; Blender log: Freedreno / Adreno 825 | PASS | Raw JSON; `gpu.png` |
| GPU workload completed | One 64×64 EEVEE PNG frame | exit 0; one frame; Blender frame time 12.570 s; wall 13.08 s | PASS | [`gpu.png`](../../evidence/2026-10-28-blender-native-gpu/gpu.png) |
| Backend actually selected — software | Explicit llvmpipe fallback, no GPU env | renderer `llvmpipe (LLVM 21.1.8, 128 bits)`; `LIBGL_ALWAYS_SOFTWARE=1` | PASS | Raw JSON; `software.png` |
| Software workload completed | One 64×64 EEVEE PNG frame | exit 0; one frame; Blender frame time 87.961 s; wall 88.48 s | PASS | [`software.png`](../../evidence/2026-10-28-blender-native-gpu/software.png) |
| Failure handling | Invalid scene script does not count as a render | Initial `BLENDER_EEVEE_NEXT` request wrote zero frames; diagnosis reported zero-frame result; corrected script passed on both backends | PASS | `mcp-results-initial-failure.json` |
| Stability/resource behavior | No crash or orphan process | Both successful render processes exited 0; no orphan Blender process from the test remained | PASS | Raw JSON and process check |
| Release qualification | Sustained, reproducible production workloads | Not tested | UNKNOWN | Scope of this smoke report |

The GPU log included `Warning: Could not find a matching GPU name. Things may not behave as expected.` and a DRM file-description permission warning. Despite these warnings, Blender logged the Adreno renderer and saved the frame. The renderer identity and successful frame are evidence for this exact run, not a guarantee that every scene behaves correctly.

## Raw measurements

- [`mcp-results.json`](../../evidence/2026-10-28-blender-native-gpu/mcp-results.json) SHA-256: `69608d4bf34ebfbec47af7145acb0cc4e24b7c8ce1766d6c353ac98dcabd868a`
- [`mcp-results-initial-failure.json`](../../evidence/2026-10-28-blender-native-gpu/mcp-results-initial-failure.json) SHA-256: `075b2c908b5bf3f666d8fe8445d63b7f57fbd542200218181aec8f226c94c066`
- `gpu.png` SHA-256: `734ab90e6c51f859997957ac9829c2d5606ab4130c84cdd540f5a2d3f3e471eb`
- `software.png` SHA-256: `37e95bf3afc625ae5a497bf1cee742170d7f9dfdfd789a9a0b30db5cd9c135dc`
- `smoke.py` SHA-256: `c7dbe2a22014b27288cc9b34a99f50e48401c0a2be03cea9eaa98cfe66e55d3a`
- [`gui-bridge-mcp-results.json`](../../evidence/2026-10-28-blender-native-gpu/gui-bridge-mcp-results.json) SHA-256: `70cc6aa6fb4284bcbc70cf91625250e7db0e366d6fd23ee8b5410daa0c8c8571`
- `gui-smoke.py` SHA-256: `108225c1e853db38484c5d187b8674f43a845893573480631a6c054ceb31c7f0`
- `gui-cleanup.py` SHA-256: `1541f20e65a3ff6f6be1796a70b1fd377ddf98a87ecd85101022c1932893f462`

## Limitations and privacy review

This is one small 64×64, one-frame smoke scene on one physical device. It does not validate character animation, large scenes, multi-frame sequencing, output assembly, audio, captions, thermal stability, memory headroom under a production project, or clean-install reproducibility of the experimental Mesa candidate. Software rendering completed but took 87.961 seconds for the small frame; GPU remains the required default for production. No Android settings, shared storage, personal files, or credentials were accessed. Raw output contains only local paths, environment facts, Blender logs, and renderer diagnostics.

## Review

- Reviewed by: Codex
- Review date: 2026-10-28
- Compatibility matrix updated: no; this is a single experimental device path
- Feature matrix updated: no; no product feature changed in Ternuxx
- Website/report index updated: test report index updated
