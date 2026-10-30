# P12 HTP candidate with third-party notices: build and isolated installer verification

Date: 2026-10-30

Phase: `P12`

## Reproducible build and artifact integrity

The merged workflow commit `e875553219f75f870ad43edad6275017df6b8e23` completed two independent clean builds and the cross-build comparison in Actions run `41013772891`. Both builds used pinned llama.cpp source commit `0ae0e1976670fac25f4e0ed864df30021accc764` and the pinned Snapdragon builder image. They produced byte-identical archives with SHA-256 `677cc34b02d8f1521c55449532100d2cc15627bfd4916a31faa7dc91e5981f09`, size 45,900,806 bytes.

The downloaded internal candidate passed `verify-candidate`: 24 runtime files; exact runtime SPDX and manifest path sets; all 24 file SHA-256 values match; and the package archive itself verifies. `THIRD_PARTY_NOTICES.txt` is inside the archive, lists nine components, and its hash matches the manifest. The artifact is retained as an internal Actions candidate; it is not a published release. The verifier reports `distribution_cleared=false`.

## Isolated installer check

The exact archive was installed through `npu_inference.install_runtime` into a private temporary state directory under `~/.tmp`. A one-off Python process supplied this candidate's size and SHA-256 as temporary constants; the repository's normal pin was not changed. Preview required no network, the installer extracted 24 files, and every path, size, and SHA-256 matched the candidate manifest. `_runtime_valid` passed; changing one byte in the notice without changing its length caused validation to fail. The temporary state was removed. No model/runtime inference was run, no live Ternuxx state was modified, and the standard installer still points at the upstream archive.

## Thermal and release gates

The preceding NPU preflight (06:35:03 UTC) read CPU 49.2°C, GPU 41.6°C, HTP 43.6°C, and battery 40.55°C. A fresh guarded preflight at 06:36:54 UTC read CPU 49.2°C, GPU 40.8°C, HTP 43.2°C, and battery 40.48°C. The 06:41:28 UTC sample read CPU 50.8°C, GPU 41.2°C, HTP 43.6°C, and battery 41.22°C. The 06:45:04 UTC sample read CPU 50.4°C, GPU 42.8°C, HTP 44.4°C, and battery 41.8°C. The empirical launch ceilings for this check are CPU 50°C and HTP 40°C; all four samples failed at least the HTP limit, and the latest also failed the CPU limit. None started inference. Telemetry rose across the latest samples, so additional preflights were stopped for this session.

The candidate source SBOM still has 227 package and 102 file records with unresolved license assertions; the runtime SBOM has unresolved binary assertions. The source-tree scan includes build and sample metadata, so it is not a list of 227 shipped dependencies. The new notice file preserves the identified vendored notices, but it does not settle each binary's license conclusion, Qualcomm Snapdragon toolchain redistribution terms, or the Ternuxx project license. Device CPU/Vulkan/HTP qualification, normal fresh installation, and rollback remain open. The separate QNN image route also remains unqualified and requires its own license and Android-app integration review.

## Decision and next work

- Reproducibility, archive integrity, notice inclusion, and isolated installer extraction passed.
- No production-ready, stable, or public-release claim is supported.
- Wait for two independent passing thermal preflights; then test this exact artifact on CPU, Vulkan, and HTP with output, telemetry, model integrity, install, and rollback evidence.
- Resolve binary and toolchain licensing and choose the Ternuxx root license before distribution.

## Evidence

The authoritative run is [GitHub Actions 41013772891](https://github.com/soobujmiah/ternuxx/actions/runs/41013772891). The downloaded candidate passed `python3 tools/package_snapdragon_release.py verify-candidate --candidate-dir artifacts/incoming/run-41013772891`. A direct manifest/SPDX comparison found 24 of 24 paths and SHA-256 values equal. An isolated installer exercise verified 24 files and rejected same-size notice tampering. The latest guarded preflight at 06:45:04 UTC returned `ok=false` and `will_start_inference=false`; all four recorded samples failed their gate.
