# Retry metadata/download transport only. Never retry a package mutation blindly.
_nt_network_retry() {
  local label="$1"; shift
  local attempt=1 log result
  log="$(mktemp "${TMPDIR:-$HOME}/ternuxx-network.XXXXXXXX")" || return 1
  while :; do
    "$@" 2>&1 | tee "$log"
    result=${PIPESTATUS[0]}
    [ "$result" -ne 0 ] || { rm -f -- "$log"; return 0; }
    if [ "$attempt" -ge 3 ] || grep -Eiq 'Hash Sum mismatch|checksum.*mismatch|signature|NO_PUBKEY|not signed|Certificate verification|Release file.*expired' "$log"; then
      rm -f -- "$log"; return "$result"
    fi
    if ! grep -Eiq 'Temporary failure resolving|Could not resolve|Failed to fetch|Connection.*timed out|Connection failed|Could not connect|Network is unreachable|Connection reset|Operation timed out|502|503|504|429' "$log"; then
      rm -f -- "$log"; return "$result"
    fi
    nt_warn "$label network interruption; retry $attempt/2 with the same source and verification."
    sleep "$attempt"
    attempt=$((attempt + 1))
  done
}
