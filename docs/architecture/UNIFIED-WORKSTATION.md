# Ternuxx unified workstation architecture

**Current product direction:** Native Termux is the host and control plane, with optional Debian PRoot workloads. The owner reauthorized Debian PRoot support on 2026-10-24; P11 tracks restoration and acceptance. Use the current [phase status](../PHASE-STATUS.md), [capability matrix](CAPABILITY-MATRIX.md), [management API](MANAGEMENT-API.md), and [device profile](../testing/DEVICE-COMPATIBILITY.md) for current claims.
**Document status:** Historical architecture proposal from 2026-10-17, reconciled with current implementation on 2026-10-24. Sections below retain original design details; their feature status is not authoritative unless explicitly updated. For current implementation use [phase status](../PHASE-STATUS.md), [capability matrix](CAPABILITY-MATRIX.md), [management API](MANAGEMENT-API.md), and the repository audit worklist.
**Basis:** original design basis is repository audit at `1a891fa` (2026-10-17), existing architecture/ADRs, and the owner-confirmed shared-management direction on 2026-10-18.
**Historical scope:** the 2026-10-17 proposal covered Native Termux, an independent Debian guest, local AI, optional cloud providers, and four clients. A Native-only direction temporarily superseded the guest provider; the owner later reversed that decision and authorized PRoot restoration.

**Decision records:** [ADR-0004: shared management layer](decisions/ADR-0004-three-interfaces-shared-management.md), [ADR-0005: explicit capabilities, permissions, and tasks](decisions/ADR-0005-capability-permission-and-task-model.md), [ADR-0006: narrow existing-Ternux provider](decisions/ADR-0006-adapt-existing-ternux-provider.md), [ADR-0007: Launch Manager and display ownership](decisions/ADR-0007-launch-manager-and-display-ownership.md), [ADR-0008: per-provider shell profiles and managed configuration](decisions/ADR-0008-shell-profiles-and-managed-configuration.md), [ADR-0009: provider-scoped optional software](decisions/ADR-0009-provider-scoped-optional-software.md), [ADR-0010: Native Termux autonomy and bounded PRoot integration](decisions/ADR-0010-native-termux-autonomy.md), [ADR-0011: unified SSH connection and lifecycle management](decisions/ADR-0011-unified-ssh-lifecycle.md), and [ADR-0012: Native-owned shared dependencies and services](decisions/ADR-0012-native-owned-shared-dependencies.md), and [ADR-0013: optional owner-controlled off-home access](decisions/ADR-0013-owner-controlled-remote-access.md). These records define approved owner requirements and draft contracts; they do not imply that the listed runtime services or interfaces exist.

This proposal is historical design context, not blanket authorization for unrelated work. The owner has explicitly authorized Native-hosted Debian PRoot restoration; current PRoot behavior and limits are tracked in P11 and the capability matrix. The general-purpose daemon, dashboard, cloud services, license choice, and public release below are not current commitments. Current acceleration claims and limits are in the linked evidence and testing documents. Historical references to the separate Ternux repository describe proposal context only; Ternuxx does not modify or route through it. Use source, tests, and the current [capability matrix](CAPABILITY-MATRIX.md) for implementation facts; remaining proposal text below is not an implementation claim.

## 1. Product architecture

Use one application/domain layer for every interface. The CLI, interactive Terminal/TUI, Web UI, Graphical UI, and automation are adapters to the same use cases, configuration, state model, permission rules, diagnostics, and lifecycle services. The interfaces may format results differently; they must not implement their own package, model, provider, or service-management rules.

```text
CLI ─────────────────────────┐
Interactive Terminal / TUI ──┤
Local Web UI ─────────────────┼── Interface adapters
Graphical UI ─────────────────┤
Automation clients ──────────┘          │
                              Shared application services
                    config · capability · authorization · tasks
                    lifecycle · diagnostics · history · recovery
                                      │
             ┌────────────────────────┼────────────────────────┐
       Native Termux adapter   Existing Ternux PRoot adapter   AI adapters
       packages / host APIs    scoped guest workloads          CPU / GPU / NPU
       native services         independent lifecycle            local / cloud
```

