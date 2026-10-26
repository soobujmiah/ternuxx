# GTK profile driven PRoot installer choices

Date: 2026-10-26 (Asia/Dhaka)

The Native GTK Management Center no longer carries its own Debian/Ubuntu and desktop option lists. At startup, it requests the read-only `proot.setup.catalog` operation through the shared management service. The bridge emits structured `D`/`E` records; GTK validates identifiers and populates the distro dropdown and per-distro desktop checkboxes. A failed or malformed response leaves the install controls disabled. Desktop route labels come from profile metadata; entries with no verified launch route are marked `launch route unverified`.

The installer passes the selected profile alias and selected desktop IDs to the existing guided `tx install` path. This UI change does not install packages or alter existing guests.

Evidence collected in the Native Termux runtime:

- `python3 scripts/management_desktop_bridge.py proot-install-catalog` returned Debian Trixie and Ubuntu Noble profiles. Debian exposed XFCE, LXQt, LXDE, MATE, Plasma, GNOME, and Cinnamon; Ubuntu exposed XFCE. The bridge labeled GNOME/Cinnamon as unverified and showed route metadata for the other entries.
- The GTK client compiled with `clang -O2 -Wall -Wextra` and GTK 4/VTE GTK 4 pkg-config flags; its `--self-check` reported GTK 4.24.1 and a successful native management client build.
- The focused management-center UI contract and desktop-bridge tests passed (87 tests); the full repository suite passed (1,222 tests).
- A 4-second GTK startup smoke test under `Xvfb` stayed alive without startup errors. The built GTK window also launched on the active Native Termux:X11 `:1` display and stayed alive for 3 seconds without GTK startup errors. The window contents were not visually inspected and no controls were activated. Package installation and desktop launch behavior were not exercised.
