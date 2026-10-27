#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
TMP_ROOT="${TMPDIR:-$PREFIX/tmp}"
STATE_DIR="$HOME/.local/share/ternuxx/proot-display0"
NATIVE_STATE="${TERNUXX_STATE_DIR:-$HOME/.local/share/ternuxx}"
discovered_state="$(python3 "$ROOT/lib/desktop_session_discovery.py" "$ROOT/lib/desktop-supervisor.sh" "$HOME" "$NATIVE_STATE" 2>/dev/null || true)"
[ -z "$discovered_state" ] || NATIVE_STATE="$discovered_state"
STATE_FILE="$STATE_DIR/session.json"
SUPERVISOR="$ROOT/lib/desktop-supervisor.sh"
WRAPPER="$ROOT/lib/proot-xfce-wrapper.sh"
OWNED_EXEC="$ROOT/lib/owned-exec.py"
STATE_HELPER="$ROOT/lib/desktop_session_state.py"
LIFECYCLE_LOCK_HELPER="$ROOT/lib/desktop_lifecycle_lock.py"
DISPLAY_TOOL="$ROOT/lib/x11_display.py"
ACTION="${1:-status}"
shift || true
MODE=auto
DESKTOP_ID=""
DISTRO_ID=debian
EXPLICIT_USER=""
PROFILE_ID=debian-trixie
if [ "$ACTION" = start ]; then
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --mode) [ "$#" -ge 2 ] || { echo "--mode needs auto|standalone|nested" >&2; exit 2; }; MODE="$2"; shift 2 ;;
      --desktop) [ "$#" -ge 2 ] || { echo "--desktop needs an installed desktop ID" >&2; exit 2; }; DESKTOP_ID="$2"; shift 2 ;;
      --user) [ "$#" -ge 2 ] || { echo "--user needs an ordinary guest account" >&2; exit 2; }; EXPLICIT_USER="$2"; shift 2 ;;
      --alias) [ "$#" -ge 2 ] || { echo "--alias needs an installed Ternuxx guest alias" >&2; exit 2; }; DISTRO_ID="$2"; shift 2 ;;
      --help|-h) ACTION=help; shift ;;
      *) echo "Unknown pgui start option: $1" >&2; exit 2 ;;
    esac
  done
  [[ "$MODE" = auto || "$MODE" = standalone || "$MODE" = nested ]] || { echo "--mode must be auto, standalone, or nested." >&2; exit 2; }
  if [ "$ACTION" = start ]; then
    PROFILE_ID="$(PYTHONPATH="$ROOT/lib" python3 -c 'import proot_profiles,sys; print(proot_profiles.profile_for_alias(sys.argv[1]))' "$DISTRO_ID")" || { echo "No Ternuxx desktop profile is defined for $DISTRO_ID." >&2; exit 2; }
    if [ "$DISTRO_ID" != debian ]; then
      PYTHONPATH="$ROOT/lib" python3 - "$DISTRO_ID" "$PREFIX" <<'PYALIAS' || { echo "The selected non-Debian guest lacks an exact Ternuxx setup receipt; no desktop was started." >&2; exit 1; }
import sys
import proot_diagnostics
alias,prefix=sys.argv[1:]
proot_diagnostics.verify_managed_guest_alias(alias,prefix)
PYALIAS
    fi
    picker_args=(--prefix "$PREFIX" --alias "$DISTRO_ID")
    [ -z "$EXPLICIT_USER" ] || picker_args+=(--user "$EXPLICIT_USER")
    guest_user="$(PYTHONPATH="$ROOT/lib" python3 "$ROOT/lib/proot_user_picker.py" "${picker_args[@]}")" || {
      echo "No desktop started. Set up an account with tx install proot $DISTRO_ID, or select one with tx pgui --user NAME." >&2
      exit 1
    }
    selection="$(PYTHONPATH="$ROOT/lib" python3 - "$PREFIX/var/lib/proot-distro/containers/$DISTRO_ID/rootfs" "$DESKTOP_ID" "$MODE" "$PROFILE_ID" <<'PYSEL'
import sys
import proot_desktops
installed = proot_desktops.installed_desktops(sys.argv[1], provider=sys.argv[4])
requested = sys.argv[2]
route = None if sys.argv[3] == "auto" else sys.argv[3]
route_ids = proot_desktops.catalog(sys.argv[4], route=route)
available = [item for item in installed if item in route_ids]
if requested:
    if requested not in installed:
        print("requested desktop is not installed; available: " + (", ".join(available) or "none"), file=sys.stderr)
        raise SystemExit(2)
    if requested not in route_ids:
        print("requested desktop is not verified on the " + route + " route; available: " + (", ".join(available) or "none"), file=sys.stderr)
        raise SystemExit(2)
    choice = requested
elif "xfce" in available:
    choice = "xfce"
elif len(available) == 1:
    choice = available[0]
