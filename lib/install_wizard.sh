# Three-profile guided setup; package changes retain exact-plan apply semantics.
. "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_picker.sh"
. "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_window.sh"
. "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_network.sh"
. "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_preflight.sh"
. "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_master.sh"

_nt_install_system_info() {
  [ "${_NT_WINDOW_ACTIVE:-0}" != 1 ] || return 0
  printf '\n=== Ternuxx installation: detected system ===\n'
  printf 'Device: %s (%s)\n' "$(getprop ro.product.model 2>/dev/null || echo unknown)" "$(getprop ro.product.manufacturer 2>/dev/null || echo unknown)"
  printf 'Android: %s | ABI: %s | Kernel: %s\n' "$(getprop ro.build.version.release 2>/dev/null || echo unknown)" "$(uname -m)" "$(uname -r)"
  printf 'Runtime: Native Termux | PREFIX: %s\n' "${PREFIX:-unknown}"
  awk '/MemTotal:|MemAvailable:/ {printf "%s %.1f GiB\n", $1, $2/1048576}' /proc/meminfo 2>/dev/null
  df -h "${PREFIX:-$HOME}" 2>/dev/null
  printf 'GPU hint: %s (device access is not acceleration proof)\n' "$(getprop ro.soc.model 2>/dev/null || echo unknown)"
  printf 'Press Enter to choose your workstation... ' >/dev/tty
  local answer
  IFS= read -r answer </dev/tty
}

_nt_wizard_prepare() {
  # Bootstrap must work before Python exists. No external curl installer.
  nt_info 'Preparation refreshes signed indexes (pkg update), enables official X11 if needed, and installs Python if missing.'
  _nt_confirm 'Prepare official Termux repositories and installer prerequisites?' || return $?
  _nt_window_run _nt_network_retry 'Package indexes' env -u LD_LIBRARY_PATH pkg update -y || return $?
  if ! _nt_package_installed x11-repo; then
    _nt_window_run env -u LD_LIBRARY_PATH pkg install -y x11-repo || return $?
    _nt_window_run _nt_network_retry 'Package indexes' env -u LD_LIBRARY_PATH pkg update -y || return $?
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    _nt_window_run env -u LD_LIBRARY_PATH pkg install -y python || return $?
  fi
  return 0
}

