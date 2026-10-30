<!-- deterministic-state-bridge: ternuxx -->

# Current Ternuxx state

**Reviewed:** 2026-10-30. Ternuxx uses Native Termux as its host and control plane, with managed Debian and Ubuntu PRoot profiles as optional isolated workload providers. Current phase status and accepted gates are maintained in [phase status](docs/PHASE-STATUS.md); this page records only the current runtime, active work, and release boundary.

## Native AI P12 model and guarded accelerator checks — 2026-10-30

The app now pins Qwen2.5-1.5B-Instruct Q4_K_M (1,117,320,736 bytes, Apache-2.0) and the exact file is present in Ternuxx private model storage with its pinned SHA-256. Vulkan passed one 29/29-layer call; its repeat was cancelled at CPU 60.4°C. HTP/b11849 passed one 29/29-layer call, but two separate repeats were cancelled: first at HTP 61.0°C, then at CPU 60.8°C despite HTP remaining at or below 51.1°C in captured samples. Two CPU attempts were also cancelled before accepted output; the latest reached CPU 67.6°C after 4.585 seconds. No thermal limits were bypassed; no backend is stable/release-qualified. Machine-readable run and current model/runtime integrity evidence are linked from [the P12 qualification report](docs/evidence/2026-10-30-p12-native-qualification.md). The qualification runner also requires empirical launch headroom (CPU: 40°C for CPU, 45°C for Vulkan and 50°C for NPU; GPU/HTP launch ceilings 50°C/40°C respectively), based on previously observed sensor rises; these are test margins, not OEM limits. A fresh CPU-only preflight at 52.8°C failed the new 40°C start gate without launching inference. The reusable runner now records exact output and model/runtime fingerprints and refuses to start on integrity failure. The pinned b11849 reproducible builder retains a 90-day internal Actions candidate only; it has no permanent public runtime release asset. Public distribution stays blocked by unresolved repository license/provenance, Mesa component licensing, and clean-install qualification. Current P12 next actions and evidence are in [phase status](docs/PHASE-STATUS.md).

The latest NPU preflight pair failed its empirical launch headroom gate: HTP measured 45.1°C and 46.3°C against the 40°C ceiling; CPU rose from 48.5°C to 54.4°C and also exceeded its 50°C ceiling in the second sample. No inference process started. The recorded CPU rise means further accelerator testing should wait for fresh passing samples. See the [NPU headroom recheck](docs/evidence/2026-10-30-p12-npu-headroom-recheck.json).

A third no-inference NPU sample at 00:00:31Z showed CPU 52.4°C and HTP 45.9°C. CPU cooled by 2°C from the prior sample but both launch ceilings still fail; no inference started.

A fourth preflight at 00:03:10Z still measured CPU 52.4°C and HTP 45.1°C, so both NPU start ceilings fail and no inference ran.

## Blender Native GUI authoring and GPU MCP — 2026-10-28

The open Native Blender 5.2.2 GUI on `:1` now has a startup `bpy` bridge and
Codex MCP tools to queue agent-written scene scripts into the visible viewport.
A temporary cube create/remove round trip passed in the existing GUI; the display
was returned to 3D View. The Native GPU and explicit llvmpipe paths each rendered
one 64×64 EEVEE smoke frame. `/sdcard/Blender` is writable for project output.
These are single-device smoke checks on the experimental KGSL/Freedreno provider,
not a sustained production qualification. Full procedure, raw responses, hashes
and limits are in the [Blender MCP report](docs/testing/reports/2026-10-28-blender-native-gpu-mcp.md).

## PRoot X11 endpoint loss and managed stop recovery — 2026-10-28

The owner reported that after exiting Termux, the standalone PRoot `:0` screen
remained visible but opening an XFCE terminal and logging out did not work.
`tx pgui stop` refused because it classified the record as failed; the recorded
supervisor and guest/X11 processes were still live while the `:0` display
endpoint artifacts were absent. Its failed-session path only accepted an
orphaned supervisor with a ready display, so its recovery preconditions could
not match this state. `tx stop` is the separate Native `:1` lifecycle and did
not stop the PRoot `:0` session.

`tx pgui stop` now routes this case through the exact recorded supervisor when
its process identity and UID are verified. The supervisor then performs its
existing scoped cleanup of its recorded desktop and X11 groups. The stricter
orphan recovery path remains in place when the supervisor is absent. The live
Native `tx` entrypoint delegates to this checkout, so no separate package copy
was needed. `bash -n` passed; the patched `tx pgui stop` stopped `:0`, and both
`tx pgui status` and the session inspector confirmed all recorded processes
absent and state `stopped`. Native `:1` remained stopped, as it already was
before this repair. A later live persistence check launched both `tx start` and
`tx pgui start --mode standalone` from short-lived shells. After each launching
shell exited, the corresponding X11 socket, supervisor and desktop processes
remained ready; `tx stop` and `tx pgui stop` then cleanly stopped their own
sessions. This verifies survival of the launching shell exit on this device, not
Android force-stop/OS process eviction or visual foreground state. The exact
Android event that caused the earlier endpoint to disappear was not captured.
See the [incident and recovery evidence](docs/evidence/2026-10-28-proot-x11-endpoint-loss-recovery.md).

## Stopped desktop inspection when the X11 socket directory is absent — 2026-10-28

I asked Codex to repair `tx start` and check `tx pgui` after both reported unknown
session ownership. The Native and standalone PRoot records were stopped, their
recorded processes were absent, and the matching display locks were absent; the
Termux temporary `.X11-unix` directory had also been removed. The shared session
classifier treated that clean stopped state as unknown, blocking Native startup
and PRoot status. It now treats a missing socket directory as absent only when
that display's lock is absent; a surviving lock remains ambiguous and is
preserved. Live Native `tx start` then succeeded on `:1`, and `tx status` verified
the supervisor, Termux:X11 and XFCE process identities. I then stopped Native
`:1` and started standalone Debian XFCE on `:0`; `tx pgui status` passed its
shell, window-manager, panel and desktop-process checks, and `xdotool` found eight
visible X11 windows. This confirms windows are mapped in the X server. The
Termux:X11 Activity launch was accepted, but foreground Activity state could not
be read because Termux lacks Android's `DUMP` permission; Android screen
visibility remains unverified. The Ctrl+Alt+Delete shortcut did not open a dialog.
I then sent `xfce4-session-logout --logout --fast` through the verified guest
session bus: the helper exited 0, PRoot status became stopped, and the session
record ended stopped with `xfce session exited with status 0`. This verifies XFCE
logout teardown, but not that the Android Activity was foreground or that the
shortcut dialog itself rendered. After that PRoot check, Native `tx start` was
repeated and the same session-bus logout helper exited 0 for the verified Native
`xfce4-session`. `tx status` then showed the supervisor, Termux:X11 and XFCE absent;
`tx pgui status` still showed the standalone guest stopped. This confirms the same
logout teardown behavior on both routes. The fixture suite also checks that a
natural XFCE session exit makes the supervisor stop its exact X11 group.

