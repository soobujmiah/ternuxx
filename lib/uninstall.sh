# Full Native Ternuxx + PRoot uninstall, preview-bound and exact-confirmed.
nt_cmd_uninstall() {
  if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then nt_help uninstall; return $?; fi
  local helper="${_TN_LIB_DIR%/lib}/scripts/ternuxx-uninstall.py" action="${1:-guided}" preview plan_id answer result
  [ -x "$helper" ] || { nt_fail "Ternuxx uninstall helper is unavailable: $helper"; return 1; }
  case "$action" in guided|preview|apply) ;; *) nt_fail 'Usage: tx uninstall [preview|apply --yes --plan-id ID --confirmation "UNINSTALL TERNUXX"]'; return 2 ;; esac
  if [ "$action" = preview ]; then
    shift
    if [ "$TERNUXX_JSON" = "1" ]; then python3 "$helper" preview --json "$@"; else python3 "$helper" preview "$@"; fi
    return $?
  fi
  if [ "$action" = apply ]; then
    shift
    python3 "$helper" apply "$@"
    return $?
  fi
  [ $# -eq 0 ] || { nt_fail 'Usage: tx uninstall [preview|apply]'; return 2; }
  preview="$(python3 "$helper" preview --json)" || { printf '%s\n' "$preview"; return 1; }
  if [ "$TERNUXX_JSON" = "1" ] || [ ! -t 0 ] || [ ! -t 1 ]; then printf '%s\n' "$preview"; return 0; fi
  python3 - "$preview" <<'PYUNINSTALLSUMMARY'
import json,sys
p=json.loads(sys.argv[1])
print("Ternuxx full uninstall preview")
checkout=p.get("checkout") or {}
print("Checkout:", checkout.get("path", "not found"))
if checkout:
    print("Local modified/deleted files:", checkout.get("local_change_count", 0))
    print("Untracked/ignored files:", checkout.get("untracked_or_ignored_count", 0))
print("Private state:", p.get("state_dir"), "| entries:", p.get("state", {}).get("entry_count", 0))
print("PRoot guests:", ", ".join(x.get("alias", "?") for x in p.get("guests", [])) or "none")
print("Verified Native files:", len(p.get("files", [])))
print(p.get("warning", ""))
print("Shared Termux packages will remain installed.")
PYUNINSTALLSUMMARY
  plan_id="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["plan_id"])' "$preview")" || return 1
  read -r -p 'Type UNINSTALL TERNUXX to permanently remove these items: ' answer || return 2
  [ "$answer" = 'UNINSTALL TERNUXX' ] || { nt_info 'Uninstall cancelled; no files or guests were removed.'; return 1; }
  result="$(python3 "$helper" apply --yes --plan-id "$plan_id" --confirmation "$answer" --json)" || { printf '%s\n' "$result"; return 1; }
  if [ "$TERNUXX_JSON" = "1" ]; then printf '%s\n' "$result"; else nt_ok 'Ternuxx checkout, state, and PRoot guests were removed.'; fi
}
