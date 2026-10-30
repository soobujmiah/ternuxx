# P12 internal candidate handoff verifier

Phase: `P12`

**Status:** Implemented and locally tested. This tool verifies a complete owner-provided internal candidate directory before device qualification. It does not download artifacts, alter the handoff, install a runtime, or grant release clearance.

## Contract

`python3 tools/package_snapdragon_release.py verify-candidate --candidate-dir PATH` requires the exact expected candidate file set. It rejects missing/extra entries, symlinks, non-regular or empty files, malformed or mismatched whole-bundle SHA-256 records, mismatched archive `SHA256SUMS`, and archive/manifest inconsistencies. It checks the two-build reproducibility record against the verified archive and manifest, validates recorded toolchain/source-input/submodule sidecars, and parses both SPDX documents. Its output summarizes package/file counts and license identifiers, including unresolved `NOASSERTION`/`NONE` assertions.

A successful result always has `distribution_cleared: false`. It reports integrity and build-record checks only. Owner/legal review, provenance acceptance, installation and exact-device inference qualification remain separate gates.

The Actions workflow writes `CANDIDATE.SHA256SUMS` after the reproducibility record and runs this verifier before uploading the internal candidate. The archive's existing `SHA256SUMS` remains separate and covers the archive itself.

## Validation

- `python3 -m py_compile tools/package_snapdragon_release.py`: passed.
- `python3 -m unittest tests.test_package_snapdragon_release`: **10 passed**, including valid synthetic candidate, exact-file-set rejection, altered record, malformed SPDX, and archive checksum mismatch cases.
- `git diff --check`: passed.

These are local tool/fixture checks. The real Actions artifact has not been copied into `artifacts/incoming`, so this verifier has not yet checked the production candidate. No device test, thermal qualification, license clearance, public release, or stable status is claimed.
