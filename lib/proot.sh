#!/data/data/com.termux/files/usr/bin/bash
# Read-only inventory of native Termux PRoot distributions.

_nt_proot_call() {
  local args=(--operation proot.status)
  [ "$TERNUXX_JSON" = "1" ] && args+=(--json)
  python3 "$_TN_LIB_DIR/management_service.py" "${args[@]}"
}

_nt_proot_operation() {
  local operation="$1"
  shift
  nt_require_termux || return $?
  nt_require_command python3 || return $?
  local -a args=(--operation "$operation")
  [ "${TERNUXX_JSON:-0}" = "1" ] && args+=(--json)
  python3 "$_TN_LIB_DIR/management_service.py" "${args[@]}" "$@"
}

_nt_proot_gui() {
  local script="$_TN_LIB_DIR/../scripts/proot-gui0.sh"
  [ -x "$script" ] || { nt_fail "Ternuxx PRoot GUI script is unavailable: $script"; return 1; }
  "$BASH" "$script" "$@"
}

nt_cmd_pgui() {
  if [ "$#" -eq 0 ]; then
    set -- start
  elif [[ "$1" = --mode || "$1" = --desktop || "$1" = --alias || "$1" = --user ]]; then
    set -- start "$@"
  fi
  case "${1:-}" in
    xfce|xfce4|lxqt|lxde|mate|plasma|gnome|cinnamon)
      local desktop="${1/xfce4/xfce}"; shift
      set -- start --desktop "$desktop" "$@" ;;
  esac
  _nt_proot_gui "$@"
}


# Compatibility entry used by existing Native XFCE menu items. These are
# fixed desktop commands mapped to the shared, provider-aware app launcher.
nt_cmd_debian_menu_app() {
  [ "$#" -ge 2 ] && [ "$1" = -- ] || {
    nt_fail "Usage: tx app -- ALLOWLISTED_DEBIAN_APP [fixed options]"
    return 2
  }
  shift
  local app_id="" program="$1"
  case "$program" in
    thunar)
      if [ "$#" -eq 1 ]; then app_id=files
      elif [ "$#" -eq 2 ] && [ "$2" = --bulk-rename ]; then app_id=thunar-bulk-rename
      fi
      ;;
    xfce4-terminal)
      if [ "$#" -eq 1 ]; then app_id=terminal
      elif [ "$#" -eq 2 ] && [ "$2" = --preferences ]; then app_id=xfce4-terminal-settings
      fi
      ;;
    firefox-esr|/usr/lib/firefox-esr/firefox-esr) [ "$#" -eq 1 ] && app_id=firefox ;;
    /usr/bin/vlc)
      if [ "$#" -eq 1 ] || { [ "$#" -eq 2 ] && [ "$2" = --started-from-file ]; }; then app_id=vlc; fi
      ;;
    blender|pavucontrol|system-config-printer|thunar-settings|thunar-volman-settings|xarchiver|xfce4-appfinder)
      [ "$#" -eq 1 ] && app_id="$program" ;;
    --help|-h)
      printf '%s\n' "Usage: tx app -- ALLOWLISTED_DEBIAN_APP [fixed options]"         "Compatibility route for existing Native XFCE PRoot menu entries."
      return 0
      ;;
  esac
  [ -n "$app_id" ] || {
    nt_fail "Unsupported or malformed Debian menu app; no guest command was run."
    return 2
  }
  nt_require_termux || return 1
  nt_require_command python3 || return 1
  local -a launch_args=(--operation proot.app.launch --app-id "$app_id")
  [ "$TERNUXX_JSON" = "1" ] && launch_args+=(--json)
  python3 "$_TN_LIB_DIR/management_service.py" "${launch_args[@]}"
}

_nt_proot_verify() {
  local distro="$1" guest_user="$2" user_source="$3" display="$4" backend="$5"
  local args=(--operation proot.guest.verify --distro "$distro" --display "$display" --backend "$backend")
  if [ "$user_source" = "rootfs" ]; then
    args+=(--guest-user-from rootfs)
  else
    args+=(--guest-user "$guest_user")
  fi
  [ "$TERNUXX_JSON" = "1" ] && args+=(--json)
  python3 "$_TN_LIB_DIR/management_service.py" "${args[@]}"
}

