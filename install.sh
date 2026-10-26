#!/data/data/com.termux/files/usr/bin/sh
# Official checkout bootstrap; the managed installer owns workstation setup.
set -eu
prefix=${PREFIX:-}
[ "$prefix" = /data/data/com.termux/files/usr ] && [ -n "${TERMUX_VERSION:-}" ] || {
  echo 'Run this installer in Native Termux on Android.' >&2; exit 2;
}
[ -r /dev/tty ] || { echo 'An attached Termux terminal is required.' >&2; exit 2; }
checkout=${TERNUXX_CHECKOUT:-$HOME/ternuxx}
case "$checkout" in "$HOME"/*) ;; *) echo 'Checkout must be inside Native HOME.' >&2; exit 2 ;; esac
# Refuse traversal and symlink ancestors before touching the checkout.
relative=${checkout#"$HOME"/}
current=$HOME
saved_ifs=$IFS
IFS=/
set -f
for part in $relative; do
  case "$part" in ''|.|..) echo 'Unsafe checkout path; preserved.' >&2; exit 2 ;; esac
  current=$current/$part
  [ ! -L "$current" ] || { echo 'Checkout path contains a symlink; preserved.' >&2; exit 2; }
done
set +f
IFS=$saved_ifs
[ ! -L "$checkout" ] || { echo 'Refusing a symlink checkout.' >&2; exit 2; }
if ! command -v git >/dev/null 2>&1 || ! command -v flock >/dev/null 2>&1; then
  pkg update -y
  pkg install -y git util-linux
fi
if [ -e "$checkout" ]; then
  [ -d "$checkout/.git" ] || { echo 'Existing target is not a Git checkout; preserve it and choose another path.' >&2; exit 2; }
  origin=$(git -C "$checkout" remote get-url origin)
  case "$origin" in
    https://github.com/soobujmiah/ternuxx|https://github.com/soobujmiah/ternuxx.git|git@github.com:soobujmiah/ternuxx.git) ;;
    *) echo 'Existing checkout has a different origin; preserved.' >&2; exit 2 ;;
  esac
  [ -z "$(git -C "$checkout" status --porcelain)" ] || { echo 'Checkout has local changes; commit/preserve them before bootstrap update.' >&2; exit 2; }
  [ "$(git -C "$checkout" branch --show-current)" = main ] || { echo 'Switch your clean checkout to main before bootstrap update.' >&2; exit 2; }
  git -C "$checkout" fetch origin main
  git -C "$checkout" merge --ff-only origin/main
else
  git clone --branch main --single-branch https://github.com/soobujmiah/ternuxx.git "$checkout"
fi
# curl/wget pipelines must not consume the installer's keyboard input.
exec "$prefix/bin/bash" "$checkout/tx" install </dev/tty >/dev/tty 2>/dev/tty
