# Native Termux installation and upgrade guide

Ternuxx manages Native Termux as the host/control plane and supports an optional Debian PRoot guest. Host package changes use a saved, preview-first transaction; guest creation uses a separate pinned image preview and explicit confirmation.

## Install

Enable the Termux X11 package repository, install Git, clone Ternuxx, and inspect the Native package transaction:

```sh
pkg update && pkg install x11-repo git && pkg update
git clone https://github.com/soobujmiah/ternuxx.git "$HOME/ternuxx"
cd "$HOME/ternuxx"
./tx install preview
```

Review the exact package and dependency plan, then apply only its saved plan ID:

```sh
./tx install apply PLAN_ID
```


## Optional Native AI inference

`tx ai runtime preview cpu|vulkan|opencl` runs a read-only Termux apt simulation for the selected llama.cpp backend package set; it never installs packages. `tx ai status` inspects the Termux-owned `llama-cpp` runtime and Ternuxx's pinned local model. If the runtime is absent, first review `apt-get -s install llama-cpp`; package installation remains a separate Termux package-manager action and is never performed by Ternuxx. After the runtime is available, `tx ai setup` offers the exact pinned 429 MB model preview and requires you to type `DOWNLOAD` before fetching it. The model file is checked against its fixed size and SHA-256 before it is installed under private Ternuxx state.

Use `tx ai model preview` to review the model URL, destination, license, required storage, and hash without network access. `tx ai run` defaults to bounded CPU inference. `tx ai devices` lists Vulkan inference devices reported by llama.cpp; when one is available, `tx ai run --backend vulkan` targets it and fails unless the run log proves GPU-layer offload. `tx ai runtime preview vulkan` simulates the exact `llama-cpp` plus `llama-cpp-backend-vulkan` Termux package transaction. Termux supplies a version-matched prebuilt Vulkan backend, so a custom source build or Ternuxx GitHub release asset is unnecessary for this device. On the observed device, `llama-cpp-backend-vulkan` 0.7.0 is installed from the configured Termux package repository, `tx ai devices` reports Adreno 825, and the pinned-model Ternuxx route proves 29/29 GPU-layer offload. For a clean installation, review the simulation and install the version-matched package with the Termux package manager before running inference. The matching OpenCL package is available, but the current device reports no OpenCL platforms and Ternuxx has no OpenCL run path. Model downloads need network access; inference uses the local model file. Network-isolated CPU inference has not yet been verified on-device. See the [CPU baseline](testing/CPU-BASELINE.md) and [graphics and GPU inference qualification](testing/GPU-ACCELERATION.md) for current evidence. An experimental SM8735-only HTP0 route is available with `tx ai npu status`, a reviewed `tx ai npu runtime preview`, and exact-plan `tx ai npu runtime apply --plan-id PLAN_ID --confirm INSTALL`; bounded runs use `tx ai run --backend npu` and require full HTP offload with CPU fallback disabled. It uses an official SHA-256-pinned MIT llama.cpp Snapdragon artifact in private HOME state and does not copy Android vendor/system libraries. The tested short prompts are slower than CPU, and sustained memory/thermal behavior and clean-device installation remain unqualified; see [NPU qualification](testing/NPU-ACCELERATION.md).

The transaction refuses removals and upgrades. To preview upgrades of installed Ternuxx core packages:

```sh
./tx install update preview
./tx install update apply PLAN_ID
```

Update refuses removals, downgrades, and packages outside official Termux repositories. The matching Termux:X11 Android app must be installed separately for a desktop.

## Optional Debian PRoot guest

First preview and apply the Native host packages; this installs `proot-distro` but does not create a Debian rootfs. Then create a fresh Debian plan for the named guest account:

```sh
./tx proot setup fresh-preview --user USER
./tx proot setup fresh-install --yes --plan-id PLAN_ID
```

Read the full preview before applying it. It pins the Debian image and repository snapshot, lists the package groups and storage estimate, and refuses to replace an existing guest. The apply asks for and verifies a guest password without saving it. After setup, inspect `./tx proot status`, then open the owned foreground login with `./tx db`. `./tx pgui` is a separate optional desktop path. On the observed device, `proot`/`proot-distro` and Debian Trixie are installed; this exact fresh-install flow is for a missing guest. Check `tx proot status` first. The transaction refuses to replace an existing guest.

## First checks and desktop

```sh
./tx help
./tx guides
./tx doctor
./tx info
```

Open the Termux:X11 Android app, then start the Native desktop:

```sh
./tx start
```

For interactive management, use `./tx tui`, `./tx web`, or `./tx mng center`. Each client uses the shared service; supported actions can vary by client. See the [capability matrix](architecture/CAPABILITY-MATRIX.md).

## GTK management center

The optional GTK center builds with `clang`, `pkg-config`, `gtk4`, and `libvte` (VTE GTK4). The installer checks these dependencies and does not install them. Its Debian terminal uses VTE to run the fixed `tx terminal start` command; closing the terminal detaches without stopping the guest.

## Native SSH and recovery

`./tx ssh inspect` reports Native SSH state. Managed SSH lifecycle actions use preview and confirmation. The product service is loopback-only on port 8023; port 8022 is a separately owner-managed repository-work channel.

`./tx backup`, `./tx recovery`, and `./tx checkpoint` show private Native state backup and recovery guidance. Checkpoint preparation and verification show a preview and require typed confirmation in an interactive terminal; with JSON mode they return only the plan. Read the exact target and plan before applying a change. Ternuxx does not scan shared storage or manage arbitrary files.

## Optional Native apps

The separate curated catalog currently offers htop, tmux, and tree. Use `tx app list`, then preview the exact install plan before applying it. After installing tree, `tx app run directory-tree HOME_PATH` provides a bounded, read-only HOME path listing. It does not access shared storage or read file contents. See the [software catalog](SOFTWARE-CATALOG.md) for source and safety details.

## Current limits

The current device is already configured; this is not a clean-device reproduction claim. Package candidates can change over time, and the saved preview is not an offline artifact mirror. GPU and NPU routes remain experimental and device-specific; sustained qualification, rollback, supported-device coverage, and public release each require separate evidence. The Native package plan includes `proot-distro`; the Debian rootfs uses a separate exact-image preview and confirmed install. Review the saved rootfs target before applying it.