_nt_wizard_upgrade() {
  # Full system upgrade, unlike the legacy core-only update, is separately
  # previewed, pinned, journaled, and explicitly confirmed in this wizard.
  local simulation fresh package version plan_id
  simulation="$(env -u LD_LIBRARY_PATH apt-get -s --no-remove upgrade 2>&1)" || { printf '%s\n' "$simulation"; return 1; }
  if ! printf '%s\n' "$simulation" | awk '/^Remv / {bad=1} /^Inst / && $0 !~ /termux-main|termux-x11/ {bad=1} END {exit bad}'; then
    nt_fail 'System upgrade contains removals or non-official packages; nothing applied.'; return 1
  fi
  _NT_PLAN_MODE=update
  _NT_PLAN_PACKAGES=(); _NT_PLAN_VERSIONS=(); _NT_PLAN_TRANSACTION=()
  while read -r package version; do
    [ -n "$package" ] || continue
    _NT_PLAN_PACKAGES+=("$package")
    _NT_PLAN_VERSIONS+=("$package=$version")
    _NT_PLAN_TRANSACTION+=("$package=$version")
  done < <(printf '%s\n' "$simulation" | awk '$1=="Inst" {for(i=3;i<=NF;i++) if(substr($i,1,1)=="(") {v=substr($i,2); if(v=="")v=$(i+1); sub(/[)]$/, "", v); print $2,v; break}}')
  [ ${#_NT_PLAN_TRANSACTION[@]} -gt 0 ] || { nt_ok 'System packages are current.'; return 0; }
  _NT_PLAN_SIMULATION="$simulation"
  printf '%s\n' "$simulation"
  _nt_write_install_record preview || return 1
  plan_id="$(_nt_compute_plan_id)" || return 1
  _nt_confirm 'Apply the displayed system upgrade (pkg upgrade equivalent)?' || return $?
  fresh="$(env -u LD_LIBRARY_PATH apt-get -s --no-remove upgrade 2>&1)" || return 1
  [ "$fresh" = "$simulation" ] || { nt_fail 'Upgrade changed; restart installation to review it.'; return 1; }
  _nt_reviewed_preview_matches "$plan_id" >/dev/null || return 1
  _nt_write_install_record applying || return 1
  if ! TERNUXX_WIZARD_ACTIVE=1 _nt_apply_install_transaction; then _nt_write_install_record failed; return 1; fi
  _nt_write_install_record applied
}

_nt_wizard_native() {
  local components="$1" output plan_id status
  # Exact selection is shared with advanced preview/apply, not a second resolver.
  output="$(TERNUXX_WIZARD_ACTIVE=1 TERNUXX_JSON=1 nt_cmd_install preview --profile custom --components "$components")" || return $?
  command python3 -c '
import json, sys
d=json.load(sys.stdin)
roots=d.get("packages", [])
print("Native management/workstation plan")
print("Requested packages:", len(roots), "| Total package changes:", len(d.get("transaction", [])))
if roots: print("Includes: " + ", ".join(p.split("=",1)[0] for p in roots))
if d.get("install") == "already_installed": print("All selected components are already installed.")
' <<<"$output" || return 1
  status="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["install"])' <<<"$output")" || return 1
  [ "$status" != already_installed ] || return 0
  plan_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_id"])' <<<"$output")" || return 1
  _nt_confirm 'Install the displayed Native package selection?' || return $?
  TERNUXX_WIZARD_ACTIVE=1 nt_cmd_install apply --profile custom --components "$components" --yes --plan-id "$plan_id"
  local result=$?
  if [ "$result" -ne 0 ] && [ "${_NT_NATIVE_RESUME_DEPTH:-0}" = 0 ]; then
    nt_warn 'Some stages may have completed. Resume rebuilds and reviews the exact remaining package plan; cached packages are reverified.'
    if _nt_confirm 'Resume Native setup from current verified package state?'; then
      _NT_NATIVE_RESUME_DEPTH=1 _nt_wizard_native "$components"
      return $?
    fi
  fi
  return "$result"
}

_nt_wizard_entrypoint() {
  local root="$1" output fields plan_id changed target
  output="$(python3 "$root/scripts/cli_entrypoint.py" preview)" || { nt_fail 'CLI command preview failed; installed packages were preserved.'; return 1; }
  fields="$(command python3 -c '
import json, re, sys
try:
    envelope = json.load(sys.stdin)
    data = envelope["data"]
    if envelope.get("ok") is not True or type(data["changed"]) is not bool:
        raise ValueError("invalid preview status")
    if not re.fullmatch(r"[0-9a-f]{64}", data["plan_id"]):
        raise ValueError("invalid plan identity")
    print(int(data["changed"]), data["plan_id"], data["target"])
except (KeyError, TypeError, ValueError) as exc:
    print("Cannot read CLI entrypoint preview: " + str(exc), file=sys.stderr)
    sys.exit(2)
' <<<"$output")" || return $?
  read -r changed plan_id target <<<"$fields"
  [ "$changed" = 1 ] || { nt_ok 'tx command is already current.'; return 0; }
  nt_info "tx command target: $target (checkout-backed; rollback retained)."
  _nt_confirm 'Install / update the tx command for this checkout?' || return $?
  output="$(python3 "$root/scripts/cli_entrypoint.py" apply --yes --plan-id "$plan_id")" || { nt_fail 'CLI command installation failed; inspect the retained recovery record.'; return 1; }
  nt_ok 'tx command installed and verified.'
}

_nt_install_wizard() {
  [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] || { nt_fail 'Run tx install in an attached terminal; automation uses tx install preview.'; return 2; }
  nt_require_termux || return 1
  local profile components=terminal,developer,proot,audio,graphics,gui,services desktops apps="" distros="" distro root answer ai_runtimes ai_default=cpu ai_npu=0 gpu_probe soc
  local -a ai_runtime_options=('none|Do not install an AI runtime now' 'cpu|CPU runtime and automatic CPU fallback (Termux llama-cpp)')
  root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
  _nt_install_system_info || return $?
  profile="$(_nt_pick 'Choose your workstation' single '' \
    'minimal|Minimal: CLI/TUI/Web, terminal/build tools and PRoot CLI provider' \
    'native|Native Full: Minimal + GUI management, GPU tools, desktops and apps' \
    'proot|Native Full + PRoot: Native selection + one or more managed distros')" || return $?
  if [ "$profile" != minimal ]; then
    desktops="$(_nt_pick 'Native desktops (select one or more)' multi xfce \
      'xfce|XFCE' 'mate|MATE' 'plasma|KDE Plasma')" || return $?
    components+=,gui,audio,sound-controls,graphics
    case ",$desktops," in *,xfce,*) components+=,desktop ;; esac
    case ",$desktops," in *,mate,*) components+=,mate ;; esac
    case ",$desktops," in *,plasma,*) components+=,plasma ;; esac
    nt_info 'Writer-only is unavailable in Native Termux: libreoffice is a monolithic suite. It is not silently installed.'
    apps="$(_nt_choose_native_apps)" || return $?
    for answer in ${apps//,/ }; do [ "$answer" = none ] || components+=,"$answer"; done
  fi
  soc="$(getprop ro.soc.model 2>/dev/null || true)"
  if [ "$soc" = SM8735 ]; then
    ai_runtime_options+=('npu|Experimental Snapdragon HTP0 runtime (SM8735; exact pinned archive)')
    ai_default=npu
  fi
  gpu_probe="$(_nt_gpu_probe "$root" 2>/dev/null || true)"
  if [[ "$gpu_probe" = supported\|* ]]; then
    ai_runtime_options+=('vulkan|Vulkan GPU runtime (Termux llama-cpp-backend-vulkan)')
    [ "$ai_default" != cpu ] || ai_default=vulkan
  fi
  ai_runtimes="$(_nt_pick 'Native AI runtimes (select one or more)' multi "$ai_default" "${ai_runtime_options[@]}")" || return $?
  [[ ",$ai_runtimes," != *",cpu,"* ]] || components+=,ai-cpu
  [[ ",$ai_runtimes," != *",vulkan,"* ]] || components+=,ai-vulkan
  if [[ ",$ai_runtimes," = *",npu,"* ]]; then components+=,ai-cpu; ai_npu=1; fi
  if [ "$profile" = proot ]; then
    components+=,nested
    distros="$(_nt_pick 'Managed PRoot distributions (one or more)' multi debian \
      'debian|Debian Trixie' 'ubuntu|Ubuntu Noble')" || return $?
  fi
  _nt_ai_guidance native "$apps"
  _nt_master_workstation "$root" "$components" "$distros" "" "$ai_npu" || return $?
  nt_ok 'Selected setup stages completed. No desktop was started.'
  nt_info 'Commands: tx tui | tx web | tx gui | tx start | tx pgui'

}

