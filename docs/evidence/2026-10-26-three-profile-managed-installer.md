# Three-profile managed installation

## Request and implementation

The owner requested a reproducible, managed reinstall through `./tx install`, with
three workstation profiles, device/system information, keyboard selection rather
than typed profile/distro/desktop IDs, selectable Native apps/DEs and multiple PRoot
guests. The implementation uses `lib/install_wizard.sh` and a dependency-free Bash
selector (`lib/install_picker.sh`) so first-run selection does not require Python.

Preparation refreshes signed indexes and bootstraps official X11/Python with explicit
confirmation. A system-wide upgrade is separately simulated, pinned, journaled and
confirmed. Native components continue through the existing exact-plan package engine.
The tx shim uses its existing preview/apply installer. Full profiles build the GTK
management center. Adreno/KGSL backend selection is optional and probe-gated.

Supported Native DEs are XFCE/MATE/Plasma. Native apps are Firefox, Audacious,
Ristretto, Evince, Mousepad, Xarchiver and VLC. Guest selections use Debian/Ubuntu
managed setup and desktop catalogs with accepted routes. GNOME/Cinnamon, which
have no accepted route, are not offered by the guided selector. Usernames/passwords
remain text/hidden inputs. The Native repository has no `libreoffice-writer` package;
its monolithic `libreoffice` is deliberately not substituted for Writer-only.

`tx pgui DE` forwards to the existing supervised start path; `xfce4` aliases `xfce`.
Default selection prefers installed XFCE. Existing standalone :0 / Native :1 + nested
Xephyr :2 ownership and route checks remain in place; Plasma remains standalone-only.

## Validation and boundaries

- Twelve new keyboard, orchestration, component, shortcut and upgrade-safety fixture
  tests passed, including refusal of a changed or non-official upgrade transaction.
- Five distro-named installer CLI tests passed, including PTY arrow/Space confirmation
  and the exact preview-to-apply guest plan.
- Thirty package-plan regression tests passed after updating the omitted-component
  assertion for the expanded catalog.
- Shell syntax and the CLI help contract passed; documentation links have no broken
  local targets; the README knowledge bridge passed.
- The first broad local run executed 1,235 tests: the old omitted-component assertion
  failed (subsequently corrected and rechecked above), and two modules could not import
  because this fresh runtime lacks PyYAML. No dependency was manually installed to
  bypass the owner's managed-install constraint. CI installs requirements-dev.txt and
  provides the full repository gate for the pushed revision.

No package install/upgrade, guest creation, desktop lifecycle action, Android UI
interaction, GPU workload or GTK build was run by the agent during this revision.
The owner's independent install session was left untouched. Clean-device reinstall,
rendered GUIs, nested rendering and acceleration remain separate live acceptance.

## Follow-up: clean guests, optional software and later additions

The owner clarified that Minimal must include the PRoot CLI provider, while managed
guests retain their pinned base/clean graphics, CPU rendering and sound configuration.
Optional guest apps are now selected after DEs and bound into that same preview.
Writer-only requests `libreoffice-writer`; shared dependencies are allowed, while
Calc/Impress are not requested. Debian keeps Firefox ESR (owner-reported working in
PRoot); Ubuntu uses the APT-native Epiphany option rather than a Snap transition.

Later additions use `tx install xfce|mate|plasma` and
`tx install proot [debian|ubuntu] [DE]`. Existing canonical Debian/Ubuntu guests use
the extended preview-bound desktop/app transaction; their rootfs and account remain
intact. Source/package changes invalidate the plan, guest-idle checks remain required,
and both requested packages and dependency versions are pinned. A fully installed
selection returns a no-op. The original guest snapshot/configuration path remains
in use for fresh installs. This provisions workstation rendering libraries and audio;
it does not install or qualify an AI inference model/backend.

The first revision `c885605` passed GitHub Actions run
[40346171127](https://github.com/soobujmiah/ternuxx/actions/runs/40346171127).
Follow-up fixture checks passed: 13 wizard/shortcut tests, 5 installer CLI tests,
29 fresh-setup tests, 20 setup tests, 9 desktop/add-on tests and 3 optional-software
tests. Ubuntu Writer add-on apply, an existing XFCE no-op, default clean packages,
Snap avoidance and unknown app refusal are explicitly covered. The follow-up still
requires its own CI result and the owner's live reinstall acceptance.

The PRoot shortcut also provisions the Native X11/PulseAudio/Xephyr bridge through
its exact Native package preview when adding a guest GUI to a Minimal host. Explicit
short desktop names are checked against accepted provider routes before that package
phase, so unsupported names cannot trigger partial provider installation.

## Follow-up: install-first help and optional headless acceleration setup

Main help now starts with `./tx install` and lists later Native DE, PRoot and GPU
commands. All guided profiles include Native sound/graphics runtimes. The shared
`tx install gpu` scope selector precedes package changes and offers Native/PRoot/
both setup without requiring a desktop. Native Zink is offered only after supported
Vulkan enumeration, with existing preferences preserved by default. On a clean host
it becomes the first recommendation after the successful probe. PRoot uses the
managed pinned Turnip staging helper, CPU rendering libraries and authenticated
Native sound integration; the CPU-runtime-only choice does not stage Turnip.
`none` is an explicit headless desktop choice, and is mutually exclusive with DEs.
Existing guest runtime changes bind the manifest and KGSL snapshot into their exact
package plan; unknown driver content is refused, not overwritten. No live installer,
driver configuration, service or GUI action was performed by the agent.

Focused checks passed: 16 wizard/keyboard/GPU-offer tests, 30 fresh setup tests,
10 managed guest desktop/runtime tests and 4 guest software tests. This includes
headless CPU/audio without Turnip staging, checksum-helper reuse for an existing
headless graphics addition, and omission of an unsupported Native GPU option.
Prior revision `9ab2a39` had one unrelated CI Mesa recipe fixture subprocess exceed
its existing ten-second timeout; the next complete CI run must independently pass.
