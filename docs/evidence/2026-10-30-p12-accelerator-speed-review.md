# P12 accelerator speed review: observed short-prompt results

Date: 2026-10-30
Phase: `P12`

## Scope

This review compares only recorded short known-answer calls on the observed Native Termux device. It does not make a general claim about NPU, GPU, or CPU capability. The two October 29 Qwen2.5 records use the same pinned `qwen2.5-1.5b-instruct-q4_k_m` model, arithmetic prompt suite, and eight-token cap. They are single successful samples and were captured before the later, stricter launch-headroom ceilings.

## Pinned Qwen2.5 1.5B Q4_K_M sample

| Backend | Accepted calls | Runtime-reported inference time | Runner wall time | Delegation and result |
|---|---:|---:|---:|---|
| Vulkan0 | 1 of 3 requested | 3.426 s | 5.050 s | 29/29 GPU layers; known answer passed |
| HTP0 | 1 of 1 requested | 4.335 s | 7.259 s | 29/29 HTP layers, no silent fallback; known answer passed; 1,023.48 MiB HTP model buffer |
| CPU | 0 of 3 requested | 4.497 s before guard cancellation | 4.497 s | No answer accepted; CPU reached 61.2°C |

The one HTP runtime-reported time was 0.909 s (26.5%) longer than the one Vulkan time. The CPU attempt was cancelled and cannot be used as a speed result. These sample counts, unequal thermal starting readings, absent warm-up set, and later stricter launch gate make this exploratory evidence only; it is not a comparative benchmark or release qualification. No token-per-second value was recorded for these one-word outputs.

## Earlier matched Qwen3 0.6B smoke

A 2026-10-24 controlled comparison used the same device, model, prompt, and eight-token cap for three CPU and three HTP runs. CPU elapsed times were 1.727, 1.704, and 2.002 s (mean 1.811 s); HTP times were 4.241, 4.087, and 4.265 s (mean 4.198 s). All CPU and HTP outputs returned the expected answer; all HTP calls reported 29/29 layers with fallback disabled. In this small workload, the HTP mean was 2.32 times the CPU mean. This older result is also workload-specific and does not predict long-form decode throughput.

## Decision and next measurement

Current evidence does not support the expectation that NPU chat inference is several times faster than GPU or CPU. It shows only that HTP delegation works for the recorded calls, with short-prompt latency higher than Vulkan in one Qwen2.5 sample and higher than CPU in an earlier Qwen3 smoke. Model size, prompt length, initialization overhead, and thermal state may change the result; none is isolated by these samples.

After the device has substantial passive cooling and meets the current launch gates, run the [benchmark methodology](../testing/BENCHMARK-METHODOLOGY.md): verify the exact model/runtime hashes, use a longer fixed-output workload, collect three warm-ups and ten measured repetitions per backend with comparable starting conditions, retain cancelled runs, and report prompt/decode tokens per second, end-to-end latency, output correctness, offload, memory, and thermal traces. Do not change the backend priority or claim a speed advantage from these one-off samples.

## Raw evidence

- [Qwen2.5 CPU qualification](2026-10-30-p12-cpu-qualification.json)
- [Qwen2.5 Vulkan qualification](2026-10-30-p12-vulkan-qualification.json)
- [Qwen2.5 HTP qualification](2026-10-30-p12-htp-qualification.json)
- [Earlier same-prompt CPU/HTP comparison](2026-10-24-native-acceleration-live-check.md)

## Evidence

The three October 29 JSON records and the October 24 same-prompt comparison linked above were inspected directly. Calculations in this review are derived from those recorded elapsed times; the raw records remain authoritative.
