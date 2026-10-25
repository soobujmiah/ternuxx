# Debian PRoot desktop catalog and Ternux audit

**Date:** 2026-10-25 (UTC)
**Evidence class:** repository implementation plus read-only Native/guest checks
**Ternux reference:** `soobujmiah/ternux` at `9fda63162426f77ee575b5f6729d8799a30f51b7`; audit checkout remote verified as `https://github.com/soobujmiah/ternux.git`.

## Ternux reference audit

The reference installer uses a staged host package, Debian, graphics, audio, launcher, and verification flow. It informed the checklist only; Ternuxx owns its implementation, plans, guest receipts, authenticated PulseAudio endpoint, and UI/service code. Ternux's storage-sharing and anonymous PulseAudio choices were not copied. The reference's Debian/XFCE path does not establish general distro or multi-desktop coverage.

## Ternuxx implementation

Ternuxx now has an allowlisted Debian Trixie desktop catalog for XFCE (`xfce4`), LXQt (`lxqt`), LXDE (`lxde-core`), and MATE (`mate-desktop-environment-core`). The base package group no longer includes XFCE; fresh preview adds packages only for the selected desktop IDs, with XFCE remaining the default only when no selection is supplied. Fresh-install and resume previews accept `--desktops ID[,ID...]`; the selected desktop IDs and package set are bound into the exact plan and persisted in the guest receipt. Unknown, duplicate, or empty selections fail closed. The default remains XFCE. Existing guest replacement remains refused.

The PRoot GUI router accepts `tx pgui start --desktop ID`, checks the guest package inventory before launch, and uses fixed session commands from the catalog. When multiple supported desktops are installed, an explicit ID is required. Shared shortcut synchronization creates Ternuxx-owned Native menu entries for installed desktop sessions. CLI, TUI, Web, and GTK use the shared shortcut service; human reports include each available `tx pgui` launch command.

This provider adapter is Debian Trixie only. Other PRoot distro/rootfs providers, their package groups, graphics/audio integration, and desktop-session commands remain unsupported until they receive their own adapters and tests. The multi-desktop package plans are repository-tested, but only XFCE is currently installed and runtime-verified on this device; LXQt/LXDE/MATE were not installed during this validation.

## Live checks and limits

At 2026-10-25 10:47 UTC, `tx proot setup status --json` reported `fresh_installed`, user `sobuj`, `sudo_mode=passwordless`, and `desktop_environments:["xfce"]`. `tx proot status --json` listed only Debian and no active Ternuxx guest session or host PRoot process. Guest `sudo -n id -u` returned `0`, and the Ternuxx-owned sudoers file passed `visudo`. `tx proot shortcuts sync preview` reported `changed:false`, `desktop_sessions:["xfce"]`, with the existing managed launcher in desired state. A full four-desktop preview resolved the expected packages and exact plan; it did not install those optional desktop packages.

The rootfs contains Mesa Vulkan packages and a pinned Turnip artifact, but these are installation inputs, not proof of accelerated rendering. Native XFCE reports `llvmpipe`. A nested GLES context probe reported Zink/Turnip/Adreno 825, but the nested `xfce4-about` OpenGL drawing-context creation failed and no rendered application workload or screenshot verified Adreno presentation. Therefore no Native or guest XFCE Adreno acceleration is claimed.
