# CPU inference baseline

**Product status:** `PARTIAL`, not release-qualified. **Device candidate:** bounded manual and shared-service workload verified on one profile. **Commercial class:** `FREE_CORE` target; not a commercial or release approval.

## Current evidence

Ternuxx now has a pinned, bounded Native CPU model lifecycle and run path through CLI, TUI, authenticated loopback Web, and GTK. The Termux `llama-cpp` package remains externally managed. A direct manual device qualification first demonstrated the candidate Native path: Termux `llama-cpp 0.7.0` with a pinned Qwen3-0.6B Q4_0 model produced a deterministic marker on CPU and a two-repeat `llama-bench` sample. The manual runtime/model qualification is in the [P6 CPU candidate audit](../evidence/2026-10-24-native-cpu-inference-candidate-audit.md); current product behavior and device smoke are in the [CPU workflow evidence](../evidence/2026-10-24-native-cpu-inference-workflow.md). The package and 429 MB model are installed only in this owner device profile; the model is not part of the repository or a Ternuxx installer.

The product path verifies the local model hash before each run, bounds CPU threads/context/output/time, handles process cancellation, and serializes operations on the model. GPU evidence is recorded separately: the official Termux Vulkan backend package and selected experimental Mesa ICD passed bounded Adreno 825 model runs; these runs do not change the CPU baseline or qualify GPU release support. A later single CPU known-answer run passed, but an immediate CPU-zone sample reached 94.4°C before returning to 65.7°C after 30 idle seconds; this is one device observation, not a throttle threshold. See the [P12 thermal observation](../evidence/2026-10-24-p12-thermal-observation.md). Do not repeat workloads until the device is in a cooler, stable state. The Termux package recipe for 0.7.0 declares MIT; the upstream project documents a Native Termux CLI path. The Termux runtime lifecycle remains package-manager-owned and is not managed by Ternuxx. Remaining gates include clean-install replay, broader correctness, network-isolated offline confirmation, sustained memory/thermal behavior, and release provenance review. The observed package came from the configured Dan Yael Termux mirror, not the Termux primary host; see the exact mirror and source evidence in the [candidate audit](../evidence/2026-10-24-native-cpu-inference-candidate-audit.md). The cited package/model versions are dated candidates, not a promise that future package indexes or model refs remain unchanged.

## Free-core acceptance

CPU remains the dependable fallback and must not require premium entitlement or network access. Before calling it supported, an authorized implementation must prove:

1. An approved runtime/model pair installs from an auditable source and its applicable licenses are recorded.
2. A named model loads, tokenizes, executes and returns output under a bounded memory/context configuration.
3. A deterministic correctness fixture passes (tokenization, known prompt behavior or runtime reference test as appropriate); quality impressions are not the correctness test.
4. Model/runtime errors, insufficient memory, cancellation, and unsupported formats fail clearly without leaving stale processes/files.
5. CPU execution is explicitly selected/observed; no hidden GPU/NPU delegation contaminates the baseline.
6. The same model/hash and inputs are measured with the protocol in [benchmark methodology](BENCHMARK-METHODOLOGY.md).
7. The local code path uses installed artifacts without a cloud route; device-level network isolation must still be verified before making a tested-offline claim. No telemetry or mandatory account is required.

Ternuxx product status is `PARTIAL`. The pinned workflow and current device smoke do not satisfy broad support qualification. Do not generalize the two-run sample or publish it as a product performance promise; do not promise model quality or support for other model sizes.