## Termux:X11 Activity launch and installed server compatibility — 2026-10-28

The owner reported that `tx start` claimed the Native desktop was running while the
Termux:X11 app showed no desktop. `tx gui` did not request the Android Activity; it
only opened the GTK management center. The launch flow now requests the Termux:X11
Activity after `tx start`, when an already-running desktop is verified, and through
`tx gui`. Standalone PRoot `:0` also requests the Activity after desktop readiness
and when brought forward; nested Xephyr `:2` stays inside the existing Native `:1`
window and does not open a separate Activity. Failed Activity requests include the
official Termux:X11 release page. Activity acceptance still does not prove visible
rendering.

A trial based on current upstream docs added the X11 `-tag` option. The installed
Native `termux-x11` rejected it (`Unrecognized option: -tag`); both the Native
`:1` and standalone PRoot `:0` startup logs recorded `Termux:X11 exited before its
display socket became ready`. That option was removed to preserve compatibility
with the installed package. The owner retried `tx stop`, which preserved the session/log records while stopping
the exact recorded process group. The current session records are `failed` with no
X11 socket/process remaining. No assistant cleanup was performed. Re-run after CI
passes to verify server startup and Activity foregrounding on this exact installed version.

## Responsive Native and PRoot app windows — 2026-10-28

Managed Native, standalone PRoot, and nested PRoot sessions now start a
session-owned X11 window-bounds watcher. It keeps oversized app windows reachable,
requests maximize only for oversized non-transient windows, and restores the saved
window size when the current work area can contain it again. Nested Xephyr also
tracks Native display geometry and requests RandR framebuffer resizing after
orientation changes. Native fresh desktop plans include `xdotool` and
`xorg-xprop`; managed guest desktop plans include `xdotool` and X11 utilities.
Source and static syntax checks are complete; on-device portrait/landscape visual
acceptance remains open and active sessions were not restarted.

## Cross-profile PRoot policy and desktop route coverage — 2026-10-28

The window-fitting watcher and X11 tool dependencies apply across every accepted
Native, standalone PRoot, and nested PRoot desktop route; the watcher does not
depend on XFCE-specific APIs. The PRoot install catalog is intentionally limited
to pinned Debian Trixie and Ubuntu Noble profiles. Debian GNOME/Cinnamon entries
without accepted launch routes were removed from install choices. Ubuntu's
reviewed package policy now holds `snapd` during fresh setup and before every
preview-bound desktop/app addition, verifies the hold, and rejects transactions
that would add the unsupported package. Ubuntu continues to offer Epiphany instead
of Snap-backed Firefox; Debian retains Firefox ESR. Other upstream proot-distro
images remain unavailable until complete distro adapters and live qualification
exist. Native/PRoot orientation visual acceptance remains open.

## PRoot desktop defaults and concise launch output — 2026-10-28

Fresh/add-on guest setup now seeds VLC's XCB X11 video output and carries the
selected XFCE wallpaper into standalone and nested per-session configuration.
Existing guest wallpaper takes precedence; otherwise setup copies the current
Native XFCE wallpaper only when its image is available inside the Termux home.
The same defaults are repaired when an account is provisioned and on XFCE start.
Normal `tx pgui` output reports the selected desktop and display plus the X11
launch request; graphics/audio setup details remain available through dedicated
checks instead of repeating on every successful launch.

## Native media packages and nested GUI lock follow-up — 2026-10-28

Native optional software now includes Blender 4.5 through the signed TUR
repository, enabled only after explicit selection/consent and scoped to that
reviewed package transaction. Blender is intentionally not installed as part of
this source change. VLC uses the GUI-enabled `vlc-qt` catalog package; prior device
checks observed a VLC PulseAudio sink input and synthetic video window on Native
`:1`, but do not establish audible speaker output or Android Termux:X11 visibility.
The Native `audacity` package is absent on this device, so guest Audacity menu
availability must not be described as a Native install result.

A reported lifecycle lock was traced to a live `tx pgui start --mode auto` child
of the Codex managed app-server, not a stale file or a Termux:Boot hook. The owner
denied starting it; the exact process group was interrupted on request and released
its own lock. `tx pgui status` then reported standalone `:0` stopped and nested `:2`
socket absent; Native `:1` was left running. `tx start` now verifies the recorded
Native session before requesting the shared lifecycle lock and returns success when
the matching desktop is already healthy, including during an active nested GUI.
`tx pgui stop` can close either the owned standalone :0 session or a cooperative
nested :2 session while leaving Native :1 running. If display readiness is lost
but the exact recorded supervisor remains live, it requests cleanup through that
supervisor; `tx stop` remains the Native :1 command. `tx stop` requests shutdown only
from a lock owner tagged by the current cooperative PRoot launcher, which runs the
guest inside its own process group; it waits for lock release before stopping Native
:1. Legacy/unknown owners are left untouched. Android GUI visibility remains unknown until the window is visually confirmed.

## Desktop lifecycle stale-lock recovery — 2026-10-27

The owner reported an empty legacy `.session.lock` directory left from a prior
lifecycle operation, blocking `tx pgui`, `tx start` and `tx stop` after a successful
install. Read-only inspection showed the managed desktop stopped and all owned
processes absent; only that empty stale directory was removed. Lifecycle locking
now records PID/start-time ownership under a serialized private guard and safely
reclaims dead-owner locks only when session/display evidence is stopped or exactly
stale with no live owned processes. Empty old-format locks use an age guard and the
same process/session verification. PRoot GUI paths use the same lock helper. Live or
uncertain sessions preserve their locks. No GUI was started during recovery.

## Simplified workstation approval — 2026-10-27

The guided coordinator now presents one concise Install/Cancel summary instead of
a forced raw report, extra acknowledgement menus and GPU/CPU-exclusive selectors.
CPU fallback remains installed alongside detected GPU support; saved Native launch
preferences are preserved. Device rows use their actual widest displayed content
for block centering. Successful or failed runs return without a completion keypress.
The latest local installer diagnostic observed during this change recorded exit 0;
that does not qualify desktop visibility, acceleration or the owner's reported failure.
No device package/account/service mutation was performed for this source change.

## Installer review and desktop/audio follow-up — 2026-10-27

