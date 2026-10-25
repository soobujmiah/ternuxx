#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
if [[ "$#" -ne 0 ]]; then
  echo "refusing unsupported PRoot desktop arguments" >&2
  exit 64
fi

SCRIPT_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
CPUINFO_PATH="$HOME/.local/share/ternuxx/proot-display0/cpuinfo"
python3 "$SCRIPT_LIB_DIR/proot_cpuinfo.py" "$CPUINFO_PATH" || {
  echo "Could not prepare the optional CPU model-name view; Debian XFCE will use Native /proc/cpuinfo as-is." >&2
  CPUINFO_PATH=""
}
desktop_id="${TERNUXX_DESKTOP_ID:-xfce}"
case "$desktop_id" in xfce) session=startxfce4 ;; lxqt) session=startlxqt ;; lxde) session=startlxde ;; mate) session=mate-session ;; *) echo "Unsupported Debian desktop selection" >&2; exit 2 ;; esac
guest_user="$(PYTHONPATH="$SCRIPT_LIB_DIR" python3 -c 'import os,proot_diagnostics; print(proot_diagnostics.resolve_proot_guest_user(distro="debian",prefix=os.environ["PREFIX"]))')" || {
  echo "Could not resolve one ordinary Debian guest account; no desktop was started." >&2
  exit 1
}
args=(login debian --shared-tmp --user "$guest_user"
  --env DISPLAY=:0
  --env TERNUXX_SESSION_ID=proot-display0
  --env TERNUXX_DESKTOP_ID="$desktop_id"
  --env TERNUXX_DESKTOP_SESSION="$session"
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
  /usr/bin/env DISPLAY=:0 TERNUXX_SESSION_ID=proot-display0 TERNUXX_DESKTOP_ID="$desktop_id" TERNUXX_DESKTOP_SESSION="$session" PULSE_SERVER=tcp:127.0.0.1:4713
  GALLIUM_DRIVER=zink MESA_LOADER_DRIVER_OVERRIDE=zink
  TU_DEBUG=sysmem,noconform MESA_VK_WSI_DEBUG=sw
  QT_X11_NO_MITSHM=1 LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
  /bin/bash -c '
    set -eu
    state="$HOME/.local/share/ternuxx/proot-display0/$TERNUXX_DESKTOP_ID"
    mkdir -p "$state/config" "$state/cache" "$state/data" "$state/runtime"
    chmod 700 "$state" "$state/config" "$state/cache" "$state/data" "$state/runtime"
    export XDG_CONFIG_HOME="$state/config" XDG_CACHE_HOME="$state/cache"
    export XDG_DATA_HOME="$state/data" XDG_RUNTIME_DIR="$state/runtime"
    if [ "$TERNUXX_DESKTOP_ID" = xfce ]; then
      xfwm="$XDG_CONFIG_HOME/xfce4/xfconf/xfce-perchannel-xml"
      mkdir -p "$xfwm"
      if [ -f "$xfwm/xfwm4.xml" ]; then
        sed -i "s|\(name=\"use_compositing\" type=\"bool\" value=\)\"true\"|\1\"false\"|" "$xfwm/xfwm4.xml"
      else
        printf "%s\n" "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" "<channel name=\"xfwm4\" version=\"1.0\">" "  <property name=\"general\" type=\"empty\">" "    <property name=\"use_compositing\" type=\"bool\" value=\"false\"/>" "  </property>" "</channel>" > "$xfwm/xfwm4.xml"
      fi
    fi
    exec dbus-launch --exit-with-session "$TERNUXX_DESKTOP_SESSION"
  ')
exec env -u ANDROID_ART_ROOT -u ANDROID_DATA -u ANDROID_I18N_ROOT \
  -u ANDROID_ROOT -u ANDROID_RUNTIME_ROOT -u ANDROID_TZDATA_ROOT \
  -u BOOTCLASSPATH -u DEX2OATBOOTCLASSPATH -u EXTERNAL_STORAGE \
  -u LD_LIBRARY_PATH -u LD_PRELOAD -u DBUS_SESSION_BUS_ADDRESS \
  -u DBUS_SESSION_BUS_PID -u DBUS_STARTER_ADDRESS -u DBUS_STARTER_BUS_TYPE \
  proot-distro "${args[@]}"
