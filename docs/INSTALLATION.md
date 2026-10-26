# Native Termux installation

Ternuxx runs in Native Termux. Debian PRoot is optional and has a separate pinned guest setup flow. A Native package install never creates or replaces a Debian root filesystem.

## Requirements

- A current Termux installation from a compatible source.
- Git and the official `x11-repo` package for the full Native desktop profile.
- The Floating Termux:X11 Android app for graphical sessions; install and open it separately.
- Network access for package indexes and packages. The Debian guest setup also downloads its pinned image and packages.

## Install the Native workstation

For a new checkout or a clean canonical checkout on `main`, run one of:

```sh
curl -fsSL https://raw.githubusercontent.com/soobujmiah/ternuxx/main/install.sh | sh
# or
wget -qO- https://raw.githubusercontent.com/soobujmiah/ternuxx/main/install.sh | sh
```

The [bootstrap](../install.sh) requires an attached Native Termux terminal. It
prepares Git and util-linux only when missing, clones the canonical repository or
fast-forwards a clean `main`, then hands keyboard input to the managed installer.
It preserves dirty checkouts and unrelated existing targets by refusing them. It
does not install the Android Termux:X11 APK. To inspect it first, download the script,
read it, then run it with `sh`.

Run the checkout's managed installer (Python is bootstrapped if missing):

```sh
./tx install
# Compatibility spelling:
./tx install interactive
```

The opening screen reports device model, Android/ABI/kernel, Native runtime,
RAM and prefix storage. Three keyboard-driven profiles follow:

- **Minimal:** Python CLI/TUI/Web management plus Git, SSH, transfer/archive tools,
  editors, tmux, process monitoring, search and clang/CMake/GDB/Make build tools.
- **Native Full:** Minimal plus selectable desktops, audio controls, graphics
  tools and one or more Native XFCE/MATE/Plasma desktops. Optional apps are Firefox,
  Audacious, Ristretto, Evince, Mousepad, Xarchiver and VLC.
- **Native Full + PRoot:** the same Native choices plus the PRoot provider/Xephyr
  and one or more managed Debian Trixie/Ubuntu Noble guests. Each guest presents
  its supported desktop selector and its own pinned preview and confirmation.

Use Up/Down to move, Space to toggle selections and Enter to continue. Single-choice
screens accept the highlighted row with Enter. Esc cancels and restores the terminal.
Lists scroll on small terminals. No profile number, distro ID or DE ID must be typed.
All profiles include CLI/TUI/Web/GTK management and SSH/service management tools;
installing tools does not activate SSH or another server. Usernames and hidden guest
passwords still require text entry. In the complete wizard these, sudo mode, DEs and
apps are collected before the bulk system upgrade/Native package transaction. Only
the Python/repository prerequisites precede collection. Passwords are held in memory
and passed through a private inherited descriptor, never command arguments or logs. On confirmation
screens, Cancel is highlighted by default; move to Continue and press Enter.

Preparation is explicitly confirmed: refresh signed indexes with `pkg update`, enable
`x11-repo` if missing, refresh again and bootstrap Python if missing. A full system
upgrade (`pkg upgrade` equivalent) has a separate APT simulation, confirmation,
exact version pins and transaction journal. Non-official upgrade transactions and
removals are refused. A changed upgrade simulation requires a fresh wizard run.
Skipping/cancelling a required stage stops the wizard; earlier completed transactions
remain installed. This is not an all-or-nothing rollback.

The Native selection then uses the existing exact-plan preview/apply engine (no
unrelated upgrades/removals). The wizard installs the checkout-backed `tx` shim
through its own preview-bound installer and builds the Native GTK center for every
guided profile. Keep the checkout at `$HOME/ternuxx`, or set `TERNUXX_CHECKOUT`.

Native Termux currently has a monolithic `libreoffice` package and no separate
`libreoffice-writer`; Writer-only cannot be installed by this Native catalog. The
wizard reports this limitation and never substitutes the full suite. The matching
Termux:X11 Android app remains a separate installation/open step.

On Adreno/KGSL, the guided flow offers a separately confirmed, probe-gated
`termux-zink` backend selection for future starts. An unavailable Vulkan backend
fails that stage rather than claiming acceleration. Workload acceleration remains
a separate live acceptance check. No desktop or guest GUI starts during installation.

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

