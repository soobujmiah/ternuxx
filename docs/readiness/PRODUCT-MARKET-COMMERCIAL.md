# Product positioning, market and commercial model

**Reviewed:** 2026-10-24. This is a research hypothesis document, not an approved offer, price list or sales claim. Historical multi-provider assumptions are not current Ternuxx scope.

## What the product is today

**Current factual description (2026-10-24):** Ternuxx is an early-stage Android workstation manager with Native Termux as host/control plane and optional Debian PRoot workloads. `./tx` in the source checkout and the installed `tx` command are canonical; the older `ternuxx` command is a compatibility entrypoint. The repository includes Native package planning, desktop/SSH lifecycle, a shared management service, bounded CPU and Vulkan inference, experimental SM8735 HTP inference, and CLI/TUI/Web/GTK management surfaces. P11 one-device guest/client acceptance passed; P12 acceleration qualification remains in progress. There are no public releases or release-qualified product tests. See [phase status](../PHASE-STATUS.md), [current state](../../CURRENT_STATE.md), and the [repository audit worklist](../audit/REPOSITORY-AUDIT.md).

**Product promise to test:** give advanced Android users one evidence-led way to inspect and manage Native Termux workstation workflows through consistent interfaces and guided recovery. The distinction between desired architecture and usable product must stay visible on all marketing pages.

## Likely first user groups

| Segment | Need / likely pain | Fit now | Evidence / validation |
|---|---|---|---|
| Advanced Termux users | Reliable install, desktop lifecycle, recovery and clear capability boundaries | Closest fit to owner problem; product not qualified yet | Recruit a small opt-in pilot after the supported Native profile is reproducible; observe setup/recovery friction |
| Android developers using phone as workstation | CLI, editors, compilers, SSH, selected Android APIs, repeatable workspace | Plausible but no validated use cases beyond owner | Interview developers; record workflows, offline/network and keyboard constraints |
| Linux-on-Android learners/hobbyists | Low-friction distro and desktop setup, guided recovery | Competes directly with established apps; support burden may be high | Compare setup failure paths, onboarding and device coverage |
| Privacy/offline-first users | Local state and no mandatory telemetry/cloud accounts | Product principles align; no audit yet verifies every code path | Threat-model, network-egress and logging review before claim |
| Local AI/accelerator users | Actual GPU/NPU access from a named application/workload | Experimental CPU/Vulkan/HTP paths have bounded device-specific workload evidence; sustained support and release qualification remain open | Validate customer demand separately; do not promise acceleration until repeated correctness, memory, and thermal qualification passes |
| Users who need setup/maintenance help | Human troubleshooting and device-specific configuration | Potential first service buyer after a stable supported profile exists | Customer interviews and paid pilots; no demand/traction currently established |

## Alternatives and competitive position

| Alternative | Verified current offer/evidence | Relevance | Limitation for comparison |
|---|---|---|---|
| Termux + community configuration | Termux is the base native terminal/package ecosystem. Termux:X11 requires both Android app and Termux companion package. Official project docs describe the host/display split. | Directly supplies native layer; users may assemble their own workflow without another manager. | Termux itself is not a full device-neutral workstation manager; do not claim superiority without comparative testing. |
| Andronix | Current official site describes Andronix 10.1 with app-guided Linux installs, nine distros, desktop/sound, no root, and optional paid Modded Pass/Complete; current prices vary by region and were showing a time-limited promotion when checked. Docs separate free distro/desktop access from paid extras. GitHub's command-line repo reports MIT; this is not the license of the Android app or every modded asset. | Closest productization/commercial example: guided install plus optional add-on monetization. | Andronix is not the same provider architecture; do not copy its UI, scripts or marketing. Its current feature/pricing snapshot will change. |
| UserLAnd | Official site describes a free app to run Linux distributions/apps on Android without root; public Android repo contains distro-specific assets in separate repos. GitHub API currently reports no recognized repository license. | Competes for no-root distro/app access. | “Public source” does not prove a redistribution license; per-component support and device behavior need direct review. |
| Linux Deploy | Official GitHub README describes distro install into image/directory/partition, SSH/VNC/X11/Framebuffer, and says it works better with superuser rights; repository shows GPL-3.0. Source last pushed in 2022. | Adjacent rooted/chroot deployment and service management alternative. | Different root assumptions and older source activity; not a direct comparison for an unrooted Termux-native product. |

