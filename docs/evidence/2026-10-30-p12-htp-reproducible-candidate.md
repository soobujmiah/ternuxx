# P12 HTP reproducible internal candidate verification

**Date:** 2026-10-30
**Phase:** `P12`

## Build and package verification

Two independent clean builds succeeded in workflow `41010520625`. Both used pinned llama.cpp source commit `0ae0e1976670fac25f4e0ed864df30021accc764` and the same builder image. Android ARM64 CPU, OpenCL, and Hexagon HTP runtime compilation, package verification, SPDX generation, and binding runtime file SHA-256 values to the package manifest all passed.

The two independently built archives have the same SHA-256: `fde7c7c4643f4df8b38a437231c59dad4516ce7c7bb986971b110a7494b9e356`. Archive size is 45,896,938 bytes. Candidate verification confirmed 23 runtime files, an exact manifest/SPDX file-set match, and matching per-file SHA-256 values. The candidate is retained as an internal Actions artifact for 90 days; it is not a published release.

The verifier reports `candidate_status=integrity_verified_internal_candidate` and `distribution_cleared=false`. This proves reproducible packaging and file integrity, not permission to distribute or production readiness.

## License evidence limits

The source SPDX scan contains 227 packages and 102 files with unresolved license assertions. This scan covers the full upstream source tree, including build workflows, sample model metadata, and other non-runtime material; the 227 entries cannot be treated as 227 runtime dependencies. Every one of the 23 packaged runtime file SHA-256 values matches the package manifest. Binary license conclusions remain `NOASSERTION`; before distribution, the license review must establish the scope of components actually linked into the artifact. The Ternuxx project license is also still undecided.

## Isolated installer smoke check

The exact candidate archive was passed through `npu_inference.install_runtime` in a one-off Python process using a private temporary Ternuxx state directory under `~/.tmp`. The process supplied the candidate size, SHA-256, and internal source identifier as temporary constants; repository code and the normal runtime pin were not changed. Preview reported no network requirement, installation extracted 23 files, the generated per-file manifest matched all candidate paths/sizes/SHA-256 values, and `_runtime_valid` returned true. The temporary state was removed after verification. No runtime executable was launched, and the live Ternuxx state was untouched. This checks the existing installer mechanics against the candidate archive, not normal fresh-install delivery or backend operation.

## Thermal preflight

Twelve NPU preflight samples were taken without `--ignore-thermal-limits`. None started inference. Every sample failed at least one empirical launch ceiling (CPU 50°C, HTP 40°C):

| Time (UTC) | CPU °C | GPU °C | HTP °C | Battery °C |
|---|---:|---:|---:|---:|
| 05:52:25 | 61.2 | 50.7 | 52.7 | 44.30 |
| 05:53:31 | 54.8 | 47.1 | 49.1 | 44.55 |
| 05:54:49 | 51.6 | 45.1 | 46.7 | 44.30 |
| 05:55:32 | 52.0 | 45.1 | 46.7 | 44.13 |
| 05:56:55 | 54.4 | 47.1 | 48.7 | 44.19 |
| 06:05:22 | 50.4 | 43.2 | 44.8 | 42.44 |
| 06:06:44 | 49.6 | 42.4 | 43.6 | 42.05 |
| 06:07:40 | 50.0 | 42.4 | 43.6 | 41.86 |
| 06:08:50 | 49.2 | 42.4 | 43.6 | 41.75 |
| 06:10:07 | 49.6 | 42.4 | 44.0 | 41.81 |
| 06:10:33 | 49.6 | 42.4 | 43.6 | 41.64 |
| 06:12:47 | 50.0 | 42.4 | 44.8 | 41.53 |

The latest sample (06:12:47 UTC) still fails because HTP is above its launch ceiling. No thermal guard was relaxed, and no inference or new backend test was run.

## Decision and next work

- This internal candidate passed reproducibility and file-integrity verification.
- It is not yet stable, production-ready, or approved for release.
- Review licenses against the components actually built and packaged, separately from the full source-tree SBOM; resolve binary `NOASSERTION` values and select the project license.
- Do not run CPU/Vulkan/HTP inference until two independent thermal preflight samples pass. Then use this exact archive to qualify CPU/GPU/HTP output, telemetry, model integrity, installation, and rollback.
- The Qualcomm QNN image route remains separate and unresolved pending applicable license acceptance, app integration, and device qualification.

## Evidence

GitHub Actions workflow 41010520625 completed successfully with all three jobs successful. The downloaded internal candidate passed `python3 tools/package_snapdragon_release.py verify-candidate --candidate-dir artifacts/incoming/run-41010520625`; the verifier reported an identical two-build archive digest, 23 runtime files, and `distribution_cleared=false`. Twelve fresh thermal preflight invocations failed the launch headroom requirements and started no inference.

Phase: `P12`
