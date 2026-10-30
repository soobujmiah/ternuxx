# =============================================================================
#  Ternuxx CLI help — Native Termux host with managed PRoot guests
# =============================================================================
. "$(dirname "${BASH_SOURCE[0]}")/core.sh"

_nt_help_raw() {
  local cmd="${1:-}"
  case "$cmd" in
    "") cat <<'EOF'
Ternuxx — Complete Native + PRoot Command Reference
COMMAND	DESCRIPTION
Detailed options: `tx help TOPIC`

SETUP AND SOFTWARE
  tx install [interactive]	Guided workstation setup
  tx install proot [DISTRO] [DE]	Install/configure a Debian or Ubuntu guest
  tx install gpu	Preview/install compatible graphics and audio runtimes
  tx install xfce|mate|plasma	Add a supported Native desktop
  tx install preview [options]	Preview exact Native package plan
  tx install apply [options]	Apply a reviewed Native package plan
  tx desktop list	List Native desktops and install state
  tx app list|catalog	List curated Native applications
  tx app preview APP_ID ACTION	Preview install, update, or remove
  tx app apply APP_ID ACTION [options]	Apply a reviewed app package plan
  tx app run directory-tree HOME_PATH	Read-only HOME path handoff
  tx app -- DEBIAN_APP [options]	Launch fixed guest menu applications

DESKTOP AND GUI
  tx start [--desktop DE] [--display :N]	Start Native Termux:X11 desktop
  tx stop	Stop owned Native desktop session
  tx restart [--desktop DE]	Restart Native desktop session
  tx status	Inspect Native desktop/session state
  tx gui	Open GTK center; start desktop first if needed
  tx gui start|stop|restart|status	Native desktop lifecycle shortcuts
  tx gui monitor ACTION [options]	Inspect/configure GUI monitor
  tx tui	Open terminal management client
  tx web [options]	Run authenticated loopback Web management

GRAPHICS AND AUDIO
  tx mng graphics status native	Inspect Native graphics selection
  tx mng graphics status proot	Inspect PRoot graphics selection
  tx mng graphics verify native API [:N]	Probe Native OpenGL/GLES/Vulkan
  tx mng graphics select proot cpu	Select PRoot CPU/Mesa fallback
  tx mng graphics select proot zink	Select PRoot Zink/Turnip backend
  tx mng graphics select native system	Select Native system graphics
  tx mng graphics select native termux-zink	Select Termux Mesa Zink/Freedreno
  tx mng graphics select native kgsl-freedreno	Select experimental KGSL candidate
  tx install gpu	Install compatible graphics/audio runtimes
  tx audio [status|start|stop|restart]	Inspect/manage Native PulseAudio
  tx graphics native status|disable	Inspect/select Native system fallback
  tx graphics native enable --prefix PATH	Select qualified KGSL candidate

PRoot GUESTS
  tx proot [status|profiles|sessions|setup ...]	Inspect/configure guest and sessions
  tx mng proot ...	Compatibility alias for PRoot management
  tx pgui [DE] [--alias DISTRO] [--user NAME]	Start managed guest desktop
  tx pgui stop	Stop managed PRoot GUI sessions
  tx db [--user NAME]	Open Debian in current terminal
  tx ub [--user NAME]	Open Ubuntu in current terminal
  tx debian [--user NAME]	Alias for Debian login
  tx ubuntu [--user NAME]	Alias for Ubuntu login
  tx kali	Reserved; managed Kali provider is not qualified

MANAGEMENT CENTER — `tx mng` (alias `tx mg`)
  tx mng center [install]	Open/install GTK management center
  tx mng catalog list [filters]	Browse managed resources/capabilities
  tx mng app launch APP_ID [options]	Launch an allowlisted guest app
  tx mng logs list|read SOURCE_ID	Inspect bounded Ternuxx logs
  tx mng cron status|start|stop	Inspect/control Native scheduler
  tx mng cron jobs ACTION [options]	Manage/validate allowlisted jobs
  tx mng cron executions list|show	Inspect scheduled job runs
  tx mng timezone status|list|set NAME	Inspect/set system timezone
  tx mng boot cron ACTION	Manage optional Cron boot helper
  tx mng boot helpers ACTION ...	Inspect/deploy/rollback owned boot helpers
  tx mng hermes status	Inspect Hermes integration
  tx mng doctor [--graphics]	Run management health report
  tx mng web [options]	Open authenticated Web interface
  tx mng http serve [--port PORT]	Serve loopback management API

