# Replay-guest lifecycle client parity — 2026-10-24

Phase: `P12`

## Evidence

The shared service and catalog retained receipt-verified replay-guest retirement and restore after a client-reach regression removed controls from GTK, TUI, and Web. GTK was restored first; this follow-up restores the TUI flow and authenticated Web flow while keeping the lifecycle confined to the dedicated `proot.replay-guests` resource.

All four clients now reach the typed service: CLI uses the shared command route, TUI requires an exact alias/backup preview and typed confirmation, Web uses authenticated CSRF-protected preview/apply under the dedicated `proot.replay.manage` session grant, and GTK uses its inline exact-target review bridge. The Web grant does not authorize the legacy ICD migration operations, which remain CLI-only.

Source and adapter verification on 2026-10-24:

- `python3 -m unittest tests.test_management_authorization tests.test_terminal_ui tests.test_management_http_runtime tests.test_management_desktop_bridge tests.test_management_center_ui_contract -q` — 168 tests passed.
- The HTTP adapter test denies a preview without CSRF and verifies preview/apply dispatch with the narrow replay scope, CSRF token, idempotency key, and typed target. Service execution is mocked.
- The GTK bridge/UI coverage is included in the 168-test run; a prior source restoration record documents its C build and `--self-check` result.
- No guest preview or apply action was run. This does not qualify browser rendering, visible client interaction, or a live guest lifecycle operation.
