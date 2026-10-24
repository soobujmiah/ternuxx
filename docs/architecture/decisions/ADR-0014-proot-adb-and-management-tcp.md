# ADR-0014: Separate PRoot ADB from Ternuxx management TCP
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-18
- **Status:** Proposed architecture; this ADR enabled no listener; an existing ADB server was observed, with bind ownership still unresolved
- **Type:** provider-boundary-and-network-service

## Context

The owner reports that ADB is available inside the existing Debian PRoot and
not in native Termux. Native Termux remains the authoritative Ternuxx control
plane. The owner also wants a TCP transport for professional Ternuxx
management use. These are two different services with different protocol,
identity, operation scope, and lifecycle. PRoot shares the Android device's
network namespace and is not a security sandbox.

The current Ternuxx management layer has an in-process typed dispatcher, an
authenticated HTTP request adapter, a bounded loopback server, and a foreground
runtime. Authenticated browser/Web clients use that shared service for a scoped
set of operations; see the current [Management API contract](../MANAGEMENT-API.md).
The HTTP runtime is not automatically provisioned as a persistent Runit or
Termux:Boot service, and no qualified private remote transport consumes the
remote policy. `remote.access.preview` remains a read-only policy preview; the
remote-access contract is in ADR-0013. The installed/runtime ADB placement and
Shizuku startup arrangement were owner-reported and then documented in the
dated ADT audit; current runtime identity and behavior remain unverified.

ADB has separate client, server, and device-daemon roles. The ADB server's
local client port (normally TCP 5037) is not the Android device's `adbd`
Wireless Debugging connect port; Android documents that the server listens on
local TCP 5037, while Wireless Debugging pairing/connect is a separate device
connection. Therefore, adding or supervising a PRoot ADB server can centralize
ADB clients but does not itself keep Android Wireless Debugging enabled,
preserve its pairing/port across reboot, or start Shizuku. Shizuku's upstream
guide says its ADB-based start must be repeated after reboot due to system
limitations. The custom fork may change the startup workflow, but that behavior
must be verified against its exact build and device evidence before relying on
it.

