#!/data/data/com.termux/files/usr/bin/bash
# Ternuxx-owned session supervisor. Only process groups it created are stopped.
set -u
umask 077

DISPLAY_VALUE="${1:-}"
STATE_DIR="${2:-}"
TMP_ROOT="${3:-}"
X11_BIN="${4:-}"
DBUS_LAUNCH_BIN="${5:-}"
XFCE_BIN="${6:-}"
OWNED_EXEC_BIN="${7:-}"
STATE_FILE="$STATE_DIR/session.json"
X11_PID=""
X11_TICKS=""
X11_PGID=""
X11_SID=""
DESKTOP_PID=""
DESKTOP_TICKS=""
DESKTOP_PGID=""
DESKTOP_SID=""
DESKTOP_MARKER="${8:-xfce4-session}"
PROVIDER="${9:-native}"
DESKTOP_ID="${10:-${TERNUXX_DESKTOP_ID:-xfce}}"
STOP_REASON=""
STARTUP_FAILED=0

fail() {
  STOP_REASON="$1"
  STARTUP_FAILED=1
  cleanup
  exit 1
}

proc_values() {
  local pid="$1" stat rest
  [ -r "/proc/$pid/stat" ] || return 1
  IFS= read -r stat < "/proc/$pid/stat" || return 1
  rest="${stat##*) }"
  set -- $rest
  [ "$#" -ge 20 ] || return 1
  # After removing pid and comm, rest[0..] starts at proc stat field 3.
  printf '%s %s %s\n' "${20}" "${3}" "${4}"
}

proc_ticks() { proc_values "$1" | awk '{print $1}'; }
proc_pgid() { proc_values "$1" | awk '{print $2}'; }
proc_sid()  { proc_values "$1" | awk '{print $3}'; }

proc_cmdline() {
  local pid="$1"
  [ -r "/proc/$pid/cmdline" ] || return 1
  tr '\000' ' ' < "/proc/$pid/cmdline" 2>/dev/null
}

matches_owned_process() {
  local pid="$1" ticks="$2" marker="$3" actual command
  [ -n "$pid" ] && [ -n "$ticks" ] || return 1
  actual="$(proc_ticks "$pid")" || return 1
  [ "$actual" = "$ticks" ] || return 1
  command="$(proc_cmdline "$pid")" || return 1
  [[ "$command" == *"$marker"* ]]
}

capture_owned_group() {
  local pid="$1" marker="$2" attempt ticks pgid sid
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    ticks="$(proc_ticks "$pid" 2>/dev/null || true)"
    pgid="$(proc_pgid "$pid" 2>/dev/null || true)"
    sid="$(proc_sid "$pid" 2>/dev/null || true)"
    if [ -n "$ticks" ] && [ "$pid" = "$pgid" ] && [ "$pgid" = "$sid" ] &&
       matches_owned_process "$pid" "$ticks" "$marker"; then
      printf '%s %s %s\n' "$ticks" "$pgid" "$sid"
      return 0
    fi
    sleep 0.05
  done
  return 1
}

group_has_live_process() {
  local wanted="$1" path stat rest pgid visible=0
  for path in /proc/[0-9]*/stat; do
    [ -r "$path" ] || continue
    visible=$((visible + 1))
    IFS= read -r stat < "$path" || continue
    rest="${stat##*) }"
    set -- $rest
    [ "$#" -ge 3 ] || continue
    case "$1" in Z|X) continue ;; esac
    pgid="$3"
    [ "$pgid" = "$wanted" ] && return 0
  done
  [ "$visible" -gt 0 ] || return 2
  return 1
}

