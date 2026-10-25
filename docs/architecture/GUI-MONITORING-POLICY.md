# GUI Activity monitoring policy

Linux Termux:X11/XFCE health and the Android Termux:X11 Activity are separate resources. Status, Doctor and management API reads never launch the Activity or inspect Android focus. Open the Android X11 app yourself to view the desktop.

## Shared policy

CLI, TUI, Web and GTK use `desktop.monitor.status` and `desktop.monitor.configure`. CLI policy controls are `tx gui monitor status|enable|disable|configure`; Web and guided TUI/GTK controls use the same policy. Saved policy does not install or start a worker.

Schema version 1 is stored privately at `$TERNUXX_STATE_DIR/gui-monitoring.json`. Updates validate ownership, mode, schema and interval; reject symlinks; serialize through a private lock directory; and use a same-directory temporary file, fsync and atomic replace. Policy files use mode 0600 and state directories mode 0700. Accepted interval units are seconds, minutes and hours, normalized to 30–86400 seconds.

Defaults: monitoring off, interval 300 seconds, focus checking off, Activity launch off. Linux-only monitoring makes no Android requests. Activity launch requires focus checking, healthy Linux GUI, an available X11 Activity package and verified background focus. Foreground, unavailable commands or ambiguous focus prevents launch. Restricted or varying Android dumpsys output is unknown, never assumed background.

## Install the fixed worker

Use Native Termux and the existing termux-services installation:

```sh
tx gui monitor service status
tx gui monitor service preview-install
tx gui monitor service install --yes --plan-id PLAN_ID
```

Apply the exact fresh plan ID after reviewing its impact. Registration accepts only the fixed GUI monitor or terminal broker definitions, validates source/manager identity and syntax, serializes installs, publishes a complete file before enabling execution, and waits for asynchronous Runit discovery. It refuses existing definitions and foreign targets. Rollback may stop/remove only its own published inode; a failed stop preserves the definition for recovery. It never adopts another registration because its hash matches.

The worker prefers the canonical checkout module and falls back to the installed canonical module only when the checkout module is unavailable. Registration delivers the saved policy; it does not enable monitoring, change Activity/focus flags, acquire a Wake Lock or edit Termux:Boot. No separate Web/TUI/GTK service-install action exists yet; those clients configure the common policy after Native CLI registration.

## Scheduler and status

One Runit worker holds `.gui-monitor-scheduler.lock` with flock. Policy reloads at most five seconds apart; enabled checks use the saved interval. Disabled policy performs no monitoring probes or log/policy writes.

- `running`: worker lock held and monitoring enabled.
- `running_idle`: worker lock held, monitoring off; shown as “Ready; monitoring is off”.
- `not_running`: monitoring enabled but no worker holds the lock.
- `disabled`: monitoring off and no active worker.
- `unknown`/`unsafe`: lock status could not be safely established.

Read-only status distinguishes Linux health, Android availability/focus, last result, freshness, next check, worker and error. It reports `activity_requests_performed=false` and `focus_probe_performed=false`. The catalog requests live status instead of hardcoding installation absence. Worker outcomes append private JSON lines under `log/gui-monitoring.log`.

## Qualification and current evidence

[Live deployment](../evidence/2026-10-22-monitor-live-deployment.json) verifies the installed run definition against source, the worker command against the canonical checkout, and running_idle with the workstation policy still off. Native desktop, SSH service, broker and the working Codex guest were preserved.

[Private replay](../evidence/2026-10-22-monitor-service-replay.json) uses an isolated Runit service root and private monitoring state. It verifies fresh registration, idle defaults, two Linux-only checks 30 seconds apart, unchanged workstation policy, and exact test-service exit/cleanup. Run it explicitly with `python3 tools/check_monitor_service.py --interval-check`. It does not install packages or restart the workstation.

Fixture tests cover persistence, bounds, symlinks, singleton state, launch gating, competing registrations, stale plans, failed-start rollback and Runit discovery delay. Real Android focus/Activity launch and a later cold boot remain unqualified. No Activity/focus opt-in was enabled during this work.