elif not available:
    print(f"no route-verified {sys.argv[4]} desktop is installed for this mode", file=sys.stderr)
    raise SystemExit(2)
else:
    print("choose an installed desktop with --desktop: " + ", ".join(available), file=sys.stderr)
    raise SystemExit(2)
print(choice, proot_desktops.session_command(sys.argv[4], choice, route=route))
PYSEL
)" || exit $?
    read -r DESKTOP_ID DESKTOP_SESSION <<<"$selection"
  fi
fi

usage() { cat <<'USAGE'
Usage: tx pgui [start [--mode auto|standalone|nested] [--desktop xfce|lxqt|lxde|mate|plasma] [--alias debian|ubuntu|ternuxx-replay-NAME] [--user NAME]|status|stop]
Auto uses standalone :0 when Native GUI is stopped, otherwise nested Xephyr :2 inside Native :1.
Standalone and Native desktop sessions cannot run together. Nested mode holds the lifecycle lock until closed; tx pgui stop closes the managed nested GUI while leaving Native :1 running.
Choose an installed environment with `tx pgui ID` or `tx pgui start --desktop ID`; XFCE is the default when installed.
The canonical Debian guest is the default. Ubuntu requires a Ternuxx install receipt; receipt-verified replay aliases can use standalone :0 or nested :2 with `--alias`.
Use tx pgui graphics verify to inspect the selected guest GUI's GLES, GLX, and Vulkan devices.
USAGE
}

inspect() { python3 "$STATE_HELPER" inspect "$HOME" "$STATE_DIR" /proc "$TMP_ROOT"; }
acquire_lifecycle_lock() { python3 "$LIFECYCLE_LOCK_HELPER" acquire "$1" "$HOME" /proc "$TMP_ROOT" "$$" "$2"; }
release_lifecycle_lock() { python3 "$LIFECYCLE_LOCK_HELPER" release "$1" /proc "$$" >/dev/null 2>&1 || true; }
json_state() { python3 -c 'import json,sys; print(json.load(sys.stdin).get("state","unknown"))' <<<"$1" 2>/dev/null || printf '%s\n' "${2:-unknown}"; }
state_value() { python3 - "$STATE_FILE" "$1" <<'PY'
import json,sys
try:
    value=json.load(open(sys.argv[1],encoding="utf-8"))
    for key in sys.argv[2].split("."):
        value=value[key]
    print("" if value is None else value)
except (OSError,ValueError,KeyError,TypeError):
    raise SystemExit(1)
PY
}

case "$ACTION" in
  help) usage ;;
  status)
    native_report="$(python3 "$STATE_HELPER" inspect "$HOME" "$NATIVE_STATE" /proc "$TMP_ROOT" 2>/dev/null || true)"
    native_state="$(json_state "$native_report" unknown)"
    printf 'Native desktop: %s\n' "$native_state"
    if [ ! -e "$STATE_FILE" ]; then
      echo "Standalone managed guest GUI: stopped; target display :0"
    else
      report="$(inspect)" || { echo "PRoot GUI ownership is unknown or unsafe; state preserved." >&2; exit 1; }
      python3 -c 'import json,sys; d=json.load(sys.stdin); state=d.get("state"); display=d.get("display",":0"); detail=d.get("reason","unknown"); readiness=d.get("desktop_readiness",{}); missing=readiness.get("missing_processes",[]); rstate=readiness.get("state","unknown"); print(("Standalone managed guest GUI: %s on %s; selected desktop shell/WM/panel check %s%s" % ("running" if rstate=="ready" else "process group live",display,rstate,("; missing "+", ".join(missing)) if missing else "")) if state=="running" else "Standalone managed guest GUI: state={state} display={display} detail={detail}".format(state=state,display=display,detail=detail))' <<<"$report"
    fi
    if [ -S "$TMP_ROOT/.X11-unix/X2" ]; then
      echo "Nested display :2 socket exists; socket presence alone does not establish session ownership."
    else
      echo "Nested display :2 socket is absent."
    fi
    ;;

  graphics)
    [ "${1:-}" = verify ] && [ "$#" -eq 1 ] || { echo "Usage: tx pgui graphics verify" >&2; exit 2; }
    report="$(inspect)" || { echo "PRoot GUI ownership is unknown or unsafe; graphics checks were not run." >&2; exit 1; }
    python3 - "$report" <<'PY' || { echo "A verified managed PRoot GUI is not running on :0; graphics checks were not run." >&2; exit 1; }
import json,sys
d=json.loads(sys.argv[1])
if d.get("state")!="running" or d.get("display")!=":0": raise SystemExit(1)
PY
    DISTRO_ID="$(state_value guest_alias 2>/dev/null || printf 'debian')"
    [ "$DISTRO_ID" = debian ] || PYTHONPATH="$ROOT/lib" python3 - "$DISTRO_ID" "$PREFIX" <<'PYALIAS'
