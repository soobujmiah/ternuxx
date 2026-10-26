# Dependency-free selector. stdout is IDs; input/rendering use the terminal.
_nt_pick() (
  local title="$1" mode="$2" defaults="$3"; shift 3
  local -a items=("$@") selected=()
  local index=0 offset=0 height rows columns key tail item id i mark
  [ -t 0 ] && [ "${TERM:-dumb}" != dumb ] || {
    printf 'Selection needs an attached terminal with arrow keys.\n' >&2; return 2;
  }
  [ ${#items[@]} -gt 0 ] || return 2
  exec 3<>/dev/tty || return 2
  for item in "${items[@]}"; do
    id="${item%%|*}"
    case ",$defaults," in *",$id,"*) selected+=(1) ;; *) selected+=(0) ;; esac
  done
  if [ "${_NT_WINDOW_ACTIVE:-0}" != 1 ]; then
    printf '\033[?1049h' >&3
    trap 'printf "\033[?1049l" >&3' EXIT
  fi
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  while :; do
    read -r rows columns < <(stty size <&3 2>/dev/null)
    rows="${rows:-24}"; columns="${columns:-80}"
    [ "$rows" -ge 7 ] || rows=24
    [ "$columns" -ge 10 ] || columns=80
    height=$((rows - 5))
    if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then
      _nt_window_size
      height=$((_NT_WINDOW_LOG_LAST - _NT_WINDOW_LOG_FIRST - 2))
      [ "$height" -gt 0 ] || height=1
    fi
    [ "$index" -ge "$offset" ] || offset="$index"
    [ "$index" -lt "$((offset + height))" ] || offset=$((index - height + 1))
    if [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then
      _nt_window_content_clear
    else
      printf '\033[H\033[2J' >&3
    fi
    printf '%s\r\nArrow keys: move | Space: select | Enter: continue | Esc: cancel\r\n' "$title" >&3
    for ((i=offset; i<${#items[@]} && i<offset+height; i++)); do
      mark=' '; [ "${selected[$i]}" = 0 ] || mark=x
      [ "$i" != "$index" ] || printf '\033[7m' >&3
      printf '[%s] %.*s\033[0m\r\n' "$mark" "$((columns - 5))" "${items[$i]#*|}" >&3
    done
    IFS= read -rsn1 key <&3 || return 130
    case "$key" in
      $'\033')
        tail=''
        IFS= read -rsn1 -t 0.15 tail <&3 || return 130
        [[ "$tail" = '[' || "$tail" = O ]] || return 130
        IFS= read -rsn1 -t 0.15 tail <&3 || return 130
        case "$tail" in
          A) index=$(((index + ${#items[@]} - 1) % ${#items[@]})) ;;
          B) index=$(((index + 1) % ${#items[@]})) ;;
        esac ;;
      ' ')
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
      '')
        if [ "$mode" = single ]; then
          printf '%s\n' "${items[$index]%%|*}"; return 0
        fi
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
