# Shared client dispatch audit — 2026-10-24

Evidence class: source inspection and existing regression tests

## Evidence

`lib/management_service.py` defines the central typed operation allowlist and dispatches operations to the domain modules. An AST check found 148 operation IDs and 148 unique keys; no duplicate key silently replaces another contract.

The inspected product routes converge on that service:

- The Native CLI shell modules call `management_service.py` for management, AI, PRoot, graphics, recovery, SSH, and related operations.
- TUI helper `_call` in `lib/terminal_ui.py` invokes `management_service.dispatch`.
- Web's `management_http_adapter.py` uses `management_service.dispatch` as its default dispatcher; `management_http_runtime.py` supplies the shared service to the runtime.
- GTK's C application invokes the fixed `scripts/management_desktop_bridge.py`; the bridge dispatches each typed request through `management_service.dispatch`.

The regression suite includes a duplicate-operation-key assertion, an explicit authorization-scope assertion for every application operation, a Web-session security-class assertion for every operation, shared Web dispatch tests, TUI service-client tests, and GTK bridge/UI contract tests. The full repository suite passed 1033 tests in the current source revision.

## Finding and limit

No duplicate backend operation catalog or second client-specific implementation of the inspected management business operations was found. CLI, TUI, Web, and GTK keep separate presentation code, as expected for their input and display models, while using the shared service for typed backend operations.

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