_nt_choose_guest_desktops() {
  local distro="$1" root="$2" choices choice
  local -a items=('none|CLI only / no desktop environment')
  choices="$(PYTHONPATH="$root/lib" command python3 - "$distro" "$root" <<'PYDESKTOPCHOICES'
import sys, proot_profiles, proot_desktops
profile = proot_profiles.install_profile(sys.argv[2], sys.argv[1])["profile_id"]
for key, item in proot_desktops.PROVIDERS[profile].items():
    routes = sorted(proot_desktops.DESKTOP_ROUTES.get(key, ()))
    if routes:
        print(key + "|" + item["name"] + " (" + ", ".join(routes) + ")")
PYDESKTOPCHOICES
)" || return 1
  while IFS= read -r choice; do [ -z "$choice" ] || items+=("$choice"); done <<<"$choices"
  _nt_pick "$distro desktops (one or more)" multi xfce "${items[@]}"
}

_nt_choose_guest_apps() {
  local distro="$1" root="$2" choices choice
  local -a items=('none|Base / clean workstation only (graphics, CPU rendering, audio)')
  choices="$(PYTHONPATH="$root/lib" command python3 - "$distro" <<'PYAPPCHOICES'
import sys, proot_software
for key, (name, packages) in proot_software.catalog(sys.argv[1]).items():
    print(key + "|" + name)
PYAPPCHOICES
)" || return 1
  while IFS= read -r choice; do [ -z "$choice" ] || items+=("$choice"); done <<<"$choices"
  _nt_pick "$distro optional software" multi none "${items[@]}"
}