Available Native presets are `minimal-native`, `full-native`, `graphical`, `developer`, `native-proot-provider`, and `custom`. For direct managed guest setup, use `tx install debian` or `tx install ubuntu`. Debian Trixie and Ubuntu Noble have pinned profiles. Ubuntu XFCE passed live standalone `:0` and guest-to-Native `:1` checks; nested `:2` remains partial because Xephyr lacks DRI3 for GLX drawing. `custom` always includes the Native management core; choose from `desktop`, `audio`, `proot`, `graphics`, `developer`, `mate`, and `plasma` with `--components`. The two route-verified alternate Native desktop groups (MATE and Plasma) resolve to the distro package for that session; XFCE remains the default and GNOME is not packaged in the Native Termux repository. The PRoot-provider preset installs only the provider package. Most users can run `tx install interactive`, confirm the Native package summary, and choose an optional managed guest; later, `tx install debian` or `tx install ubuntu` starts that guest flow directly. Only the full-native preset is selected by the legacy `tx install preview` command when no profile is named.

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

Ternuxx asks for the guest username and, in an attached terminal, offers the profile's desktops with accepted routes for one-or-more keyboard selection; press Enter to keep the XFCE default. Each choice shows its accepted display routes. It then shows the exact pinned target and asks whether to install it. Confirming applies that same plan; declining leaves the guest unchanged. Ternuxx applies guest configuration with available graphics/audio integration. Password mode prompts in the attached terminal; guest-only `passwordless` sudo is also available. Existing rootfs data is preserved. Separate `preview` and `apply --yes --plan-id ID` forms are available for explicit review and automation. The TUI launches the guided command in its attached terminal. Web offers direct setup after the optional managed-guest scope is granted. GTK opens the guided command in an embedded terminal. Each interface supports catalogued desktop selection; GNOME and Cinnamon currently lack a verified launch route, and Plasma is verified only on standalone :0.

For a non-default guest setup, check `tx proot status` first. You can select guest-only passwordless sudo and (on Debian) multiple desktop environments in the same guided command; Ternuxx still shows the plan and asks before applying it:

```sh
tx install debian --user NAME --sudo-mode passwordless --desktops xfce,lxqt
```

Ubuntu Noble currently provides its pinned XFCE profile only. Live install, standalone `:0`, and guest-to-Native `:1` checks passed; nested `:2` starts XFCE and passes Vulkan/audio endpoint checks but remains partial because Xephyr DRI3/GLX drawing is unavailable. Other distribution profiles are not yet implemented.

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

## Guest desktop shortcuts

```sh
tx pgui               # Debian XFCE when installed; automatic display route
tx pgui xfce4         # alias for xfce
tx pgui mate          # selected installed DE
tx pgui start --alias ubuntu --desktop xfce
```

Auto uses standalone `:0` when the Native desktop is stopped, or nested Xephyr
`:2` inside the verified running Native desktop on `:1`. Existing lifecycle locks
and display-ownership checks remain authoritative. Plasma remains standalone-only;
unsupported nested routes are refused. These shortcuts do not install desktops or
stop the Native desktop. Nested rendering limitations remain documented separately.

## PRoot clean profile and later additions

Minimal now includes the Native `proot-distro` CLI provider; it does not create any
guest rootfs. Each managed guest keeps the existing pinned **base/clean** profile
as its default: selected desktop(s), Mesa CPU rendering libraries, Vulkan/Turnip
setup where device access supports it, and authenticated Native PulseAudio handoff.
This is workstation graphics/CPU rendering configuration, not installation or
qualification of an AI inference model/backend. Workload acceleration and audible
playback still require separate checks.

After choosing guest DEs, select optional apps with arrow keys/Space: browser,
Audacious, Writer-only, Ristretto, Evince, Mousepad, Xarchiver and VLC. The clean
choice adds no optional apps. Debian uses Firefox ESR; Ubuntu uses Epiphany because
Noble Firefox delegates to Snap. Writer requests `libreoffice-writer`, not the full
suite or Calc/Impress. Required shared Writer dependencies are resolved by APT.
Apps are included in the same pinned guest preview before confirmation. Automation
can use `tx install debian preview --user NAME --apps writer,pdf`.

Install additional Native DEs or managed guests later:

```sh
tx install xfce             # Native XFCE (also accepts xfce4)
tx install mate             # Native MATE
tx install plasma           # Native KDE Plasma
tx install proot            # keyboard distro selector
tx install proot debian     # Debian, then DE and app selectors
tx install proot debian xfce # explicit DE, then optional apps
tx install proot ubuntu xfce
```

The PRoot shortcut first previews any missing Native X11/PulseAudio/Xephyr bridge
packages, so a Minimal host can add a guest GUI through the same managed flow.
For a missing guest, these commands use the fresh pinned installer. For an existing
managed Debian Trixie/Ubuntu Noble rootfs, they preview only the requested DE/app
additions; they never replace the rootfs or recreate the account. Existing guest
APT sources and installed versions are bound to the add-on plan; upgrades/removals
are refused. Repeating a fully installed selection is a read-only no-op. The guest
must be idle, and any source/package change invalidates the plan. The default guest
CPU/GPU/audio configuration is preserved during add-on installs. On a fresh host,
run `./tx install` first to prepare the repositories and Python.

