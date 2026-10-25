# Desktop supervisor CI test timeout follow-up

## Observation

GitHub Actions run [40242792907](https://github.com/soobujmiah/ternuxx/actions/runs/40242792907) ran 1,192 tests and reported one failure in `test_proot_exec_transition_preserves_owned_process_group`: the test harness did not observe the supervisor exit within its 8-second `Popen.wait` timeout after SIGTERM. The job log did not include process-state evidence at the timeout, so the underlying timing cause is not established. The repository validation job completed with that single reported failure; deterministic-state sync correctly marked the workflow failed.

## Change

The fixture now allows up to 20 seconds for bounded shutdown, includes the recorded lifecycle state in a failure, and cleans up only fixture process groups whose PID, start ticks, PGID, and SID still match the private session record. This preserves the normal SIGTERM and stopped-state assertions while preventing a failed test from leaving its exact fixture processes behind.

## Validation

- The previously failing isolated test passed 30 consecutive repetitions before the timeout adjustment.
- All seven `test_desktop_supervisor` tests passed after the adjustment.
- The full repository suite passed 1,193 tests in 158.197 seconds after the GTK checkbox picker and supervisor test-harness update; CLI help contract passed.
- Document inventory/link audit, repository knowledge verification, GTK C syntax check, and `git diff --check` passed.

## Limits

The original 8-second timeout event was not reproduced, and no product-code defect was demonstrated. The timeout was widened with a finite bound and stronger diagnostics; it does not establish a root cause for the single hosted-run slowdown. A successful GitHub validation run for the follow-up commit remains pending.
