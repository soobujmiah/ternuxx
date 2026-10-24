# Native reboot-recovery and read-only runtime status commands.

_nt_management_call() {
  nt_require_termux || return 1
  nt_require_command python3 || return 1
  local format_args=()
  [ "$TERNUXX_JSON" = "1" ] && format_args+=(--json)
  TERNUXX_WAKELOCK_CALLER_PID="${PPID:-}" python3 "$_TN_LIB_DIR/management_service.py" "$@" "${format_args[@]}"
}

nt_cmd_reboot() {
  local action="${1:-status}"; [ "$#" -gt 0 ] && shift
  case "$action" in
    status)
      local test_id="${1:-}"
      if [ -n "$test_id" ]; then _nt_management_call --operation continuity.status --test-id "$test_id"; else _nt_management_call --operation continuity.status; fi
      ;;
    prepare)
      local test_id="" baseline="" confirmed=0 plan_id="" response="" preview_op="continuity.prepare-reboot-test.preview"
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --test-id) [ "$#" -ge 2 ] || { nt_fail "--test-id needs a value"; return 2; }; test_id="$2"; shift 2 ;;
          --baseline-json) [ "$#" -ge 2 ] || { nt_fail "--baseline-json needs a value"; return 2; }; baseline="$2"; shift 2 ;;
          --yes) confirmed=1; shift ;;
          --plan-id) [ "$#" -ge 2 ] || { nt_fail "--plan-id needs a value"; return 2; }; plan_id="$2"; shift 2 ;;
          *) nt_fail "Unknown reboot prepare option: $1"; return 2 ;;
        esac
      done
      [ -n "$test_id" ] && [ -n "$baseline" ] || { nt_fail "Usage: tx reboot prepare --test-id ID --baseline-json JSON [--yes --plan-id ID]"; return 2; }
      if [ "$confirmed" -eq 1 ] || [ -n "$plan_id" ]; then
        [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || { nt_fail "Apply requires both --yes and the exact preview --plan-id"; return 2; }
        _nt_management_call --operation continuity.prepare-reboot-test --test-id "$test_id" --baseline-json "$baseline" --yes --plan-id "$plan_id"
      else
        if [ "$TERNUXX_JSON" = "1" ]; then
          _nt_management_call --operation "$preview_op" --test-id "$test_id" --baseline-json "$baseline"
          return $?
        fi
        response=$(TERNUXX_JSON=1 _nt_management_call --operation "$preview_op" --test-id "$test_id" --baseline-json "$baseline") || return $?
        printf '%s\n' "$response"
        local current_plan
        current_plan=$(printf '%s' "$response" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["plan_id"])') || return 1
        [ -t 0 ] || { nt_fail "No TTY: review the preview, then rerun with --yes --plan-id $current_plan"; return 2; }
        printf 'Type CREATE REBOOT TEST RECORD to continue: '
        local answer=""; IFS= read -r answer
        [ "$answer" = "CREATE REBOOT TEST RECORD" ] || { nt_fail "Confirmation did not match; no record was created"; return 2; }
        _nt_management_call --operation continuity.prepare-reboot-test --test-id "$test_id" --baseline-json "$baseline" --yes --plan-id "$current_plan"
      fi
      ;;
    verify)
      local test_id="${1:-}" confirmed=0 plan_id="" response=""
      [ -n "$test_id" ] || { nt_fail "Usage: tx reboot verify <test-id> [--yes --plan-id ID]"; return 2; }
      shift
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --yes) confirmed=1; shift ;;
          --plan-id) [ "$#" -ge 2 ] || { nt_fail "--plan-id needs a value"; return 2; }; plan_id="$2"; shift 2 ;;
          *) nt_fail "Unknown reboot verify option: $1"; return 2 ;;
        esac
      done
      if [ "$confirmed" -eq 1 ] || [ -n "$plan_id" ]; then
        [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || { nt_fail "Apply requires both --yes and the exact preview --plan-id"; return 2; }
        _nt_management_call --operation continuity.verify-reboot-test --test-id "$test_id" --yes --plan-id "$plan_id"
      else
        if [ "$TERNUXX_JSON" = "1" ]; then
          _nt_management_call --operation continuity.verify-reboot-test.preview --test-id "$test_id"
          return $?
        fi
        response=$(TERNUXX_JSON=1 _nt_management_call --operation continuity.verify-reboot-test.preview --test-id "$test_id") || return $?
        printf '%s\n' "$response"
        local current_plan
        current_plan=$(printf '%s' "$response" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["plan_id"])') || return 1
        [ -t 0 ] || { nt_fail "No TTY: review the preview, then rerun with --yes --plan-id $current_plan"; return 2; }
        printf 'Type VERIFY REBOOT TEST to continue: '
        local answer=""; IFS= read -r answer
        [ "$answer" = "VERIFY REBOOT TEST" ] || { nt_fail "Confirmation did not match; no verification was recorded"; return 2; }
        _nt_management_call --operation continuity.verify-reboot-test --test-id "$test_id" --yes --plan-id "$current_plan"
      fi
      ;;
    resume-info)
      local test_id="${1:-}"
      [ -n "$test_id" ] || { nt_fail "Usage: tx reboot resume-info <test-id>"; return 2; }
      _nt_management_call --operation continuity.resume-info --test-id "$test_id"
      ;;
    *) nt_fail "Supported reboot operations: status, prepare, verify, resume-info"; return 2 ;;
  esac
}