AI INFERENCE
  tx ai status [--model MODEL_ID]|devices	Inspect a selected model or Vulkan devices
  tx ai runtime preview [cpu|vulkan|opencl]	Read-only package simulation
  tx ai setup	Guided local model/runtime preflight
  tx ai model ACTION [options]	Preview/install/remove pinned model
  tx ai run [--model MODEL_ID] [--backend auto|cpu|vulkan|npu]	Run local inference (auto prefers HTP0, then Vulkan, then CPU)
  tx ai npu status	Inspect experimental HTP availability
  tx ai npu runtime preview|apply	Review/install pinned NPU runtime

SYSTEM, RECOVERY, AND ACCESS
  tx check	Run Native prerequisite checks
  tx doctor [--graphics]	Run detailed read-only health report
  tx info	Show device, packages, commands, and renderer
  tx ssh ACTION [options]	Manage SSH; key actions: `tx help ssh`
  tx remote access preview	Read-only remote-access policy preview
  tx terminal ACTION [options]	Manage guest terminal broker/sessions
  tx boot ACTION [options]	Inspect/configure startup integration
  tx wakelock ACTION [options]	Inspect/manage Android Wake Locks
  tx checkpoint prepare|verify [options]	Record continuity evidence; no reboot
  tx reboot ACTION [options]	Inspect reboot test; does not reboot device
  tx backup create|list|inspect [options]	Preview/manage private backups
  tx restore --preview BACKUP_ID	Review backup restore plan
  tx restore BACKUP_ID --yes --plan-id ID	Apply exact restore plan
  tx recovery ACTION [options]	Inspect/reconcile recovery state
  tx guides	Open interactive setup/documentation guide

HELP, ALIASES, AND OPTIONS
  tx help [TOPIC] | tx TOPIC --help	Show this index or topic help
  tx --version	Show Ternuxx version and repository
  Aliases: up=start, dn=stop, rs=restart, st=status, doc=doctor, inf=info
  Aliases: mg=mng, in=install, ck=check, cp=checkpoint, ra=remote, rb=reboot
  Aliases: bt=boot, wl=wakelock, bk=backup, rc=recovery, rt=restore, g=guides
  Aliases: h=help, db=debian, ub=ubuntu; `tx management` is deprecated
  Global flags: --json, --verbose, --quiet, --help

Package/service changes use previews and confirmation where required. Guest
additions preserve existing root filesystems. GPU detection alone does not prove
accelerated rendering. See `tx help TOPIC` for full syntax and safety details.
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
list profiles and their accepted desktop routes. Use `tx install proot [DISTRO] [DE]`
for the guided flow; it asks for a distro when omitted, then offers desktop/software
choices (arrows/Space) and reviews the combined guest plan before apply. You do not
need to copy a plan ID in this flow. For explicit fresh-rootfs review and automation,
use `tx proot setup fresh-preview` and `tx proot setup fresh-install`.
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
tx install — Device info, then Minimal / Native Full / Native Full + PRoot
tx install interactive — Choose, preview, and confirm a Native workstation profile in one session
Use arrows + Space + Enter for profile, DE, app, distro and confirmation choices.
tx install proot [debian|ubuntu] [DE] — Guided managed guest setup/additions
tx install gpu — Device-aware Native/PRoot graphics and sound runtime setup
tx install xfce|mate|plasma — Add a supported Native desktop
Native package plan:
  tx install preview [--profile NAME] [--components GROUPS]
  tx install apply [--profile NAME] --yes --plan-id ID — Apply the exact saved plan
Managed guest fresh-rootfs review/apply:
  tx proot setup fresh-preview --user NAME [--desktops IDS]
  tx proot setup fresh-install --yes --plan-id ID
  tx proot setup catalog — List profiles and accepted desktop routes
`tx install debian` and `tx install ubuntu` are retired; use `tx install proot`
with a distro name. Existing guests are preserved and receive reviewed additions.
Profiles: minimal-native, full-native, graphical, developer, native-proot-provider, custom.
All profiles use shared dependency/repository checks. The PRoot-provider preset
installs the runtime only. If APT fails, create a fresh preview before retrying.
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
tx ssh deploy — Preview first-time loopback 8023 configuration and Runit setup,
  then apply the exact reviewed plan.
tx ssh start|stop|restart — Preview, then confirm with --yes --plan-id ID
SSH keys use the managed service's validated AuthorizedKeysFile.
Inspect the preview impact before applying key changes.
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

