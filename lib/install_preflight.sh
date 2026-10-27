# No repair or process termination: preflight only inspects the selected host.
_nt_install_lock() {
  command -v flock >/dev/null 2>&1 || { nt_fail 'Installer locking requires util-linux. Run the official bootstrap to prepare prerequisites.'; return 2; }
  local state="${TERNUXX_STATE_DIR:-$HOME/.local/share/ternuxx}" relative current part
  case "$state" in "$HOME"/*) relative=${state#"$HOME"/} ;; *) nt_fail 'Installer state must remain inside Native HOME.'; return 2 ;; esac
  local -a parts
  current="$HOME"
  IFS=/ read -r -a parts <<<"$relative"
  for part in "${parts[@]}"; do
    [[ -n "$part" && "$part" != . && "$part" != .. ]] || return 2
    current="$current/$part"
    [ ! -L "$current" ] || { nt_fail 'Installer state path contains a symlink; preserved.'; return 2; }
  done
  umask 077
  mkdir -p "$state" || return 2
  [ -O "$state" ] && [ -d "$state" ] || return 2
  local path="$state/install-session.lock"
  [ ! -L "$path" ] && { [ ! -e "$path" ] || { [ -f "$path" ] && [ -O "$path" ]; }; } || return 2
  exec {_NT_INSTALL_LOCK_FD}>"$path" || return 2
  flock -n "$_NT_INSTALL_LOCK_FD" || { nt_fail 'Another Ternuxx installer is active. It was left untouched; finish it before retrying.'; return 75; }
}

_nt_install_preflight() {
  local free audit
  free="$(df -Pk "${PREFIX:-$HOME}" | awk 'NR==2 {print $4}')"
  [[ "$free" =~ ^[0-9]+$ ]] && [ "$free" -ge 32768 ] || { nt_fail 'Less than 32 MiB free on the selected prefix filesystem; no installation started.'; return 1; }
  audit="$(env -u LD_LIBRARY_PATH dpkg --audit 2>&1)" || { nt_fail 'Native package audit could not complete.'; return 1; }
  if [ -n "$audit" ]; then
    nt_fail 'Native package state needs attention before another transaction.'
    printf '%s\n' "$audit" >&2
    nt_info 'Inspect dpkg --audit and repair the reported package state explicitly; then retry.'
    return 1
  fi
}

_nt_install_diagnostic() {
  local result="$1" target="$TERNUXX_STATE_DIR/install-last-result.txt" temporary
  [ ! -L "$target" ] || return 1
  temporary="$(mktemp "$TERNUXX_STATE_DIR/.install-result.XXXXXXXX")" || return 1
  {
    printf 'Ternuxx installation result\nexit_code=%s\n' "$result"
    printf 'stage=%s\n' "${_NT_WINDOW_STAGE:-not-started}"
    printf 'elapsed_seconds=%s\n' "$((SECONDS - _NT_WINDOW_STARTED))"
    printf 'combined_plan_id=%s\n' "${_NT_INSTALL_MASTER_ID:-not-approved}"
    printf 'combined_plan_directory=%s\n' "${_NT_INSTALL_MASTER_FOLDER:-not-created}"
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'Secrets, account passwords and environment are excluded from this summary.\n'
    printf 'live_output_log=%s\n' "$_NT_WINDOW_LOG_FILE"
    printf 'The private output log contains sanitized package-manager output.\n'
    printf 'Retry through tx install; remaining packages get a fresh exact plan. Existing guests are preserved.\n'
  } >"$temporary"
  chmod 600 "$temporary"
  mv -- "$temporary" "$target"
  nt_info "Installation summary: $target"
}
