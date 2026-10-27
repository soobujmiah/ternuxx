#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
if [[ "$#" -ne 0 ]]; then
  echo "refusing unsupported PRoot desktop arguments" >&2
  exit 64
fi

SCRIPT_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_LIB_DIR/.." && pwd -P)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
guest_alias="${TERNUXX_PROOT_ALIAS:-debian}"
profile_id="$(TERNUXX_PROOT_ALIAS="$guest_alias" PYTHONPATH="$SCRIPT_LIB_DIR" python3 -c 'import os,proot_profiles; print(proot_profiles.profile_for_alias(os.environ["TERNUXX_PROOT_ALIAS"]))')" || {
  echo "No verified Ternuxx desktop profile exists for the selected PRoot guest." >&2; exit 1;
}
CPUINFO_PATH="$HOME/.local/share/ternuxx/proot-display0/cpuinfo"
python3 "$SCRIPT_LIB_DIR/proot_cpuinfo.py" "$CPUINFO_PATH" || {
  echo "Could not prepare the optional CPU model-name view; the guest will use Native /proc/cpuinfo as-is." >&2
  CPUINFO_PATH=""
}
desktop_id="${TERNUXX_DESKTOP_ID:-xfce}"
case "$desktop_id" in
  xfce) desktop_argv=(startxfce4) ;;
  lxqt) desktop_argv=(startlxqt) ;;
  lxde) desktop_argv=(startlxde) ;;
  mate) desktop_argv=(mate-session) ;;
  plasma) desktop_argv=(startplasma-x11) ;;
  *) echo "Unsupported managed guest desktop selection" >&2; exit 2 ;;
esac
guest_user="$(PYTHONPATH="$SCRIPT_LIB_DIR" python3 - <<'PYUSER'
import os,proot_diagnostics as guests
alias=os.environ['TERNUXX_PROOT_ALIAS'];prefix=os.environ['PREFIX'];user=os.environ.get('TERNUXX_PROOT_USER')
try:
    if user:
        if guests.ordinary_guest_users(distro=alias,prefix=prefix).count(user)!=1:raise ValueError('selected ordinary account is no longer valid')
        print(user)
    else:print(guests.resolve_proot_guest_user(distro=alias,prefix=prefix))
except ValueError as exc:
    print(str(exc),file=__import__('sys').stderr);raise SystemExit(1)
PYUSER
)" || { echo 'Guest account is unavailable; no desktop was started.' >&2; exit 1; }
args=(login "$guest_alias" --shared-tmp --user "$guest_user"
  --env DISPLAY=:0
  --env TERNUXX_SESSION_ID=proot-display0
  --env TERNUXX_DESKTOP_ID="$desktop_id"
  --env TERNUXX_REPO_ROOT="$REPO_ROOT"
  --env TERNUXX_DESKTOP_SESSION="$desktop_id"
  --env GALLIUM_DRIVER=zink
  --env MESA_LOADER_DRIVER_OVERRIDE=zink
  --env TU_DEBUG=sysmem,noconform
  --env MESA_VK_WSI_DEBUG=sw
  --env MESA_DISK_CACHE_SINGLE_FILE=1
  --env MESA_SHADER_CACHE_MAX_SIZE=2048M
  --env QT_X11_NO_MITSHM=1
  --env LANG=en_US.UTF-8 --env LC_ALL=en_US.UTF-8)
[ -z "$CPUINFO_PATH" ] || args+=(--bind "$CPUINFO_PATH:/proc/cpuinfo")
[ -c /dev/kgsl-3d0 ] && args+=(--bind /dev/kgsl-3d0:/dev/kgsl)
[ -d /dev/dri ] && args+=(--bind /dev/dri)
if [ -n "${TERNUXX_PULSE_COOKIE:-}" ]; then
  [ -f "$TERNUXX_PULSE_COOKIE" ] && [ ! -L "$TERNUXX_PULSE_COOKIE" ] || {
    echo "Ternuxx PulseAudio cookie is unavailable or unsafe" >&2; exit 1;
  }
  args+=(--bind "$TERNUXX_PULSE_COOKIE:/tmp/.ternuxx-pulse-cookie"
    --env PULSE_COOKIE=/tmp/.ternuxx-pulse-cookie)