cleanup_owned_display_artifacts() {
  local number socket lock lock_pid rc
  [[ "$DISPLAY_VALUE" =~ ^:[0-9]{1,2}$ ]] || return 1
  [ -n "$X11_PID" ] && [ -n "$X11_TICKS" ] && [ -n "$X11_PGID" ] && [ -n "$X11_SID" ] || return 0

  # The display files may be removed only after the exact server process group
  # recorded for this session is gone. A non-empty/unknown group fails closed.
  group_has_live_process "$X11_PGID"; rc=$?
  [ "$rc" -eq 1 ] || return 1

  number="${DISPLAY_VALUE#:}"
  socket="$TMP_ROOT/.X11-unix/X$number"
  lock="$TMP_ROOT/.X$number-lock"
  [ -e "$socket" ] || [ -e "$lock" ] || return 0

  # Termux:X11's lock records the server PID. Requiring it to match the
  # recorded child prevents deleting a socket left by an unrelated server.
  [ -f "$lock" ] || return 1
  lock_pid="$(tr -d '[:space:]' < "$lock" 2>/dev/null)"
  [ "$lock_pid" = "$X11_PID" ] || return 1
  [[ "$lock_pid" =~ ^[0-9]+$ ]] || return 1

  if [ -e "$socket" ]; then
    [ -S "$socket" ] || return 1
    rm -f -- "$socket" || return 1
  fi
  rm -f -- "$lock" || return 1
}

write_state() {
  local phase="$1" error_text="${2:-}"
  python3 - "$STATE_FILE" "$phase" "$DISPLAY_VALUE" "$$" "$(proc_ticks "$$")" \
    "$X11_PID" "$X11_TICKS" "$X11_PGID" "$X11_SID" \
    "$DESKTOP_PID" "$DESKTOP_TICKS" "$DESKTOP_PGID" "$DESKTOP_SID" "$error_text" "$DESKTOP_MARKER" "$PROVIDER" "$DESKTOP_ID" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

(path, phase, display, supervisor_pid, supervisor_ticks, x11_pid, x11_ticks,
 x11_pgid, x11_sid, desktop_pid, desktop_ticks, desktop_pgid, desktop_sid,
 error, desktop_marker, provider, desktop_id) = sys.argv[1:]
def role(pid, ticks, pgid, sid, marker):
    return {"pid": int(pid) if pid else None, "start_ticks": ticks or None,
            "pgid": int(pgid) if pgid else None, "sid": int(sid) if sid else None,
            "command_marker": marker}
state = {
    "schema": 2, "owner": "ternuxx", "provider": provider,
    "display": display, "status": phase, "desktop_id": desktop_id,
    "supervisor": {"pid": int(supervisor_pid), "start_ticks": supervisor_ticks,
                   "command_marker": "desktop-supervisor.sh"},
    "x11": role(x11_pid, x11_ticks, x11_pgid, x11_sid, "termux-x11"),
    "desktop": role(desktop_pid, desktop_ticks, desktop_pgid, desktop_sid, desktop_marker),
    "error": error or None, "updated_at": datetime.now(timezone.utc).isoformat(),
}
fd, temporary = tempfile.mkstemp(prefix=".session.", dir=os.path.dirname(path))
try:
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2)
        stream.write("\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
finally:
    try: os.unlink(temporary)
    except FileNotFoundError: pass
PY
}

stop_group() {
  local pid="$1" ticks="$2" marker="$3" pgid="$4" sid="$5" attempt rc
  [ -n "$pid" ] && [ -n "$pgid" ] && [ -n "$sid" ] || return 0
  matches_owned_process "$pid" "$ticks" "$marker" || return 0
  [ "$pid" = "$pgid" ] && [ "$pgid" = "$sid" ] || return 1
  [ "$(proc_pgid "$pid")" = "$pgid" ] && [ "$(proc_sid "$pid")" = "$sid" ] || return 1
  matches_owned_process "$pid" "$ticks" "$marker" || return 1
  kill -TERM -- "-$pgid" 2>/dev/null || return 1
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    group_has_live_process "$pgid"; rc=$?
    [ "$rc" -eq 1 ] && return 0
    [ "$rc" -eq 2 ] && return 1
    sleep 0.2
  done
  group_has_live_process "$pgid"; rc=$?
  [ "$rc" -eq 1 ]
}

