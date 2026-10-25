# Ternuxx native desktop lifecycle.
# Owns only the supervisor and exact child processes recorded in session.json.
. "$(dirname "${BASH_SOURCE[0]}")/core.sh"

_nt_session_file() { printf '%s/session.json\n' "$TERNUXX_STATE_DIR"; }

_nt_adopt_live_session_state() {
  [ -f "$TERNUXX_STATE_DIR/session.json" ] && return 0
  [ -n "${TERMUX_VERSION:-}" ] && [ "${PREFIX:-}" = "/data/data/com.termux/files/usr" ] || return 0
  local discovered
  discovered="$(python3 "$_TN_LIB_DIR/desktop_session_discovery.py" "$_TN_LIB_DIR/desktop-supervisor.sh" "$HOME" "$TERNUXX_STATE_DIR" 2>/dev/null)" || return 0
  [ -n "$discovered" ] || return 0
  TERNUXX_STATE_DIR="$discovered"
  export TERNUXX_STATE_DIR
}
_nt_journal_begin() {
  python3 "$_TN_LIB_DIR/operation_journal.py" begin "$TERNUXX_STATE_DIR" "$1" "$2"
}
_nt_journal_update() {
  python3 "$_TN_LIB_DIR/operation_journal.py" update "$TERNUXX_STATE_DIR" "$1" "$2" "$3"
}
_nt_session_lock() { printf '%s/.session.lock\n' "$TERNUXX_STATE_DIR"; }
_NT_ACTIVE_SESSION_LOCK=""

_nt_release_session_lock() {
  [ -n "${_NT_ACTIVE_SESSION_LOCK:-}" ] || return 0
  rmdir "$_NT_ACTIVE_SESSION_LOCK" 2>/dev/null || true
  _NT_ACTIVE_SESSION_LOCK=""
}

_nt_state_value() {
  local key="$1" file
  file="$(_nt_session_file)"
  [ -f "$file" ] || return 1
  python3 - "$file" "$key" <<'PY'
import json
import sys
try:
    with open(sys.argv[1], encoding="utf-8") as stream:
        value = json.load(stream)
    current = value
    for part in sys.argv[2].split("."):
        current = current[part]
    if current is None:
        raise SystemExit(1)
    print(current)
except (OSError, ValueError, KeyError, TypeError):
    raise SystemExit(1)
PY
}

_nt_proc_start_ticks() {
  local pid="$1" stat rest
  [ -r "/proc/$pid/stat" ] || return 1
  IFS= read -r stat < "/proc/$pid/stat" || return 1
  rest="${stat##*) }"
  set -- $rest
  [ "$#" -ge 20 ] || return 1
  printf '%s\n' "${20}"
}

_nt_proc_matches() {
  local pid="$1" expected_ticks="$2" marker="$3" actual_ticks command
  [ -n "$pid" ] && [ -n "$expected_ticks" ] || return 1
  actual_ticks="$(_nt_proc_start_ticks "$pid")" || return 1
  [ "$actual_ticks" = "$expected_ticks" ] || return 1
  [ -r "/proc/$pid/cmdline" ] || return 1
  command="$(tr '\000' ' ' < "/proc/$pid/cmdline")"
  [[ "$command" == *"$marker"* ]]
}

_nt_state_process_live() {
  local role="$1" pid ticks marker
  pid="$(_nt_state_value "$role.pid")" || return 1
  ticks="$(_nt_state_value "$role.start_ticks")" || return 1
  marker="$(_nt_state_value "$role.command_marker")" || return 1
  _nt_proc_matches "$pid" "$ticks" "$marker"
}

_nt_owned_stop() {
  local role="$1" pid ticks marker
  pid="$(_nt_state_value "$role.pid")" || return 0
  ticks="$(_nt_state_value "$role.start_ticks")" || return 0
  marker="$(_nt_state_value "$role.command_marker")" || return 0
  [ "$pid" != "None" ] && [ -n "$pid" ] || return 0
  if ! _nt_proc_matches "$pid" "$ticks" "$marker"; then
    return 0
  fi
  kill -TERM "$pid" 2>/dev/null || return 1
  local attempt
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    _nt_proc_matches "$pid" "$ticks" "$marker" || return 0
    sleep 0.2
  done
  return 1
}

