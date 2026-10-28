# PRoot X11 endpoint loss and stop recovery

**Observed:** 2026-10-28, Native Termux on Android
**Checkout:** `~/ternuxx`; `origin` is `https://github.com/soobujmiah/ternuxx.git`
**Scope:** Diagnose the owner-reported standalone PRoot `:0` GUI failure and repair Ternuxx's scoped stop path.

## Incident and diagnosis

The owner reported that after exiting Termux, the standalone PRoot GUI remained on screen, but opening an XFCE terminal and logging out did not work. `tx pgui stop` returned:

```text
desktop_orphan_stop: session is not the exact verified orphaned PRoot :0 desktop
Orphaned PRoot GUI identity could not be proved; no process was signaled.
```

The owner then ran `tx stop`, which reported stopping Ternuxx-owned desktop processes. Ternuxx has separate records and lifecycle commands: `tx pgui stop` manages PRoot `:0`/`:2`; `tx stop` manages Native `:1`.

Before this repair, the live PRoot record still said `running`. Ternuxx's inspector verified the recorded supervisor, X11 launcher, and desktop process identities as live, but reported the `:0` display endpoint as absent. The combined status was therefore `failed`. The PRoot stop handler sent every `failed` state to orphan recovery. That helper deliberately accepts only an absent supervisor and a ready display, so it rejected this live-supervisor/missing-endpoint condition. The record therefore had no supported cleanup route even though its supervisor remained available.

The observation establishes that the X11 endpoint was unavailable while the recorded processes remained. The exact Android lifecycle event that removed the endpoint was not logged; this does not prove that closing Termux itself always kills or preserves the Termux:X11 server. Termux:X11 distinguishes its Android Activity from the Termux background X-server process in its [upstream README](https://github.com/termux/termux-x11#closing-android-activity-running-in-foreground-not-x-server). Endpoint availability and process liveness must be reported separately.

## Change

When `tx pgui stop` sees a failed state and the recorded supervisor is still live according to Ternuxx's process inspection, it now verifies the supervisor PID, start ticks, command marker, and UID, then sends `TERM` to that supervisor. The supervisor uses its existing exact process-group checks to stop only its recorded PRoot desktop and X11 groups. If the supervisor is absent, the strict orphan recovery path is unchanged. `tx stop` remains the Native `:1` lifecycle command.

The status output now includes the display endpoint state for non-running sessions. The operations guide describes the distinction between the two stop commands and the failed-endpoint recovery.

## Local implementation and evidence

`$PREFIX/bin/tx` is a thin launcher that executes `~/ternuxx/tx`, so the checkout change is active locally without copying a second implementation.

- `bash -n scripts/proot-gui0.sh` passed.
- Patched `tx pgui stop` reported a verified supervisor and stopped the managed PRoot session on `:0`.
- `tx pgui status` reported `state=stopped`; the shared inspector reported supervisor, X11, and desktop processes absent and session record status `stopped`.
- Native `tx status` reported `:1` stopped before and after this PRoot operation. The PRoot stop left Native state and Native audio untouched.
- The automated test suite was not run.
- Background persistence check: `sh -c 'tx start'` exited; afterward `tx status` reported Native `:1` supervisor, Termux:X11, XFCE, and display endpoint ready. `tx stop` then stopped that session cleanly. `sh -c 'tx pgui start --mode standalone'` exited; afterward `tx pgui status` reported PRoot `:0` ready with all expected XFCE processes and a ready endpoint. `tx pgui stop` then stopped that session cleanly. Final status reported both desktops stopped.
- This verifies that each managed GUI survives its launching shell exiting, then stops through its matching Ternuxx command. Android force-stop/OS process eviction and visual foreground presentation were not tested. The earlier endpoint-loss trigger remains unknown; this repair does not restore a missing endpoint automatically.
