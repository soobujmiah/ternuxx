# P12 Native inference thermal observation — 2026-10-24

Phase: `P12`

## Evidence

This was a bounded live check on the Native Termux device. It is an observation, not a sustained qualification or a general thermal limit.

Before inference, read-only status reported:

- Vulkan available on `Vulkan0: Adreno (TM) 825`.
- Experimental Hexagon HTP available on `HTP0`, runtime `b11849`, SoC `SM8735`, with silent fallback disabled.
- CPU model `qwen3-0.6b-q4_0` present at the pinned path.
- Approximately 4.6 GiB available memory.
- CPU thermal-zone sensors up to 64.1°C; battery sensor 41.7°C.

One CPU inference used the exact prompt `2 + 2? Reply with one digit.` and an eight-token limit. The pinned model returned `2 + 2 = 4.`, backend `CPU`, `gpu_layers=0`, exit 0, in 2.552 seconds. A sensor sample immediately after the run read a maximum CPU-zone value of 94.4°C, GPU zones at 59.4°C, HTP zones at 71.7°C, and battery at 41.8°C. After 30 seconds without another inference, the maximum CPU-zone value was 65.7°C, HTP zones were 54.7°C, GPU zones were 50.7°C, and the battery sensor read 42.7°C. Available memory then read approximately 4.3 GiB, and no `llama-cli` process remained.

The device thermal-zone labels were read alongside temperatures; the high value came from `cpu-2-0-1`. The battery reading came from the `battery` zone. This short sequence does not establish causality, a hardware throttle point, or sustained behavior. No repeated CPU run and no GPU/HTP inference was started in this check after the high CPU-zone sample. Existing bounded GPU and HTP workload evidence remains in the [P12 live acceleration check](2026-10-24-native-acceleration-live-check.md) and [HTP runtime-integrity follow-up](2026-10-24-p12-htp-runtime-integrity-followup.md). Controlled repeated testing under a cooler, stable device state remains open.

## Later read-only temperature check

After source review and the host-like repository suite, `tx ai status`, `tx ai devices`, and `tx ai npu status` again reported the pinned CPU model, Vulkan0 Adreno 825, and experimental HTP0 SM8735 runtime available. A later read-only sysfs sample reported CPU zones up to 68.8°C, GPU zones up to 55.9°C, HTP-related zones up to 59.8°C, `socd` 60.0°C, and battery 42.0°C. No inference was started because the device had not returned to a cool, stable state. These values are a dated snapshot, not a device-wide limit; the sensors do not establish sustained qualification.

## Later bounded repeatability check

At 2026-10-24 19:12 +06:00, a fresh read-only preflight reported the pinned Qwen3 0.6B model, Vulkan0 Adreno 825, and experimental HTP0 SM8735 runtime available. Before inference, CPU zones peaked at 50.5°C, GPU zones at 44.4°C, HTP-related `nsphv` zones at 45.1°C, and battery at 40.9°C. A short CPU run raised the observed CPU-zone maximum to 61.7°C; after 30 seconds idle, readable CPU/GPU/HTP sensor maxima returned to 46.5°C/42.4°C/43.2°C. Testing continued one route at a time.

Two bounded runs per route used the same prompt, `2 + 2? Reply with one digit.`, and eight-token cap. All six returned `2 + 2 = 4.` with exit 0. CPU selected CPU with zero GPU layers (2.639s and 2.749s). Vulkan selected `Vulkan0` and reported 29/29 layers offloaded (2.676s and 3.566s). Experimental NPU selected `HTP0`, reported 29/29 NPU layers, a 319.96 MiB NPU model buffer, and `silent_fallback=false` (4.935s and 5.139s). After the final run, readable sensor maxima were CPU 46.9°C, GPU 44.4°C, HTP-related 45.1°C, and battery 38.9°C. `/proc/meminfo` then reported 4,842,244 kB `MemAvailable` and 9,308,516 kB `SwapFree`.

This establishes repeatable short known-answer execution for the pinned model on these three routes under the observed session state. It does not establish sustained load, peak process memory, concurrent workload behavior, broader model/operator coverage, a clean-install Vulkan ICD path, or HTP release qualification. Sensor labels and readings are preserved as observed; no device-wide thermal threshold is inferred.

## Bounded longer-output generation with live memory/thermal sampling

On 2026-10-24, after a fresh status check reported the pinned model, Vulkan0 Adreno 825, and HTP0 SM8735 runtime available, each route ran one request with a 64-token cap and the same prompt: `Write one coherent paragraph of about sixty words explaining how a local language model answers a question.` The three runs were sequential, each in its own process group with a 60-second wall-clock bound. All exited 0 and returned 51–55 words. CPU completed in 3.880 seconds with backend CPU and zero GPU layers. Vulkan completed in 4.414 seconds on Vulkan0 and verified 29/29 GPU layers. Experimental HTP completed in 22.717 seconds on HTP0 and verified 29/29 NPU layers, a 319.96 MiB NPU model buffer, and `silent_fallback=false`.

During each run, a read-only sampler polled `/proc/meminfo`, thermal zones, and matching `llama-cli` process RSS. Minimum `MemAvailable` was 4,480,056 kB for CPU, 4,113,408 kB for Vulkan, and 4,124,588 kB for HTP. Approximate matching process RSS peaks were 557,900 kB, 256,568 kB, and 184,616 kB respectively; the separate HTP runtime reported its model-buffer size above. Sensor maxima during the CPU run were CPU 72.8°C, GPU 47.9°C, HTP-related 53.1°C, and battery 37.9°C. Vulkan maxima were CPU 52.1°C, GPU 54.7°C, HTP-related 47.5°C, and battery 37.9°C. HTP maxima were CPU 54.4°C, GPU 45.9°C, HTP-related 50.7°C, and battery 37.9°C.

After the CPU run peaked at 72.8°C, the device idled for 30 seconds; before starting Vulkan, sensor maxima had returned to CPU 45.0°C, GPU 40.8°C, and HTP-related 41.6°C. After the later HTP run and another 30 seconds idle, sensor maxima were CPU 44.6°C, GPU 41.6°C, HTP-related 42.4°C, and battery 38.2°C; `MemAvailable` was 4,779,016 kB, and `pgrep -x llama-cli` found no remaining inference process. These three bounded longer-output runs add process/resource observations, but do not qualify continuous sustained load, concurrency, thermal limits, broad semantic quality, or release readiness. The 72.8°C CPU-zone observation is reported without inferring a hardware threshold; no workload ran after the final idle sample.