Primary sources: [Andronix official product/pricing](https://andronix.app/), [Andronix source repo](https://github.com/AndronixApp/andronix), [Andronix open-source note](https://docs.andronix.app/v10/miscellaneous/open-source), [UserLAnd official site](https://userland.tech/linux/), [UserLAnd repository](https://github.com/CypherpunkArmory/UserLAnd), [Linux Deploy](https://github.com/meefik/linuxdeploy), Termux:X11. Accessed 2026-10-17.

### Differentiation: claim versus present evidence

- **Potential differentiated direction:** provide consistent Native Termux management, read-only diagnostics, ownership-aware recovery, and workload guidance across CLI, TUI, Web and GTK.
- **Currently usable differentiation:** not yet commercially verified. The code is early and device qualification, release readiness, licensing and support remain open.
- **Defensibility:** not a moat today. Long-term value would come from verified device compatibility, safe lifecycle/recovery, quality support and evidence records; those are maintenance costs, not proprietary lock-in.
- **Market evidence:** no customer interviews, waitlist, service inquiries, conversions or revenue were found in the audited repo. GitHub stars/forks are not buyer evidence. Do not estimate total market size from them.

## Minimum commercially credible product

Before selling or advertising a supported workstation profile, require:

1. Honest, reviewed brand/license/provenance decision and product name clearance.
2. Native installer preview/apply/rollback with user-readable ownership scope, accurate help and tested failure behavior.
3. Doctor and safe lifecycle on an actual named Android/Termux/Termux:X11 profile.
4. Optional Debian PRoot setup/session controls with clean-device replay, safe lifecycle/recovery, and verified display/audio/workload behavior; do not couple Ternuxx state or lifecycle to the separate Ternux project.
5. Tested recovery/backup boundaries and local data/privacy policy.
6. Versioned release artifacts, source provenance, checksums/signatures where feasible, known issues, support boundaries, accessibility/bilingual install docs.
7. A small pilot across more than the owner's one device/workflow before claiming broad compatibility.

The minimal first revenue product should be a human-delivered, bounded setup/diagnostic service on a tested profile, not a subscription platform or paid software module.

## Business-model comparison

| Model | Adoption/trust | Revenue path | Cost and risk | Assessment |
|---|---|---|---|---|
| A. Free/open-source core + paid services | Strongest if license is clear and core is genuinely useful; users may fork or redistribute | Setup, troubleshooting, maintenance, training, customization | Owner time dominates; service liability and scheduling; open license allows commercial forks | Best first validation model **if** owner wants an OSI open-source license. Do not call current unlicensed code open source. |
| B. Free core + paid premium modules | Core can attract users while modules earn product revenue | One-time modules or carefully justified recurring feature | Entitlement/offline updates, payment/tax/legal work, platform fragmentation, dual-maintenance burden | Premature. Introduce only after repeated demand and clean module boundary. Never paywall current core to manufacture upgrades. |
| C. Hybrid: useful free core + paid services, then selective premium | Balances adoption with human-first revenue; module option remains later | Services first; modules only after usage evidence | Requires clear license, scope, support capacity and separate paid/free maintenance plan | **Recommended staged model**, conditional on owner license decision. Stage 1 services; Stage 2 evaluate premium only with evidence. |

An OSI-approved open-source license permits commercial use by recipients; a noncommercial restriction cannot also be labelled OSI open source. The historical PolyForm/addendum wording must be resolved first. Brand/trademark can remain owner-controlled independently of a permissive source license, subject to counsel.

## Proposed service catalog (not yet offered)

| Service hypothesis | Deliverable | Explicit exclusions | Delivery / data | Validation gate |
|---|---|---|---|---|
| Compatibility and setup review | Scoped preflight, package/source review, agreed checklist and written result | No guaranteed GPU/NPU, no unauthorized installs/settings, no broad file access | Owner-operated or customer-controlled steps; collect only device/software versions and volunteered logs | First offer after a repeatable profile and support runbook exist |
| Assisted installation | Walkthrough and documented install on a named supported profile | No unattended remote shell, no password/SSH key collection, no unsupported device guarantee | Screen-share only if separately consented; customer executes protected Android actions | Pilot with written scope, time cap and rollback plan |
| Troubleshooting/recovery | Diagnose one described issue; recovery plan limited to project state | No Ternux rootfs repair/pruning; no recovery guarantee for untested states | Customer-selected/redacted logs; delete temporary support copies by defined retention schedule | Test runbook and incident boundary first |
| Maintenance/update help | Review release notes, backups and package plans | No automatic upgrade or silent system modifications | Time-boxed session; exact transaction consent | Repeat customer interest needed |
| Custom integration/training | Written scope, acceptance criteria, source ownership terms | No open-ended support or third-party license violation | Signed statement of work once operating legally | Counsel-reviewed IP/payment terms before accepting paid work |

No support SLA, price, warranty, response time or current availability is approved.

## BDT price hypotheses and unit economics

These are **planning arithmetic only**, not researched market prices. They are derived from an unvalidated owner-time placeholder of BDT 500–1,250/hour, with no local competitor quote or buyer interviews. Do not publish or charge these figures without owner review and professional tax/payment advice.

| Package hypothesis | Time assumption | Illustrative BDT range | Validation needed |
|---|---:|---:|---|
| Diagnostic session + short report | 1–1.5 h | 500–1,875 | At least 5 buyer interviews and one paid pilot |
| Guided setup on an already-supported profile | 2–4 h | 1,000–5,000 | Record actual prep/support time, failure/refund rate |
| Recovery/troubleshooting session | 1–3 h | 500–3,750 | Define what is excluded and safe recovery boundaries |
| Custom integration/training | 4–12 h | 2,000–15,000 | Estimate scope after discovery; written acceptance and IP terms |
| Monthly maintenance (future) | 2–4 h/month | 1,000–5,000/month | Do not launch subscription until recurring work/demand is demonstrated |

Use price = delivery hours × owner-approved effective hourly floor + directly attributable payment/communication/tool costs + tax/accounting effects determined by a professional. Show gross revenue separately from contribution and net income. Don't bundle unpaid indefinite support.

| Scenario (illustrative only) | Jobs/month | Avg. hours/job | Assumed BDT/hour | Gross service revenue | Direct contribution before owner time, tax, refunds and payment costs |
|---|---:|---:|---:|---:|---|
| Conservative | 0 | — | — | BDT 0 | BDT 0 |
| Base planning case | 2 | 3 | 750 | BDT 4,500 | Not calculated until actual costs/time are known |
| Optimistic capacity case | 6 | 4 | 1,000 | BDT 24,000 | Not calculated until actual costs/time are known |

These are not forecasts or demand evidence. A transparent spreadsheet should later include delivery/sales/admin hours, payment fees, VAT/tax, refunds, connectivity, domain/hosting, legal/accounting and maintenance. Break-even cannot be credibly stated until those inputs and owner capacity are measured.

## First-revenue validation

After minimum product gates, interview 5–10 technically capable Android/Termux users, ask them to describe the last failure and current workaround, and request consent before recording any notes. Offer at most two time-boxed paid pilots with a written scope and no performance guarantee. Track inquiry source, willingness-to-pay range, hours, failure class, refund request, and repeated need. Do not log personal data that does not answer a product question. Stop if support time exceeds the value users show they will pay.
