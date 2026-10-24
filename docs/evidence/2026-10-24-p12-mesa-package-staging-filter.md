# P12 Mesa package-staging validation follow-up

**Workflow:** [run 40123636196](https://github.com/soobujmiah/ternuxx/actions/runs/40123636196)  
**Observed:** 2026-10-24 19:25 UTC  
**Pinned build source:** Ternuxx `ae6e68267fea171c58cc6a4290a3b8d11ea37865`; Termux packages `0219ff84b372c9d38aad4e40f448c20ec3d1588e`; Mesa `98f3d6229d61452cef80f8563af7c56ae599dc14`.

## Result

The workflow completed host and target Mesa build-graph capture and uploaded its metadata-only artifact. The following package-staging validation step failed before creating `package-staging-manifests.json`. The log reports 36 staged archives: all five requested Mesa split packages plus 31 dependency packages. The validator had incorrectly required the entire shared staging directory to contain only the five requested packages.

The downloaded artifact contains both host and aarch64 target Meson introspection, Ninja command/target listings, build files, source commit markers, builder image identity, and build metadata. It contains no `.deb` archives or package manifests, as intended by the metadata-only upload policy.

## Local correction

The package-manifest collector now selects the requested package archives from shared staging, records the other staged filenames for audit context, and still rejects missing or duplicate requested package archives. A regression fixture covers dependency filtering and missing-target rejection. The focused Mesa tooling tests pass (6 tests), and the full repository suite passes (1,077 tests, 402 subtests).

The corrected remote workflow has not yet been rerun. Package payload hashes, the five target package manifests, and final source-to-package review remain unverified until that run succeeds.
