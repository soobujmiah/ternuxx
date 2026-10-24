# P12 repository regression follow-up — 2026-10-24

Phase: `P12`
Gate: PASS for this repository regression slice; accelerator qualification remains open.

## Finding

The shared management operation registry contained duplicate PRoot keys that Python silently overwrote. Web session authorization also relied on two manually maintained operation sets, so a newly added service operation could otherwise miss explicit read-only or mutating/CSRF classification. The NPU runtime preview exposes a live free-space observation, which can change between calls even when the pinned install plan is unchanged.

## Correction

Removed the duplicate registry entries and redundant duplicate assertion. Added regression checks that reject duplicate operation keys and require every service operation to appear in exactly one Web-session security class. Updated the NPU preview test to prove the plan remains stable while its displayed free-space observation changes.

## Verification

`env -u LD_LIBRARY_PATH bash scripts/repo_test.sh` passed 1,008 Python tests in 113.190 seconds and the CLI help/preview contract. The authorization and HTTP runtime slice passed 40 focused tests. After adding preview-gated CLI routing/help for reversible legacy Turnip ICD migration, 30 PRoot setup/CLI tests and 2 focused routing/help tests passed before the latest full run. `python3 -m tools.repo_knowledge verify`, strict README bridge validation, document path/hash validation, and `git diff --check` passed. This slice used fixtures and mocks; no live inference workload was started.

## Evidence

- Registry and authorization contract: `lib/management_service.py`, `lib/management_sessions.py`.
- Regression tests: `tests/test_management_authorization.py`, `tests/test_npu_inference.py`.
- Full-run summary: `.repo/STATUS.md`.
