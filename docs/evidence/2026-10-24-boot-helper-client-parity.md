# Termux:Boot helper parity and Native source reconciliation — 2026-10-24

Evidence class: source/tests plus a narrowly scoped Native Termux status, exact preview, and exact-plan apply.

## Finding

The shared service and CLI already supported status, preview, deploy, and rollback for the two fixed repository-owned helpers (`00-ternuxx-services` and `ternuxx-recovery`). The TUI, GTK center, and Web UI did not expose those operations. Status also omitted the saved snapshot IDs needed to select a rollback target.

## Changes

- `boot.helpers.status` now includes metadata for the 40 newest recorded rollback snapshots. It does not expose snapshot bytes or change files; rollback preview still verifies the chosen snapshot bytes and installed helper identity.
- TUI and GTK expose helper selection, deploy/rollback, exact-preview review, and confirmation. The bridge validates helper IDs, action, snapshot ID, and exact plan ID before shared-service dispatch.
- Web exposes the same flow only after the user opts into the separate `boot.helpers.manage` session scope. Status remains under `diagnostics.read`; the write scope covers only `boot.helpers.preview` and `boot.helpers.apply`.
- Web requests now include idempotency keys for helper preview/apply and Cron boot preview, both of which persist plans.
- The installed Native `services` helper had three stale PRoot-only wording/marker lines; its service behavior already matched the Native-only source. An exact preview-confirmed deploy brought the file to source identity and retained the prior bytes in the private rollback snapshot store. The recovery helper already matched.

## Validation

- Focused boot-helper, authorization, Web-runtime, TUI, bridge, GTK-contract, and shared-service suite: **251 tests passed**.
- `bash scripts/repo_test.sh`: **1,062 tests passed**; CLI help contract passed.
- GTK syntax check passed with `clang -fsyntax-only -Wall -Wextra` and the installed GTK4/VTE flags.
- `python3 -m tools.repo_knowledge verify`: zero findings; `git diff --check` passed.
- Native read-only `tx mng boot helpers status --json` after apply reports both fixed helpers `identity=match`, mode `0700`, and four recorded snapshots. `boot_delivery` remains `not_qualified`.

The helper script was not executed, no service was started or stopped, and no Android reboot was performed. This verifies source reconciliation and client/API coverage, not Termux:Boot delivery.
