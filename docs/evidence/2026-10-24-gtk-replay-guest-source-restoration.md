# GTK replay-guest lifecycle source restoration — 2026-10-24

The replay-guest catalog entry and shared retirement/restore operations remained in source, but the current GTK center no longer exposed their controls. Historical device evidence in [the P4 acceptance record](2026-10-22-gtk-replay-guest-apply.md) documents a previously working inline review panel and explains why the stock GTK4 alert was replaced.

The Native GTK client now exposes exact-alias retirement and exact backup-ID restore previews for `proot.replay-guests`. The typed bridge checks the `ternuxx-replay-NAME` alias, 32-character backup ID, 64-character plan ID, confirmation requirement, and exact target returned by the shared service. GTK displays an inline review with the alias, plan, backup ID, impact, no-delete guarantee for retirement, and explicit Cancel and Apply buttons. Apply rechecks the selected resource and the current entry values against the reviewed target; changing resources or inputs invalidates the review. TUI and Web continue to omit this specialized lifecycle operation; CLI remains available.

At the time of this source restoration, TUI and Web controls were also absent. A later same-day parity follow-up restored those controls with a dedicated Web session scope; see [the cross-client restoration record](2026-10-24-replay-guest-client-parity.md).

Source-level verification on 2026-10-24:

- `python3 -m unittest tests.test_management_desktop_bridge tests.test_management_center_ui_contract -q` — 72 tests passed after the change.
- The GTK4/VTE C source compiled with `clang -O2 -Wall -Wextra`; the built client `--self-check` reported GTK 4.24.1.
- After updating the client capability matrix, `env -u LD_LIBRARY_PATH bash scripts/repo_test.sh` passed 1,011 Python tests in 113.003 seconds plus the CLI help/preview contract.
- `python3 -m tools.repo_knowledge verify`, strict README bridge validation, `python3 tools/audit_documents.py --check`, and `git diff --check` passed.
- No guest preview or apply operation was run. The GTK application, Termux desktop, and guest state were left untouched. This source-level check does not replace a fresh visible-device interaction test.
