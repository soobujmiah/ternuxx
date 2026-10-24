#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: proot-x11-shortcuts.sh {list|add ID|remove ID|install|uninstall}
Shortcut changes are previewed and confirmed through the Ternuxx management service.
IDs: terminal, files, firefox, shortcut-manager
USAGE
}

service() {
  "$ROOT/tx" management shortcuts "$@"
}

confirm_change() {
  local action="$1" id="$2" preview plan_id changed
  preview="$(service plan "$action" "$id")"
  plan_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["plan_id"])' <<<"$preview")"
  changed="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin)["data"]["changed"]).lower())' <<<"$preview")"
  if [ "$changed" != true ]; then
    printf '%s\n' "$preview"
    return 0
  fi
  printf '%s\n' "$preview"
  [ -t 0 ] || { echo "A terminal is required to confirm this shortcut change." >&2; return 1; }
  read -r -p "Apply this exact shortcut change? [y/N] " answer
  [[ "$answer" == [yY] || "$answer" == [yY][eE][sS] ]] || return 1
  service apply "$action" "$id" --plan-id "$plan_id" --yes
}

case "${1:-}" in
  list) shift; [ "$#" -eq 0 ] || { usage >&2; exit 2; }; service list ;;
  add|remove)
    action="$1"; shift
    [ "$#" -eq 1 ] || { usage >&2; exit 2; }
    confirm_change "$action" "$1"
    ;;
  install)
    shift; [ "$#" -eq 0 ] || { usage >&2; exit 2; }
    for id in terminal files shortcut-manager; do confirm_change add "$id"; done
    ;;
  uninstall)
    shift; [ "$#" -eq 0 ] || { usage >&2; exit 2; }
    for id in terminal files firefox shortcut-manager; do confirm_change remove "$id"; done
    ;;
  -h|--help|help|"") usage ;;
  *) usage >&2; exit 2 ;;
esac
