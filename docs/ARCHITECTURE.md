# Ternuxx architecture

Ternuxx is an Android workstation manager with Native Termux as its host and control plane and optional Ternuxx-managed PRoot workload providers. Debian Trixie and Ubuntu Noble currently have pinned profiles; additional distro families require their own package-manager, base-image, graphics/audio, desktop, lifecycle, and recovery adapters. Its public command is `tx`; the installed shim dispatches into the checkout. Product state lives under `$TERNUXX_STATE_DIR` or the default `$HOME/.local/share/ternuxx`, and installed runtime modules live under `$PREFIX/lib/ternuxx`.

Native Termux owns desktop lifecycle, boot/recovery, SSH, service supervision, state, diagnostics, and host workloads. Managed PRoot profiles are optional guest providers with typed, target-specific lifecycle, setup, application, GUI, and shortcut operations. Guest operations do not replace or silently fall back to Native operations. Ternuxx does not invoke or modify the separate Ternux project or launcher.

## Shared management

The local management service exposes a typed operation allowlist to the CLI, TUI, authenticated loopback Web UI, and GTK management center. Clients share validation, authorization, preview/confirmation, journals, and result reporting. Each client may support a subset of the shared Native and PRoot operation catalog; unsupported actions are not shown as active controls.

The Web service binds to loopback, uses one-time bootstrap, scoped sessions, same-origin checks, CSRF, and durable idempotency for permitted writes. It has no generic shell or arbitrary file API. Native GTK is separately built and installed with source/bridge/binary identity checks.

## Native process ownership

Ternuxx controls only the Native services and processes it records. Desktop and service recovery requires exact process/config identity and refuses ambiguous ownership. Termux:X11 Android Activity visibility is reported separately from server readiness. SSH management applies only to the fixed Native Runit service; the separately owner-managed development port remains external to product lifecycle controls.

## Graphics and audio

Native graphics selection is stored in private Ternuxx state and applies to future Native desktop sessions. Each managed guest uses its distro-compatible Mesa/Turnip stack and a bounded Native display/audio handoff; graphics claims are qualified per guest and display route. The two rendering contexts are qualified separately; installed libraries, device nodes, or a renderer string without a workload do not prove application acceleration. Native PulseAudio remains Native-owned.

## Scope migration

On 2026-10-24, the owner first retired and then reauthorized Debian PRoot support. P11 now tracks its restoration and installed-guest acceptance. Treat older dated PRoot observations as snapshots, and do not use guest results to qualify Native workloads. Current status is in [phase status](PHASE-STATUS.md), the [capability matrix](architecture/CAPABILITY-MATRIX.md), and [PRoot restoration evidence](evidence/2026-10-24-p11-proot-source-restoration-audit.md).
