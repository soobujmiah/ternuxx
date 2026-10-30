# P12 Snapdragon HTP candidate artifact audit

Phase: `P12`

**Status:** The internal Actions artifact from run [`40962919123`](https://github.com/soobujmiah/ternuxx/actions/runs/40962919123) was downloaded into the private project handoff directory `artifacts/incoming` on 2026-10-30. The archive, manifest, reproducibility record and SPDX reports were inspected. No runtime was installed from this artifact and no inference was run.

## Artifact identity and checks

- Candidate name: `ternuxx-p12-htp-reproducible-candidate-40962919123`; artifact ID `12936224523`; Actions run conclusion `success`; artifact expiry `2027-01-27T22:04:01Z`.
- Archive size: 49,219,753 bytes; SHA-256: `f1a6f9ade2dd6b31503bf9b12c87c92a63ef6b043ffb318bf4a4e10692156b29`.
- Pinned upstream source: llama.cpp `b11849`, commit `0ae0e1976670fac25f4e0ed864df30021accc764`.
- `sha256sum -c artifacts/incoming/SHA256SUMS`: passed.
- `python3 tools/package_snapdragon_release.py verify --archive ... --manifest ...`: passed; 23 runtime files.
- The two-build record reports identical archive SHA-256 values and keeps `license_and_device_release_gates_closed: false`.
- The whole-candidate verifier passed after a local receipt checksum envelope was created for the downloaded bundle. The Actions artifact predates the workflow change that produces `CANDIDATE.SHA256SUMS`; this local envelope records the downloaded sidecars and is not claimed as an Actions-generated signature or attestation.

## SPDX findings and limits

Both SPDX documents parse as SPDX 2.3. The source SBOM lists 227 packages and 102 files; all package and file license assertions are `NOASSERTION` (454 package-field assertions and 204 file-field assertions). The runtime SBOM lists one package and 22 files; it likewise has unresolved `NOASSERTION` assertions (2 package-field assertions and 44 file-field assertions). Integrity verification does not resolve these claims or grant redistribution permission. The verifier reports `distribution_cleared: false`.

The candidate remains internal and is not wired into the public installer. It has not been installed or tested on SM8735. Exact-device output, complete offload, repeated stability, thermal behavior, rollback, clean-install, full provenance/license review and owner release acceptance remain open. The artifact is retained in `artifacts/incoming` for the next qualification step; it is not committed to Git.