_nt_guest_login() {
  local distro="$1"; shift
  if [ "${1:-}" = --help ] || [ "${1:-}" = -h ]; then
    printf 'Open the installed %s guest through the shared owned session service.\nPreview then type LOGIN. No GUI or service starts.\n' "$distro"
    return 0
  fi
  [ "$#" = 0 ] || { nt_fail "Guest login accepts no arguments; use tx proot setup for management."; return 2; }
  [ -t 0 ] && [ -t 1 ] || { nt_fail "Guest login needs an attached terminal."; return 2; }
  nt_require_termux || return 1
  nt_require_command python3 || return 1
  local service="$_TN_LIB_DIR/management_service.py" preview plan_id answer login_user
  preview="$(python3 "$service" --operation proot.start.preview --guest-profile debian-interactive --alias "$distro" --json)" || { printf '%s\n' "$preview"; return 1; }
  plan_id="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("plan_id", "") if d.get("ok") else "")' <<<"$preview")"
  [ -n "$plan_id" ] || { printf '%s\n' "$preview"; return 1; }
  login_user="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["user"])' <<<"$preview")" || return 1
  nt_info "Guest login: $distro | Account: $login_user | Foreground terminal; no GUI/service start."
  printf 'Type LOGIN to enter this exact %s session: ' "$distro"
  IFS= read -r answer || return 1
  [ "$answer" = LOGIN ] || { nt_warn 'Cancelled; no guest session started.'; return 2; }
  python3 "$service" --operation proot.start --guest-profile debian-interactive --alias "$distro" --yes --plan-id "$plan_id" --json
}

nt_cmd_db() { _nt_guest_login debian "$@"; }
nt_cmd_ub() { _nt_guest_login ubuntu "$@"; }
nt_cmd_kali() { nt_fail 'Kali has no qualified Ternuxx provider yet; no guest was started. Available managed logins: tx db, tx ub.'; return 2; }