import sys,proot_diagnostics
proot_diagnostics.verify_managed_guest_alias(sys.argv[1],sys.argv[2])
PYALIAS
    guest_user="$(PYTHONPATH="$ROOT/lib" python3 -c 'import os,sys,proot_diagnostics; print(proot_diagnostics.resolve_proot_guest_user(distro=sys.argv[1],prefix=os.environ["PREFIX"]))' "$DISTRO_ID")" || { echo "Could not resolve the managed guest account; no graphics checks were run." >&2; exit 1; }
    args=(login "$DISTRO_ID" --shared-tmp --user "$guest_user"
      --env DISPLAY=:0 --env GALLIUM_DRIVER=zink --env MESA_LOADER_DRIVER_OVERRIDE=zink
      --env TU_DEBUG=sysmem,noconform --env MESA_VK_WSI_DEBUG=sw)
    [ ! -c /dev/kgsl-3d0 ] || args+=(--bind /dev/kgsl-3d0:/dev/kgsl)
    [ ! -d /dev/dri ] || args+=(--bind /dev/dri)
    args+=(-- /bin/bash -c '
set +e
result=0
printf "GLES context renderer:\\n"
if command -v es2_info >/dev/null 2>&1; then
  output="$(es2_info 2>&1)"; code=$?
  printf "%s\\n" "$output" | sed -n "/^GL_VERSION:/p; /^GL_RENDERER:/p"
  printf "%s\\n" "$output" | grep -q "^GL_RENDERER:" || result=1
  [ "$code" -eq 0 ] || result=1
else echo "unavailable: es2_info is not installed"; result=1; fi
printf "\\nGLX renderer summary:\\n"
if command -v glxinfo >/dev/null 2>&1; then
  output="$(glxinfo -B 2>&1)"; code=$?
  printf "%s\\n" "$output" | sed -n "/^direct rendering:/p; /^Extended renderer info/,+3p; /^OpenGL renderer string:/p"
  printf "%s\\n" "$output" | grep -q "^OpenGL renderer string:" || result=1
  [ "$code" -eq 0 ] || result=1
else echo "unavailable: glxinfo is not installed"; result=1; fi
printf "\\nVulkan devices:\\n"
if command -v vulkaninfo >/dev/null 2>&1; then
  output="$(vulkaninfo --summary 2>&1)"; code=$?
  printf "%s\\n" "$output" | awk "/^GPU[0-9]+:/ {if (seen++) print \"\"; print; next} /^[[:space:]]*(deviceName|driverName|deviceType)[[:space:]]*=/ {print}"
  printf "%s\\n" "$output" | grep -q "deviceName[[:space:]]*=" || result=1
  [ "$code" -eq 0 ] || result=1
else echo "unavailable: vulkaninfo is not installed"; result=1; fi
printf "\\nThese checks verify context creation and device enumeration; they do not prove frame presentation or inference offload."
exit "$result"
')
    env -u DBUS_SYSTEM_BUS_ADDRESS -u DBUS_SESSION_BUS_ADDRESS -u DBUS_SESSION_BUS_PID -u DBUS_STARTER_ADDRESS -u DBUS_STARTER_BUS_TYPE -u ANDROID_ART_ROOT -u ANDROID_DATA -u ANDROID_I18N_ROOT -u ANDROID_ROOT -u ANDROID_RUNTIME_ROOT -u ANDROID_TZDATA_ROOT -u BOOTCLASSPATH -u DEX2OATBOOTCLASSPATH -u EXTERNAL_STORAGE -u LD_LIBRARY_PATH -u LD_PRELOAD "$PREFIX/bin/proot-distro" "${args[@]}"
    ;;

  start)
    [[ "$MODE" = auto || "$MODE" = standalone || "$MODE" = nested ]] || { echo "--mode must be auto, standalone, or nested." >&2; exit 2; }
    python3 "$STATE_HELPER" ensure-state "$HOME" "$NATIVE_STATE" >/dev/null
    python3 "$STATE_HELPER" ensure-state "$HOME" "$STATE_DIR" >/dev/null
    GLOBAL_LOCK="$NATIVE_STATE/.session.lock"
    LOCAL_LOCK="$STATE_DIR/.session.lock"
    acquire_lifecycle_lock "$NATIVE_STATE" "PRoot $MODE start" || exit 1
    global_lock=1; local_lock=0
    release_locks() {
      [ "$local_lock" -eq 0 ] || release_lifecycle_lock "$STATE_DIR"
      [ "$global_lock" -eq 0 ] || release_lifecycle_lock "$NATIVE_STATE"
    }
    trap release_locks EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    native_report="$(python3 "$STATE_HELPER" inspect "$HOME" "$NATIVE_STATE" /proc "$TMP_ROOT")" || { echo "Native GUI ownership is unknown; refusing PRoot GUI startup." >&2; exit 1; }
    native_state="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("state","unknown"))' <<<"$native_report")"
    [ "$MODE" != auto ] || { [ "$native_state" = running ] && MODE=nested || MODE=standalone; }
    PYTHONPATH="$ROOT/lib" python3 - "$DESKTOP_ID" "$MODE" "$PROFILE_ID" <<'PYROUTE'
