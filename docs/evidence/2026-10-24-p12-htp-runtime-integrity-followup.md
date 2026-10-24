# P12 HTP runtime integrity follow-up — 2026-10-24

Phase: `P12`
Gate: PASS for the runtime-integrity correction; P12 remains in progress.

## Finding

The pinned Snapdragon runtime installer verified selected archive members while extracting and wrote their hashes into a private manifest. Later status and inference validation compared only file type, owner, mode, and size; a changed file with the same size could therefore pass the manifest check. The existing test explicitly used a placeholder digest, so it did not catch this case.

## Correction and verification

`lib/npu_inference.py::_runtime_valid` now validates each required manifest entry, opens each selected file with `O_NOFOLLOW`, checks the opened descriptor's type, owner, mode, and size, and streams SHA-256 before treating the runtime as valid. The exact executable, three required libraries, and license are checked. The regression test changes a runtime library to different bytes of the same size and confirms validation fails; it also confirms a missing file fails.

## Evidence

Focused verification passed:

- `python3 -m unittest discover -s tests -p 'test_npu_inference.py' -v` — 10 passed.
- `python3 -m unittest discover -s tests -p 'test_management_service.py' -q` — 51 passed.
- `python3 -m unittest discover -s tests -p 'test_management_desktop_bridge.py' -q` — 53 passed.
- Python compilation and feature-matrix YAML parsing passed.
- After the source/test change, `env -u LD_LIBRARY_PATH bash scripts/repo_test.sh` passed 1,001 Python tests and the CLI help/preview contract in 106.312 seconds.

After the integrity change, live Native `tx ai npu status --json` still reported SM8735, HTP0, release `b11849`, and `silent_fallback=false`. A bounded `tx ai run --backend npu --max-tokens 8` with prompt `2 + 2? Reply with one digit.` exited 0, returned `2 + 2 = 4.`, reported 29/29 layers offloaded and a 319.96 MiB HTP model buffer, and took 4.349 seconds. No inference process remained afterward.

After adding feature-matrix evidence-reference validation, the latest full Native Termux repository run passed 1,002 Python tests and the CLI help/preview contract in 118.012 seconds.

This is a same-device short smoke after runtime-integrity verification. No sustained benchmark or thermal/memory claim is made; the device remained on its normal thermal controls. P12 remains open for broader model/operator coverage, sustained stability, and the other qualification gates.
