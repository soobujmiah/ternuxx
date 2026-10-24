# Comparable inference benchmark methodology

**Status:** qualification protocol. Existing device results are exploratory until they meet the full controls below. **All benchmarking is opt-in and owner-operated on the physical device.**

## Experimental controls

For a CPU/GPU/NPU comparison, hold constant:

- physical device, Android build, Termux app/runtime, model file SHA-256 and license;
- model architecture, quantization, tokenizer/chat template, prompt token IDs and fixed input corpus;
- context/window, batch size, output length, sampler/seed, thread settings where supported, runtime commit/build flags;
- execution context, display/background state, charging/performance mode, network state, storage location, and warm/cold cache condition.

Only change the backend selection and backend-specific options required to select it. Record every deviation; if hardware/runtime forces different model compilation or quantization, do not call it a direct comparison. Use a CPU run from the same runtime/model whenever possible.

## Run protocol

1. Record a report ID, Git commit, release (or explicitly `unreleased`), device profile, tool versions, model license/hash, runtime configuration and exact command.
2. Verify no other inference workload is active. Record initial Android thermal status/temperature, battery/charging state, free memory and ambient/context notes when available. Do not bypass thermal controls or manipulate device governor.
3. Run one cold model-load test and report model load/initialization latency separately.
4. Run 3 warm-up prompts that match the measured workload shape; discard them from latency statistics but retain failures.
5. Run 10 measured repetitions for a short workload, or at least 5 sustained runs for a longer workload. Fix prompt/input/output token counts. Randomized generation uses fixed seeds where supported; otherwise use deterministic greedy output for correctness and separately record generation performance.
6. Before, during and after every run, verify backend selection from runtime logs/counters, including actual HTP/GPU operation assignment and CPU fallback. If selection cannot be proved, mark backend `UNKNOWN` and do not attribute speed to it.
7. Record temperature/thermal throttling at consistent intervals with an available supported sensor/API; if no reliable method exists, mark it unavailable and do not claim energy or thermal superiority. Let the device return to a documented comparable starting state between backends.
8. Preserve raw measurements, including failed, interrupted, OOM, fallback and crash runs. Report median, minimum, maximum and interquartile range or median absolute deviation; do not select only the fastest run.
9. Run a backend-appropriate correctness validator and compare output/tokenization. For floating-point/model kernels use a documented tolerance or reference metric; for generated text record exact token IDs and deterministic setup where possible.
10. Keep raw data local by default; redact serials, account names, personal paths and prompt data before any public report.

## Metrics

For LLM-style generation, report separately where applicable:

- cold load and backend initialization time;
- TTFT, prompt processing tokens/s, decode tokens/s, total end-to-end latency and requested/actual input/output tokens;
- peak process RSS and backend-reported GPU/NPU memory if trustworthy;
- CPU/GPU/NPU utilization only with a named reliable source; utilization is not proof of correct delegation by itself;
- temperature/thermal state and throttling observations; battery delta only if measurement resolution is adequate;
- selected/offloaded operations/tensors and explicit fallback counts;
- correctness results, error/crash/OOM/cancel counts and output truncation.

For non-LLM workloads, define domain-specific latency/throughput and correctness rather than forcing tokens/s. Never aggregate model performance across different models into one device score without a justified normalization method.

## Machine-readable records and report generation

Store one JSON record per run or a documented CSV plus a report manifest. Minimum schema fields: `report_id`, `run_id`, `source_commit`, `release`, `timestamp_utc`, `operator_type`, `device`, `android`, `termux`, `execution_context`, `runtime`, `runtime_commit`, `backend_requested`, `backend_observed`, `model_id`, `model_sha256`, `model_license`, `quantization`, `prompt_sha256` (not raw private prompt), `input_tokens`, `output_tokens`, `seed`, `warmup`, `duration_ms`, `ttft_ms`, `prompt_tokens_per_second`, `decode_tokens_per_second`, `peak_rss_bytes`, `temperature_source`, `temperature_readings`, `thermal_status`, `fallback_operations`, `correctness_status`, `result_status`, `error_code`, and limitations.

Charts must be generated from accepted machine-readable reports and retain a link to methodology, raw-data file hash, report ID and source commit. Website rendering is read-only; test report is canonical. Do not insert placeholder zero values for unavailable metrics.

## Acceptance status

This protocol defines a qualification bar; it is not itself a test run. P12 contains bounded CPU, Vulkan, and HTP workload measurements for the named device and models, but those checks do not complete the warm-up/repetition, sustained memory/thermal, and clean-install requirements above. No cross-backend result is qualified as a full protocol-compliant comparative benchmark. See [current acceleration evidence](../evidence/2026-10-24-native-acceleration-live-check.md) and the [active P12 gate](../PHASE-STATUS.md).