The owner-provided [ADT operational dependency audit](https://github.com/soobujmiah/adt/blob/abece9e714a3bcb24d4a8dcc9f001feb421c1411/docs/ON_DEVICE_ADB_SHIZUKU_OPERATIONAL_DEPENDENCY.md)
already contains the detailed custom-fork analysis. Its dated 2026-09-13
topology distinguishes the PRoot ADB client relay (`adb -L tcp:5037`, loopback)
from the Android-side `:5555` endpoint and `shizuku_server` bridge. It reports
that the bridge and Shizuku boot bootstrap are required for that workflow after
cold boot, although the TCP port property can remain during a session after
Shizuku is stopped. The relay's own startup was manual in that audit. So a
local 5037 server does not reduce the Shizuku dependency in this specific
workflow; a separately paired Android Wireless Debugging connection can serve
as another ADB transport, but Shizuku-backed privileged APIs still require a
working Shizuku service. Ternuxx reuses that analysis instead of reproducing
its source/forensic investigation; current device observations remain in the
separate evidence record below.

## Current device observation — 2026-10-18 06:56 UTC

A read-only native SSH session found no native Termux `adb` executable in PATH.
It did observe an `adb`-named process running through the Termux PRoot loader,
and a loopback-only ADB protocol `host:version` request to `127.0.0.1:5037`
returned protocol version `0x0029`. This verifies that an ADB server answered
on local port 5037 at that time. The process command line indicated a TCP
listener on 5037, but its host/bind scope could not be classified from the
available evidence. A read-only command lookup inside the default
`proot-distro` Debian login did not find `adb`; this does not identify or
disprove the separate active Ternux PRoot process root. The exact executable,
guest identity, listener ownership/bind scope, Wireless Debugging device
endpoint, connected-device authorization, custom Shizuku fork identity, and
watchdog behavior remain unverified. No ADB client command, device-list
request, pairing, setting change, or service lifecycle action was performed.
See [ADB live recheck](../../evidence/2026-10-18-p3-adb-live-recheck-0656.json).

## Decision

1. Track the **PRoot ADB service** and the **Ternuxx management TCP API** as
   separate capabilities, operation IDs, configuration, logs, health checks,
   authorization, and lifecycle owners. Neither service starts, stops, or
   grants authority to the other.
2. The PRoot ADB adapter targets only the explicitly selected Ternux-managed
   Debian guest and its ADB client/server binaries. It must report binary
   presence/version separately from server readiness, connected device state,
   and authorization. Native Termux must not acquire an implicit ADB package
   dependency. Device access unavailable from PRoot remains an explicit
   capability limitation; never silently fall back to a host `adb`.
3. If a PRoot ADB server is enabled, default to `127.0.0.1:5037`, with no
   wildcard bind, LAN exposure, or boot auto-start. Because PRoot shares the
   host network namespace, port conflict checks are device-wide. Enabling,
   restarting, or exposing the ADB endpoint requires its own preview and
   confirmation. TCP reachability is not treated as client authentication or
   device authorization. Remote ADB requires a separately reviewed secure
   transport, explicit client scope, and revocation path; it is off by default.
4. The Ternuxx management TCP API is a separate adapter over the existing
   typed shared management services, never a shell proxy or direct ADB bridge.
   Its foreground runtime is fixed to loopback and is explicitly invoked; it
   is not automatically provisioned as a persistent service or boot profile.
   Authenticated Web clients are integrated with scoped grants, but target-device
   lifecycle and private-transport qualification remain gates. Off-home access
   follows ADR-0013 through an owner-selected private transport. No public bind,
   router port-forward, wildcard CORS, or generic command route is introduced.
5. Professional-service requirements for the management endpoint include:
   versioned typed routes; explicit target provider; operation-scoped
   authentication and authorization; default-deny scopes; loopback bind and
   private-transport path verification; origin/Host and CSRF protections for
   browser clients; bounded request/frame sizes, concurrency, rate, and
   execution time; idempotency keys; durable operation IDs and sanitized
   audit events; health/readiness distinct from process-running state;
   graceful shutdown and recovery; key rotation/revocation; offline behavior;
   compatibility negotiation; observable but secret-redacted diagnostics;
   and a tested disable/revoke procedure. SSH client authentication alone
   does not authorize API operations.
6. Keep native and guest identities, keys, configuration, logs, package state,
   and service leases separate. Do not copy credentials or host keys between
   providers. Agent access is limited to named capabilities; no arbitrary
   `adb shell`, guest shell, filesystem bridge, or command execution is
   exposed through the management API.

## Delivery gates

### P3: Ternuxx management TCP adapter

- Current source implements the typed API, one-use session bootstrap, exact
  operation scopes, CSRF, request limits, audit/idempotency, and a bounded
  loopback listener. Persistent service/boot ownership, restart-safe bootstrap
  provisioning, operational recovery, and private remote transport remain open
  before this endpoint can be treated as a production managed service.
- An API-v1 operation-to-capability map now covers the full application
  service allowlist and has parity tests. It is policy data only; a transport
  must authenticate the session and enforce its scope before dispatch. The
  optional source listener is not automatically started and has no service or
  remote-access integration.
- `lib/management_http_adapter.py` wires the request guard, one-use session
  bootstrap, exact operation scopes, CSRF, revoke, durable idempotency, and
  typed local dispatch. Mutation routing is disabled by default and requires
  explicit opt-in plus the private durable request store. The adapter itself
  opens no socket.
- An in-memory session authority provides one-use bootstrap exchange,
  explicit scope narrowing, idle/absolute expiry, mutation CSRF proof, and
  revoke operations. It stores token digests and is wired to the in-process
  adapter. Session authority resets on process restart; secure bootstrap-secret
  provisioning and service lifecycle integration remain open.
- A transport-independent request policy checks exact loopback Host/Origin,
  method/content type, body size, and request rate. It creates no socket;
  the separate HTTP adapter adds authorization, CSRF, audit/idempotency, and
  response security headers.
- `lib/management_http_server.py` now provides an explicitly started
  `127.0.0.1` listener with a bounded worker pool, bounded request headers/body,
  total request deadline, overload rejection, security headers, and graceful
  handler drain. Deadline expiry closes the client connection but does not cancel
  work already dispatched; durable idempotency prevents unsafe automatic replay. It has no boot/service integration; operation execution
  deadlines still belong to typed services, and target-device loopback
  qualification remains open.
- `lib/management_http_runtime.py` is now exposed as
  `ternuxx management http serve`. It runs in the foreground, grants only
  reviewed read-only scopes, and displays a new one-use bootstrap secret only
  on an interactive terminal. It writes no bootstrap secret and starts no
  service automatically; boot/service integration, durable/restart-safe
  bootstrap provisioning, and target-device lifecycle qualification remain
  open. The shared authenticated Web client is described in the current
  Management API contract.
- The loopback HTTP contract separates `GET /health` liveness from
  `GET /ready` listener readiness. The latter is tied to the owned serving
  thread and reports 503 when its readiness probe is false; during drain the
  listener rejects new connections. It does not claim Android GUI, guest, SSH,
  or workload readiness.
- Add fake-adapter contract tests for bind policy, invalid origin/CSRF,
  unauthenticated rejection, scope denial, rate/size/time limits, idempotent
  mutations, secret redaction, disconnect/recovery, and shutdown.
- Validate loopback-only behavior on-device, then qualify the selected private
  remote transport on an explicitly selected client/network. CI and same-device
  tests do not prove off-home reachability or security.

### P4/P8: PRoot ADB capability

- First perform read-only inventory inside the selected PRoot: ADB client and
  server versions, effective configuration, listener owner/bind, device list,
  and available authorization state. Distinguish local client-to-server port
  5037 from the Android `adbd` Wireless Debugging endpoint. Do not start or
  stop a process during discovery.
- Inspect the exact custom Shizuku fork/build and watchdog contract separately:
  boot receiver behavior, Wireless Debugging enable/re-enable behavior,
  pairing identity, endpoint discovery, retry bounds, and user-visible failure
  state. Do not infer these from package presence or a watchdog label.
- Define the intended workflow and prove the ADB endpoint can access only the
  intended device/transport. PRoot device-node presence alone is not proof.
- Implement provider-owned preview/apply/status/stop with exact process
  identity, port conflict detection, loopback default, no automatic boot start,
  and no effect on native Termux or the existing Ternux desktop/rootfs.
- Test absence, stale PID, occupied port, unauthorized client, disconnected
  device, guest unavailable, repeated start/stop, timeout, and recovery cases.

Neither track is complete from documentation alone. Do not claim either
service as implemented until its device evidence and contract tests pass.

## Consequences

- The management TCP API can be delivered without installing or enabling ADB.
- PRoot ADB remains optional and cannot make native boot, native management,
  or off-home access depend on an active guest.
- A local PRoot ADB server on 5037 may reduce the need for multiple ADB client
  processes, but it does not itself enable the Android device transport or
  replace Shizuku-backed APIs. ADT's 2026-09-13 device audit records a
  Shizuku-bootstrapped path and a standard Wireless Debugging alternative that
  requires manual pairing after reboot; neither has been qualified in the
  current Ternuxx runtime. Keep the two TCP services and their lifecycle,
  authorization, and ports separate.
- Port 5037 is reserved only while an explicitly enabled PRoot-owned ADB server
  is running; conflicts with any other local process must fail closed.
- The owner-selected remote transport/client and intended ADB device workflow
  remain decisions for their respective implementation gates.

## Related decisions

- [ADR-0005: capabilities and permissions](ADR-0005-capability-permission-and-task-model.md)
- [ADR-0013: owner-controlled remote access](ADR-0013-owner-controlled-remote-access.md)
- [Management API](../MANAGEMENT-API.md)
- [Native and PRoot integration](../../HYBRID-INTEGRATION.md)
- [Android Debug Bridge architecture and port 5037](https://developer.android.com/tools/adb)
- [Shizuku setup guide](https://shizuku.rikka.app/guide/setup/)
- [ADT custom Shizuku operational dependency audit](https://github.com/soobujmiah/adt/blob/abece9e714a3bcb24d4a8dcc9f001feb421c1411/docs/ON_DEVICE_ADB_SHIZUKU_OPERATIONAL_DEPENDENCY.md)
- [ADB live recheck](../../evidence/2026-10-18-p3-adb-live-recheck-0656.json)