_nt_install_guest_addons() {
  local distro="$1" desktops="$2" apps="$3" desktops_set="$4" apps_set="$5" root="$6" output status plan_id
  [ "$desktops_set" = 1 ] || desktops="$(_nt_choose_guest_desktops "$distro" "$root")" || return $?
  [ "$apps_set" = 1 ] || apps="$(_nt_choose_guest_apps "$distro" "$root")" || return $?
  if [ "$desktops" != none ] && [[ ",$apps," != *,cpu-runtime,* ]] && [[ ",$apps," != *,graphics-runtime,* ]]; then
    apps="${apps:+$apps,}cpu-runtime"
  fi
  if [ "${_NT_GUEST_READY[$distro]:-0}" != 1 ]; then _nt_collect_guest_account "$distro" "$root" || return $?; fi
  if [ "${_NT_GUEST_ACCOUNT_NEEDED[$distro]:-}" = create ]; then
    apps="${apps:+$apps,}account-tools"
  fi
  _nt_ai_guidance "$distro" "$apps"
  apps=",$apps,"; apps="${apps//,none,/,}"; apps="${apps#,}"; apps="${apps%,}"
  local -a args=(desktop-preview --repo-root "$root" --alias "$distro" --desktops "$desktops" --json)
  [ -z "$apps" ] || args+=(--apps "$apps")
  output="$(_nt_window_query "Review $distro packages and download sizes" python3 "$root/lib/proot_setup.py" "${args[@]}")" || return $?
  command python3 -c '
import json,sys
d=json.load(sys.stdin)
print("Existing guest additions")
print("Guest:", sys.argv[1], "| Desktops:", sys.argv[2], "| Apps:", sys.argv[3] or "base only")
print("Status:", d.get("status", "unknown"))
print("Existing rootfs and accounts are preserved; no removals or upgrades.")
' "$distro" "$desktops" "$apps" <<<"$output" || return 1
  status="$(command python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$output")" || return 1
  [ "$status" != already_installed ] || { nt_ok 'Selected guest desktops/apps are already installed.'; _nt_apply_guest_account "$distro" "$root"; return $?; }
  plan_id="$(command python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_id"])' <<<"$output")" || return 1
  _nt_confirm "Add the displayed desktops/apps to existing $distro (no rootfs replacement)?" || return $?
  _nt_window_run python3 "$root/lib/proot_setup.py" desktop-install --repo-root "$root" --yes --plan-id "$plan_id" --json || return $?
  _nt_apply_guest_account "$distro" "$root"
}

_nt_install_native_desktop() {
  [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] || { nt_fail 'Desktop shortcuts need an attached terminal; automation uses install preview/apply.'; return 2; }
  local desktop="${1/xfce4/xfce}" root="${_TN_LIB_DIR%/lib}" components=gui,developer,audio,sound-controls,graphics
  shift
  [ $# -eq 0 ] || { nt_fail 'Use tx install NATIVE_DE; guest desktops use tx install proot DISTRO DE.'; return 2; }
  case "$desktop" in
    xfce) components+=,desktop ;;
    mate|plasma) components+=,"$desktop" ;;
    *) nt_fail 'Supported Native desktops: xfce, mate, plasma.'; return 2 ;;
  esac
  nt_require_termux || return 1
  _nt_master_workstation "$root" "$components" ""
}

_nt_install_proot_short() {
  [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] || { nt_fail 'Guest shortcuts need an attached terminal; automation uses install DISTRO preview/apply.'; return 2; }
  local distro="${1:-}" desktop="${2:-}" root="${_TN_LIB_DIR%/lib}"
  [ $# -le 2 ] || { nt_fail 'Use tx install proot [debian|ubuntu] [DESKTOP].'; return 2; }
  if [ -z "$distro" ]; then
    distro="$(_nt_pick 'Choose a managed PRoot distro' single '' 'debian|Debian Trixie' 'ubuntu|Ubuntu Noble')" || return $?
  fi
  case "$distro" in debian|ubuntu) ;; *) nt_fail 'Supported managed distros: debian, ubuntu.'; return 2 ;; esac
  nt_require_termux || return 1
  if [ -n "$desktop" ]; then
    PYTHONPATH="$root/lib" command python3 - "$distro" "${desktop/xfce4/xfce}" <<'PYSHORTDESKTOP' || return $?
