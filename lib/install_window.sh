# Shared installer frame. Only the content pane scrolls; no desktop/service control.
_nt_window_size() {
  read -r _NT_WINDOW_ROWS _NT_WINDOW_COLS < <(stty size </dev/tty 2>/dev/null)
  _NT_WINDOW_ROWS=${_NT_WINDOW_ROWS:-24}; _NT_WINDOW_COLS=${_NT_WINDOW_COLS:-80}
  [ "$_NT_WINDOW_ROWS" -ne 0 ] || _NT_WINDOW_ROWS=24
  [ "$_NT_WINDOW_COLS" -ne 0 ] || _NT_WINDOW_COLS=80
  _NT_WINDOW_TOO_SMALL=0
  if [ "$_NT_WINDOW_ROWS" -lt 22 ] || [ "$_NT_WINDOW_COLS" -lt 32 ]; then _NT_WINDOW_TOO_SMALL=1; fi
  [ "$_NT_WINDOW_ROWS" -ge 22 ] || _NT_WINDOW_ROWS=22
  [ "$_NT_WINDOW_COLS" -ge 32 ] || _NT_WINDOW_COLS=32
  _NT_WINDOW_LOG_FIRST=16
  _NT_WINDOW_LOG_LAST=$((_NT_WINDOW_ROWS - 3))
}

_nt_window_line() {
  printf '\033[%s;1H\033[2K%.*s' "$1" "$((_NT_WINDOW_COLS - 1))" "$2" >/dev/tty
}

