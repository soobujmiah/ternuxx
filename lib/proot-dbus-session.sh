#!/data/data/com.termux/files/usr/bin/bash
# Supervisor adapter: keep D-Bus inside Debian instead of exporting a host bus.
set -euo pipefail
expected="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/proot-xfce-wrapper.sh"
if [[ "$#" -ne 2 || "$1" != "--exit-with-session" || "$(readlink -f -- "$2" 2>/dev/null || true)" != "$(readlink -f -- "$expected")" ]]; then
  echo "refusing unsupported PRoot D-Bus session command" >&2
  exit 64
fi
exec "$expected"
