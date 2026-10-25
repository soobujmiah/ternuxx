# Native Termux installation

Ternuxx runs in Native Termux. Debian PRoot is optional and has a separate pinned guest setup flow. A Native package install never creates or replaces a Debian root filesystem.

## Requirements

- A current Termux installation from a compatible source.
- Git and the official `x11-repo` package for the full Native desktop profile.
- The Floating Termux:X11 Android app for graphical sessions; install and open it separately.
- Network access for package indexes and packages. The Debian guest setup also downloads its pinned image and packages.

## Install the Native workstation

Enable the official X11 package source and clone the repository:

```sh
pkg update && pkg install git x11-repo && pkg update
git clone https://github.com/soobujmiah/ternuxx.git "$HOME/ternuxx"
cd "$HOME/ternuxx"
```

Preview every requested package and the complete dependency closure:

```sh
./tx install preview --verbose
```

The preview shows package versions, APT's full dependency simulation, approximate download and installed sizes from the signed package index, current free space on the Termux prefix filesystem, and a host memory snapshot. Add `--verbose` to see estimates per package. Memory and storage are observations, not guarantees. Review repository origins and the exact `PLAN_ID` before installing:

```sh
./tx install apply --yes --plan-id PLAN_ID
```

The transaction refuses removals, upgrades, recommendations, changed plans, and packages outside the official Termux repositories. It installs the current Native CLI dependencies, XFCE/Termux:X11 desktop packages, audio support, `glxinfo`/`vulkaninfo` inspection tools, and the `proot-distro` runtime. Tool availability does not qualify a renderer or workload. It does not create a Debian guest.

For an interactive profile chooser, run `./tx install interactive`; it previews the selected profile without applying it. Automated profile selection uses the same dependency resolver and exact-plan apply path:

```sh
./tx install preview --profile minimal-native --verbose
./tx install apply --profile minimal-native --yes --plan-id PLAN_ID
```

Available presets are `minimal-native`, `full-native`, `graphical`, `developer`, `native-proot-provider`, and `custom`. `custom` always includes the Native management core; choose from `desktop`, `audio`, `proot`, `graphics`, and `developer` with `--components`. The PRoot-provider preset installs only the provider package; guest creation remains a separately previewed operation. Only the full-native preset is selected by the legacy `tx install preview` command when no profile is named.

Run read-only checks after installation:

```sh
./tx help
./tx doctor
./tx status
./tx proot status
```

Open the Floating Termux:X11 Android app before starting the Native desktop:

```sh
./tx start
```

## Create an optional Debian guest

Check `./tx proot status` first. Preview the pinned Debian Trixie image, package groups, storage availability, graphics inputs, and exact guest target:

```sh
./tx proot setup fresh-preview --user NAME
```

If the preview names the intended fresh target and reports no existing guest, apply that plan:

```sh
./tx proot setup fresh-install --yes --plan-id PLAN_ID
```

The attached setup flow asks twice for a guest sudo password using hidden prompts. Type it directly into that prompt; do not place it in shell arguments, environment variables, logs, or files. Setup records package versions and verifies its owned guest configuration. Then inspect and enter the guest:

```sh
./tx proot status
./tx db
```

The fresh setup flow refuses to replace an existing guest. Debian desktop and graphics acceptance are separate from Native desktop verification; see the [capability matrix](architecture/CAPABILITY-MATRIX.md) and [known limitations](testing/KNOWN-LIMITATIONS.md).

## Interfaces

```sh
./tx tui
./tx web
./tx gui
```

The Web UI binds to loopback and requires its authenticated setup flow. The TUI, Web UI, and GTK center expose only the operations implemented for each client through the shared management service. Check current support in the [capability matrix](architecture/CAPABILITY-MATRIX.md).

## SSH and recovery

Inspect SSH before changing service state:

```sh
./tx ssh inspect
```

The managed Ternuxx SSH service targets loopback port 8023 and uses a fixed Native Runit unit. Lifecycle changes require preview and exact-plan confirmation. Port 8022 is a separate owner-managed channel; Ternuxx does not manage that service. Listener ownership and authenticated access must be verified in the current runtime before reporting SSH ready.

For recovery, backup, remote-access, graphics, AI, or audio setup, follow the specific guide linked from the [documentation index](README.md).
