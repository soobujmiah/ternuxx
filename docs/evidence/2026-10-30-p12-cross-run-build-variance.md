# P12 cross-run HTP archive variance and build-input pinning

Phase: `P12`

**Status:** A cross-run comparison found that two internally successful reproducible builds produced different archives. This is stronger evidence than the within-run two-builder comparison: one mutable external UI input was observed and has now been disabled in the candidate workflow; a later cross-run rebuild must confirm the fix.

## Observed comparison

Both Actions runs completed successfully and each verified two independent builders against one another:

| Run | Archive SHA-256 | Size | Source commit | Builder image |
|---|---|---:|---|---|
| [`40962919123`](https://github.com/soobujmiah/ternuxx/actions/runs/40962919123) | `f1a6f9ade2dd6b31503bf9b12c87c92a63ef6b043ffb318bf4a4e10692156b29` | 49,219,753 | `0ae0e1976670fac25f4e0ed864df30021accc764` | `sha256:e39e5e9c0957550a92c0de756b7556d81196c7c7f7328ed80de252bfb4878adf` |
| [`40985050416`](https://github.com/soobujmiah/ternuxx/actions/runs/40985050416) | `f2f15c869da065137078f4219a7ee8770816dda91a4d0c19b03ec07f2dc75bbb` | 49,219,269 | same | same |

The manifest runtime inventory differs in one file: `lib/libllama-server-impl.so` (39,865,136 bytes, SHA-256 `a4ffc659d0b782911cd18e498cbebd8e4192cd00c8062df8d5634e39b0fb1544`) versus 39,865,608 bytes, SHA-256 `9fe009c09d5fef8b5e5e5f18df41dc59c48938e6a942e6ee5932333ad5b178ec`. ELF strings in that library show different hashed web-UI assets.

The pinned upstream [UI CMake configuration](https://github.com/ggml-org/llama.cpp/blob/0ae0e1976670fac25f4e0ed864df30021accc764/tools/ui/CMakeLists.txt) enables prebuilt UI assets by default. Its pinned [asset provisioner](https://github.com/ggml-org/llama.cpp/blob/0ae0e1976670fac25f4e0ed864df30021accc764/scripts/ui-assets.cmake) tries a versioned Hugging Face bucket and then falls back to `latest`. The run logs confirm both builds first failed to fetch `b1` and then fetched `https://huggingface.co/buckets/ggml-org/llama-ui/resolve/latest/dist.tar.gz`, embedding 70 assets. This is the observed source of cross-run variability; the within-run comparison alone did not catch it because both jobs fetched the same then-current `latest` contents.

## Corrective build contract

The reproducible workflow was changed to request a CLI-only package: `LLAMA_BUILD_SERVER=OFF`, `LLAMA_BUILD_UI=OFF`, and `LLAMA_USE_PREBUILT_UI=OFF`. The first post-change run, [`40986902773`](https://github.com/soobujmiah/ternuxx/actions/runs/40986902773), failed both Android builds because upstream `LLAMA_BUILD_TESTS` remained on and server test targets still compiled after the server target was disabled; four compile errors reported missing `mtmd.h`. No candidate artifact was produced.

The next run, [`40987954678`](https://github.com/soobujmiah/ternuxx/actions/runs/40987954678), compiled both builders but failed during packaging: the pinned upstream CMake source creates `tools/cli` only inside `if (LLAMA_BUILD_SERVER)`, so disabling the server also removes the required `llama-cli` executable. No candidate artifact was produced. The next correction enables that upstream build switch while leaving the UI, tests, examples, and unified app disabled; the packager still selects only the CLI and required runtime libraries.

The corrected workflow was merged as PR [#10](https://github.com/soobujmiah/ternuxx/pull/10) at `5e3ff398d4fcf6dcd34fa86eab7f982ced03f194`. Main-branch run [`40989392795`](https://github.com/soobujmiah/ternuxx/actions/runs/40989392795) passed both independent builds, byte-identical within-run archive comparison, and candidate verification. The downloaded archive also passed local whole-candidate verification: SHA-256 `fde7c7c4643f4df8b38a437231c59dad4516ce7c7bb986971b110a7494b9e356`, size 45,896,938 bytes, 23 runtime files. Its source and runtime SPDX documents still contain 456 unresolved package-license assertions in total; the candidate verifier correctly reports `distribution_cleared=false`.

A second, separate main-branch run [`41004311539`](https://github.com/soobujmiah/ternuxx/actions/runs/41004311539) also passed both independent builds, the in-workflow comparison, and whole-candidate verification. Its downloaded archive has the same SHA-256 (`fde7c7c4643f4df8b38a437231c59dad4516ce7c7bb986971b110a7494b9e356`) and size (45,896,938 bytes). Both independent run archives were locally verified with the candidate verifier. Cross-run build reproducibility is now demonstrated for this pinned source, workflow, and toolchain; this does not qualify device inference or authorize distribution.

## Evidence

- Corrected main-branch runs [`40989392795`](https://github.com/soobujmiah/ternuxx/actions/runs/40989392795) and [`41004311539`](https://github.com/soobujmiah/ternuxx/actions/runs/41004311539) each passed two independent builds, within-run archive comparison, and candidate verification.
- Both downloaded archives were locally verified at SHA-256 `fde7c7c4643f4df8b38a437231c59dad4516ce7c7bb986971b110a7494b9e356`.
- Candidate installer-shape probe passed in an isolated temporary state directory; static ELF inspection confirmed Android AArch64 host executable and Qualcomm DSP6 HTP modules.
- Recent preflight-only snapshots remain above HTP launch ceiling; the 05:10 UTC sample is [recorded here](2026-10-30-p12-npu-candidate-preflight-6.json) and started no inference.

## Release status

The corrected candidate is reproducible and integrity-verified, but remains internal-only. Both SPDX SBOMs still contain unresolved `NOASSERTION` license assertions, and the Ternuxx project license/provenance review is open. The exact corrected candidate has not been installed into the managed app runtime or inference-qualified. The four recent preflight-only samples (total samples 3–6) on 2026-10-30 04:54, 05:00, 05:05, and 05:10 UTC reported CPU/HTP of 51.2/44.8 C, 50.0/44.0 C, 49.6/43.6 C, and 50.0/43.6 C against launch ceilings of 50/40 C. All correctly started no inference. The existing Qwen2.5 1.5B Q4_K_M model is present under Ternuxx private state, SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`.

The exact candidate archive was also extracted through `npu_inference.install_runtime` into a temporary, isolated state directory with the module’s expected archive size/hash/URL pinned in-memory to the verified candidate and the archive pre-seeded locally. Preview reported `network_required=false`; extraction and `_runtime_valid` both passed; the temporary directory was removed on exit. This validates candidate archive shape against the installer path only: the live managed runtime remains upstream b11849, production source still pins that upstream asset, and the candidate has not been device-run. Static inspection found `llama-cli` is ELF64 AArch64 for Android 34/NDK r29, with five ELF32 Qualcomm DSP6 HTP modules.