The CLI should remain usable when no visual interface or server is running. The smallest design is a shared domain library plus thin interface adapters; an always-on daemon is not a prerequisite. If either graphical client requires HTTP, start a small on-demand loopback management server whose handlers call those same application services. It must use the same state/configuration stores as direct CLI commands and must exit cleanly when its clients end. A later persistent service needs separate resource, Android background-execution, and recovery evidence.

### 1.0 Fallback behavior

Every subsystem must have a defined fallback and report when it was used. A fallback must preserve the user's privacy, cost policy, selected provider, and existing working configuration; it must never silently cross an environment boundary.

| Failure | Safe fallback |
|---|---|
| Web UI, Graphical UI, or local API unavailable | Keep the CLI usable against the same local services/state; do not make GUI availability a service dependency. |
| Native or PRoot provider unavailable | Mark that provider unavailable and keep the other provider usable for its own operations. Cross-provider rerouting requires an explicit operation plan/selection. |
| Selected shell missing or unsupported | Preserve the current shell/configuration; offer the detected installed shell or Bash baseline only as an explicit alternative. Do not install/switch shells silently. |
| Shell migration or target validation fails | Keep the old shell and its last validated configuration selected; retain the staged target diff for diagnosis and offer retry/rollback. |
| Theme or config draft fails target-shell validation | Keep the last validated revision active; expose errors and offer the built-in default theme. |
| Config write/apply fails partway | Stop the operation, restore the prior Ternuxx-owned revision where safe, and report exact recovery state. Never overwrite unrelated RC files as recovery. |
| PRoot/display/permission integration fails | Defer only the affected operation, explain the owner action needed, and leave native services and existing Ternux workloads alone. |
| GPU/NPU backend fails correctness/readiness | Use CPU only when the workload has a verified compatible CPU route and the selected policy permits fallback; show the actual backend. |
| Local AI route fails | Do not send data to cloud automatically. A cloud retry needs explicit provider, data-transfer, and cost authorization. |
| Boot or service startup fails | Continue only independent selected services; record failure and recovery hints. Never launch every model/agent as an implicit fallback. |

### Native-first autonomy

Native Termux is the primary workstation and authoritative owner of native SSH, native services, boot recovery, lifecycle, and persistent continuity evidence. Native startup and recovery must not enter Debian PRoot, depend on Debian systemd, or wait for a guest agent. PRoot is an optional, independently managed execution provider; its unavailability affects only operations that explicitly target it.

Use `tx db` as Ternuxx’s first-party Debian shell command. The Native `db` and `droot` aliases now delegate to its validated regular-user and root forms after an owner-authorized exact migration; `x`/`xgo` remain convenience launchers. Treat shell configuration as user-owned: any future change needs explicit authorization, caller review, backup, and rollback. Never broadly clean up user launchers. Ternuxx integrations use namespaced commands and scoped adapters. Cross-provider operations require explicit authorization, bounded inputs, timeouts, and structured outcomes. Task checkpoints live in native private storage; after reboot, a PRoot-dependent task waits for a fresh guest session and the owner's request to continue. Process and wake-lock cleanup is limited to the service/workload that acquired the resource. See [ADR-0010](decisions/ADR-0010-native-termux-autonomy.md) for acceptance tests and evidence requirements.

### Optional access while away from home

Off-home use is an owner-approved product requirement, with remote access disabled by default. The design uses an owner-selected private VPN overlay or authenticated outbound tunnel; direct Internet listeners and router port-forwarding are not the default. A remote client reaches the same shared Ternuxx services through a narrow Native Termux transport adapter, then explicitly selects the native or PRoot provider. The adapter forwards typed, authorized operations rather than arbitrary shell text. Native-to-PRoot work remains a local provider-adapter call; the providers do not need to SSH to each other. The current loopback SSH candidate on port 8023 is not, by itself, an off-home route or the full management bridge. See [ADR-0013](decisions/ADR-0013-owner-controlled-remote-access.md). Actual network/device enablement still needs a separate review and owner action.

