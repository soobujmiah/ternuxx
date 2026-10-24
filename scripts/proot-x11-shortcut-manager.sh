#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
TMP_ROOT="${TMPDIR:-$PREFIX/tmp}"
GUEST_USER="$(PYTHONPATH="$ROOT/lib" python3 -c 'import os,proot_diagnostics; print(proot_diagnostics.resolve_proot_guest_user(distro="debian", prefix=os.environ["PREFIX"]))')" || {
  echo "Could not resolve one regular Debian account from the installed rootfs." >&2
  exit 1
}

DISPLAY_VALUE="$("$ROOT/tx" status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("status")=="running" and d.get("x11")=="yes"; print(d["display"])')" || {
  echo "Start the Ternuxx desktop first, then open Manage PRoot Shortcuts again." >&2
  exit 1
}
[[ "$DISPLAY_VALUE" =~ ^:[0-9]+$ ]] || { echo "Unsupported display: $DISPLAY_VALUE" >&2; exit 1; }
[[ -S "$TMP_ROOT/.X11-unix/X${DISPLAY_VALUE#:}" ]] || { echo "X11 socket is unavailable for $DISPLAY_VALUE" >&2; exit 1; }
env -u ANDROID_ART_ROOT -u ANDROID_DATA -u ANDROID_I18N_ROOT \
  -u ANDROID_ROOT -u ANDROID_RUNTIME_ROOT -u ANDROID_TZDATA_ROOT \
  -u BOOTCLASSPATH -u DEX2OATBOOTCLASSPATH -u EXTERNAL_STORAGE proot-distro login debian --shared-tmp --user "$GUEST_USER" --env "DISPLAY=$DISPLAY_VALUE" -- xdpyinfo >/dev/null || {
  echo "Debian PRoot cannot connect to $DISPLAY_VALUE" >&2
  exit 1
}

service() { "$ROOT/tx" management shortcuts "$@"; }

dialog() {
  local title="$1" buttons="$2" default="$3" message="$4"
  env -u ANDROID_ART_ROOT -u ANDROID_DATA -u ANDROID_I18N_ROOT \
  -u ANDROID_ROOT -u ANDROID_RUNTIME_ROOT -u ANDROID_TZDATA_ROOT \
  -u BOOTCLASSPATH -u DEX2OATBOOTCLASSPATH -u EXTERNAL_STORAGE proot-distro login debian --shared-tmp --user "$GUEST_USER" --env "DISPLAY=$DISPLAY_VALUE" -- \
    xmessage -center -title "$title" -buttons "$buttons" -default "$default" "$message"
}

show_notice() { dialog "PRoot Shortcuts" "OK:0" OK "$1" || true; }

manage_shortcut() {
  local action="$1" id="$2" preview plan_id changed target confirmation result reason
  if ! preview="$(service plan "$action" "$id")"; then
    reason="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("error", {}).get("message", "management service unavailable"))' <<<"$preview" 2>/dev/null || true)"
    show_notice "Could not prepare this change. ${reason:-The launcher was left unchanged.}"
    return 1
  fi
  read -r plan_id changed target < <(python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; print(d["plan_id"], str(d["changed"]).lower(), d["affected_resources"][0]["path"])' <<<"$preview")
  if [ "$changed" != true ]; then
    show_notice "No menu change is needed for $id."
    return 0
  fi
  if [ "$action" = add ]; then confirmation="Add $id to the native Applications menu?\n\nTarget: $target"; else confirmation="Remove the Ternuxx-managed $id launcher?\n\nRunning apps and X11 sessions stay open.\n\nTarget: $target"; fi
  if dialog "Confirm Shortcut Change" "Apply:10,Cancel:0" Cancel "$confirmation"; then result=0; else result=$?; fi
  [ "$result" -eq 10 ] || return 0
  if service apply "$action" "$id" --plan-id "$plan_id" --yes >/dev/null; then
    show_notice "Shortcut change completed for $id. Running apps were not stopped."
  else
    show_notice "Shortcut change failed. The current menu entry was preserved."
    return 1
  fi
}

show_current() {
  local result
  result="$(service list | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; print("\\n".join(x["name"] + ": " + x["shortcut_state"] for x in d["items"]))')"
  show_notice "$result"
}

while :; do
  if dialog "Manage PRoot Shortcuts" \
    "Add app:10,Remove app:20,View current:30,Close:0" Close \
    "Manage Debian PRoot app launchers in the native XFCE menu. Changes go through the shared management service and ask before writing."; then result=0; else result=$?; fi
  case "$result" in
    10)
      if dialog "Add a PRoot App" "Terminal:10,Files:20,Firefox:30,Back:0" Back \
        "Choose an installed Debian PRoot application to add to the native XFCE menu."; then result=0; else result=$?; fi
      case "$result" in
        10) manage_shortcut add terminal || true ;;
        20) manage_shortcut add files || true ;;
        30) manage_shortcut add firefox || true ;;
      esac
      ;;
    20)
      if dialog "Remove a PRoot Shortcut" "Terminal:10,Files:20,Firefox:30,Back:0" Back \
        "Choose a Ternuxx-managed PRoot launcher. Removing it does not stop the app or desktop."; then result=0; else result=$?; fi
      case "$result" in
        10) manage_shortcut remove terminal || true ;;
        20) manage_shortcut remove files || true ;;
        30) manage_shortcut remove firefox || true ;;
      esac
      ;;
    30) show_current ;;
    0|*) exit 0 ;;
  esac
done