import sys, proot_profiles, proot_desktops
profile = proot_profiles.profile_for_alias(sys.argv[1])
available = [key for key in proot_desktops.catalog(profile) if proot_desktops.DESKTOP_ROUTES.get(key)]
if sys.argv[2] != "none" and sys.argv[2] not in available:
    print("Supported guest desktops: " + ", ".join(available), file=sys.stderr)
    raise SystemExit(2)
PYSHORTDESKTOP
  fi
  _nt_master_workstation "$root" proot,guest-display,gui,developer "$distro" "${desktop/xfce4/xfce}"
}

_nt_gpu_probe() {
  PYTHONPATH="$1/lib" command python3 - <<'PYGPUPROBE'
import os, graphics_manager
ok, device, reason = graphics_manager._termux_freedreno_device(os.environ.get("PREFIX", ""))
print(("supported|" + str(device)) if ok else ("unavailable|" + str(reason)))
PYGPUPROBE
}

_nt_gpu_setup() {
  local root="$1" target backend choices choice distros distro probe gpu_preview gpu_plan selected current_guest_backend
  local -a native_options=('system|Native CPU/Mesa software fallback (always available)') proot_options=('runtime|PRoot CPU/Mesa software fallback (always available)') active_options=('keep|Keep current Native backend' 'system|System Mesa / CPU fallback')
  target="$(_nt_pick 'Graphics/sound setup (select every provider to prepare)' multi 'native,proot' \
    'native|Native Termux' 'proot|Managed PRoot guests' 'none|Keep all existing setup')" || return $?
  [[ ",$target," = *,none,* ]] && return 0
  nt_info "Device: $(getprop ro.product.model 2>/dev/null || echo unknown); SoC: $(getprop ro.soc.model 2>/dev/null || echo unknown)."
  if [ "${2:-0}" = 1 ]; then
    _nt_wizard_native audio,graphics,proot || return $?
  fi
  nt_info 'CPU rendering remains the fallback. Selected compatible providers are installed; one backend at a time is selected for new Native desktop starts.'
  if [[ ",$target," = *,native,* ]]; then
    probe="$(_nt_gpu_probe "$root")" || return $?
    if [[ "$probe" = supported\|* ]]; then
      native_options+=( 'termux-zink|Termux Zink + Freedreno ICD (device enumeration passed)' )
    else
      nt_info "Native Termux Zink not selected: ${probe#*|}. Stock Vulkan ICD enumeration is required before this route can be offered."
    fi
    if [ -r /dev/kgsl-3d0 ] && [ "$(getprop ro.soc.model 2>/dev/null)" = SM8735 ]; then
      native_options+=( 'kgsl-freedreno|Pinned experimental Adreno 825 KGSL Mesa (verified candidate)' )
      nt_info 'This Adreno 825 candidate is isolated and checksum-pinned; applying it preserves the Termux system Mesa.'
    fi
    local native_defaults=system
    [[ "$probe" != supported\|* ]] || native_defaults+=,termux-zink
    if [ -r /dev/kgsl-3d0 ] && [ "$(getprop ro.soc.model 2>/dev/null)" = SM8735 ]; then native_defaults+=,kgsl-freedreno; fi
    selected="$(_nt_pick 'Native graphics providers to install (compatible choices preselected)' multi "$native_defaults" "${native_options[@]}")" || return $?
    if [[ ",$selected," = *,kgsl-freedreno,* ]]; then
      gpu_preview="$(python3 "$root/lib/native_gpu_setup.py" preview)" || return $?
      gpu_plan="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_id"])' <<<"$gpu_preview")" || return 1
      nt_info 'Review the pinned KGSL plan below; it downloads only the pinned release, verifies its checksum, privately extracts and probes it.'
      _nt_confirm 'Apply this exact experimental Native KGSL plan?' || return $?
      _nt_window_run python3 "$root/lib/native_gpu_setup.py" apply --yes --plan-id "$gpu_plan" || return $?
    fi
    if [[ ",$selected," = *,termux-zink,* ]]; then
      nt_info 'Termux Zink packages were included in the Native graphics profile; the stock Freedreno ICD passed device enumeration.'
    fi
    [[ ",$selected," = *,termux-zink,* ]] && active_options+=( 'termux-zink|Termux Zink + Freedreno ICD' )
    [[ ",$selected," = *,kgsl-freedreno,* ]] && active_options+=( 'kgsl-freedreno|Pinned experimental Adreno 825 KGSL Mesa' )
    backend="$(_nt_pick 'Native backend for future desktop starts' single '' "${active_options[@]}")" || return $?
    if [ "$backend" != keep ]; then
      _nt_confirm "Select Native $backend for future starts? A running desktop is not restarted." || return $?
      if [ "$backend" = kgsl-freedreno ]; then
        # The verified acquisition plan above performs selection only after its compatibility probe.
        :
      else
        "$root/tx" mng graphics select native "$backend" || return $?
      fi
    fi
  fi
  if [[ ",$target," = *,proot,* ]]; then
    if [ -r /dev/kgsl-3d0 ]; then
      proot_options=( 'zink|PRoot Zink/Turnip + CPU rendering/audio (KGSL detected; verify workload separately)' "${proot_options[@]}" )
    else
      nt_info 'No readable KGSL device: accelerated managed Zink/Turnip is not offered on this device.'
    fi
    local proot_defaults=runtime
    [ ! -r /dev/kgsl-3d0 ] || proot_defaults+=,zink
    backend="$(_nt_pick 'PRoot graphics runtime (select installable routes)' multi "$proot_defaults" "${proot_options[@]}")" || return $?
    distros="$(_nt_pick 'Configure guest runtimes (one or more)' multi debian 'debian|Debian Trixie' 'ubuntu|Ubuntu Noble')" || return $?
    for distro in ${distros//,/ }; do
      local app=cpu-runtime
      [[ ",$backend," != *,zink,* ]] || app=graphics-runtime
      _nt_install_managed_guest "$distro" --desktops none --apps "$app" || return $?
    done
    current_guest_backend="$(PYTHONPATH="$root/lib" python3 -m proot_graphics_selection status | python3 -c 'import json,sys; print(json.load(sys.stdin)["backend"])')" || return $?
    local -a guest_backends=()
    if [[ ",$backend," = *,zink,* ]]; then
      if [ "$current_guest_backend" = zink ]; then
        guest_backends=( 'zink|Zink + Turnip (KGSL; workload verification separate)' 'cpu|CPU/Mesa software rendering' )
      else
        guest_backends=( 'cpu|CPU/Mesa software rendering' 'zink|Zink + Turnip (KGSL; workload verification separate)' )
      fi
    else
      guest_backends=( 'cpu|CPU/Mesa software rendering' )
    fi
    guest_backend="$(_nt_pick 'PRoot backend for future desktop starts' single '' "${guest_backends[@]}")" || return $?
    _nt_confirm "Save PRoot $guest_backend for future desktop starts? A running guest desktop is not restarted." || return $?
    PYTHONPATH="$root/lib" python3 -m proot_graphics_selection select "$guest_backend" || return $?
    nt_info 'PRoot VirGL is not offered as installable: this checkout has a verifier route but no managed VirGL server install/lifecycle. CPU and managed Zink/Turnip routes are available above.'
  fi
  nt_info 'Configuration only. Verify a bounded workload separately; provider detection or installation does not prove accelerated rendering.'
}

