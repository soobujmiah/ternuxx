#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
CLI="$ROOT/bin/tx"

# Exercise CLI help, setup, inference, and preview paths on Termux and Linux CI. The only
# package-manager call below is `tx ai runtime preview`; replace apt-get with a
# read-only fixture so this contract test never depends on host package state.
export TERMUX_VERSION="${TERMUX_VERSION:-repo-test}"
export PREFIX="/data/data/com.termux/files/usr"
apt-get() {
  [[ "$#" -ge 3 && "$1" == "-s" && "$2" == "install" ]] || return 2
  printf 'Simulated Termux package transaction: %s\n' "$*"
}
export -f apt-get

main="$(bash "$CLI" --help)"
start="$(bash "$CLI" start --help)"
stop="$(bash "$CLI" stop --help)"
restart="$(bash "$CLI" restart --help)"
status="$(bash "$CLI" status --help)"
install="$(bash "$CLI" install --help)"
remote="$(bash "$CLI" --help remote)"
web="$(bash "$CLI" --help web)"
mng="$(bash "$CLI" --help mng)"
app="$(bash "$ROOT/tx" help app)"
retired="$(bash "$CLI" --help proot)"
terminal="$(bash "$CLI" --help terminal)"
ai_vulkan="$(bash "$ROOT/tx" ai runtime preview vulkan)"
ai_help="$(bash "$ROOT/tx" help ai)"
ai_npu_preview="$(bash "$ROOT/tx" ai npu runtime preview)"

 grep -Fq 'Native Termux host and managed PRoot workstation management' <<<"$main"
grep -Fq 'tx guides' <<<"$main"
grep -Fq 'tx db [--user NAME] (Debian), tx ub (Ubuntu)' <<<"$main"
grep -Fq 'experimental HTP inference routes' <<<"$main"
grep -Fq 'opens its Termux:X11 window automatically' <<<"$start"
grep -Fq 'isolated process group first' <<<"$stop"
grep -Fq 'Stop, then start the Native desktop' <<<"$restart"
grep -Fq 'does not start' <<<"$status"
grep -Fq 'Review exact package transaction' <<<"$install"
grep -Fq 'tx install debian [--user NAME]' <<<"$install"
grep -Fq 'tx install ubuntu [--user NAME]' <<<"$install"
grep -Fq 'Choose, preview, and confirm a Native workstation profile in one session' <<<"$install"
grep -Fq 'Apply the exact saved plan' <<<"$install"
grep -Fq 'native-proot-provider' <<<"$install"
grep -Fq 'does not persist settings' <<<"$remote"
grep -Fq 'public ingress' <<<"$remote"
grep -Fq 'binds to loopback' <<<"$web"
grep -Fq 'cron' <<<"$mng"
grep -Fq 'tx app run directory-tree HOME_PATH' <<<"$app"
grep -Fq 'file contents are not read' <<<"$app"
grep -Fq 'Read-only Termux package simulation' <<<"$ai_vulkan"
grep -Fq 'llama-cpp-backend-vulkan' <<<"$ai_vulkan"
grep -Fq 'tx ai npu status' <<<"$ai_help"
grep -Fq 'backend cpu|vulkan|npu' <<<"$ai_help"
grep -Fq 'inference.npu.runtime.preview' <<<"$ai_npu_preview"
grep -Fq 'plan_id' <<<"$ai_npu_preview"
grep -Fq 'Managed PRoot guests use the Native Termux host' <<<"$retired"
grep -Fq 'tx proot setup fresh-preview' <<<"$retired"
grep -Fq 'tx pgui start --mode nested --desktop xfce --alias ALIAS' <<<"$retired"
grep -Fq 'tx terminal service preview-install' <<<"$terminal"
grep -Fq 'never starts a guest automatically' <<<"$terminal"
grep -Fq 'Ternuxx v' <<<"$(bash "$ROOT/tx" --version)"

echo 'CLI help contract: PASS'