_nt_display_available() {
  local number="$1" tmp_root="${TMPDIR:-/data/data/com.termux/files/usr/tmp}"
  local helper="${_TN_LIB_DIR:-}/x11_display.py" result
  if [ -f "$helper" ]; then
    result="$(python3 "$helper" "$tmp_root" "$number" 2>/dev/null)" || return 1
    [ "$result" = "available" ]
    return $?
  fi
  [ ! -e "$tmp_root/.X11-unix/X$number" ] || return 1
  [ ! -e "$tmp_root/.X$number-lock" ] || return 1
}

_nt_request_termux_x11_activity() {
  local termux_am="${PREFIX:-/data/data/com.termux/files/usr}/bin/am"
  if [ ! -x "$termux_am" ]; then
    nt_warn "Termux activity launcher is unavailable; desktop processes are running. Open Termux:X11 manually."
    return 1
  fi
  if "$termux_am" start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1; then
    nt_info "Requested the Termux:X11 activity; actual GUI visibility remains unknown."
    return 0
  fi
  nt_warn "Termux did not accept the Termux:X11 activity request; desktop processes are running. Open Termux:X11 manually."
  return 1
}

_nt_state_path_is_private() {
  python3 - "$HOME" "$TERNUXX_STATE_DIR" <<'PY'
import os, sys
home = os.path.realpath(sys.argv[1])
state = os.path.realpath(sys.argv[2])
raise SystemExit(0 if state.startswith(home.rstrip(os.sep) + os.sep) else 1)
PY
}

_nt_session_active() {
  [ -f "$(_nt_session_file)" ] || return 1
  _nt_state_process_live supervisor
}

