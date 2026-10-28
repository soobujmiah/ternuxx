# =============================================================================
#  Ternuxx CLI help — Native Termux host with managed PRoot guests
# =============================================================================
. "$(dirname "${BASH_SOURCE[0]}")/core.sh"

_nt_help_raw() {
  local cmd="${1:-}"
  case "$cmd" in
    "") cat <<'EOF'
Ternuxx — Native Termux host and managed PRoot workstation management

First install:
  ./tx install                    Device info and guided setup
  tx install                      Same wizard after tx is installed

Add or configure later:
  tx install xfce|mate|plasma      Native desktop
  tx install proot [DISTRO] [DE]   Guest, desktop and optional software
  tx install gpu                  Device-aware Native / PRoot / both setup
  tx install debian|ubuntu        Guided managed guest setup

Open and inspect:
  tx tui / tx web / tx gui         Terminal / browser / GTK management
  tx start [--desktop DE]          Native desktop
  tx pgui [DE]                     Debian XFCE; auto :0 or nested :2
  tx pgui --alias ubuntu          Ubuntu GUI; --user NAME selects an existing account
  tx status / tx doctor            Current state / health checks
  tx audio status                  Sound status

More commands:
  Guests: tx db [--user NAME] (Debian), tx ub (Ubuntu); proot setup, pgui
  tx kali                         Reserved; provider not qualified yet
  tx app / tx mng                  Software and services
  tx ai                           CPU, Vulkan GPU and experimental HTP inference routes
  tx checkpoint / tx recovery      Recovery tools
  tx guides                       Interactive setup guide

Use tx help NAME for options, graphics checks, SSH, boot and recovery details.
Options: --json, --verbose, --quiet, --help
Changes show a preview and require confirmation. Remote access is disabled by default.
EOF
      ;;
    kali)
      printf '%s\n' 'tx kali is reserved for a future managed Kali provider; it is not available yet.' 'Use tx db / tx debian or tx ub / tx ubuntu for supported guest login.' ;;
    proot|db|ub|debian|ubuntu|pgui|virgl)
      cat <<'EOF'
Login aliases: tx db / tx debian; tx ub / tx ubuntu. No repeated LOGIN confirmation is needed.
When multiple ordinary guest accounts exist, Ternuxx asks which one to use; pass --user NAME to choose directly.
Kali is not qualified yet.
Managed PRoot guests use the Native Termux host. Run `tx proot setup catalog` to
list profiles and their accepted desktop routes. The short flows are `tx install debian`
and `tx install ubuntu`; each asks for the guest username and, in an attached
terminal, offers desktop and software choices (arrow keys/Space; XFCE default), then
shows the pinned plan and asks before applying it. You do not need to copy a
plan ID in the guided flow. Use explicit `preview`/`apply` only for review-only
or automated setup.
The lower-level equivalent is `tx proot setup fresh-preview --user NAME
--desktops xfce,lxqt`; Desktop IDs depend on the selected profile: Debian offers `xfce`, `lxqt`, `lxde`, `mate`, and `plasma`; Ubuntu currently offers `xfce`. Only selected desktops are installed; XFCE is the default in non-interactive preview flows.
The Debian catalog accepts XFCE, LXQt, LXDE, and MATE on standalone :0 and nested :2; Plasma is standalone :0 only. GNOME and Cinnamon are not selectable because no complete Ternuxx launch route is available. Review the exact
image/package plan, then apply it with
`tx proot setup fresh-install --yes --plan-id ID`.
Choose `--sudo-mode password` for hidden prompts, or `passwordless` for
NOPASSWD sudo inside the guest. Never put passwords in
command arguments. Fresh setup runs in an attached Native Termux terminal and
preserves an existing guest.
Managed Ubuntu and receipt-verified Ternuxx replay aliases can select their own guest with
`tx pgui start --mode nested --desktop xfce --alias ALIAS`; canonical `debian`
is the default when no alias is supplied.
`tx proot sessions list` inspects managed sessions;
`tx proot sessions recovery-inspect SESSION_ID` and `reconcile-preview`
inspect interrupted records. Apply reconciliation only when its exact preview
proves the original process exited. `tx proot stop-preview SESSION_ID` prepares
an exact stop plan; apply it with
`tx proot stop SESSION_ID --yes --plan-id ID`. `tx db [--user NAME]` opens an owned
interactive Debian login and asks for an account only when multiple ordinary accounts exist;
`tx pgui [--user NAME]` starts Debian XFCE by default and prompts for an account when needed;
`tx pgui DE` selects an installed desktop. Standalone `:0` opens Termux:X11 after readiness; nested Xephyr `:2` appears inside Native `:1` without opening another window. `tx pgui stop` closes managed standalone `:0` and nested `:2` sessions; Native `:1` remains running. `tx stop` closes a cooperative nested guest first, then stops Native `:1`.
`tx gui` starts the Native desktop when stopped, opens its Termux:X11 window automatically, then opens the GTK center.
`tx mng app launch --desktop-id APP.desktop --display :N` launches an
allowlisted Debian XFCE application through the shared guest service.
`tx proot shortcuts list` inspects launcher state; `preview add|remove APP_ID`
and `apply add|remove APP_ID --yes --plan-id ID` manage one Native launcher.
`shortcuts sync preview|apply` synchronizes eligible Debian applications and managed-guest desktop launchers, and
`shortcuts rollback list|preview|apply` reviews and restores a prior sync.
For a guest with the exact recognized legacy Turnip ICD, use
`tx proot setup icd-migrate-preview --alias debian`, review the file move and
backup, then apply with `icd-migrate --alias debian --yes --plan-id ID`.
Rollback uses `icd-rollback-preview --operation-id MIGRATION_ID` followed by
`icd-rollback --operation-id MIGRATION_ID --yes --plan-id ID`.
Every mutation requires its exact preview plan.
EOF
      ;;
    terminal)
      cat <<'EOF'