_nt_install_gpu() {
  [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] || { nt_fail 'Run tx install gpu in an attached terminal.'; return 2; }
  nt_require_termux || return 1
  local root="${_TN_LIB_DIR%/lib}"
  _nt_gpu_setup "$root" 1
}

# Session-memory-only choices. Passwords never enter env, argv, logs or saved plans.
declare -gA _NT_GUEST_READY _NT_GUEST_USER _NT_GUEST_SUDO _NT_GUEST_DESKTOPS _NT_GUEST_APPS _NT_GUEST_PASSWORD _NT_GUEST_ACCOUNT_NEEDED
_nt_collect_guest_account() {
  local distro="$1" root="$2" user='' sudo_mode=password password='' confirmation=''
  _NT_WINDOW_INSTALLING=0
  _nt_window_selection "Choose $distro login account"
  _NT_GUEST_ACCOUNT_NEEDED[$distro]=''
  local existing=0 candidates='' choice
  local -a account_options=()
  if [ -e "$PREFIX/var/lib/proot-distro/containers/$distro" ]; then
    existing=1
    candidates="$(python3 "$root/lib/proot_account_setup.py" users --alias "$distro")" || return $?
    while IFS= read -r choice; do [ -z "$choice" ] || account_options+=("account:$choice|Use existing account: $choice"); done < <(python3 -c 'import json,sys; print("\n".join(json.load(sys.stdin)))' <<<"$candidates")
    if [ "${#account_options[@]}" -gt 0 ]; then
      account_options+=("new|Create a new guest username")
      choice="$(_nt_pick "Choose $distro login account" single '' "${account_options[@]}")" || return $?
      if [[ "$choice" = account:* ]]; then
        user="${choice#account:}"
        _NT_GUEST_ACCOUNT_NEEDED[$distro]=select
      else
        _NT_GUEST_ACCOUNT_NEEDED[$distro]=create
      fi
    else
      nt_info "$distro has no ordinary login account. The reviewed installer will create one, preserving the rootfs."
      _NT_GUEST_ACCOUNT_NEEDED[$distro]=create
    fi
  fi
  if [ -z "$user" ]; then
    while :; do
      user="$(_nt_input "New $distro guest username (letters, digits, _ or -)")" || return $?
      [[ "$user" =~ ^[a-z_][a-z0-9_-]{0,31}$ && "$user" != root ]] && break
      nt_warn 'Use an ordinary Linux username (letters/digits/_/-).'
    done
    sudo_mode="$(_nt_pick "$distro guest sudo authentication" single '' \
      'password|Password-protected sudo (recommended)' 'passwordless|Guest-only passwordless sudo')" || return $?
    if [ "$sudo_mode" = password ]; then
      while :; do
        password="$(_nt_input 'Create guest sudo password (hidden)' 1)" || return $?
        confirmation="$(_nt_input 'Confirm guest sudo password (hidden)' 1)" || return $?
        if [ "$password" = "$confirmation" ] && [ ${#password} -ge 4 ] && [ ${#password} -le 1024 ]; then break; fi
        nt_warn 'Passwords must match and contain 4–1024 characters.'
      done
    fi
  fi
  _NT_GUEST_USER[$distro]="$user"; _NT_GUEST_SUDO[$distro]="$sudo_mode"
  _NT_GUEST_PASSWORD[$distro]="$password"; _NT_GUEST_READY[$distro]=1
  password=''; confirmation=''
}


_nt_collect_guest() {
  local distro="$1" root="$2"
  _nt_collect_guest_account "$distro" "$root" || return $?
  if [ -n "${_NT_MASTER_PRESET_DESKTOP:-}" ]; then _NT_GUEST_DESKTOPS[$distro]="$_NT_MASTER_PRESET_DESKTOP"; else
    _NT_GUEST_DESKTOPS[$distro]="$(_nt_choose_guest_desktops "$distro" "$root")" || return $?
  fi
  _NT_GUEST_APPS[$distro]="$(_nt_choose_guest_apps "$distro" "$root")" || return $?
}

_nt_apply_guest_account() {
  local distro="$1" root="$2" output plan_id credential_fd='' result
  [ -n "${_NT_GUEST_ACCOUNT_NEEDED[$distro]:-}" ] || return 0
  output="$(python3 "$root/lib/proot_account_setup.py" preview --alias "$distro" --user "${_NT_GUEST_USER[$distro]}" --sudo-mode "${_NT_GUEST_SUDO[$distro]}")" || return $?
  plan_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_id"])' <<<"$output")" || return 1
  nt_info "Guest account plan: ${_NT_GUEST_ACCOUNT_NEEDED[$distro]} ${_NT_GUEST_USER[$distro]} in $distro; existing accounts/passwords stay unchanged."
  _nt_confirm 'Apply this exact ordinary-account plan for guest login and GUI?' || return $?
  local -a args=(apply --yes --plan-id "$plan_id")
  if [ "${_NT_GUEST_ACCOUNT_NEEDED[$distro]}" = create ] && [ "${_NT_GUEST_SUDO[$distro]}" = password ]; then
    exec {credential_fd}< <(printf '%s\n' "${_NT_GUEST_PASSWORD[$distro]}")
    args+=(--password-fd "$credential_fd")
  fi
  _nt_window_run python3 "$root/lib/proot_account_setup.py" "${args[@]}"
  result=$?
  [ -z "$credential_fd" ] || exec {credential_fd}<&-
  unset '_NT_GUEST_PASSWORD[$distro]'
  return "$result"
}
