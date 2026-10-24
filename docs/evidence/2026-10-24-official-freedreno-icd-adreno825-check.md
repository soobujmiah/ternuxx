# Official Termux Freedreno ICD check on Adreno 825

Phase: `P12`

**Observed:** 2026-10-24 13:57 UTC
**Host:** Native Termux, aarch64, Android 16, Redmi Turbo 4 Pro (`25053RT47C`)
**Scope:** Read-only package-index inspection and private archive extraction; no package install, upgrade, or desktop change.

## Package and procedure

The configured Termux main package index offered `mesa-vulkan-icd-freedreno` 26.2.5 for aarch64. Its package metadata gives SHA-256 `79d4328e41b3b40edea91088c7992f5522469c682e44223efb69ef0861903c37`. `apt-get download` fetched that exact archive into a private directory under `$HOME/.local/share/ternuxx/`; `dpkg-deb -x` extracted it there. The downloaded archive hash matched the package-index hash. Only the shared ICD library and its JSON manifest were included.

For the probe, a private copy of the manifest pointed directly to the extracted library. The loader was given that manifest with `VK_ICD_FILENAMES`, and `LD_LIBRARY_PATH` was set to the active `$PREFIX/lib` so the inherited Codex Node library path could not override Termux runtime libraries. No files under `$PREFIX` or graphics-provider state were changed.

## Result

Both `vulkaninfo --summary` and `llama-cli --list-devices` loaded the extracted official ICD but rejected the phone's GPU:

```text
TU: ... device (chip_id = 44030000, gpu_id = 6830) is unsupported (VK_ERROR_INCOMPATIBLE_DRIVER)
```

`vulkaninfo` consequently reported no valid GPUs; `llama-cli` reported `Available devices: (none)`. This directly disproves the official 26.2.5 package as a clean Vulkan installation path for this Adreno 825 device. It does not contradict the separately qualified experimental Mesa 26.3.0-devel artifact, and does not establish compatibility for other Adreno models or later Mesa builds.

The official [Termux Mesa build recipe](https://github.com/termux/termux-packages/blob/master/packages/mesa/build.sh) enables Freedreno with KGSL on aarch64, but that build setting is not a device-support guarantee. An older Termux packaging discussion describes the Freedreno package as supporting Adreno 6xx and 7xx; the direct probe above is the device-specific evidence for this result.

## Qualification impact

P12 remains open. A repeatable, Adreno 825-compatible clean-install/provenance path, sustained resource behavior, broader HTP correctness, and clean-device/release gates remain unqualified. No workload inference or sustained stress run was started with this incompatible ICD.

## Evidence

- Package source: configured Termux main index; package metadata and downloaded archive SHA-256 matched.
- Runtime checks: `VK_ICD_FILENAMES=<private-manifest> vulkaninfo --summary` and `VK_ICD_FILENAMES=<private-manifest> llama-cli --list-devices`, with `LD_LIBRARY_PATH=$PREFIX/lib`.
- Device identifier: Adreno 825, reported `gpu_id = 6830`; both tools returned `VK_ERROR_INCOMPATIBLE_DRIVER` and no usable Vulkan device.