_nt_native_graphics_prefix() {
  local config="$TERNUXX_STATE_DIR/native-graphics-prefix" prefix
  local candidate="$TERNUXX_STATE_DIR/graphics/providers/native-mesa-0219ff84/extracted/data/data/com.termux/files/usr"
  [ -f "$config" ] && [ ! -L "$config" ] || return 1
  IFS= read -r prefix < "$config" || return 1
  [[ "$prefix" = /* && "$prefix" != *$'\n'* ]] || return 1
  [ -d "$prefix" ] && [ ! -L "$prefix" ] || return 1
  [ -f "$prefix/lib/dri/libdril_dri.so" ] && [ -f "$prefix/lib/libgallium-26.3.0-devel.so" ] || return 1
  [ -f "$prefix/share/glvnd/egl_vendor.d/50_mesa.json" ] || return 1
  printf '%s\n' "$prefix"
}

_nt_native_zink_icd() {
  local selection="$TERNUXX_STATE_DIR/native-graphics-backend"
  local icd="$PREFIX/share/vulkan/icd.d/freedreno_icd.aarch64.json"
  local library="$PREFIX/lib/libvulkan_freedreno.so"
  local -a gallium=("$PREFIX"/lib/libgallium-*.so)
  [ -f "$selection" ] && [ ! -L "$selection" ] || return 1
  [ "$(cat "$selection")" = termux-zink ] || return 1
  [ -f "$PREFIX/lib/dri/libdril_dri.so" ] && [ ! -L "$PREFIX/lib/dri/libdril_dri.so" ] || return 1
  [ -f "$library" ] && [ ! -L "$library" ] || return 1
  [ -f "$icd" ] && [ ! -L "$icd" ] || return 1
  [ "${#gallium[@]}" -eq 1 ] && [ -f "${gallium[0]}" ] && [ ! -L "${gallium[0]}" ] || return 1
  python3 - "$icd" "$library" <<'PYICD'
import json, os, stat, sys
icd, library = sys.argv[1:]
try:
    if stat.S_ISLNK(os.lstat(icd).st_mode) or stat.S_ISLNK(os.lstat(library).st_mode): raise ValueError
    value=json.load(open(icd, encoding="utf-8"))["ICD"]["library_path"]
    if not isinstance(value, str): raise ValueError
    valid=os.path.realpath(value)==os.path.realpath(library) if os.path.isabs(value) else value=="libvulkan_freedreno.so"
    raise SystemExit(0 if valid else 1)
except (OSError, ValueError, KeyError, TypeError):
    raise SystemExit(1)
PYICD
}

nt_cmd_graphics() {
  local target="${1:-}" action="${2:-}" prefix="" expected="$TERNUXX_STATE_DIR/graphics/providers/native-mesa-0219ff84/extracted/data/data/com.termux/files/usr" arg
  [ "$target" = native ] || { nt_fail "Use 'tx mng graphics status|verify|select' for shared graphics management."; return 2; }
  shift; [ "$#" -gt 0 ] && shift
  case "$action" in
    status)
      [ "$#" -eq 0 ] || { nt_fail "Usage: tx graphics native status"; return 2; }
      python3 "$_TN_LIB_DIR/management_service.py" --operation graphics.provider.status --provider native --json
      ;;
    enable)
      while [ "$#" -gt 0 ]; do
        arg="$1"; shift
        case "$arg" in
          --prefix) [ "$#" -gt 0 ] || { nt_fail "--prefix needs a path"; return 2; }; prefix="$1"; shift ;;
          *) nt_fail "Unknown graphics option: $arg"; return 2 ;;
        esac
      done
      [ "$prefix" = "$expected" ] || { nt_fail "Only the qualified KGSL candidate is selectable through shared management."; return 2; }
      python3 "$_TN_LIB_DIR/management_service.py" --operation graphics.provider.select --provider native --graphics-backend kgsl-freedreno --yes --json
      ;;
    disable)
      [ "$#" -eq 0 ] || { nt_fail "Usage: tx graphics native disable"; return 2; }
      python3 "$_TN_LIB_DIR/management_service.py" --operation graphics.provider.select --provider native --graphics-backend system --yes --json
      ;;
    *) nt_fail "Use 'tx mng graphics status|verify|select'."; return 2 ;;
  esac
}

nt_cmd_start() {
  local display_number="" arg state_root supervisor owned_exec log_file tmp_root operation_id mesa_prefix=""
  local -a launch_env=()
  local stale_display="" stale_display_number="" stale_x11_pid="" stale_artifact_state=""
  while [ $# -gt 0 ]; do
    arg="$1"; shift
    case "$arg" in
      --display)
        [ $# -gt 0 ] || { nt_fail "--display needs a number"; return 2; }
        display_number="${1#:}"; shift
        [[ "$display_number" =~ ^[0-9]{1,2}$ ]] || { nt_fail "Invalid display number"; return 2; }
        ;;
      *) nt_fail "Unknown start option: $arg"; return 2 ;;
    esac
  done

  nt_require_termux || return 1
  for tool in termux-x11 dbus-launch xfce4-session python3 nohup setsid; do
    nt_require_command "$tool" || return 1
  done
  supervisor="$_TN_LIB_DIR/desktop-supervisor.sh"
  owned_exec="$_TN_LIB_DIR/owned-exec.py"
  [ -x "$supervisor" ] || { nt_fail "Ternuxx session supervisor is missing"; return 1; }
  [ -x "$owned_exec" ] || { nt_fail "Ternuxx owned-process launcher is missing"; return 1; }

  _nt_adopt_live_session_state
  state_root="$TERNUXX_STATE_DIR"
  python3 "$_TN_LIB_DIR/desktop_session_state.py" ensure-state "$HOME" "$state_root" >/dev/null 2>&1 || {
    nt_fail "Ternuxx state path is unsafe or cannot be made private; no session file or process was changed."; return 1;
  }

  local lock session_report session_state
  lock="$(_nt_session_lock)"
  if ! (umask 077 && mkdir "$lock") 2>/dev/null; then
    nt_fail "Another Ternuxx lifecycle operation holds the session lock. If no operation is running, inspect and recover the lock manually."; return 1
  fi
  _NT_ACTIVE_SESSION_LOCK="$lock"
  trap '_nt_release_session_lock' EXIT

  session_report="$(python3 "$_TN_LIB_DIR/desktop_session_state.py" inspect "$HOME" "$state_root" /proc "${TMPDIR:-/data/data/com.termux/files/usr/tmp}" 2>/dev/null)" || {
    nt_fail "Session ownership or process identity is unknown or unsafe. Processes and state were preserved; inspect session.json and desktop.log."; return 1;
  }
  session_state="$(printf '%s' "$session_report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("state", "unknown"))')"
  case "$session_state" in
    running)
      local active_display
      active_display="$(_nt_state_value display)"
      _nt_use audio && nt_audio_ensure || true
      nt_ok "Ternuxx desktop is already running and its recorded process and display identities are verified."
      nt_info "Display: $active_display"
      if [ "$TERNUXX_JSON" = "1" ]; then
        nt_json_object "start" "running" "display" "$active_display" "activity_request" "disabled_by_default" "gui_visible" "unknown" "audio_owner" "ternuxx-native"
      fi
      return 0 ;;
    stale)
      stale_display="$(_nt_state_value display 2>/dev/null || true)"
      stale_x11_pid="$(_nt_state_value x11.pid 2>/dev/null || true)"
      session_report="$(python3 "$_TN_LIB_DIR/desktop_session_state.py" reconcile-stale "$HOME" "$state_root" /proc "${TMPDIR:-/data/data/com.termux/files/usr/tmp}" 2>/dev/null)" || {
        nt_fail "Stale session evidence changed or could not be reconciled safely; no process was started."; return 1;
      }
      case "$stale_display" in
        :1|:2|:3|:4|:5|:6|:7|:8|:9|:10) stale_display_number="${stale_display#:}" ;;
      esac
      if [ -n "$stale_display_number" ] && [[ "$stale_x11_pid" =~ ^[0-9]+$ ]]; then
        stale_artifact_state="$(python3 "$_TN_LIB_DIR/x11_display.py" recover "${TMPDIR:-/data/data/com.termux/files/usr/tmp}" "$stale_display_number" "$stale_x11_pid" 2>/dev/null)" || stale_artifact_state=busy
        case "$stale_artifact_state" in
          recovered) nt_warn "Reconciled the exact stale Ternuxx :$stale_display_number socket/lock pair using its recorded, absent X11 PID." ;;
          available) nt_warn "Reconciled the stale Ternuxx session; its recorded display artifacts were already absent." ;;
          *) nt_fail "Stale session record was reconciled, but display :$stale_display_number artifacts did not match the exact recorded dead X11 PID; no display was started."; return 1 ;;
        esac
      else
        nt_fail "Stale session display/PID evidence is not eligible for automatic cleanup; no display was started."; return 1
      fi ;;
    stopped) ;;
    starting|stopping)
      nt_fail "A Ternuxx desktop lifecycle operation is $session_state; no duplicate session was started."; return 1 ;;
    failed)
      nt_fail "The prior Ternuxx session is failed. Review $state_root/desktop.log and session.json; no process was signaled."; return 1 ;;
    *)
      nt_fail "Session state is $session_state and cannot be safely reconciled. Processes and files were preserved."; return 1 ;;
  esac

  tmp_root="${TMPDIR:-/data/data/com.termux/files/usr/tmp}"
  if [ -f "$_TN_LIB_DIR/x11_display.py" ]; then
    python3 "$_TN_LIB_DIR/x11_display.py" ensure-directory "$tmp_root" >/dev/null 2>&1 || {
      nt_fail "Native X11 socket directory is unsafe or unavailable; no display process was started."; return 1;
    }
  fi
  if [ -z "$display_number" ]; then
    display_number="$(nt_find_free_display)" || { nt_fail "Canonical Native Termux display :1 is occupied or ambiguous; inspect its owner instead of starting a duplicate display."; return 1; }
  fi
  _nt_display_available "$display_number" || { nt_fail "Display :$display_number has a socket or lock; refusing to reuse it"; return 1; }

  _nt_use audio && nt_audio_ensure || true

  if [ -e "$TERNUXX_STATE_DIR/native-graphics-backend" ] || [ -L "$TERNUXX_STATE_DIR/native-graphics-backend" ]; then
    if [ -e "$TERNUXX_STATE_DIR/native-graphics-prefix" ] || [ -L "$TERNUXX_STATE_DIR/native-graphics-prefix" ] \
      || ! _nt_native_zink_icd; then
      nt_fail "Saved Native Zink selection is missing, conflicting, or unsafe; no desktop process was started."; return 1
    fi
    local zink_icd="$PREFIX/share/vulkan/icd.d/freedreno_icd.aarch64.json"
    launch_env+=("MESA_LOADER_DRIVER_OVERRIDE=zink" "GALLIUM_DRIVER=zink" "TU_DEBUG=noconform" \
      "MESA_VK_WSI_DEBUG=sw" "VK_ICD_FILENAMES=$zink_icd")
    nt_info "Applying the selected Termux Mesa Zink backend with the Freedreno ICD to this desktop session."
  fi
  if [ -e "$TERNUXX_STATE_DIR/native-graphics-prefix" ] || [ -L "$TERNUXX_STATE_DIR/native-graphics-prefix" ]; then
    mesa_prefix="$(_nt_native_graphics_prefix 2>/dev/null)" || {
      nt_fail "Saved Native graphics candidate is missing or unsafe; no desktop process was started."; return 1;
    }
  fi
  if [ -n "$mesa_prefix" ]; then
    launch_env=("LD_LIBRARY_PATH=$mesa_prefix/lib:$PREFIX/lib"
      "LIBGL_DRIVERS_PATH=$mesa_prefix/lib/dri"
      "MESA_LOADER_DRIVER_OVERRIDE=kgsl"
      "__EGL_VENDOR_LIBRARY_FILENAMES=$mesa_prefix/share/glvnd/egl_vendor.d/50_mesa.json"
      "GLX_VENDOR_LIBRARY_NAME=mesa" "MESA_SHADER_CACHE_DISABLE=true")
    local candidate_prefix="$TERNUXX_STATE_DIR/graphics/providers/native-mesa-0219ff84/extracted/data/data/com.termux/files/usr"
    local candidate_icd="$TERNUXX_STATE_DIR/graphics/providers/native-mesa-0219ff84/freedreno-isolated.json"
    if [ "$mesa_prefix" = "$candidate_prefix" ] && [ -f "$candidate_icd" ] && [ ! -L "$candidate_icd" ] \
      && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); raise SystemExit(0 if d.get("ICD",{}).get("library_path")==sys.argv[2] else 1)' \
        "$candidate_icd" "$mesa_prefix/lib/libvulkan_freedreno.so" 2>/dev/null; then
      launch_env+=("VK_ICD_FILENAMES=$candidate_icd")
    fi
    nt_info "Applying the saved Native KGSL graphics candidate to this desktop session."
  fi

  operation_id="$(_nt_journal_begin desktop.start "display :$display_number")" || { nt_fail "Could not write durable operation journal; no desktop process was started"; return 1; }
  log_file="$state_root/desktop.log"
  touch "$log_file" || { _nt_journal_update "$operation_id" failed "desktop log could not be created" || true; nt_fail "Cannot create the Ternuxx desktop log"; return 1; }
  chmod 600 "$log_file" 2>/dev/null || true
  rm -f "$state_root/session.ready" 2>/dev/null || true
  nt_step "Starting Ternuxx-owned X11 and XFCE on :$display_number..."
  nohup setsid env "${launch_env[@]}" "$supervisor" ":$display_number" "$state_root" "$tmp_root" \
    "$(command -v termux-x11)" "$(command -v dbus-launch)" \
    "$(command -v xfce4-session)" "$owned_exec" >> "$log_file" 2>&1 </dev/null &

  local ready=0 result
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
    result="$(_nt_state_value status 2>/dev/null || true)"
    if [ "$result" = "running" ]; then
      ready=1
      break
    fi
    if [ "$result" = "failed" ] || [ "$result" = "stop_incomplete" ]; then
      _nt_journal_update "$operation_id" failed "supervisor reported $result" || true
      nt_fail "Desktop startup failed (state: $result). Review $log_file and session.json; no unrelated process was stopped."
      return 1
    fi
    sleep 0.25
  done
  if [ "$ready" -ne 1 ]; then
    local pid ticks
    pid="$(_nt_state_value supervisor.pid 2>/dev/null || true)"
    ticks="$(_nt_state_value supervisor.start_ticks 2>/dev/null || true)"
    if _nt_proc_matches "$pid" "$ticks" "desktop-supervisor.sh"; then
      kill -TERM "$pid" 2>/dev/null || true
      for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
        _nt_proc_matches "$pid" "$ticks" "desktop-supervisor.sh" || break
        sleep 0.2
      done
    fi
    _nt_journal_update "$operation_id" needs_recovery "startup readiness timed out; inspect session and log" || true
    nt_fail "Desktop did not report ready within 7.5 seconds. Inspect $log_file and session.json; do not delete sockets or kill untracked processes."
    return 1
  fi

  _nt_journal_update "$operation_id" complete "desktop reported running on :$display_number" || { nt_fail "Desktop is running but journal completion failed; Doctor will report recovery required"; return 1; }
  nt_ok "Ternuxx desktop session is running on :$display_number."
  nt_info "Termux:X11 Activity launch is disabled by default; open the app manually if needed."
  nt_info "GUI visibility remains unknown until the Termux:X11 window is actually visible."
  nt_info "Native PulseAudio is managed independently; tx stop leaves it running for active clients."
  if [ "$TERNUXX_JSON" = "1" ]; then
    nt_json_object "start" "running" "display" ":$display_number" "activity_request" "disabled_by_default" "gui_visible" "unknown" "audio_owner" "ternuxx-native"
  fi
}

nt_cmd_stop() {
  nt_require_termux || return 1
  _nt_adopt_live_session_state
  local file status supervisor_pid supervisor_ticks lock operation_id
  file="$(_nt_session_file)"
  if [ ! -f "$file" ]; then
    nt_info "No Ternuxx session record exists; no processes were inspected or stopped."
    return 0
  fi

  lock="$(_nt_session_lock)"
  if ! (umask 077 && mkdir "$lock") 2>/dev/null; then
    nt_fail "Another Ternuxx lifecycle operation holds the session lock. If no operation is running, inspect and recover the lock manually."
    return 1
  fi
  _NT_ACTIVE_SESSION_LOCK="$lock"
  trap '_nt_release_session_lock' EXIT

  local ownership_report ownership_state
  ownership_report="$(python3 "$_TN_LIB_DIR/desktop_session_state.py" inspect "$HOME" "$TERNUXX_STATE_DIR" /proc "${TMPDIR:-/data/data/com.termux/files/usr/tmp}" 2>/dev/null)" || {
    nt_fail "Session ownership is unknown or unsafe; stop sent no signals and preserved all state."; _nt_release_session_lock; return 1;
  }
  ownership_state="$(printf '%s' "$ownership_report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("state", "unknown"))')"
  case "$ownership_state" in
    unknown|unsafe)
      nt_fail "Session ownership is $ownership_state; stop sent no signals and preserved all state."; _nt_release_session_lock; return 1 ;;
    stale)
      python3 "$_TN_LIB_DIR/desktop_session_state.py" reconcile-stale "$HOME" "$TERNUXX_STATE_DIR" /proc "${TMPDIR:-/data/data/com.termux/files/usr/tmp}" >/dev/null 2>&1 || {
        nt_fail "Stale session changed during reconciliation; stop sent no signals."; _nt_release_session_lock; return 1;
      } ;;
  esac

  status="$(_nt_state_value status 2>/dev/null || printf unknown)"
  supervisor_pid="$(_nt_state_value supervisor.pid 2>/dev/null || true)"
  supervisor_ticks="$(_nt_state_value supervisor.start_ticks 2>/dev/null || true)"

  operation_id="$(_nt_journal_begin desktop.stop "state $status")" || { nt_fail "Could not write durable operation journal; no desktop process was signaled"; _nt_release_session_lock; return 1; }

  if [ -n "$supervisor_pid" ] && _nt_proc_matches "$supervisor_pid" "$supervisor_ticks" "desktop-supervisor.sh"; then
    nt_step "Stopping the recorded Ternuxx session supervisor..."
    if ! kill -TERM "$supervisor_pid" 2>/dev/null; then
      _nt_journal_update "$operation_id" failed "verified supervisor signal failed" || true
      nt_fail "Could not signal the verified session supervisor"
      _nt_release_session_lock
      return 1
    fi
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
      status="$(_nt_state_value status 2>/dev/null || true)"
      [ "$status" = "stopped" ] && break
      [ "$status" = "stop_incomplete" ] && break
      _nt_proc_matches "$supervisor_pid" "$supervisor_ticks" "desktop-supervisor.sh" || break
      sleep 0.2
    done
    # The supervisor may atomically publish "stopped" just after the last
    # status read and exit before the identity check. Re-read once after exit
    # so a clean shutdown is not misreported as an unconfirmed running state.
    status="$(_nt_state_value status 2>/dev/null || printf unknown)"
  else
    nt_warn "Supervisor is not live with its recorded identity; checking only its exact recorded desktop/X11 child PIDs."
    local failures=0
    _nt_owned_stop desktop || failures=1
    _nt_owned_stop x11 || failures=1
    if [ "$failures" -eq 0 ]; then
      python3 - "$file" <<'PY'
import json, os, sys, tempfile
from datetime import datetime, timezone
path=sys.argv[1]
with open(path, encoding="utf-8") as stream: state=json.load(stream)
state["status"]="stopped"
state["updated_at"]=datetime.now(timezone.utc).isoformat()
fd,tmp=tempfile.mkstemp(prefix=".session.",dir=os.path.dirname(path))
try:
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        json.dump(state,stream,indent=2); stream.write("\n")
    os.chmod(tmp,0o600); os.replace(tmp,path)
finally:
    try: os.unlink(tmp)
    except FileNotFoundError: pass
PY
      status=stopped
    fi
  fi

  # Stop is also called by restart in this same CLI process. Release its lock
  # when the stop operation is complete so restart can acquire it for start;
  # the EXIT trap remains a fallback for any lock still owned at process exit.
  if [ "$status" = stopped ]; then
    _nt_journal_update "$operation_id" complete "owned desktop processes stopped" || { nt_fail "Desktop stopped but journal completion failed; Doctor will report recovery required"; _nt_release_session_lock; return 1; }
  else
    _nt_journal_update "$operation_id" needs_recovery "stop result $status; inspect session and log" || true
  fi
  _nt_release_session_lock

  case "$status" in
    stopped)
      nt_ok "Ternuxx-owned desktop processes stopped. Session record and log were retained."
      [ "$TERNUXX_JSON" = "1" ] && nt_json_object "stop" "stopped" "owner" "ternuxx"
      return 0 ;;
    stop_incomplete)
      nt_fail "An owned process did not exit cleanly. State and log are retained; no SIGKILL or broad cleanup was used."
      return 1 ;;
    *)
      nt_fail "Stop result is not confirmed (state: ${status:-unknown}). Review the session record and log."
      return 1 ;;
  esac
}

nt_cmd_restart() {
  nt_require_termux || return 1
  nt_cmd_stop || return $?
  nt_cmd_start "$@"
}

nt_cmd_status() {
  _nt_adopt_live_session_state
  local file report lifecycle reason display supervisor_live x11_live desktop_live
  file="$(_nt_session_file)"
  report="$(python3 "$_TN_LIB_DIR/desktop_session_state.py" inspect "$HOME" "$TERNUXX_STATE_DIR" /proc "${TMPDIR:-/data/data/com.termux/files/usr/tmp}" 2>/dev/null || true)"
  lifecycle="$(printf '%s' "$report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("state", "unknown"))' 2>/dev/null || printf unknown)"
  reason="$(printf '%s' "$report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("reason", "classification unavailable"))' 2>/dev/null || printf 'classification unavailable')"
  display="$(_nt_state_value display 2>/dev/null || printf none)"
  supervisor_live="$(printf '%s' "$report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("processes", {}).get("supervisor", "absent"))' 2>/dev/null || printf unknown)"
  x11_live="$(printf '%s' "$report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("processes", {}).get("x11", "absent"))' 2>/dev/null || printf unknown)"
  desktop_live="$(printf '%s' "$report" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("processes", {}).get("desktop", "absent"))' 2>/dev/null || printf unknown)"

  if [ "$TERNUXX_JSON" = "1" ]; then
    nt_json_object "status" "$lifecycle" "display" "$display" \
      "supervisor" "$supervisor_live" "x11" "$x11_live" \
      "xfce4_session" "$desktop_live" "reconciliation_state" "$lifecycle" \
      "reconciliation_reason" "$reason" "gui_visible" "unknown" \
      "audio_owner" "ternuxx-native"
  else
    printf '  %-18s %s\n' "Ternuxx:" "$lifecycle"
    printf '  %-18s %s\n' "Display:" "$display"
    printf '  %-18s %s\n' "Supervisor:" "$supervisor_live"
    printf '  %-18s %s\n' "Termux:X11:" "$x11_live"
    printf '  %-18s %s\n' "XFCE session:" "$desktop_live"
    printf '  %-18s %s\n' "Reconciliation:" "$reason"
    printf '  %-18s %s\n' "GUI visible:" "unknown (open/check Termux:X11)"
    printf '  %-18s %s\n' "Audio owner:" "external (not managed)"
  fi
}
