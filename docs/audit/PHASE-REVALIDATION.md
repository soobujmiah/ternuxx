# P1–P3 criterion revalidation — 2026-10-22

This maps every exit criterion currently written in the [roadmap](../ROADMAP.md) to evidence and the work still needed for the full repository audit. It does not reopen or silently recertify historical phase transitions. [Phase state](../../project/phase-state.json) remains authoritative for those transitions.

**Date basis:** phase-state `completed_on`/`skipped_on` values use UTC calendar dates from `tools/phase_docs.py`. Device observations may record Asia/Dhaka local time alongside UTC. Existing phase dates are preserved as recorded; any date-label discrepancy is reviewed as provenance metadata and does not independently pass or fail an acceptance gate.

The P3 transition is a concrete boundary example: commit `b3f61d4` records `completed_on: 2026-10-21` and has commit time 2026-10-22 02:50:27 Asia/Dhaka, which is 2026-10-21 20:50:27 UTC. The linked [RB08 P3 evidence](../evidence/2026-10-22-p3-rb08-postboot-exit-audit.md) is dated October 22 in Dhaka-local naming. The dates are consistent under the declared UTC phase-state rule; preserve both records as written.

**Reading rule:** a dated completion report is evidence of the recorded review. Current fixtures test source behavior in their covered cases. An installed-state query proves only the queried state. None substitutes for an unobserved transaction, fresh installation or device boot.

## P1 — three exit criteria

| Roadmap criterion | Evidence inspected | Current audit disposition |
|---|---|---|
| Official base candidates plus reviewed simulated transactions; dated optional app sources | [P1 completion](../evidence/P1-compatibility-research.md) references the dated research/index/simulation review | Dated evidence only. Reconcile the full research sections, candidate manifests and original resolved simulations; a new official-index check is not yet recorded in this continuation. |
| Unverified behavior and NPU process-context limits are explicit | P1 completion explicitly leaves SM8735/QAIRT mapping and shell/PRoot NPU access unproven; current roadmap keeps NPU workload qualification open | Documentation boundary agrees at this level. Inspect remaining GPU/NPU/feature matrices and source before declaring all claims consistent. |
| No-install report/checklist; unresolved runtime licensing, ABI and Android integration remain open | P1 completion records read-only commands and no device mutation in that phase | Historical no-install scope, not a claim that subsequent phases installed nothing. Primary-reference freshness and complete provenance remain to be rechecked. |

## P2 — three exit criteria

| Roadmap criterion | Evidence inspected | Current audit disposition |
|---|---|---|
| Exact install transaction preview before consent | [P2 completion](../evidence/P2-phase-completion-2026-10-18.md), [four-package validation](../evidence/P2-live-installer-preview-validation-2026-10-18.json), the dated package-plan fixtures in the [2026-10-22 732-test regression](../evidence/2026-10-22-terminal-guest-regression.json) | The four-package apply was intercepted; it did not execute APT. Current fixtures support preview binding. The original 77-package pre-consent preview is unrecoverable (A23), so historical approval coverage cannot be upgraded to proven. Fresh Native transaction replay remains open. |
| Start/repeated start/partial failure/stop/repeated stop/unrelated preservation | P2 completion references physical lifecycle evidence and later fixture regressions | Recorded historical pass; current suite supports covered source behavior. Do not restart the workstation merely to recreate it. Review the underlying device record and exact current lifecycle coverage; a fresh Native isolated replay remains open. |
| Physical Termux/X11/display/audio evidence | P2 completion references the device record and owner-observed GUI/audio; [current entrypoint inventory](../evidence/2026-10-22-native-entrypoint-inventory.json) covers selected installed scripts/modules | Selected installed identities are current, not a fresh display/audio lifecycle qualification. The new [read-only package check](../evidence/2026-10-22-p2-package-revalidation.json) confirms 77/77 exact installed versions/status with no package mutation or index refresh. Rendering, visibility and original consent are outside that query. |

## P3 — six exit criteria

| Roadmap criterion | Evidence inspected | Current audit disposition |
|---|---|---|
| Read-only Doctor and fail-closed missing/failed/unknown/stale/conflict handling | [RB08 exit audit](../evidence/2026-10-22-p3-rb08-postboot-exit-audit.md); current shared source regression | Historical device result plus current covered fixtures. Complete stable-finding/source review is still open. Android socket-to-process correlation remains unknown. |
| Fixture-verified TTY ownership; serialized, previewed, confirmed, journaled/recoverable mutations | RB08 exit audit, [session contract](../architecture/PROOT-SESSIONS.md), current session/broker/attachment tests | Ownership/transport implementation has advanced during P4; three real CLI/TUI attachment leaks were reproduced and fixed. All-client live lifecycle remains unqualified. The entire mutation registry still needs per-operation coverage review. |
| Shared P3 actions across all clients or explicit accepted limits | RB08 exit audit references the accepted P3-first decision; [client matrix](../architecture/CAPABILITY-MATRIX.md) is the implementation authority | The terminal was explicitly staged for P4. A later sequential same-session handoff passed through CLI, Web API, TUI and installed GTK/VTE, but this proves terminal continuity only, not parity for every lifecycle or management mutation. This does not waive the owner's later credential/recovery, service-policy and interaction requests (A10/A22). Review every supported action against each actual client; a catalog entry is insufficient. |
| Installed boot/recovery parity plus preview/apply/rollback preservation | [Current entrypoint inventory](../evidence/2026-10-22-native-entrypoint-inventory.json), RB08 audit, [monitor registration/replay](../evidence/2026-10-22-monitor-service-registration.md) | All seven checked script entrypoints and three canonical recovery modules matched. Monitor registration received an isolated live replay. Other config/profile/package/driver parity and every rollback path remain open. |
| Authorized Native cold boot/background behavior; PRoot/Hybrid deferred | RB08 audit records changed boot, matching observer, ready Native log, Cron result and authenticated 8023 client | Pass remains limited to that observed boot. Private checkpoint remains NOT_READY, automatic resume is off. Canonical modules deployed after boot have no later cold-boot observation. No reboot is authorized by this audit procedure. |
| Preserve Native XFCE, SSH channels, guest rootfs and scoped launch workflows | RB08 preservation record; current Native development session; separate-guest installer target checks | Current development and fresh setup are separate from the working guest. Full original-to-current user-data preservation is not inferred from selected hashes or a running process. Finish the live wrapper's selected-file/root identity comparison and review remaining preservation evidence. Legacy launcher retirement is governed by the later P4 owner decision. |

## Remaining evidence work

I have mapped all twelve roadmap exit criteria; their underlying artifacts, source coverage and current reproducibility are not all revalidated. The full document/source inventory is still incomplete. Remaining work includes full primary research/provenance review, current installer/lifecycle coverage mapping, every P3 operation/client boundary, complete installed configuration/driver inventory and supported fresh replay with rollback.

A15 tracks phase date-basis reconciliation. This table does not invent a new completion date or replace the observed RB08/manual/checkpoint distinctions. No workstation restart, guest stop, package update or credential mutation was performed for this mapping or the read-only 77-package comparison.