cleanup() {
  local failed=0
  trap - TERM INT HUP
  stop_group "$DESKTOP_PID" "$DESKTOP_TICKS" "$DESKTOP_MARKER" "$DESKTOP_PGID" "$DESKTOP_SID" || failed=1
  stop_group "$X11_PID" "$X11_TICKS" "termux-x11" "$X11_PGID" "$X11_SID" || failed=1
  if [ "$failed" -eq 0 ]; then
    cleanup_owned_display_artifacts || failed=1
  fi
  if [ "$failed" -ne 0 ]; then
    write_state stop_incomplete "${STOP_REASON:-owned process group did not exit or could not be verified}"
  elif [ "$STARTUP_FAILED" -eq 1 ]; then
    write_state failed "$STOP_REASON"
  else
    write_state stopped "${STOP_REASON:-}"
  fi
}

on_signal() {
  STOP_REASON="received stop signal"
  cleanup
  exit 0
}
trap on_signal TERM INT HUP

[[ "$DISPLAY_VALUE" =~ ^:[0-9]{1,2}$ ]] || fail "invalid display"
[[ "$PROVIDER" = native || "$PROVIDER" = proot ]] || fail "unsupported desktop provider"
[ -d "$STATE_DIR" ] || fail "state directory missing"
[ -d "$TMP_ROOT/.X11-unix" ] || fail "Termux X11 socket directory missing"
[ -x "$X11_BIN" ] || fail "termux-x11 executable missing"
[ -x "$DBUS_LAUNCH_BIN" ] || fail "dbus-launch executable missing"
[ -x "$XFCE_BIN" ] || fail "desktop session executable missing"
if [[ "$PROVIDER" == native ]]; then
  PYTHONPATH="$(dirname "$0")" python3 - "$DESKTOP_ID" "$DESKTOP_MARKER" "$XFCE_BIN" <<'PY_NATIVE' || fail "Native desktop identity is not allowlisted"
import native_desktops, sys
item = native_desktops.NATIVE_DESKTOPS.get(sys.argv[1])
if not item or item["command"] != sys.argv[2] or not sys.argv[3].endswith("/" + item["command"]):
    raise SystemExit(1)
PY_NATIVE
fi
[ -x "$OWNED_EXEC_BIN" ] || fail "owned process launcher missing"

write_state starting
"$OWNED_EXEC_BIN" "$X11_BIN" "$DISPLAY_VALUE" >> "$STATE_DIR/desktop.log" 2>&1 &
X11_PID="$!"
x11_identity="$(capture_owned_group "$X11_PID" "termux-x11")" || fail "could not verify Termux:X11 owned process group"
read -r X11_TICKS X11_PGID X11_SID <<EOF_ID
$x11_identity
EOF_ID
write_state starting

socket="$TMP_ROOT/.X11-unix/X${DISPLAY_VALUE#:}"
ready=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  [ -S "$socket" ] && { ready=1; break; }
  matches_owned_process "$X11_PID" "$X11_TICKS" "termux-x11" || fail "Termux:X11 exited before its display socket became ready"
  sleep 0.25
done
[ "$ready" -eq 1 ] || fail "Termux:X11 display socket did not become ready"

mkdir -p "$STATE_DIR/$DESKTOP_ID/config" "$STATE_DIR/$DESKTOP_ID/cache" "$STATE_DIR/$DESKTOP_ID/data" "$STATE_DIR/$DESKTOP_ID/runtime"
chmod 700 "$STATE_DIR/$DESKTOP_ID" "$STATE_DIR/$DESKTOP_ID/config" "$STATE_DIR/$DESKTOP_ID/cache" "$STATE_DIR/$DESKTOP_ID/data" "$STATE_DIR/$DESKTOP_ID/runtime" 2>/dev/null || true

