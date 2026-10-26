# Installer keyboard and branding follow-up — 2026-10-26

Evidence classes: owner-reported failure screenshot; Native Termux read-only package
metadata; isolated PTY/source tests; upstream documentation. No live installation,
service control, existing guest mutation, Android settings or owner-terminal reset.

## Report and implementation

The owner reported that arrow keys printed literal escape text at the existing
Debian add-on confirmation. Review found per-byte temporary input modes, a 150 ms
escape timeout, and a concurrent cursor-writing heartbeat. The revised selector
holds noncanonical/non-echo mode for its complete lifetime, reads `/dev/tty`, parses
bounded CSI/SS3 keys with 400 ms inter-byte tolerance, and restores termios on normal
exit, Esc, SIGINT and termination. EOF exits; timeout only refreshes the UI.

The background timer is removed. Selector idle refresh and package/build output
relay own their painting. The relay shows partial prompts, propagates the worker's
nonzero exit status, and updates elapsed time without another cursor writer. APT's
guided apply disables its nested dpkg PTY/fancy progress. Resize rebuilds the frame
and scroll margins. Below 22 rows/32 columns, choices pause; already running commands
continue, and output during an undersized interval may not be displayed. No process
is stopped to resize the UI.

Branding uses centered green-pulsing `TERNUXX`, centered `Workstation In Your Hand`,
aligned/green system labels, contextual dividers and centered copyright. The initial
choice view has no installation-log heading. Lines reserve the last terminal column
to avoid autowrap. Long lists expose position/count and Home/End/PageUp/PageDown.

## Catalog/source boundaries

The Native optional catalog has 51 entries and the guest catalog 49. These include
AI recipes/prerequisites, not hidden external agent installation. Native app
candidates and their main/X11 origins were checked read-only against the already
configured signed APT index; no refresh or device mutation was performed. The exact
plan resolver still rejects missing/changed/nonofficial candidates. Blender was
absent from the checked Native index and is offered through guest APT instead.

AI commands and current upstream sources are maintained in [AI-TOOLS.md](../AI-TOOLS.md).
The owner supplied the same official Hermes Termux guide that was reviewed; it
lists signed stable/canary channels and currently warns the package is broken.
Native canary remains an experimental guide, with no key/repository auto-enrollment.
Claude guidance is guest-only. Owner-used community Codex `@next` is distinguished
from upstream OpenAI Codex, and a mutable channel is not described as reproducible.

## Verification

Five real PTY tests cover delayed arrow bytes after idle, consecutive menus with
redirected stdin, long-list paging/resizing/multiselect, Esc/Ctrl+C mode restoration,
and the exact existing-Debian confirmation inside the fixed frame. The frame test
also shrinks/re-expands the terminal and checks command-relay partial prompts,
worker failure propagation and a single alternate-screen lifecycle. Existing wizard,
package-plan, guest fresh/add-on and software tests cover resolver integration.
Documentation inventory/link and CLI-help checks are run before handoff; complete
CI evidence is recorded in generated repository status.

This does not establish that the owner's exact physical keyboard/display path is
fixed, or that every newly selected graphics/network/AI application runs correctly.
Those remain live acceptance checks. The assistant did not stop the reported live
installation; the owner can cancel it with Ctrl+C, update the clean checkout and
run `./tx install` again. `stty sane` is a manual recovery command if the owner shell
was left with broken echo/input after interruption.
