"""Alpine guest compatibility fixes for Ternuxx-managed PRoot."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile


_GLYCIN_BWRAP_SHIM = r'''#!/bin/sh
# Glycin asks bubblewrap for Linux namespaces, which Android PRoot cannot create.
# Only allow Glycin's known image loader binaries and execute them in the guest.
set -eu
home=/tmp-home
runtime=/tmp-run
data=/tmp-home/.local/share
cache=/tmp-home/.cache
while [ "$#" -gt 0 ]; do
  case "$1" in
    --unshare-all|--unshare-user|--unshare-pid|--unshare-net|--unshare-uts|--unshare-ipc|--unshare-cgroup|--die-with-parent|--new-session|--as-pid-1|--clearenv)
      shift ;;
    --chdir|--dev|--tmpfs|--seccomp|--cap-drop|--uid|--gid|--hostname)
      [ "$#" -ge 2 ] || exit 125
      shift 2 ;;
    --ro-bind|--ro-bind-try|--bind|--bind-try|--symlink|--symlink-try|--remount-ro)
      [ "$#" -ge 3 ] || exit 125
      shift 3 ;;
    --setenv)
      [ "$#" -ge 3 ] || exit 125
      case "$2" in
        HOME) home=$3 ;;
        XDG_RUNTIME_DIR) runtime=$3 ;;
        XDG_DATA_HOME) data=$3 ;;
        XDG_CACHE_HOME) cache=$3 ;;
      esac
      shift 3 ;;
    --)
      shift
      break ;;
    -*)
      exit 125 ;;
    *)
      break ;;
  esac
done
case "${1:-}" in
  /usr/libexec/glycin-loaders/2+/glycin-*) ;;
  *) exit 125 ;;
esac
exec /usr/bin/env -i HOME="$home" XDG_RUNTIME_DIR="$runtime" \
  XDG_DATA_HOME="$data" XDG_CACHE_HOME="$cache" "$@"
'''


def install_glycin_bwrap_shim(rootfs: str | Path) -> Path:
    """Install a constrained loader-only bwrap adapter in an Alpine rootfs."""
    root = Path(rootfs).resolve(strict=True)
    if not root.is_dir() or root == Path("/"):
        raise ValueError("Alpine rootfs identity is invalid")
    usr = root / "usr"
    local = usr / "local"
    bin_dir = local / "bin"
    for directory in (usr, local, bin_dir):
        if directory.is_symlink():
            raise ValueError("Alpine local executable directory is unsafe or unavailable")
        directory.mkdir(mode=0o755, exist_ok=True)
        if not directory.is_dir():
            raise ValueError("Alpine local executable directory is unsafe or unavailable")
    destination = bin_dir / "bwrap"
    if destination.is_symlink():
        raise ValueError("Alpine PRoot bwrap compatibility path is unsafe")
    if destination.exists():
        if (destination.is_file() and destination.read_text(encoding="utf-8") == _GLYCIN_BWRAP_SHIM
                and stat.S_IMODE(destination.stat().st_mode) == 0o755):
            return destination
        raise ValueError("Alpine PRoot bwrap compatibility path already exists")
    fd, temporary = tempfile.mkstemp(prefix=".bwrap-", dir=bin_dir)
    try:
        os.fchmod(fd, 0o755)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(_GLYCIN_BWRAP_SHIM)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return destination
