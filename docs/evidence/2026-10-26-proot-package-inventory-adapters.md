# PRoot package inventory adapter foundation

A shared `proot_packages` module now reads package state from a fixed allowlist of paths beneath the selected guest rootfs and normalizes installed name, version, architecture, held state, and database digest. The existing dpkg status behavior is used by guest adoption and managed desktop inventory. A parser for Alpine APK's installed database is implemented for future profile use; it is not an Alpine installer or a claim of distro support.

The adapter rejects unknown database types, symlinks in package database paths, malformed package records, and package groups that do not match the selected guest architecture. It retains the legacy `dpkg_status_sha256` output field for current Debian/Ubuntu receipt compatibility and adds a generic package database identity field.

## Verification

- `PYTHONPATH=tests python3 -m unittest test_proot_packages test_proot_setup test_proot_desktops test_proot_desktop_setup test_proot_shortcuts -q` — 68 passed after the final no-follow file-open hardening.
- `env -u LD_LIBRARY_PATH PYTHONDONTWRITEBYTECODE=1 bash scripts/repo_test.sh` — 1,216 passed in 203.242 seconds before that final hardening; the focused suite reran all affected inventory/adoption/desktop/shortcut paths afterward.
- `bash tests/test_cli_help.sh` — PASS.
- APK fixture confirms `aarch64` package selection, wrong-architecture exclusion, package versions, and a stable database digest.
- dpkg fixtures confirm installed-state filtering, held-package reporting, and the legacy digest field.
- Existing desktop inventory and preview-bound desktop setup tests pass through the shared dpkg adapter.
- This change does not create or modify any PRoot guest, Native service, package installation, or display session.

## Remaining cross-distro work

Fresh provisioning and post-install package-version recording still use APT/dpkg-specific commands. Alpine remains unavailable until a pinned base-image and repository transaction adapter, distro package/desktop mappings, graphics/audio handoff, lifecycle, recovery, and live route acceptance are implemented.
