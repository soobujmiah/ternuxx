# Pulse cookie test fixture and CI result

**Date:** 2026-10-25 (Asia/Dhaka)  
**Evidence class:** GitHub Actions failure log plus local test execution  
**Failing run:** [40177494173](https://github.com/soobujmiah/ternuxx/actions/runs/40177494173) on `127214395d1b643ef1bd027d5009d651b145ca63`

The CI test step ran 1,096 tests and failed only `test_cookie_requires_private_regular_file_and_expected_size`. The fixture stored `cookie` directly in the temporary directory root. On the Termux host that parent is owned by the test user, while on the GitHub runner its parent is shared `/tmp` with unsafe permissions. Production `_cookie()` correctly rejected that path because it is not a private Native `$HOME/.config/pulse/cookie` hierarchy.

The test now creates a private `.config/pulse/cookie` hierarchy before checking cookie mode, regular-file type, and expected 256-byte size. The focused `tests.test_pulse_lifecycle` suite passed 13 tests. The complete local `env -u LD_LIBRARY_PATH bash scripts/repo_test.sh` passed 1,096 tests in 113.005 seconds, including the CLI help contract. Corrected GitHub Actions run [40177830891](https://github.com/soobujmiah/ternuxx/actions/runs/40177830891) then passed all 1,096 tests in 38.677 seconds; its validation and generated-state synchronization jobs both succeeded.
