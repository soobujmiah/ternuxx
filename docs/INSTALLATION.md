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

Install the `tx` entrypoint with its preview-first installer. This installs a thin command shim under `$PREFIX/bin/tx` that dispatches into the checkout:

```sh
python3 scripts/cli_entrypoint.py preview
python3 scripts/cli_entrypoint.py apply --yes --plan-id PLAN_ID
tx help
```

Keep the checkout at `$HOME/ternuxx`, or set `TERNUXX_CHECKOUT` before using the shim. Preview every requested package and the complete dependency closure:

```sh
tx install preview --verbose
```

The preview shows package versions, APT's full dependency simulation, approximate download and installed sizes from the signed package index, current free space on the Termux prefix filesystem, and a host memory snapshot. Add `--verbose` to see estimates per package. Memory and storage are observations, not guarantees. Review repository origins and the exact `PLAN_ID` before installing:

```sh
tx install apply --yes --plan-id PLAN_ID
```

The transaction refuses removals, upgrades, recommendations, changed plans, and packages outside the official Termux repositories. It installs the current Native CLI dependencies, XFCE/Termux:X11 desktop packages, audio support, `glxinfo`/`vulkaninfo` inspection tools, the official `mesa-vulkan-icd-freedreno` package, and the `proot-distro` runtime. On Adreno/KGSL devices, `tx mng graphics select native termux-zink` can select stock Termux Mesa's Zink path for future desktop starts only after the installed ICD successfully enumerates a supported Vulkan device. This selection is not an acceleration claim: start a fresh Ternuxx desktop and run `tx mng graphics verify native opengl` and `tx mng graphics verify native vulkan`; only a rendered workload reporting the Adreno device counts as verified. `tx mng graphics select native system` returns future starts to the default Termux stack. Tool availability does not qualify a renderer or workload. It does not create a Debian guest. If APT fails or is interrupted, some packages may already have changed: read the error, create a fresh preview for the same profile, and apply only its newly reviewed ID; do not assume the old plan still matches.

For an interactive profile chooser, run `tx install interactive`; it previews the selected profile without applying it. Automated profile selection uses the same dependency resolver and exact-plan apply path:

```sh
tx install preview --profile minimal-native --verbose
tx install apply --profile minimal-native --yes --plan-id PLAN_ID
```

Available presets are `minimal-native`, `full-native`, `graphical`, `developer`, `native-proot-provider`, `native-debian`, and `custom`. `custom` always includes the Native management core; choose from `desktop`, `audio`, `proot`, `graphics`, `developer`, `lxqt`, `mate`, `cinnamon`, and `plasma` with `--components`. The four alternate Native desktop groups resolve to the distro package for that session; XFCE remains the default and GNOME is not packaged in the Native Termux repository. The PRoot-provider preset installs only the provider package. `native-debian` reviews the full Native package plan and fresh pinned Debian guest plan together, then applies Native packages before creating the guest. Only the full-native preset is selected by the legacy `tx install preview` command when no profile is named.

Run read-only checks after installation:

```sh
tx help
tx doctor
tx status
tx proot status
```

Open the Floating Termux:X11 Android app before starting the Native desktop:

```sh
tx start
```

## Create an optional Debian guest

For a combined first-time Native workstation and fresh guest install, preview both plans together. Supply the exact IDs printed by the preview when applying; if the Native profile is already installed, the preview omits its Native plan ID:

```sh
tx install preview --profile native-debian --user NAME
tx install apply --profile native-debian --user NAME --yes --plan-id NATIVE_PLAN_ID --guest-plan-id GUEST_PLAN_ID
```

The combined `native-debian` profile currently uses the selected account password in hidden terminal prompts. Guest-only setup also supports an exact-plan-bound `passwordless` mode without secret input.

For guest-only setup, check `tx proot status` first. Preview the pinned Debian Trixie image, package groups, storage availability, graphics inputs, and exact guest target:

```sh
tx proot setup fresh-preview --user NAME --sudo-mode passwordless --desktops xfce,lxqt
```

If the preview names the intended fresh target and reports no existing guest, apply that plan:

```sh
tx proot setup fresh-install --sudo-mode passwordless --yes --plan-id PLAN_ID
```

Choose `--sudo-mode password` to set a guest-only password through hidden prompts, or `--sudo-mode passwordless` to avoid credential entry. Passwordless sudo applies only inside the PRoot guest; PRoot shares the Native Termux app's Android UID and is not a security boundary. The exact preview binds the choice, and setup validates sudoers before recording package versions. Then inspect and enter the guest:

```sh
tx proot status
tx db
```

The fresh setup flow refuses to replace an existing guest. Debian desktop and graphics acceptance are separate from Native desktop verification; see the [capability matrix](architecture/CAPABILITY-MATRIX.md) and [known limitations](testing/KNOWN-LIMITATIONS.md).

## Interfaces

```sh
tx tui
tx web
tx gui
```

The Web UI binds to loopback and requires its authenticated setup flow. The TUI, Web UI, and GTK center expose only the operations implemented for each client through the shared management service. Check current support in the [capability matrix](architecture/CAPABILITY-MATRIX.md).

## SSH and recovery

Inspect SSH before changing service state:

```sh
tx ssh inspect
```

First-time setup uses `tx ssh deploy` to preview the exact dedicated config and Native Runit service, then applies with `tx ssh deploy --yes --plan-id PLAN_ID`. It binds only to `127.0.0.1:8023`, disables password and keyboard-interactive authentication, and uses `$HOME/.ssh/ternuxx-keys/authorized_keys`. Create a client key with `tx ssh client-key-preview --key-name NAME` and its exact apply command; enroll its `.pub` file with `tx ssh enroll-preview --public-key-stdin < "$HOME/.ssh/ternuxx-keys/NAME.pub"`, review the affected service, then apply the returned plan. `tx ssh inspect` verifies configuration, Runit and the loopback SSH banner; verify login separately with an actual client connection. Other Native SSH configurations remain outside Ternuxx control; its service and authorized keys are dedicated.

For recovery, backup, remote-access, graphics, AI, or audio setup, follow the specific guide linked from the [documentation index](README.md).
