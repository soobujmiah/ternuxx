# Native Termux desktop; thin aliases over the existing lifecycle commands.
# Native Termux desktop; thin aliases over the existing lifecycle commands.
nt_cmd_gui_monitor() {
  local action="${1:-status}" operation flag value
  [ $# -eq 0 ] || shift
  local -a args=()
  case "$action" in
    --help|-h) nt_help gui; return 0 ;;
    service)
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      python3 "$_TN_LIB_DIR/gui_monitoring.py" service "$@"
      return $? ;;
    status) operation="desktop.monitor.status" ;;
    enable) operation="desktop.monitor.configure"; args+=(--monitor-enabled) ;;
    disable) operation="desktop.monitor.configure"; args+=(--monitor-disabled) ;;
    configure)
      operation="desktop.monitor.configure"
      while [ "$#" -gt 0 ]; do
        flag="$1"; shift
        case "$flag" in
          --enabled|--activity-launch|--focus-check)
            [ "$#" -ge 1 ] || { nt_fail "$flag requires on or off"; return 2; }
            value="$1"; shift
            case "$flag:$value" in
              --enabled:on) args+=(--monitor-enabled) ;;
              --enabled:off) args+=(--monitor-disabled) ;;
              --activity-launch:on) args+=(--monitor-activity-launch) ;;
              --activity-launch:off) args+=(--monitor-no-activity-launch) ;;
              --focus-check:on) args+=(--monitor-focus-check) ;;
              --focus-check:off) args+=(--monitor-no-focus-check) ;;
              *) nt_fail "$flag accepts on or off"; return 2 ;;
            esac ;;
          --interval)
            [ "$#" -ge 2 ] || { nt_fail "--interval requires a value and unit"; return 2; }
            args+=(--monitor-interval "$1" --monitor-unit "$2"); shift 2 ;;
          *) nt_fail "Unknown GUI monitoring option: $flag"; return 2 ;;
        esac
      done ;;
    *) nt_fail "Use gui monitor [status|enable|disable|configure options]"; return 2 ;;
  esac
  nt_require_termux || return 1
  nt_require_command python3 || return 1
  python3 "$_TN_LIB_DIR/management_service.py" --operation "$operation" "${args[@]}" --json
}

nt_cmd_gui() {
  local action="${1:-open}"
  [ $# -eq 0 ] || shift
  if [ "$action" = "monitor" ]; then nt_cmd_gui_monitor "$@"; return $?; fi
  case "$action" in
    open|center)
      [ $# -eq 0 ] || { nt_fail "Usage: tx gui"; return 2; }
      _nt_use desktop || return 1
      local desktop_report lifecycle
      desktop_report="$(TERNUXX_JSON=1 nt_cmd_status)" || return 1
      lifecycle="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("status", "unknown"))' <<<"$desktop_report" 2>/dev/null)" || lifecycle=unknown
      case "$lifecycle" in
        running) ;;
        stopped|stale)
          nt_info "The Native desktop is $lifecycle; starting it so the GUI center has a verified display."
          nt_cmd_start || return $? ;;
        *) nt_fail "Native desktop state is $lifecycle; inspect 'tx status' before opening the GUI center."; return 1 ;;
      esac
      _nt_use management || return 1
      nt_cmd_management center
      ;;
    start|stop|restart|status)
      # Preserve the historical explicit desktop lifecycle subcommands.
      _nt_use desktop || return 1
      case "$action" in
        start)   nt_cmd_start "$@" ;;
        stop)    nt_cmd_stop "$@" ;;
        restart) nt_cmd_restart "$@" ;;
        status)  nt_cmd_status "$@" ;;
      esac
      ;;
    *) nt_fail "Use 'tx gui' to open the Native management center, or tx gui [start|stop|restart|status] for desktop lifecycle."; return 2 ;;
  esac
}