The owner-reported installer frame clipped long review lines and showed a vague
unknown-size note. The review now wraps to the terminal width, lists each unresolved
size reason, and offers the full read-only plan report before the final approval.
The single-choice row now describes its action/key controls. The apply frame shows
an overall phase bar, elapsed time and a rough ETA once phase timing is available;
raw stage output is retained in a private, sanitized `install-live.log` and its path
is included in the final diagnostic. Branding spacing and Android add-on detection
were updated to probe allowlisted companion package paths rather than a cross-user
package list.

The owner's nested GUI log failed because the Debian runtime group did not guarantee
`x11-utils`, which supplies `xdpyinfo`; that dependency is now included in the
managed CPU/graphics runtime selection. The Native Audacious log explicitly reported
that no output plugin was found, so the Native music selection now includes
`audacious-plugins`. VLC remains installed in the owner's report, but playback and
GUI launch are not yet verified. The reported `tx gui` refusal followed `tx stop`;
local read-only status also shows the desktop stopped, so refusing management-center
launch in that state is expected. A later `tx start` check is required before claiming
GUI readiness. No desktop or service was started/stopped for this source edit, and
no package transaction was applied while awaiting CI/local review.

Focused regression checks for installer plans/output logging, package grouping,
geometry parsing, and terminal streaming passed (48 tests). The complete local
Termux suite ran 1,308 tests but had 10 PRoot fixture errors and 2 PRoot fixture
assertion failures: mocked APT fixtures omitted `dbus-x11`, and temporary rootfs
receipts failed identity validation. These checks do not exercise the changed code. Previous GitHub validation run
40541456525 also exposed six desktop-plan fixture errors: the simulated existing
XFCE guest omitted the newly-required `dbus-x11` package. The fixture now models the
pinned base profile, which already includes `dbus-x11`. The PRoot diagnostics/session
tests now also isolate HOME and state so device receipts cannot affect fixture
results; all 90 previously affected desktop/diagnostic/session tests pass. Clean-run
GitHub CI remains the integration gate. Fixture/PTY passes do not establish
device GUI visibility or audible output.

## Guest HTTPS timeout and read-only report repair — 2026-10-27

Read-only inspection of the owner's failed run found a guest APT `TimeoutExpired`
journal, 78 installed packages, no incomplete dpkg records, no ordinary login user,
and no guest CA package/bundle. The reviewed transaction was 813 packages, about
385 MB download and 1547 MB additional disk. No package repair/install was run by
the assistant. Native Python HTTPS to one exact snapshot package returned 403 with
its default user-agent but 200/206 with `curl/8`, a verified Native CA and a bounded
one-byte range read. URI-only guest APT queries matched epoch-escaped cache names
and left the dpkg status hash unchanged; they did not fetch/install packages.

Existing-rootfs add-on plans now bind package URIs/cache filenames from APT's
URI-only metadata, SHA-256/size from acquired indexes, index digests and Native CA
digest. Native TLS downloads use the same reviewed URLs/versions, three bounded
network attempts, hash-verified persistent cache, and stage all archives before
guest APT runs with `--no-download`. Missing `ca-certificates` is explicitly part
of the reviewed package plan. Both cache copies are reserved in the peak storage
estimate. Integrity failure does not switch repositories/payloads. Fresh setup
retains its Native CA bootstrap and now uses the same HTTPS user-agent/time bounds;
the new Native archive transport currently targets existing-rootfs add-ons.

Private categorized event logs retain redacted errors. Guest add-on and fresh setup
logs are mode 0600 and bounded; fresh-install failures now retain the stage, command
exit code, and log path, while the success path records package-version evidence
only after release/account/package verification. Guest apply has no-output and
overall deadlines; failed journals include stage, event-log path, timeout kind and
last output where available. The plan report is a read-only viewer without checkboxes/selection
counts; Space cannot select dependencies. Live complete install/user/desktop
acceptance remains owner-pending; source/fixture results do not claim completion.

## Combined approval and live APT event follow-up — 2026-10-27

The owner stopped their installer and required every selection/estimate before
workstation mutation. Guided setup and Native/PRoot DE shortcuts now build a private
combined plan across Native upgrades/packages, guest/account changes, CLI launcher,
shared management and GPU choice. Full scrollable report, known storage estimates,
free space and explicit unknown-size acknowledgement precede final approval.
Missing planner prerequisites have a distinct minimal bootstrap consent. Signed
metadata refresh is separate from workload installation. Exact subplans and report
hashes are bound to the combined ID; changed state stops rather than silently
replanning. The reviewed account subplan permits only package-added non-login
UID 1–999 accounts before account setup; all existing passwd record hashes, rootfs
identity and the selected account/home/sudo action remain bound. Native upgrades/new packages share one dependency transaction. Guest
APT apply streams categorized stderr events while preserving machine JSON stdout;
header redraw is throttled to one second to keep bulk logs responsive. Failure
journals mark streamed APT failures and retain partial state for reviewed recovery.
Tests use fixtures only; no device install, package repair or existing-session stop
was performed by the assistant. Fresh guest APT/unpacked-rootfs and build/graphics
scratch sizes remain explicitly unresolved until their respective runtime stages;
the report never treats them as zero or a guaranteed total.

## Installer review/output state and header follow-up — 2026-10-27

Phase entry no longer labels a pending review as installation output. Review,
noninteractive plan queries and executing commands have distinct pane captions;
phase entry always shows a status line, and guest profile loading is observed from
the first query. Output painting explicitly returns to the scroll pane after
changing its caption. The phase counter identifies workflow position, not a
measured package-download percentage. Tall/wide terminals use a five-row heavy
block logo and expanded bold tagline; compact layouts retain smaller branding.
Dividers share the live green animation. Device facts form a centered block with
aligned labels. A bounded read-only Android package query shows positively detected
Boot/API/Styling/Widget/Float/Tasker/X11 apps; unavailable package visibility is
reported as unknown. Current-device read-only detection found Boot, API, Styling
and X11. No add-on or package was installed or started by the assistant.

## Preview wait and visible username repair — 2026-10-27

A subsequent owner screenshot showed a blank-looking stage 5/7. Guest previews
can wait for captured APT simulation/download-size queries without showing their
operation. Guided fresh/add-on previews now show a named busy state, refresh elapsed
time/branding, keep JSON separate from terminal output, suppress keyboard echo and
discard keys typed during that noninteractive wait. This identifies the operation;
it does not prove the owner's exact backend wait cause from a screenshot alone.
A separate confirmed field bug cropped short usernames to empty text; cropping now
applies only to overlong values. PTY coverage asserts visible username text and
clean JSON/input isolation through a delayed query. The logo uses a vertical green
color wave. The header reports only `PulseAudio installed`; playback readiness
remains a separate diagnostic claim, without an unsolicited audio test.

