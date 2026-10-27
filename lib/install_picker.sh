# Keyboard selector. stdout contains IDs only; the controlling terminal owns input.
_nt_pick() (
  local title="$1" mode="$2" defaults="$3"; shift 3
  declare -p _NT_PICK_SUMMARY >/dev/null 2>&1 || local -a _NT_PICK_SUMMARY=()
  local -a items=("$@") selected=()
  local index=0 offset=0 height rows columns key tail sequence item id i mark saved_terminal count read_status redraw=1 previous_rows=0 previous_columns=0 dimensions_changed=0
  [ "${TERM:-dumb}" != dumb ] || { printf 'Selection needs an attached terminal with arrow keys.\n' >&2; return 2; }
  [ ${#items[@]} -gt 0 ] || return 2
  exec 3<>/dev/tty || return 2
  saved_terminal="$(stty -g <&3)" || return 2
  _nt_picker_cleanup() {
    stty "$saved_terminal" <&3
    printf '\033[0m\033[?25h' >&3
    if [ "${_NT_WINDOW_ACTIVE:-0}" != 1 ]; then
      printf '\033[?1049l' >&3
    else
      _nt_window_content_clear
      if [ "${_NT_WINDOW_INSTALLING:-0}" = 1 ]; then
        _nt_window_stage "${_NT_WINDOW_STAGE:-Installation}" "${_NT_WINDOW_PENDING:-Review and confirm}"
      fi
    fi
  }
  trap _nt_picker_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  # Keep one noncanonical, non-echo mode across the entire escape sequence.
  # Per-byte silent reads previously left echo/canonical gaps between key bytes.
  stty -echo -icanon -ixon min 1 time 0 <&3 || return 2
  if [ "${_NT_WINDOW_ACTIVE:-0}" != 1 ]; then printf '\033[?1049h\033[r' >&3; fi
  printf '\033[?25l' >&3
  for item in "${items[@]}"; do
    id="${item%%|*}"
    case ",$defaults," in *",$id,"*) selected+=(1) ;; *) selected+=(0) ;; esac
  done
  while :; do
    read -r rows columns < <(stty size <&3 2>/dev/null)
    rows="${rows:-24}"; columns="${columns:-80}"
    [ "$rows" -ge 7 ] || rows=24
    [ "$columns" -ge 10 ] || columns=80
    dimensions_changed=0
    if [ "$rows" != "$previous_rows" ] || [ "$columns" != "$previous_columns" ]; then redraw=1; dimensions_changed=1; fi
    previous_rows="$rows"; previous_columns="$columns"
    height=$((rows - 7))
    if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then
      _nt_window_size
      if [ "$dimensions_changed" = 1 ]; then _nt_window_draw; fi
      if [ "$_NT_WINDOW_TOO_SMALL" = 1 ]; then
        key=''
        IFS= read -rn1 -t 1 key <&3
        read_status=$?
        [ "$read_status" = 0 ] || [ "$read_status" -gt 128 ] || return 130
        [ "$key" != $'\033' ] || return 130
        redraw=0
        continue
      fi
      height=$((_NT_WINDOW_LOG_LAST - _NT_WINDOW_LOG_FIRST))
      [ "$height" -gt 0 ] || height=1
    fi
    local -a wrapped_summary=() display_items=("${items[@]}")
    local summary_line wrapped_line summary_height=0
    if [ "$mode" = view ]; then
      display_items=()
      for item in "${items[@]}"; do
        while IFS= read -r wrapped_line; do display_items+=("line|$wrapped_line"); done < <(printf '%s\n' "${item#*|}" | fold -s -w "$((columns - 4))")
      done
    fi
    for summary_line in "${_NT_PICK_SUMMARY[@]}"; do
      while IFS= read -r wrapped_line; do wrapped_summary+=("$wrapped_line"); done < <(printf '%s\n' "$summary_line" | fold -s -w "$((columns - 2))")
    done
    summary_height=${#wrapped_summary[@]}
    height=$((height - summary_height))
    [ "$height" -gt 0 ] || height=1
    [ "$index" -ge "$offset" ] || offset="$index"
    [ "$index" -lt "$((offset + height))" ] || offset=$((index - height + 1))
    if [ "$redraw" = 1 ]; then
      if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then
        _nt_window_selection "$title"
        if [ "$mode" = view ]; then _nt_window_line "$((12 + _NT_WINDOW_SHIFT))" 'Arrows/PgUp/PgDn: scroll | Enter/Esc: return'; fi
      else
        printf '\033[H\033[2J' >&3
        local hint='Arrow keys: move | Space: select | Enter: continue | Esc: cancel'
        [ "$mode" != view ] || hint='Arrows/PgUp/PgDn: scroll | Enter/Esc: return'
        printf '%.*s\r\n' "$((columns - 1))" "$hint" >&3
        printf '%.*s\r\n%.*s\r\n%.*s\r\n' "$((columns - 1))" '-------------------------------------------------------------------------------' "$((columns - 1))" "$title" "$((columns - 1))" '-------------------------------------------------------------------------------' >&3
      fi
      for item in "${wrapped_summary[@]}"; do
        printf '\033[38;5;114m%.*s\033[0m\r\n' "$((columns - 1))" "$item" >&3
      done
      for ((i=offset; i<${#display_items[@]} && i<offset+height; i++)); do
        mark=' '; [ "${selected[$i]:-0}" = 0 ] || mark=x
        if [ "$i" = "$index" ]; then printf '\033[1;38;5;46m> ' >&3; else printf '  ' >&3; fi
        if [ "$mode" = view ]; then
          printf '%.*s\033[0m\r\n' "$((columns - 3))" "${display_items[$i]#*|}" >&3
        else
          printf '[%s] %.*s\033[0m\r\n' "$mark" "$((columns - 7))" "${display_items[$i]#*|}" >&3
        fi
      done
      count=0
      for i in "${selected[@]}"; do count=$((count + i)); done
      local position="$((index + 1))/${#items[@]} | $count selected | Home/End, PgUp/PgDn"
      if [ "$mode" = single ] && [ "${#_NT_PICK_SUMMARY[@]}" -gt 0 ]; then
        position="Choice $((index + 1)) of ${#items[@]} | Up/Down choose | Enter confirm | Esc cancel"
      fi
      [ "$mode" != view ] || position="Line $((index + 1))/${#display_items[@]} | Read-only | Home/End, PgUp/PgDn"
      printf '\033[2K\033[38;5;114m%.*s\033[0m' "$((columns - 1))" "$position" >&3
    elif [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then
      _nt_window_footer
      printf '\033[s' >&3
      _nt_window_brand
      printf '\033[u' >&3
    fi
    # Timeout refreshes elapsed time/green pulse in this same writer, never a competing ticker.
    key=''
    IFS= read -rn1 -t 1 key <&3
    read_status=$?
    if [ "$read_status" -ne 0 ]; then
      [ "$read_status" -gt 128 ] && [ -t 3 ] || return 130
      redraw=0
      continue
    fi
    redraw=1
    case "$key" in
      $'\033')
        tail=''; sequence=''
        IFS= read -rn1 -t 0.4 tail <&3 || { [ "$mode" != view ] || return 0; return 130; }
        [[ "$tail" = '[' || "$tail" = O ]] || continue
        for ((i=0; i<16; i++)); do
          tail=''
          IFS= read -rn1 -t 0.4 tail <&3 || break
          sequence+="$tail"
          [[ "$tail" = [A-Za-z~] ]] && break
        done
        case "$sequence" in
          A|[0-9]*A) index=$(((index + ${#display_items[@]} - 1) % ${#display_items[@]})) ;;
          B|[0-9]*B) index=$(((index + 1) % ${#display_items[@]})) ;;
          H|1~|7~) index=0 ;;
          F|4~|8~) index=$((${#display_items[@]} - 1)) ;;
          5~) index=$((index - height)); [ "$index" -ge 0 ] || index=0 ;;
          6~) index=$((index + height)); [ "$index" -lt "${#display_items[@]}" ] || index=$((${#display_items[@]} - 1)) ;;
        esac ;;
      ' ')
        [ "$mode" != view ] || continue
        if [ "$mode" = single ]; then
          for i in "${!selected[@]}"; do selected[$i]=0; done
        fi
        selected[$index]=$((1 - selected[index]))
        if [ "${selected[$index]}" = 1 ]; then
          for i in "${!items[@]}"; do
            [ "$i" != "$index" ] || continue
            if [[ "${items[$index]%%|*}" = none || "${items[$i]%%|*}" = none ]]; then selected[$i]=0; fi
          done
        fi ;;
      ''|$'\r')
        [ "$mode" != view ] || return 0
        if [ "$mode" = single ]; then printf '%s\n' "${items[$index]%%|*}"; return 0; fi
        local result=''
        for i in "${!selected[@]}"; do
          [ "${selected[$i]}" = 1 ] || continue
          result+="${result:+,}${items[$i]%%|*}"
        done
        [ -n "$result" ] || continue
        printf '%s\n' "$result"; return 0 ;;
    esac
  done
)

_nt_confirm() {
  local answer
  answer="$(_nt_pick "$1" single '' 'no|Cancel / skip' 'yes|Continue with the displayed operation')" || return $?
  [ "$answer" = yes ]
}

# Text fields share the selector's terminal ownership and resize/animation loop.
# stdout is the value only; hidden values are never drawn to the terminal.
_nt_input() (
  local title="$1" hidden="${2:-0}" value='' key='' tail='' saved_terminal status i shown redraw=1
  exec 3<>/dev/tty || return 2
  saved_terminal="$(stty -g <&3)" || return 2
  _nt_input_cleanup() {
    stty "$saved_terminal" <&3
    printf '\033[0m\033[?25h' >&3
    if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then _nt_window_content_clear; fi
  }
  trap _nt_input_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  stty -echo -icanon -ixon min 1 time 0 <&3 || return 2
  while :; do
    if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then
      local old_size="${_NT_WINDOW_ROWS:-0}:${_NT_WINDOW_COLS:-0}:${_NT_WINDOW_TOO_SMALL:-0}"
      _nt_window_size
      [ "$old_size" = "$_NT_WINDOW_ROWS:$_NT_WINDOW_COLS:$_NT_WINDOW_TOO_SMALL" ] || { _nt_window_draw; redraw=1; }
      if [ "$_NT_WINDOW_TOO_SMALL" != 1 ] && [ "$redraw" = 1 ]; then
        _nt_window_selection "$title"
        _nt_window_line "$((12 + _NT_WINDOW_SHIFT))" 'Type text | Backspace: edit | Enter: continue | Esc: cancel'
        redraw=0
      elif [ "$_NT_WINDOW_TOO_SMALL" != 1 ]; then
        _nt_window_footer
        printf '\033[s' >&3; _nt_window_brand; printf '\033[u' >&3
      fi
    elif [ "$redraw" = 1 ]; then
      redraw=0
      printf '\r\033[2K%s (Enter: continue, Esc: cancel)\n' "$title" >&3
    fi
    if [ "${_NT_WINDOW_TOO_SMALL:-0}" != 1 ]; then
      if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then
        printf '\033[%s;1H\033[2K' "$_NT_WINDOW_LOG_FIRST" >&3
      else
        printf '\r\033[2K' >&3
      fi
      shown="$value"
      if [ "$hidden" = 1 ]; then printf -v shown '%*s' "${#value}" ''; shown=${shown// /*}; fi
      local field_width=$((${_NT_WINDOW_COLS:-80} - 4))
      if [ "${#shown}" -gt "$field_width" ]; then shown="${shown: -field_width}"; fi
      printf '\033[?25h> %s\033[K' "$shown" >&3
    fi
    key=''; IFS= read -rn1 -t 1 key <&3; status=$?
    if [ "$status" != 0 ]; then [ "$status" -gt 128 ] || return 130; continue; fi
    case "$key" in
      $'\033')
        tail=''; IFS= read -rn1 -t 0.4 tail <&3 || return 130
        # Consume CSI/SS3 keyboard sequences; arrows never become username text.
        if [[ "$tail" = '[' || "$tail" = O ]]; then
          for ((i=0;i<16;i++)); do
            tail=''; IFS= read -rn1 -t 0.4 tail <&3 || break
            [[ "$tail" = [A-Za-z~] ]] && break
          done
        fi ;;
      *)
        [ "${_NT_WINDOW_TOO_SMALL:-0}" != 1 ] || continue
        case "$key" in
          ''|$'\r') printf '%s\n' "$value"; return 0 ;;
          $'\177'|$'\b') value="${value%?}" ;;
          *) [[ "$key" < ' ' ]] || { [ "${#value}" -ge 1024 ] || value+="$key"; } ;;
        esac ;;
    esac
  done
)
