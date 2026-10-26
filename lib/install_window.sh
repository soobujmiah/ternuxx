# Shared installer frame. Only the content pane scrolls; no desktop/service control.
_nt_window_size() {
  read -r _NT_WINDOW_ROWS _NT_WINDOW_COLS < <(stty size </dev/tty 2>/dev/null)
  _NT_WINDOW_ROWS=${_NT_WINDOW_ROWS:-24}; _NT_WINDOW_COLS=${_NT_WINDOW_COLS:-80}
  [ "$_NT_WINDOW_ROWS" -ne 0 ] || _NT_WINDOW_ROWS=24
  [ "$_NT_WINDOW_COLS" -ne 0 ] || _NT_WINDOW_COLS=80
  [ "$_NT_WINDOW_ROWS" -ge 22 ] || _NT_WINDOW_ROWS=22
  [ "$_NT_WINDOW_COLS" -ge 32 ] || _NT_WINDOW_COLS=32
  _NT_WINDOW_LOG_FIRST=14
  _NT_WINDOW_LOG_LAST=$((_NT_WINDOW_ROWS - 3))
}

_nt_window_line() {
  printf '\033[%s;1H\033[2K%.*s' "$1" "$_NT_WINDOW_COLS" "$2" >/dev/tty
}

_nt_window_snapshot() {
  _NT_WINDOW_DEVICE="$(getprop ro.product.model 2>/dev/null || echo unknown)"
  _NT_WINDOW_ANDROID="$(getprop ro.build.version.release 2>/dev/null || echo unknown)"
  _NT_WINDOW_SOC="$(getprop ro.soc.model 2>/dev/null || echo unknown)"
  _NT_WINDOW_RAM="$(awk '/MemTotal:/ {t=$2} /MemAvailable:/ {a=$2} END {printf "%.1f/%.1f GiB free",a/1048576,t/1048576}' /proc/meminfo 2>/dev/null)"
  _NT_WINDOW_STORAGE="$(df -Pk "${PREFIX:-$HOME}" 2>/dev/null | awk 'NR==2 {printf "%.1f GiB free", $4/1048576}')"
  _NT_WINDOW_GPU='No accessible KGSL/DRI node'
  if [ -r /dev/kgsl-3d0 ]; then _NT_WINDOW_GPU='/dev/kgsl-3d0 (readable)'
  elif [ -d /dev/dri ]; then _NT_WINDOW_GPU='/dev/dri (present; probe required)'; fi
  _NT_WINDOW_AUDIO='PulseAudio not installed'
  if command -v pulseaudio >/dev/null 2>&1; then _NT_WINDOW_AUDIO='PulseAudio installed; playback unverified'; fi
  _NT_WINDOW_KERNEL="$(uname -r)"
  _NT_WINDOW_ABI="$(uname -m)"
}

