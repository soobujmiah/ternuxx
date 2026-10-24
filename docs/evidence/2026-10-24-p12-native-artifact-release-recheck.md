# P12 Native graphics artifact provenance recheck — 2026-10-24

Phase: `P12` — in progress
Evidence class: read-only GitHub source, release, and workflow metadata
Observed: 2026-10-24 14:48 UTC

## Evidence

The relevant Termux packaging change is [lfdevs/termux-packages PR #25](https://github.com/lfdevs/termux-packages/pull/25). GitHub currently reports it as **open and draft**, based on branch `dev/mesa/freedreno-kgsl` at commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e`. Its description says the build uses Mesa from the author's [`mesa-for-android-container` branch](https://github.com/lfdevs/mesa-for-android-container/tree/dev/adreno-main) with additional Android/Adreno patches.

The associated [Termux package workflow run](https://github.com/lfdevs/termux-packages/actions/runs/36377469447) completed successfully for that commit. GitHub's artifact API currently lists the aarch64 package bundle `debs-aarch64-0219ff84b372c9d38aad4e40f448c20ec3d1588e`, but it is a workflow artifact with expiry `2026-12-27T04:23:02Z`; it is not a stable release asset.

The source repository does publish a separate [Mesa 26.3.0-devel-20260824 release](https://github.com/lfdevs/mesa-for-android-container/releases/tag/mesa-26.3.0-devel-20260824). Its published assets are Debian/Ubuntu/Fedora/Alpine/Void/Arch Linux distributions and a separate Turnip archive; the release provides no Termux aarch64 package. The Debian Trixie archive checksum in its release notes is `c014cf66bdbff96417ee30d34f006cf51df64ae04893d599711b0b6b73b52ccf`. This Linux-container release is not interchangeable with the Native Termux/Bionic package.

## Interpretation

The successful device Vulkan work still depends on the experimental Termux package built from an open draft PR. A separate Mesa GitHub release does not supply a durable Native Termux installer. Do not present the Linux distribution archives or expiring Actions artifact as a supported Native package source. P12 still needs a durable, auditable Bionic-compatible source/build/release path and clean-install replay. No artifact was downloaded or installed during this metadata recheck.
