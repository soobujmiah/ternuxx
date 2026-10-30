# P12 Snapdragon builder and Hexagon SDK licensing evidence audit

Date: 2026-10-30

Phase: `P12`

## Scope and candidate provenance

This audit concerns distribution of the existing Ternuxx internal HTP candidate, not acceptance of a Qualcomm agreement. Candidate run `41013772891` used image digest `ghcr.io/snapdragon-toolchain/arm64-android@sha256:e39e5e9c0957550a92c0de756b7556d81196c7c7f7328ed80de252bfb4878adf`. Its recorded toolchain inventory identifies Android NDK `29.0.14206865` and Hexagon SDK `6.7.0.0`. The archive is 45,900,806 bytes with SHA-256 `677cc34b02d8f1521c55449532100d2cc15627bfd4916a31faa7dc91e5981f09`.

## What the primary sources establish

The upstream [llama.cpp Snapdragon build guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md) identifies the Qualcomm Snapdragon Toolchain registry and says its Android image contains Android NDK, OpenCL SDK, Hexagon SDK, CMake and cross-compilers. The [image source repository](https://github.com/snapdragon-toolchain/docker) describes the images as including SDKs. Its current [Dockerfile](https://github.com/snapdragon-toolchain/docker/blob/main/Dockerfile) installs Hexagon SDK Community Edition `6.7.0.0` from the [snapdragon-toolchain/hexagon-sdk release](https://github.com/snapdragon-toolchain/hexagon-sdk/releases/tag/v6.7.0.0), matching the candidate's recorded SDK version. These current source files are not cryptographically bound to the candidate image digest in its manifest; the candidate's own `toolchain-versions.txt` is the direct evidence for the version actually recorded by that build.

Qualcomm's [Hexagon SDK page](https://www.qualcomm.com/developer/software/hexagon-npu-sdk) identifies the SDK as Qualcomm software and links a Product License Agreement. The [AI Engine Direct SDK page](https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk) also points to a product license agreement. The existence of these pages does not itself establish whether the exact Community Edition terms allow redistribution of build tools, SDK materials, or binaries produced with them.

## Candidate license metadata

The candidate includes llama.cpp's MIT `LICENSE` and `THIRD_PARTY_NOTICES.txt` for nine identified vendored components. The packaged runtime SPDX file still reports `NOASSERTION` for the package and for the built CLI/shared-library file entries; its automated scan is not a license conclusion. The builder inventory records SDK versions and paths, but no Hexagon SDK or toolchain license text or redistribution grant. The repository now has a root `LICENSE` recording GPL-3.0-or-later for original project source; that choice does not license or clear the candidate binaries or Qualcomm toolchain.

Therefore this audit does not establish a public distribution right for the toolchain, Hexagon SDK-derived outputs, or Ternuxx itself. Keep `distribution_cleared=false`; do not publish or pin this candidate in the public installer until the exact applicable terms are reviewed and release permission is recorded; the owner-selected GPL-3.0-or-later applies only to original project source. This report does not accept any terms.

## Next work

- Preserve the exact SDK/toolchain license text and source/version provenance from the original licensee or image publisher without accepting new terms on their behalf.
- Have the authorized licensee/reviewer decide whether the built artifacts may be distributed and record the permitted scope.
- Resolve the Ternuxx root license as an explicit owner decision.
- Independently complete device qualification, normal installation and rollback before describing this candidate as production-ready.

## Evidence

- [GitHub Actions candidate build 41013772891](https://github.com/soobujmiah/ternuxx/actions/runs/41013772891)
- Candidate-local `toolchain-versions.txt`, manifest, source SBOM and runtime SPDX were checked in `artifacts/incoming/run-41013772891`.
