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
  _NT_WINDOW_BRAND_SHIFT=0
  if [ "$_NT_WINDOW_ROWS" -ge 26 ] && [ "$_NT_WINDOW_COLS" -ge 50 ]; then _NT_WINDOW_BRAND_SHIFT=2; fi
  if [ "$_NT_WINDOW_ROWS" -ge 30 ] && [ "$_NT_WINDOW_COLS" -ge 60 ]; then _NT_WINDOW_BRAND_SHIFT=4; fi
  _NT_WINDOW_ADDON_ROWS=0
  [ "$_NT_WINDOW_ROWS" -lt 24 ] || _NT_WINDOW_ADDON_ROWS=1
  _NT_WINDOW_SHIFT=$((_NT_WINDOW_BRAND_SHIFT + _NT_WINDOW_ADDON_ROWS))
  _NT_WINDOW_LOG_FIRST=$((16 + _NT_WINDOW_SHIFT))
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
  local color="${greens[$((SECONDS % 6))]}"
  if [ "${_NT_WINDOW_BRAND_SHIFT:-0}" = 4 ]; then
    local row=1 line
    for line in '█████ █████ ████  █   █ █   █ █   █ █   █' '  █   █     █   █ ██  █ █   █  █ █   █ █ ' '  █   ████  ████  █ █ █ █   █   █     █  ' '  █   █     █ █   █  ██ █   █  █ █   █ █ ' '  █   █████ █  ██ █   █  ███  █   █ █   █'; do
      _nt_window_center "$row" "$line" "${greens[$(((SECONDS + row) % 6))]}"
      row=$((row + 1))
    done
    _nt_window_center 6 'W o r k s t a t i o n  I n  Y o u r  H a n d' 114
  elif [ "${_NT_WINDOW_BRAND_SHIFT:-0}" = 2 ]; then
    _nt_window_center 1 '╺┳╸ ┏━╸ ┏━┓ ┏┓╻ ╻ ╻ ╻ ╻ ╻ ╻' "$color"
    _nt_window_center 2 ' ┃  ┣╸  ┣┳┛ ┃┗┫ ┃ ┃  ╳   ╳ ' "${greens[$(((SECONDS + 1) % 6))]}"
    _nt_window_center 3 ' ╹  ┗━╸ ╹┗╸ ╹ ╹ ┗━┛ ╹ ╹ ╹ ╹' "${greens[$(((SECONDS + 2) % 6))]}"
    _nt_window_center 4 'Workstation In Your Hand' 114
  else
    _nt_window_center 1 TERNUXX "$color"
    _nt_window_center 2 'Workstation In Your Hand' 114
  fi
}

_nt_window_divider() {
  local -a greens=(29 35 41 47 41 35)
  printf '\033[%s;1H\033[2K\033[38;5;%sm%s\033[0m' "$1" "${greens[$((SECONDS % 6))]}" "$_NT_WINDOW_RULE" >/dev/tty
}

