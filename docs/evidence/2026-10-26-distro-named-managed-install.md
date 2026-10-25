# Distro-named managed guest install flow

## Behavior

`tx install debian --user NAME` is a short entrypoint to the pinned, preview-first Debian guest installer. It defaults to XFCE and exposes the existing desktop selector, Ternuxx-managed guest configuration, available graphics/audio handoff, and a single guest plan ID. The matching apply form is `tx install debian apply --user NAME --yes --plan-id ID`; password mode continues to prompt only on an attached terminal, and guest-only passwordless sudo remains an explicit alternative. Existing root filesystems are never replaced. Known distro names without a setup profile return a clear unsupported message.

Native workstation installation previews and completion output suggest the optional Debian flow. The TUI, Web, and Native GTK PRoot panels expose the same distro-named command and direct the owner to an attached Native Termux terminal, where the existing hidden-password flow is supported. These are command handoffs; rendered UI interaction and one-click provisioning from the GUI remain unqualified. The old `native-debian` combined installer remains available for users who intentionally want Native and guest plans together.

## Validation

- The focused package-plan, TUI, Web, and GTK contract tests passed (155 tests). The full local repository suite passed 1,187 tests in 215.016 seconds, the CLI help contract passed, and `bash -n lib/phases.sh` passed.
- On the attached Native Termux host, `tx install debian --user sobuj --sudo-mode passwordless` returned `Ternuxx fresh container already exists; only an exact failed-plan resume is allowed`. A following read-only `tx proot status --json` still reported the installed `debian` alias, no managed guest sessions, and no host PRoot processes. No rootfs was changed.
- A non-interactive password-mode apply attempt stopped before password input with a clear attached-terminal requirement. No password was supplied.

## Limits

Only Debian has a pinned Ternuxx setup profile. Ubuntu, Alpine, Arch Linux, Fedora, and Void commands are refused until their distro-specific setup, graphics/audio configuration, and launch routes are implemented and verified. This source milestone does not claim fresh-device installation, rendered GUI launch, or workload-level guest GPU acceleration.
