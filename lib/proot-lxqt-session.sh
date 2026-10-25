# LXQt discovers an arbitrary installed window manager when no user preference
# exists. KWin is present in multi-desktop guests but cannot composite on all
# PRoot/Xephyr routes. Seed only a missing Ternuxx-managed X11 profile with the
# guaranteed lightweight, non-compositing Openbox default; preserve user edits.
nt_proot_lxqt_session_defaults() {
  local config_home="${1:-}"
  local lxqt_dir session_conf
  [ -n "$config_home" ] && [ "${config_home#/}" != "$config_home" ] || return 2
  lxqt_dir="$config_home/lxqt"
  if [ -e "$lxqt_dir" ] || [ -L "$lxqt_dir" ]; then
    [ -d "$lxqt_dir" ] && [ ! -L "$lxqt_dir" ] || return 1
  else
    mkdir -p -- "$lxqt_dir" || return 1
  fi
  session_conf="$lxqt_dir/session.conf"
  if [ -e "$session_conf" ] || [ -L "$session_conf" ]; then
    [ -f "$session_conf" ] && [ ! -L "$session_conf" ] || return 1
    return 0
  fi
  if (umask 077; set -C; printf '%s\n' '[General]' '__userfile__=true' 'window_manager=openbox' > "$session_conf") 2>/dev/null; then
    return 0
  fi
  # A concurrent first launch may have created the regular file.
  [ -f "$session_conf" ] && [ ! -L "$session_conf" ]
}
