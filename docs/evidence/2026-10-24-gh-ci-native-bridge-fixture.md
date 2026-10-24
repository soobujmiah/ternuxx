# P12 evidence: GitHub Native bridge test fixture correction

Phase: `P12`
Gate: PASS for this regression correction; P12 remains in progress.

## Finding

GitHub Repository Knowledge Sync run `40059254710` tested source revision
`e5f1c5a5886016bab2aaa0b342001d89f8ba3945` on Ubuntu with Python 3.14.8. The
repository-test step ran 738 tests and reported 41 failures, all in
`ManagementDesktopBridgeTests`. The bridge correctly requires both
`TERMUX_VERSION` and the exact Native Termux `PREFIX`; those tests inherited the
Ubuntu runner environment, so `bridge.main()` returned exit code 2 before
reaching the mocked service. The workflow then committed the failed test state
to generated `.repo` metadata and exited nonzero by design.

## Correction and verification

`tests/test_management_desktop_bridge.py` now gives its unit tests an explicit
Native Termux fixture environment and includes a negative test proving that a
non-Termux environment is still rejected before dispatch. The product guard is
unchanged. `tests/test_cli_help.sh` now supplies the same isolated Native
environment for its CLI smoke checks and replaces the read-only apt simulation
with a deterministic fixture, so host package state is not consulted.

On Native Termux, the focused GTK bridge suite passed 53/53 tests. The canonical
`bash scripts/repo_test.sh` runner passed 1,000 Python tests and its CLI
help/preview contract before the later PRoot lifecycle regression was added.
The latest host-like full runner passed 1,017 Python tests in 94.697 seconds
with `TERMUX_VERSION`, `PREFIX`, and `LD_LIBRARY_PATH` removed, matching the
relevant GitHub host condition. `python3 -m tools.repo_knowledge verify` reported zero findings,
`python3 tools/doc_bridge.py check --strict --project-id ternuxx README.md`
passed, and `git diff --check` passed.

The correction and later parity updates are present only in the local worktree
at this review point. GitHub run `40059254710` tested the prior `e5f1c5a`
source: its validation job completed, but the repository-state sync job
recorded the failed test status and failed intentionally. The new local
host-like pass is not remote CI evidence; publish the reviewed source changes
and require a successful GitHub run before calling remote CI green.

## Latest regression after guide and documentation audit

On 2026-10-24, the `tx guides` menu was expanded to surface CPU/GPU/NPU status
and Debian status/setup preview. The first full-suite rerun passed all other
tests but exposed two stale menu-label assertions; those assertions were
updated, the focused guide tests passed 2/2, and the CLI launch tests passed
11/11. A fresh Native Termux run of `env -u LD_LIBRARY_PATH bash
scripts/repo_test.sh` then passed 1,001 Python tests and the CLI help/preview
contract in 113.652 seconds. The working tree was dirty and based on
`e5f1c5a`; this remains local evidence, not a clean GitHub Actions result.

## Evidence

- GitHub run: `40059254710`, source `e5f1c5a5886016bab2aaa0b342001d89f8ba3945`.
- Local fixture diff: `tests/test_management_desktop_bridge.py`.
- Focused verification: `python3 -m unittest discover -s tests -p 'test_management_desktop_bridge.py'` — 53 passed.
- Native full verification: `bash scripts/repo_test.sh` — 1,000 Python tests and CLI help/preview contract passed before the additional lifecycle regression test.
- Latest host-like full verification: `env -u TERMUX_VERSION -u PREFIX -u LD_LIBRARY_PATH bash scripts/repo_test.sh` — 1,017 Python tests in 94.697 seconds and CLI help/preview contract passed.
- Repository checks: deterministic knowledge verification reported 0 findings; strict README bridge validation and `git diff --check` passed.

## Acceptance criteria

- GTK bridge unit tests supply the Native Termux contract explicitly on all hosts.
- A separate negative test confirms a non-Termux host is rejected without dispatching a management operation.
- The CLI smoke contract works without host Termux variables and does not consult the runner's package database.
- Focused and full local repository tests pass after the fixture change.
- No remote CI pass is claimed until GitHub Actions reruns on the corrected source.