_nt_window_info() {
  local label="$2" value="$3"
  local block_width=0 candidate pad
  local -a values=("$_NT_WINDOW_DEVICE | Android $_NT_WINDOW_ANDROID | $_NT_WINDOW_ABI" "$_NT_WINDOW_SOC | RAM $_NT_WINDOW_RAM" "$_NT_WINDOW_GPU" "$_NT_WINDOW_AUDIO" "$_NT_WINDOW_STORAGE | Native Termux" "$_NT_WINDOW_KERNEL" "Native Termux | ${PREFIX:-unknown}")
  [ "${_NT_WINDOW_ADDON_ROWS:-0}" != 1 ] || values+=("${_NT_WINDOW_ADDONS:-Android visibility unknown}")
  for candidate in "${values[@]}"; do
    [ "$((11 + ${#candidate}))" -le "$block_width" ] || block_width=$((11 + ${#candidate}))
  done
  [ "$block_width" -le "$((_NT_WINDOW_COLS - 2))" ] || block_width=$((_NT_WINDOW_COLS - 2))
  pad=$(((_NT_WINDOW_COLS - block_width) / 2))
  printf '\033[%s;1H\033[2K%*s\033[38;5;114m%-9s\033[0m  %.*s' "$1" "$pad" '' "$label" "$((block_width - 11))" "$value" >/dev/tty
}

_nt_window_keys() {
  if [ "${1:-80}" -ge 62 ]; then
    printf '%s' 'Arrow keys: move | Space: select | Enter: continue | Esc: cancel'
  else
    printf '%s' 'Arrows | Space | Enter | Esc'
  fi
}

_nt_window_section() {
  printf '\033[%s;1H\033[2K\033[1;38;5;114m%.*s\033[0m' "$1" "$((_NT_WINDOW_COLS - 1))" "$2" >/dev/tty
}

_nt_window_progress() {
  local label="$1" done='' pending='' n
  if [[ "$label" =~ ^([1-7])/7 ]]; then
    for ((n=1;n<=7;n++)); do
      if [ "$n" -le "${BASH_REMATCH[1]}" ]; then done+='#'; else pending+='.'; fi
    done
    label="[$done$pending] $label"
  fi
  _nt_window_section "$((12 + _NT_WINDOW_SHIFT))" "$label"
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
  if command -v pulseaudio >/dev/null 2>&1; then _NT_WINDOW_AUDIO='PulseAudio installed'; fi
  _NT_WINDOW_KERNEL="$(uname -r)"
  _NT_WINDOW_ABI="$(uname -m)"
  _NT_WINDOW_ADDONS='Android visibility unknown'
  local packages name package
  if packages="$(timeout 3 /system/bin/pm list packages com.termux 2>/dev/null)" && [[ "$packages" = *package:* ]]; then
    _NT_WINDOW_ADDONS=''
    while IFS='|' read -r package name; do
      if [[ $'\n'"$packages"$'\n' = *$'\n'"package:$package"$'\n'* ]]; then
        _NT_WINDOW_ADDONS+="${_NT_WINDOW_ADDONS:+ · }$name"
      fi
    done <<'ADDONS'
com.termux.boot|Boot
com.termux.api|API
com.termux.styling|Styling
com.termux.widget|Widget
com.termux.window|Float
com.termux.tasker|Tasker
com.termux.x11|X11
ADDONS
    _NT_WINDOW_ADDONS="${_NT_WINDOW_ADDONS:-None detected (Android visibility limited)}"
  fi
}

_nt_window_footer() {
  [ "${_NT_WINDOW_TOO_SMALL:-0}" != 1 ] || return 0
  local elapsed=$((SECONDS - _NT_WINDOW_STARTED)) left right width
  left="${_NT_WINDOW_PENDING:-Collecting installation choices}"
  right="$(printf '%02d:%02d' "$((elapsed / 60))" "$((elapsed % 60))")"
  width=$((_NT_WINDOW_COLS - ${#right} - 3))
  printf '\033[s' >/dev/tty
  _nt_window_divider "$((3 + _NT_WINDOW_BRAND_SHIFT))"
  _nt_window_divider "$((11 + _NT_WINDOW_SHIFT))"
  _nt_window_divider "$((13 + _NT_WINDOW_SHIFT))"
  _nt_window_divider "$((15 + _NT_WINDOW_SHIFT))"
  _nt_window_divider "$((_NT_WINDOW_ROWS - 2))"
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
  printf -v _NT_WINDOW_RULE '%*s' "$((_NT_WINDOW_COLS - 1))" ''
  _NT_WINDOW_RULE="╶${_NT_WINDOW_RULE:2}"
  _NT_WINDOW_RULE="${_NT_WINDOW_RULE// /─}╴"
  printf '\033[H\033[2J' >/dev/tty
  _nt_window_brand
  _nt_window_divider "$((3 + _NT_WINDOW_BRAND_SHIFT))"
  _nt_window_info "$((4 + _NT_WINDOW_BRAND_SHIFT))" Device "$_NT_WINDOW_DEVICE | Android $_NT_WINDOW_ANDROID | $_NT_WINDOW_ABI"
  _nt_window_info "$((5 + _NT_WINDOW_BRAND_SHIFT))" CPU "$_NT_WINDOW_SOC | RAM $_NT_WINDOW_RAM"
  _nt_window_info "$((6 + _NT_WINDOW_BRAND_SHIFT))" GPU "$_NT_WINDOW_GPU"
  _nt_window_info "$((7 + _NT_WINDOW_BRAND_SHIFT))" Sound "$_NT_WINDOW_AUDIO"
  _nt_window_info "$((8 + _NT_WINDOW_BRAND_SHIFT))" Storage "$_NT_WINDOW_STORAGE | Native Termux"
  _nt_window_info "$((9 + _NT_WINDOW_BRAND_SHIFT))" Kernel "$_NT_WINDOW_KERNEL"
  _nt_window_info "$((10 + _NT_WINDOW_BRAND_SHIFT))" Runtime "Native Termux | ${PREFIX:-unknown}"
  if [ "$_NT_WINDOW_ADDON_ROWS" = 1 ]; then _nt_window_info "$((11 + _NT_WINDOW_BRAND_SHIFT))" Add-ons "${_NT_WINDOW_ADDONS:-Android visibility unknown}"; fi
  _nt_window_divider "$((11 + _NT_WINDOW_SHIFT))"
  if [ "${_NT_WINDOW_INSTALLING:-0}" = 1 ]; then
    _nt_window_progress "${_NT_WINDOW_STAGE:-Installation}"
    _nt_window_section "$((14 + _NT_WINDOW_SHIFT))" "${_NT_WINDOW_PANE:-Review and confirmation}"
  else
    _nt_window_line "$((12 + _NT_WINDOW_SHIFT))" "$(_nt_window_keys "$_NT_WINDOW_COLS")"
    _nt_window_section "$((14 + _NT_WINDOW_SHIFT))" 'Choose your workstation'
  fi
  _nt_window_divider "$((13 + _NT_WINDOW_SHIFT))"
  _nt_window_divider "$((15 + _NT_WINDOW_SHIFT))"
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
  [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ] || return 0
  _nt_window_content_clear
  _nt_window_brand
  _nt_window_line "$((12 + _NT_WINDOW_SHIFT))" "$(_nt_window_keys "$_NT_WINDOW_COLS")"
  _nt_window_divider "$((13 + _NT_WINDOW_SHIFT))"
  _nt_window_section "$((14 + _NT_WINDOW_SHIFT))" "$1"
  _nt_window_divider "$((15 + _NT_WINDOW_SHIFT))"
  _nt_window_footer
  printf '\033[%s;1H' "$_NT_WINDOW_LOG_FIRST" >/dev/tty
}

_nt_window_stage() {
  [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ] || return 0
  _NT_WINDOW_INSTALLING=1; _NT_WINDOW_PANE='Review and confirmation'
  _NT_WINDOW_STAGE="$1"; _NT_WINDOW_PENDING="${2:-Review and confirm}"
  local old_size="${_NT_WINDOW_ROWS:-0}:${_NT_WINDOW_COLS:-0}"
  _nt_window_size
  if [ "$_NT_WINDOW_TOO_SMALL" = 1 ]; then _nt_window_draw; return 0; fi
  [ "$old_size" = "$_NT_WINDOW_ROWS:$_NT_WINDOW_COLS" ] || _nt_window_draw
  printf '\033[s' >/dev/tty
  _nt_window_brand
  _nt_window_progress "$_NT_WINDOW_STAGE"
  _nt_window_divider "$((13 + _NT_WINDOW_SHIFT))"
  _nt_window_section "$((14 + _NT_WINDOW_SHIFT))" "$_NT_WINDOW_PANE"
  _nt_window_divider "$((15 + _NT_WINDOW_SHIFT))"
  printf '\033[u' >/dev/tty
  _nt_window_footer
  _nt_window_content_clear
  printf 'Reviewing phase: %s\n' "$_NT_WINDOW_STAGE" >/dev/tty
}

# While a package/build command runs, relay its output through one terminal writer.
# The command keeps its stdin for legitimate prompts; partial lines are shown too.
_nt_window_run() {
  if [ "${_NT_WINDOW_ACTIVE:-0}" != 1 ] || [ "${_NT_WINDOW_STREAM_ACTIVE:-0}" = 1 ]; then "$@"; return $?; fi
  local _NT_WINDOW_STREAM_ACTIVE=1
  local _NT_WINDOW_PANE='Installation output'
  [ "${_NT_WINDOW_QUERY:-0}" != 1 ] || _NT_WINDOW_PANE='Plan review output'
  _nt_window_section "$((14 + _NT_WINDOW_SHIFT))" "$_NT_WINDOW_PANE"
  _nt_window_content_clear
  printf 'Running: %s\nCommand output appears below; elapsed time updates in the footer.\n' "${_NT_WINDOW_PENDING:-Current operation}" >/dev/tty
  "$@" 2>&1 | (
    trap - EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP
    local line status old_size last_refresh=-1
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
      if [ -n "$line" ]; then
        local color=114
        case "$line" in
          '[DOWNLOAD]'*|Get:*|Fetched*) color=81 ;;
          '[UNPACK]'*|Unpacking*|'Preparing to unpack'*) color=141 ;;
          '[CONFIGURE]'*|'Setting up'*|'Processing triggers'*) color=82 ;;
          '[WARNING]'*|W:*) color=220 ;;
          '[ERROR]'*|E:*|Err:*) color=203 ;;
        esac
        printf '\033[38;5;%sm%s\033[0m' "$color" "$line" >/dev/tty
      fi
      if [ "$status" = 0 ]; then
        printf '\n' >/dev/tty
      elif [ "$status" -le 128 ]; then
        break
      fi
      if [ "$last_refresh" != "$SECONDS" ]; then
        _nt_window_footer
        printf '\033[s' >/dev/tty
        _nt_window_brand
        printf '\033[u' >/dev/tty
        last_refresh=$SECONDS
      fi
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
  _nt_window_cleanup
  trap - EXIT
  printf 'TERNUXX installation finished (exit %s). Diagnostic: %s/install-last-result.txt\n' "$result" "$TERNUXX_STATE_DIR"
  return "$result"
)

# Observe a noninteractive JSON preview without mixing progress into its stdout.
# Only the temporary captured response is removed; product state is untouched.
_nt_window_query() (
  local label="$1"; shift
  if [ "${_NT_WINDOW_ACTIVE:-0}" != 1 ]; then "$@"; return $?; fi
  local response saved_terminal result
  umask 077
  response="$(mktemp "${TMPDIR:-/tmp}/ternuxx-query.XXXXXX")" || return 2
  saved_terminal="$(stty -g </dev/tty)" || { rm -- "$response"; return 2; }
  _nt_query_cleanup() {
    # Busy queries do not accept choices; discard keys typed while they ran.
    python3 -c 'import os,termios; fd=os.open("/dev/tty",os.O_RDWR); termios.tcflush(fd,termios.TCIFLUSH); os.close(fd)' 2>/dev/null || true
    stty "$saved_terminal" </dev/tty
    rm -- "$response"
  }
  trap _nt_query_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  stty -echo </dev/tty || return 2
  local _NT_WINDOW_QUERY=1
  _NT_WINDOW_PENDING="Working: $label | not a selection screen"
  _nt_window_content_clear
  printf 'Working: %s\nWaiting for command output; elapsed time updates below.\n' "$label" >/dev/tty
  _nt_window_footer
  _nt_query_worker() { "$@" </dev/null >"$response"; }
  if _nt_window_run _nt_query_worker "$@"; then result=0; else result=$?; fi
  if [ "$result" = 0 ]; then cat "$response"; else
    printf '\nPreview failed (exit %s): %s\n' "$result" "$label" >/dev/tty
  fi
  return "$result"
)