tx terminal status — Inspect the Native terminal-broker service
tx terminal service preview-install — Review the exact Runit service registration
tx terminal service install --yes --plan-id ID — Register and start the broker
tx terminal start — Preview, confirm, and attach to a fixed Debian login
tx terminal attach SESSION_ID — Attach to a verified broker session
tx terminal close SESSION_ID — Preview and confirm stopping one owned session
tx terminal service socket preview|recover — Inspect or recover one stale socket
The broker never starts a guest automatically. Guest session start needs a local
TTY; service install needs Termux Runit and writes only the fixed broker service.
EOF
      ;;
    start) cat <<'EOF'
tx start — Start the Native Termux:X11/XFCE desktop
The command starts only the verified Native desktop process group, records
private session state, and opens its Termux:X11 window automatically.
Run `tx status` to inspect the saved session and `tx stop` to stop it.
EOF
      ;;
    stop) cat <<'EOF'
tx stop — Stop the Native desktop session
If a verified nested PRoot desktop is using Native :1, tx stop closes that exact
guest's isolated process group first, then stops the recorded Native session.
Unknown or changed processes are preserved. State and logs remain for diagnosis.
EOF
      ;;
    restart) cat <<'EOF'
tx restart — Stop, then start the Native desktop
This changes process and session state. See `tx stop --help` and
`tx start --help` for lifecycle details.
EOF
      ;;
    status) cat <<'EOF'
tx status — Inspect the Native desktop session
Reads saved state and verifies recorded process identities. It does not start
or stop processes. GUI visibility is reported as unknown unless observed.
EOF
      ;;
    install) cat <<'EOF'
tx install debian [--user NAME] — Guided Debian Trixie guest setup
Guest setup: choose DEs, then optional apps; base/clean keeps graphics/CPU rendering/audio.
tx install ubuntu [--user NAME] — Guided Ubuntu Noble guest setup
tx install debian preview --user NAME — Review-only; no guest changes
tx proot setup catalog — List installable guest profiles and desktop routes
tx install ubuntu preview --user NAME — Review-only; no guest changes
tx install gpu — Device-aware Native/PRoot/both runtime and backend selector
All guided profiles include sound and graphics tools; desktops remain optional.
tx install xfce|mate|plasma — Add a supported Native desktop
 tx install proot [debian|ubuntu] [DE] — Create guest or add DE/apps to existing guest
 tx install — Device info, then Minimal / Native Full / Native Full + PRoot