import sys
import proot_desktops
selected, route, profile = sys.argv[1:]
if selected not in proot_desktops.catalog(profile, route=route):
    available = ", ".join(proot_desktops.catalog(profile, route=route))
    print(f"{profile} {selected} has no accepted {route} route; available: {available}", file=sys.stderr)
    raise SystemExit(2)
PYROUTE
    if [ "$MODE" = nested ]; then
      [ "$native_state" = running ] || { echo "Nested PRoot GUI requires the verified Native desktop to be running." >&2; exit 1; }
      native_display="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("display",""))' <<<"$native_report")"
      [ "$native_display" = :1 ] || { echo "Nested PRoot GUI currently requires Native display :1; found $native_display." >&2; exit 1; }
      python3 "$LIFECYCLE_LOCK_HELPER" tag-nested-stop "$NATIVE_STATE" /proc "$$" || exit 1
      nested_display_state="$(python3 "$DISPLAY_TOOL" "$TMP_ROOT" 2 2>/dev/null || true)"
      [ -n "$nested_display_state" ] || nested_display_state=unknown
      if [ "$nested_display_state" = busy ]; then
        nested_recovery="$(python3 "$DISPLAY_TOOL" recover-proot "$TMP_ROOT" 2 "$PREFIX/var/lib/proot-distro/containers/$DISTRO_ID/rootfs" 2>/dev/null || true)"
        if [ "$nested_recovery" = recovered ]; then
          echo "Recovered the exact dead PRoot Xephyr :2 lock/socket chain; no process was signaled."
          nested_display_state="$(python3 "$DISPLAY_TOOL" "$TMP_ROOT" 2 2>/dev/null || true)"
          [ -n "$nested_display_state" ] || nested_display_state=unknown
        fi
      fi
      [ "$nested_display_state" = available ] || {
        echo "Nested Xephyr display :2 is $nested_display_state; refusing startup because existing display ownership cannot be verified." >&2
        exit 1
      }
      PYTHONPATH="$ROOT/lib" python3 -c 'import os,sys,proot_diagnostics; proot_diagnostics.resolve_proot_guest_shell(distro=sys.argv[1],user=sys.argv[2],prefix=os.environ["PREFIX"])' "$DISTRO_ID" "$guest_user" >/dev/null 2>&1 || { echo "The selected guest account profile is unavailable; no setup changes were made." >&2; exit 1; }
      "$ROOT/tx" audio start >/dev/null || { echo "Ternuxx Native PulseAudio could not be made ready; no managed guest GUI was started." >&2; exit 1; }
      cookie="$(PYTHONPATH="$ROOT/lib" python3 -c 'import proot_diagnostics; print(proot_diagnostics._native_pulse_cookie_path() or "")' 2>/dev/null)"
      [ -n "$cookie" ] && [ -f "$cookie" ] && [ ! -L "$cookie" ] || { echo "Ternuxx Native PulseAudio cookie is unavailable; no PRoot GUI was started." >&2; exit 1; }
      guest_script=$(cat <<'GUEST'
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
state="$HOME/.local/share/ternuxx/proot-nested-gui/$TERNUXX_DESKTOP_ID"
mkdir -p "$state" "$state/config" "$state/cache" "$state/data" "$state/runtime"
chmod 700 "$state" "$state/config" "$state/cache" "$state/data" "$state/runtime"
export XDG_CONFIG_HOME="$state/config" XDG_CACHE_HOME="$state/cache" XDG_DATA_HOME="$state/data" XDG_RUNTIME_DIR="$state/runtime"
if [ "$TERNUXX_DESKTOP_ID" = lxqt ]; then
  [ -n "${TERNUXX_REPO_ROOT:-}" ] && [ -f "$TERNUXX_REPO_ROOT/lib/proot-lxqt-session.sh" ] || { echo "Ternuxx LXQt session defaults are unavailable." >&2; exit 1; }
  . "$TERNUXX_REPO_ROOT/lib/proot-lxqt-session.sh"
  nt_proot_lxqt_session_defaults "$XDG_CONFIG_HOME" || { echo "Could not prepare the isolated LXQt window-manager defaults." >&2; exit 1; }
fi
if [ "$TERNUXX_DESKTOP_ID" = xfce ]; then
  mkdir -p "$XDG_CONFIG_HOME/xfce4/xfconf/xfce-perchannel-xml"
  printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' '<channel name="xfwm4" version="1.0"><property name="general" type="empty"><property name="use_compositing" type="bool" value="false"/></property></channel>' > "$XDG_CONFIG_HOME/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml"
fi
case "$TERNUXX_DESKTOP_ID" in
  xfce) desktop_argv=(startxfce4); export XDG_CURRENT_DESKTOP=XFCE XDG_SESSION_DESKTOP=xfce DESKTOP_SESSION=xfce ;;
  lxqt) desktop_argv=(startlxqt); export XDG_CURRENT_DESKTOP=LXQt XDG_SESSION_DESKTOP=LXQt DESKTOP_SESSION=lxqt ;;
  lxde) desktop_argv=(startlxde); export XDG_CURRENT_DESKTOP=LXDE XDG_SESSION_DESKTOP=LXDE DESKTOP_SESSION=lxde ;;
  mate) desktop_argv=(mate-session); export XDG_CURRENT_DESKTOP=MATE XDG_SESSION_DESKTOP=MATE DESKTOP_SESSION=mate ;;
  # Xephyr lacks GLX; Debian KWin's X11 backend can manage windows with its compositor disabled.
  plasma) desktop_argv=(startplasma-x11); export XDG_CURRENT_DESKTOP=KDE XDG_SESSION_DESKTOP=KDE DESKTOP_SESSION=plasma KWIN_COMPOSE=N ;;
  *) echo "Unsupported desktop selection" >&2; exit 2 ;;
