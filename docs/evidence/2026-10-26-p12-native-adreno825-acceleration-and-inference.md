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
