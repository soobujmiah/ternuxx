# Debian PRoot extra desktop cleanup — 2026-10-26

Owner scope: retain route-passing installed desktop environments; remove failed/partial Debian PRoot desktop installs while keeping catalog support for future explicit installs. This operation touched only the canonical `debian` guest package database. Native `:1` and the separate Ubuntu/replay guests were not targeted.

## Pre-state and exact plan

Read-only checks before the package transaction showed Native XFCE running on `:1`, no managed PRoot sessions, standalone `:0` stopped, and nested `:2` absent. The Debian package database showed XFCE, LXQt, LXDE, MATE, and KDE Plasma desktop roots installed. GNOME and Cinnamon package payloads were already removed; 13 residual package configuration records remained. Existing evidence accepts XFCE for the full PRoot desktop routes; the other PRoot environments did not have full route acceptance.

The first `apt-get -s purge --auto-remove lxqt lxde-core mate-desktop-environment-core kde-plasma-desktop` preview listed 411 removals, including `7zip`. The receipt's Debian workstation profile includes `7zip`, so its APT auto/manual marker was corrected to manual before taking the final preview. The saved final simulation is [the exact APT plan](data/2026-10-26-debian-extra-desktop-removal-plan.txt), SHA-256 `fb7bb079a207a849c0880a82416762bed52c94f892151aea56411a921897d571`. It listed 410 removals, no current Ternuxx manifest package, and no package from the 335-entry installed-version receipt. It preserved XFCE. Applying the same command after byte-for-byte simulation comparison returned exit 0.

The 13 residual configuration records were selected by read-only `dpkg-query` as `rc` packages matching the failed GNOME/Cinnamon tests. Their exact APT simulation is [the residual-config purge plan](data/2026-10-26-debian-failed-desktop-residual-purge-plan.txt), SHA-256 `b27f877c7bce9a54fb78e496a866d8947cefb7566cb37ec3ee762a606b20dc8e`. A byte-for-byte recheck preceded application; purge returned exit 0.

## Post-state verification

The Ternuxx package inventory now reports only `xfce` installed and route-launchable. All 335 recorded package names remain installed at their recorded versions; `7zip` remains installed. `dpkg --audit` exited 0 with no findings, and a fresh `dpkg-query` returned no GNOME/Cinnamon residual-config records.

Final lifecycle status: Native desktop remains running, standalone guest `:0` is stopped, nested `:2` socket is absent, and `tx proot sessions list` is empty. No desktop was relaunched after package cleanup, so this is package-state evidence, not a new GUI route or rendering test. Earlier [Debian standalone render evidence](2026-10-26-debian-standalone-render-follow-up.md) and [nested route evidence](2026-10-25-debian-desktop-catalog-extension.md) remain the relevant visual/runtime checks.
