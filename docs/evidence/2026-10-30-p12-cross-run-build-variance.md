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

A second, separate main-branch run [`41004311539`](https://github.com/soobujmiah/ternuxx/actions/runs/41004311539) is now in progress. Cross-run reproducibility remains unproven until that run also passes and its downloaded, verified archive SHA-256 matches the first. This is build reproducibility evidence only, not device inference qualification.

## Release status

The two older archives remain integrity-verified internal candidates, but neither qualifies the corrected build contract. The latest SPDX SBOMs still contain unresolved `NOASSERTION` assertions. No runtime is release-cleared, installed into the app path, or inference-qualified by this report.