## Guest account input form repair — 2026-10-27

The owner reported an apparently blank guest-account screen with echoed arrow
sequences. The root-only guest path used canonical shell text reads rather than
the keyboard selector. Username and hidden password entry now use a visible,
non-echo form with explicit typing instructions, Backspace/Enter/Esc handling,
escape-sequence filtering, resize preservation and terminal-state restoration.
Choice collection no longer labels this screen as an installation log. Large
terminals show a three-line TERNUXX logo with a green color pulse; smaller layouts
keep the compact title. Dividers use restrained green box-drawing rules. PTY
fixtures cover the complete root-only account form without creating an account
or changing installed packages; owner-device visual acceptance remains pending.

## Reinstall/account/GPU audit follow-up — 2026-10-27

The owner's PRoot GUI failure was reproduced as a read-only account-discovery fact:
the existing Debian rootfs has no ordinary `/home/USER` login account, and no managed
account receipt. The earlier add-on path preserved that root-only guest without
creating one. Reinstall now collects/creates or selects an ordinary account through
an exact rootfs/passwd-bound plan, persists a private identity-bound default, and
preserves existing users/passwords. `pgui --user` propagates the validated user to
the standalone wrapper; friendly errors replace the raw start traceback.

The installed official Mesa/Freedreno 26.2.5 read-only Vulkan probe rejected the
owner's GPU. The managed wizard now offers the pinned experimental Adreno 825 Mesa
provider from an owner-authorized versioned release. ZIP, original package and four
runtime-file hashes are verified; private extraction leaves system packages intact,
and a loader/device check gates future-session selection. Repeat installs verify
cache plus current compatibility. Source archive, all matching source license
notices and build recipe/provenance accompany the release. This is stable acquisition
of experimental bytes, not closure of the P12 transitive attribution/source-rebuild
gate or current-device rendered-workload acceptance.

Login aliases now route Debian (`db`/`debian`) and Ubuntu (`ub`/`ubuntu`) through the
same owned-session service with the selected alias bound to the preview. Kali is
explicitly unavailable. The installer adds green section headers and a compact
seven-stage progress indicator. See the [repository-wide audit report](docs/evidence/2026-10-27-reinstall-repository-audit.md)
for coverage and limits. No live guest/account, installed package, desktop/service
or Android setting was changed by the assistant during this follow-up.

## Keyboard and installer branding follow-up — 2026-10-26

The owner reported literal arrow escape text and a stuck existing-Debian add-on
confirmation. Selector input now keeps one noncanonical/non-echo terminal mode,
accepts delayed CSI/SS3 sequences, uses the controlling terminal independently of
stdin, and restores terminal state on exit/cancel/signals. A single writer handles
selection, progress/clock and package/build output; the racing background ticker
was removed. Resize redraws include scroll margins; undersized selection pauses
until the terminal grows again.

The frame uses centered green `TERNUXX`, `Workstation In Your Hand`, spaced green
system labels, contextual keyboard/title dividers and centered copyright. The log
heading is absent before installation starts. Optional catalogs now cover 51 Native
and 49 guest entries, including clearly labeled AI prerequisite/setup recipes;
Blender is guest-only and Claude guidance is PRoot-only. No external AI installer,
agent login or Hermes repository enrollment is performed by selection. The supplied
Hermes upstream guide currently warns its Termux package is broken.

See [keyboard/UI evidence](docs/evidence/2026-10-26-installer-keyboard-branding.md)
and [AI setup guidance](docs/AI-TOOLS.md). These changes have isolated PTY/source
coverage; the owner's physical Termux reinstall and application workloads remain
separate acceptance checks. Existing live installer/services/guests were untouched.

## Installer crash and reliability follow-up — 2026-10-26

The reported post-package `KeyError: 'changed'` came from reading the CLI shim's
`{ok, data}` response as a flat object. The wizard now validates that real envelope;
regression coverage uses the actual shim preview/apply in an isolated prefix.
Guided setup adds a persistent terminal frame, early guest credential collection,
bounded verified-download retries, a single-session lock, package/storage preflight
and a private redacted result summary. Existing client management is reused for
fixed terminal installer handoff, with explicit Android opt-in/manual fallback.
See the [installation guide](docs/INSTALLATION.md) and
[implementation evidence](docs/evidence/2026-10-26-installer-reliability.md).
These are source/fixture changes; the owner's new clean reinstall, sound/rendering
and rendered Android/Web/GTK acceptance remain pending. No device install or
service activation was performed during this follow-up.

## Managed installer revision — 2026-10-26

The owner-requested three-profile keyboard wizard is implemented at `./tx install`
(`interactive` remains an alias): device/system summary, Minimal terminal/build
workstation with PRoot CLI provider, Native Full with DE/app selection, and Native Full + multiple managed
Debian/Ubuntu guests. Arrow/Space/Enter replace typed profile, DE and distro choices.
Preparation, full system upgrade, Native packages, CLI shim, graphics selection and
guest plans have separate confirmation boundaries. All guided profiles build the GTK center and include SSH/service management tools;
Python/X11 bootstrap stays inside the managed wizard. `tx pgui DE` accepts a desktop
short name, and the existing auto routing keeps standalone :0 / Native :1 + Xephyr :2.
XFCE is preferred by default even with multiple installed guest desktops.

Guest setup now offers optional software after DE selection, including Writer-only.
The pinned base/clean profile retains Mesa CPU rendering, device-gated Turnip graphics
and authenticated Native audio. Short `tx install DE` and `tx install proot DISTRO [DE]`
commands support later additions. Existing Debian/Ubuntu rootfs targets use preview-bound
add-on transactions (no rootfs/account replacement; no upgrades/removals); already
installed selections return a no-op. Ubuntu browser selection uses APT Epiphany to
avoid the Snap-only Firefox path. These are implemented/fixture-tested paths; the
owner's fresh reinstall and live workload acceptance remain pending.

The help landing page is install-first and summarizes later desktop/guest/GPU
commands. All guided profiles now include Native audio/graphics runtimes; `tx install
gpu` opens the same device-aware Native/PRoot/both selector without requiring a DE.
Native Zink recommendations require successful Vulkan device enumeration. Current
backend preferences remain default; no desktop/service is restarted. Managed guest
Turnip repair/addition reuses the checksum-bound staging helper and refuses unknown
existing files. Explicit CLI-only guests use `--desktops none`; CPU-runtime-only
setup does not stage Turnip. These remain dependency/configuration claims pending
live workload and audible-playback acceptance.

