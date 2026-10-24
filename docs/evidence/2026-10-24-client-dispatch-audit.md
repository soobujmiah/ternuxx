# Shared client dispatch audit — 2026-10-24

Evidence class: source inspection and existing regression tests

## Evidence

`lib/management_service.py` defines the central typed operation allowlist and dispatches operations to the domain modules. An AST check found 148 operation IDs and 148 unique keys; no duplicate key silently replaces another contract.

The inspected product routes converge on that service:

- The Native CLI shell modules call `management_service.py` for management, AI, PRoot, graphics, recovery, SSH, and related operations.
- TUI helper `_call` in `lib/terminal_ui.py` invokes `management_service.dispatch`.
- Web's `management_http_adapter.py` uses `management_service.dispatch` as its default dispatcher; `management_http_runtime.py` supplies the shared service to the runtime.
- GTK's C application invokes the fixed `scripts/management_desktop_bridge.py`; the bridge dispatches each typed request through `management_service.dispatch`.

The regression suite includes a duplicate-operation-key assertion, an explicit authorization-scope assertion for every application operation, a Web-session security-class assertion for every operation, shared Web dispatch tests, TUI service-client tests, and GTK bridge/UI contract tests. The full repository suite passed 1033 tests in the source revision audited at that point.

## Finding and limit

CLI, TUI, Web, and GTK keep separate presentation code, as expected for their input and display models, while using the shared service for typed backend operations. The first pass confirmed that the inspected clients did not duplicate domain implementation code; the follow-up below found and removed a redundant typed-operation alias.

This source audit does not prove that every operation is reachable and presented correctly in every client, nor does it verify rendered Web/GTK visual parity, accessibility, or live user flows. Those checks remain open in the [capability matrix](../architecture/CAPABILITY-MATRIX.md) and [feature matrix](../testing/FEATURE-MATRIX.yaml). Keep `management.shared_service` at `PARTIAL` until that per-operation and rendered-client acceptance is complete.

## Reproduction

```sh
python3 -m unittest tests.test_management_authorization tests.test_management_http_adapter tests.test_terminal_ui tests.test_management_desktop_bridge tests.test_management_center_ui_contract -q
python3 - <<'PY'
import ast
from pathlib import Path
tree = ast.parse(Path("lib/management_service.py").read_text())
node = next(n for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "OPERATIONS" for t in n.targets))
keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
print(f"{len(keys)} operation IDs; {len(set(keys))} unique")
PY
```

## Validation

- Focused client/service suite: 149 tests passed.
- Operation-map check: 148 IDs, 148 unique.
- `python3 tools/audit_documents.py --check`: 521 documents indexed, 161 marked read, zero broken local links. This count does not mean all repository documentation has been reviewed.
- Strict README bridge, repo-knowledge verification, and `git diff --check` passed.


## Follow-up — canonical SSH diagnostics operation

A per-client resource-route review found that `ssh.inspect` and `native.ssh.status` both called `ssh_diagnostics.inspect_native` with identical arguments and the same `diagnostics.read` capability. GTK selected the alias for the managed 8023 resource, while other clients used `ssh.inspect`. This was duplicate API surface without distinct behavior.

The redundant `native.ssh.status` operation has been removed from the service allowlist, authorization map, Web session classification, catalog, and presentation labels. GTK now uses `ssh.inspect` for both SSH resources, and the Web status chooser uses the same canonical operation. The remaining 147 operation IDs are unique. A regression confirms the removed alias fails as unsupported and both GTK resource inspections converge on `ssh.inspect`.

The same review found `cron.executor.self_test` was the only service operation absent from both resource and domain inventories. It is the fixed, no-side-effect action behind Cron’s `scheduler.self_test`; the operation now appears in the Cron resource and domain. A regression requires every service operation to be classified. These source corrections do not complete per-operation client reachability, rendered parity, accessibility, or live UI acceptance; those remain open in the [capability matrix](../architecture/CAPABILITY-MATRIX.md).

### Follow-up validation

- Focused authorization, service, catalog, and GTK bridge tests: 19 passed.
- `bash scripts/repo_test.sh`: 1036 tests passed; CLI help contract passed.
- Strict README bridge, document inventory/link check, repo-knowledge verification, and `git diff --check` passed.

### Web presentation duplicate cleanup

A second source pass found three duplicate keys in the Web operation-label object for managed SSH Wake Lock status, preview, and apply. JavaScript silently kept the later labels. The duplicates were removed and a regression now requires unique keys in the operation-label map. The focused regression and inline JavaScript syntax check both passed after the cleanup.

### Shared presentation duplicate cleanup

A literal-dictionary scan found a second `ssh.inspect` key in the Python operation-label map. The duplicate label was removed and consolidated to `SSH diagnostics`. A regression now verifies unique keys in the Python operation-label map; the focused Python/Web label and JavaScript syntax checks passed.

### Follow-up — fixed SSH definition deployment reach

The current shared-operation allowlist also exposes `ssh.service.deploy`, `ssh.service.deploy.rollback.preview`, and `ssh.service.deploy.rollback.apply`. `lib/ssh.sh` provides these through the Native CLI. Source inspection found no corresponding deploy/rollback action in the TUI or GTK client; the Web runtime has a regression that rejects `ssh.service.deploy` with `permission_denied` before shared dispatch. This is a real per-operation reach difference, not duplicate backend implementation.

The current [SSH lifecycle contract](../architecture/SSH-LIFECYCLE.md) and [coverage matrix](../architecture/CAPABILITY-MATRIX.md) now state this limitation directly. The gap remains open: either implement a shared preview-confirmed flow in the clients where policy permits, or record a reviewed product boundary for CLI-only definition deployment. The Web deny should not be removed without a separate capability/session-scope review. No service definition was deployed or changed during this source audit.

Validation: `tests.test_management_http_runtime` contains `test_web_mode_exposes_scoped_desktop_monitoring_and_managed_ssh_8023_mutations`, which asserts the deploy request is denied without dispatch. The full suite passed 1,041 tests on this source state; source absence in TUI/GTK is an inspection result, not runtime UI acceptance.

### Follow-up — SSH definition deploy and rollback client parity

The reviewed gap above is now closed in source. TUI previews `ssh.service.deploy`, displays the exact plan, and applies only after the owner types `yes`; rollback lists only completed or recovery-needed `service.deploy` journal entries, previews the selected operation, and confirms its exact plan. GTK uses fixed bridge actions and exact preview IDs for deploy and rollback, with the same journal filter. The bridge rejects malformed operation/plan IDs and dispatches only the shared typed operations. No service definition was deployed or rolled back during this work.

Web sessions can opt into `services.manage` through a separate unchecked login checkbox. Authorization maps that grant only to `ssh.service.deploy` and `ssh.service.deploy.rollback.apply`; rollback preview remains read-only. The existing Web regression confirms deploy is denied without the grant, and the scoped Web tests exercise preview and apply dispatch. The UI labels clearly state that only the fixed Runit definition changes and that the current daemon is not restarted.

Validation: the focused TUI, bridge, Web-runtime, and GTK-contract suite passed 166 tests; `bash scripts/repo_test.sh` passed 1,048 tests. `git diff --check` and `clang -fsyntax-only -Wall -Wextra apps/management-center/management-center.c $(pkg-config --cflags gtk4 vte-2.91-gtk4)` passed. The GTK source compiles syntactically; rendered UI acceptance remains open. No live service action was run.
