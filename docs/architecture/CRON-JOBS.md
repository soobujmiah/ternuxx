# Ternuxx Cron Job Registry and schedule contract

**Status (2026-10-19):** typed persistent registry, deterministic preview, Native Termux named-timezone resolution, explicit lease-guarded scheduler runtime, and isolated typed-action dispatch are implemented. The runtime is not started by default. An opt-in official Termux:Boot entry manager is available, but its script is not installed on the device and reboot delivery is unverified. Production job policies beyond skip/one-attempt/skip-overlap, Android boot delivery, and scheduler-recovery delivery are not qualified.

## Public namespace

`tx mng` is the canonical public management namespace. `tx management` remains a deprecated compatibility alias and prints a warning; `mg` remains the short historical alias. Help and current examples use `mng`.

The Cron commands are:

```text
tx mng cron status
tx mng cron jobs list
tx mng cron jobs show JOB_ID
tx mng cron jobs validate JOB_ID
tx mng cron jobs next-runs JOB_ID [--count N]
tx mng cron jobs create --job-name NAME --job-action ACTION --schedule-type TYPE ...
tx mng cron jobs update JOB_ID [typed update options]
tx mng cron jobs enable JOB_ID
tx mng cron jobs disable JOB_ID
tx mng cron jobs remove JOB_ID
tx mng cron jobs apply --plan-id PLAN_ID --yes
tx mng cron executions list [--job-id JOB_ID] [--limit N]
```

Create/update/enable/disable/remove commands only save and show a private preview plan; they do not change the registry. Copy the exact plan ID and run `tx mng cron jobs apply --plan-id PLAN_ID --yes` to confirm. Plans expire after 15 minutes and are refused if the registry changes in the meantime. Creation defaults to disabled. Job actions are registry identifiers (`diagnostics.doctor`, `management.catalog.refresh`, `hermes.status`); they do not imply that an executor exists. No shell strings, arbitrary commands, secrets, or environment maps are accepted. Removal deletes only the job definition; execution-ledger history is retained and can remain empty.

## Persistence and schema

Job definitions use schema `schemas/cron-job-v1.schema.json`, version 1, and are stored in `$TERNUXX_STATE_DIR/cron/jobs.json`. The registry directory is private (0700), its JSON file is private (0600), and updates use a same-directory exclusive temporary file, `fsync`, and atomic replace. A directory lock serializes mutations. An existing unresolved lock, corrupt store, symlink, wrong owner, unsafe permissions, duplicate ID, unsupported schema, or invalid field fails closed. Status/list do not create the registry directory. There is no automatic migration from unsupported versions.

Each job has a stable random job ID, action/provider/source identity, versioned typed schedule, enabled state, timeout/output policy, timestamps, and a null last-execution summary. Schema-v1 retains policy fields for reading older records, but new or updated jobs currently require one attempt with zero delay, missed-run skip, skip_overlap concurrency, native-termux execution, no required-capability claims, and both boot/recovery flags false. Unsupported older records remain listable but are blocked before dispatch; no stored jobs were present at the 2026-10-20 remediation baseline, so no migration was applied.

## Schedules

The four schedule types are exactly `cron`, `interval`, `calendar`, and `one_time`.

- **cron:** five numeric fields `minute hour day-of-month month day-of-week`; lists, ranges and steps are accepted; names, macros and wrapping ranges are rejected. Day-of-month and day-of-week follow the common cron OR rule when both are restricted. Sunday accepts 0 or 7. The search is bounded to five years and minute precision.
- **interval:** positive seconds plus an explicit offset-bearing `anchor_at`. Slots are anchored to that timestamp; expired slots are skipped in previews. There is no production catch-up.
- **calendar daily:** 24-hour `HH:MM` plus an IANA timezone. A missing local wall time during a DST jump is skipped; for a repeated wall time, the first occurrence is selected. Native Termux resolves ordinary TZif files with Python `zoneinfo`, or reads the Android packed `tzdata` index through a bounded read-only adapter. The currently observed Android database is version `2025a`; `Asia/Dhaka` resolves from its actual zone entry, not a hard-coded offset. If neither source is available, named-zone validation fails closed with a diagnostic. UTC remains available without external timezone data.
- **calendar specific:** one future ISO-8601 datetime with an explicit UTC offset.
- **one_time:** one future ISO-8601 datetime with an explicit UTC offset. The future executor must mark completion so startup triggers cannot repeat it.

The engine takes an injectable clock in tests. Validation and preview never execute actions. `next-runs` returns the calculated UTC instants.



## Timezone preference

New installations default to `Asia/Dhaka`. `tx mng timezone status` reports the selected name, source, local time, offset, and detected timezone database. `tx mng timezone list` lists IANA names available from the current runtime. `tx mng timezone set IANA_NAME` validates and atomically persists a user choice as private `$TERNUXX_STATE_DIR/timezone.json` state (schema v1). The default is not written over an existing preference. A user-selected saved value takes precedence over the optional `TERNUXX_INSTALL_TIMEZONE` installation setting and the default. There is no IP geolocation request; suggestions are not implemented.

