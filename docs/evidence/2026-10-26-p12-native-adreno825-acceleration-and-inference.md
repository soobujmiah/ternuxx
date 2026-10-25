# P12 Native Adreno 825 acceleration and inference qualification

The owner asked that conservative thermal thresholds not delay the work. The bounded inference runner now has the per-run `--ignore-thermal-limits` override; temperature readings remain in the report, while minimum memory, per-call timeout, existing-process refusal, and orphan checks remain enforced.

## Native graphics recovery

Native status initially showed `llvmpipe` and no Vulkan device because the previously tested Mesa/Freedreno candidate was missing from private state. The currently published Termux Mesa 26.2.5 Vulkan ICD reports this Adreno as unsupported (`VK_ERROR_INCOMPATIBLE_DRIVER`). Restored the previously device-qualified Mesa 26.3.0-devel artifact from [community PR #25](https://github.com/lfdevs/termux-packages/pull/25), source commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e`, successful Actions run [36377469447](https://github.com/lfdevs/termux-packages/actions/runs/36377469447). All five `.deb` hashes matched that run's checksum artifact; all four files enforced by `config/graphics/native-kgsl.json` matched their pinned SHA-256 values. The two required packages were extracted into the private Ternuxx provider state, not installed into Termux's package database or shared prefix. The candidate remains experimental, comes from a community draft PR, and has no fresh-install installer.

Installed Termux `llama-cpp` and `llama-cpp-backend-vulkan` 0.7.0 plus `libandroid-spawn` 0.3 after an APT simulation showed exactly three new packages, no upgrades/removals, and 47.8 MB additional installed size. Selected the hash-checked `kgsl-freedreno` provider and restarted only the Ternuxx-owned Native XFCE session on `:1`; Native PulseAudio remained independently managed. Read-only `/proc` inspection confirmed the live XFCE process inherited the private Mesa library path, `MESA_LOADER_DRIVER_OVERRIDE=kgsl`, and isolated Turnip ICD.

After restart, Native graphics status identified Adreno (TM) 825 and Mesa 26.3.0-devel. On display `:1`:

- The bounded GLES 3.2 shader draw rendered 1,049 frames at 1280x720 in five seconds (209.67 frames/sec), with `glFinish()` per frame.
- The Vulkan verifier enumerated Adreno 825 and completed its bounded X11 `vkcube` draw for 120 frames on that same device.
- Status reported Native OpenGL accelerated on Adreno 825. `gui_visible` remains unknown; no screenshot or Android presentation capture was made.

## Inference qualification

`tx ai devices` reported `Vulkan0`, Adreno 825, with 4,069 MiB free at the time of the query. Installed the pinned Qwen3-0.6B-Q4_0 GGUF (428,970,080 bytes); SHA-256 matched `da2572f16c06133561ce56accaa822216f2391ef4d37fba427801cd6736417d4`. The fixed subtraction prompt was adjusted to `What is 9 - 4? Answer with one digit.` after the model used its eight-token budget starting an explanation; a direct bounded check then returned `9 - 4 = 5`.

The three-case CPU suite passed 3/3 and the three-case Vulkan suite passed 3/3, both with eight output tokens and a 30-second per-call timeout. Vulkan reported complete positive offload of all 29/29 model layers to Adreno 825 on every run; the known answers were verified. The largest sampled `MemAvailable` drop still left over 4.0 GiB. No `llama-cli` process remained after either suite. The qualification reports recorded `thermal_limits_ignored: true`; the SoC sensor read 76.0°C during the Vulkan run. These short correctness runs do not qualify sustained performance, OEM thermal behavior, or other models/operators.

The local full test and CI status are recorded by the repository state workflow. Future installer reproducibility, community artifact provenance/licensing review, sustained workload qualification, HTP multi-case coverage, and visible GUI capture remain open.

Phase: `P12`

## Evidence

P12 evidence: live Native Adreno 825 graphics and bounded CPU/Vulkan inference qualification, including the owner-authorized thermal-limit override and the remaining qualification boundaries.


## Experimental HTP route follow-up

Installed the exact previewed llama.cpp Snapdragon b11849 archive through `tx ai npu runtime apply`; archive SHA-256 matched `2d0f1a989a8f0c4329839c3bb85b6fb70edb03e0b017fee0be4cf55b7ece8f6c`. `tx ai npu status --json` then reported experimental HTP0 available on SM8735 with silent fallback disabled. The three-case pinned-model suite passed 3/3 under the owner-authorized thermal override, with 29/29 layers on HTP0, answer verification on each case, and no remaining `llama-cli` process. Available memory stayed above 4.4 GiB during the run. This is a short correctness qualification of the experimental runtime, not sustained performance or broad operator/model coverage.


## Ten-run per-backend repeat qualification

With `--runs 10 --max-tokens 8 --timeout 30 --idle-seconds 0 --ignore-thermal-limits`, all three backends passed 10/10 answer-verified calls. Vulkan reported 29/29 layers for each call; HTP reported 29/29 layers with silent fallback disabled; CPU reported zero GPU layers. No new `llama-cli` process remained after any call. Minimum sampled available memory was 5,004.4 MiB (CPU), 4,726.7 MiB (Vulkan), and 4,080.3 MiB (HTP). The highest sensor readings across each run were CPU/GPU/HTP/battery/SoC-digital: CPU backend 72.4/51.9/56.6/42.84/78.0 C; Vulkan 72.0/58.2/56.3/43.52/78.0 C; HTP 95.2/63.4/67.7/45.07/78.0 C. Thermal thresholds were explicitly ignored for these runs at the owner's direction; Android's system thermal controls were not changed. These are repeated correctness calls, not a sustained benchmark or OEM safety qualification. Full JSON reports remain in private `$HOME/.local/share/ternuxx/qualification/` and are not committed.
