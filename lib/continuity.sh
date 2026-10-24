# Native-only CLI wrapper for private reboot-continuity checkpoints.

nt_cmd_checkpoint() {
  nt_require_termux || return 1
  local action="${1:-}"
  if [ "$#" -gt 0 ]; then shift; fi
  case "$action" in
    prepare|verify) ;;
    *) nt_fail "Usage: tx checkpoint {prepare|verify} [options]"; return 2 ;;
  esac
  nt_require_command python3 || return 1
  local service="$_TN_LIB_DIR/management_service.py" action_word="" plan_id="" response="" yes=0
  local -a args=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --yes) yes=1; shift ;;
      --plan-id)
        [ "$#" -ge 2 ] || { nt_fail "--plan-id needs a value."; return 2; }
        plan_id="$2"; shift 2 ;;
      *) args+=("$1"); shift ;;
    esac
  done
  [ "$action" = prepare ] && action_word="CREATE CHECKPOINT" || action_word="VERIFY CHECKPOINT"
  local preview
  preview=$(python3 "$service" --operation "continuity.$action.preview" --json "${args[@]}") || return 1
  local preview_plan
  preview_plan=$(printf '%s' "$preview" | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r.get("data",{}).get("plan_id", "") if r.get("ok") else "")') || return 1
  [ -n "$preview_plan" ] || { printf '%s\n' "$preview"; return 1; }
  if [ "$yes" -eq 1 ]; then
    [ -n "$plan_id" ] || { nt_fail "--yes requires the exact --plan-id from the current preview."; return 2; }
    [ "$plan_id" = "$preview_plan" ] || { nt_fail "The checkpoint plan changed; review the current preview before applying."; return 2; }
    python3 "$service" --operation "continuity.$action" --yes --plan-id "$preview_plan" --json "${args[@]}"
    return $?
  fi
  [ -z "$plan_id" ] || { nt_fail "--plan-id requires --yes."; return 2; }
  if [ "${TERNUXX_JSON:-0}" = "1" ]; then
    printf '%s\n' "$preview"
    return 0
  fi
  printf 'Read-only continuity preview:\n%s\n' "$preview"
  [ -t 0 ] || { nt_fail "Non-interactive checkpoint action needs --yes --plan-id from the preview."; return 2; }
  printf 'Type %s to confirm: ' "$action_word"
  IFS= read -r response || return 1
  [ "$response" = "$action_word" ] || { nt_fail "Cancelled; no checkpoint evidence was written."; return 1; }
  python3 "$service" --operation "continuity.$action" --yes --plan-id "$preview_plan" --json "${args[@]}"
}
