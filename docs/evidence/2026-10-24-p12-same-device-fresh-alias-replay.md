# P12 same-device fresh-alias Debian replay

**Date:** 2026-10-24 (Native Termux, Android arm64)
**Classification:** live device evidence; an isolated fresh-alias setup replay on the existing device. This is not a clean-device replay.
Phase: `P12`

## Evidence

### Setup and guest verification

- Previewed a new alias, `ternuxx-replay-p12-cleancheck`, with plan ID `c06d288c7cf463bb5241d30783d7b72c97de7dc6f1a0fce8c79730bbfc699d76`. The preview named the exact new rootfs target and reported `existing_debian_rootfs_changed=false`; the alias did not exist before apply.
- Applied the previewed setup. It exited successfully, verified the requested 18-package base group, recorded the installed package versions, and installed Turnip files. Turnip runtime/graphics was explicitly not verified.
- The installed guest identified as Debian GNU/Linux 13 (Trixie), version 13.7. An isolated login as `txaudit` succeeded; live `dpkg-query` confirmed all 18 requested base packages installed. The temporary CA file was absent after setup.
- The package-version record was SHA-256 checked (`dd30bd0a4dbf1ed70d2d1bda393973b5e0801c4ea424ea97ede07529ef089d1c`). No password or credential is recorded here. Guest sudo authentication was not verified.

### Rollback-safe cleanup and resulting state

- Previewed retirement of this exact receipt-verified alias, then applied plan ID `d38f86b3c00d7b1b77650fb99dc75cb69ee35fe399e44edc0cf773d4e6c9e4e6`.
- Retirement returned `status=retired` and `files_deleted=false`; the same container directory is retained in Ternuxx's private retired-guest backup and can be restored. Its recorded container inode is `5153266`.
- Post-apply `tx proot status --json` and `proot-distro list -q` report only the pre-existing `debian` distribution. The retired backup and receipt remain present.
- The pre-existing Debian guest and five previously observed zombie PRoot children under the long-running TUI were left untouched. No Termux app, GUI, or owner-managed service was stopped.

This proves a fresh-alias replay on this device against the current package repositories. It does not prove a clean-device setup, sudo credential correctness, Turnip runtime, GUI acceptance, or cross-device reproducibility. The clean-device gate remains open.