fi
args+=(--env PULSE_SERVER=tcp:127.0.0.1:4713 --
  /usr/bin/env DISPLAY=:0 TERNUXX_SESSION_ID=proot-display0 TERNUXX_DESKTOP_ID="$desktop_id" TERNUXX_DESKTOP_SESSION="$desktop_id" PULSE_SERVER=tcp:127.0.0.1:4713
  GALLIUM_DRIVER=zink MESA_LOADER_DRIVER_OVERRIDE=zink
  TU_DEBUG=sysmem,noconform MESA_VK_WSI_DEBUG=sw
  QT_X11_NO_MITSHM=1 LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
  /bin/bash -c '
    set -eu
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    printf "Ternuxx PRoot guest launcher entered: desktop=%s display=%s uid=%s\n" "$TERNUXX_DESKTOP_ID" "$DISPLAY" "$(id -u)" >&2
    state="$HOME/.local/share/ternuxx/proot-display0/$TERNUXX_DESKTOP_ID"
    mkdir -p "$state/config" "$state/cache" "$state/data" "$state/runtime"
    chmod 700 "$state" "$state/config" "$state/cache" "$state/data" "$state/runtime"
    export XDG_CONFIG_HOME="$state/config" XDG_CACHE_HOME="$state/cache"
    export XDG_DATA_HOME="$state/data" XDG_RUNTIME_DIR="$state/runtime"
    if [ "$TERNUXX_DESKTOP_ID" = xfce ] && [ -f "${TERNUXX_REPO_ROOT:-}/lib/proot_desktop_preferences.py" ]; then
      python3 "$TERNUXX_REPO_ROOT/lib/proot_desktop_preferences.py" --runtime-home "$HOME" --config-home "$XDG_CONFIG_HOME" >/dev/null 2>&1 || echo "Could not apply the saved VLC/XFCE defaults; continuing desktop startup." >&2
    fi
    if [ "$TERNUXX_DESKTOP_ID" = lxqt ]; then
      [ -n "${TERNUXX_REPO_ROOT:-}" ] && [ -f "$TERNUXX_REPO_ROOT/lib/proot-lxqt-session.sh" ] || { echo "Ternuxx LXQt session defaults are unavailable." >&2; exit 1; }
      . "$TERNUXX_REPO_ROOT/lib/proot-lxqt-session.sh"
      nt_proot_lxqt_session_defaults "$XDG_CONFIG_HOME" || { echo "Could not prepare the isolated LXQt window-manager defaults." >&2; exit 1; }
    fi
    if [ "$TERNUXX_DESKTOP_ID" = xfce ]; then
      xfwm="$XDG_CONFIG_HOME/xfce4/xfconf/xfce-perchannel-xml"
      mkdir -p "$xfwm"
      if [ -f "$xfwm/xfwm4.xml" ]; then
        sed -i "s|\(name=\"use_compositing\" type=\"bool\" value=\)\"true\"|\1\"false\"|" "$xfwm/xfwm4.xml"
      else
        printf "%s\n" "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" "<channel name=\"xfwm4\" version=\"1.0\">" "  <property name=\"general\" type=\"empty\">" "    <property name=\"use_compositing\" type=\"bool\" value=\"false\"/>" "  </property>" "</channel>" > "$xfwm/xfwm4.xml"
      fi
    fi
    case "$TERNUXX_DESKTOP_ID" in
      xfce) desktop_argv=(startxfce4); export XDG_CURRENT_DESKTOP=XFCE XDG_SESSION_DESKTOP=xfce DESKTOP_SESSION=xfce ;;
      lxqt) desktop_argv=(startlxqt); export XDG_CURRENT_DESKTOP=LXQt XDG_SESSION_DESKTOP=LXQt DESKTOP_SESSION=lxqt ;;
      lxde) desktop_argv=(startlxde); export XDG_CURRENT_DESKTOP=LXDE XDG_SESSION_DESKTOP=LXDE DESKTOP_SESSION=lxde ;;
      mate) desktop_argv=(mate-session); export XDG_CURRENT_DESKTOP=MATE XDG_SESSION_DESKTOP=MATE DESKTOP_SESSION=mate ;;
      plasma) desktop_argv=(startplasma-x11); export XDG_CURRENT_DESKTOP=KDE XDG_SESSION_DESKTOP=KDE DESKTOP_SESSION=plasma ;;
      *) echo "Unsupported managed guest desktop selection" >&2; exit 2 ;;
    esac
    export XDG_SESSION_TYPE=x11
    # PRoot has no systemd or Android system bus. Give desktop sessions a
    # private guest-local bus so system-bus clients can degrade gracefully;
    # never export or bind the Native host system bus into a guest.
    system_bus_dir="$(mktemp -d "$XDG_RUNTIME_DIR/system-bus.XXXXXX")"
    system_bus_address="unix:path=$system_bus_dir/bus"
    system_bus_pid=
    printf "Ternuxx PRoot private bus directory allocated: %s\n" "$system_bus_dir" >&2
    cleanup_system_bus() {
      [ -z "${system_bus_pid:-}" ] || kill -TERM "$system_bus_pid" 2>/dev/null || true
      [ -z "${system_bus_pid:-}" ] || wait "$system_bus_pid" 2>/dev/null || true
      [ -z "${system_bus_dir:-}" ] || { [ ! -S "$system_bus_dir/bus" ] || rm -f -- "$system_bus_dir/bus"; }
      [ -z "${system_bus_dir:-}" ] || rmdir "$system_bus_dir" 2>/dev/null || true
    }
    trap cleanup_system_bus EXIT
    trap "exit 130" INT
    trap "exit 143" TERM
    trap "exit 129" HUP
    [ -x /usr/bin/dbus-daemon ] || { echo "Guest dbus-daemon is unavailable." >&2; exit 127; }
    printf "Ternuxx PRoot starting private dbus-daemon: %s\n" "$system_bus_address" >&2
    /usr/bin/dbus-daemon --session --address="$system_bus_address" --nofork >"$state/system-bus.log" 2>&1 &
    system_bus_pid=$!
    for _ in $(seq 1 80); do
      [ -S "$system_bus_dir/bus" ] && break
      if ! kill -0 "$system_bus_pid" 2>/dev/null; then
        if wait "$system_bus_pid"; then bus_status=0; else bus_status=$?; fi
        printf "Ternuxx PRoot private dbus-daemon exited before socket readiness: status=%s\n" "$bus_status" >&2
        exit 1
      fi
      sleep 0.05
    done
    [ -S "$system_bus_dir/bus" ] || { kill -TERM "$system_bus_pid" 2>/dev/null || true; wait "$system_bus_pid" 2>/dev/null || true; rmdir "$system_bus_dir"; echo "Private guest system bus did not become ready." >&2; exit 1; }
    export DBUS_SYSTEM_BUS_ADDRESS="$system_bus_address"
    printf "Ternuxx PRoot private system bus ready; launching: %s\n" "${desktop_argv[*]}" >&2
    dbus-launch --exit-with-session "${desktop_argv[@]}" &
    desktop_pid=$!
    if wait "$desktop_pid"; then result=0; else result=$?; fi
    printf "Ternuxx PRoot desktop command exited: desktop=%s status=%s\n" "$TERNUXX_DESKTOP_ID" "$result" >&2
    exit "$result"
  ')
printf 'Ternuxx PRoot host launcher: guest=%s desktop=%s display=:0 user=%s\n' "$guest_alias" "$desktop_id" "$guest_user" >&2
exec env -u ANDROID_ART_ROOT -u ANDROID_DATA -u ANDROID_I18N_ROOT \
  -u ANDROID_ROOT -u ANDROID_RUNTIME_ROOT -u ANDROID_TZDATA_ROOT \
  -u BOOTCLASSPATH -u DEX2OATBOOTCLASSPATH -u EXTERNAL_STORAGE \
  -u LD_LIBRARY_PATH -u LD_PRELOAD -u DBUS_SYSTEM_BUS_ADDRESS \
  -u DBUS_SESSION_BUS_ADDRESS -u DBUS_SESSION_BUS_PID \
  -u DBUS_STARTER_ADDRESS -u DBUS_STARTER_BUS_TYPE \
  proot-distro "${args[@]}"