esac
export XDG_SESSION_TYPE=x11
native_geometry="$(PYTHONPATH="$TERNUXX_REPO_ROOT/lib" python3 -c 'import os,proot_gui_geometry; print(proot_gui_geometry.query_display_geometry(os.environ["DISPLAY"]))')" || { echo "Could not read Native display geometry; nested GUI was not started." >&2; exit 1; }
printf 'Starting Xephyr :2 at Native display size %s with a resizable host window; fullscreen/orientation resizing depends on Termux:X11 and window-manager bounds.\n' "$native_geometry"
/usr/bin/Xephyr :2 -glamor_gles2 -screen "$native_geometry" -resizeable -no-host-grab -nolisten tcp >"$state/xephyr.log" 2>&1 &
xephyr_pid=$!
xfce_pid=
system_bus_dir=
system_bus_address=
system_bus_pid=
cleanup() {
  [ -z "${xfce_pid:-}" ] || kill -TERM "$xfce_pid" 2>/dev/null || true
  [ -z "${xfce_pid:-}" ] || wait "$xfce_pid" 2>/dev/null || true
  [ -z "${system_bus_pid:-}" ] || kill -TERM "$system_bus_pid" 2>/dev/null || true
  [ -z "${system_bus_pid:-}" ] || wait "$system_bus_pid" 2>/dev/null || true
  [ -z "${system_bus_dir:-}" ] || { [ ! -S "$system_bus_dir/bus" ] || rm -f -- "$system_bus_dir/bus"; }
  [ -z "${system_bus_dir:-}" ] || rmdir "$system_bus_dir" 2>/dev/null || true
  [ -z "${xephyr_pid:-}" ] || kill -TERM "$xephyr_pid" 2>/dev/null || true
  [ -z "${xephyr_pid:-}" ] || wait "$xephyr_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
system_bus_dir="$(mktemp -d "$XDG_RUNTIME_DIR/system-bus.XXXXXX")"
system_bus_address="unix:path=$system_bus_dir/bus"
/usr/bin/dbus-daemon --session --address="$system_bus_address" --nofork >"$state/system-bus.log" 2>&1 &
system_bus_pid=$!
for _ in $(seq 1 80); do
  [ -S "$system_bus_dir/bus" ] && break
  kill -0 "$system_bus_pid" 2>/dev/null || { wait "$system_bus_pid" || true; echo "Private guest system bus failed; nested desktop was not started." >&2; exit 1; }
  sleep 0.05
done
[ -S "$system_bus_dir/bus" ] || { echo "Private guest system bus did not become ready; nested desktop was not started." >&2; exit 1; }
export DBUS_SYSTEM_BUS_ADDRESS="$system_bus_address"
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
ready=0
for _ in $(seq 1 80); do
  if DISPLAY=:2 xdpyinfo >/dev/null 2>&1; then ready=1; break; fi
  kill -0 "$xephyr_pid" 2>/dev/null || break
  sleep 0.25
done
[ "$ready" -eq 1 ] || { echo "Xephyr :2 did not become ready; see $state/xephyr.log" >&2; exit 1; }
renderer="$(DISPLAY=:2 es2_info 2>&1 | sed -n 's/^GL_RENDERER: //p' | head -n 1 || true)"
printf 'Nested %s %s display :2 is ready; GLES context renderer (draw/presentation not verified): %s\n' "$TERNUXX_PROOT_ALIAS" "$TERNUXX_DESKTOP_ID" "${renderer:-unreported}"
DISPLAY=:2 dbus-launch --exit-with-session "${desktop_argv[@]}" &
xfce_pid=$!
wait "$xfce_pid"
GUEST
)
      args=(login "$DISTRO_ID" --shared-tmp --user "$guest_user"
        --bind "$cookie:/tmp/.ternuxx-pulse-cookie"
        --env DISPLAY=:1 --env TERNUXX_PROOT_ALIAS="$DISTRO_ID" --env TERNUXX_DESKTOP_ID="$DESKTOP_ID" --env TERNUXX_DESKTOP_SESSION="$DESKTOP_SESSION" --env TERNUXX_REPO_ROOT="$ROOT" --env PULSE_SERVER=tcp:127.0.0.1:4713 --env PULSE_COOKIE=/tmp/.ternuxx-pulse-cookie
        --env GALLIUM_DRIVER=zink --env MESA_LOADER_DRIVER_OVERRIDE=zink
        --env TU_DEBUG=sysmem,noconform --env MESA_VK_WSI_DEBUG=sw
        --env MESA_DISK_CACHE_SINGLE_FILE=1 --env MESA_SHADER_CACHE_MAX_SIZE=2048M
        --env QT_X11_NO_MITSHM=1 --env LANG=en_US.UTF-8 --env LC_ALL=en_US.UTF-8)
      [ ! -c /dev/kgsl-3d0 ] || args+=(--bind /dev/kgsl-3d0:/dev/kgsl)
      [ ! -d /dev/dri ] || args+=(--bind /dev/dri)
      args+=(-- /usr/bin/env DISPLAY=:1 TERNUXX_PROOT_ALIAS="$DISTRO_ID" PULSE_SERVER=tcp:127.0.0.1:4713 PULSE_COOKIE=/tmp/.ternuxx-pulse-cookie
        GALLIUM_DRIVER=zink MESA_LOADER_DRIVER_OVERRIDE=zink TU_DEBUG=sysmem,noconform MESA_VK_WSI_DEBUG=sw
        MESA_DISK_CACHE_SINGLE_FILE=1 MESA_SHADER_CACHE_MAX_SIZE=2048M QT_X11_NO_MITSHM=1 LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
        /bin/bash -c "$guest_script")
      printf "Starting %s %s nested in Native :1 through Xephyr :2 at Native display geometry. Use Termux:X11 fullscreen/orientation controls; the Xephyr host window is resizable. Press Ctrl-C in this terminal to close only the nested desktop.\n" "$DISTRO_ID" "$DESKTOP_ID"
      python3 "$ROOT/lib/session_exec.py" env -u DBUS_SYSTEM_BUS_ADDRESS -u DBUS_SESSION_BUS_ADDRESS -u DBUS_SESSION_BUS_PID -u DBUS_STARTER_ADDRESS -u DBUS_STARTER_BUS_TYPE -u ANDROID_ART_ROOT -u ANDROID_DATA -u ANDROID_I18N_ROOT -u ANDROID_ROOT -u ANDROID_RUNTIME_ROOT -u ANDROID_TZDATA_ROOT -u BOOTCLASSPATH -u DEX2OATBOOTCLASSPATH -u EXTERNAL_STORAGE -u LD_LIBRARY_PATH -u LD_PRELOAD "$PREFIX/bin/proot-distro" "${args[@]}" &
      nested_pid=$!
      nested_shutdown() {
        local result="$1"
        trap - INT TERM HUP USR1
        kill -TERM -- -"$nested_pid" 2>/dev/null || kill -TERM "$nested_pid" 2>/dev/null || true
        wait "$nested_pid" 2>/dev/null || true
        exit "$result"
      }
      trap 'nested_shutdown 0' USR1
      trap 'nested_shutdown 130' INT
      trap 'nested_shutdown 143' TERM
      trap 'nested_shutdown 129' HUP
      set +e
      wait "$nested_pid"
      nested_status=$?
      set -e
      trap - USR1
      exit "$nested_status"
    fi
    [ "$native_state" = stopped ] || { echo "Standalone display :0 requires Native GUI stopped; current Native state is $native_state. Choose nested mode while Native GUI is running." >&2; exit 1; }
    [ -x "$SUPERVISOR" ] && [ -x "$WRAPPER" ] && [ -x "$ROOT/lib/proot-dbus-session.sh" ] && [ -x "$OWNED_EXEC" ] || { echo "Ternuxx PRoot desktop component is unavailable." >&2; exit 1; }
    PYTHONPATH="$ROOT/lib" python3 -c 'import os,sys,proot_diagnostics; proot_diagnostics.resolve_proot_guest_shell(distro=sys.argv[1],user=sys.argv[2],prefix=os.environ["PREFIX"])' "$DISTRO_ID" "$guest_user" >/dev/null 2>&1 || { echo "The selected guest account profile is unavailable; no setup changes were made." >&2; exit 1; }
    acquire_lifecycle_lock "$STATE_DIR" "PRoot standalone start" || exit 1
    local_lock=1
    current="$(inspect 2>/dev/null || true)"
    current_state="$(json_state "$current" unknown)"
    if [ "$current_state" = running ]; then
      echo "Ternuxx standalone PRoot GUI is already running on :0."
      exit 0
    fi
    case "$current_state" in
      stopped) ;;
      failed)
        python3 - "$current" <<'PY' || { echo "Failed PRoot GUI record still has live/unknown processes or display artifacts; preserving it and refusing restart." >&2; exit 1; }
