#!/data/data/com.termux/files/usr/bin/bash


nt_cmd_app() {
  if [ "${1:-}" = "--" ]; then
    _nt_use proot || return $?
    nt_cmd_debian_menu_app "$@"
    return $?
  fi
  nt_require_termux || return $?
  local service="${_TN_LIB_DIR}/management_service.py" sub="${1:-list}" app_id="" action="" plan_id="" confirm=""
  [ "$#" -gt 0 ] && shift || true
  case "$sub" in
    list|catalog)
      [ "$#" -eq 0 ] || { nt_fail "Usage: tx app list"; return 2; }
      local args=(--operation software.apps.list)
      [ "$TERNUXX_JSON" = "1" ] && args+=(--json)
      python3 "$service" "${args[@]}"
      ;;
    run)
      [ "$#" -eq 2 ] && [ "$1" = directory-tree ] || { nt_fail "Usage: tx app run directory-tree HOME_PATH"; return 2; }
      local app_path="$2"; local args=(--operation software.app.run --app-id directory-tree --app-path "$app_path")
      [ "$TERNUXX_JSON" = "1" ] && args+=(--json)
      python3 "$service" "${args[@]}"
      ;;
    preview)
      [ "$#" -eq 2 ] || { nt_fail "Usage: tx app preview APP_ID {install|update|remove}"; return 2; }
      app_id="$1"; action="$2"
      case "$action" in install|update|remove) ;; *) nt_fail "App action must be install, update, or remove."; return 2 ;; esac
      local args=(--operation software.app.preview --app-id "$app_id" --app-action "$action")
      [ "$TERNUXX_JSON" = "1" ] && args+=(--json)
      python3 "$service" "${args[@]}"
      ;;
    apply)
      [ "$#" -ge 2 ] || { nt_fail "Usage: tx app apply APP_ID {install|update|remove} --plan-id ID [--confirm TOKEN]"; return 2; }
      app_id="$1"; action="$2"; shift 2
      case "$action" in install|update|remove) ;; *) nt_fail "App action must be install, update, or remove."; return 2 ;; esac
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --plan-id) [ "$#" -ge 2 ] || { nt_fail "--plan-id requires the ID from a saved preview."; return 2; }; plan_id="$2"; shift 2 ;;
          --confirm) [ "$#" -ge 2 ] || { nt_fail "--confirm requires INSTALL, UPDATE, or REMOVE."; return 2; }; confirm="$2"; shift 2 ;;
          *) nt_fail "Unknown app option: $1"; return 2 ;;
        esac
      done
      if [ -z "$confirm" ] && [ -t 0 ]; then
        read -r -p "Type ${action^^} to apply this exact package plan: " confirm || return 2
      fi
      local args=(--operation software.app.apply --app-id "$app_id" --app-action "$action"
                  --plan-id "$plan_id" --app-confirm "$confirm")
      [ "$TERNUXX_JSON" = "1" ] && args+=(--json)
      python3 "$service" "${args[@]}"
      ;;
    *) nt_fail "Usage: tx app {list|run|preview|apply}"; return 2 ;;
  esac
}