_nt_window_footer() {
  local elapsed=$((SECONDS - _NT_WINDOW_STARTED)) left right width
  left="${_NT_WINDOW_PENDING:-Collecting installation choices}"
  right="$(printf '%02d:%02d' "$((elapsed / 60))" "$((elapsed % 60))")"
  width=$((_NT_WINDOW_COLS - ${#right} - 2))
  printf '\033[s' >/dev/tty
  _nt_window_line "$((_NT_WINDOW_ROWS - 2))" "$_NT_WINDOW_RULE"
  _nt_window_line "$((_NT_WINDOW_ROWS - 1))" "$(printf '%-*.*s  %s' "$width" "$width" "$left" "$right")"
  _nt_window_line "$_NT_WINDOW_ROWS" 'Copyright (c) 2026 Sobuj Miah | Ternuxx'
  printf '\033[u' >/dev/tty
}

_nt_window_draw() {
  _nt_window_size
  printf -v _NT_WINDOW_RULE '%*s' "$_NT_WINDOW_COLS" ''
  _NT_WINDOW_RULE=${_NT_WINDOW_RULE// /-}
  printf '\033[H\033[2J' >/dev/tty
  _nt_window_line 1 'Ternuxx | Mobile workstation'
  _nt_window_line 2 'Your phone. Your workstation.'
  _nt_window_line 3 "$_NT_WINDOW_RULE"
  _nt_window_line 4 "Device  $_NT_WINDOW_DEVICE | Android $_NT_WINDOW_ANDROID | $_NT_WINDOW_ABI"
  _nt_window_line 5 "CPU     $_NT_WINDOW_SOC | RAM $_NT_WINDOW_RAM"
  _nt_window_line 6 "GPU     $_NT_WINDOW_GPU"
  if [ "$_NT_WINDOW_LOG_FIRST" -ge 12 ]; then
    _nt_window_line 7 "Sound   $_NT_WINDOW_AUDIO"
    _nt_window_line 8 "Storage $_NT_WINDOW_STORAGE | Native Termux"
    _nt_window_line 9 "Kernel  $_NT_WINDOW_KERNEL"
    _nt_window_line 10 "Runtime Native Termux | ${PREFIX:-unknown}"
    _nt_window_line 11 "$_NT_WINDOW_RULE"
  fi
  _nt_window_line "$((_NT_WINDOW_LOG_FIRST - 2))" "${_NT_WINDOW_STAGE:-Setup | Choose your workstation}"
  _nt_window_line "$((_NT_WINDOW_LOG_FIRST - 1))" "Installation log / choices $_NT_WINDOW_RULE"
  printf '\033[%s;%sr\033[%s;1H' "$_NT_WINDOW_LOG_FIRST" "$_NT_WINDOW_LOG_LAST" "$_NT_WINDOW_LOG_FIRST" >/dev/tty
  _nt_window_footer
}

_nt_window_content_clear() {
  [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ] || return 0
  local row
  for ((row=_NT_WINDOW_LOG_FIRST; row<=_NT_WINDOW_LOG_LAST; row++)); do _nt_window_line "$row" ''; done
  printf '\033[%s;1H' "$_NT_WINDOW_LOG_FIRST" >/dev/tty
}

_nt_window_stage() {
  [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ] || return 0
  _NT_WINDOW_STAGE="$1"; _NT_WINDOW_PENDING="${2:-Review and confirm}"
  printf '\033[s' >/dev/tty
  _nt_window_line "$((_NT_WINDOW_LOG_FIRST - 2))" "$_NT_WINDOW_STAGE"
  printf '\033[u' >/dev/tty
  _nt_window_footer
}

_nt_window_session() (
  if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then "$@"; return $?; fi
  [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] || { "$@"; return $?; }
  local saved_terminal heartbeat result
  saved_terminal="$(stty -g </dev/tty)" || return 2
  local terminal_rows terminal_columns
  read -r terminal_rows terminal_columns < <(stty size </dev/tty)
  if [ "${terminal_rows:-24}" -ne 0 ] && [ "${terminal_rows:-24}" -lt 22 ]; then
    printf 'Installer needs at least 22 terminal rows; enlarge the terminal and retry. No changes made.\n' >&2
    return 2
  fi
  _nt_install_lock || return $?
  _NT_WINDOW_ACTIVE=1; _NT_WINDOW_STARTED=$SECONDS
  _nt_window_snapshot
  printf '\033[?1049h' >/dev/tty
  _nt_window_draw
  _nt_window_cleanup() {
    [ -z "${heartbeat:-}" ] || { kill "$heartbeat" 2>/dev/null; wait "$heartbeat" 2>/dev/null; }
    printf '\033[r\033[0m\033[?25h\033[?1049l' >/dev/tty
    stty "$saved_terminal" </dev/tty
  }
  trap _nt_window_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  trap '_nt_window_draw' WINCH
  # The ticker never consumes terminal input or changes package/service state.
  ( trap - EXIT; trap 'exit 0' TERM INT HUP
    while :; do
      sleep 1
      _nt_window_size
      elapsed=$((SECONDS - _NT_WINDOW_STARTED))
      printf '\033[s\033[%s;%sH%02d:%02d\033[u' "$((_NT_WINDOW_ROWS - 1))" "$((_NT_WINDOW_COLS - 4))" "$((elapsed / 60))" "$((elapsed % 60))" >/dev/tty
    done
  ) & heartbeat=$!
  if _nt_install_preflight; then "$@"; result=$?; else result=$?; fi
  _nt_install_diagnostic "$result" || true
  _nt_window_stage "Finished | exit $result" 'Press Enter to return to your terminal'
  local answer
  IFS= read -r answer </dev/tty || true
  return "$result"
)