Cron-expression and daily schedules created through the CLI inherit the current preference when `--timezone` is omitted; TUI, Web, and GTK forms inherit the same preference when their optional timezone is blank. An explicit schedule timezone remains unchanged. Calendar/schedule previews always resolve named zones through the available database. Fixed intervals remain UTC-instant anchored and are unaffected by timezone changes. The CLI, TUI, Web, and GTK clients manage this preference through the shared `timezone.set` operation and `timezone.manage` capability. Web bootstrap requests that capability explicitly, and mutations use the authenticated, idempotent management transport. The UI changes only Ternuxx's private preference; it never changes Android system time.

The Android database is a read-only platform artifact under `/system/usr/share/zoneinfo/tzdata` (with an APEX fallback). Its version is surfaced at status time; normal schedule calculation makes no network request and installs no package. A database update is observed after a new CLI process starts; long-lived schedulers must refresh/restart their timezone cache before claiming updated data.

## Device boot and scheduler recovery

`enabled` means a definition may be considered by the explicitly started scheduler; it does not start the scheduler. Schema-v1 retains the two startup fields for compatibility, but new writes must keep both false until delivery is implemented.

A pure startup-trigger planner can model stable event IDs, disabled jobs, already-processed IDs, and device-boot precedence for legacy records. A completed one-time job is ineligible. This planner is a testable policy contract only: event claims are not persisted, no Android receiver is wired, and no trigger runs a job. New job validation rejects both startup flags until delivery exists.

## Execution ledger and bounded typed-action core

The private schema-v1 ledger is stored beside the registry at $TERNUXX_STATE_DIR/cron/executions.json (mode 0600 in a mode-0700 directory). It records stable event/execution IDs, job and scheduler-instance identity, trigger source, due/claim/start/completion times, state, attempt number, bounded redacted output summary and failure category. Updates use the same Cron directory lock as job mutations, an exclusive temporary file, fsync, and atomic replace. History reads are bounded (1–500 records; 5,000 retained records). Corruption, unsafe file identity, duplicate event/record identities, unsupported schema and unresolved locks fail closed.

cron_execution.claim_event atomically claims a due event before launch. A repeated (job_id,event_id) returns the original record. Disabled jobs, disallowed legacy boot/recovery triggers and overlapping events are recorded as skipped. New jobs accept only skip_overlap, one attempt with zero delay/fixed backoff, missed-run skip, native-termux execution, no capability claim, and no boot/recovery trigger. Unsupported legacy policy records remain readable but are refused before an event claim or launch. Only an enabled job, a registered action ID and an already-claimed event can reach execute_claimed.

The production action map is fixed to read-only management operations (diagnostics.doctor, management.catalog.refresh, hermes.status, and scheduler.self_test); there is no command-string or shell API. The runner uses a private process group, bounded pipe capture, timeout, and PID start-time/session-leader checks before signaling that group. Output is discarded or bounded and redacted according to the job policy. This code is not automatically invoked: no scheduler loop, service unit, API run operation, live job run, boot receiver, or scheduler-recovery delivery was enabled in this increment. Fixture-injected executors prove state transitions only; the production subprocess path was not invoked on the owner’s device.

A crash after claim but before launch leaves claimed; a crash after launch leaves running. Both remain unresolved and block overlapping claims. They are not automatically rerun or declared successful: manual reconciliation is required. Atomic claim prevents redispatch of the same event, but cannot guarantee exactly-once external side effects across a crash after action completion and before ledger commit. There is no cancellation operation yet. Only one attempt is supported; bounded retry is planned. The existing missed-run settings remain validated, but production catch-up/recovery semantics are not delivered. The one-time guard prevents rerunning a job after an execution reached succeeded, failed, timed-out or cancelled.

The execution ledger and summaries are private state; credentials are redacted from captured output. The watchdog remains separate and planned. Device boot delivery, scheduler recovery delivery, scheduler start/stop, cancellation, worker recovery, and production retry/queue behavior remain unavailable.

## API and client support

The shared management API provides typed Cron reads and cron.jobs.mutation.preview / cron.jobs.mutation.apply, plus read-only bounded execution history. Reads require diagnostics.read; preview and apply require cron.manage.

A create preview accepts {action:"create", name, action_id, schedule_type, schedule} with optional supported execution-policy fields. schedule_type is cron, interval, calendar, or one_time; the schedule object follows the registry schema. The service creates the canonical registry record, including its ID, ownership, timestamps, and safe defaults. Clients submit schedule fields, not generated metadata.

