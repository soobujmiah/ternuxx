# Repository/reinstall audit — 2026-10-27 (Asia/Dhaka)

## Scope and evidence classes

This pass combines whole-tree mechanical inventory/syntax/document checks, the full
repository test harness, and focused manual review of installer, guest identity,
GUI routing, Native graphics, shared service authorization and session lifecycle.
It is not a claim that every source line or every workload was manually qualified.
Source/fixtures, owner report, historical device qualification and current read-only
device observations are kept separate. The Native checkout was used directly; no
SSH development shell was used. The separate Ternux repository was not modified.

Initial tracked-tree snapshot: 2,607 files, 205 Python sources and 38 shell scripts/
entry points; every inventoried Python file parsed and every shell script passed
`bash -n`. New modules/tests are separately compiled and included in CI. The
GTK/VTE source syntax check and document inventory/local-link audit are run before
handoff. Generated repository status owns exact commit/CI facts.

## Findings and repairs

1. **Existing root-only guest skipped account setup.** Read-only Debian passwd
   inspection found only the app-UID/nonlogin account in the ordinary UID range,
   without a `/home/USER` login or managed receipt. The existing-rootfs add-on path
   installed selected software but never provisioned an ordinary user. A new
   preview/apply account engine binds rootfs identity and passwd digest, locks with
   the add-on engine, checks guest idleness, and creates only a newly selected user.
   Existing account selection records a default without rewriting passwords/sudo.
   Passwords use a private FD/stdin, not arguments/environment/plans/receipts.
   Failed partial account setup remains journaled for explicit inspection.
2. **Debian account resolver ignored managed receipts.** Both distro account and
   fresh-install receipts can now supply an identity-verified default, validated
   against current passwd. Missing and ambiguous users have distinct actionable
   messages. No automatic root fallback is introduced. Explicit `pgui --user` is
   revalidated and passed through the standalone wrapper.
3. **Official GPU driver is unsupported on this device.** Read-only installed
   Mesa/Freedreno 26.2.5 `vulkaninfo --summary` returned
   `VK_ERROR_INCOMPATIBLE_DRIVER`, chip ID `44030000`, GPU ID `6830`. No renderer
   workload or desktop restart was performed. Forcing that same ICD is not a fix.
   The historical, hash-pinned experimental Adreno 825 candidate now has reviewed
   private extraction and a versioned public acquisition path. Every use verifies
   hashes and loader/device compatibility, preserves system packages and guards
   backend-selection drift. Explicit selected GPU environments remove inherited
   software-only forcing; system/CPU mode retains caller choices.
4. **Login/help was Debian-only.** `tx db`/`tx debian` and `tx ub`/`tx ubuntu` use
   the shared owned PTY/session engine and bind the selected distro to the plan.
   Canonical Ubuntu still requires a managed identity receipt. `tx kali` is an
   explicit unsupported placeholder; no unqualified distro adapter is advertised.
5. **Window organization.** Existing single-writer keyboard/log/resize handling is
   retained; green section titles and a compact seven-stage bar improve hierarchy.
   PTY tests continue to cover mode restoration, interrupted/delayed keys, paging,
   resize/shrink and worker status propagation.

## Release record

The owner explicitly authorized publication of the verified GPU bundle after the
original roadmap-only packaging scope. Versioned experimental tag:
`native-mesa-adreno825-2026.10.27`. Runtime acquisition uses a fixed public release
URL/SHA-256, never `latest`, GitHub authentication or an expiring Actions URL. It
has no alternate-repository or integrity-bypass fallback. Reinstallation reuses a
verified private cache; cache corruption or ABI/device incompatibility fails before
changing the backend. Running desktops retain their original environment until the
owner explicitly restarts them.

The preparation tool verifies original upstream ZIP SHA-256
`8493482210f9cc625f4fadb95e53cb417650c31f6e2b5a0d8725a2ef3c82ff5e`, the nested tar,
and original package hashes. The release ZIP contains only the unchanged `mesa`
and `mesa-vulkan-icd-freedreno` packages plus source license notices, pinned recipe
and provenance; original OpenCL/dev/swrast packages are excluded. Matching full Mesa
source archive SHA-256 is
`5211bd235658a0585740fb2dfbe64e7e8ca3085ad8e423fc333b4d5e0de6fd93`.
The release ZIP SHA-256 is
`42475bf49bb0241717ce379d4efa50ae4b3b8e88676f46f672e37121249effe0`.