## Device-aware graphics and default sound runtime

Every guided profile, including Minimal, installs the Native sound runtime and
graphics/CPU rendering tools by default. Desktop environments remain optional;
installing a runtime never starts an audio service, display server or GUI.
Existing managed Native and guest configuration is preserved by default.

The setup offers Native / PRoot / both backend configuration. Later, open the same
selector directly:

```sh
tx install gpu
```

The scope selector appears before package changes. Native Zink is offered only
when the installed Termux Freedreno ICD actually enumerates a supported Vulkan GPU.
On a clean Native configuration it is the first recommendation after that probe;
existing Native choices stay first when a saved preference exists. System Mesa
defaults remain available without forcing a GPU backend. Backend changes are
confirmed and affect future workloads; no running desktop is restarted.

On readable KGSL devices the guest menu offers the existing pinned managed Turnip/
Zink stack, CPU rendering libraries and authenticated Native audio integration.
A CPU/audio-runtime-only choice preserves existing GPU files. For existing guests,
GPU setup uses the same exact package/add-on plan, manifest hash, KGSL snapshot and
checksum-verified Turnip staging helper as managed setup. Unrecognized existing
driver files are preserved and cause refusal rather than being overwritten.

Guest DE selectors also offer **CLI only / no desktop environment**. GPU-only guest
setup uses this path, so a missing guest can be created without implicitly installing
XFCE. An explicit headless CPU profile is available with
`tx install proot debian none`, then the software/runtime choices, or through
`tx install gpu`. The advanced fresh preview spelling is `--desktops none`.

These steps provision dependencies and configuration. Vulkan enumeration, file
presence, or a successful installer is not proof of rendered acceleration, audible
sound, AI inference acceleration or clean-device reproducibility. Bounded workload
and owner-visible/audio acceptance remain separate checks.


## Installer window, checks and recovery

The guided workstation, desktop, guest-shortcut and GPU setup paths share a terminal
window with a fixed device/CPU/RAM/storage/kernel/runtime header, GPU-node and sound
availability, current stage, elapsed time and next action. Only choices/logs scroll.
Use at least 22 terminal rows. GPU-node access and installed audio packages are
availability hints; verify actual rendering and playback after installation.

Before the guided session changes packages, it acquires a nonblocking installer
lock, requires at least 32 MiB free on the prefix filesystem and checks `dpkg --audit`.
The storage floor only protects basic operation; actual DE/rootfs downloads require
more room and package-manager checks still apply. A competing guided session exits
without stopping the holder. Package-state failures print inspection instructions;
the installer does not automatically repair them or remove guests.

Index/download transport failures can retry at most three times. Guided Native
package application first downloads the exact reviewed versions, then applies with
`--no-download`; APT verifies cached packages. The pinned graphics archive retries
the same URL only and retains checksum/member verification. Signature, certificate,
version or hash failures never select another repository or driver automatically.
A failed Native transaction offers one explicit resume that previews the remaining
current package state and requires confirmation again. No package mutation is blindly
retried. Failed guest transactions retain their journals; use their existing
`fresh-resume-preview` / exact-plan `fresh-install` recovery API rather than deleting
or overwriting a partial rootfs. See `python3 lib/proot_setup.py --help` from the checkout.

After an ordinary success/failure, the guided window writes
`$TERNUXX_STATE_DIR/install-last-result.txt` (default
`~/.local/share/ternuxx/install-last-result.txt`), mode 0600. It contains exit code,
stage, elapsed seconds and architecture, excluding passwords, environment and raw
logs. An interrupted/killed process may not write a final summary. Existing sessions
and guests remain untouched by preflight and lock handling.

## Open setup from management clients

After base `tx` is installed, TUI (`I`), authenticated Web and GTK offer shared
workstation/GPU installer actions. They call the same fixed `installer.open`
operation and open an attached Native terminal; the installer still owns package
preview and confirmation. Web requires `software.manage` and mutation protection.
The Android terminal handoff requires the owner's existing
`allow-external-apps=true` Termux opt-in; see the official
[RUN_COMMAND intent contract](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent).
Ternuxx does not change this setting. Without it, the client reports the fixed
`tx install` or `tx install gpu` command to run manually. A handoff request is not
proof that installation completed. Actual Android handoff/rendered-client acceptance
remains a device check.
