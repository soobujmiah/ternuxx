#!/data/data/com.termux/files/usr/bin/bash
set -u
if [ "$#" -lt 2 ]; then
  echo "usage: window_fit_session.sh FIT_HELPER COMMAND [ARG ...]" >&2
  exit 64
fi
helper="$1"
shift
python3 "$helper" --watch >>"${TERNUXX_DESKTOP_LOG:-/dev/null}" 2>&1 &
fit_pid=$!
cleanup_fit() {
  kill -TERM "$fit_pid" 2>/dev/null || true
  wait "$fit_pid" 2>/dev/null || true
}
trap cleanup_fit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
if "$@"; then result=0; else result=$?; fi
exit "$result"
