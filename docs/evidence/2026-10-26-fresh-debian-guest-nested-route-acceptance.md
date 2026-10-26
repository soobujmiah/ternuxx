# Fresh Debian guest and nested XFCE route check

**Observed:** 2026-10-25 23:52–23:58 UTC (2026-10-26 Dhaka time) on the physical Redmi Turbo 4 Pro / Android 16, Native Termux host. Repository checkout was `~/ternuxx`, branch `main`; the source revision before this work was `643d3dd`.

## Fresh managed guest

The canonical `debian` guest already existed and was preserved. A separate Ternuxx replay alias, `ternuxx-replay-cleanroom-20261026`, was installed from the exact saved fresh-install plan `22a534a0473b4e70c9c39c8a0ea02c85a6617331e2a895653bb93b4576f36667`, with guest user `sobuj`, Debian Trixie, and XFCE. The install command returned success; its receipt recorded the requested packages and package versions as verified, and Turnip installation as complete. No password was recorded in the repository or output.

`tx proot verify --distro ternuxx-replay-cleanroom-20261026 --guest-user sobuj --display :1 --backend zink` returned `status: complete`:

- X11 and native PulseAudio endpoint were reachable; PulseAudio reported `OpenSL_ES_sink`.
- DRI3 was available. GLES context reported Zink/Vulkan 1.4 with `Adreno 825 (MESA_TURNIP)`.
- Bounded GLX draw completed 586 frames in the initial route acceptance run; a later read-only recheck completed 515 frames with that renderer.
- Bounded Vulkan `vkcube --c 120` draw selected Adreno 825 (`IntegratedGpu`).

The verifier accurately marked its payload read-only while disclosing `read_only: false` and possible launcher profile writes. It changed no packages or services.

## Nested XFCE on :2

Added `tx pgui start --mode nested --desktop xfce --alias ALIAS` for exact receipt-verified Ternuxx Debian Trixie replay aliases. The canonical `debian` alias remains the default. Replay aliases are limited to nested mode; standalone :0 continues to use canonical Debian. The preflight validates the private install receipt, rootfs identity, Debian Trixie release, ordinary account, installed desktop, and accepted route before startup. An unreceipted alias is rejected before state directories are written.

The live command `tx pgui start --mode nested --desktop xfce --alias ternuxx-replay-cleanroom-20261026` started Xephyr `:2` at 752x1155 while Native XFCE remained on `:1`. XFCE session, window manager, panel, and desktop processes were present; six visible X11 windows were returned by `xdotool`. This confirms X11 window creation, not Android foreground visibility or owner visual confirmation.

During that nested session, the shared guest verifier returned `status: partial`:

- X11 reachable; GLES context was Zink/Vulkan 1.4 on Adreno 825 Turnip.
- Bounded Vulkan draw selected Adreno 825 and passed.
- PulseAudio endpoint was reachable and retained `OpenSL_ES_sink`.
- Xephyr did not expose DRI3. GLX draw returned zero frames and is unverified. Do not treat the nested XFCE route as GLX-accelerated.

Ctrl-C ended the nested launcher with exit 130. `tx pgui status` then reported `:2` socket absent, while `tx status --json` still reported Native XFCE running on `:1`; `tx audio status` remained running. No unrelated host service was stopped.

## Validation

`env -u LD_LIBRARY_PATH PYTHONDONTWRITEBYTECODE=1 bash scripts/repo_test.sh` passed 1,199 tests in 199.839 seconds after the receipt-aware inventory change. A 61-test focused run covering diagnostics, management authorization, nested GUI routing, and distro-named guided installation also passed; a targeted fixture proves inventory trusts the exact private receipt release and does not follow a guest `/etc/os-release` symlink. Live `tx proot status --json` lists both canonical Debian and the receipt-verified replay alias without entering the guest or observing PRoot processes. A fresh read-only `:1` verification returned complete: Zink/Turnip GLES, a 515-frame GLX draw, Adreno 825 Vulkan draw, and reachable Native PulseAudio endpoint. `bash -n scripts/proot-gui0.sh`, `git diff --check`, document inventory/link audit (0 broken links), `python3 -m tools.repo_knowledge verify` (0 findings), and the CURRENT_STATE bridge check passed. GitHub Actions for this source revision is pending.

## Remaining gates

- Nested :2 GLX/DRI3 rendering and actual audio playback are not qualified; Android foreground visibility was not confirmed.
- Standalone :0 was not part of this fresh-alias check; prior route evidence is separate.
- Only the Debian Trixie provider is implemented. Ubuntu, Alpine, Arch, Fedora, and Void setup profiles and desktop package/session mappings remain unavailable.
- The replay alias is a separately installed test rootfs and is not listed by upstream `proot-distro list`. Ternuxx `tx proot status --json` now includes it only after validating its private receipt, rootfs identity, and Debian Trixie release; the live read-only inventory returned both canonical `debian` and this alias with no managed sessions or host PRoot processes.