### Native-owned shared dependencies

Prefer Native Termux for Android-facing and host-shared services that should be
ready independently at boot. PRoot may consume those services through a
verified local API, protocol, socket, or explicitly scoped data contract. Keep
provider-local execution dependencies in the provider that runs the workload:
Termux/Bionic packages do not satisfy Debian/glibc package or library
requirements, and cross-ABI libraries must not be copied or symlinked between
environments. Boot starts only the selected lightweight services; it does not
start every package, desktop, model, or agent. See
[ADR-0012](decisions/ADR-0012-native-owned-shared-dependencies.md).

### 1.1 Layers and ownership

| Layer | Responsibility | Must not own |
|---|---|---|
| Interface adapters | Parse CLI/API input, present progress/errors, request confirmations, localize text | Business rules, direct protected-file writes, provider-specific policy copies |
| Application services | Validate requests, authorize actions, create plans/operations, coordinate modules, return structured outcomes | Arbitrary shell evaluation, UI state, cloud credentials in output |
| Domain/state | Typed config, provider and capability records, model metadata, operation journal, event history | Existing Ternux files or broad shared-storage scans |
| Provider adapters | Invoke explicitly supported Termux, PRoot, runtime, Android API, or cloud operations | Cross-provider assumptions or unscoped cleanup |
| Evidence/reporting | Store test provenance and derive compatibility/report views | Claims unsupported by accepted raw evidence |

Configuration and mutable state belong under Ternuxx-owned Termux app-private paths. Define schemas and migration rules before implementation. Keep generated phase/repository state separate from runtime state and human-authored evidence per [ADR-0003](decisions/ADR-0003-deterministic-state-and-skb-return.md). Never use shared Android storage as a default model catalog, log destination, or state directory.

### 1.2 Provider boundaries

| Provider | Role | Boundary and status rule |
|---|---|---|
| Native Termux | Host packages, native CLI/desktop processes, supported Termux:API/Boot integrations | Separate package/state namespace; native desktop/SSH lifecycle is implemented and exercised. Android cold-boot delivery and remaining installed-state parity are still being audited. |
| Existing Debian PRoot | Existing Linux userland, desktop/workloads, separately configured graphics path | Ternuxx uses typed, target-specific operations. This owner-approved audit permits task-required guest package/config changes after exact preview, state preservation, explicit apply, and tested rollback. Preserve user data and rootfs; do not reset/prune it, modify the separate Ternux source repository/launcher, invoke broad cleanup, or infer AI acceleration from Zink/Turnip desktop graphics. |
| Local CPU inference | Dependable inference baseline/fallback | Bounded pinned-model CPU path works through Termux llama.cpp; sustained performance, thermal, memory, offline, and release qualification remain. |
| Local GPU inference | Workload acceleration through a compatible backend | Shared Vulkan runner uses the selected Native graphics ICD and requires device/layer-offload proof. A checksum-verified official Termux backend extracted to a temporary prefix passed short full-layer runs on Adreno 825, including through the Ternuxx API. Live PREFIX still lacks the package; sustained and clean-install qualification remain. Native Termux and PRoot contexts are distinct. |
| Local NPU/Hexagon | Optional inference backend | Ternuxx exposes an experimental pinned Snapdragon b11849 HTP0 path, currently workload-verified only on SM8735. It requires complete HTP layer delegation, has no CPU fallback, and is slower than CPU for tested prompts; sustained and release qualification remain open. |
| Cloud AI providers | Explicitly authorized remote inference | Optional and disabled until configured. Each route identifies data destination and possible provider charges; never silently cloud-fallback a local/private request. |
| Future isolated environments | Separate, supplementary execution profile | Requires a demonstrated need and owner decision; cannot replace or minimize the established PRoot. |