Install and change providers:
  tx install gpu
      Open the device-aware installer. Native and PRoot are selected by default.
      CPU rendering stays selected; compatible accelerated providers are
      preselected after device probes. Use Space to change selections.
      Package/runtime changes show a plan and require confirmation.

  tx mng graphics select proot cpu
      Select the PRoot CPU/Mesa fallback for future guest launches.
  tx mng graphics select proot zink
      Select PRoot Zink/Turnip for future guest launches; install its runtime
      with `tx install gpu` first.
  tx mng graphics select native system
      Select the Native system graphics stack / CPU fallback.
  tx mng graphics select native termux-zink
      Select Termux Mesa Zink + Freedreno for future Native desktop starts.
  tx mng graphics select native kgsl-freedreno
      Select the experimental device-specific KGSL candidate for future starts.
      This is not the Termux Vulkan ICD; Vulkan compatibility is not implied.

Inspect and verify:
  tx mng graphics status native
      Show the Native backend and OpenGL/GLES/Vulkan probe results.
  tx mng graphics status proot
      Show the saved PRoot backend and its default/selected source.
  tx mng graphics verify native {opengl|gles|vulkan} [:N]
      Run a bounded Native graphics probe. Display defaults to :1.

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
  tx mng graphics status native|proot
      Show the saved backend and runtime state for Native or PRoot.
  tx mng graphics verify native {opengl|gles|vulkan} [:N]
      Run a bounded Native API probe; the display defaults to :1.
  tx mng graphics select proot cpu|zink
      Choose CPU/Mesa fallback or Zink/Turnip for future PRoot launches.
  tx mng graphics select native system|termux-zink|kgsl-freedreno
      Choose the Native backend for future desktop starts.

Run `tx install gpu` to install missing runtimes and choose compatible
providers. The same installer is available from `tx tui`, `tx web`, and `tx gui`.
Installing a runtime and selecting it are separate steps; selectors only change
the saved backend preference. Existing desktop sessions are not switched.
Zink/Turnip availability depends on device probes. VirGL is not installable
until its managed server lifecycle is implemented.
EOF
      ;;
    audio) cat <<'EOF'
tx audio [status|start|stop|restart] — Manage Native PulseAudio
status inspects readiness; start/stop/restart control the Native user service.
Audio is managed separately from Native and PRoot desktop lifecycle commands.
EOF
      ;;
    gui) cat <<'EOF'
tx gui — Start Native desktop if needed, then open the GTK management center
tx gui start|stop|restart|status — Native desktop lifecycle shortcuts
tx gui monitor status|enable|disable|configure — Inspect/configure GUI monitor
  Android X11 Activity behavior can be configured separately.
Monitor configure accepts --enabled on|off, --activity-launch on|off,
--focus-check on|off, and --interval VALUE UNIT.
EOF
      ;;
    boot) cat <<'EOF'
tx boot status — Inspect startup policy and helper state
tx boot profile status|preview <cli-only|native>
  Inspect the startup profile or preview a profile change.
tx boot enable --profile <cli-only|native> [--yes] — Enable the selected profile
tx boot disable [--yes] — Disable startup integration
tx boot gui <on|off> [--yes] — Compatibility form for Native GUI startup policy
Preview before applying optional startup changes.
EOF
      ;;
    backup) cat <<'EOF'
tx backup create --name NAME [--yes --plan-id ID] — Preview/create a backup
tx backup list — List available backups
tx backup inspect BACKUP_ID — Inspect one backup
Creation applies only the exact current preview plan.
EOF
      ;;
    restore) cat <<'EOF'
tx restore --preview BACKUP_ID — Preview a backup restore
tx restore BACKUP_ID --yes --plan-id ID — Apply the exact restore plan
Review the preview before applying; existing data may be changed by restore.
EOF
      ;;
    recovery) cat <<'EOF'
tx recovery status — Inspect recovery journal state
tx recovery inspect OPERATION_ID — Inspect one recorded operation
tx recovery resolve OPERATION_ID [--yes --plan-id ID]
  Preview/reconcile supported recovery state.
tx recovery rollback OPERATION_ID [--yes --plan-id ID]
  Preview/rollback a recorded operation.
Mutations require the exact current preview plan.
EOF
      ;;
    reboot) cat <<'EOF'
tx reboot status [TEST_ID] — Inspect continuity/reboot test records
tx reboot prepare --test-id ID [--baseline-json JSON] [--yes --plan-id ID]
tx reboot verify TEST_ID [--yes --plan-id ID]
tx reboot resume-info TEST_ID — Read post-reboot resume information
Prepare and verify create evidence records; they do not reboot the device.
EOF
      ;;
    wakelock) cat <<'EOF'
tx wakelock status — Inspect Wake Lock state
tx wakelock acquire OWNER [--persistent] — Acquire a named Wake Lock
tx wakelock release OWNER — Release a named Wake Lock
tx wakelock ssh-policy status|preview --enabled|--disabled
tx wakelock ssh-policy apply --enabled|--disabled --yes --plan-id ID
Inspect the exact SSH policy preview before applying it.
EOF
      ;;
    ssh) cat <<'EOF'