Actual staged-release verification passed archive hash, both original package hashes,
private temporary extraction and all four pinned runtime-file hashes. Static ELF
inspection found all direct non-Android-system dependencies in the current Native
prefix, including libLLVM. This does not prove dynamic ABI compatibility; the
installer's Vulkan probe remains mandatory. No staged driver was loaded or selected
on the owner's device during preparation. The release includes PROVENANCE.json,
NOTICE.txt, SHA256SUMS and full corresponding source. It does not assert MIT-only
licensing, upstream conformance, a byte-reproducible build or completed P12 transitive
build-input attribution; `licenseConcluded` remains `NOASSERTION` in that record.

## Validation and remaining gates

New fixtures exercise real-manifest parsing, missing-account discovery, account-plan
drift, private password delivery, default receipt selection with multiple users,
pinned release extraction/cache/ABI rejection/integrity failure and alias propagation.
Existing guest, management, graphics, desktop and installer suites are rerun; exact
complete-suite results belong to generated CI status. Current SSH wildcard/password
warnings are owner environment observations; the audit did not rewrite unmanaged
SSH configuration or activate the dedicated Ternuxx service.

Owner reinstall and visible Native/guest desktops, audible playback, application
GPU rendering and broader distro qualification remain live gates. P12 source-owner/
license-attribution and source-rebuild gaps remain open; this mirror does not mark
them complete. General Ternuxx application release licensing/packaging remains a
separate roadmap item.

## Owner-reported account screen follow-up

The owner subsequently reported an apparently blank account screen with literal
arrow-key echo. Read-only user enumeration still returns no ordinary account;
that branch previously entered canonical shell username/password reads outside
the selector's terminal/input loop. The replacement is an explicit text form,
with a clearly visible field and typing instructions instead of arrow-menu hints.
It filters cursor-key sequences, masks password input, supports Backspace and Esc,
refreshes branding in the same writer and preserves input during terminal resize.
Account collection resets the installation/log phase. A full PTY fixture drives
root-only passwd discovery, username editing with arrows, sudo selection, both
hidden password fields, resize from large to compact layout and termios recovery.
Fixtures create no live guest or account. Large green animated logo and styled
rules have source/PTY evidence; actual owner-device visual acceptance is pending.

## Subsequent stage-5 wait / username visibility report

Confirmed source defect: the text field always used a negative tail offset, even
when the username was shorter than the field. Bash returned an empty substring.
Only overlong display strings are cropped now; a real PTY assertion checks visible
`> alice` text after arrow filtering and Backspace editing.

The owner's later stage-5 screenshot alone cannot establish which backend command
was waiting. Source review identified silent captured guest previews: existing
rootfs APT simulation and download-size estimation have bounded subprocess waits,
but previously provided no live operation label. The guided preview observer now
shows the named operation plus elapsed-time/branding refresh, retains stdout as
machine JSON in a private temporary file, relays stderr, and restores terminal
state after success/failure. Noninteractive preview input is disabled and queued
keys are discarded before the next selector. The PTY delayed-query fixture checks
this contract. No live APT, package installation, audio playback or guest mutation
was run to reproduce the owner's install. Backend wait diagnosis remains pending
owner retry with the operation label visible.

## Review/output state and Android add-on header follow-up

Source review found phase entry unconditionally labeling the pane as installation
log, regardless of whether a reviewed command had begun. It also found that a new
command caption moved the cursor away from the content pane before output began.
The frame now distinguishes review/confirmation, plan-query output and command
execution, explicitly resets the output cursor to the pane, and paints a status
line at phase entry. Managed-profile loading is now observed before the earlier
guest-plan queries, so a backend wait has a named entry point. This is not a claim
that the screenshot proves a specific backend deadlock or package failure.

PTY coverage checks review-before-command captions and a large responsive header.
A bounded read-only `pm list packages com.termux` snapshot on the current Native
device positively detected Boot, API, Styling and X11. No package/service/settings
mutation was performed. Limited Android visibility remains unknown rather than
being treated as absence. Header layout and animation still need owner visual
acceptance in the actual installer.

## Combined approval / live guest APT implementation

Owner stopped their installation and changed the desired sequencing: every
selection, exact package plan and consumption estimate must precede workload
installation. The combined coordinator now collects account/DE/app/runtime/GPU
choices, resolves Native upgrades with selected packages in one exact transaction,
previews every guest/account/launcher/GPU operation, and binds the private component
records plus report hash into one combined ID. A scrollable full report and
explicit unknown-size acknowledgement precede final approval. Missing planner
Python/X11 prerequisites retain their own minimal bootstrap consent; signed-index
refresh is planning metadata, not a guest/workstation transaction.

