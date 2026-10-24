# P11 Debian PRoot restoration and live acceptance — 2026-10-24

Phase: `P11` (completed; 2026-10-24)

> This evidence file records a sequence of dated checkpoints. Statements inside earlier follow-ups describe the state at that checkpoint and are not the final state. The later acceptance entries below supersede their earlier "remaining work" and GUI-state notes. The final reconciliation is recorded in [live state evidence](2026-10-24-live-state-reconciliation.md); current client scope and qualification limits are in the [capability matrix](../architecture/CAPABILITY-MATRIX.md).

## Evidence

## Native host and package manager

The runtime is Native Termux. Official `proot` and `proot-distro` packages were installed from a reviewed exact package preview. `proot --version` reports `5.1.107.100`; `proot-distro` is `5.10.2`. Configured package source files were not changed. Before guest setup, the Debian target did not exist.

## Debian setup and live guest

Fresh Debian Trixie was installed from the manifest's digest-pinned arm64 OCI image and dated Debian snapshot using plan `b1cc5ec5d19829e52c13093443a4a405943cffca0973fcc9ca8e05b868a97e7a`. The guest is `debian`, account `sbj`, and the setup receipt confirms all requested packages and the pinned Turnip artifact were installed. The password was entered through hidden prompts; it is not in repository files, setup plans, command arguments, or evidence.

Live checks confirm Debian GNU/Linux 13 (Trixie), aarch64, the expected unprivileged guest UID, installed `sudo`, Xfce terminal, Xephyr, Vulkan tools, Mesa EGL/GBM/GLX/Vulkan packages, and Turnip ICD/driver files. A real interactive `sudo -k id` authenticated the selected account and returned guest root. The first check exposed PRoot's missing supplementary-group propagation; the setup now writes a validated per-user sudoers entry and checks it with `visudo`. This repair is applied to the current guest and included in the installer source/tests.

`vulkaninfo --summary` loaded the installed Turnip ICD and enumerated the Adreno 825 as an integrated GPU (`DRIVER_ID_MESA_TURNIP`, Mesa 26.3.0-devel). This verifies Vulkan device discovery, not desktop presentation, rendering correctness, or GPU inference. `DISPLAY` is unset in this shell; GUI presentation remains a separate acceptance check.

