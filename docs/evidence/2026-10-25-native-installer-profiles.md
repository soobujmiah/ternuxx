# Native installer profile validation

**Date:** 2026-10-25 (Asia/Dhaka)  
**Evidence class:** repository tests and direct Native Termux package previews  
**Source commit before this implementation:** `ff3a52535bf80476425f70a2b5e8e8306fab1f0d`

The Native package installer now offers `minimal-native`, `full-native`, `graphical`, `developer`, `native-proot-provider`, and `custom` profiles. Custom selection accepts only the fixed `desktop`, `audio`, `proot`, `graphics`, and `developer` groups, always including the Native Python management core. Profile selection changes the requested package roots; dependency resolution, repository-origin validation, no-upgrade/no-removal policy, exact saved plan, and apply verification remain in the existing shared APT engine. Interactive mode is a TTY chooser that produces a preview; `--profile` is the non-interactive path.

On the live Native Termux host, `./tx install preview --profile developer --verbose` resolved 11 new packages (including CMake, GDB, Make, and dependencies) exclusively from the signed official `termux-main` index, with zero upgrades and zero removals. The preview was recorded; no package was applied. A live `./tx install interactive` run showed all six choices; selecting Minimal Native Workstation reported the Python core already installed and made no package changes.

`tests.test_package_plan` passed 20 tests, including profile composition, custom allowlist rejection, and a synthetic minimal-profile preview followed by exact-profile apply through the same transaction engine. The full local `env -u LD_LIBRARY_PATH bash scripts/repo_test.sh` suite passed 1,099 tests in 115.512 seconds, and the CLI help contract, document hash/link audit, strict README bridge, and `git diff --check` passed. GitHub validation of these profile changes is pending.

The native-proot-provider profile installs `proot-distro` only; Debian guest creation remains a separate preview-confirmed operation. The requested combined Native-plus-fresh-guest preset, per-package resource estimates, interactive progress/resume reporting, and Bangla installer localization remain open.