nt_cmd_proot() {
  local subcommand="${1:-status}" session_id="" plan_id="" confirmed=0 option
  [ $# -eq 0 ] || shift
  if [ "$subcommand" = "--help" ] || [ "$subcommand" = "-h" ]; then
    nt_help proot
    return 0
  fi
  case "$subcommand" in
    status|inspect)
      [ $# -eq 0 ] || { nt_fail "Use proot status; it only lists installed guests."; return 2; }
      _nt_proot_call
      ;;
    profiles)
      local action="${1:-list}"
      [ "$#" -eq 0 ] || shift
      case "$action" in
        list) [ "$#" -eq 0 ] || { nt_fail "Usage: tx proot profiles list"; return 2; }
          _nt_proot_operation proot.profiles.list ;;
        show) [ "$#" -eq 1 ] || { nt_fail "Usage: tx proot profiles show PROFILE_ID"; return 2; }
          _nt_proot_operation proot.profiles.show --guest-profile "$1" ;;
        *) nt_fail "Use tx proot profiles {list|show PROFILE_ID}."; return 2 ;;
      esac
      ;;
    sessions)
      local action="${1:-list}"
      [ "$#" -eq 0 ] || shift
      case "$action" in
        list) [ "$#" -eq 0 ] || { nt_fail "Usage: tx proot sessions list"; return 2; }
          _nt_proot_operation proot.sessions.list ;;
        show|health|recover-preview|recovery-inspect|reconcile-preview)
          [ "$#" -eq 1 ] || { nt_fail "Usage: tx proot sessions $action SESSION_ID"; return 2; }
          local operation="proot.sessions.show"
          case "$action" in
            health) operation="proot.sessions.health" ;;
            recover-preview|recovery-inspect) operation="proot.recovery.inspect" ;;
            reconcile-preview) operation="proot.recovery.reconcile.preview" ;;
          esac
          _nt_proot_operation "$operation" --session-id "$1" ;;
        *) nt_fail "Use tx proot sessions {list|show|health|recovery-inspect|reconcile-preview} [SESSION_ID]."; return 2 ;;
      esac
      ;;
    shortcuts)
      local action="${1:-list}" app_id="" shortcut_action="" plan_id="" rollback_id="" confirmed=0
      [ "$#" -eq 0 ] || shift
      case "$action" in
        list)
          [ "$#" -eq 0 ] || { nt_fail "Usage: tx proot shortcuts list"; return 2; }
          _nt_proot_operation proot.shortcuts.list
          ;;
        preview|apply)
          [ "$#" -ge 1 ] || { nt_fail "Usage: tx proot shortcuts $action add|remove APP_ID [--yes --plan-id ID]"; return 2; }
          shortcut_action="$1"; shift
          [ "$shortcut_action" = add ] || [ "$shortcut_action" = remove ] || {
            nt_fail "Shortcut action must be add or remove."; return 2;
          }
          [ "$#" -ge 1 ] || { nt_fail "Shortcut $action requires an app ID."; return 2; }
          app_id="$1"; shift
          while [ "$#" -gt 0 ]; do
            option="$1"; shift
            case "$option" in
              --yes) confirmed=1 ;;
              --plan-id)
                [ "$#" -gt 0 ] || { nt_fail "--plan-id requires an ID from the exact shortcut preview."; return 2; }
                plan_id="$1"; shift ;;
              *) nt_fail "Unknown PRoot shortcut option: $option"; return 2 ;;
            esac
          done
          if [ "$action" = preview ]; then
            [ "$confirmed" -eq 0 ] && [ -z "$plan_id" ] || {
              nt_fail "Shortcut preview accepts no apply flags."; return 2;
            }
            _nt_proot_operation proot.shortcuts.preview --shortcut-action "$shortcut_action" --app-id "$app_id"
          else
            [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || {
              nt_fail "Shortcut apply requires --yes and the exact --plan-id returned by shortcut preview."; return 2;
            }
            _nt_proot_operation proot.shortcuts.apply --shortcut-action "$shortcut_action" --app-id "$app_id" --yes --plan-id "$plan_id"
          fi
          ;;
        sync)
          local sync_action="${1:-}"
          [ "$#" -gt 0 ] || { nt_fail "Use tx proot shortcuts sync {preview|apply [--yes --plan-id ID]}"; return 2; }
          shift
          case "$sync_action" in
            preview)
              [ "$#" -eq 0 ] || { nt_fail "Usage: tx proot shortcuts sync preview"; return 2; }
              _nt_proot_operation proot.shortcuts.sync.preview ;;
            apply)
              while [ "$#" -gt 0 ]; do
                option="$1"; shift
                case "$option" in
                  --yes) confirmed=1 ;;
                  --plan-id) [ "$#" -gt 0 ] || { nt_fail "--plan-id requires the exact sync preview ID."; return 2; }; plan_id="$1"; shift ;;
                  *) nt_fail "Unknown shortcut sync option: $option"; return 2 ;;
                esac
              done
              [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || { nt_fail "Sync apply requires --yes and the exact --plan-id."; return 2; }
              _nt_proot_operation proot.shortcuts.sync.apply --yes --plan-id "$plan_id" ;;
            *) nt_fail "Use tx proot shortcuts sync {preview|apply}."; return 2 ;;
          esac
          ;;
        rollback)
          local rollback_action="${1:-}"
          [ "$#" -gt 0 ] || { nt_fail "Use tx proot shortcuts rollback {list|preview ID|apply ID --yes --plan-id ID}."; return 2; }
          shift
          case "$rollback_action" in
            list)
              [ "$#" -eq 0 ] || { nt_fail "Usage: tx proot shortcuts rollback list"; return 2; }
              _nt_proot_operation proot.shortcuts.sync.rollback.list ;;
            preview|apply)
              [ "$#" -ge 1 ] || { nt_fail "Shortcut rollback $rollback_action requires a rollback ID."; return 2; }
              rollback_id="$1"; shift
              if [ "$rollback_action" = preview ]; then
                [ "$#" -eq 0 ] || { nt_fail "Usage: tx proot shortcuts rollback preview ROLLBACK_ID"; return 2; }
                _nt_proot_operation proot.shortcuts.sync.rollback.preview --rollback-id "$rollback_id"
              else
                while [ "$#" -gt 0 ]; do
                  option="$1"; shift
                  case "$option" in
                    --yes) confirmed=1 ;;
                    --plan-id) [ "$#" -gt 0 ] || { nt_fail "--plan-id requires the exact rollback preview ID."; return 2; }; plan_id="$1"; shift ;;
                    *) nt_fail "Unknown shortcut rollback option: $option"; return 2 ;;
                  esac
                done
                [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || { nt_fail "Rollback apply requires --yes and the exact --plan-id."; return 2; }
                _nt_proot_operation proot.shortcuts.sync.rollback.apply --rollback-id "$rollback_id" --yes --plan-id "$plan_id"
              fi
              ;;
            *) nt_fail "Use tx proot shortcuts rollback {list|preview ID|apply ID --yes --plan-id ID}."; return 2 ;;
          esac
          ;;
        *) nt_fail "Use tx proot shortcuts {list|preview|apply|sync|rollback}."; return 2 ;;
      esac
      ;;
    reconcile)
      [ "$#" -ge 1 ] || { nt_fail "Usage: tx proot reconcile SESSION_ID --yes --plan-id ID"; return 2; }
      session_id="$1"; shift
      while [ "$#" -gt 0 ]; do
        option="$1"; shift
        case "$option" in
          --yes) confirmed=1 ;;
          --plan-id) [ "$#" -gt 0 ] || { nt_fail "--plan-id requires an ID from reconcile-preview."; return 2; }; plan_id="$1"; shift ;;
          *) nt_fail "Unknown PRoot reconciliation option: $option"; return 2 ;;
        esac
      done
      [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || {
        nt_fail "Reconciliation requires --yes and the exact --plan-id returned by tx proot sessions reconcile-preview SESSION_ID."; return 2;
      }
      _nt_proot_operation proot.recovery.reconcile --session-id "$session_id" --yes --plan-id "$plan_id"
      ;;
    stop-preview)
      [ "$#" -eq 1 ] || { nt_fail "Usage: tx proot stop-preview SESSION_ID"; return 2; }
      _nt_proot_operation proot.stop.preview --session-id "$1"
      ;;
    stop)
      [ "$#" -ge 1 ] || { nt_fail "Usage: tx proot stop SESSION_ID --yes --plan-id ID"; return 2; }
      session_id="$1"; shift
      while [ "$#" -gt 0 ]; do
        option="$1"; shift
        case "$option" in
          --yes) confirmed=1 ;;
          --plan-id) [ "$#" -gt 0 ] || { nt_fail "--plan-id requires an ID from stop-preview."; return 2; }; plan_id="$1"; shift ;;
          *) nt_fail "Unknown PRoot stop option: $option"; return 2 ;;
        esac
      done
      [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || {
        nt_fail "Stopping requires --yes and the exact --plan-id returned by tx proot stop-preview."; return 2;
      }
      _nt_proot_operation proot.stop --session-id "$session_id" --yes --plan-id "$plan_id"
      ;;
    verify)
      local distro="" guest_user="" user_source="" display="" backend="" option value
      while [ "$#" -gt 0 ]; do
        option="$1"; shift
        case "$option" in
          --distro|--guest-user|--guest-user-from|--display|--backend)
            [ "$#" -gt 0 ] || { nt_fail "$option requires a value."; return 2; }
            value="$1"; shift
            case "$option" in
              --distro) distro="$value" ;;
              --guest-user) guest_user="$value" ;;
              --guest-user-from) user_source="$value" ;;
              --display) display="$value" ;;
              --backend) backend="$value" ;;
            esac
            ;;
          --help|-h) nt_help proot; return 0 ;;
          *) nt_fail "Unknown PRoot verify option: $option"; return 2 ;;
        esac
      done
      [ -n "$distro" ] && [ -n "$display" ] && [ -n "$backend" ] || {
        nt_fail "Use proot verify --distro debian --guest-user USER|--guest-user-from rootfs --display :N --backend zink|virgl."
        return 2
      }
      if { [ -n "$guest_user" ] && [ -n "$user_source" ]; } ||
         { [ -z "$guest_user" ] && [ "$user_source" != "rootfs" ]; }; then
        nt_fail "Select exactly one guest-user source: --guest-user USER or --guest-user-from rootfs."
        return 2
      fi
      [ -z "$user_source" ] || [ "$user_source" = "rootfs" ] || {
        nt_fail "Unsupported guest-user source."; return 2;
      }
      _nt_proot_verify "$distro" "$guest_user" "$user_source" "$display" "$backend"
      ;;
    legacy-cli)
      local scope="guest" action="" plan_id="" backup_id="" option
      if [ "${1:-}" = "host" ]; then scope="host"; shift; fi
      action="${1:-}"
      [ "$#" -gt 0 ] || { nt_fail "Use tx proot legacy-cli [host] {preview|remove|rollback} [plan options]."; return 2; }
      shift
      case "$action" in preview|remove|rollback) ;; *) nt_fail "Use tx proot legacy-cli [host] {preview|remove|rollback}."; return 2 ;; esac
      while [ "$#" -gt 0 ]; do
        option="$1"; shift
        case "$option" in
          --plan-id) [ "$#" -gt 0 ] || { nt_fail "--plan-id needs a value."; return 2; }; plan_id="$1"; shift ;;
          --backup-id) [ "$#" -gt 0 ] || { nt_fail "--backup-id needs a value."; return 2; }; backup_id="$1"; shift ;;
          *) nt_fail "Unknown legacy CLI option: $option"; return 2 ;;
        esac
      done
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      local state_dir="${TERNUXX_STATE_DIR:-$HOME/.local/share/ternuxx}"
      local tool_action="$action" tool="$_TN_LIB_DIR/../tools/retire_legacy_guest_cli.py"
      local -a retirement_args=()
      [ "$action" = "remove" ] && tool_action="apply"
      if [ "$scope" = "host" ]; then
        tool="$_TN_LIB_DIR/../tools/retire_legacy_host_cli.py"
        retirement_args=("$tool_action" --prefix "$PREFIX" --state-dir "$state_dir" --json)
      else
        local rootfs="$PREFIX/var/lib/proot-distro/containers/debian/rootfs"
        retirement_args=("$tool_action" --rootfs "$rootfs" --state-dir "$state_dir" --json)
      fi
      case "$action" in
        preview) [ -z "$plan_id" ] && [ -z "$backup_id" ] || { nt_fail "Usage: tx proot legacy-cli [host] preview"; return 2; } ;;
        remove) [ -n "$plan_id" ] && [ -z "$backup_id" ] || { nt_fail "Remove requires --plan-id from the exact preview."; return 2; }; retirement_args+=(--plan-id "$plan_id") ;;
        rollback) [ -n "$backup_id" ] && [ -z "$plan_id" ] || { nt_fail "Rollback requires --backup-id from the retirement result."; return 2; }; retirement_args+=(--backup-id "$backup_id") ;;
      esac
      python3 "$tool" "${retirement_args[@]}"
      ;;
    db) _nt_use launch; nt_cmd_db "$@" ;;
    gui)   _nt_proot_gui "$@" ;;
    setup)
      local action="${1:-status}" user="" plan_id="" backup_id="" guest_alias="" package_groups="" package_apps="" desktop_choices="" sudo_mode="password" migration_id="" confirmed=0 option
      [ $# -eq 0 ] || shift
      case "$action" in
        catalog|status|adopt-preview|adopt|adoption-rollback-preview|adoption-rollback|fresh-preview|fresh-resume-preview|fresh-install|desktop-preview|desktop-install|desktop-resume-preview|desktop-resume|retire-preview|retire|restore-preview|restore|icd-migrate-preview|icd-migrate|icd-rollback-preview|icd-rollback) ;;
        *) nt_fail "Use tx proot setup status|adopt-preview|adopt|fresh-preview|fresh-install|icd-migrate-preview|icd-migrate|icd-rollback-preview|icd-rollback|retire-preview|retire|restore-preview|restore."; return 2 ;;
      esac
      while [ "$#" -gt 0 ]; do
        option="$1"; shift
        case "$option" in
          --user) [ "$#" -gt 0 ] || { nt_fail "--user needs a value."; return 2; }; user="$1"; shift ;;
          --alias)
            [ "$#" -gt 0 ] && [ -n "$1" ] || { nt_fail "--alias needs a value."; return 2; }
            guest_alias="$1"; shift ;;
          --plan-id) [ "$#" -gt 0 ] || { nt_fail "--plan-id needs a value."; return 2; }; plan_id="$1"; shift ;;
          --groups) [ "$#" -gt 0 ] && [ -n "$1" ] || { nt_fail "--groups needs comma-separated package groups."; return 2; }; package_groups="$1"; shift ;;
          --apps) [ "$#" -gt 0 ] && [ -n "$1" ] || { nt_fail "--apps needs comma-separated guest app IDs."; return 2; }; package_apps="$1"; shift ;;
          --desktops) [ "$#" -gt 0 ] && [ -n "$1" ] || { nt_fail "--desktops needs comma-separated desktop IDs."; return 2; }; desktop_choices="$1"; shift ;;
          --sudo-mode) [ "$#" -gt 0 ] || { nt_fail "--sudo-mode needs password or passwordless."; return 2; }; sudo_mode="$1"; shift ;;
          --backup-id) [ "$#" -gt 0 ] || { nt_fail "--backup-id needs a value."; return 2; }; backup_id="$1"; shift ;;
          --operation-id) [ "$#" -gt 0 ] || { nt_fail "--operation-id needs a value."; return 2; }; migration_id="$1"; shift ;;
          --yes) confirmed=1 ;;
          --help|-h) nt_help proot; return 0 ;;
          *) nt_fail "Unknown PRoot setup option: $option"; return 2 ;;
        esac
      done
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      local repo_root="${_TN_LIB_DIR%/lib}"
      if [[ "$action" == icd-migrate-preview || "$action" == icd-migrate || "$action" == icd-rollback-preview || "$action" == icd-rollback ]]; then
        local operation
        local -a operation_args=()
        case "$action" in
          icd-migrate-preview)
            [ "$guest_alias" = debian ] && [ -z "$migration_id$plan_id$backup_id" ] && [ "$confirmed" -eq 0 ] || { nt_fail "Usage: tx proot setup icd-migrate-preview --alias debian"; return 2; }
            operation="proot.setup.icd-migrate.preview" ;;
          icd-migrate)
            [ "$guest_alias" = debian ] && [ -z "$migration_id$backup_id" ] && [ -n "$plan_id" ] && [ "$confirmed" -eq 1 ] || { nt_fail "ICD migration requires --alias debian, --yes, and exact --plan-id."; return 2; }
            operation="proot.setup.icd-migrate.apply" ;;
          icd-rollback-preview)
            [ -n "$migration_id" ] && [ -z "$guest_alias$plan_id$backup_id" ] && [ "$confirmed" -eq 0 ] || { nt_fail "Usage: tx proot setup icd-rollback-preview --operation-id MIGRATION_ID"; return 2; }
            operation="proot.setup.icd-migrate.rollback.preview" ;;
          icd-rollback)
            [ -n "$migration_id" ] && [ -n "$plan_id" ] && [ -z "$guest_alias$backup_id" ] && [ "$confirmed" -eq 1 ] || { nt_fail "ICD rollback requires --operation-id, --yes, and exact --plan-id."; return 2; }
            operation="proot.setup.icd-migrate.rollback.apply" ;;
        esac
        operation_args=(--operation "$operation" --json)
        [ -z "$guest_alias" ] || operation_args+=(--alias "$guest_alias")
        [ -z "$migration_id" ] || operation_args+=(--operation-id "$migration_id")
        [ -z "$plan_id" ] || operation_args+=(--plan-id "$plan_id")
        [ "$confirmed" -eq 0 ] || operation_args+=(--yes)
        python3 "$repo_root/lib/management_service.py" "${operation_args[@]}"
        return $?
      fi
      if [[ "$action" == retire-preview || "$action" == retire || "$action" == restore-preview || "$action" == restore ]]; then
        [ -n "$guest_alias" ] && [ -z "$user" ] || { nt_fail "Replay retirement requires --alias ternuxx-replay-NAME."; return 2; }
        local retirement_action
        local -a retirement_args=()
        case "$action" in
          retire-preview)
            [ -z "$plan_id" ] && [ -z "$backup_id" ] && [ "$confirmed" -eq 0 ] || { nt_fail "Usage: tx proot setup retire-preview --alias ternuxx-replay-NAME"; return 2; }
            retirement_action="proot.setup.retire.preview" ;;
          retire)
            [ -n "$plan_id" ] && [ -z "$backup_id" ] && [ "$confirmed" -eq 1 ] || { nt_fail "Retire requires --yes and --plan-id from the exact preview."; return 2; }
            retirement_action="proot.setup.retire.apply" ;;
          restore-preview)
            [ -n "$backup_id" ] && [ -z "$plan_id" ] && [ "$confirmed" -eq 0 ] || { nt_fail "Restore preview requires only --backup-id."; return 2; }
            retirement_action="proot.setup.restore.preview" ;;
          restore)
            [ -n "$backup_id" ] && [ -n "$plan_id" ] && [ "$confirmed" -eq 1 ] || { nt_fail "Restore requires --backup-id, --yes, and --plan-id from its exact preview."; return 2; }
            retirement_action="proot.setup.restore.apply" ;;
        esac
        retirement_args=(--operation "$retirement_action" --alias "$guest_alias" --json)
        [ -z "$plan_id" ] || retirement_args+=(--plan-id "$plan_id")
        [ -z "$backup_id" ] || retirement_args+=(--backup-id "$backup_id")
        [ "$confirmed" -eq 0 ] || retirement_args+=(--yes)
        python3 "$repo_root/lib/management_service.py" "${retirement_args[@]}"
        return $?
      fi
      case "$sudo_mode" in password|passwordless) ;; *) nt_fail "--sudo-mode must be password or passwordless."; return 2 ;; esac
      local setup_args=("$action" --repo-root "$repo_root" --json)
      case "$action" in
        catalog) [ -z "$user$plan_id$backup_id$package_groups$desktop_choices$guest_alias$migration_id" ] && [ "$confirmed" -eq 0 ] && [ "$sudo_mode" = password ] || {
          nt_fail "Usage: tx proot setup catalog"; return 2;
        } ;;
        status) [ -z "$user" ] && [ -z "$plan_id" ] && [ "$confirmed" -eq 0 ] || {
          nt_fail "Usage: tx proot setup status"; return 2;
        } ;;
        adoption-rollback-preview) [ -n "$backup_id" ] && [ -z "$plan_id" ] && [ "$confirmed" -eq 0 ] || {
          nt_fail "Usage: tx proot setup adoption-rollback-preview --backup-id BACKUP_ID"; return 2;
        }; setup_args+=(--backup-id "$backup_id") ;;
        adoption-rollback) [ -n "$backup_id" ] && [ -n "$plan_id" ] && [ "$confirmed" -eq 1 ] || {
          nt_fail "Adoption rollback requires --backup-id, --yes, and --plan-id from the exact preview."; return 2;
        }; setup_args+=(--backup-id "$backup_id" --yes --plan-id "$plan_id") ;;
        adopt-preview) [ -n "$user" ] && [ -z "$plan_id" ] && [ "$confirmed" -eq 0 ] || {
          nt_fail "Usage: tx proot setup adopt-preview --user NAME"; return 2;
        }; setup_args+=(--user "$user") ;;
        adopt) [ -n "$user" ] && [ -n "$plan_id" ] && [ "$confirmed" -eq 1 ] || {
          nt_fail "Adoption requires --user NAME --yes --plan-id ID from the matching preview."; return 2;
        }; setup_args+=(--user "$user" --yes --plan-id "$plan_id") ;;
        desktop-install) [ -n "$plan_id" ] && [ "$confirmed" -eq 1 ] && [ -z "$user$package_groups$desktop_choices$guest_alias$backup_id$migration_id" ] || {
          nt_fail "Desktop install requires --yes --plan-id ID from its exact preview."; return 2;
        }; setup_args+=(--yes --plan-id "$plan_id") ;;
        desktop-resume-preview) [ -n "$plan_id" ] && [ "$confirmed" -eq 0 ] && [ -z "$user$package_groups$desktop_choices$guest_alias$backup_id$migration_id" ] || {
          nt_fail "Desktop resume preview requires --plan-id FAILED_PLAN_ID."; return 2;
        }; setup_args+=(--plan-id "$plan_id") ;;
        desktop-resume) [ -n "$plan_id" ] && [ "$confirmed" -eq 1 ] && [ -z "$user$package_groups$desktop_choices$guest_alias$backup_id$migration_id" ] || {
          nt_fail "Desktop resume requires --yes --plan-id RECOVERY_PLAN_ID."; return 2;
        }; setup_args+=(--yes --plan-id "$plan_id") ;;
        desktop-preview) [ -n "$desktop_choices" ] && [ -z "$user$plan_id$package_groups$backup_id$migration_id" ] && [ "$confirmed" -eq 0 ] || {
          nt_fail "Usage: tx proot setup desktop-preview --desktops ID[,ID...] [--alias debian|ternuxx-replay-NAME] [--apps APP[,APP...]]"; return 2;
        }; [ -z "$guest_alias" ] || setup_args+=(--alias "$guest_alias"); [ -z "$package_apps" ] || setup_args+=(--apps "$package_apps") ;;
        fresh-install) [ -n "$plan_id" ] && [ "$confirmed" -eq 1 ] || {
          nt_fail "Fresh install requires --yes --plan-id ID from the matching preview."; return 2;
        }; [ -z "$user" ] || setup_args+=(--user "$user"); setup_args+=(--sudo-mode "$sudo_mode" --yes --plan-id "$plan_id") ;;
        fresh-preview) [ -n "$user" ] && [ -z "$plan_id" ] && [ "$confirmed" -eq 0 ] || {
          nt_fail "Usage: tx proot setup fresh-preview --user NAME [--groups base,fonts] [--desktops xfce,lxqt,lxde,mate,plasma] [--sudo-mode password|passwordless]"; return 2;
        }; setup_args+=(--user "$user" --sudo-mode "$sudo_mode") ;;
        fresh-resume-preview) [ -n "$user" ] && [ -n "$plan_id" ] && [ "$confirmed" -eq 0 ] || {
          nt_fail "Usage: tx proot setup fresh-resume-preview --user NAME --plan-id FAILED_PLAN_ID [--groups base,fonts] [--desktops xfce,lxqt,lxde,mate,plasma] [--sudo-mode password|passwordless]"; return 2;
        }; setup_args+=(--user "$user" --plan-id "$plan_id" --sudo-mode "$sudo_mode") ;;
      esac
      if [ -n "$desktop_choices" ]; then
        case "$action" in
          fresh-preview|fresh-resume-preview|desktop-preview) setup_args+=(--desktops "$desktop_choices") ;;
          *) nt_fail "--desktops is supported only by fresh preview actions."; return 2 ;;
        esac
      fi
      if [ -n "$package_apps" ] && [ "$action" != desktop-preview ]; then
        nt_fail "--apps is supported only by desktop-preview."; return 2
      fi
      if [ -n "$package_groups" ]; then
        case "$action" in
          fresh-preview|fresh-resume-preview) setup_args+=(--groups "$package_groups") ;;
          *) nt_fail "--groups is supported only by fresh preview actions."; return 2 ;;
        esac
      fi
      if [ -n "$guest_alias" ]; then
        case "$action" in
          fresh-preview|fresh-resume-preview|fresh-install) setup_args+=(--alias "$guest_alias") ;;
          desktop-preview) ;;
          *) nt_fail "--alias is supported only by fresh setup."; return 2 ;;
        esac
      fi
      python3 "$_TN_LIB_DIR/proot_setup.py" "${setup_args[@]}"
      ;;
    *) nt_fail "Use proot status|inspect|verify|legacy-cli [host]|db|gui|setup; use tx pgui for the full Debian desktop."; return 2 ;;
  esac
}