nt_cmd_management() {
  local section="${1:-}"
  [ "$#" -gt 0 ] && shift
  case "$section" in
    proot)
      _nt_use proot || return $?
      nt_cmd_proot "$@"
      ;;
    app)
      local action="${1:-}" app_id="" desktop_id="" display=""
      [ "$#" -gt 0 ] && shift
      [ "$action" = launch ] || {
        nt_fail "Use tx mng app launch APP_ID | --desktop-id DESKTOP_ID [--display :N]."
        return 2
      }
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --desktop-id)
            [ "$#" -ge 2 ] && [ -z "$app_id$desktop_id" ] || { nt_fail "--desktop-id requires one application ID."; return 2; }
            desktop_id="$2"; shift 2 ;;
          --app-id)
            [ "$#" -ge 2 ] && [ -z "$app_id$desktop_id" ] || { nt_fail "--app-id requires one fixed application ID."; return 2; }
            app_id="$2"; shift 2 ;;
          --display)
            [ "$#" -ge 2 ] && [ -z "$display" ] || { nt_fail "--display requires one X11 display such as :0."; return 2; }
            display="$2"; shift 2 ;;
          --help|-h)
            printf '%s\n' "Usage: tx mng app launch APP_ID | --desktop-id DESKTOP_ID [--display :N]" \
              "Launch an allowlisted Debian XFCE application through the shared PRoot service."
            return 0 ;;
          *)
            if [ -z "$app_id$desktop_id" ]; then
              case "$1" in
                *.desktop) desktop_id="$1" ;;
                *) app_id="$1" ;;
              esac
              shift
            else
              nt_fail "Unexpected Debian app launch argument: $1"; return 2
            fi ;;
        esac
      done
      [ -n "$app_id$desktop_id" ] || { nt_fail "Provide a fixed APP_ID or --desktop-id DESKTOP_ID."; return 2; }
      if [ -n "$display" ] && ! [[ "$display" =~ ^:[0-9]{1,2}$ ]]; then
        nt_fail "Display must be an X11 display such as :0."; return 2
      fi
      _nt_use proot || return $?
      local -a launch_args=()
      [ -n "$app_id" ] && launch_args+=(--app-id "$app_id")
      [ -n "$desktop_id" ] && launch_args+=(--desktop-id "$desktop_id")
      [ -n "$display" ] && launch_args+=(--display "$display")
      _nt_proot_operation proot.app.launch "${launch_args[@]}"
      ;;
    papps|shortcuts)
      nt_fail 'Use `tx proot` for Debian status/setup and `tx gui` for the management center; Native app management is `tx app`.'
      return 2 ;;
    graphics)
      local action="${1:-status}" provider="${2:-native}" api="${3:-opengl}" display="${4:-:1}"
      [ "$provider" = native ] || { nt_warn "Only Native Termux graphics are supported."; return 2; }
      case "$action" in
        status) python3 "$_TN_LIB_DIR/management_service.py" --operation graphics.provider.status --provider "$provider" --json ;;
        verify) python3 "$_TN_LIB_DIR/management_service.py" --operation graphics.provider.verify --provider "$provider" --graphics-api "$api" --display "$display" --json ;;
        select) [ "$provider" = native ] || { nt_fail "Only Native Termux graphics backends are supported here."; return 2; }; python3 "$_TN_LIB_DIR/management_service.py" --operation graphics.provider.select --provider native --graphics-backend "$api" --yes --json ;;
        *) nt_fail "Usage: tx mng graphics {status native|verify native {opengl|gles|vulkan} [:N]|select native {system|termux-zink|kgsl-freedreno}}"; return 2 ;;
      esac
      ;;
    logs)
      local action="list"
      if [ "$#" -gt 0 ]; then action="$1"; shift; fi
      case "$action" in
        list)
          [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng logs list"; return 2; }
          python3 "$_TN_LIB_DIR/management_service.py" --operation management.logs.list --json
          ;;
        read)
          [ "$#" -eq 1 ] || { nt_fail "Usage: tx mng logs read SOURCE_ID"; return 2; }
          python3 "$_TN_LIB_DIR/management_service.py" --operation management.logs.read --source-id "$1" --json
          ;;
        *) nt_fail "Usage: tx mng logs {list|read SOURCE_ID}"; return 2 ;;
      esac
      ;;
    center)
      local action="${1:-}"
      [ "$#" -eq 0 ] || shift
      case "$action" in
        install)
          [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng center install"; return 2; }
          bash "$_NT_BIN_DIR/../scripts/install-management-center.sh"
          ;;
        ""|open|start)
          [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng center"; return 2; }
          nt_require_termux || return 1
          local app="$PREFIX/bin/tx-management-center"
          nt_require_command python3 || return 1
          _nt_use desktop || return 1
          _nt_adopt_live_session_state
          local session_report session_state session_display selected_display
          session_report="$(python3 "$_TN_LIB_DIR/desktop_session_state.py" inspect "$HOME" "$TERNUXX_STATE_DIR" /proc "${TMPDIR:-$PREFIX/tmp}" 2>/dev/null)" || {
            nt_fail "Could not verify the Ternuxx-owned Native desktop session; run 'tx status' before opening the management center."
            return 1
          }
          session_state="$(printf '%s' "$session_report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("state", "unknown"))')" || session_state=unknown
          session_display="$(printf '%s' "$session_report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("display", ""))')" || session_display=""
          [ "$session_state" = running ] || {
            nt_fail "The Ternuxx Native desktop is not verified running. Run 'tx start', then retry 'tx gui'."
            return 1
          }
          [ -n "$session_display" ] || { nt_fail "The verified Ternuxx session has no display identity."; return 1; }
          if [ -n "${DISPLAY:-}" ] && [ "$DISPLAY" != "$session_display" ]; then
            nt_fail "DISPLAY=$DISPLAY does not match the verified Ternuxx display $session_display; refusing to attach to another session."
            return 1
          fi
          selected_display="$session_display"
          local probe="$_NT_BIN_DIR/../scripts/native_display_probe.py"
          local display_result
          display_result="$(python3 "$probe" "$selected_display" "${TMPDIR:-$PREFIX/tmp}" 2>&1)" || {
            nt_fail "Cannot open the selected Native Termux display: $display_result"
            return 1
          }
          [ -x "$app" ] || { nt_fail "GTK management client is not installed; run 'tx mng center install'."; return 1; }
          if [ "${TERNUXX_SKIP_X11_ACTIVITY_REQUEST:-0}" != 1 ]; then
            _nt_request_termux_x11_activity || nt_warn "Could not foreground the Native Termux:X11 window; open Termux:X11 manually."
          fi
          _nt_use audio || return 1
          nt_audio_ensure || true
          nt_info "Opening the GTK management center in the foreground; this command waits while its window is open. Ctrl+C closes the center, but leaves the Native desktop running; use 'tx stop' to stop the desktop."
          DISPLAY="$selected_display" "$app"
          ;;
        --help|-h) nt_help management ;;
        *) nt_fail "Use 'tx mng center [install]'."; return 2 ;;
      esac
      ;;
    catalog)
      local action="${1:-}"
      [ "$#" -gt 0 ] && shift
      [ "$action" = "list" ] || { nt_fail "Usage: tx mng catalog list [--category ID] [--query TEXT] [--status STATE]"; return 2; }
      local -a catalog_args=()
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --category|--query|--status)
            [ "$#" -ge 2 ] || { nt_fail "$1 requires a value"; return 2; }
            case "$1" in --category) catalog_args+=(--category "$2");; --query) catalog_args+=(--query "$2");; --status) catalog_args+=(--status "$2");; esac
            shift 2 ;;
          *) nt_fail "Unknown catalog option: $1"; return 2 ;;
        esac
      done
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      python3 "$_TN_LIB_DIR/management_service.py" --operation management.catalog "${catalog_args[@]}" --json
      ;;
    timezone)
      local action="${1:-status}"
      [ "$#" -gt 0 ] && shift
      local operation="timezone.$action"
      case "$action" in
        status|list) [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng timezone $action"; return 2; } ;;
        set)
          [ "$#" -eq 1 ] || { nt_fail "Usage: tx mng timezone set IANA_NAME"; return 2; }
          local timezone_name="$1"
          ;;
        --help|-h) nt_help management; return 0 ;;
        *) nt_fail "Use tx mng timezone {status|list|set IANA_NAME}."; return 2 ;;
      esac
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      if [ "$action" = "set" ]; then
        python3 "$_TN_LIB_DIR/management_service.py" --operation "$operation" --timezone "$timezone_name" --json
      else
        python3 "$_TN_LIB_DIR/management_service.py" --operation "$operation" --json
      fi
      ;;
    cron)
      local area="${1:-status}"
      [ "$#" -eq 0 ] || shift
      local operation="cron.status"
      local -a cron_args=()
      case "$area" in
        start)
          operation="cron.scheduler.start"
          local start_confirmed=0
          while [ "$#" -gt 0 ]; do
            case "$1" in
              --yes) start_confirmed=1; cron_args+=(--yes); shift ;;
              --poll-seconds) [ "$#" -ge 2 ] || { nt_fail "--poll-seconds requires a value"; return 2; }; cron_args+=(--poll-seconds "$2"); shift 2 ;;
              *) nt_fail "Unknown scheduler start option: $1"; return 2 ;;
            esac
          done
          [ "$start_confirmed" -eq 1 ] || { nt_fail "Starting Cron may run enabled jobs; confirm with --yes."; return 2; } ;;
        stop)
          [ "$#" -eq 1 ] && [ "$1" = "--yes" ] || { nt_fail "Usage: tx mng cron stop --yes"; return 2; }
          operation="cron.scheduler.stop"; cron_args+=(--yes) ;;
        executions)
          local action="${1:-list}"
          [ "$#" -eq 0 ] || shift
          case "$action" in
            list)
              operation="cron.executions.list"
              while [ "$#" -gt 0 ]; do
                case "$1" in
                  --job-id) [ "$#" -ge 2 ] || { nt_fail "--job-id requires an ID"; return 2; }; cron_args+=(--job-id "$2"); shift 2 ;;
                  --limit) [ "$#" -ge 2 ] || { nt_fail "--limit requires a number"; return 2; }; cron_args+=(--limit "$2"); shift 2 ;;
                  *) nt_fail "Unknown executions list option: $1"; return 2 ;;
                esac
              done ;;
            show)
              [ "$#" -eq 1 ] || { nt_fail "Usage: tx mng cron executions show EXECUTION_ID"; return 2; }
              operation="cron.executions.show"; cron_args+=(--execution-id "$1") ;;
            *) nt_fail "Use tx mng cron executions {list|show}."; return 2 ;;
          esac ;;
        status) [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng cron status"; return 2; } ;;
        jobs)
          local action="${1:-list}"
          [ "$#" -eq 0 ] || shift
          case "$action" in
            list) operation="cron.jobs.list"; [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng cron jobs list"; return 2; } ;;
            validate)
              if [ "$#" -gt 0 ] && [[ "$1" != -* ]]; then cron_args+=(--job-id "$1"); shift; fi
              operation="cron.jobs.validate"; cron_args+=("$@");;
            show|next-runs|remove|enable|disable|update)
              [ "$#" -ge 1 ] || { nt_fail "Usage: tx mng cron jobs $action JOB_ID [options]"; return 2; }
              local job_id="$1"; shift
              case "$action" in
                show) operation="cron.jobs.show"; [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng cron jobs show JOB_ID"; return 2; }; cron_args+=(--job-id "$job_id") ;;
                next-runs) operation="cron.jobs.next_runs"; cron_args+=(--job-id "$job_id"); while [ "$#" -gt 0 ]; do case "$1" in --count) [ "$#" -ge 2 ] || { nt_fail "--count requires a number"; return 2; }; cron_args+=(--count "$2"); shift 2;; *) nt_fail "Unknown next-runs option: $1"; return 2;; esac; done ;;
                remove) operation="cron.jobs.mutation.preview"; [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng cron jobs remove JOB_ID"; return 2; }; cron_args+=(--mutation-action remove --job-id "$job_id") ;;
                enable|disable) operation="cron.jobs.mutation.preview"; [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng cron jobs $action JOB_ID"; return 2; }; cron_args+=(--mutation-action update --job-id "$job_id" "$( [ "$action" = enable ] && echo --job-enabled || echo --job-disabled )") ;;
                update) operation="cron.jobs.mutation.preview"; cron_args+=(--mutation-action update --job-id "$job_id" "$@") ;;
              esac ;;
            create) operation="cron.jobs.mutation.preview"; cron_args+=(--mutation-action create "$@") ;;
            apply) operation="cron.jobs.mutation.apply"; cron_args+=("$@") ;;
            *) nt_fail "Use tx mng cron jobs {list|show|validate|next-runs|create|update|enable|disable|remove|apply}."; return 2 ;;
          esac ;;
        *) nt_fail "Use tx mng cron {status|start|stop|jobs|executions}."; return 2 ;;
      esac
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      python3 "$_TN_LIB_DIR/management_service.py" --operation "$operation" "${cron_args[@]}" --json
      ;;
    boot)
      local boot_area="${1:-cron}"
      [ "$#" -gt 0 ] && shift
      if [ "$boot_area" = "helpers" ]; then
        local action="${1:-status}" helper_id="" helper_action="" snapshot_id="" plan_id="" confirmed=0 operation="boot.helpers.status"
        [ "$#" -gt 0 ] && shift
        case "$action" in
          status) [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng boot helpers status"; return 2; } ;;
          preview)
            [ "$#" -ge 2 ] || { nt_fail "Usage: tx mng boot helpers preview {deploy|rollback} HELPER_ID [SNAPSHOT_ID]"; return 2; }
            helper_action="$1"; helper_id="$2"; shift 2
            [ "$helper_action" = deploy ] || [ "$helper_action" = rollback ] || { nt_fail "Helper action must be deploy or rollback."; return 2; }
            if [ "$helper_action" = rollback ]; then [ "$#" -eq 1 ] || { nt_fail "Rollback preview needs SNAPSHOT_ID."; return 2; }; snapshot_id="$1"; shift; else [ "$#" -eq 0 ] || { nt_fail "Unexpected helper preview arguments."; return 2; }; fi
            operation="boot.helpers.preview" ;;
          apply)
            [ "$#" -ge 4 ] || { nt_fail "Usage: tx mng boot helpers apply {deploy|rollback} HELPER_ID [SNAPSHOT_ID] --yes --plan-id ID"; return 2; }
            helper_action="$1"; helper_id="$2"; shift 2
            if [ "$helper_action" = rollback ]; then [ "$#" -ge 3 ] || { nt_fail "Rollback apply needs SNAPSHOT_ID --yes --plan-id ID."; return 2; }; snapshot_id="$1"; shift; fi
            while [ "$#" -gt 0 ]; do case "$1" in --yes) confirmed=1; shift;; --plan-id) [ "$#" -ge 2 ] || { nt_fail "--plan-id requires ID."; return 2; }; plan_id="$2"; shift 2;; *) nt_fail "Unknown helper apply option: $1"; return 2;; esac; done
            [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || { nt_fail "Preview first, then apply exact plan with --yes --plan-id ID."; return 2; }
            operation="boot.helpers.apply" ;;
          *) nt_fail "Use tx mng boot helpers {status|preview|apply}."; return 2 ;;
        esac
        nt_require_termux || return 1
        nt_require_command python3 || return 1
        local -a helper_args=(--operation "$operation")
        [ -z "$helper_id" ] || helper_args+=(--helper-id "$helper_id")
        [ -z "$helper_action" ] || helper_args+=(--helper-action "$helper_action")
        [ -z "$snapshot_id" ] || helper_args+=(--snapshot-id "$snapshot_id")
        [ "$confirmed" -eq 0 ] || helper_args+=(--yes --plan-id "$plan_id")
        python3 "$_TN_LIB_DIR/management_service.py" "${helper_args[@]}" --json
        return $?
      fi
      [ "$boot_area" = "cron" ] || { nt_fail "Use tx mng boot {helpers|cron}."; return 2; }
      local action="${1:-status}"
      [ "$#" -gt 0 ] && shift
      local operation="boot.cron.status" boot_action="" confirmed=0 plan_id=""
      case "$action" in
        status|validate) [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng boot cron $action"; return 2; }
          [ "$action" = "validate" ] && operation="boot.cron.validate" ;;
        preview)
          [ "$#" -eq 1 ] && { [ "$1" = "enable" ] || [ "$1" = "disable" ]; } || { nt_fail "Usage: tx mng boot cron preview {enable|disable}"; return 2; }
          operation="boot.cron.preview"; boot_action="$1" ;;
        enable|disable)
          operation="boot.cron.$action"
          while [ "$#" -gt 0 ]; do
            case "$1" in
              --yes) confirmed=1; shift ;;
              --plan-id) [ "$#" -ge 2 ] || { nt_fail "--plan-id requires the exact preview ID"; return 2; }; plan_id="$2"; shift 2 ;;
              *) nt_fail "Unknown boot integration option: $1"; return 2 ;;
            esac
          done
          [ "$confirmed" -eq 1 ] && [ -n "$plan_id" ] || { nt_fail "Preview first, then confirm with --yes --plan-id PLAN_ID."; return 2; } ;;
        *) nt_fail "Use tx mng boot cron {status|validate|preview|enable|disable}."; return 2 ;;
      esac
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      local -a boot_args=(--operation "$operation")
      [ -z "$boot_action" ] || boot_args+=(--boot-action "$boot_action")
      [ "$confirmed" -eq 0 ] || boot_args+=(--yes --plan-id "$plan_id")
      python3 "$_TN_LIB_DIR/management_service.py" "${boot_args[@]}" --json
      ;;
    hermes)
      local action="${1:-}"
      [ "$#" -gt 0 ] && shift
      [ "$action" = "status" ] && [ "$#" -eq 0 ] || { nt_fail "Usage: tx mng hermes status"; return 2; }
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      python3 "$_TN_LIB_DIR/management_service.py" --operation agent.hermes.status --json
      ;;
    doctor)
      local graphics_flag=""
      [ "$#" -le 1 ] || { nt_fail "Usage: tx mng doctor [--graphics]"; return 2; }
      [ "${1:-}" != "--graphics" ] || graphics_flag="--graphics"
      [ -z "${1:-}" ] || [ -n "$graphics_flag" ] || { nt_fail "Usage: tx mng doctor [--graphics]"; return 2; }
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      python3 "$_TN_LIB_DIR/management_service.py" --operation doctor.report $graphics_flag --json
      ;;
    web)
      local port=8765 show_secret_fallback=0 browser=choose
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --port) [ "$#" -ge 2 ] || { nt_fail "--port requires a value."; return 2; }; port="$2"; shift 2 ;;
          --browser) [ "$#" -ge 2 ] || { nt_fail "--browser requires choose, android, native, or auto."; return 2; }; browser="$2"; shift 2 ;;
          --show-secret-on-clipboard-failure) show_secret_fallback=1; shift ;;
          --help|-h) nt_help web; return 0 ;;
          *) nt_fail "Unknown Web UI option: $1"; return 2 ;;
        esac
      done
      nt_require_termux || return 1
      nt_require_command python3 || return 1
      local -a web_args=(--port "$port" --web --browser "$browser")
      [ "$show_secret_fallback" -eq 0 ] || web_args+=(--show-secret-on-clipboard-failure)
      python3 "$_TN_LIB_DIR/management_http_runtime.py" "${web_args[@]}"
      ;;
    http)
      local action="${1:-}"
      [ "$#" -gt 0 ] && shift
      case "$action" in
        serve)
          local port=8765
          while [ "$#" -gt 0 ]; do
            case "$1" in
              --port)
                [ "$#" -ge 2 ] || { nt_fail "--port requires a value."; return 2; }
                port="$2"; shift 2 ;;
              --help|-h) nt_help management; return 0 ;;
              *) nt_fail "Unknown management HTTP option: $1"; return 2 ;;
            esac
          done
          nt_require_termux || return 1
          nt_require_command python3 || return 1
          python3 "$_TN_LIB_DIR/management_http_runtime.py" --port "$port"
          ;;
        --help|-h|"") nt_help management ;;
        *) nt_fail "Use 'tx mng center', 'tx mng catalog list', 'tx mng logs', 'tx mng doctor', 'tx mng shortcuts', or 'tx mng http serve'."; return 2 ;;
      esac
      ;;
    --help|-h|"") nt_help management ;;
    *) nt_fail "Use 'tx mng center', 'tx mng catalog list', 'tx mng logs', 'tx mng doctor', 'tx mng shortcuts', or 'tx mng http serve'."; return 2 ;;
  esac
}

nt_cmd_web() { nt_cmd_management web "$@"; }
