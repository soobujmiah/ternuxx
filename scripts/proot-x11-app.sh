#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
TMP_ROOT="${TMPDIR:-$PREFIX/tmp}"
GUEST_USER="$(python3 "$ROOT/lib/proot_account_setup.py" resolve --alias debian)" || {
  echo "Could not resolve one regular Debian account from the installed rootfs." >&2
  exit 1
}
DISPLAY_VALUE=""

usage() {
  cat <<'USAGE'
Usage: proot-x11-app.sh [--display :N] [--] PROGRAM [ARG ...]
Runs one GUI application from the installed Debian PRoot on a selected live X11
session. The helper uses only a verified Ternuxx Native `:1` or standalone PRoot
`:0` display and does not invoke the separate Ternux project or its CLI.
This helper never starts or stops either desktop session.
If PROGRAM is omitted, opens Debian's xfce4-terminal.
USAGE
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --display)
      [ "$#" -ge 2 ] || { usage >&2; exit 2; }
      DISPLAY_VALUE="$2"; shift 2 ;;
    --session)
      echo "--session is no longer supported; Ternuxx uses its verified Native display." >&2
      exit 2 ;;
    --) shift; break ;;
    -h|--help) usage; exit 0 ;;
    *) break ;;
  esac
done
if [ "$#" -eq 0 ]; then
  set -- xfce4-terminal
fi
if [ -n "$DISPLAY_VALUE" ] && [[ ! "$DISPLAY_VALUE" =~ ^:[0-9]{1,2}$ ]]; then
  echo "unsupported X11 display: $DISPLAY_VALUE" >&2
  exit 2
fi

native_report="$("$ROOT/tx" status --json)" || { echo "Could not verify the Native desktop state." >&2; exit 1; }
native_state="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("status","unknown"))' <<<"$native_report")"
native_display="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("display", "") if d.get("x11")=="live" else "")' <<<"$native_report")"
PGUI_STATE="$HOME/.local/share/ternuxx/proot-display0"
pgui_report="$(python3 "$ROOT/lib/desktop_session_state.py" inspect "$HOME" "$PGUI_STATE" /proc "$TMP_ROOT")" || {
  echo "Could not verify the standalone Debian GUI state." >&2
  exit 1
}
pgui_state="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("state","unknown"))' <<<"$pgui_report")"
pgui_display="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("display", ""))' <<<"$pgui_report")"
pgui_provider="$(python3 - "$PGUI_STATE/session.json" <<'PY'
import json,os,stat,sys
try:
    path=sys.argv[1]
    meta=os.lstat(path)
    if stat.S_ISLNK(meta.st_mode) or meta.st_uid != os.getuid(): raise SystemExit(1)
    with open(path,encoding="utf-8") as stream: data=json.load(stream)
    if data.get("schema") != 2 or data.get("owner") != "ternuxx": raise SystemExit(1)
    print(data.get("provider", ""))
except (OSError,ValueError,TypeError):
    raise SystemExit(1)
PY
)" || pgui_provider=""

if [ -z "$DISPLAY_VALUE" ]; then
  if [ "$native_state" = running ] && [ "$native_display" = :1 ]; then
    DISPLAY_VALUE=:1
  elif [ "$native_state" = stopped ] && [ "$pgui_state" = running ] && [ "$pgui_display" = :0 ] && [ "$pgui_provider" = proot ]; then
    DISPLAY_VALUE=:0
  else
    echo "No verified Ternuxx Native :1 or standalone Debian :0 display is running." >&2
    exit 1
  fi
fi
case "$DISPLAY_VALUE" in
  :1)
    [ "$native_state" = running ] && [ "$native_display" = :1 ] || {
      echo "Native display :1 is not verified running; refusing to launch a Debian application." >&2
      exit 1
    }
    ;;
  :0)
    [ "$native_state" = stopped ] && [ "$pgui_state" = running ] && [ "$pgui_display" = :0 ] && [ "$pgui_provider" = proot ] || {
      echo "Standalone Debian display :0 is not verified running with Native desktop stopped; refusing to launch." >&2
      exit 1
    }
    ;;
  *)
    echo "Only verified Ternuxx displays :0 and :1 are supported; found $DISPLAY_VALUE." >&2
    exit 1
    ;;
