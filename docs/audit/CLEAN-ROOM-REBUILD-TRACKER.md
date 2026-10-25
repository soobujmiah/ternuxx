# Clean-room Native workstation rebuild

**Milestone opened:** 2026-10-25  
**Repository:** `soobujmiah/ternuxx`  
**Starting commit:** `038316c9125f21ea7b7e5d2379832926b09016b5` (`main`)  
**Recovery point:** `snapshot/2026-10-25-clean-rebuild-baseline`

This tracker follows the owner-authorized clean-room workstation mandate. It records observed state and open acceptance separately; source support or an old runtime observation does not prove a clean installation works.

## Baseline observed

- The checkout remote is `https://github.com/soobujmiah/ternuxx.git`; the initial `main` tree was clean.
- The host is Native Termux `0.119.0-beta.3` on the Redmi Turbo 4 Pro (`25053RT47C`), Android 16, `aarch64`. `DISPLAY` was unset. No PRoot distribution was installed; `tx proot status --json` reported `status: none` after the host packages were installed.
- The first repository test run could not import PyYAML in two test modules. After installing the declared `requirements-dev.txt` dependency, `env -u LD_LIBRARY_PATH bash scripts/repo_test.sh` passed: 1,087 tests; `bash tests/test_cli_help.sh` passed. Test output was captured under Termux's private temporary directory, not committed.
- The first `tx install preview` failed closed because the official Termux:X11 package index was absent. The documented bootstrap (`x11-repo` installation and package-index refresh) fixed that prerequisite.
- The reviewed Native package transaction added 125 packages, downloaded 86.7 MB, and reported 504 MB installed size, with zero upgrades and removals. It completed through the exact saved-plan apply workflow; current CLI syntax is `tx install apply --yes --plan-id PLAN_ID`. A second exact Ternuxx plan installed `mesa-demos` and `vulkan-tools` plus `glu`/`freeglut`: 5.2 MB download, 56.7 MB disk, zero upgrades/removals. Native CLI/help, Doctor, and PRoot inventory commands ran afterward.
- A targeted installer regression showed `--verbose` was consumed by the global parser and did not reach the installer. The installer now inherits the global verbosity value; the focused test passes and the live `tx install --verbose` path prints the package versions and complete APT simulation.
- First live desktop start found the required `$PREFIX/tmp/.X11-unix` directory absent. Ternuxx now creates it only beneath the verified owned Native temp root, with mode `0700`, and refuses symlinked/foreign paths. Live `tx start --json` then verified XFCE and Termux:X11 on `:1`; the owner confirmed the XFCE desktop is visible in Floating Termux:X11. This is owner visual observation; no screenshot was retained.
- Clean-install audio startup found `$HOME/.config/pulse` and its cookie absent. The lifecycle now safely creates private `0700` config directories and an exclusive `0600`, 256-byte random cookie, preserving existing cookies and refusing symlinked/unsafe paths. Twelve targeted Pulse lifecycle tests pass. Live `tx audio start/status --json` reports Ternuxx-owned authenticated loopback audio ready on `127.0.0.1:4713`, sink `OpenSL_ES_sink`.
- The owner opened the GTK Management Center through `tx mng center` in Floating Termux:X11 and confirmed the window was visible and category interaction worked. This verifies GTK launch/rendering plus one basic navigation path by direct owner observation; it does not verify every control, error path, accessibility, or narrow-screen layout. No screenshot was retained; see the [owner check record](../evidence/2026-10-25-gtk-management-center-owner-check.md).
- Latest live `tx proot status --json` reports no installed guest. The current exact preview is pinned to `debian:trixie-20261005`, targets the `debian` alias and `sobuj` guest user, and uses plan `2e0a13024567c3a5085a7a9855e066a6a6fc0eb51157355294df485f96a0c82d`. The owner said they will apply it locally; the hidden sudo password must be typed only into the Native terminal prompt.
- Read-only SSH inspection found an existing wildcard/password-enabled config on port 8022, with listener ownership unavailable. The Ternuxx-managed 8023 config does not exist. After simulating exactly `runit` and `termux-services`, both were installed with zero upgrades/removals. All four pre-existing Runit units had `down` markers; no `runsvdir`/`runsv` process was started. Inspection now sees Runit available but 8023 service status/config unavailable. No SSH config, listener, key, or service was changed.
- After installing official inspection tools, `DISPLAY=:1 ./tx doctor --graphics --json` found OpenGL `llvmpipe (LLVM 21.1.8, 128 bits)` and Vulkan initialization reported no drivers. This proves software OpenGL is currently selected for this Native X11 context and no Vulkan driver is available to the default loader. No benchmark or sustained workload was run; acceleration and thermal qualification remain open.
- The latest `env -u LD_LIBRARY_PATH bash scripts/repo_test.sh` passed 1,104 tests in 123.594 seconds after adding the package resource estimator, capacity preflight, and failed-transaction journal tests; `bash tests/test_cli_help.sh`, `python3 tools/audit_documents.py --check`, and `git diff --check` passed. The resource-estimate commit passed CI run [40179434997](https://github.com/soobujiah/ternuxx/actions/runs/40179434997); the latest failed-transaction journal update is awaiting CI. CI run [40177494173](https://github.com/soobujmiah/ternuxx/actions/runs/40177494173) exposed one fixture-only failure: a Pulse cookie test placed its file directly under the temporary root, which is writable by the Termux user but correctly rejected when the CI parent is shared `/tmp`. The fixture now builds a private `.config/pulse/cookie` path matching production. Corrected GitHub Actions run [40177830891](https://github.com/soobujmiah/ternuxx/actions/runs/40177830891) passed all 1,096 tests in 38.677 seconds, and both validation and state-sync jobs succeeded. The installer-profile commit `f9ab7ca6613a4babc483466ea6c759bb3fe653f8` passed GitHub Actions run [40178757853](https://github.com/soobujiah/ternuxx/actions/runs/40178757853): 1,099 tests in 37.360 seconds, CLI help contract passed, and both validation and state-sync jobs succeeded. The document inventory records 547 documents, with the read count verified by the latest inventory audit, and zero broken local links. These repository checks are not live rendered UI acceptance.
- Ternux and ADT README files were read as style references. Local clones were absent; authenticated GitHub metadata confirmed the canonical repositories.

## Acceptance gates

| Gate | State | Evidence / next action |
|---|---|---|
| Reproducible Native bootstrap | In progress | Native package transaction, desktop, and audio now work with no guest. Record a repeatable end-to-end recipe and verify recovery from interrupted install. |
| Native core independent of a guest | Verified for live CLI/desktop/audio baseline | CLI/Doctor, visible XFCE `:1`, and authenticated audio `127.0.0.1:4713` work while `tx proot status` reports no guest. Other Native workflows remain open. |
| Interactive and automatic profiles on one engine | Partly implemented; guest bundle and finish/recovery reporting open | `tx install interactive` and `--profile` share the same preview-bound APT resolver. Profiles: `minimal-native`, `full-native`, `graphical`, `developer`, `native-proot-provider`, and allowlisted `custom` groups. The Native `developer` profile was live-previewed with 11 new packages, zero upgrades/removals, and official `termux-main` origins; it was not applied. The interactive chooser selected the already-installed minimal profile without package changes. `native-proot-provider` installs the runtime only; there is no one-step combined guest preset yet. The preview now estimates archive and installed sizes per package from exact APT metadata and reports current prefix-filesystem free space plus a host memory snapshot; `developer` live preview estimated 22.4 MiB download and 134.8 MiB installed payload. The installer records `applying` and `failed` outcomes if APT returns an error and directs the owner to review a fresh profile plan before retrying. In-transaction progress/resume UI and Bangla localization remain open. See [Native profile evidence](../evidence/2026-10-25-native-installer-profiles.md). |
| Fresh Debian guest through Ternuxx | Previewed, not installed | Exact pinned Trixie image and base package plan exists. Installation needs the owner to enter a sudo password in the hidden terminal prompts. Do not treat an existing guest as evidence. |
| Native/guest separation | Source-audited, live acceptance open | Validate isolation after fresh guest creation and check that guest setup leaves Native settings intact. |
| Shared CLI/TUI/Web/GTK service layer | Source/tests pass; Native desktop and basic GTK interaction owner-verified | The owner confirmed GTK Management Center is visible and category interaction works in Floating Termux:X11. Web visible acceptance and broader client journeys remain open. |
| Critical UI outcomes and error handling | Open | Exercise complete user journeys in each supported client; source rendering or HTTP 200 is insufficient. |
| Managed SSH on loopback 8023 | Partly prepared; service open | Runit/termux-services are installed; no supervisor, SSH config, key, or daemon was started. Add a preview-confirmed 8023-only config/host-key setup path, then verify authenticated readiness. Keep unrelated 8022 configuration untouched. |
| Graphics selection, qualification, safe fallback | Partly verified | Current Native X11 reports software OpenGL llvmpipe and Vulkan loader reports no drivers. Hardware KGSL presence is not qualification. Driver selection, representative render, fallback recovery, and guarded thermal evidence remain open. |
| Optional application catalogue | Source/tests present; live route audit open | Verify candidates in Native and guest against current signed package indexes and runtime compatibility. |
| Security, resource limits, recovery | Open | Audit current paths and exercise bounded failure/recovery cases without weakening guards. |
| Concise fresh-install documentation | Implemented for existing English docs | README and `docs/INSTALLATION.md` now cover a short Native setup and optional pinned Debian flow. No separate Bangla installation guide exists in this repo to keep in sync. |
| Automated and live-device acceptance | Partly verified | Full suite passed 1,104 tests locally; CLI help, document hash/link audit, README bridge, and `git diff --check` pass. GitHub Actions run [40178757853](https://github.com/soobujiah/ternuxx/actions/runs/40178757853) validated installer profiles, and [40179434997](https://github.com/soobujiah/ternuxx/actions/runs/40179434997) validated resource estimates; CI for the newest recovery-journal change is pending. Native desktop visibility, basic GTK launch/category interaction, audio readiness, and graphics diagnostics are live-checked. Fresh guest, broader GTK/Web journeys, SSH 8023, and performance gates remain open. |
| Reproducible performance/resource measures | Open | Measure install, startup, idle, service and graphics workloads with timestamps, versions, and thermal boundaries. |
| Final evidence report | Open | Report starting/final commit, install/test/device/UI/guest/security/performance results and exact residual limitations. |

## Current implementation change

The package preview's global `--verbose` flag now reaches `nt_cmd_install`, so a user can review the resolved APT transaction through the public `tx` command before applying it. Regression tests cover this path. Native XFCE on `:1` is live and owner-visible; Native Ternuxx PulseAudio is authenticated and ready on loopback. No Debian guest was created, managed SSH did not start, and hardware acceleration remains unqualified.

## Session commands

```sh
env -u LD_LIBRARY_PATH bash scripts/repo_test.sh
bash tests/test_cli_help.sh
./tx doctor --json
./tx proot status --json
./tx ssh inspect --json
```

Re-run status and capability checks after each significant configuration change. Keep shared Android storage out of all discovery and test paths.