All capability reports use cumulative stages `DETECTED`, `INITIALIZED`, `WORKLOAD_VERIFIED`, and `RELEASE_QUALIFIED`, alongside `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, or `UNKNOWN` results. `ACTIVE` means a workload’s actual backend was observed, not merely that a device node or library exists. Report CPU fallback visibly, including partial delegation.

## 2. Shared management modules

### Installation plans and optional software

The shared installer service owns one versioned optional-software catalog with distinct `native_termux` and `proot_debian` sections. Install selections are provider-scoped typed IDs. The planner resolves dependencies and conflicts, checks provider readiness, and returns an exact preview; it never interprets a catalog value as shell code. CLI, Web, and X11 clients display and confirm the same plan. Non-interactive defaults are core-only. Partial failures are represented per catalog item and provider. The PRoot target is an explicitly selected Ternuxx-managed guest by default; the existing independent Ternux guest is not a default mutation target. The catalog schema is a contract draft, not a populated or verified software list.

Modules expose application-service interfaces and typed data, not terminal commands that a UI or API can splice together.

| Module | Responsibility | Free-core direction / current status |
|---|---|---|
| Environment & capability | Inspect Termux/Android/PRoot/runtime facts with provenance and age | Basic truthful diagnostics are free; current diagnostics are partial. |
| Native lifecycle | Native desktop/services, dependencies, process ownership, clean shutdown | Native desktop and managed SSH lifecycle are implemented and exercised; Android cold-boot delivery and remaining installed-state parity are not fully qualified. |
| Launch registry/profiles | Named native, PRoot and shared-service targets; selected workspace/boot profiles; cross-provider resource reservation | Proposed in [ADR-0007](decisions/ADR-0007-launch-manager-and-display-ownership.md); no central registry or profile manager exists. |
| Shell profiles and themes | Select Bash, Zsh, or Fish independently for Native Termux and PRoot; manage themes and shell config through shared CLI/GUI/Web services | Not implemented; installer preselection, package plans, adapters, managed overlays, validation, diff, backup and rollback are required. See [ADR-0008](decisions/ADR-0008-shell-profiles-and-managed-configuration.md) and [profile contract](../../schemas/shell-profile.schema.json). |
| PRoot integration | Native Termux uses typed Ternuxx operations for inventory, guest verification, owned-session lifecycle, shortcuts, and selected configuration workflows | Existing Debian guest changes remain target-specific and preview-bound; P11 guest acceptance, shared-rootfs concurrency qualification, and clean reproducibility remain open. The separate Ternux CLI is not a dependency. |
| Package/catalog | Preview, consent, source, exact package set, transaction outcome and rollback limits | Basic install/update management remains free; no UI may bypass preview/consent. |
| Model library | Explicit managed directory, metadata, checksum, license, compatibility, load/use references | Basic model management is a free-core target, not implemented. Never scan personal shared storage. |
| Runtime/backend | CPU/GPU/NPU runtime availability, workload selection, fallback and evidence | CPU inference is bounded; Vulkan GPU routing is partial and workload-verified on the observed Adreno 825 with an experimental ICD; Hexagon HTP routing is partial and workload-verified only on SM8735. CPU fallback is explicit and never silent. |
| AI gateway/provider routing | Local API, configured provider adapters, explicit route and health | Basic local gateway/provider adapters are free-core targets; not implemented. Keep admin API separate from inference API. |
| Tools/agents | Registry of named capabilities and permissioned invocations | Safe essential tool use is free. No unrestricted shell tool by default. |
| Boot/service supervision | Manual lifecycle first; optional user-selected profiles and health policies | Basic startup controls remain free; boot is opt-in and Android constraints are reported. |
| Testing/evidence | Execute approved tests, validate schemas, retain reports, render compatibility | Basic reproducibility and public evidence remain free; harness/data are not implemented. |
| Recovery/update/release | Preview scope, state backup, recover Ternuxx-owned paths, update provenance | Essential safe recovery remains free; no complete recovery engine exists. Never repair the independent Ternux guest implicitly. |

Potential premium candidates are advanced orchestration, specialized business connectors, scheduled or fleet reporting, custom integrations, and hosted services with real operating costs. These add optional value; they must not gate CPU fallback, supported GPU/NPU, essential diagnostics, model basics, public evidence, or learning/developer access. This is a proposal, not a product or pricing approval. See [feature source of truth](../testing/FEATURE-MATRIX.yaml) and [premium distribution analysis](../readiness/PREMIUM-DISTRIBUTION.md).

## 3. Visualizer and X11 GUI specification

The Web Visualizer and X11 Desktop GUI are first-class whole-workstation interfaces, not AI-only dashboards. They are local control surfaces, not the public website and not separate backends. They should disclose when a module is unavailable and continue to offer safe read-only views if a runtime or gateway is stopped.

### 3.1 Navigation

1. **Overview** — native/PRoot status, active tasks and service health, capability stage, models/sessions, gateway/provider state, authorized resource summaries, warnings and evidence.
2. **Workstation** — native environment, PRoot connection, packages/dependencies/environments, service lifecycle, configuration, health, logs, recovery and operation history.
3. **Models** — catalog, explicit managed path, add/download, metadata/hash/license, format/quantization/size/compatibility, sessions and safe removal checks.
4. **Runtime & acceleration** — CPU/GPU/NPU stage, runtime adapters, selected backend per workload, visible fallback, compatibility and evidence.
5. **AI Gateway** — local endpoint, providers/routing, credential status without secrets, readiness, streaming, errors and reliable usage/cost summaries.
6. **Agents & tools** — integrations, tool registry, scopes, permission review, confirmations, execution history and config recovery.
7. **Boot & services** — profiles, dependencies, health, restart policy, logs, resource use, startup status and shutdown.
8. **Permission & capability center** — integration availability, authorization state, capability scope, verification time, limitations and Android revocation guidance.
9. **Task center** — progress, structured errors, safe cancellation and recent operations.
10. **Diagnostics & benchmarks** — tests, actual measurements, evidence reports and qualification state.
11. **Updates & recovery** — version, integrity, backup/migration preview, recovery guidance and rollback limits.
12. **Configuration** — validated settings, profiles and safe import/export.
13. **Extensions** — version, dependencies, compatibility and declared permissions; unavailable until a reviewed extension system exists.
14. **Documentation & roadmap** — guides, limitations, releases and phase status.

### 3.2 X11 Desktop GUI client

The Native GTK management center is implemented and installed as a client of the shared management services; CLI remains usable without X11. Display/session checks and visible GUI acceptance are tracked separately from service readiness. Full GTK interaction coverage and smaller-viewport review remain open. GTK is the selected current toolkit; new toolkit packages should be installed only when a reviewed task requires them and the exact dependency transaction is previewed. The GUI must call the shared application/API contract and must not own system state.

### 3.3 Primary workflows

- **First run:** inspect read-only facts → explain each available provider → let the user choose a profile → preview required package/model/runtime changes → ask for explicit consent → show operation progress → verify actual outcome → save a recovery/evidence record. Do not silently switch providers.
- **Run a model:** select a managed model → display license/hash/requirements → estimate resources → choose CPU or a verified compatible backend → state local/cloud destination and fallback policy → run → show actual backend and output/test result → allow unload.
- **Install or update:** show source, exact changes, conflicts, privilege scope, disk estimate if measured, and rollback limits → confirm → track progress/cancellation boundary → report installed version and failures.
- **Recovery:** inspect only Ternuxx-owned state → propose bounded actions with affected paths → export/backup preview → confirm consequential changes → journal each step → report incomplete rollback clearly.
- **Cloud request:** show provider, data leaving device, configured model and potential charges → require the user’s configured authorization → send only the request needed → record redacted status/latency, not prompt or key by default.
- **Boot profile:** user selects a small named set of services → check Android integration and dependency availability → show background/foreground limitations → opt in and verify next boot manually. No hidden watchdog/restart loop.

### 3.4 Mobile, accessibility, and localization

Use responsive layouts and progressive disclosure: common safe workflows first, detailed backend/configuration fields on request. Support keyboard-only navigation, visible focus, screen-reader names/status, scalable text, adequate contrast, reduced motion, touch targets, semantic error summaries, and no color-only status encoding. Validate on narrow phone viewports and low-memory operation.

Provide complete English and Bangla locale catalogs with stable message keys, plural/date/number handling, and a user-controlled language setting. Do not mix languages within a selected UI locale except for code, package names, and proper technical identifiers. Bangla wording and technical terminology need owner review before release. Public documentation can remain separately language-tagged.

Keep the frontend lightweight: static same-origin assets, lazy-load large evidence views, paginate logs, avoid redundant model/state copies, use event updates where practical and bounded polling as fallback. No analytics or telemetry by default. The CLI must work independently of frontend availability.

## 4. AI and model flow

Managed models reside in a Ternuxx-owned application directory, with explicit user selection for any alternate path. Never crawl `/sdcard`, `/storage/emulated/0`, or arbitrary home folders. For each model record source, version/revision, content hash, format, quantization, license/usage restrictions, expected memory, tokenizer/runtime compatibility, and verification state. Downloads require a displayed source/size/license and user confirmation; write atomically to a bounded path, validate hash, and reject traversal/symlink escapes. Do not redistribute model artifacts until their license permits it.

Backend choice is an explicit runtime decision per workload. Store requested backend, actual selected backend, delegated operations when measurable, fallback reason, runtime versions, and correctness result. Automatic selection may choose only among previously compatible choices; it must expose the decision and never change a private local request to cloud without asking. Model/session removal is blocked while in use unless the user deliberately stops the session.

Treat the **management API** as privileged local administration and the **inference API** as a separate, narrower workload interface. They must use separate authorization tokens/scopes, request limits, and logs. Cloud provider credentials stay in an OS/app-private credential store if one is selected after feasibility review; never send credentials to browser code or return them from an API.

## 5. Operation and state model

Every long operation gets a random opaque ID and a durable, bounded local record: type, requesting interface, provider, redacted inputs, preview/consent reference, state, progress, timestamps, result, failure, and cancellation/recovery status. Suggested states: `planned`, `awaiting_confirmation`, `queued`, `running`, `cancelling`, `succeeded`, `failed`, `cancelled`, `needs_recovery`. Transitions are validated by the shared application layer. Progress is monotonic when the task can provide a meaningful measure; otherwise use named stages instead of invented percentages.

Cancellation is cooperative. Package managers and non-interruptible driver/runtime operations may not be safely cancellable; disclose the boundary before execution. Writes use atomic replacement where possible, ownership checks, locks, and recovery journals. Retention is configurable and bounded. Logs/events redact keys, tokens, prompts, model input/output, private paths, device serials, and account identifiers by default; an export has a preview/redaction step.

## 6. Backend and interface contract

The proposed API is a versioned localhost management contract, documented separately in [Management API proposal](MANAGEMENT-API.md). It returns stable typed resource records, structured errors, operation IDs, progress, and diagnostics. All validation, authorization, confirmation, provider routing, and state changes remain in shared application services. HTTP routes must not call shell strings assembled from request data.

Every mutating request follows `preview/plan → confirmation → operation → verified result`. A short-lived, unpredictable confirmation reference is bound to the exact plan, current state version, action, and expiry; it is single-use. Read-only endpoints still minimize sensitive fields. API schema evolution is additive where possible; breaking changes use a new major version and clear CLI/UI compatibility behavior.

## 7. Security and privacy summary

The initial dashboard binds to `127.0.0.1`/`::1` only and has no LAN/public mode. Loopback does not make browser requests inherently trusted. The management server must validate `Host` and exact `Origin`, use same-origin assets, reject wildcard CORS, require a short-lived session token on state-changing calls, enforce CSRF protections, limit body size/rate, and reject unexpected content types. Browser session credentials should not be placed in URLs or persistent JavaScript storage. No authentication-less admin API.

Use capability-scoped authorization in the shared layer, with read-only default; require preview and deliberate confirmation for installs, deletes, updates, recovery, provider changes, boot changes, and remote/cloud routing. Tool execution uses a named allowlisted registry; no arbitrary shell endpoint. File operations constrain canonicalized paths to owned roots or an explicitly selected item. Audit sensitive actions without storing secret values or inference prompts.

The dashboard is not an internet-facing service. Off-home access is now an owner-approved product requirement under [ADR-0013](decisions/ADR-0013-owner-controlled-remote-access.md); its implementation and device/network enablement remain pending. Keep services loopback-only and use a separately reviewed private VPN/tunnel adapter; no direct WAN listener or router port-forwarding by default. Do not enable SSH, Wireless ADB, Shizuku, or a watchdog as an implicit dependency. Termux/PRoot separation and the existing guest-preservation requirements remain governed by [current architecture](../ARCHITECTURE.md), [hybrid integration](../HYBRID-INTEGRATION.md), and [threat model](../readiness/THREAT-MODEL.md).

## 8. Feature and integration status

The machine-readable feature matrix remains the canonical capability/commerce record. Add visualizer and management features there, and have any future website derive status from that data and accepted test reports. Do not duplicate live benchmark facts in frontend source.

Current integration status rechecked 2026-10-24: Native lifecycle/diagnostics, the typed management API, CLI/TUI/Web/GTK clients, and a scoped Debian PRoot adapter are implemented. P11 installed-guest interaction and owner-reported portrait plus landscape/fullscreen rotation passed on this device; see the [P11 acceptance record](../evidence/2026-10-24-p11-proot-source-restoration-audit.md#owner-physical-rotation-acceptance). The replay-guest lifecycle controls added to TUI/Web/GTK have source and adapter test coverage, while fresh guest setup remains a Native CLI handoff. Shared-rootfs concurrency and clean reproducible setup remain open. Ternuxx has bounded Native CPU, Vulkan, and experimental HTP inference routes; HTP is workload-verified on SM8735 with full offload and explicit no-fallback behavior, but remains slower than CPU on tested prompts and is not release-qualified. External Ternux CPU/Vulkan or HTP/QNN results remain research context and do not establish Ternuxx support. Native Termux and PRoot graphics remain separate contexts. See the [current feature matrix](../testing/FEATURE-MATRIX.yaml), [testing overview](../testing/README.md), [device compatibility matrix](../testing/DEVICE-COMPATIBILITY.md), and [external Ternux research](../RESEARCH.md#existing-ternux-ai-provider-separate-project-reviewed-2026-10-17).

## 9. Implementation sequence and gates

This sequence is a historical proposal and does not replace the current generated project roadmap or active P12 phase. It does not advance or gate current project phases.

| Phase | Deliverable and gate |
|---|---|
| 0 — Repository & environment audit | Produce an owner-reviewable baseline, feature inventory, boundary/permission/AI/GUI inventory, risk register and phase-mapped gap matrix. |
| 1 — Architecture & security foundations | Approve shared service/API, state, task, capability/permission, credential and provider-boundary decisions; define security acceptance tests. |
| 2 — Core management backend & CLI | Stabilize/test shared use cases and preserve a working CLI independent of any UI. |
| 3 — Boot & permission integration | Add justified adapters/profiles with idempotence, runtime authorization checks and physical-device evidence. |
| 4 — Full-product Web Visualizer | Deliver a mobile/local-secure UI for verified capabilities using the shared services. |
| 5 — X11 Desktop GUI | Select a lightweight client after measured toolkit/dependency review; retain the shared backend. |
| 6 — AI Runtime & Gateway | Prefer a versioned adapter to Ternux's existing CPU/Vulkan PRoot provider; qualify local runtimes/backends individually and preserve opt-in cloud routing. |
| 7 — Evidence & Recovery | Generate reproducible reports and implement bounded Ternuxx-owned backup/recovery. |
| 8 — Public Website & Commercial Preparation | Publish only verified feature/evidence data after license/legal and privacy gates. |
| 9 — Release Qualification | Traceable build/artifact, security/accessibility/device evidence, recovery/install validation and explicit release decision. |

This historical sequence is not a permission gate for the active owner-approved full-repository task. Current work must follow AI_ASSISTANT.md and CURRENT_STATE.md, including its Native/PRoot target boundaries, preservation, preview, and rollback requirements. Physical-device acceptance remains subject to the applicable project policy.

The launch/profile registry and backward-compatibility requirements are further specified in [ADR-0007](decisions/ADR-0007-launch-manager-and-display-ownership.md). In particular, the established Ternux aliases remain externally owned; the namespaced `ternuxx launch` commands are the proposed stable interface.

## 10. Owner decisions before implementation

| Decision | Recommendation | Why it remains open |
|---|---|---|
| Management server lifecycle | No always-on daemon; launch a local server only while the dashboard is used | Android background policy, memory and shutdown behavior need device evidence. |
| Local API transport/implementation | Define contract first; choose the smallest maintained local HTTP option compatible with Termux and tests | No language/framework/API server exists in source. Dependency, binding, and update policy remain to review. |
| Dashboard packaging | Static same-origin frontend served by the on-demand manager; do not choose a heavy desktop/web stack yet | Requires mobile-memory and accessibility prototype evidence. |
| Credential storage | Select a Termux-compatible private storage mechanism; never browser/localStorage or logs | Android Keystore access from Termux and recovery/export trade-offs are unverified. |
| Model source/catalog | Start with user-selected local models; approve any remote catalog/source and licensing rules separately | No model license/provenance policy or provider exists. |
| Inference runtime/backends | Native CPU and Vulkan runners are implemented; separately assess experimental HTP/QNN | Termux supplies the version-matched Vulkan plugin as a reusable package artifact; HTP/QNN remain unqualified and cannot be treated as supported NPU inference. |
| Inference API compatibility | Decide whether to offer OpenAI-compatible routes, a native API, or both | Compatibility surface and security impact are unimplemented. |
| Cloud providers/fallback | Explicit opt-in per provider and per route; no implicit local-to-cloud fallback | Data transfer, charges, regional/privacy terms, and user experience require approval. |
| Tool registry | Named, least-privilege operations; shell access not default | Capability list, confirmation tiers and audit retention need product review. |
| Boot profiles | Manual launch first; optional Termux:Boot only after user opts in | Android background and failure recovery behavior need device validation. |
| Local authentication | Short-lived session + CSRF/origin/host defenses even on loopback | Concrete secure token provisioning for mobile browser remains to test. |
| Bangla UI wording | Complete locale, human-reviewed by owner | Terminology and translation quality need owner sign-off. |
| Premium candidates | Keep all essential management, inference, diagnostics and evidence free | Demand, license, security, maintenance and unit economics not established. |

## 11. Acceptance checklist

- CLI and dashboard invoke the same application services and authorization logic.
- CLI remains usable without the dashboard/server.
- Native Termux and existing PRoot states/lifecycles remain distinct; PRoot is never treated as a security sandbox or mutated implicitly.
- Dashboard binds loopback by default and resists cross-origin and CSRF requests.
- No arbitrary shell, model-directory crawl, credential display, prompt logging, or silent cloud fallback.
- Every accelerator status names the workload/process context and evidence stage; CPU fallback is visible.
- Long tasks report real stages, outcomes, cancellation boundaries, and recovery state.
- Mobile English/Bangla UI is accessible and resource-bounded.
- Reports and public feature catalog derive from canonical evidence and matrix records.
- All unimplemented features remain labeled planned/unknown; no deployment or release claim is implied.