The known download/installed/additional-disk subtotal and peak/free-space check use
Native package metadata and existing-guest APT estimates. Fresh pinned rootfs layer
bytes are explicit; unresolved guest APT/unpacked rootfs, graphics and GTK build
scratch are labeled unknown. No fabricated complete-size guarantee is made.

Live guest APT was previously captured until process completion. The apply path
now drains bounded subprocess output continuously to categorized stderr events,
keeping stdout machine-readable. Download/unpack/configure/warning/error receive
separate terminal colors; resize/branding updates remain in the single writer and
are throttled during bulk logs. Timeout/interrupt cleanup affects only the owned
streaming child process group. Failure journals mark errors; no automatic repair,
rollback or replacement plan is applied. Fixture evidence covers rejecting a
combined plan without any apply calls, every preview preceding approval, report
mutation rejection, merged upgrade/new-package pinning, events arriving before
child completion and bounded timeout cleanup. No live installer was run by the
assistant during this work; current-device end-to-end acceptance remains pending.

The combined account preview has an explicit conditional contract: dependency
packages may add non-login system accounts with UID 1–999 before the account
step. All baseline passwd records remain hash-bound; ordinary-user additions,
existing-record edits/removals, rootfs drift or selected account/home/sudo-action
changes still fail. This prevents expected systemd/service user creation from
invalidating a reviewed new-user action, without silently adopting a new account
plan. Legacy standalone account previews retain their strict whole-passwd digest.
A fixture accepts a package-style system user and rejects an added ordinary login.

## Failed guest HTTPS run / plan report viewer repair

Read-only owner-device evidence: the failed combined run lasted 19,249 seconds and
ended at guest packages/account stage. The matching guest journal says
`TimeoutExpired`. Its plan requested 813 new packages, approximately 385 MB download
and 1547 MB additional disk. Current inventory has 78 installed packages, zero
incomplete dpkg records, no ordinary login account, empty archive/partial caches,
and no `ca-certificates` package or public guest CA bundle. Old output was not
persisted, so the precise prior HTTPS error cannot be retrospectively asserted.

Native curl HEAD followed the exact first reviewed snapshot package URL to HTTP
200. Native Python with its verified CA returned 403 with the default user-agent;
`curl/8` returned HTTP 200, and a one-byte Range GET returned HTTP 206 with the
archive prefix. This is bounded network reachability evidence, not package or
workload installation. Two URI-only guest APT queries (download and install
print-URIs modes) both reported the same epoch-escaped KDE cache filename; the
before/after guest dpkg status hash was identical. No complete archive was
downloaded/staged, and no package installation/recovery operation was executed by
the assistant. The network probe read only one byte without saving a payload.

The [APT manual](https://manpages.debian.org/trixie/apt/apt-get.8.en.html)
documents URI destination filenames separately from remote filenames. The repair
uses APT's metadata output rather than guessing filenames. Existing guest add-on
plans bind exact archive URI/name/size/SHA-256, acquired-index digests and the Native
CA digest. Downloads use Native Python TLS with `curl/8`, the same approved URLs,
bounded network retries and verified persistent cache. All archives must verify
before guest cache staging and `--no-download` APT apply. Missing guest CA tools
are explicitly in the package plan. No alternative repo/driver/version is used,
and TLS verification is not disabled. Additional cache-copy peak storage is
included. Fresh setup keeps its Native-CA path with the matching user-agent and
HTTPS time bounds; it is not claimed to use the add-on transport.

Private event logs now retain sanitized output; journals include failed stage,
reason, event-log location and timeout tail/kind. No-output deadlines bound silent
legacy network APT and offline package work separately. Fixture evidence covers
metadata/URI binding, cache/hash verification, retry bounds, no guest staging on
integrity failure, verified-fetch-before-offline-install order, missing CA being
planned before approval, redacted idle-timeout logs and double-cache peak space.

The 450-line report was incorrectly rendered through a selection menu. The new
view mode displays read-only line position, no checkboxes/selection counts, ignores
Space, and returns to the separate approval on Enter/Esc. This does not approve
individual dependency lines. Complete owner reinstall/ordinary-user/desktop
acceptance is still pending; no live package repair or installation was done here.