Writer-only Native installation remains unavailable because the official repository
provides a monolithic LibreOffice package. This revision does not install it silently.
Repository/fixture checks are separate from the owner's pending reinstall and rendered
GUI/GPU acceptance. No live package transaction or desktop lifecycle action was run
by the agent while implementing this revision.

## Live runtime

Fresh-clone reinstall and route recheck (2026-10-26): main clone ea1a07d is the canonical checkout; the prior checkout was preserved. The owned tx shim was preview-bound reinstalled. The full-native package profile was already installed, so no package transaction ran. A follow-up simulation against the 19 profile roots proposed 108 removals plus mesa-vulkan-icd-swrast; leaving shared dbus/audio/provider/Python roots out still proposed 21 removals including Plasma packages. No package transaction ran, so full Ternuxx package uninstall/reinstall remains open. Fresh-tree tests passed 1,228/1,228 in 224.994 seconds and CLI help passed. Native :1 OpenGL-window, GLES shader, and Vulkan draws all rendered on Adreno 825; Debian replay standalone :0 passed Adreno Zink/Turnip GLX and Vulkan draws plus DRI3/audio endpoint checks. Nested Debian :2 remains partial: Adreno Vulkan and audio endpoint pass, Xephyr DRI3 is unavailable and GLX drawing fails. Native :1/audio/managed SSH are restored; :0/:2 and managed PRoot sessions are stopped. See [fresh checkout and route evidence](docs/evidence/2026-10-26-fresh-checkout-reinstall-and-desktop-routes.md).

