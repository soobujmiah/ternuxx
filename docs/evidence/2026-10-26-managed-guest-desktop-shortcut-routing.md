# Managed guest desktop shortcut routing

This source follow-up addresses a route mismatch in the shared Native desktop-shortcut inventory: the old generator found Debian desktops only and emitted a tx pgui command with no guest alias. An Ubuntu XFCE shortcut could therefore not identify its Ubuntu guest.

proot_shortcuts now inventories route-accepted desktops from the canonical Debian Trixie guest and from Ubuntu only after its private Ternuxx receipt/rootfs identity is verified. Each generated launcher is keyed by guest alias and desktop ID, includes --alias ubuntu for Ubuntu, and carries a new ownership marker. Existing v1 Ternuxx desktop launchers remain recognized for exact update/removal and rollback validation. Unknown or receipt-invalid Ubuntu roots are omitted.

The shared shortcut list now reports guest_alias and the matching launch command; CLI help, TUI formatting, and Web presentation distinguish fixed Debian app shortcuts from alias-bound managed guest desktop shortcuts.

## Verification

- PYTHONPATH=tests python3 -m unittest test_proot_shortcuts test_management_service test_management_presentation test_terminal_ui passed 151 tests before the added fail-closed inventory regression.
- PYTHONPATH=tests python3 -m unittest test_proot_shortcuts test_management_presentation passed 30 tests after the alias-bound launcher change and read-only inventory assertion; a 175-test client/GTK/help regression run passed. The completed full suite passed 1,212 tests in 159.420 seconds.
- python3 -m py_compile lib/proot_shortcuts.py lib/management_presentation.py, bash -n lib/help.sh, and git diff --check passed.
- A read-only live proot_shortcuts.list_shortcuts call listed Debian XFCE, LXQt, LXDE, MATE, and standalone-only Plasma, plus receipt-verified Ubuntu XFCE. Its commands selected debian by default and --alias ubuntu for the Ubuntu entry. All six shortcuts were absent; no native launcher was written or changed.

This does not add distro profiles beyond Debian/Ubuntu, qualify new desktop routes, or verify Android foreground visibility or audio playback.
