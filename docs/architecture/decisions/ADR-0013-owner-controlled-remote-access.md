# ADR-0013: Optional owner-controlled access from outside home
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-18
- **Status:** Owner-approved product requirement; local shared-management/CLI preview integrated; transport adapter and device/network enablement pending
- **Type:** remote-access-and-security-boundary

## Context

The owner wants to use the mobile workstation while away from home, for regular
interactive work and authorized agent workflows. Ternuxx has Native Termux as
the host provider and an independent existing Debian PRoot provider. The
providers share a device/network context but have separate lifecycle and
ownership boundaries. PRoot is not a network or security sandbox.

The current managed Native Termux SSH candidate uses loopback port 8023. It
was exercised from the same-device PRoot route; this does not establish
reachability from another device or an off-home network. A port number by
itself does not provide authentication, authorization, or network isolation.

## Decision

1. Treat off-home access as an optional, user-selectable product mode. It is
   disabled by default. The owner's request approves the product option and
   architecture work; it does not authorize enabling a listener, changing a
   router, installing a VPN/tunnel client, or exposing this phone to a network.
2. Design a vendor-neutral **private access transport** adapter. The initial
   supported route should use an owner-selected authenticated VPN overlay or
   outbound tunnel that can reach the phone without requiring a public inbound
   port-forward. Do not make direct Internet exposure or router port-forwarding
   the default. No specific third-party provider is selected by this ADR.
3. Keep Native Termux management services loopback-only. A separately reviewed
   transport adapter may relay approved requests to the local shared management
   service. It must not relax the service's bind address through a simple
   configuration toggle. If the selected transport cannot preserve a narrow,
   verifiable path to the service, remote mode remains unavailable.
4. Keep native and PRoot targets explicit. A remote operation selects
   `native`, `proot`, or a documented `hybrid` workflow; provider fallback is
   never silent. Native-to-PRoot execution uses the local ownership-aware
   `proot-distro` adapter with bounded `argv`, workdir, environment, timeout,
   and structured result. It does not need SSH between two providers on the
   same device. PRoot-to-native operations use a named, authorized management
   request; the 8023 SSH endpoint is not itself a full cross-provider API.
5. Separate remote transport identity, SSH client authentication, the Termux
   login principal, and Ternuxx operation authorization. Remote agent clients
   receive only named capabilities. A remote SSH shell, if later offered, is a
   separate explicit capability and does not grant management API authority.
6. Let the owner select the access provider, allowed client devices, target
   provider, and operation scope. Validate port conflicts and actual bind/
   route behavior before enabling anything. Changing the SSH port alone never
   enables remote access or makes an endpoint safer.
7. Keep local CLI, native SSH, and existing PRoot workflows usable when the
   remote transport is off, disconnected, or unavailable. Do not auto-launch
   PRoot desktops, AI models, or agents at boot for remote reachability. A
   PRoot-dependent task waits for a fresh guest session and explicit owner
   continuation after reboot.
8. Store no VPN credentials, tunnel tokens, SSH secrets, or private keys in
   Git, ordinary logs, screenshots, exported evidence, or agent prompts. Provide
   an owner-controlled disable/revoke path that leaves local use intact.

## Intended request path

```text
Off-home client
    → owner-selected private VPN/tunnel
    → Native Termux remote-access adapter
    → shared Ternuxx authorization and operation services
    → selected Native Termux or Debian PRoot provider adapter
    → bounded result, status, and selected output returned to the client
```

The remote adapter terminates or validates the private transport and forwards
only typed requests. It is not a generic shell proxy, internet-facing dashboard,
or unrestricted bridge into Termux home/PRoot rootfs. File transfer uses the
selected Ternuxx workspace or a separately selected path, not blanket mounts.

## Security and implementation gates

Before remote mode is implemented or enabled, the project must define and
validate:

- per-device/user authentication, authorization, key rotation/revocation, and
  recovery after a lost phone or client;
- the exact transport, endpoint, bind behavior, firewall/network assumptions,
  relay/data costs, and Android background/battery behavior;
- default-deny provider and operation scopes, rate/time limits, audit redaction,
  and a tested disable/offline path;
- rejection of unauthenticated clients and requests that arrive outside the
  selected private path; no fallback to public cloud or direct WAN exposure;
- provider-separated ownership, no host/guest key sharing, no whole-home/rootfs
  mount, and no unbounded remote command execution;
- CI contract tests plus owner-operated device tests. A same-device loopback
  test or CI pass cannot qualify off-home access; actual remote testing must use
  an explicitly selected client/network and be reported separately.

The current product architecture remains local-first. A remote mode is a
separately enabled transport for the same bounded services, not a new authority
source and not a prerequisite for local operation.

## Offline policy contract status — 2026-10-18

`lib/remote_access_policy.py` validates a secret-free desired policy and builds
a non-applying preview. Its default is `disabled`; a private-transport policy
reports `unavailable` until a reviewed transport adapter exists. It does not
read or persist configuration, resolve credentials, inspect network state, or
change services. The schema is version 2 because credential references use a dedicated
`credential_ref_...` ID shape. The shared management API allowlists
`remote.access.preview`, and the CLI accepts an explicitly piped policy only
with `--policy-stdin`. The response has a separate version-1 schema. These paths
remain read-only: they do not resolve references, persist configuration, probe a
network, or start services. No transport adapter consumes this policy for
connection setup, so this source integration does not qualify a provider or
enable off-home access. Verification is recorded in
`docs/evidence/2026-10-18-p3-private-remote-policy-tests.json`.

## Android Tailscale candidate note — 2026-10-18

A documentary review records Tailscale as an unselected candidate: official docs describe policy-permitted incoming connections to services on Android devices, but the Android app has no supported CLI, so the CLI-based `tailscale serve` localhost relay cannot be assumed. Directly reusing the current wildcard/password SSH listener is not accepted as the adapter design. No tailnet identity, connection, relay, or service path has been tested or enabled. See [P3 Tailscale candidate review](../../evidence/2026-10-18-p3-offhome-tailscale-candidate-review.md).
