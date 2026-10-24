# Live runtime and documentation reconciliation

**Observed:** 2026-10-24, Native Termux session. Live device checks were read-only; no live desktop, guest PRoot process, or service was started, stopped, or signalled.

## Runtime evidence

- `getprop` reported Android 16 and device model `25053RT47C`; the shell reports Termux `0.119.0-beta.3` on aarch64.
- `tx status --json` reported the Native desktop `running` on `:1`, with supervisor, X11, and XFCE live. `gui_visible` was `unknown`.
- `tx pgui status` reported standalone Debian GUI `stopped` on `:0` and nested display `:2` absent.
- `tx proot status --json` reported the Debian distribution installed and did not enter the guest. All records from `tx proot sessions list --json` were `stopped`.
- The PRoot inventory simultaneously reported five host `proot` PIDs with `ownership=unverified`. A read-only `/proc` check found each in zombie state with parent PID `15918`; `ps` identified that parent as a long-running `python3 .../lib/terminal_ui.py` process. The zombies are not executing guest workloads. They were left untouched because their owner could not be established from the session records.
- `tx terminal service status --json` reported the fixed terminal broker installed and running with source identity match.
- `tx ai status --json` reported the pinned CPU model and Termux llama.cpp runtime available. `tx ai devices --json` reported Vulkan device `Adreno (TM) 825`. `tx ai npu status --json` reported experimental `HTP0` available on `SM8735`, release `b11849`. These are availability observations, not new inference workload tests.
- At the read-only sensor sample, the highest labeled CPU thermal-zone value was 50.9 °C and Termux battery status reported 40.1 °C, 65% charge, unplugged. No inference was run during this audit.

## Documentation correction

The prior `CURRENT_STATE.md` claimed Native `:1` was stopped while Debian GUI `:0` was running, and described P11 as active with P12 planned. The live status contradicted those statements: Native `:1` was running, Debian `:0` was stopped, P11 was complete, and P12 was in progress in the phase ledger. `CURRENT_STATE.md` and `docs/testing/KNOWN-LIMITATIONS.md` were rewritten to separate live state, active phase, and product qualification limits.

The zombie observation exposed a client-lifecycle bug: isolated probes were direct children of the caller, which may be a long-running TUI or Web process. `lib/proot_sessions.py` now uses a short-lived intermediate process to reparent the bounded probe, and a regression test confirms the workload PID is not a child of the caller before stopping it with its exact preview. The focused PRoot session suite passed 45 tests. The latest host-like `env -u TERMUX_VERSION -u PREFIX bash scripts/repo_test.sh` run passed 1,001 Python tests plus the CLI help/preview contract. The original five zombie entries are unchanged under the still-running TUI; no live runtime cleanup was attempted.

## Evidence commands

```text
tx status --json
tx pgui status
tx proot status --json
tx proot sessions list --json
tx terminal service status --json
ps -p 15918 -o pid,ppid,etime,tty,stat,args
getprop ro.build.version.release
getprop ro.product.model
tx ai status --json
tx ai devices --json
tx ai npu status --json
termux-battery-status
```
