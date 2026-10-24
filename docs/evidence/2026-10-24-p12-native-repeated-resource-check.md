# P12 Native repeated accelerator resource check — 2026-10-24

Phase: `P12`
Gate: PARTIAL — repeated Vulkan runs completed; HTP sequence stopped at its conservative guard.

## Method

The pinned Qwen3 0.6B Q4_0 model ran the same 64-token paragraph prompt through the Ternuxx inference functions, sequentially and in separate bounded child processes. Ten Vulkan calls were requested, followed by ten HTP calls. Every result was checked for nonempty output, successful exit, complete 29/29 layer offload, and (for HTP) disabled silent fallback. Thermal zones, battery, and available memory were sampled before and after each call. The preselected stop guards were CPU/GPU/HTP 60°C, battery 45°C, `socd` 70°C, and minimum `MemAvailable` 2 GiB. These are conservative test guards, not OEM-rated limits. The harness checked between calls; it did not cancel an in-flight inference when a sensor crossed a guard.

## Result

All ten Vulkan runs completed with 55-word output and 29/29 GPU layers on `Vulkan0` / Adreno 825. They took 4.604–6.447 seconds each (48.752 seconds total inference time). Sampled `MemAvailable` stayed at or above 3,676.8 MiB; sampled process RSS peaked at 249,316 KiB. The highest sampled CPU, GPU, and HTP zones were 58.1°C, 55.1°C, and 54.7°C. The sequence returned below those values after completion. This is repeatability/resource evidence for this prompt and profile, not continuous-load qualification.

The first two HTP runs completed with 51-word output, 29/29 HTP layers, a 319.96 MiB model buffer, exit 0, and `silent_fallback=false`. After run 2, the post-call sample reported CPU/GPU/HTP zone maxima of 80.4°C/68.5°C/67.4°C, exceeding the preselected guards. The test did not start run 3. A subsequent read-only check found no remaining `llama-cli`; CPU/GPU/HTP sensor maxima had returned to 54.1°C/48.7°C/49.9°C. This does not establish why the readings changed, prove throttling, or define a device limit. No further inference was started in this sequence.

A separate single-call follow-up added an active 250 ms sampler and sent SIGINT to the Ternuxx CLI process group as soon as the CPU-zone sample reached 61.6°C; GPU and HTP zones were 47.9°C and 53.1°C at that point. The client returned the expected bounded HTP-cancellation error, and exact `pgrep -x llama-cli` plus process-list checks found no remaining inference process. Later idle readings were CPU-zone maximum 45.3°C, GPU 42.0°C, HTP 42.8°C, and `MemAvailable` 5,025 MiB. This confirms the guarded interrupt/cleanup path and a repeated CPU-zone excursion during the tested HTP workload; it still does not establish a hardware limit, throttling cause, or completed inference result.

Machine-readable per-route results and preflight/final samples are in [the raw record](data/2026-10-24-p12-native-repeated-resource.json). The official packaged Vulkan ICD check is separately recorded in the [Adreno 825 compatibility report](2026-10-24-official-freedreno-icd-adreno825-check.md).

## Qualification impact

The tested Vulkan route has repeated medium-output evidence but still lacks prolonged or clean-device qualification. HTP has a concrete resource/sensor guard stop and remains short-run experimental; investigate the observation and broaden model/operator checks only with a reviewed, guarded procedure. The official Termux Freedreno 26.2.5 package rejects this GPU, so an Adreno 825-compatible install/provenance route remains open. P12 remains in progress.

## Evidence

- Native API calls: `cpu_inference.run_inference(..., backend="vulkan", max_tokens=64)` and `npu_inference.run_inference(..., max_tokens=64)`.
- Layer/offload and resource samples: [machine-readable run record](data/2026-10-24-p12-native-repeated-resource.json).
- Process cleanup: after the HTP guard stops, exact process-name checks found no `llama-cli`; readable thermal values returned below the selected guards in later snapshots.