tx install interactive — Choose, preview, and confirm a Native workstation profile in one session
Use arrow keys + Space + Enter for profile, DE, app, distro and confirmation choices.
Minimal includes CLI/TUI/Web, terminal/build tools and the PRoot CLI provider; Full adds GUI management/audio/graphics.
tx install preview [--profile NAME] [--components GROUPS] — Review exact package transaction
tx install update preview — Review Native Ternuxx core updates
tx install apply [--profile NAME] --yes --plan-id ID — Apply the exact saved plan
Profiles: minimal-native, full-native, graphical, developer, native-proot-provider, custom.
The guided Native flow previews the transaction and asks before installing; after
it, you can also set up the optional managed Debian or Ubuntu guest. `tx install debian` or `tx install ubuntu`
shows its pinned target and confirms the same plan in one terminal flow. Plan-ID
commands are for explicit review and automation.
Custom groups: desktop,audio,proot,graphics,developer,mate,plasma,terminal,gui,
sound-controls,nested,guest-display,browser,music,images,pdf,editor,archive,video. All profiles use the same
repository and dependency checks. The PRoot-provider profile installs the runtime only.
If APT fails, some packages may have changed; create a fresh preview before retrying.
EOF
      ;;
    checkpoint) cat <<'EOF'
tx checkpoint prepare --test-id ID — Preview, then type CREATE CHECKPOINT
tx checkpoint verify --checkpoint-id ID — Preview, then type VERIFY CHECKPOINT
JSON mode shows the plan only. Automation applies with --yes --plan-id from the
exact current preview. This records evidence only; it never reboots or resumes.
Reboot qualification commands remain owner-operated through `tx reboot`.
EOF
      ;;
    ssh) cat <<'EOF'
tx ssh inspect — Inspect Native SSH state
tx ssh deploy — Preview first-time loopback 8023 config + Runit setup, then apply exact plan
tx ssh start|stop|restart — Preview, then confirm with --yes --plan-id ID
SSH keys use the managed service’s validated AuthorizedKeysFile; inspect the preview impact.
EOF
      ;;
    remote) cat <<'EOF'
tx remote access preview — Inspect optional remote-access policy
Remote access is disabled by default. Preview does not persist settings, contact
a network, start a service, or enable public ingress.
EOF
      ;;
    graphics|gpu) cat <<'EOF'
Graphics setup and management

Commands:
  tx install gpu
      Open the device-aware installer. Native and PRoot are selected by default.
      CPU rendering stays selected; compatible accelerated providers are
      preselected after device probes. Use Space to change selections.
      Package/runtime changes show a plan and require confirmation.

  tx mng graphics status native
      Show the Native backend and OpenGL/GLES/Vulkan probe results.
  tx mng graphics status proot
      Show the saved PRoot backend and its default/selected source.
  tx mng graphics verify native {opengl|gles|vulkan} [:N]
      Run a bounded Native graphics probe. Display defaults to :1.
  tx mng graphics select native {system|termux-zink|kgsl-freedreno}
      Save the Native backend for future starts; running desktops are unchanged.
  tx mng graphics select proot {cpu|zink}
      Save the PRoot backend for future starts. Install runtimes with
      `tx install gpu` first.

  tx tui | tx web | tx gui
      Open a management client. Choose GPU setup to install runtimes or change
      the saved Native/PRoot backend through the shared installer.

Provider notes:
  Native Zink requires successful Vulkan device enumeration by the installed
  Termux Freedreno ICD. The pinned KGSL Mesa candidate is experimental and
  Adreno 825-specific. PRoot Zink/Turnip requires accessible KGSL. VirGL has
  a verifier but no managed server installation/lifecycle, so it is not an
  install choice. Detection does not prove accelerated rendering.
EOF
      ;;
    web) cat <<'EOF'
tx web — Open the authenticated Native Termux management Web UI
The service binds to loopback and uses the shared management API for Native
desktop, graphics, SSH, Cron, and timezone operations. Browser choices are
Android or an installed Native Termux browser. Press Ctrl-C to stop the service.
EOF
      ;;
    management|mng) cat <<'EOF'
Ternuxx management commands

  tx mng center [install]
      Open or install the Native GTK app.
  tx mng catalog list
      Browse supported Native resources.
  tx mng logs list|read ID
      Read bounded Ternuxx logs.
  tx mng cron ...
      Manage the Native scheduler and jobs.
  tx mng timezone ...
      Inspect or set the system timezone.
  tx mng http serve
      Run the authenticated loopback API.