import json,sys
report=json.loads(sys.argv[1])
if report.get("state")!="failed" or report.get("display_state")!="absent" or any(v!="absent" for v in report.get("processes",{}).values()):
    raise SystemExit(1)
PY
        archive="$STATE_DIR/session.failed.$(date +%s).json"
        [ ! -e "$archive" ] || { echo "Failed-session archive already exists; preserving state." >&2; exit 1; }
        mv -- "$STATE_FILE" "$archive"
        chmod 600 "$archive"
        echo "Archived the verified failed startup record; no recorded process or display artifact remains."
        ;;
      stale)
        old_x11="$(state_value x11.pid)"
        python3 "$STATE_HELPER" reconcile-stale "$HOME" "$STATE_DIR" /proc "$TMP_ROOT" >/dev/null || { echo "Stale PRoot GUI identity changed; no display files were touched." >&2; exit 1; }
        recovery="$(python3 "$DISPLAY_TOOL" recover "$TMP_ROOT" 0 "$old_x11")" || { echo "The exact stale :0 socket/lock pair could not be safely recovered; no new server started." >&2; exit 1; }
        [ "$recovery" = recovered ] || [ "$recovery" = available ] || { echo "Display :0 recovery returned $recovery; refusing startup." >&2; exit 1; }
        cp -p "$STATE_FILE" "$STATE_DIR/session.recovered.$(date +%s).json"
        chmod 600 "$STATE_DIR"/session.recovered.*.json
        ;;
      starting|stopping|failed|unknown|unsafe|*) echo "Standalone PRoot GUI state is $current_state; inspect the session record and log. No process was signaled." >&2; exit 1 ;;
    esac
    display_state="$(python3 "$DISPLAY_TOOL" "$TMP_ROOT" 0)" || display_state=busy
    [ "$display_state" = available ] || { echo "Display :0 is $display_state; refusing to start another X server." >&2; exit 1; }
    "$ROOT/tx" audio start >/dev/null || { echo "Ternuxx Native PulseAudio could not be made ready; no managed guest GUI was started." >&2; exit 1; }
    cookie="${TERNUXX_PULSE_COOKIE:-$(PYTHONPATH="$ROOT/lib" python3 -c 'import proot_diagnostics; print(proot_diagnostics._native_pulse_cookie_path() or "")' 2>/dev/null)}"
    [ -f "$cookie" ] && [ ! -L "$cookie" ] || { echo "Ternuxx Native PulseAudio cookie is unavailable; no PRoot GUI was started." >&2; exit 1; }
    touch "$STATE_DIR/desktop.log"; chmod 600 "$STATE_DIR/desktop.log"
    nohup setsid env TERNUXX_PROOT_USER="$guest_user" TERNUXX_PULSE_COOKIE="$cookie" TERNUXX_DESKTOP_ID="$DESKTOP_ID" TERNUXX_PROOT_ALIAS="$DISTRO_ID" "$SUPERVISOR" ":0" "$STATE_DIR" "$TMP_ROOT" \
      "$PREFIX/bin/termux-x11" "$ROOT/lib/proot-dbus-session.sh" "$WRAPPER" "$OWNED_EXEC" \
      proot-display0 proot >>"$STATE_DIR/desktop.log" 2>&1 </dev/null &
    ready=0
    for _ in $(seq 1 80); do
      report="$(inspect 2>/dev/null || true)"
      current_state="$(json_state "$report" unknown)"
      if [ "$current_state" = running ]; then ready=1; break; fi
      case "$current_state" in failed|unsafe|unknown) break ;; esac
      sleep 0.25
    done
    [ "$ready" -eq 1 ] || { echo "PRoot GUI did not become ready on :0. Inspect $STATE_DIR/desktop.log; no unrelated process was stopped." >&2; exit 1; }
    desktop_ready=0
    report=""
    for _ in $(seq 1 60); do
      report="$(inspect 2>/dev/null || true)"
      current_state="$(json_state "$report" unknown)"
      readiness="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("desktop_readiness",{}).get("state","unknown"))' <<<"$report" 2>/dev/null || printf unknown)"
      if [ "$current_state" = running ] && [ "$readiness" = ready ]; then desktop_ready=1; break; fi
      [ "$current_state" = running ] || break
      sleep 1
    done
    if [ "$desktop_ready" -eq 1 ]; then
      printf "Ternuxx-owned %s %s session passed shell, window-manager, panel and desktop process checks on standalone display :0. Android visibility remains unverified.\n" "$DISTRO_ID" "$DESKTOP_ID"
    else
      missing="$(python3 -c 'import json,sys; print(", ".join(json.load(sys.stdin).get("desktop_readiness",{}).get("missing_processes",[])))' <<<"$report" 2>/dev/null || true)"
      echo "The managed session group is live, but $DESKTOP_ID desktop readiness is incomplete${missing:+; missing $missing}. The session was left running; inspect with 'tx pgui status' and do not infer a usable desktop." >&2
      exit 1
    fi
    echo "Graphics: $DISTRO_ID Zink/Turnip is configured per guest process; inspect the running GUI with 'tx pgui graphics verify'."
    echo "Audio: uses the authenticated Ternuxx Native PulseAudio client endpoint; the server remains Native-owned."
    ;;

  stop)
    [ "$#" -eq 0 ] || { usage >&2; exit 2; }
    python3 "$STATE_HELPER" ensure-state "$HOME" "$NATIVE_STATE" >/dev/null
    GLOBAL_LOCK="$NATIVE_STATE/.session.lock"
    if python3 "$LIFECYCLE_LOCK_HELPER" request-nested-stop "$NATIVE_STATE" /proc >/dev/null 2>&1; then
      echo "Closing the verified nested PRoot GUI on :2; Native :1 will remain running."
      nested_wait=0
      while [ -e "$GLOBAL_LOCK" ] && [ "$nested_wait" -lt 150 ]; do sleep 0.1; nested_wait=$((nested_wait + 1)); done
      [ ! -e "$GLOBAL_LOCK" ] || { echo "Nested PRoot GUI did not release its lifecycle lock; other sessions were left running." >&2; exit 1; }
    elif [ -e "$GLOBAL_LOCK" ]; then
      echo "Another lifecycle operation owns the shared lock; no GUI process was changed." >&2
      exit 1
    fi
    [ -f "$STATE_FILE" ] || { echo "No standalone PRoot session record or cooperative nested session was found; no other process was changed."; exit 0; }
    LOCAL_LOCK="$STATE_DIR/.session.lock"
    acquire_lifecycle_lock "$NATIVE_STATE" "PRoot stop" || exit 1
    global_lock=1; local_lock=0
    release_locks() { [ "$local_lock" -eq 0 ] || release_lifecycle_lock "$STATE_DIR"; [ "$global_lock" -eq 0 ] || release_lifecycle_lock "$NATIVE_STATE"; }
    trap release_locks EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    acquire_lifecycle_lock "$STATE_DIR" "PRoot standalone stop" || exit 1
    local_lock=1
    report="$(inspect)" || { echo "PRoot GUI ownership is unknown or unsafe; no signal was sent." >&2; exit 1; }
    current_state="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("state","unknown"))' <<<"$report")"
    if [ "$current_state" = failed ]; then
      recovery="$(python3 "$ROOT/lib/desktop_orphan_stop.py" "$HOME" "$STATE_DIR" "$TMP_ROOT" "$DISPLAY_TOOL")" || {
        echo "Orphaned PRoot GUI identity could not be proved; no process was signaled. Inspect $STATE_FILE." >&2
        exit 1
      }
      echo "$(python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print("Stopped only the verified orphaned managed PRoot GUI on %s; preserved its prior session record as %s."%(d["display"],d["archive"]))' <<<"$recovery")"
      exit 0
    fi
    [ "$current_state" = running ] || { echo "PRoot GUI is $current_state; stop sent no signal and preserved all state." >&2; exit 1; }
    pid="$(state_value supervisor.pid)"; ticks="$(state_value supervisor.start_ticks)"
    python3 - "$pid" "$ticks" <<'PY'
import sys
from pathlib import Path
pid,ticks=sys.argv[1:]
try:
 raw=Path(f"/proc/{pid}/stat").read_text(); fields=raw[raw.rfind(")")+2:].split()
 cmd=Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0",b" ").decode(errors="replace")
 if fields[19] != ticks or "desktop-supervisor.sh" not in cmd:
  raise SystemExit("supervisor PID identity mismatch")
except (OSError,IndexError):
 raise SystemExit("supervisor identity is unavailable")
PY
    kill -TERM "$pid"
    for _ in $(seq 1 80); do
      report="$(inspect 2>/dev/null || true)"
      current_state="$(json_state "$report" unknown)"
      [ "$current_state" = stopped ] && { echo "Stopped only the verified managed PRoot GUI session on :0; Native :1 and Native audio were left running."; exit 0; }
      sleep 0.25
    done
    echo "PRoot GUI stop did not complete. Inspect $STATE_DIR/session.json and desktop.log; no broad cleanup was run." >&2
    exit 1
    ;;
  *) usage >&2; exit 2 ;;
esac
