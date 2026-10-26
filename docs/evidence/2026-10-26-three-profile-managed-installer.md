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
