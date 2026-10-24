# Native GUI session lifecycle

Native desktop lifecycle is managed in Native Termux. Debian PRoot GUI sessions are a separate optional provider with their own scoped lifecycle records and process identity; stopping one must not stop the Native desktop or an unverified owner session. Current commands and acceptance limits are in the [operations guide](../OPERATIONS.md#debian-proot-guest) and [P11 evidence](../evidence/2026-10-24-p11-proot-source-restoration-audit.md). The schema-v2 Native `session.json` described below applies only to Native desktop sessions.

## Shared operation path

`tx start|stop|restart|status` is the canonical native desktop lifecycle. `tx gui` verifies the recorded live Native session and opens the separate GTK management center on that session's display. If `DISPLAY` is unset, it derives the value from the verified session; if the shell has a conflicting display, launch fails closed rather than attaching to a different session. Explicit `tx gui start|stop|restart|status` remains a compatibility alias. The local management service routes `desktop.status`, `desktop.start`, `desktop.stop`, and `desktop.restart` through the same `bin/tx --json` command path. The TUI consumes the service contract. The Web runtime is read-only and does not expose these mutations. These clients do not have separate session-state rules.

## Evidence and states

`lib/desktop_session_state.py` classifies the persisted record against live evidence. A PID alone never establishes ownership or health. For each recorded process it checks `/proc` start ticks, command marker, process owner UID, and, for X11/XFCE children, the recorded process group and session. PID absence or a start-tick/command mismatch means the recorded process identity is absent; permission or inventory failures remain unknown. The display check rejects symlinked/foreign temporary and socket directories, requires the expected owned socket and lock, verifies the lock file by no-follow open and matching inode, requires a lock PID matching the recorded X11 PID, and requires a successful local socket connect before `running` is reported.

The lifecycle states exposed by the classifier are:

- `stopped`: no session record, or an explicitly stopped record with all recorded identities and display artifacts absent.
- `starting` / `stopping`: the record says the operation is in progress and at least one recorded process remains verifiable; a second start is refused.
- `running`: all three recorded process identities are live and the display endpoint is responsive.
- `failed`: an explicit failure or a running record whose verified process roles disagree, including a live session whose display is not ready.
- `stale`: the prior record is not `stopped`, every recorded process identity is absent, and no display artifact remains.
- `unknown`: evidence is insufficient or `/proc` cannot verify a recorded identity.
- `unsafe`: schema, ownership, permissions, process owner, or symlink checks fail.

`status` is read-only. `start` acquires the lifecycle lock before inspection. A `stale` record is rechecked under that lock and atomically changed to `stopped` only when every recorded process and display artifact remains absent. Startup then continues through the normal journal, supervisor, and readiness path. `starting`, `stopping`, `failed`, `unknown`, and `unsafe` records do not trigger duplicate startup or destructive recovery. Unknown or unsafe states preserve processes and files. Failed states require diagnosis before an explicitly supported recovery.

`stop` uses the same classifier. It refuses unknown or unsafe ownership and signals only exact recorded process identities. Stale display artifacts are never removed by status or generic display inspection. When a stale session record names a prior native display, `start` may reclaim that display's lock/socket pair only when the lock PID equals the record's exact X11 PID, that PID is absent, the socket refuses a connection, and both artifact identities remain unchanged during the check. Unknown, mismatched, live, or ambiguous artifacts are preserved. A private lifecycle lock serializes Ternuxx operations.

## Stable native display

Native Ternuxx defaults to display `:1`. Default startup fails closed when `:1` is occupied or ambiguous; it does not silently create another native desktop on `:2` or higher. An explicit `tx start --display N` remains available for an owner-selected alternate. After a stale Ternuxx `:1` record is safely reconciled, startup reuses `:1`; repeated start is idempotent, and stop signals only the recorded Ternuxx process identities while retaining state and logs.

## Health limits

A responsive X11 socket and live XFCE process establish session readiness, not Android window visibility. Termux:X11 Activity launch and focus polling are disabled by default. An explicit monitoring policy can request launch only after a scheduled focus check confirms the Activity is backgrounded; actual visibility remains a separate state. Audio remains externally owned. Termux `/proc` visibility is platform-limited; any unreadable identity is reported as unknown rather than treated as stopped.

## Current qualification

On 2026-10-19, the live schema-v2 record for display `:1` said `running` while its supervisor, X11, and XFCE identities were absent and no display socket or lock existed. Under owner-authorized validation, one session was started and status verified its processes and responsive socket. On 2026-10-20, a stale `:1` record had a dead recorded PID but its matching private socket and lock remained; those artifacts were preserved during initial diagnosis, and the session was temporarily started on explicit display `:2`. The owner then clarified that Native Ternuxx must remain on `:1`. The implementation now makes `:1` the fixed default and permits exact record-bound stale artifact recovery; the current live migration result is recorded in the current execution evidence. Android window visibility remains unknown. Fixture tests cover stale-running reconciliation, exact-PID recovery, mismatches, active sockets, malformed/symlinked records, display readiness, lock contention, repeated lifecycle requests, and management-service response routing. Full Native Termux suite results and separate boot findings are recorded in [the recovery evidence](../evidence/2026-10-19-gui-session-recovery.md) and the current [qualification execution evidence](../evidence/2026-10-20-workstation-qualification-execution.md).

This dated lifecycle record does not qualify cold boot, general GUI visibility, or listener socket ownership. Current project gates are listed in [phase status](../PHASE-STATUS.md).
