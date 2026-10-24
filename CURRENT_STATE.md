<!-- deterministic-state-bridge: ternuxx -->

# Current Ternuxx state

**Reviewed:** 2026-10-24 12:25 UTC. Ternuxx uses Native Termux as its host and control plane, with Debian PRoot as an optional isolated workload provider. Current phase status and accepted gates are maintained in [phase status](docs/PHASE-STATUS.md); this page records only the current runtime, active work, and release boundary.

## Live runtime

Read-only checks on the Redmi Turbo 4 Pro (`25053RT47C`, Android 16, aarch64; Termux `0.119.0-beta.3`) report the Native XFCE session running on display `:1`; X11 and XFCE process identities reconcile as live, while Android-window visibility remains unknown. Standalone Debian XFCE on `:0` is stopped, and nested Xephyr display `:2` is absent. The Debian Trixie guest and `proot`/`proot-distro` packages are installed. Read-only `tx proot setup status` reports the adopted workstation profile and matching package baseline. The optional terminal broker is installed, running, and matches its source. These checks did not start or stop either desktop.

All recorded Ternuxx PRoot sessions report stopped. A read-only process inventory also observed five defunct `proot` children under the long-running TUI process; their session ownership is unverified. They are zombies rather than executing workloads. The probe launcher now double-forks so future bounded probes are not children of long-lived clients; the focused fixture and full repository tests pass. These five older zombies remain under the active TUI, whose code was already loaded before the source fix; no signal or cleanup was attempted. Full command results and the exact observation are in the [live state reconciliation evidence](docs/evidence/2026-10-24-live-state-reconciliation.md).

## Active work

P11 Debian PRoot source restoration and integration is complete. P12 Native CPU/GPU/NPU workload qualification remains in progress. CPU inference works through the bounded pinned-model path. Vulkan inference has passed short Adreno 825 tests with full layer offload using an experimental Mesa/Freedreno ICD. Experimental HTP0 inference passes bounded SM8735 tests with full offload, but the tested short prompts are slower than CPU. A new single CPU known-answer run passed, followed by a CPU-zone sample of 94.4°C that returned to 65.7°C after 30 idle seconds; no further workload ran in that check. Sustained thermals and memory, broad correctness, clean-install provenance, and release qualification remain open. See the [CPU](docs/testing/CPU-BASELINE.md), [GPU](docs/testing/GPU-ACCELERATION.md), [NPU](docs/testing/NPU-ACCELERATION.md), [P12 live evidence](docs/evidence/2026-10-24-native-acceleration-live-check.md), and [thermal observation](docs/evidence/2026-10-24-p12-thermal-observation.md).

The latest Native Termux runner passed 1,011 Python tests and the CLI help/preview contract in 113.003 seconds. Regression checks cover unique service-operation keys, complete Web-session CSRF/read-only classification, stable NPU plans under changing free-space readings, complete PRoot domain/resource operation coverage, CLI ICD-migration plan routing, and GTK replay-guest lifecycle preview/apply routing. The latest observed GitHub run for clean source `e5f1c5a` failed 41 GTK bridge tests because the Ubuntu test fixture lacked Native Termux variables. The fixture correction is local and verified; GitHub has not rerun it. [.repo status](.repo/STATUS.md) records the latest local pass on a dirty worktree based on `e5f1c5a`; it is not a clean GitHub CI result.

## Release boundary

Internal phase completion does not mean public-release readiness. No project license has been selected; source provenance and license review, a build-specific SBOM, release signing, clean-device qualification, boot recovery, and the owner-reviewed SSH security decision remain open. Do not treat public repository visibility as redistribution permission. See [legal/IP readiness](docs/readiness/LEGAL-IP.md), [security policy](SECURITY.md), and [known limitations](docs/testing/KNOWN-LIMITATIONS.md).

The earlier Web reload/reconnect work remains preserved; its evidence is in the [Web session report](docs/evidence/2026-10-24-web-session-reload-reconnect.md).