The owner reported that XFCE About shows the GPU as `Unknown`. This is consistent with the nested display path: [XFCE About's libxfce4ui implementation](https://gitlab.xfce.org/xfce/libxfce4ui/-/raw/xfce-4.20/xfce4-about/system-info.c) asks GDK for an OpenGL context and supplements it with DRM render-node/udev data; this Android KGSL path has no DRM render node. The Ternuxx nested launcher deliberately starts Xephyr with `-glamor_gles2` ([Xephyr option source](https://gitlab.freedesktop.org/xorg/xserver/-/blob/xorg-server-21.1.16/hw/kdrive/ephyr/ephyrinit.c)); live `glxinfo -B` against `:2` reports `couldn't find RGB GLX visual or fbconfig`, while the launcher's GLES context reports `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`. So `Unknown` in About is a GLX/DRM hardware-identification gap, not evidence that the selected GLES/Vulkan renderer is software. Do not claim GLX or pixel presentation from this result.

The managed nested GUI smoke test started XFCE successfully on `:2`, reported the Adreno-backed Zink GLES renderer, and exited via Ctrl-C. Post-check confirms the `:2` socket and PRoot process are gone, while Native desktop `:1` remains running.

Nested Xephyr now queries the current Native `:1` dimensions inside Debian and uses that geometry at startup instead of forcing `1280x720`. The live portrait display reports `752x1124`, and the same bounded parser accepts swapped `1124x752` landscape dimensions after rotation. Xephyr starts with `-resizeable`, which allows its host window to be resized; this option alone does not prove that Android rotation or fullscreen changes the nested screen resolution. The Debian Trixie [Xephyr manual](https://manpages.debian.org/trixie/xserver-xephyr/Xephyr.1.en.html) documents resizable-window support and RandR, but not Android-specific fullscreen behavior. Unit tests cover portrait, landscape, malformed and oversized dimensions, and the real Debian shared-TMP route successfully queried `:1`; a physical rotation/fullscreen interaction was not performed during this check.

The typed `tx db` route was also exercised: its exact-session preview showed the intended Debian rootfs identity and guest user, explicit `LOGIN` entered Debian 13 as `sbj`, and `exit` returned exit code 0 with zero remaining session processes. Session inventory records it as stopped. The owner's separate nested GUI remains present; its process ownership is not inferred from socket presence and it was left untouched.

The latest `./tx proot status --json` reports `status=installed`, `manager_available=true`, and installed distribution `debian`. A concurrent `tx pgui` nested-desktop process was observed after the bounded checks; `tx pgui status` reports Native desktop running, standalone Debian GUI stopped, and a nested `:2` socket. The process/session association is not verified by the current status command, so it was left untouched. No Termux app or service was stopped.

## Source and acceptance status

The P11 source set covers Native-host PRoot inventory and diagnostics, exact-preview Debian setup, setup recovery/presentation, scoped guest lifecycle/session identity, guest GUI/D-Bus wrappers, shortcut management, terminal broker/service, and typed management routes. The later installed-guest acceptance entry in this file closes the earlier CLI/TUI/Web/GTK lifecycle gap. Fresh guest setup remains attached Native CLI-only; current client reach is in the [capability matrix](../architecture/CAPABILITY-MATRIX.md).

At this earlier audit checkpoint, the Native Termux fixture suite passed `952` tests in `113.996` seconds. `python3 -m tools.repo_knowledge verify` reported zero findings, `git diff --check` passed, and the document audit found zero broken local links across 97 scanned files. The Native PRoot-independence probe result from the earlier audit remains fixture evidence, not a live guest result.

At the initial audit checkpoint, CLI/TUI/Web/GTK parity and lifecycle acceptance were still open. Later entries in this file record those checks and the Native GUI `:1` running with Debian GUI `:0` stopped. Physical portrait/landscape rotation and fullscreen resizing remain untested. The About GPU label remains limited by its GLX/DRM detection path; the verified GLES/Zink/Turnip renderer is the relevant graphics evidence for this guest profile.


## Follow-up: adoption, terminal recovery, and interactive handoff

The live Debian guest was in `needs_adoption` because its rootfs had no Ternuxx private lifecycle receipt. `tx proot setup adopt-preview --user sbj` reported Debian 13/Trixie, the exact rootfs device/inode, all 14 requested base packages present, no package/service/guest changes, and an unblocked plan. The exact preview was applied. A fresh `tx proot setup status` now reports `status=adopted`, `next_action=none`, and an unchanged `dpkg` baseline; a second adoption preview reports no baseline changes. Adoption wrote only the private Native receipt and did not modify the guest. Optional desktop-apps, development, compatibility, and font groups remain uninstalled and are not part of the current base receipt.

`tx terminal service status` initially showed the installed broker, but `tx terminal status` failed because its private socket was stale. The exact socket preview found an owned mode-0600 Unix socket with a refused connection; the preview-bound recovery removed only that unchanged socket. The Runit service then recreated its socket and now reports `running`, source hash matching, and a responsive broker status.

A real `tx terminal start` preview showed the fixed Debian `sbj` login and exact rootfs identity. After confirmation, the attached shell returned `sbj` for `id -un`, Debian version `13.7`, and exit code 0. This first run exposed a final-output race when the guest exited. The broker now retains final PTY output until the client detaches and marks closed-session output; the CLI drains that output and exits cleanly. Targeted terminal broker/CLI tests pass 20/20. The fixed production Runit broker was restarted with no active guest session to load the corrected code, and the full interactive preview/login/identity/version/exit smoke passed again. `tx terminal status` now reports `pty_relay=not_connected`, the service remains running, and Ternuxx session records show the test login stopped. The isolated temporary test broker/state was removed. Native desktop `:1` remains running; the owner's nested `:2` session was not signaled or modified.

`tx pgui start --mode nested` now queries Native `:1` inside Debian and starts Xephyr at the current display size instead of fixed landscape geometry. `-resizeable` permits resizing the Xephyr host window; dynamic nested-screen changes across Android rotation/fullscreen are not verified. Current Native geometry is `752x1124`; parser tests cover portrait `752x1124`, landscape `1124x752`, and invalid/oversized values. The guest helper was live-queried through the shared-TMP route. Physical device rotation/fullscreen interaction remains untested, including whether Termux:X11 and its window manager update the host window bounds as expected.

## Follow-up: PRoot session-stop parity and app dispatch

The shared Ternuxx session-stop operation is now available through the CLI, TUI, Web, and GTK paths. CLI exposes `tx proot sessions list`, `tx proot stop-preview SESSION_ID`, and `tx proot stop SESSION_ID --yes --plan-id ID`; TUI and Web only offer verified running Ternuxx-owned sessions, show the exact preview, then require the typed `STOP` confirmation. GTK's bridge validator and prompt now use the runtime's actual `proot-` plus 32-hex session ID format; the previous `s-` format rejected every live session ID.

The CLI audit also found that the `app` command was listed twice in the dispatch case, making the allowlisted Debian XFCE menu route unreachable. The duplicate mapping was removed while preserving Native `tx app` software management; `tx app -- thunar` now routes to the fixed PRoot app launcher. The deprecated `tx mng proot` alias delegates to the current implementation. Web's Debian resource had two controls for the same `proot.status` operation; it now has one catalog-driven status control with the Debian-specific label.

At the session-stop parity checkpoint, the Native Termux full fixture suite passed `952` tests in `113.996` seconds, including CLI routing, Web syntax and control contracts, TUI exact-plan handling, and GTK bridge identifier validation. `git diff --check` passed. The current device inventory had no verified running Ternuxx guest session to stop, so no live stop was applied. External PRoot processes remained unverified and untouched; Native `:1` and the owner's nested `:2` remained untouched. Live installed-guest stop acceptance and physical Xephyr portrait/fullscreen rotation remain open.

## Follow-up: shortcut parity and full regression

CLI, TUI, Web, and GTK now expose fixed Debian shortcut add/remove using the shared list, exact preview, and confirmed apply operations. TUI and Web restrict choices to absent or Ternuxx-managed launchers, show the selected plan, and require `ADD SHORTCUT` or `REMOVE SHORTCUT`; conflicting or edited files are excluded and preserved. GTK already used this exact-plan contract. Sync rollback controls remain a parity gap.

The Native Termux fixture suite passes `959` tests in `119.204` seconds after adding the CLI router. The inline Web JavaScript syntax test passed, and CLI/TUI/Web contract tests verify service arguments and exact-plan confirmation. A live read-only `tx proot shortcuts list` returned the Debian launcher inventory; no live shortcut mutation was made. The owner's nested `:2` socket still has unknown process ownership and was left untouched. Physical portrait/fullscreen rotation, installed-guest client acceptance, and shortcut sync/rollback parity remain open.

## Follow-up: shortcut sync and rollback parity

The existing shared sync and rollback services are now reachable through all four clients. CLI exposes `tx proot shortcuts sync preview|apply` and `shortcuts rollback list|preview|apply`; TUI and Web show the exact changes and require typed confirmation; GTK displays the exact plan in a confirmation dialog and supports read-only rollback inventory plus ID-bound preview. All paths call the same typed operations and preserve stale-plan checks in the service. The GTK rollback picker uses the listed opaque rollback ID entered into its field.

Validation: `963` Native Termux fixture tests pass in `121.773` seconds. The focused client/service suite passed `224` tests. Python and shell syntax checks passed, the inline Web JavaScript syntax check passed, and the GTK4/VTE C source passed `clang -fsyntax-only -Wall -Wextra`. No live sync/rollback was applied; the live read-only inventory route was checked separately. Physical rotation/fullscreen and interactive GTK/Web/TUI acceptance on the installed guest remain open.

## Follow-up: compact shortcut inventory presentation

The live `tx proot shortcuts list` response exposed an unnecessarily large JSON dump of localized desktop-entry metadata. The human-readable CLI and Web results now show fixed/discovered launcher names, IDs, state, and a bounded diagnostics count; explicit CLI `--json` still returns the complete machine-readable inventory. Native CLI output was live-checked at 45 lines rather than thousands.

The updated full fixture suite passes `965` tests in `124.256` seconds. It includes presentation privacy/compactness and Web inline-JavaScript syntax checks. This is a presentation change only; no guest packages, launchers, or running GUI sessions were changed.

## Read-only live state recheck

`tx proot setup status` reports `adopted`, `next_action=none`, and a matching Debian package baseline. `tx terminal status` reports no connected PTY relay. `tx pgui status` reports Native `:1` running, standalone `:0` stopped, and a `:2` socket whose owner cannot be inferred from socket presence. `tx proot status --json` reports Debian installed and all Ternuxx-recorded sessions stopped; two host PRoot processes remain ownership-unverified. These were read-only checks; no guest, service, or display lifecycle action was performed.

A live `tx proot shortcuts sync preview` completed read-only against the installed Debian menu: 27 applications discovered, 28 launcher changes proposed, zero conflicts, and a valid plan ID. No apply was run, so Native launchers and the XFCE menu were left unchanged.

## Follow-up: setup handoff guidance across clients

TUI, Web, and GTK now give the same attached-Native-CLI handoff for a missing guest: create a fresh setup preview, review its image/package plan, and apply that exact plan. The instructions state that the guest sudo password is entered only in two hidden prompts, never as command arguments, and that an existing guest is preserved. Fresh installation remains in the attached CLI flow; UI clients do not collect or transmit guest credentials.

The updated Native Termux suite passes `967` tests in `116.305` seconds. Targeted TUI/Web/GTK/CLI guide tests pass, Web inline JavaScript syntax passes, and GTK C syntax plus `bash -n` pass. This completes user-facing setup handoff guidance, not live missing-guest installation acceptance.

## Follow-up: current-scope documentation alignment

Review found current architecture, API, readiness, Bengali overview, and several PRoot reference pages still described the temporary Native-only period as the active product direction. Updated those human-authored pages to state Native Termux host/control-plane ownership, optional Debian PRoot workloads, the reversal of ADR-0017, and links to current P11 evidence. The earlier removal audit and dated research remain historical snapshots. No generated `.repo` state was hand-edited.

Validation: `python3 tools/audit_documents.py` found zero broken local links; `python3 -m tools.repo_knowledge verify` reported zero findings; `git diff --check` passed. The current read-only `tx pgui status` reports the Native desktop running, standalone `:0` stopped, and a `:2` socket with unknown owner; the PRoot process inventory also includes ownership-unverified host processes. This shell has no `DISPLAY` and no `adb` executable. No GUI session was started, resized, or stopped, so Android-visible portrait/fullscreen rotation remains unverified and P11 stays open.

A read-only Native X11 query was possible through the installed `xdotool`: `:1` reported display geometry `752x1541`, while the visible window titled `Xephyr on :2.0` measured `1280x720` at `(5,56)`. The window had no PID property, and the Ternuxx status service still could not establish its owner. This confirms the currently visible Xephyr window is landscape-sized, but does not identify who started it or establish whether it is the P11 launcher. Nested GUI startup now checks Native display `:2` with the existing non-mutating X11 ownership helper and refuses `busy`, `stale`, or unknown states before guest validation or audio startup. It never reclaims the socket. Validation passed: geometry/routing/X11 helper tests `22/22`; full Native Termux fixture suite `969/969` in `108.317s`; `bash -n scripts/proot-gui0.sh`; document-link audit (zero broken links); `tools.repo_knowledge verify` (zero findings); and `git diff --check`. The existing `:2` window/socket were left untouched.


## Owner physical rotation acceptance

The owner manually tested the nested Debian Xephyr desktop on-device and confirmed both portrait and landscape/fullscreen presentation work after rotating the phone. This closes the physical rotation acceptance item based on owner observation; no screenshot or independent sensor/window measurement was captured. The visible `:2` window and socket remain ownership-unverified and were not modified. The launcher starts Xephyr using current Native display geometry and `-resizeable`; fullscreen and orientation are controlled through Termux:X11. An attempted xdotool fullscreen request was rejected by the current window-manager setup and has been removed.


## Standalone display and XFCE CPU label follow-up

On owner request, Native desktop `:1` was stopped through `tx stop` and the installed Debian XFCE session was launched on standalone Termux:X11 `:0`. `DISPLAY=:0 xdotool getdisplaygeometry` returned `752x1124`; the owner observed the About XFCE system page with Zink/Vulkan listed and CPU blank. Read-only Debian checks show eight CPUs and identify seven Cortex-A720 cores plus one Cortex-X4 with `lscpu`. The Android-backed guest `/proc/cpuinfo` exposes `CPU implementer` and `CPU part` but no `model name`; Xfce About's upstream parser checks only `model name`, `cpu`, and `Processor`, so it leaves the CPU label empty. This is a reporting mismatch, not evidence that guest CPU execution is absent.

The standalone X server and Debian XFCE processes remain present, but the recorded supervisor PID disappeared after startup. Consequently the ownership-aware `tx pgui status` reports `failed` for display `:0`, despite a responsive display socket and live child process records. Native `:1` remains stopped. Do not call managed PRoot lifecycle acceptance complete until supervisor persistence and safe stop/restart are fixed and verified.

After the PRoot provider identity fix and these GUI checks, the full Native Termux fixture suite passed `970/970` in `104.564s`; targeted desktop session/provider and GUI routing tests passed `30/30`; shell syntax checks and Python compilation passed. The current source includes a safe archive path for a verified failed startup record with absent processes and display, and the provider-aware desktop identity marker.


## Supervisor and CPU reporting fix

The prior live session was stopped through a new fail-closed orphan recovery path: it required the private PRoot `:0` record, an absent supervisor, live X11 and Debian process groups, a responsive display, and exact PID/start-time/UID/command/PGID/SID matches. It sent SIGTERM only to those two recorded session groups, recovered the exact display socket pair, and archived the old session record. Native `:1` remained stopped. The next launch detached the supervisor with `setsid`; `tx pgui status` now reports `running` with supervisor, X11, and Debian process identities live.

The PRoot wrapper generates a private CPU-info compatibility view by pairing Android `/proc/cpuinfo` processor IDs with Native `lscpu -p=CPU,MODELNAME` output, preserving existing CPU fields and adding only model-name values. The running PRoot command includes the bind to guest `/proc/cpuinfo`; a read-only guest query verified seven Cortex-A720 and one Cortex-X4 names. This should populate Xfce About's CPU row; the dialog itself has not yet been visually inspected after the restart.

Validation after these changes: full Native Termux fixture suite `977/977` in `103.922s`; the preceding targeted session/CPU/gui tests `30/30`; `tx pgui status` reports running; Native `tx gui status` reports stopped; `DISPLAY=:0 xdotool getdisplaygeometry` reports `752x1124`; `python3 tools/audit_documents.py --check`, `python3 -m tools.repo_knowledge verify`, and `git diff --check` are recorded after documentation refresh.


## Follow-up: live standalone graphics verification and regression

The owner-directed standalone Debian desktop is running on `:0`, while Native desktop `:1` is stopped and nested display `:2` is absent. `tx pgui graphics verify` completed successfully against the managed guest: GLES context creation reports OpenGL ES 3.2 and `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`; GLX reports direct rendering and `Accelerated: yes` with the same Zink/Adreno renderer; Vulkan enumeration reports Adreno 825 with Turnip and also the llvmpipe CPU device. This is context creation, renderer reporting, and device enumeration only; no presented frame, visual correctness, sustained performance, or inference offload was measured.

The focused GUI routing/CPU overlay/orphan recovery suite passes `13/13`. The complete Native Termux fixture suite passes `978` tests and `277` subtests in `110.60s`. `tx pgui status` reconciles the standalone supervisor, X server, and guest as running; `tx gui status` reports Native desktop stopped; `tx pgui status` reports `:2` absent. Display geometry depends on Termux:X11 mode: with fullscreen off it reported `208x442`; after the owner-requested fullscreen preference was enabled, the standalone screen reported `752x1630`. The CPU model overlay is verified through the running desktop bind and read-only guest query. The shared app-launch wrapper now prepares and binds the same private `/proc/cpuinfo` view for each separate Debian process. Live `xfce4-about` then visibly reported `Cortex-A720 × 7 Cortex-X4`; its GPU row reported Zink Vulkan 1.4 on Adreno 825 (MESA_TURNIP). The temporary capture included the local username and clock, so it was inspected and deleted rather than retained in the repository. Owner-confirmed portrait and landscape/fullscreen rotation remains accepted from the earlier on-device test.

P11 remains in progress for installed-guest interactive acceptance across CLI/TUI/Web/GTK and a final lifecycle/client review. P12 remains planned for broader Native CPU/GPU/NPU qualification; graphics rendering evidence does not change the separate workload-inference qualification or unimplemented NPU status.

## Follow-up: live read-only client routing

With the installed Debian guest and standalone XFCE left running on `:0`, a fresh read-only `tx proot status --json` and `tx proot shortcuts list --json` both returned successfully and identified Debian. The host process inventory still contains ownership-unverified PRoot processes; none were signalled or changed. The installed GTK desktop bridge's `proot-status` action also returned the live guest inventory through the shared service.

The TUI was opened in a sized `xterm-256color` PTY, navigated to “Debian PRoot & applications,” and completed the “Existing Debian PRoot” `proot.status` action. An authenticated local HTTP request through a temporary loopback-only management server returned HTTP 200 for the same `proot.status` operation and listed Debian. The server was closed after the request. These checks establish live read-only service routing through CLI, TUI, Web API, and GTK bridge; they do not establish browser-rendered Web or GTK-center visual acceptance, or acceptance of guest lifecycle mutations. The Native `:1` desktop remains off by owner request, so it was not started for a GTK visual test. The existing PRoot `:0` session and fullscreen preference remain unchanged.

P11 remains open for browser-rendered Web and GTK-center visual acceptance, installed-guest interactive terminal/lifecycle flows, and a final operation-parity review. P12 remains planned: the version-matched Vulkan package is installed and bounded inference is verified, while sustained CPU/GPU qualification and a usable, reproducible NPU path remain open.

## Follow-up: GTK center on the active PRoot display

To keep the Native XFCE session `:1` stopped, the installed Native GTK management-center binary was launched directly with `DISPLAY=:0` against the already-running Termux:X11 server. The center rendered over the Debian XFCE desktop, and its “Debian PRoot & applications” view completed the live read-only `proot.status` request, listing the installed Debian guest and preserving the explicit unverified status of unrelated host PRoot processes. The window was closed with Alt+F4; the exact center process exited 0 without a GTK warning, and the Debian desktop remained running at `752x1630`. Temporary captures used for visual inspection were deleted because the screen included the local username and clock. This verifies GTK rendering and its read-only PRoot status path on the active display; the supported `tx mng center` launcher still targets a verified Native `:1` session, and no Native desktop was started.

The remaining P11 visual item is the browser-rendered Web UI. Installed-guest terminal and lifecycle acceptance plus the cross-client operation-parity review remain open.


## Follow-up: Debian app-launch route repair and XFCE About inspection

The generated dynamic Debian launcher used `tx mng app launch --desktop-id ...`, but live dispatch reached the Native package-app help instead of the PRoot service. After adding the management CLI route, the service CLI parser still rejected `--desktop-id`; both defects are fixed. The route accepts either a fixed app ID or one discovered desktop ID, validates the optional X11 display, and invokes the existing typed `proot.app.launch` operation. The PRoot GUI app wrapper now accepts only a verified Native `:1` session or a verified standalone Debian `:0` session, checking provider identity, process/display evidence, and mutual exclusion before launching.

Focused verification passes `99` tests with `8` subtests, including CLI dispatch, desktop-ID payload parsing, shortcut launch wiring, provider session state, and CPU-info binding for app processes. Live `tx mng app launch --desktop-id xfce4-about.desktop --display :0` opened `About the Xfce Desktop Environment`. The first capture showed the floating-mode `208x442` screen clipping its `648x600` window. Termux:X11 fullscreen was enabled with `termux-x11-preference fullscreen:true`; the live screen then reported `752x1630`. After the app-launch wrapper bound the private CPU-info view, a fresh capture visibly showed CPU `Cortex-A720 × 7 Cortex-X4` and GPU `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))`. The About window and exact app process were closed; the PRoot desktop remained running. Captures/logs were deleted after inspection because the image included the local username and clock. `ffmpeg` could not start because its Native shared-library dependency was unresolved; `scrot` provided the temporary captures.


## Follow-up: full regression after standalone app and CPU reporting fixes

The complete Native Termux suite passes `984` tests and `277` subtests in `129.80s`. `bash -n` passes for the changed shell entrypoints. The document path/hash audit reports zero broken local links, `tools.repo_knowledge verify` reports zero findings, and `git diff --check` passes. Live PGUI state remains reconciled as running on `:0`; Native `:1` remains stopped. Termux:X11 fullscreen is enabled and `DISPLAY=:0 xdotool getdisplaygeometry` reports `752x1630`. The temporary About window and capture were closed/deleted after visually verifying CPU Cortex-A720 × 7 Cortex-X4 and GPU Zink/Vulkan Adreno 825. P11 interactive acceptance across TUI/Web/GTK and final lifecycle review remain open.


## Follow-up: native menu routing and supervisor persistence

The owner asked to keep the Native GUI on when the separate Debian GUI is not needed. The managed PRoot display `:0` was stopped through its ownership-verified `tx pgui stop` path; the adopted Debian rootfs was preserved. Native XFCE was started on `:1`. Its Applications menu visibly shows the separate **PRoot Apps** category. Live shortcut inventory reports 27 guest applications, all 27 installed, with zero absent entries and zero conflicts; the read-only sync preview reports no remaining changes. This verifies menu presentation and inventory, not clicking a guest launcher.

That check exposed a menu-path mismatch when PRoot XFCE is active. The shortcut service previously defaulted to the Native XFCE tree even when the managed Debian display used its own per-session XDG paths. It now selects the PRoot XFCE tree only when `desktop_session_state.inspect` verifies the recorded PRoot session and `:0`/`:2` display live; otherwise it keeps the Native XFCE tree. Explicit XDG environment overrides remain honored. Against the verified PRoot `:0` session, the exact preview listed 27 launcher entries, one menu definition, one category directory, and no conflicts. Applying that exact plan created those files under the private PRoot XFCE tree, leaving the existing Native menu tree intact.

Starting Native XFCE from a short-lived Native shell also exposed that its supervisor inherited the caller's process session and disappeared when that shell exited, leaving the GUI children unowned. The Native launcher now starts the supervisor with `setsid`, matching the PRoot supervisor's detachment, and checks that `setsid` is present. The fixture verifies the supervisor remains live in its own process group and session after its caller exits. The orphaned previous Native session was stopped only through the exact recorded child identities; a fresh `tx gui start` now remains `running` with supervisor, Termux:X11, and XFCE identities live. `tx pgui status` reports Native `:1` running, standalone PRoot GUI stopped, and nested `:2` absent.

The focused service/shortcut suite passes 78 tests, and the detached-supervisor lifecycle fixture passes. The full Native Termux suite passes 986 tests in 105.554 seconds. `bash -n lib/desktop.sh`, Python compilation for the changed service/tests, and `git diff --check` pass. Browser-rendered Web acceptance is recorded below; installed-guest terminal/lifecycle interaction across clients and final parity review remain open for P11.


## Follow-up: browser-rendered Web PRoot status

With the Native GUI on `:1`, `tx web --browser native --port 8765` opened the authenticated local Web UI in Native Firefox 158.0.1 after clearing the session's inherited `LD_LIBRARY_PATH`. The browser auto-filled the one-time code, connected to `127.0.0.1`, and rendered the `Debian PRoot & applications` category and its three resources. Selecting the live-status action returned the installed Debian distribution, no active Ternuxx-managed guest session, and explicit unverified ownership for unrelated host PRoot processes. No mutation action was activated. The foreground Web server was stopped, the one-time clipboard code was cleared, port `8765` was confirmed closed, and temporary captures were deleted after visual inspection.

This closes browser-rendered Web visual and read-only PRoot status acceptance. Installed-guest terminal/lifecycle mutation through the other clients and the final operation-parity review remain open. Current live GUI state is Native `:1` running with supervisor, X11, and XFCE identities verified; standalone Debian GUI `:0` is stopped; nested `:2` is absent.

## Follow-up: installed-guest terminal and lifecycle acceptance

The installed Debian Trixie guest was opened through the Native interactive CLI; `/etc/os-release` returned `ID=debian`, `VERSION_ID=13`, and the managed session exited cleanly. The TUI started a bounded isolated guest probe, showed its exact verified process ownership and signal preview, and stopped it only after the typed `STOP` confirmation. Two additional probes expired naturally. The GTK management center was rebuilt from current repository source after its installed identity was found stale; its session-stop action previewed and stopped the exact selected probe. The browser Web client previewed the exact selected guest session and stopped it after typed confirmation. These checks exercised the same shared typed lifecycle operations across CLI, TUI, Web, and GTK.

The TUI also inspected and reconciled a disposable exited guest using `process_absent` evidence and a preview-bound `mark_exited_without_signal` action; no signal was authorized. Two older stale records were likewise reconciled only after identity inspection established their original processes had exited, with signaling disallowed. The terminal broker service remains installed, running, and source-matched. The current managed session inventory reports every recorded session stopped; Native XFCE `:1` remains running, Debian display `:0` is stopped, and nested `:2` is absent. Unrelated PRoot host processes remain ownership-unverified and untouched.

The final full Native Termux regression passes 986 tests in 120.565 seconds. `git diff --check` passes. Browser-rendered Web status and GTK rendering were previously inspected live; Native GUI remains available as requested. No guest removal or rootfs mutation was performed.

## Evidence

Gate: PASS

## Acceptance criteria

- Debian PRoot setup, interactive login, bounded guest sessions, and guest application routing are implemented and verified on Native Termux.
- Shared guest lifecycle and recovery operations are available through CLI, TUI, Web, and GTK with exact-plan review and typed confirmation where required.
- Live guest stop and exited-session reconciliation were verified without signaling unverified processes or touching unrelated host PRoot processes.
- Native and Debian desktop ownership is explicit; the Native GUI remains running and the stopped Debian GUI/rootfs remain preserved.
- Full repository tests and documentation integrity checks pass; known ownership uncertainty and historical GUI rotation evidence remain explicit.