Graphics commands:
  tx mng graphics status {native|proot}
  tx mng graphics verify native {opengl|gles|vulkan} [:N]
  tx mng graphics select native {system|termux-zink|kgsl-freedreno}
  tx mng graphics select proot {cpu|zink}

Use `tx install gpu` to install or change providers. The same installer is
available from `tx tui`, `tx web`, and `tx gui`. Zink/Turnip choices depend on
device probes. VirGL is not installable until its managed server lifecycle is
implemented.
EOF
      ;;
    tui) cat <<'EOF'
tx tui — Interactive Native Termux management
Use arrows or the displayed keys to browse resources and review supported
Native actions. Mutating operations use shared preview/confirmation rules.
EOF
      ;;
    app) cat <<'EOF'
tx app list — List the curated Native Termux apps and current package state
tx app preview APP_ID install|update|remove — Simulate the exact official package transaction
tx app apply APP_ID ACTION --plan-id ID [--confirm ACTION] — Apply a saved plan
tx app run directory-tree HOME_PATH - Bounded read-only HOME file/directory handoff
Only htop, tmux, and tree are selectable. Apply requires a current plan and
exact typed INSTALL, UPDATE, or REMOVE confirmation. No autoremove is used.
File handoff accepts only regular files/directories below HOME; file contents are not read.
EOF
      ;;
    ai) cat <<'EOF'
tx ai status — Inspect llama.cpp runtime and pinned local model state
tx ai devices — List llama.cpp Vulkan inference devices
tx ai npu status — Check pinned HTP0 runtime and SM8735 availability
tx ai npu runtime preview|apply — Preview or install the pinned experimental NPU runtime
tx ai runtime preview [cpu|vulkan|opencl] — Run a read-only Termux apt simulation
tx ai setup — Interactive runtime preflight, model preview, and optional CPU run
tx ai model preview — Show the exact 429 MB download, checksum, license, and target
tx ai model install — Preview first; type DOWNLOAD to install the pinned model
tx ai model remove-preview / tx ai model remove — Preview, then type REMOVE
tx ai run [--backend cpu|vulkan|npu] [--device ID] [--max-tokens N] — Bounded local inference
The experimental NPU path is SM8735-only, requires full HTP0 offload, and never silently falls back to CPU.
Review Termux-owned llama.cpp packages with `tx ai runtime preview [cpu|vulkan|opencl]`; this runs apt simulation only. Ternuxx never installs packages here.
EOF
      ;;
    doctor) cat <<'EOF'
tx doctor [--graphics] — Run read-only Native Termux health checks
Graphics probes are optional and report observed evidence without claiming
workload acceleration from library or device-node presence alone.
EOF
      ;;
    *) nt_fail "No help available for '$cmd'. Run 'tx help' for Native Termux usage."; return 1 ;;
  esac
}

nt_cmd_help() { nt_help "${1:-}"; }

# Color is used only for an interactive capable terminal. Redirected help,
# scripts, and terminals opting out with NO_COLOR receive plain text.
nt_help() {
  local body line first=1
  body="$(_nt_help_raw "$1")" || return $?
  if [ ! -t 1 ] || [ -n "${NO_COLOR:-}" ] || [ "${TERM:-dumb}" = dumb ]; then
    printf '%s\n' "$body"
    return 0
  fi
  while IFS= read -r line; do
    if [ "$first" -eq 1 ] && [[ "$line" == Ternuxx* ]]; then
      printf '\033[1;36m╭────────────────────────────────────────────────────────────────────╮\033[0m\n'
      printf '\033[1;36m│\033[0m \033[1;97m%-66s\033[0m \033[1;36m│\033[0m\n' "$line"
      printf '\033[1;36m╰────────────────────────────────────────────────────────────────────╯\033[0m\n'
      first=0
      continue
    fi
    first=0
    case "$line" in
      Usage:*|Options:*|Commands:*|Examples:*|Safety:*|Quick\ launch:*|Short\ forms:*)
        printf '\033[1;35m%s\033[0m\n' "$line" ;;
      "  "*)
        printf '  \033[1;32m%s\033[0m\n' "${line#  }" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done <<< "$body"
}
