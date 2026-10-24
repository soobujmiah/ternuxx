# P12 Native graphics artifact provenance recheck — 2026-10-24

Phase: `P12` — in progress
Evidence class: read-only GitHub source, release, and workflow metadata
Observed: 2026-10-24 15:03 UTC

## Evidence

The relevant Termux packaging change is [lfdevs/termux-packages PR #25](https://github.com/lfdevs/termux-packages/pull/25). GitHub currently reports it as **open and draft**, with no reviews, based on branch `dev/mesa/freedreno-kgsl` at commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e`. Its description says the build uses Mesa from the author's [`mesa-for-android-container` branch](https://github.com/lfdevs/mesa-for-android-container/tree/dev/adreno-main) with additional Android/Adreno patches.

The associated [Termux package workflow run](https://github.com/lfdevs/termux-packages/actions/runs/36377469447) completed successfully for that commit. GitHub's artifact API currently lists the aarch64 package bundle `debs-aarch64-0219ff84b372c9d38aad4e40f448c20ec3d1588e`, but it is a workflow artifact with expiry `2026-12-27T04:23:02Z`; it is not a stable release asset.

The source repository does publish a separate [Mesa 26.3.0-devel-20260824 release](https://github.com/lfdevs/mesa-for-android-container/releases/tag/mesa-26.3.0-devel-20260824). Its published assets are Debian/Ubuntu/Fedora/Alpine/Void/Arch Linux distributions and a separate Turnip archive; the release provides no Termux aarch64 package. The Debian Trixie archive checksum in its release notes is `c014cf66bdbff96417ee30d34f006cf51df64ae04893d599711b0b6b73b52ccf`. This Linux-container release is not interchangeable with the Native Termux/Bionic package.

## Private Termux package bundle inspection

Read-only inspection of the existing app-private package cache found the original aarch64 Actions bundle `debs-aarch64-0219ff84b372c9d38aad4e40f448c20ec3d1588e.tar` with SHA-256 `8b8f3dfccefd4dc3dba65a0099dc9c3efdfd6afc7f9679f3b92a2b8b781a9353`. The preserved upstream checksum sidecar verified all five `.deb` files (`mesa`, `mesa-dev`, `mesa-opencl-icd-rusticl`, `mesa-vulkan-icd-freedreno`, and `mesa-vulkan-icd-swrast`) successfully with `sha256sum -c`.

The fetched Termux `packages/mesa/build.sh` at the PR head identifies Mesa `26.3.0`, source branch `dev/adreno-main`, source commit `98f3d6229d61452cef80f8563af7c56ae599dc14`, and `TERMUX_PKG_LICENSE="MIT"`. The packaged `mesa` archive contains `share/doc/mesa/license.rst`, which explicitly warns that Mesa has multiple component licenses and directs readers to source-file SPDX identifiers and the upstream `licenses/` directory. The four split packages have no separate copyright/license document path in their package file lists. This package metadata and the general MIT field do not by themselves constitute a complete per-component license inventory or release SBOM.

## Interpretation

The successful device Vulkan work still depends on the experimental Termux package built from an open draft PR. Its preserved local bundle passes its published checksum sidecar, but full component-license/SBOM review is still missing. A separate Mesa GitHub release does not supply a durable Native Termux installer. Do not present the Linux distribution archives or expiring Actions artifact as a supported Native package source. P12 still needs a durable, auditable Bionic-compatible source/build/release path, complete notices/SBOM review, and clean-install replay. No artifact was downloaded or installed during this metadata recheck.