if [[ "$PROVIDER" == native ]]; then
  case "$DESKTOP_ID" in
    xfce) CURRENT_DESKTOP=XFCE; SESSION_DESKTOP=xfce; DESKTOP_SESSION=xfce ;;
    lxqt) CURRENT_DESKTOP=LXQt; SESSION_DESKTOP=LXQt; DESKTOP_SESSION=lxqt ;;
    mate) CURRENT_DESKTOP=MATE; SESSION_DESKTOP=MATE; DESKTOP_SESSION=mate ;;
    cinnamon) CURRENT_DESKTOP=X-Cinnamon; SESSION_DESKTOP=X-Cinnamon; DESKTOP_SESSION=cinnamon ;;
    plasma) CURRENT_DESKTOP=KDE; SESSION_DESKTOP=KDE; DESKTOP_SESSION=plasma ;;
    *) fail "unsupported Native desktop environment" ;;
  esac
else
  case "$DESKTOP_ID" in
    xfce) CURRENT_DESKTOP=XFCE; SESSION_DESKTOP=xfce; DESKTOP_SESSION=xfce ;;
    lxqt) CURRENT_DESKTOP=LXQt; SESSION_DESKTOP=LXQt; DESKTOP_SESSION=lxqt ;;
    lxde) CURRENT_DESKTOP=LXDE; SESSION_DESKTOP=LXDE; DESKTOP_SESSION=lxde ;;
    mate) CURRENT_DESKTOP=MATE; SESSION_DESKTOP=MATE; DESKTOP_SESSION=mate ;;
    gnome) CURRENT_DESKTOP=GNOME; SESSION_DESKTOP=gnome; DESKTOP_SESSION=gnome ;;
    plasma) CURRENT_DESKTOP=KDE; SESSION_DESKTOP=KDE; DESKTOP_SESSION=plasma ;;
    cinnamon) CURRENT_DESKTOP=X-Cinnamon; SESSION_DESKTOP=X-Cinnamon; DESKTOP_SESSION=cinnamon ;;
    *) fail "unsupported PRoot desktop environment" ;;
  esac
fi
DISPLAY="$DISPLAY_VALUE" XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP="$CURRENT_DESKTOP" \
XDG_SESSION_DESKTOP="$SESSION_DESKTOP" DESKTOP_SESSION="$DESKTOP_SESSION" \
XDG_CONFIG_HOME="$STATE_DIR/$DESKTOP_ID/config" XDG_CACHE_HOME="$STATE_DIR/$DESKTOP_ID/cache" \
XDG_DATA_HOME="$STATE_DIR/$DESKTOP_ID/data" XDG_RUNTIME_DIR="$STATE_DIR/$DESKTOP_ID/runtime" \
  "$OWNED_EXEC_BIN" "$DBUS_LAUNCH_BIN" --exit-with-session "$XFCE_BIN" >> "$STATE_DIR/desktop.log" 2>&1 &
DESKTOP_PID="$!"
desktop_identity="$(capture_owned_group "$DESKTOP_PID" "$DESKTOP_MARKER")" || fail "could not verify desktop owned process group"
read -r DESKTOP_TICKS DESKTOP_PGID DESKTOP_SID <<EOF_ID
$desktop_identity
EOF_ID
desktop_ready=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  matches_owned_process "$DESKTOP_PID" "$DESKTOP_TICKS" "$DESKTOP_MARKER" && { desktop_ready=1; break; }
  kill -0 "$DESKTOP_PID" 2>/dev/null || fail "desktop launcher exited before session readiness"
  sleep 0.1
done
[ "$desktop_ready" -eq 1 ] || fail "desktop session process identity did not become verifiable"
write_state running

wait "$DESKTOP_PID"
result=$?
STOP_REASON="$DESKTOP_ID session exited with status $result"
cleanup
exit "$result"
