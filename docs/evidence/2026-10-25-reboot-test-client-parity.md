# Detailed reboot qualification client parity

**Date:** 2026-10-25  
**Scope:** source and automated-test verification for the detailed reboot qualification workflow.

## Result

The detailed reboot qualification workflow is available through the shared management service in CLI, TUI, Web, and GTK. TUI, Web, and GTK expose preview followed by an exact-plan confirmation before writing. Web uses the dedicated `continuity.reboot-test.manage` capability. The generated baseline records Native Termux version and repository branch, commit, and worktree counts where Git can report them. SSH, Termux:Boot, and Wake Lock facts that this collector cannot observe remain explicitly unknown; it does not claim a reboot occurred or that the system is ready.

The plan binds the preview details, including the baseline. Apply regenerates the default baseline and requires the exact plan ID, so changed repository state invalidates the stale preview. Preparation writes a private `NOT_READY` record only after confirmation. Verification likewise requires a fresh preview and confirmation and records evidence; it does not reboot Android or resume work.

## Verification

- Focused backend and client suite: **266 passed, 220 subtests passed**.
- Full repository suite: **1,076 passed, 402 subtests passed**.
- GTK source syntax compilation with `clang -O2 -Wall -Wextra -fsyntax-only`: passed.
- Native CLI JSON smoke preview: returned success, `read_only: true`, and `NOT_READY`; SSH and Termux:Boot remained unknown, and no private record was created.
- `python3 -m tools.repo_knowledge verify`: zero findings.
- `git diff --check`: passed.

No reboot, reboot-test record write, or GTK/Web rendered-UI acceptance test was performed. Rendered client acceptance remains open.
