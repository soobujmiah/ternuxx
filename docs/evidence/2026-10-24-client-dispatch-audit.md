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
