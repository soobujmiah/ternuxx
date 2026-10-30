# P12 HTP runtime SPDX integrity audit

**Date:** 2026-10-30

Phase: `P12`

## Scope and observed defect

Reviewed the retained internal candidate built from pinned llama.cpp commit 0ae0e1976670fac25f4e0ed864df30021accc764. Its package manifest lists 23 runtime files, including the MIT LICENSE. The generated runtime SPDX document listed only 22 files, omitted LICENSE, and gave all 22 files a placeholder SHA-1 of forty zeroes instead of the per-file SHA-256 values already recorded in the manifest. The source SPDX document separately lists 227 packages whose declared and concluded licenses are NOASSERTION. Those unresolved source assertions remain a release blocker.

The existing runtime archive remains byte-identical and integrity-verified at SHA-256 fde7c7c4643f4df8b38a437231c59dad4516ce7c7bb986971b110a7494b9e356. This audit did not modify that retained candidate.

## Change made

The release builder now normalizes the packaged-runtime SPDX document from the verified package manifest: it binds every packaged file to its manifest SHA-256, adds the omitted LICENSE record with MIT identification, and leaves binary file-license assertions untouched. Candidate verification now requires exact agreement between runtime SPDX filenames and manifest filenames and validates each SHA-256. This improves artifact traceability; it does not clear unresolved source or binary licensing.

## Verification

- Targeted package tests: 14 passed.
- A copy of the retained candidate SBOM was normalized in temporary storage and validated: 23 of 23 files present, 23 SHA-256 entries, LICENSE identified as MIT. The retained source SBOM and candidate archive were not changed.
- Python compilation, repository-state verification, document inventory, and diff whitespace checks passed.
- The pull-request CI and a fresh independent two-build workflow remain necessary to verify the committed build path and new SBOM output.
- No device inference or release qualification was performed.

## Evidence

This change corrects the packaged-runtime SPDX file list and per-file checksums while preserving NOASSERTION results for unreviewed binary/source licensing. It does not make the existing candidate distribution-cleared; that candidate has not been rebuilt with the corrected workflow. Thermal qualification, source-license review, exact artifact device testing, clean installation and rollback remain open.
