<!-- deterministic-state-bridge: ternuxx -->

# Current Ternuxx state

**Reviewed:** 2026-10-24 14:02 UTC. Ternuxx uses Native Termux as its host and control plane, with Debian PRoot as an optional isolated workload provider. Current phase status and accepted gates are maintained in [phase status](docs/PHASE-STATUS.md); this page records only the current runtime, active work, and release boundary.

## Live runtime

Read-only checks on the Redmi Turbo 4 Pro (`25053RT47C`, Android 16, aarch64; Termux `0.119.0-beta.3`) at 2026-10-24 13:52 UTC report the Native XFCE session and Termux:X11 live on display `:1`; process/display evidence reconciles, while Android-window visibility remains unknown. No standalone Debian XFCE or Xephyr process for `:0`/`:2` was observed. `tx proot status --json` reports only the existing Debian distribution installed; the same-device fresh-alias replay test is retired into a private backup and did not replace that guest. These checks did not start or stop a desktop or guest.

All recorded Ternuxx PRoot sessions report stopped. A read-only process inventory also observed five defunct `proot` children under the long-running TUI process; their session ownership is unverified. They are zombies rather than executing workloads. The probe launcher now double-forks so future bounded probes are not children of long-lived clients; the focused fixture and full repository tests pass. These five older zombies remain under the active TUI, whose code was already loaded before the source fix; no signal or cleanup was attempted. Full command results and the exact observation are in the [live state reconciliation evidence](docs/evidence/2026-10-24-live-state-reconciliation.md).

## Active work

P11 Debian PRoot source restoration and integration is complete. P12 Native CPU/GPU/NPU workload qualification remains in progress. The pinned Qwen3 0.6B route and Termux llama.cpp runtime are available; Vulkan0 enumerates Adreno 825 and the experimental b11849 HTP0 route targets SM8735. The managed API still accepts only the pinned model. Ten repeated 64-token Vulkan calls completed with 29/29 layer offload; minimum sampled `MemAvailable` was 3.6 GiB. A parallel HTP sequence stopped after two calls when post-run CPU/GPU/HTP sensor readings crossed conservative test guards; those readings do not establish a hardware limit or throttling. CPU 20-run evidence already exists. The current indexed Termux Freedreno ICD 26.2.5 was hash-verified and privately extracted, then rejected Adreno 825 (`VK_ERROR_INCOMPATIBLE_DRIVER`), so it does not provide a clean install path for this device. The experimental ICD still lacks a supported clean-install/provenance path; broader HTP model/operator correctness and release qualification remain open. See the [CPU](docs/testing/CPU-BASELINE.md), [GPU](docs/testing/GPU-ACCELERATION.md), [NPU](docs/testing/NPU-ACCELERATION.md), [repeated resource check](docs/evidence/2026-10-24-p12-native-repeated-resource-check.md), [official ICD check](docs/evidence/2026-10-24-official-freedreno-icd-adreno825-check.md), and [P12 live evidence](docs/evidence/2026-10-24-native-acceleration-live-check.md).

GitHub Actions run [40100129084](https://github.com/soobujmiah/ternuxx/actions/runs/40100129084) passed on source `eda1adecadc157c1c37a2bb1d304730d3b7f3b97`: repository verification, strict README bridge validation, 1,017 Python tests in 35.653 seconds, CLI help/preview contract, and deterministic-state synchronization. The latest documentation-focused local checks also passed feature-matrix and phase-doc tests, document/link/hash audit, strict README bridge validation, and `repo_knowledge verify`. The earlier GitHub fixture failure is historical and has been superseded by successful CI runs; [.repo status](.repo/STATUS.md) holds the machine-generated result.

## Release boundary

Internal phase completion does not mean public-release readiness. No project license has been selected; source provenance and license review, a build-specific SBOM, release signing, clean-device qualification, boot recovery, and the owner-reviewed SSH security decision remain open. Do not treat public repository visibility as redistribution permission. See [legal/IP readiness](docs/readiness/LEGAL-IP.md), [security policy](SECURITY.md), and [known limitations](docs/testing/KNOWN-LIMITATIONS.md).

The earlier Web reload/reconnect work remains preserved; its evidence is in the [Web session report](docs/evidence/2026-10-24-web-session-reload-reconnect.md).