# Center plain text first, then apply ANSI styles so escape bytes do not affect width.
_nt_window_center() {
  local row="$1" text="$2" color="${3:-114}" pad
  text="${text:0:$((_NT_WINDOW_COLS - 1))}"
  pad=$(((_NT_WINDOW_COLS - 1 - ${#text}) / 2))
  printf '\033[%s;1H\033[2K%*s\033[1;38;5;%sm%s\033[0m' "$row" "$pad" '' "$color" "$text" >/dev/tty
}

_nt_window_brand() {
  local -a greens=(46 82 118 154 118 82)
  _nt_window_center 1 TERNUXX "${greens[$((SECONDS % 6))]}"
  _nt_window_center 2 'Workstation In Your Hand' 114
}

_nt_window_info() {
  local label="$2" value="$3"
  # Values use a shared column with breathing room after each label.
  printf '\033[%s;1H\033[2K\033[38;5;114m%-9s\033[0m  %.*s' "$1" "$label" "$((_NT_WINDOW_COLS - 12))" "$value" >/dev/tty
}

_nt_window_keys() {
  if [ "${1:-80}" -ge 62 ]; then
    printf '%s' 'Arrow keys: move | Space: select | Enter: continue | Esc: cancel'
  else
    printf '%s' 'Arrows | Space | Enter | Esc'
  fi
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
  [ "${_NT_WINDOW_TOO_SMALL:-0}" != 1 ] || return 0
  local elapsed=$((SECONDS - _NT_WINDOW_STARTED)) left right width
  left="${_NT_WINDOW_PENDING:-Collecting installation choices}"
  right="$(printf '%02d:%02d' "$((elapsed / 60))" "$((elapsed % 60))")"
  width=$((_NT_WINDOW_COLS - ${#right} - 3))
  printf '\033[s' >/dev/tty
  _nt_window_line "$((_NT_WINDOW_ROWS - 2))" "$_NT_WINDOW_RULE"
  _nt_window_line "$((_NT_WINDOW_ROWS - 1))" "$(printf '%-*.*s  %s' "$width" "$width" "$left" "$right")"
  _nt_window_center "$_NT_WINDOW_ROWS" 'Copyright (c) 2026 Sobuj Miah | Ternuxx'
  printf '\033[u' >/dev/tty
}

_nt_window_draw() {
  _nt_window_size
  if [ "$_NT_WINDOW_TOO_SMALL" = 1 ]; then
    printf '\033[r\033[H\033[2JEnlarge terminal: 22 rows x 32 columns.\nSelection paused; Esc cancels.\nRunning commands continue.\n' >/dev/tty
    return 0
  fi
  printf -v _NT_WINDOW_RULE '%*s' "$_NT_WINDOW_COLS" ''
  _NT_WINDOW_RULE=${_NT_WINDOW_RULE// /-}
  printf '\033[H\033[2J' >/dev/tty
  _nt_window_brand
  _nt_window_line 3 "$_NT_WINDOW_RULE"
  _nt_window_info 4 Device "$_NT_WINDOW_DEVICE | Android $_NT_WINDOW_ANDROID | $_NT_WINDOW_ABI"
  _nt_window_info 5 CPU "$_NT_WINDOW_SOC | RAM $_NT_WINDOW_RAM"
  _nt_window_info 6 GPU "$_NT_WINDOW_GPU"
  _nt_window_info 7 Sound "$_NT_WINDOW_AUDIO"
  _nt_window_info 8 Storage "$_NT_WINDOW_STORAGE | Native Termux"
  _nt_window_info 9 Kernel "$_NT_WINDOW_KERNEL"
  _nt_window_info 10 Runtime "Native Termux | ${PREFIX:-unknown}"
  _nt_window_line 11 "$_NT_WINDOW_RULE"
  if [ "${_NT_WINDOW_INSTALLING:-0}" = 1 ]; then
    _nt_window_line 12 "${_NT_WINDOW_STAGE:-Installation}"
    _nt_window_line 14 'Installation log'
  else
    _nt_window_line 12 "$(_nt_window_keys "$_NT_WINDOW_COLS")"
    _nt_window_line 14 'Choose your workstation'
  fi
  _nt_window_line 13 "$_NT_WINDOW_RULE"
  _nt_window_line 15 "$_NT_WINDOW_RULE"
  printf '\033[%s;%sr\033[%s;1H' "$_NT_WINDOW_LOG_FIRST" "$_NT_WINDOW_LOG_LAST" "$_NT_WINDOW_LOG_FIRST" >/dev/tty
  _nt_window_footer
}

_nt_window_content_clear() {
  [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ] && [ "${_NT_WINDOW_TOO_SMALL:-0}" != 1 ] || return 0
  local row
  for ((row=_NT_WINDOW_LOG_FIRST; row<=_NT_WINDOW_LOG_LAST; row++)); do _nt_window_line "$row" ''; done
  printf '\033[%s;1H' "$_NT_WINDOW_LOG_FIRST" >/dev/tty
}

_nt_window_selection() {
  _nt_window_content_clear
  _nt_window_brand
  _nt_window_line 12 "$(_nt_window_keys "$_NT_WINDOW_COLS")"
  _nt_window_line 13 "$_NT_WINDOW_RULE"
  _nt_window_line 14 "$1"
  _nt_window_line 15 "$_NT_WINDOW_RULE"
  _nt_window_footer
  printf '\033[%s;1H' "$_NT_WINDOW_LOG_FIRST" >/dev/tty
}

_nt_window_stage() {
  [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ] || return 0
  _NT_WINDOW_INSTALLING=1
  _NT_WINDOW_STAGE="$1"; _NT_WINDOW_PENDING="${2:-Review and confirm}"
  local old_size="${_NT_WINDOW_ROWS:-0}:${_NT_WINDOW_COLS:-0}"
  _nt_window_size
  if [ "$_NT_WINDOW_TOO_SMALL" = 1 ]; then _nt_window_draw; return 0; fi
  [ "$old_size" = "$_NT_WINDOW_ROWS:$_NT_WINDOW_COLS" ] || _nt_window_draw
  printf '\033[s' >/dev/tty
  _nt_window_brand
  _nt_window_line 12 "$_NT_WINDOW_STAGE"
  _nt_window_line 13 "$_NT_WINDOW_RULE"
  _nt_window_line 14 'Installation log'
  _nt_window_line 15 "$_NT_WINDOW_RULE"
  printf '\033[u' >/dev/tty
  _nt_window_footer
}

# While a package/build command runs, relay its output through one terminal writer.
# The command keeps its stdin for legitimate prompts; partial lines are shown too.
_nt_window_run() {
  if [ "${_NT_WINDOW_ACTIVE:-0}" != 1 ]; then "$@"; return $?; fi
  "$@" 2>&1 | (
    trap - EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP
    local line status old_size
    while :; do
      line=''
      IFS= read -r -t 1 line
      status=$?
      old_size="$_NT_WINDOW_ROWS:$_NT_WINDOW_COLS:${_NT_WINDOW_TOO_SMALL:-0}"
      _nt_window_size
      [ "$old_size" = "$_NT_WINDOW_ROWS:$_NT_WINDOW_COLS:$_NT_WINDOW_TOO_SMALL" ] || _nt_window_draw
      if [ "$_NT_WINDOW_TOO_SMALL" = 1 ]; then
        [ "$status" = 0 ] || [ "$status" -gt 128 ] || break
        continue
      fi
      [ -z "$line" ] || printf '%s' "$line" >/dev/tty
      if [ "$status" = 0 ]; then
        printf '\n' >/dev/tty
      elif [ "$status" -le 128 ]; then
        break
      fi
      _nt_window_footer
      printf '\033[s' >/dev/tty
      _nt_window_brand
      printf '\033[u' >/dev/tty
    done
  )
  local -a outcomes=("${PIPESTATUS[@]}")
  [ "${outcomes[0]}" = 0 ] || return "${outcomes[0]}"
  return "${outcomes[1]}"
}

_nt_window_session() (
  if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then "$@"; return $?; fi
  [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] || { "$@"; return $?; }
  local saved_terminal result
  saved_terminal="$(stty -g </dev/tty)" || return 2
  local terminal_rows terminal_columns
  read -r terminal_rows terminal_columns < <(stty size </dev/tty)
  if [ "${terminal_rows:-24}" -ne 0 ] && [ "${terminal_rows:-24}" -lt 22 ]; then
    printf 'Installer needs at least 22 terminal rows; enlarge the terminal and retry. No changes made.\n' >&2
    return 2
  fi
  _nt_install_lock || return $?
  _NT_WINDOW_ACTIVE=1; _NT_WINDOW_INSTALLING=0; _NT_WINDOW_STARTED=$SECONDS
  _nt_window_snapshot
  printf '\033[?1049h' >/dev/tty
  _nt_window_draw
  _nt_window_cleanup() {
    printf '\033[r\033[0m\033[?25h\033[?1049l' >/dev/tty
    stty "$saved_terminal" </dev/tty
  }
  trap _nt_window_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  # Selectors/command relays own resize painting; the waiting parent never races them.
  trap ':' WINCH
  # A single UI writer prevents cursor-save/restore races with selectors and logs.
  # Selection and command relays refresh elapsed time and the green title.
  if _nt_install_preflight; then "$@"; result=$?; else result=$?; fi
  _nt_install_diagnostic "$result" || true
  _nt_window_stage "Finished | exit $result" 'Press Enter to return to your terminal'
  local answer
  IFS= read -r answer </dev/tty || true
  return "$result"
)
