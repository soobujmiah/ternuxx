# Debian GNOME session entry correction

**Observed:** 2026-10-25 19:38 UTC  
**Source checkout:** Ternuxx `main`; Debian desktop packages had already been removed per the owner's cleanup instruction.

Earlier live GNOME diagnostics showed that Debian Trixie's session directory contains `gnome.session` but not `gnome-xorg.session`; the old catalog argv therefore requested a nonexistent session file. Corrected the fixed GNOME argv from `gnome-session --session=gnome-xorg` to `gnome-session --session=gnome` in the shared desktop catalog and both standalone/nested launchers. `XDG_SESSION_TYPE=x11` remains exported by the guest launchers. Added/updated catalog and routing assertions.

The earlier diagnostic with the corrected session name reached GNOME Shell/Mutter processes but did not pass full desktop acceptance. The GNOME package set has since been removed, so this source correction has **not** been rerun against an installed GNOME guest. It fixes the invalid session identifier only; GNOME desktop readiness, GLX/GLES rendering, and Android presentation remain unverified.

Validation after the source change: 18 focused tests in `tests.test_proot_desktops` and `tests.test_proot_gui_routing` passed; `bash -n` passed for `scripts/proot-gui0.sh` and `lib/proot-xfce-wrapper.sh`; no source/test references to `gnome-xorg` remain.