Native/Ubuntu route evidence (2026-10-26 09:15 UTC): Native XFCE is running on `:1`; Ubuntu standalone `:0` is stopped and nested `:2` is absent. A fresh bounded Native `:1` verification at 09:15 UTC rendered OpenGL in an X11 window (Adreno 825, score 617), rendered a 910-frame GLES shader draw (Adreno 825, 1280x720, five seconds), and rendered 120 Vulkan frames on Adreno 825. Ubuntu Noble passed standalone XFCE `:0` and guest workloads directed to Native `:1`; nested XFCE `:2` exposed its session, panel, desktop, WM, and Thunar windows, and Vulkan/audio endpoint checks passed, while GLX failed because Xephyr DRI3 is unavailable, so nested remains partial. GLES contexts report Zink/Turnip Adreno 825; GLES draw, Android foreground visibility, and audible playback remain unverified on the Ubuntu routes. Existing Debian guests remain preserved. See [Native Adreno 825 live verification](docs/evidence/2026-10-26-p12-native-adreno825-acceleration-and-inference.md#2026-10-26-0915-utc-fresh-native-1-graphics-verification), [Ubuntu live install and route qualification](docs/evidence/2026-10-26-ubuntu-noble-live-install-route.md), and [fresh guest nested route acceptance](docs/evidence/2026-10-26-fresh-debian-guest-nested-route-acceptance.md). As of 12:32 UTC the canonical Debian guest has only XFCE installed; the managed desktop catalog remains available for future explicit selections. LXQt, LXDE, MATE, and Plasma package trees were removed after their PRoot route tests failed full desktop acceptance; GNOME/Cinnamon payloads and residual config records are absent. Post-cleanup nested `:2` was relaunched: the XFCE session/window tree and authenticated PulseAudio endpoint passed, but GLX reported llvmpipe and Adreno 825 Vulkan presentation failed because Xephyr lacks DRI3. The nested session was closed and Native `:1` remains available; Android visibility and audible playback remain unverified. See [post-cleanup nested route evidence](docs/evidence/2026-10-26-debian-postcleanup-nested-route-check.md). A separate post-cleanup standalone `:0` run passed the Ternuxx readiness check, rendered 819 GLX frames/5 seconds on Zink/Turnip Adreno 825, completed bounded `vkcube --c 120` exit 0 with Adreno selection, and authenticated to Native PulseAudio. GLES frame output, audible playback, and Android visibility remain unverified; `:0` was stopped and Native XFCE/audio restored on `:1`. See [standalone route evidence](docs/evidence/2026-10-26-debian-postcleanup-standalone-route-check.md). A bounded Debian guest check against Native `:1` then returned complete with an 837-frame Adreno 825 GLX draw, Vulkan Adreno draw, authenticated audio endpoint, and GLES context; it reported `gles_draw_verified=false` and `read_only=false` because launcher-profile writes were possible. Its safety record showed no guest write command, package/service change, or host lifecycle action. Current Native `:1` and audio are live; all PRoot sessions are stopped. See [Debian `:1` workload evidence](docs/evidence/2026-10-26-debian-native1-workload-recheck.md).
Fresh Debian replay standalone `:0` recheck on 2026-10-26 passed display/window discovery, Adreno 825 Zink/Turnip GLES context, 736-frame GLX draw, Adreno 825 Vulkan draw, and Native PulseAudio endpoint reachability. Native `:1` and audio were restored/running afterward; `:0`/`:2` and managed sessions are stopped. Audible playback and Android foreground visibility remain unverified. See [Debian route recheck evidence](docs/evidence/2026-10-26-nested-debian-start-fix-and-live-check.md#fresh-standalone-0-replay-check).
Debian standalone `:0` follow-up: an immediate probe at 11:24 UTC returned `partial` with zero GLX frames; a later rerun after a 20-second startup wait returned `complete` with 623 Zink/Turnip Adreno 825 GLX frames, Adreno 825 Vulkan drawing, and a reachable Native PulseAudio endpoint. GLES drawing remains unverified. The timing difference suggests startup readiness may affect the result, but the cause is not isolated. Native-host `xwininfo` was unavailable, so XFCE panel/window-tree readiness and Android visibility remain unverified; endpoint reachability does not prove audible playback. Native `:1` was restored, `:0`/`:2` stopped, and there are no managed sessions. See [the standalone route evidence](docs/evidence/2026-10-26-debian-standalone-render-follow-up.md).
Mesa provenance capture hashes the requested Ubuntu archives and Packages indexes, but pinned workflows [40314482083](https://github.com/soobujmiah/ternuxx/actions/runs/40314482083) and [40318021029](https://github.com/soobujmiah/ternuxx/actions/runs/40318021029) both failed strict validation: 22 extracted host inputs had no exact archive path/payload owner match. The second run found no matching basename members in any of the eight requested archives, so the discrepancy remains unexplained. Capture now compares dpkg-deb's package listing with its tar stream, including exit status and member count; focused tests pass (14). Ownership checks remain strict. Package attribution and license closure remain open. See [P12 host-owner validation evidence](docs/evidence/2026-10-26-p12-mesa-generated-source-follow-up.md#pinned-host-owner-validation-failure--workflow-40314482083).
PRoot standalone startup now waits up to 60 seconds for the selected desktop shell, WM, panel, and desktop processes in its verified session group; `tx pgui status` reports readiness. Live `:0` checks passed for XFCE, LXQt, LXDE, MATE, and Plasma. XFCE then passed 615-frame Adreno 825 GLX and Vulkan draws plus PulseAudio endpoint reachability. Per-desktop window capture, GLES drawing, audible playback, and Android visibility remain unverified. Native `:1` is restored and live; `:0` and `:2` are stopped. The full repository suite passes 1,227 tests after this change. See [standalone readiness and render evidence](docs/evidence/2026-10-26-debian-standalone-render-follow-up.md).
Source follow-up at 19:38 UTC corrected the GNOME launch argv to Debian Trixie's existing `gnome.session` name in the catalog and both GUI launchers. The removed GNOME packages were not reinstalled, so this correction has focused code tests only; full GNOME session acceptance remains open. See the [GNOME session correction evidence](docs/evidence/2026-10-25-debian-gnome-session-correction.md).

At 2026-10-25 09:24 UTC, the Native entrypoint installer found `$PREFIX/bin/tx` absent. Its exact preview was applied; the installed shim matches `scripts/tx-installed` at SHA-256 `a8735006203922cb7d7ab885e7fa1b85ca8608282de79d427d12a21a2511c401` and dispatches into `$HOME/ternuxx`. `tx help` and `tx doctor --json` ran through the installed command. Doctor reported 0 errors and 2 warnings (unrelated wildcard/password-enabled Native SSH configuration and unknown Ternuxx SSH service state). The installed `full-native` package profile is already present. At 09:42 UTC, `tx --json install preview --profile native-debian --user sobuj` returned valid combined JSON with the Native phase already installed and a fresh Debian preview; `tx proot status --json` still reported no distributions. No guest rootfs was created. See [Native CLI installation evidence](docs/evidence/2026-10-25-native-cli-entrypoint-install.md) and [combined profile evidence](docs/evidence/2026-10-25-native-installer-profiles.md).
At 2026-10-25 09:59 UTC, Native Ternuxx SSH first-time setup was applied from an exact combined preview. The dedicated config is valid and key-only on `127.0.0.1:8023`; the managed Runit service is running with verified process identity and a successful SSH banner probe. A Native Ed25519 client key was enrolled only in `.ssh/ternuxx-keys/authorized_keys`, and a strict-host-key SSH client test authenticated locally and returned the Native account identity. The external Native `sshd_config` and shared `.ssh/authorized_keys` hashes are unchanged. Kernel listener correlation remains unavailable under Android permissions; external SSH config remains outside Ternuxx management. See [isolated SSH setup evidence](docs/evidence/2026-10-25-native-ssh-isolated-setup.md).
A fresh guarded Native Vulkan qualification preflight on 2026-10-25 was refused before inference because SoC digital temperature was 72.0°C against the unchanged 70°C guard; CPU/GPU/HTP/battery sensors and available memory passed. No Vulkan inference case ran; see the [preflight evidence](docs/evidence/2026-10-26-p12-vulkan-preflight-soc-guard.md). The P12 Mesa provenance workflow run [40128850286](https://github.com/soobujmiah/ternuxx/actions/runs/40128850286) completed successfully on 2026-10-24. Its target source map, package manifests, candidate audit, and unresolved licensing/provenance boundary are recorded in the [build artifact audit](docs/evidence/2026-10-25-p12-mesa-build-artifact-audit.md); P12 remains active. The 2026-10-26 audit mapped all 75 generated outputs and 12 outside-root build inputs; 7 Wayland protocol XML inputs match the checksum-verified 1.49 source archive. Extended pinned build [40237840375](https://github.com/soobujmiah/ternuxx/actions/runs/40237840375) exposed empty Rusticl source inventory, incomplete package-owner lookup, unhashed metadata for 31 staged dependencies, and uncaptured shipped license text. Follow-up run [40241516521](https://github.com/soobujmiah/ternuxx/actions/runs/40241516521) passed with Rusticl source/header inputs, hashes for all staged Debian archives, and bounded Mesa license text captured. Owner-indexing correction was rerun in pinned workflow [40244463700](https://github.com/soobujmiah/ternuxx/actions/runs/40244463700), whose build and capture validator passed. Auditing its metadata-only artifact found zero package-owner candidates for all 29 host and 49 target external build inputs; the validator accepts unresolved owners when candidate arrays are empty. Package/source attribution and the wider 1,165-file NOASSERTION inventory remain open. See the [generated/external source follow-up](docs/evidence/2026-10-26-p12-mesa-generated-source-follow-up.md).

At 17:25 UTC, the fixed Native Termux:Boot helper status reported the installed `services` helper as previously managed (source hash differed) and `recovery` as matching. The exact source diff was limited to obsolete PRoot wording/markers; service actions were unchanged. After exact preview/apply, a fresh read-only status reported both helpers matching their source at mode `0700` and four recorded private rollback snapshots. The helper was not executed, no service was started/stopped, and no reboot was performed. Details: [boot-helper client parity and reconciliation](docs/evidence/2026-10-24-boot-helper-client-parity.md).

All recorded Ternuxx PRoot sessions report stopped. A read-only process inventory also observed five defunct `proot` children under the long-running TUI process; their session ownership is unverified. They are zombies rather than executing workloads. The probe launcher now double-forks so future bounded probes are not children of long-lived clients; the focused fixture and full repository tests pass. These five older zombies remain under the active TUI, whose code was already loaded before the source fix; no signal or cleanup was attempted. Full command results and the exact observation are in the [live state reconciliation evidence](docs/evidence/2026-10-24-live-state-reconciliation.md).

## Active work

A clean-room Native workstation rebuild is underway. Cross-distro PRoot profile and installer/session generalization remains open. Shared guest package inventory now has a rootfs-confined dpkg adapter used by adoption and desktop inventory plus an APK database reader covered by fixtures; no Alpine installer/profile is exposed until package transactions, base-image pinning, desktop, graphics/audio, lifecycle, and recovery paths are qualified. Source now defines pinned Debian Trixie and Ubuntu Noble profiles, distro-aware desktop routing, and receipt-verified guest selection; Ubuntu standalone `:0` and guest workloads directed at `:1` are live-qualified; nested `:2` has Adreno Vulkan drawing but Xephyr GLX/DRI3 remains partial. Managed audio lifecycle recovery now cleans an exact stale Native PulseAudio PID/socket pair, but actual playback remains unqualified. The verified baseline, test results, current device observations, and acceptance checklist are in [the rebuild tracker](docs/audit/CLEAN-ROOM-REBUILD-TRACKER.md). Its evidence distinguishes the fresh Native runtime from historical PRoot observations.

Native `:1` was restored after the standalone route check; its UI foreground visibility still reads unknown. Its OpenGL verifier completed a visible X11-window draw on Adreno 825 (score 544), and Vulkan drew 120 frames on Adreno 825. The latest full repository suite passed 1,223 tests in 201.012 seconds after the nested Debian startup fix; a previously failing supervisor fixture passed on the clean full rerun. The current implementation and open acceptance are summarized in the [capability matrix](docs/architecture/CAPABILITY-MATRIX.md), [phase status](docs/PHASE-STATUS.md), and [repository audit](docs/audit/REPOSITORY-AUDIT.md). Latest relevant results:

- `tx install interactive` now previews the selected Native transaction and applies that exact saved plan after one in-session confirmation, without requiring the user to copy a plan ID; named `--profile` preview/apply remains the automation path. The guided Native flow offers optional Debian or Ubuntu setup afterward. In an attached Native terminal, `tx install debian --user NAME` now previews the pinned target and asks before applying that exact plan; explicit `preview` and JSON/noninteractive calls remain review-only. After Native profile apply, the CLI offers optional managed Debian or Ubuntu setup. The TUI now offers a Debian/Ubuntu selector, then launches the matching guided `tx install <distro> --desktops ...` flow from its attached terminal; GTK offers a real checkbox multi-select in an embedded VTE terminal, with accepted routes labeled and unverified GNOME/Cinnamon routes identified; Web now offers direct Debian/Ubuntu fresh-guest preview/apply behind an optional `proot.install.manage` grant; its password field is transient and excluded from persisted idempotency fingerprints. All clients expose desktop selection. One-session guided `tx install debian --user NAME` and `tx install ubuntu --user NAME` flows exist, and Native setup offers either optional guest afterward; the old `native-debian` two-plan-ID flow remains for explicit automation. A fresh pinned Debian Trixie XFCE guest was installed under a separate replay alias to preserve the existing canonical guest. Its shared `:1` verifier returned complete: Zink/Turnip GLES, 515-frame GLX draw, Adreno 825 Vulkan draw, and reachable Native PulseAudio endpoint. Receipt-verified replay aliases now have an explicit nested `tx pgui ... --alias ALIAS` route; fresh XFCE started on `:2` with live session/panel/desktop processes and six visible X11 windows. On `:2`, Vulkan draw and audio endpoint passed, while Xephyr lacked DRI3 and GLX draw failed; this is a partial graphics result, and Android foreground visibility/audio playback remain unverified. GNOME/Cinnamon routes remain unverified, Plasma is standalone-only, and Debian Trixie is live-qualified. Ubuntu Noble is now live-qualified on standalone `:0` and guest workloads directed to Native `:1`; nested `:2` runs XFCE and Vulkan/audio but remains partial because Xephyr has no DRI3 and GLX drawing fails. Alpine, Arch, Fedora, and Void have no Ternuxx profiles. The clean replay alias is retained for now; upstream `proot-distro list` omits it, while Ternuxx status now adds it only after its private receipt, rootfs identity, and Debian Trixie release validate. The full suite now passes 1,212 tests in 159.420 seconds after Ubuntu receipt/symlink fixes and alias-bound guest desktop shortcut routing. A 120-test focused diagnostics, fresh-setup, session, and launch run also passed. Managed guest desktop shortcut sync now generates distinct alias-bound Debian and receipt-verified Ubuntu launchers; a read-only live inventory listed Debian XFCE/LXQt/LXDE/MATE/Plasma plus Ubuntu XFCE with their correct launch commands. The current live :1 probe again completed Zink/Turnip GLES, a 515-frame GLX draw, an Adreno 825 Vulkan draw, and PulseAudio endpoint reachability. GitHub Actions run [40293406719](https://github.com/soobujmiah/ternuxx/actions/runs/40293406719) passed validation, the repository test suite, and deterministic state sync for commit `24793ed`; generated state sync is at `8324447`. The alias-bound shortcut change is included in the following main-branch validation run [40307753701](https://github.com/soobujmiah/ternuxx/actions/runs/40307753701), which passed repository tests and deterministic state sync. A live read-only `tx proot status --json` now reports canonical `debian`, the valid Ternuxx replay alias, and canonical `ubuntu` while entering no guest; no managed PRoot sessions are running. The GTK picker was rendered and exercised on Native `:1`: the Debian/Ubuntu dropdown updates its profile-owned checkbox list and route labels; see [GTK picker evidence](docs/evidence/2026-10-26-gtk-profile-driven-proot-picker.md). A fresh Debian nested `:2` rerun fixed a guest-payload alias error and reached the XFCE desktop; Adreno Vulkan draw passed, GLX failed due to Xephyr DRI3, and audible playback remains unverified. The replay guest also returned a clean read-only `dpkg --audit` and successful `apt-get check`; see [nested route evidence](docs/evidence/2026-10-26-nested-debian-start-fix-and-live-check.md). The overall diagnostic is `partial` and reports possible launcher profile writes. See [managed guest desktop shortcut routing](docs/evidence/2026-10-26-managed-guest-desktop-shortcut-routing.md), [nested render evidence](docs/evidence/2026-10-25-pgui-nested-render-follow-up.md) and the [verifier follow-up](docs/evidence/2026-10-25-nested-proot-diagnostics-vulkan.md). See [distro-named install evidence](docs/evidence/2026-10-26-distro-named-managed-install.md) and [Native installer profile evidence](docs/evidence/2026-10-25-native-installer-profiles.md).
- TUI, Web, and GTK expose the guarded reboot-test preview/apply flow through the shared service; Web uses a dedicated `continuity.reboot-test.manage` capability. The owner has now confirmed the GTK Management Center renders in Floating Termux:X11 and that category interaction works; this is a basic live GTK check, while full critical-flow/accessibility acceptance and rendered Web acceptance remain open. See [reboot-test client parity evidence](docs/evidence/2026-10-25-reboot-test-client-parity.md) and [the clean-room tracker](docs/audit/CLEAN-ROOM-REBUILD-TRACKER.md).
- The pinned Mesa archive inventory covers 9,376 files (3,965 with SPDX headers, 5,411 `NOASSERTION`). The captured graph has 322 targets and 1,579 source paths; 1,567 Mesa paths match the inventory. Per-target membership is in the [configured source map](docs/evidence/data/2026-10-24-p12-mesa-configured-target-source-map-40125903141.json). Run [40125903141](https://github.com/soobujiah/ternuxx/actions/runs/40125903141) built Mesa and emitted five package manifests, but its final validator incorrectly required `aarch64` for `mesa-dev` (whose correct Debian architecture is `all`). The corrected local validator passes the captured artifact; corrected rerun [40128850286](https://github.com/soobujiah/ternuxx/actions/runs/40128850286) is building Mesa. A cautious [package-to-target candidate map](docs/evidence/data/2026-10-24-p12-mesa-package-target-candidates-40125903141.json) records 11 unique basename matches and 46 symlinks resolving to those files; this is not complete install/source/license attribution. Generated/external inputs and applicable notices remain open. Full scan detail and limits are in the [Mesa evidence report](docs/evidence/2026-10-24-p12-mesa-source-license-inventory.md).
- Under the owner-requested `--ignore-thermal-limits` override, the current pinned model passed the three-case CPU and Vulkan answer suites. Vulkan reported complete 29/29-layer offload to Adreno 825 for each case; CPU runs reported zero GPU layers. The runner kept memory/time/process cleanup checks active and recorded temperatures. The pinned Snapdragon b11849 runtime was then installed via exact preview and checksum verification; experimental HTP0 passed the same 3/3 suite with 29/29 layers and silent fallback disabled. Ten-call repeat suites then passed 10/10 on CPU, Vulkan, and HTP; Vulkan/HTP proved full layer offload every call, no orphan process remained, and minimum available memory stayed above 4 GiB. Peak observed CPU sensor reading was 95.2 C during HTP (thermal guard intentionally overridden; Android thermal policy unchanged). These repeat correctness checks do not qualify sustained performance or wider operators. A later 32-token HTP probe fully offloaded its first call but the strict one-digit answer verifier rejected a ten-word response; it stopped before a repeated suite and is recorded separately in the same evidence report. See the [Native Adreno 825 acceleration and inference evidence](docs/evidence/2026-10-26-p12-native-adreno825-acceleration-and-inference.md). Earlier guard-block and missing-runtime observations remain in their dated records.

A prior full suite passed **1,181 tests in 176.519 seconds** after adding route-aware Debian desktop selection (nested Plasma is refused), standalone-only Plasma shortcuts, removing failed Native LXQt/Cinnamon installer choices, and syncing CLI/TUI/Web help. The previous baseline passed **1,109 tests in 131.210 seconds** after adding the combined Native/fresh-Debian profile preview/apply coverage on top of exact APT metadata estimates, storage preflight, failed-transaction journal coverage, an apply-time low-storage refusal integration test, and empty-transaction estimate handling (2026-10-25; the earlier clean-room baseline passed 1,087 tests and 402 subtests). CI run 40177494173 exposed a Pulse cookie test-fixture path assumption; that fixture now matches the production `.config/pulse/cookie` hierarchy, and CI run 40177830891 passed all 1,096 tests on the corrected fix. Installer-profile commit `f9ab7ca6613a4babc483466ea6c759bb3fe653f8` passed GitHub Actions run [40178757853](https://github.com/soobujmiah/ternuxx/actions/runs/40178757853): 1,099 tests in 37.360 seconds. Resource-estimate commit `32dd7ef` is included in validation run [40179434997](https://github.com/soobujmiah/ternuxx/actions/runs/40179434997), which passed 1,103 tests in 46.449 seconds, CLI help, and both validation/state-sync jobs. The failed-transaction journal and low-storage apply integration tests passed local suite 1,105 tests and GitHub Actions run [40180194280](https://github.com/soobujmiah/ternuxx/actions/runs/40180194280), which passed 1,105 tests in 46.641 seconds and completed both validation and repository state-sync jobs. The empty-transaction estimator fix passed GitHub Actions run [40181143844](https://github.com/soobujmiah/ternuxx/actions/runs/40181143844). The combined Native/fresh-Debian installer change passed the 1,109-test full suite and its later package/guest focused checks. The local full suite subsequently passed 1,122 tests before a final isolated SSH rollback-path fix; after that fix, all 127 focused SSH/catalog/management tests and the 76-test management regression group passed. The environment-normalized `scripts/repo_test.sh` gate, document inventory/link audit, README bridge, and CLI help contract also passed. These repository checks do not substitute for rendered UI or live workload acceptance. The document inventory currently tracks 573 documents; read/hash counts are maintained in the generated inventory; see the [document inventory](docs/audit/document-inventory.json). Historical build failures and individual thermal observations remain in their dated evidence files.

## Release boundary

Internal phase completion does not mean public-release readiness. No project license has been selected; source provenance and license review, a build-specific SBOM, release signing, clean-device qualification, boot recovery, and the owner-reviewed SSH security decision remain open. Do not treat public repository visibility as redistribution permission. See [legal/IP readiness](docs/readiness/LEGAL-IP.md), [security policy](SECURITY.md), and [known limitations](docs/testing/KNOWN-LIMITATIONS.md).

The earlier Web reload/reconnect work remains preserved; its evidence is in the [Web session report](docs/evidence/2026-10-24-web-session-reload-reconnect.md).
At 11:33 UTC, read-only `dpkg --audit` returned no findings for the existing Debian, Ubuntu, and receipt-verified replay guests; no package transaction ran. This is dpkg-state evidence only. See [managed guest package audit](docs/evidence/2026-10-26-proot-guest-package-audit.md).

Debian extra-desktop cleanup (2026-10-26 12:32 UTC): exact APT purges removed the installed LXQt/LXDE/MATE/Plasma roots and auto dependencies, then cleared 13 residual GNOME/Cinnamon package configuration records. The canonical Debian guest now inventories only XFCE; all 335 package versions from the Ternuxx install receipt remain installed and unchanged, `7zip` is preserved, and `dpkg --audit` is clean. Native `:1` remains live, `:0`/`:2` are stopped, and no managed PRoot sessions exist. This was package-state verification only; the desktop was not relaunched after cleanup. See [Debian desktop cleanup evidence](docs/evidence/2026-10-26-debian-extra-desktop-cleanup.md).

Verification on the fresh checkout: `bash scripts/repo_test.sh` passed 1,228 tests in 224.994 seconds and the CLI help contract passed; after the P12 host-build-root inference fix, all 14 focused Mesa evidence tests also passed. Pinned workflow [40325224173](https://github.com/soobujmiah/ternuxx/actions/runs/40325224173) completed its Mesa build/staging but failed capture validation because the subprocess did not inherit the shell-local `TERMUX_PKG_HOSTBUILD_DIR`; the local fix infers the sibling `host-build/ubuntu_packages` root. A pinned rerun is required. See the [P12 capture evidence](docs/evidence/2026-10-26-p12-mesa-generated-source-follow-up.md).
