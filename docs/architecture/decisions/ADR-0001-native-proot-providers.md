# ADR-0001: Keep native Termux and existing Ternux PRoot as complementary providers
> **Scope update (2026-10-24):** ADR-0017 recorded a temporary Native-only direction, later reversed when the owner reauthorized Debian PRoot support. This record remains historical; current behavior is defined by source, [P11 phase status](../../PHASE-STATUS.md), and [restoration evidence](../../evidence/2026-10-24-p11-proot-source-restoration-audit.md).

- **Date:** 2026-10-17
- **Status:** accepted
- **Type:** cli-tool

## Context

The owner wants a phone-first workstation that uses Termux-native applications and Android-facing integrations together with the existing, separately stable Ternux Debian PRoot environment. Ternux already has an owner-configured desktop and GPU route. Native Termux uses a different userspace and the recorded Adreno 825 Vulkan test rejected the native driver. A one-layer design would either lose native host integration or risk reducing the established guest capabilities.

## Decision

Keep Native Termux independently usable without any PRoot workload. Treat Debian PRoot as an optional provider selected only for explicitly routed tasks. Model the Native host and guest workload as separate first-class providers; keep Ternuxx's host management and guest adapters additive and opt-in. Hybrid mode routes selected work through scoped arguments, files, and display/audio endpoints. One owner controls each display/session. Preserve Ternux's launcher, rootfs, GPU environment, and lifecycle; use a separately reviewed adapter that tracks only processes it starts.

## Alternatives considered

- **Native-only:** good access to Termux packages and host APIs, but does not preserve the established Debian Linux workload environment.
- **PRoot-only:** already provides the guest userland, but cannot replace native Termux host responsibilities and Android-facing APIs.
- **Rewrite or minimize the existing PRoot:** rejected because it could remove working, demonstrated capabilities and cross the project's independent ownership boundary.

## Rationale

Provider separation matches the two actual runtime contexts and allows each capability to be measured where it runs. A narrow adapter can connect workflows without claiming that native libraries, GPU drivers, permissions, or service state transfer across the boundary.

## Trade-offs

The project must manage two package/state namespaces, validate environment handoffs, and handle display/audio conflicts. Hybrid workflows require explicit provider selection and stronger Doctor/recovery evidence.

## Consequences

- Keep native and guest GPU/NPU/CPU evidence distinct.
- No blanket shared `$HOME`, `.ssh`, `.config`, or shared-storage mount.
- No use of Ternux's broad-cleanup launcher as a boot hook.
- Test one provider and one workload at a time; route to another provider only with the owner's explicit choice.

## Evidence

- Owner direction in the Ternuxx project brief.
- Ternuxx `docs/ARCHITECTURE.md`, `docs/HYBRID-INTEGRATION.md`, and `docs/PROOT-GPU.md`.
- Native independence and bounded PRoot scope are clarified by [ADR-0010](ADR-0010-native-termux-autonomy.md) and the superseding owner direction in [ADR-0006](ADR-0006-adapt-existing-ternux-provider.md).
- Read-only inspection of the existing Ternux source and launcher, as summarized in Ternuxx research; no live PRoot renderer rerun was made for this decision.
