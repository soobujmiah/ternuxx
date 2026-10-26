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

Keep the checkout at `$HOME/ternuxx`, or set `TERNUXX_CHECKOUT` before using the shim. For normal setup, run `tx install interactive` in the attached Native terminal. Choose a profile, review the short package summary, and answer `y` to install that exact transaction in the same session. Ternuxx then offers optional managed Debian or Ubuntu setup. The normal path does not ask you to copy a plan ID.

The guided transaction refuses removals, upgrades, recommendations, changed plans, and packages outside the official Termux repositories. It installs the selected Native packages; the Termux:X11 Android app is still installed separately. After setup, on Adreno/KGSL devices, `tx mng graphics select native termux-zink` can select stock Termux Mesa's Zink path for future desktop starts only after the installed ICD successfully enumerates a supported Vulkan device. This selection is not an acceleration claim: start a fresh Ternuxx desktop and run `tx mng graphics verify native opengl` and `tx mng graphics verify native vulkan`; only a rendered workload reporting the Adreno device counts as verified. `tx mng graphics select native system` returns future starts to the default Termux stack.

For automation and detailed APT review, preview every requested package and the complete dependency closure:

```sh
tx install preview --verbose
```

The preview shows package versions, APT's full dependency simulation, approximate download and installed sizes from the signed package index, current free space on the Termux prefix filesystem, and a host memory snapshot. Memory and storage are observations, not guarantees. Review repository origins and the exact `PLAN_ID` before applying:

```sh
tx install apply --yes --plan-id PLAN_ID
```

If APT fails or is interrupted, some packages may already have changed: read the error, create a fresh preview for the same profile, and apply only its newly reviewed ID; do not assume the old plan still matches. Automated profile selection uses the same dependency resolver and exact-plan apply path:

```sh
tx install preview --profile minimal-native --verbose
tx install apply --profile minimal-native --yes --plan-id PLAN_ID
```

Available Native presets are `minimal-native`, `full-native`, `graphical`, `developer`, `native-proot-provider`, and `custom`. For direct managed guest setup, use `tx install debian` or `tx install ubuntu`. Debian Trixie is the live-qualified profile; Ubuntu Noble now has its own pinned profile and remains pending device qualification. `custom` always includes the Native management core; choose from `desktop`, `audio`, `proot`, `graphics`, `developer`, `mate`, and `plasma` with `--components`. The two route-verified alternate Native desktop groups (MATE and Plasma) resolve to the distro package for that session; XFCE remains the default and GNOME is not packaged in the Native Termux repository. The PRoot-provider preset installs only the provider package. Most users can run `tx install interactive`, confirm the Native package summary, and choose an optional managed guest; later, `tx install debian` or `tx install ubuntu` starts that guest flow directly. Only the full-native preset is selected by the legacy `tx install preview` command when no profile is named.

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

## Create an optional managed guest

For a fresh managed Debian or Ubuntu guest, run the matching command in an attached Native terminal:

```sh
tx install debian
# or: tx install ubuntu
```

Ternuxx asks for the guest username, shows the exact pinned target, and asks whether to install it. Confirming applies that same plan; declining leaves the guest unchanged. The flow defaults to XFCE and applies Ternuxx guest configuration with available graphics/audio integration. Password mode prompts in the attached terminal; guest-only `passwordless` sudo is also available. Existing rootfs data is preserved. Separate `preview` and `apply --yes --plan-id ID` forms are available for explicit review and automation. The TUI launches the guided command in its attached terminal. Web offers direct setup after the optional managed-guest scope is granted. GTK opens the guided command in an embedded terminal. Each interface supports catalogued desktop selection; GNOME and Cinnamon currently lack a verified launch route, and Plasma is verified only on standalone :0.

For a non-default guest setup, check `tx proot status` first. You can select guest-only passwordless sudo and (on Debian) multiple desktop environments in the same guided command; Ternuxx still shows the plan and asks before applying it:

```sh
tx install debian --user NAME --sudo-mode passwordless --desktops xfce,lxqt
```

Ubuntu Noble currently provides its pinned XFCE profile only; its live install and graphics route still need device qualification.

For automation or a separate review-only step, add `preview`; if the preview names the intended fresh target and reports no existing guest, apply its exact plan ID. Most users should use the guided command above. For example:

```sh
tx install debian apply --user NAME --sudo-mode passwordless --yes --plan-id PLAN_ID
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