tx ssh inspect — Inspect Native SSH service and keys
tx ssh deploy — Preview/apply managed SSH service setup
tx ssh start|stop|restart — Preview and control Native SSH lifecycle
tx ssh keys-list | rollback-list | rollback-preview ID
tx ssh rollback-apply ID --yes --plan-id PLAN_ID
tx ssh enroll-preview|enroll | revoke-preview|revoke — Manage authorized client keys
tx ssh client-key-preview|client-key-create — Create a client key with preview/confirmation
tx ssh autostart-status|autostart-preview|autostart-apply — Manage SSH autostart
Use --help on the command and inspect plans before applying changes.
EOF
      ;;
    tui) cat <<'EOF'
tx tui — Interactive Native Termux management
Use arrows or the displayed keys to browse resources and review supported
Native actions. Mutating operations use shared preview/confirmation rules.
EOF
      ;;
    desktop) cat <<'EOF'
tx desktop list — List Native Termux desktop environments and install state
Start a selected installed desktop with `tx start --desktop ID`.
EOF
      ;;
    info) cat <<'EOF'
tx info — Show Android device, Termux paths/version, desktop packages,
  available commands, and renderer.
This is an informational snapshot; it does not install or change packages.
EOF
      ;;
    check) cat <<'EOF'
tx check — Run Native Termux prerequisite checks
tx doctor [--graphics] — Run the detailed read-only health report
Checks report observed prerequisites and probes.
They do not install missing items.
EOF
      ;;
    guides) cat <<'EOF'
tx guides — Open the interactive Native Termux/PRoot setup guide
The menu links to installer, health, desktop, AI, and guest workflows,
plus TUI, Web, and GTK management.
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
tx ai model preview — Show the exact pinned model download size, checksum, license, and target
tx ai model install — Preview first; type DOWNLOAD to install the pinned model
tx ai model remove-preview / tx ai model remove — Preview, then type REMOVE
tx ai run [--model MODEL_ID] [--backend auto|cpu|vulkan|npu] [--device ID] [--max-tokens N] — Bounded local inference; auto prefers HTP0, then Vulkan, then CPU
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
  local body line first=1 tab=$'\t' colored=0 command_text description
  local command_width=45 description_width padding chunk remainder
  body="$(_nt_help_raw "$1")" || return $?
  if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != dumb ]; then
    colored=1
  fi
  while IFS= read -r line; do
    if [[ "$line" == *"$tab"* ]]; then
      command_text="${line%%"$tab"*}"
      description="${line#*"$tab"}"
      command_text="${command_text#  }"
      description_width=$((80 - 2 - command_width - 1))
      padding="$(printf '%*s' "$((2 + command_width + 1))" '')"
      while [ -n "$description" ]; do
        chunk="${description:0:description_width}"
        if [ "${#description}" -gt "$description_width" ] && [[ "$chunk" == *" "* ]]; then
          chunk="${chunk% *}"
        fi
        [ -n "$chunk" ] || chunk="${description:0:description_width}"
        remainder="${description:${#chunk}}"
        description="${remainder# }"
        if [ -n "$command_text" ]; then
          if [ "$colored" -eq 1 ]; then
            printf '  \033[1;32m%-*s\033[0m %s\n' "$command_width" "$command_text" "$chunk"
          else
            printf '  %-*s %s\n' "$command_width" "$command_text" "$chunk"
          fi
          command_text=""
        else
          printf '%s%s\n' "$padding" "$chunk"
        fi
      done
      continue
    fi
    if [ "$colored" -eq 1 ] && [ "$first" -eq 1 ] && [[ "$line" == Ternuxx* ]]; then
      printf '\033[1;36m╭────────────────────────────────────────────────────────────────────╮\033[0m\n'
      printf '\033[1;36m│\033[0m \033[1;97m%-66s\033[0m \033[1;36m│\033[0m\n' "$line"
      printf '\033[1;36m╰────────────────────────────────────────────────────────────────────╯\033[0m\n'
      first=0
      continue
    fi
    first=0
    if [ "$colored" -eq 1 ]; then
      case "$line" in
        Usage:*|Options:*|Commands:*|Examples:*|Safety:*|Quick\ launch:*|Short\ forms:*)
          printf '\033[1;35m%s\033[0m\n' "$line" ;;
        "  "*) printf '  \033[1;32m%s\033[0m\n' "${line#  }" ;;
        *) printf '%s\n' "$line" ;;
      esac
    else
      printf '%s\n' "$line"
    fi
  done <<< "$body"
}