CLI, TUI, Web, and GTK use the shared preview/apply operations. Each supports create, update, remove, enabled-state changes, bounded history, and confirmed scheduler start/stop with a bounded poll interval. All four create forms support the four schedule types; calendar schedules support daily and specific modes. Every client reuses the saved plan ID and requires explicit confirmation. Service, bridge, and client-contract tests exercise these paths; live interactive acceptance remains open. No client claims that a resident scheduler is ready or running.

## PRoot guest-session integration

Cron currently runs as a Native Termux service. There is no PRoot guest-session scheduler integration or guest-targeted Cron action. Debian PRoot restoration does not change that boundary; a guest scheduler provider would need its own ownership model, lifecycle integration, authorization, and acceptance evidence before it can be supported.

## Hermes

Hermes remains an optional external provider with read-only `hermes --version` and `hermes cron status` inspection. Its task contents, history and configuration are not read or changed; no Hermes task ran. Its scheduler is disconnected from this registry. See [Hermes provider](HERMES-PROVIDER.md).


## Current implementation update - 2026-10-19

The scheduler core in lib/cron_scheduler.py uses a nonblocking OS file lease, a private atomically written scheduler instance record (PID plus process start identity), and a lease-guarded due-event poller. Stable event IDs derive from job ID and due instant normalized to UTC. lib/cron_daemon.py provides explicit start/stop with a detached Termux-compatible process and revalidates marker, command, PID start-time, lease and instance identity before stop.

The real bounded subprocess runner was exercised only through a new registered no-side-effect action, scheduler.self_test, in a temporary registry. Its operation reports diagnostic-only status and no side effects. This is fixture-state integration evidence, not a production schedule. The action map remains fixed and accepts no shell or user-supplied command.

Dispatch health is based on recent successful polls, separate from process liveness and lease ownership. CLI/API provide explicit scheduler start/stop, but no boot service or persistent production process was enabled. Automatic retry, queue-one, cancellation, catch-up delivery, device boot and scheduler recovery adapters are not implemented. Unresolved claimed/running records remain uncertain and are not automatically retried. A crash after an action side effect but before durable completion remains an uncertain boundary; duplicate event claims are suppressed but arbitrary external effects are not exactly-once.

No PRoot scheduler/session integration is implemented. Any historical design material remains background context and does not imply a supported guest scheduler target.


## Scheduler runtime increment (2026-10-19)

The source now includes an explicitly started Termux-compatible daemon. It
holds an advisory OS lease, records a private PID/start-time/instance identity,
polls at a bounded 1-to-60-second interval, resolves due times through the same
registry/timezone engine, claims stable event IDs before using the existing
typed action executor, and writes poll/dispatch health. It is not installed as
a boot service and is not started by status or UI requests. Use tx mng cron
start with an optional poll interval only when intentionally enabling the
configured registry; tx mng cron stop --yes requires the dedicated
cron.scheduler.manage scope through authenticated transports.

The production poller currently implements only missed_run_policy=skip,
max_attempts=1, and skip_overlap. Other retry, queue, recovery, cancellation
and boot-trigger delivery policies remain explicitly unavailable. A due event
is claimed before action dispatch and repeated scans reuse its claim. A crash
after an external side effect but before completion persistence can leave an
uncertain claim; it is not automatically replayed. This provides duplicate
claim suppression, not exactly-once external side effects. Device boot and
scheduler-recovery delivery remain unqualified; no boot hook is installed.


## Official Termux:Boot integration (opt-in)

Ternuxx uses the official Termux:Boot companion app and its `$HOME/.termux/boot/` convention. `tx mng boot cron status|validate` inspect integration state; `preview enable|disable` returns the exact target path, file operation, mode/hash, and plan ID; `enable|disable --yes --plan-id ID` applies only that reviewed plan. Shared writes require the narrow `boot.cron.manage` capability. CLI, TUI, GTK, and Web expose status/validation and preview-confirmed enable/disable; Web grants `boot.cron.manage` only when the user checks its optional login scope. Enable is refused unless `com.termux.boot` is positively reported installed. A denied/ambiguous PackageManager query remains `unknown`. No package is installed or app opened by Ternuxx. The owner must install Termux:Boot from a compatible source and launch it once manually if not already done.

The dedicated `20-ternuxx-cron` script starts only `tx mng cron start --yes`, through the supported CLI. It sets the native Termux environment, bounds startup to 20 seconds, uses a private append-only result log and an invocation lock, and relies on the Cron daemon's existing scheduler lease for duplicate-start prevention. Safe-test mode requires an isolated state directory containing the exact fixture marker; it cannot silently override production state. The manager refuses symlinks, unrecognized target contents, stale plan IDs, and replacement/removal of unrelated scripts.

Diagnostic states distinguish integration not configured versus script configured, confirmed companion installation versus unknown/not installed, last script outcome, current scheduler state, and actual device-boot delivery (`not_yet_verified`). A manual isolated script test proves start then `already_running` for one scheduler instance; it is not a reboot test. Device-boot delivery remains unqualified until the owner performs a reboot and confirms the script log and scheduler identity.
