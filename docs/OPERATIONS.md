# Native Termux operations

Ternuxx manages the Android workstation from the Native Termux app. Run `tx help` for the current command list and `tx guides` for interactive setup and recovery guidance. Debian PRoot runs as an optional isolated workload provider, managed from the Native host.

## Core workflow

```sh
tx doctor
tx info
tx start
tx status
tx tui
tx web
tx mng center
```

`tx start`, `stop`, `restart`, and `status` operate on the recorded Native desktop. The supervisor verifies process identity before sending signals and refuses ambiguous ownership. The Android Termux:X11 app's visible state is separate from server readiness.

## Management clients

The CLI, TUI, authenticated Web UI, and GTK center call the same typed management service. Implemented operations share validation, authorization, and state; each client exposes only actions supported in its context. Read the catalog and each command's `--help` output before applying a change. Mutations that affect services, packages, keys, boot state, or recovery require the exact preview and confirmation described by the command.

## SSH and services

`tx ssh inspect` is read-only. Managed SSH configuration and lifecycle changes are scoped to the fixed Native Runit service and use preview/rollback flows. Fixed service-definition deploy/rollback is available in CLI, TUI, GTK, and Web; Web requires an explicit, unchecked-at-login `services.manage` option. Each client reviews an exact preview before apply. The action replaces only the fixed Runit run definition; it does not restart the current daemon, alter SSH configuration, or change port 8022. Ternuxx-managed SSH on 8023 is configured loopback-only and key-only. The separate owner-managed development SSH configuration on 8022 currently reports wildcard binds and password authentication enabled; listener ownership and external reachability remain unknown. Ternuxx does not manage 8022. Review the [security record](../SECURITY.md) before exposing remote access.

Native audio, desktop monitoring, boot profiles, and Wake Lock controls have independent owners and state. A stop operation releases only resources whose identity matches a Ternuxx record.

`tx mng boot helpers status` inspects the two fixed repository-owned Termux:Boot helper files. CLI, TUI, GTK, and Web can preview and confirm deployment or rollback; each deployment keeps a private exact-byte snapshot, and rollback requires selecting the helper's snapshot ID. Web requires the separate opt-in `boot.helpers.manage` session capability. These file reconciliation actions do not run a boot script or prove Android delivery.

The optional Termux:Boot Cron entrypoint starts only the Ternuxx Cron daemon. CLI, TUI, GTK, and Web expose status/validation and exact-preview enable/disable flows; Web requires the separate opt-in `boot.cron.manage` session capability. This does not establish Android cold-boot delivery, which remains unverified.

## Packages and updates

`tx install preview` and `tx install update preview` show the exact Native Termux package transaction. Apply only the reviewed plan ID. If a package operation fails partway, inspect APT output/history and create a fresh preview; Ternuxx does not claim an automatic package rollback.

## Optional Native apps and HOME file handoff

Use tx app list to inspect the curated htop, tmux, and tree catalog. Preview install, update, or removal before applying the saved plan. The TUI, authenticated Web UI, and GTK center use the same service.

When tree is installed, tx app run directory-tree HOME_PATH passes one selected HOME-relative file or directory to the fixed tree executable. It lists names only, is limited to two levels and 32 entries per directory, and rejects paths outside Native HOME, symlinks, special files, and traversal. It does not read file contents or Android shared storage. The TUI, Web, and GTK clients expose the same bounded action.

## Local inference

Run `tx ai status` to inspect the Termux-owned runtime and pinned model. `tx ai setup` guides first use; it does not install Termux packages. Preview model download or removal before confirming it. TUI, Web, and GTK expose the shared inference service with explicit CPU, Vulkan, and experimental HTP actions. Prompts are handled on-device and are not written to Ternuxx logs; the Web interface is authenticated and loopback-only.

CPU runs use four threads, a 512-token context, at most 128 output tokens, one prompt line, and a 120-second timeout. Ctrl-C terminates only the owned inference process group. Ternuxx verifies the pinned model SHA-256 before each run and removes only that fixed model after confirmation. The runtime package remains owned by Termux. Vulkan runs require an enumerated device and complete GPU-layer-offload proof; they fail instead of silently falling back. The experimental NPU runtime is installed only from the exact pinned release into private HOME state; `tx ai npu runtime preview` shows the artifact and storage plan, and apply requires that exact plan plus typed `INSTALL`. HTP inference is gated to SM8735, verifies full delegation, and has no CPU fallback. Do not treat it as a performance improvement: the tested short prompt was slower than CPU. See the [CPU baseline](testing/CPU-BASELINE.md), [GPU qualification](testing/GPU-ACCELERATION.md), and [NPU qualification](testing/NPU-ACCELERATION.md).

## Recovery and backups

`tx backup`, `tx restore`, `tx recovery`, and `tx checkpoint` operate on the private Ternuxx Native state paths. They do not inspect Android shared storage. Checkpoint creation and verification are preview-first and require exact confirmation; verification rejects a checkpoint whose record changes after preview. Recovery refuses symlinks, stale plans, ambiguous process identity, and changed targets. Keep private keys, passwords, bootstrap codes, and unredacted logs out of evidence and Git.

## Debian PRoot guest

Use `tx proot status` for Native-host inventory, `tx proot setup fresh-preview --user USER` to inspect a new Debian install, and `tx proot setup fresh-install --yes --plan-id PLAN_ID` to apply that exact plan. Fresh installation must run in an attached Native Termux terminal; enter the guest sudo password twice in hidden prompts and never place it in command arguments. The installer preserves an existing guest. Use `tx db` for the managed foreground login and `tx pgui` for a separate guest desktop. The observed device has Native `proot` and `proot-distro` plus an adopted Debian Trixie guest.

`tx proot shortcuts list` inspects launcher state. Use `shortcuts preview add|remove APP_ID` before `shortcuts apply add|remove APP_ID --yes --plan-id PLAN_ID`. To synchronize eligible Debian menu applications, run `shortcuts sync preview`, review conflicts and changes, then apply its exact plan. Prior syncs are listed with `shortcuts rollback list`; preview a rollback ID before applying its exact plan. Individual edits and bulk sync share a lock, preserve unmanaged files, and never stop running applications.

The generated Debian application launchers use `tx mng app launch --desktop-id APP.desktop --display :N` to enter the shared typed launcher service. Fixed apps can use `tx mng app launch APP_ID [--display :N]`. Only installed, visible XFCE desktop entries are accepted; arbitrary shell commands are not.

Nested `tx pgui start --mode nested` uses Xephyr display `:2`. It refuses to start if that display is occupied or stale because socket presence does not identify an owner. Do not remove its socket or stop a process unless its exact ownership is established. Startup geometry follows Native display dimensions. The owner has physically accepted portrait and landscape/fullscreen rotation on this device; screen resizing remains dependent on Termux:X11 and its window manager, and no independent capture was recorded.
