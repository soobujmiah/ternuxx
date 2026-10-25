# Native `tx` entrypoint installation

**Date:** 2026-10-25 (Asia/Dhaka)  
**Evidence class:** direct Native Termux runtime  
**Repository:** `soobujmiah/ternuxx`, checkout `$HOME/ternuxx`

The source checkout existed, but `$PREFIX/bin/tx` was absent and `command -v tx` returned no path. The supported preview-first entrypoint installer identified only `$PREFIX/bin/tx` as its target and reported that the target was absent. Its source was `scripts/tx-installed`, a thin dispatcher into `$HOME/ternuxx/tx`. I applied that exact preview with `scripts/cli_entrypoint.py apply --yes --plan-id …`; it reported `status=installed` and a rollback snapshot available.

The installed shim SHA-256 is `a8735006203922cb7d7ab885e7fa1b85ca8608282de79d427d12a21a2511c401`, matching the source shim exactly. `command -v tx` resolves to `$PREFIX/bin/tx`; `tx help`, `tx doctor --json`, and `tx proot status --json` ran through the installed command. Doctor identified Native Termux 0.119.0-beta.3 on Android 16/aarch64 with 0 errors and 2 warnings. The fresh PRoot inventory remains `status=none` with no installed distributions.

`tx install preview --profile full-native` reports that the profile packages are already installed and makes no package changes. Before the empty-transaction estimator fix in the same worktree, that no-op preview emitted a stray package-estimator usage line; the fix now returns a zero-size estimate for an empty transaction. Its regression test passes, and the same live preview now completes without that diagnostic.

The installed entrypoint is intentionally a source-backed shim, not a copied standalone runtime: keep the checkout at `$HOME/ternuxx`, or set `TERNUXX_CHECKOUT` before using `tx`. This step installs the user-facing `tx` command, not a Debian guest. Guest creation remains a distinct fresh-plan operation. No password or other credential is recorded here.