nt_cmd_boot() {
  local action="${1:-status}"
  case "$action" in
    status)
      [ "$#" -le 1 ] || { nt_fail "Usage: tx boot status"; return 2; }
      _nt_management_call --operation boot.status ;;
    gui)
      local choice="${2:-}" confirmed=0 profile
      [ "$#" -ge 2 ] || { nt_fail "Usage: tx boot gui <on|off> [--yes]"; return 2; }
      case "$choice" in
        on) profile="native" ;;
        off) profile="cli-only" ;;
        *) nt_fail "GUI startup choice must be on or off"; return 2 ;;
      esac
      shift 2
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --yes) confirmed=1; shift ;;
          *) nt_fail "Unknown boot gui option: $1"; return 2 ;;
        esac
      done
      local gui_args=(--operation boot.enable --profile "$profile")
      [ "$confirmed" -eq 1 ] && gui_args+=(--yes)
      _nt_management_call "${gui_args[@]}" ;;
    enable)
      local profile="" confirmed=0
      shift
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --profile) [ "$#" -ge 2 ] || { nt_fail "--profile needs a value"; return 2; }; profile="$2"; shift 2 ;;
          --yes) confirmed=1; shift ;;
          *) nt_fail "Unknown boot enable option: $1"; return 2 ;;
        esac
      done
      [ -n "$profile" ] || { nt_fail "Usage: tx boot enable --profile <cli-only|native> [--yes]"; return 2; }
      local enable_args=(--operation boot.enable --profile "$profile")
      [ "$confirmed" -eq 1 ] && enable_args+=(--yes)
      _nt_management_call "${enable_args[@]}" ;;
    disable)
      local confirmed=0
      shift
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --yes) confirmed=1; shift ;;
          *) nt_fail "Unknown boot disable option: $1"; return 2 ;;
        esac
      done
      local disable_args=(--operation boot.disable)
      [ "$confirmed" -eq 1 ] && disable_args+=(--yes)
      _nt_management_call "${disable_args[@]}" ;;
    profile)
      case "${2:-status}" in
        status)
          [ "$#" -le 2 ] || { nt_fail "Usage: tx boot profile status"; return 2; }
          _nt_management_call --operation boot.profile.status ;;
        preview)
          [ "$#" -eq 3 ] || { nt_fail "Usage: tx boot profile preview <cli-only|native>"; return 2; }
          _nt_management_call --operation boot.profile.preview --profile "$3" ;;
        *)
          nt_fail "Usage: tx boot profile status | preview <cli-only|native>"
          return 2 ;;
      esac ;;
    *)
      nt_fail "Supported boot operations: status, profile status/preview, enable/disable (preview first; --yes applies)"
      return 2 ;;
  esac
}

nt_cmd_wakelock() {
  local action="${1:-status}"
  [ "$#" -gt 0 ] && shift
  case "$action" in
    status)
      [ "$#" -eq 0 ] || { nt_fail "Usage: tx wakelock status"; return 2; }
      _nt_management_call --operation wakelock.status ;;
    ssh-policy)
      local sub="${1:-status}" enabled_flag="" confirmed=0 plan_id=""
      case "$sub" in
        status)
          [ "$#" -eq 1 ] || { nt_fail "Usage: tx wakelock ssh-policy status"; return 2; }
          _nt_management_call --operation wakelock.ssh-policy.status ;;
        preview|apply)
          shift
          while [ "$#" -gt 0 ]; do
            case "$1" in
              --enabled) [ -z "$enabled_flag" ] || { nt_fail "Choose one SSH Wake Lock setting"; return 2; }; enabled_flag="--ssh-wakelock-enabled"; shift ;;
              --disabled) [ -z "$enabled_flag" ] || { nt_fail "Choose one SSH Wake Lock setting"; return 2; }; enabled_flag="--ssh-wakelock-disabled"; shift ;;
              --yes) confirmed=1; shift ;;
              --plan-id) [ "$#" -ge 2 ] || { nt_fail "--plan-id needs a value"; return 2; }; local plan_id="$2"; shift 2 ;;
              *) nt_fail "Unknown SSH Wake Lock option: $1"; return 2 ;;
            esac
          done
          [ -n "$enabled_flag" ] || { nt_fail "Choose --enabled or --disabled"; return 2; }
          if [ "$sub" = "preview" ]; then
            _nt_management_call --operation wakelock.ssh-policy.preview "$enabled_flag"
          else
            [ "$confirmed" -eq 1 ] && [ -n "${plan_id:-}" ] || { nt_fail "Apply requires --yes and --plan-id"; return 2; }
            _nt_management_call --operation wakelock.ssh-policy.apply "$enabled_flag" --yes --plan-id "$plan_id"
          fi ;;
        *) nt_fail "Usage: tx wakelock ssh-policy status | preview --enabled|--disabled | apply --enabled|--disabled --yes --plan-id ID"; return 2 ;;
      esac ;;
    acquire|release)
      local owner="${1:-}" persistent=0
      [ -n "$owner" ] || { nt_fail "Usage: tx wakelock $action <owner> [--persistent]"; return 2; }
      shift
      if [ "${1:-}" = "--persistent" ]; then persistent=1; shift; fi
      [ "$#" -eq 0 ] || { nt_fail "Unexpected Wake Lock option"; return 2; }
      local op="wakelock.$action"
      if [ "$persistent" -eq 1 ]; then
        _nt_management_call --operation "$op" --owner "$owner" --persistent
      else
        _nt_management_call --operation "$op" --owner "$owner"
      fi ;;
    *) nt_fail "Supported Wake Lock operations: status, ssh-policy status/preview/apply, acquire <owner>, release <owner>"; return 2 ;;
  esac
}
