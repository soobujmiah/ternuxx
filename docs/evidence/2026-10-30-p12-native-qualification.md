# P12 native inference qualification: Qwen2.5 1.5B

Date: 2026-10-30
Phase: `P12`

## Evidence

The pinned Qwen2.5 Q4_K_M model (1,117,320,736 bytes; Apache-2.0) was installed only in Ternuxx private HOME storage. SHA-256 before and after the test sequence was `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`; file mode was `0600`. Each backend attempt began after two passing thermal preflight samples. No thermal override was used. Test guards were CPU/GPU/HTP 60°C, battery 45°C, SoC 70°C, and at least 2,048 MiB available memory; these are conservative test guards, not OEM limits.

- CPU: aborted after 4.497 seconds at CPU 61.2°C; peak `llama-cli` RSS 1,186,356 KiB; no output accepted; no process remained. Not a CPU baseline.
- Vulkan: first call passed known-answer verification with Vulkan0 and 29/29 layers; runtime-reported inference 3.426 seconds; peak RSS 271,644 KiB. Second call aborted at CPU 60.4°C; three-call sequence failed.
- HTP/b11849: one call passed known-answer verification on HTP0 with 29/29 layers and silent fallback disabled; runtime-reported inference 4.335 seconds, runner wall time 7.259 seconds, peak RSS 283,112 KiB. HTP reached 59.0°C, below but close to the 60°C guard. A second guarded call after two new passing preflight samples was cancelled when HTP reached 61.0°C after 7.270 seconds; peak RSS was 222,768 KiB and no process remained. The second call returned no accepted output. Repeat HTP qualification therefore fails.

Full machine-readable samples and cleanup evidence: [CPU](2026-10-30-p12-cpu-qualification.json), [Vulkan](2026-10-30-p12-vulkan-qualification.json), and [HTP initial pass](2026-10-30-p12-htp-qualification.json), [HTP repeat cancellation](2026-10-30-p12-htp-repeat-qualification.json). The report schema has since been adjusted to preserve exact generated output for future runs; the initial reports retain answer verification and word count but not exact response text.

**Decision:** no backend is stable or release-qualified. P12 remains in progress. Next: establish thermal headroom, capture exact output and model/runtime integrity in the report, and pass repeated bounded calls without overriding guards. Clean-install and provenance gates also remain open.

Bengali version: [2026-10-30-p12-native-qualification.bn.md](2026-10-30-p12-native-qualification.bn.md).
