# Fresh checkout reinstall and desktop route verification — 2026-10-26

Phase: Native/PRoot clean-room rebuild. Evidence class: live Native Termux installation and bounded device route checks. This record does not claim a clean package-manager image or release qualification.

## Checkout and reinstall

A new clone of https://github.com/soobujmiah/ternuxx.git was verified at main, commit ea1a07d57aad1cf96d42c7c4f8bd359639106a54, and made the canonical ~/ternuxx checkout. The previous checkout, including its uncommitted P12 capture fix, was preserved separately. The exact owned $PREFIX/bin/tx shim was removed after owner/type/hash checks, then reinstalled from the fresh checkout with the preview-bound entrypoint installer. tx help, tx status, and tx doctor ran afterward.

The guided full-native installer reported that its packages were already installed; it made no APT changes. Existing Native state, models, artifacts, configuration, and PRoot guests were retained. A read-only purge simulation for the full-native package roots proposed 131 removals, including the accepted Native MATE/Plasma packages and unrelated applications, plus a software-renderer package installation. That broad transaction was not applied. Termux package ownership is shared with other working desktop and Codex tooling, so this reinstall replaced the Ternuxx source/shim and reran the supported install flow without purging shared packages or personal state.

Follow-up removal-scope check: `apt-get -s --no-install-recommends --no-auto-remove remove` with the exact 19 `full-native` package roots still proposed 108 removals and one new package (`mesa-vulkan-icd-swrast`), including Native MATE/Plasma and unrelated applications. Excluding shared `dbus`, `pulseaudio`, `proot-distro`, and `python` from the request still proposed 21 removals, including Plasma packages, and a software-renderer replacement. Individual simulations showed removing `dbus` would remove 100 packages and removing `pulseaudio` would remove 56. These were simulations only; no package transaction ran. The clean package uninstall/reinstall gate remains open because the current APT dependency graph does not isolate all requested Native profile roots from accepted desktops and other installed applications.

## Validation

On the fresh checkout, bash scripts/repo_test.sh passed 1,228 tests in 224.994 seconds and the CLI help contract passed. The Native XFCE session was restarted on :1; graphics checks rendered an OpenGL X11 window on Adreno 825 (score 426), a GLES 3.2 shader draw on Adreno 825 (724 frames in five seconds), and 120 Vulkan X11 frames on Adreno 825. The authenticated Native PulseAudio endpoint was reachable at tcp:127.0.0.1:4713, sink OpenSL_ES_sink.

The receipt-verified Debian replay guest started standalone XFCE on :0. The bounded verifier returned complete: X11 and DRI3 were available, GLX drew 327 frames on Zink/Turnip Adreno 825, Vulkan drawing selected Adreno 825, and Native PulseAudio was reachable. GLES context creation reported Zink/Turnip Adreno 825, but GLES drawing was not verified. The diagnostic reports read_only=false because launcher-profile writes are possible; its safety record showed no guest write command or package/service changes.

The canonical Debian XFCE guest started nested on Xephyr :2 inside Native :1. The bounded verifier returned partial: X11, Zink/Turnip GLES context, Adreno 825 Vulkan drawing, and the Native PulseAudio endpoint passed; Xephyr DRI3 was unavailable and GLX drawing failed. GLES drawing was not verified. The probe reports read_only=false because launcher-profile writes are possible; no guest write command or package/service transaction ran.

## Restored state and limits

After both route checks, Native XFCE and audio were running on :1, the Ternuxx-managed SSH service was restored, standalone :0 and nested :2 were stopped, and no managed PRoot sessions remained. Termux:X11 foreground visibility and audible playback remain unverified. The nested Xephyr GLX/DRI3 limitation remains open. The package-manager environment was already populated before this reinstall; this is a source/shim reinstall and live-route recheck, not a clean-device installation.