esac

if [[ ! "$DISPLAY_VALUE" =~ ^:[0-9]{1,2}$ ]]; then
  echo "unsupported X11 display: $DISPLAY_VALUE" >&2
  exit 2
fi
socket="$TMP_ROOT/.X11-unix/X${DISPLAY_VALUE#:}"
[ -S "$socket" ] || { echo "active X11 socket is missing: $socket" >&2; exit 1; }
for tool in proot-distro python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "required host command is missing: $tool" >&2; exit 1; }
done
CPUINFO_DIR="$HOME/.local/share/ternuxx/proot-app"
CPUINFO_PATH="$CPUINFO_DIR/cpuinfo"
mkdir -p "$CPUINFO_DIR"
if [ -L "$CPUINFO_DIR" ] || [ ! -d "$CPUINFO_DIR" ]; then
  echo "Guest CPU model-name state directory is unsafe; continuing without it." >&2
  CPUINFO_PATH=""
else
  chmod 700 "$CPUINFO_DIR"
fi
if [ -n "$CPUINFO_PATH" ] && ! python3 "$ROOT/lib/proot_cpuinfo.py" "$CPUINFO_PATH"; then
  echo "Could not prepare the optional guest CPU model-name view; continuing without it." >&2
  CPUINFO_PATH=""
fi
# Verify that the installed Debian guest can reach this X server before starting a GUI app.
PROOT_ENV=(env -u ANDROID_ART_ROOT -u ANDROID_DATA -u ANDROID_I18N_ROOT
  -u ANDROID_ROOT -u ANDROID_RUNTIME_ROOT -u ANDROID_TZDATA_ROOT
  -u BOOTCLASSPATH -u DEX2OATBOOTCLASSPATH -u EXTERNAL_STORAGE)
"${PROOT_ENV[@]}" proot-distro login debian --shared-tmp --user "$GUEST_USER" --env "DISPLAY=$DISPLAY_VALUE" -- xdpyinfo >/dev/null
# The Ternux activity and desktop are owner-managed; never take over its UI here.
if ! "$ROOT/tx" audio start >/dev/null; then
  echo "Native PulseAudio is not ready; continuing the PRoot GUI launch without audio." >&2
fi
binds=()
[ -z "$CPUINFO_PATH" ] || binds+=(--bind "$CPUINFO_PATH:/proc/cpuinfo")
[ ! -e /dev/kgsl-3d0 ] || binds+=(--bind /dev/kgsl-3d0:/dev/kgsl)
[ ! -d /dev/dri ] || binds+=(--bind /dev/dri)
pulse_args=()
pulse_cookie="$(PYTHONPATH="$ROOT/lib" python3 -c 'import proot_diagnostics; p=proot_diagnostics._native_pulse_cookie_path(); print(p or "")')" || pulse_cookie=""
if [ -n "$pulse_cookie" ]; then
  pulse_args+=(--bind "$pulse_cookie:/tmp/.ternuxx-pulse-cookie" --env PULSE_COOKIE=/tmp/.ternuxx-pulse-cookie)
fi
exec "${PROOT_ENV[@]}" proot-distro login debian --shared-tmp "${binds[@]}" "${pulse_args[@]}" --user "$GUEST_USER" --env "DISPLAY=$DISPLAY_VALUE" --env PULSE_SERVER=tcp:127.0.0.1:4713 --env MESA_LOADER_DRIVER_OVERRIDE=zink --env GALLIUM_DRIVER=zink --env TU_DEBUG=sysmem,noconform --env MESA_VK_WSI_DEBUG=sw --env MESA_SHADER_CACHE_DISABLE=true --env QT_X11_NO_MITSHM=1 -- "$@"
