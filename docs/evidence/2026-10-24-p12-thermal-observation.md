# P12 Native inference thermal observation — 2026-10-24

This was a bounded live check on the Native Termux device. It is an observation, not a sustained qualification or a general thermal limit.

Before inference, read-only status reported:

- Vulkan available on `Vulkan0: Adreno (TM) 825`.
- Experimental Hexagon HTP available on `HTP0`, runtime `b11849`, SoC `SM8735`, with silent fallback disabled.
- CPU model `qwen3-0.6b-q4_0` present at the pinned path.
- Approximately 4.6 GiB available memory.
- CPU thermal-zone sensors up to 64.1°C; battery sensor 41.7°C.

One CPU inference used the exact prompt `2 + 2? Reply with one digit.` and an eight-token limit. The pinned model returned `2 + 2 = 4.`, backend `CPU`, `gpu_layers=0`, exit 0, in 2.552 seconds. A sensor sample immediately after the run read a maximum CPU-zone value of 94.4°C, GPU zones at 59.4°C, HTP zones at 71.7°C, and battery at 41.8°C. After 30 seconds without another inference, the maximum CPU-zone value was 65.7°C, HTP zones were 54.7°C, GPU zones were 50.7°C, and the battery sensor read 42.7°C. Available memory then read approximately 4.3 GiB, and no `llama-cli` process remained.

The device thermal-zone labels were read alongside temperatures; the high value came from `cpu-2-0-1`. The battery reading came from the `battery` zone. This short sequence does not establish causality, a hardware throttle point, or sustained behavior. No repeated CPU run and no GPU/HTP inference was started in this check after the high CPU-zone sample. Existing bounded GPU and HTP workload evidence remains in the [P12 live acceleration check](2026-10-24-native-acceleration-live-check.md) and [HTP runtime-integrity follow-up](2026-10-24-p12-htp-runtime-integrity-followup.md). Controlled repeated testing under a cooler, stable device state remains open.
