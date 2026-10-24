# ADR-0012: Native-owned shared dependencies and services
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** Owner requirement accepted; implementation partial (current status reviewed 2026-10-24)
- **Type:** provider-and-service-ownership

## Context

The owner wants Termux-native components installed and ready under Native
Termux's boot and service policy, with the existing Debian PRoot able to use
those capabilities when needed. This can reduce duplicate daemons and keep
host integrations available independently of PRoot. It does not make Termux
packages or libraries interchangeable with Debian packages: Termux targets
Android/Bionic and Debian targets Linux/glibc, with separate package databases,
ABI assumptions, filesystem roots, and process environments.

The current optional-software design already separates Native Termux and
PRoot package plans. The current service architecture makes Native Termux the
host owner and PRoot an independent provider. This decision defines when a
capability should be installed once on the host and consumed by the guest.

## Decision

1. Prefer Native Termux for host-owned capabilities that need to survive
   independently of PRoot or integrate with Android: boot orchestration,
   native SSH, Termux:API, Termux:X11, host audio services, and any future
   native gateway/service whose lifecycle is explicitly enabled by the owner.
2. Keep execution dependencies inside the provider that executes them. A
   Debian application needing a glibc library, Debian package, or Linux-only
   tool gets that dependency in its selected PRoot guest. Installing a package
   with `pkg` does not satisfy Debian `apt` dependencies.
3. Let PRoot consume a native-owned service only through a documented and
   verified boundary: a local protocol/API, a deliberately shared socket, or a
   narrowly scoped file/data contract. Define endpoint, permissions, readiness,
   timeout, failure behavior, and lifecycle owner. Do not expose a host service
   to LAN by default.
4. Do not copy, symlink, or inject Termux/Bionic shared libraries or binaries
   into Debian to satisfy guest dependencies. Any cross-ABI bridge requires a
   separately researched and tested adapter with an explicit compatibility
   contract.
5. Native boot starts only selected, lightweight host services and records
   readiness. It does not imply that every installed package, desktop, model,
   agent, or heavy workload starts at boot. PRoot may start later and use an
   available native service; native recovery must not wait for PRoot.
6. Installation plans remain provider-scoped and preview exact package changes.
   A dependency declared for a PRoot workload may be satisfied by a native
   service only when the catalog identifies it as a service/API dependency,
   verifies the host capability, and does not silently install into either
   provider. Otherwise install the dependency in the selected execution
   provider.
7. GUI, CLI, and Web management use the shared service registry and planner.
   The registry records the owner provider, consumer providers, readiness
   check, endpoint/transport class (without secrets), startup policy, and
   fallback behavior.

## Consequences

- Native Termux is the place for Android-facing and shared host services.
- PRoot remains independently useful and keeps its own Linux runtime
  dependencies; it is not made smaller by assumption or destructive cleanup.
- Sharing a service can avoid duplicate package/service instances, but requires
  explicit boundary and compatibility testing. A native package being present
  is not proof that PRoot can use it.
- Service readiness and package installation are separate states. Boot policy
  is opt-in per service, and services-only startup must not launch a GUI or
  heavy workload implicitly.

## Acceptance criteria

1. The catalog distinguishes provider-local packages from cross-provider
   service/API requirements.
2. A PRoot workload cannot resolve a Termux package ID as a Debian package or
   treat a Bionic library as a glibc dependency.
3. Shared-service plans name the Native owner, PRoot consumer, transport,
   permission boundary, health check, and fallback.
4. Native boot readiness is testable with PRoot stopped and starts only the
   explicitly selected services.
5. PRoot reports a shared native service as unavailable without stopping or
   impairing native services.
6. No existing PRoot package, rootfs, launcher, graphics, or workload is
   changed implicitly.

## Current implementation status

This ADR records the ownership boundary; it does not itself qualify a runtime. Implemented slices include Native-managed SSH, the terminal broker, the idle GUI-monitor service, preview-first boot/service helpers, and Native PulseAudio consumed through the documented authenticated Debian handoff. Current per-client coverage and remaining gaps are in the [capability matrix](../CAPABILITY-MATRIX.md). Android cold-boot delivery, broader shared-service client lifecycle parity, and workload-level graphics/audio qualification remain incomplete; see [monitor replay evidence](../../evidence/2026-10-22-monitor-service-registration.md) and [P4 phase state](../../../project/phase-state.json).
