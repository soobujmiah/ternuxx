# One workstation approval after every selection and exact subplan is collected.
_nt_master_prepare() {
  local -a prerequisites=()
  command -v python3 >/dev/null || prerequisites+=(python)
  _nt_package_installed x11-repo || prerequisites+=(x11-repo)
  if [ "${#prerequisites[@]}" -gt 0 ]; then
    _nt_confirm "Bootstrap missing planner prerequisites ONLY: ${prerequisites[*]}? Workstation install requires combined approval later." || return 130
    _nt_window_run _nt_network_retry 'Bootstrap metadata' env -u LD_LIBRARY_PATH pkg update -y || return $?
    _nt_window_run env -u LD_LIBRARY_PATH pkg install -y --no-upgrade "${prerequisites[@]}" || return $?
  fi
  _nt_confirm 'Refresh signed package indexes for planning? No package install or upgrade.' || return 130
  _nt_window_run _nt_network_retry 'Planning metadata' env -u LD_LIBRARY_PATH pkg update -y
}

_nt_master_gpu_choices() {
  local root="$1" distro runtime probe app cleaned option
  local -a choices=('keep|Preserve current Native GPU preference' 'system|System defaults / CPU fallback for future starts')
  probe="$(_nt_gpu_probe "$root")" || return $?
  if [[ "$probe" = supported\|* ]]; then
    option='termux-zink|Native Zink/Turnip (enumeration passed; workload verification separate)'
    if [ -e "$TERNUXX_STATE_DIR/native-graphics-prefix" ] || [ -e "$TERNUXX_STATE_DIR/native-graphics-backend" ]; then choices+=("$option"); else choices=("$option" "${choices[@]}"); fi
  fi
  if [ -r /dev/kgsl-3d0 ] && [ "$(getprop ro.soc.model 2>/dev/null)" = SM8735 ]; then
    option='kgsl-freedreno|Pinned experimental Adreno 825 Mesa'
    if [ -e "$TERNUXX_STATE_DIR/native-graphics-prefix" ] || [ -e "$TERNUXX_STATE_DIR/native-graphics-backend" ]; then choices+=("$option"); else choices=("$option" "${choices[@]}"); fi
  fi
  _NT_MASTER_BACKEND="$(_nt_pick 'Native GPU choice for the combined plan' single '' "${choices[@]}")" || return $?
  for distro in ${_NT_MASTER_DISTROS//,/ }; do
    local -a runtime_options=('cpu-runtime|CPU rendering + sound; preserve GPU files')
    [ ! -r /dev/kgsl-3d0 ] || runtime_options=('graphics-runtime|Managed pinned Turnip/Zink + CPU + sound (KGSL detected)' "${runtime_options[@]}")
    runtime="$(_nt_pick "$distro graphics/audio runtime for the combined plan" single '' "${runtime_options[@]}")" || return $?
    cleaned=''
    for app in ${_NT_GUEST_APPS[$distro]//,/ }; do
      case "$app" in cpu-runtime|graphics-runtime) continue ;; esac
      cleaned+="${cleaned:+,}$app"
    done
    _NT_GUEST_APPS[$distro]="${cleaned:+$cleaned,}$runtime"
  done
}

_nt_master_guest_preview() {
  local distro="$1" root="$2" folder="$3" apps="${_NT_GUEST_APPS[$1]}" result groups=base app
  local -a args=()
  apps=",$apps,"; apps="${apps//,none,/,}"; apps="${apps#,}"; apps="${apps%,}"
  if [ -e "$PREFIX/var/lib/proot-distro/containers/$distro" ]; then
    if [ "${_NT_GUEST_ACCOUNT_NEEDED[$distro]:-}" = create ]; then apps="${apps:+$apps,}account-tools"; fi
    args=(desktop-preview --repo-root "$root" --alias "$distro" --desktops "${_NT_GUEST_DESKTOPS[$distro]}" --json)
    [ -z "$apps" ] || args+=(--apps "$apps")
    result="$(_nt_window_query "Resolve all $distro dependencies and disk/download sizes" python3 "$root/lib/proot_setup.py" "${args[@]}")" || return $?
    printf '%s\n' "$result" >"$folder/guest-$distro.part.json"
    if [ -n "${_NT_GUEST_ACCOUNT_NEEDED[$distro]:-}" ]; then
      python3 "$root/lib/proot_account_setup.py" preview --allow-system-accounts --alias "$distro" --user "${_NT_GUEST_USER[$distro]}" --sudo-mode "${_NT_GUEST_SUDO[$distro]}" >"$folder/account-$distro.part.json" || return $?
    fi
  else
    for app in ${apps//,/ }; do groups+=,app-"$app"; done
    result="$(_nt_window_query "Resolve $distro fresh-rootfs plan" python3 "$root/lib/proot_setup.py" fresh-preview --repo-root "$root" --alias "$distro" --user "${_NT_GUEST_USER[$distro]}" --sudo-mode "${_NT_GUEST_SUDO[$distro]}" --desktops "${_NT_GUEST_DESKTOPS[$distro]}" --groups "$groups" --json)" || return $?
    printf '%s\n' "$result" >"$folder/guest-$distro.part.json"
  fi
}

_nt_master_review() {
  local folder="$1" plan="$2" choice line
  local -a report=()
  while IFS= read -r line || [ -n "$line" ]; do report+=("row${#report[@]}|${line:- }"); done <"$folder/report.txt"
  # Always present the report before the approval menu, including size limitations.
  _nt_pick 'Combined plan: download/disk sizes and all selections — Enter/Esc returns' single '' "${report[@]}" >/dev/null || true
  while :; do
    choice="$(_nt_pick "Combined plan ${plan:0:12} — approval starts installation" single '' \
      'details|Read full selections, exact packages, download/disk estimates and unknowns' \
      'approve|Review acknowledgement and approve this exact combined plan' 'cancel|Cancel; no workstation installation')" || return $?
    case "$choice" in
      details) _nt_pick 'Combined plan report — arrows/page keys scroll; Enter/Esc returns' single '' "${report[@]}" >/dev/null || true ;;
      approve)
        # Force the size limitations to be visible in the approval itself.
        _nt_confirm 'Approve known size estimates AND explicitly accept unresolved fresh-rootfs/graphics/build-scratch sizes shown in the report?' || continue
        _nt_confirm "Install exact combined plan ${plan:0:16}? Native + guest changes start only now." && return 0 ;;
      cancel) return 130 ;;
    esac
  done
}

_nt_master_verify() { python3 "$1/lib/install_master_plan.py" verify "$2" "$3"; }
_nt_master_id() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1]));print(d.get("plan_id",d.get("data",{}).get("plan_id","")))' "$1"; }

_nt_master_apply_guest() {
  local root="$1" folder="$2" distro="$3" plan_id kind credential_fd='' rc
  plan_id="$(_nt_master_id "$folder/guest-$distro.part.json")" || return 1
  kind="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["operation"]["operation"])' "$folder/guest-$distro.part.json")" || return 1
  if [[ "$kind" = *desktop-install ]]; then
    if ! python3 -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1]))["status"]=="already_installed" else 1)' "$folder/guest-$distro.part.json"; then
      TERNUXX_INSTALL_LOG=1 _nt_window_run python3 -u "$root/lib/proot_setup.py" desktop-install --repo-root "$root" --yes --plan-id "$plan_id" --json || return $?
    fi
    if [ -f "$folder/account-$distro.part.json" ]; then
      plan_id="$(_nt_master_id "$folder/account-$distro.part.json")" || return 1
      local -a account=(python3 "$root/lib/proot_account_setup.py" apply --yes --plan-id "$plan_id")
      if [ "${_NT_GUEST_ACCOUNT_NEEDED[$distro]}" = create ] && [ "${_NT_GUEST_SUDO[$distro]}" = password ]; then
        exec {credential_fd}< <(printf '%s\n' "${_NT_GUEST_PASSWORD[$distro]}"); account+=(--password-fd "$credential_fd")
      fi
      if _nt_window_run "${account[@]}"; then rc=0; else rc=$?; fi
      [ -z "$credential_fd" ] || exec {credential_fd}<&-
      [ "$rc" = 0 ] || return "$rc"
    fi
  else
    local -a fresh=(python3 -u "$root/lib/proot_setup.py" fresh-install --repo-root "$root" --alias "$distro" --user "${_NT_GUEST_USER[$distro]}" --sudo-mode "${_NT_GUEST_SUDO[$distro]}" --yes --plan-id "$plan_id")
    if [ "${_NT_GUEST_SUDO[$distro]}" = password ]; then
      exec {credential_fd}< <(printf '%s\n' "${_NT_GUEST_PASSWORD[$distro]}"); fresh+=(--password-fd "$credential_fd")
    fi
    if TERNUXX_INSTALL_LOG=1 _nt_window_run "${fresh[@]}"; then rc=0; else rc=$?; fi
    [ -z "$credential_fd" ] || exec {credential_fd}<&-
    [ "$rc" = 0 ] || return "$rc"
  fi
  unset '_NT_GUEST_PASSWORD[$distro]'
}

_nt_master_workstation() {
  local root="$1" components="$2" distros="$3" folder plan native_id distro output entry_id
  local _NT_MASTER_DISTROS="$distros" _NT_MASTER_BACKEND=keep _NT_MASTER_PRESET_DESKTOP="${4:-}"
  _nt_master_prepare || return $?
  umask 077
  python3 -c 'import os,stat,pathlib; p=pathlib.Path(os.environ["TERNUXX_STATE_DIR"])/"wizard-plans"; p.mkdir(mode=0o700,parents=True,exist_ok=True); s=p.lstat(); assert not p.is_symlink() and stat.S_ISDIR(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode & 0o077, "unsafe wizard plan directory"' || return 1
  folder="$(mktemp -d "$TERNUXX_STATE_DIR/wizard-plans/plan.XXXXXXXX")" || return 1
  declare -g _NT_INSTALL_MASTER_FOLDER="$folder"
  _nt_window_stage 'Plan | Collecting every guest account, desktop and app' 'No workstation apply has started'
  for distro in ${distros//,/ }; do _nt_collect_guest "$distro" "$root" || return $?; done
  _nt_master_gpu_choices "$root" || return $?
  _nt_window_stage 'Plan | Resolving Native and guest dependencies' 'No workstation apply has started'
  components+=,system-upgrade
  output="$(TERNUXX_WIZARD_ACTIVE=1 TERNUXX_JSON=1 _nt_window_query 'Resolve Native upgrades and every selected package' nt_cmd_install preview --profile custom --components "$components")" || return $?
  printf '%s\n' "$output" >"$folder/native.part.json"
  for distro in ${distros//,/ }; do _nt_master_guest_preview "$distro" "$root" "$folder" || return $?; done
  python3 "$root/scripts/cli_entrypoint.py" preview >"$folder/entrypoint.part.json" || return $?
  if [ "$_NT_MASTER_BACKEND" = kgsl-freedreno ]; then python3 "$root/lib/native_gpu_setup.py" preview >"$folder/gpu.part.json" || return $?; fi
  python3 - "$folder/choices.part.json" "$components" "$distros" "$_NT_MASTER_BACKEND" <<'PY'
import json,sys
from pathlib import Path
import os,hashlib
p,components,distros,backend=sys.argv[1:]
state=Path(os.environ['TERNUXX_STATE_DIR'])
baseline={n:hashlib.sha256((state/n).read_bytes()).hexdigest() if (state/n).exists() else None for n in ('native-graphics-prefix','native-graphics-backend')}
Path(p).write_text(json.dumps(dict(components=components,distros=distros,native_backend=backend,gpu_baseline=baseline,management='Build/install shared GTK management and checkout-backed tx; no service/desktop activation')))
PY
  plan="$(python3 "$root/lib/install_master_plan.py" build "$folder")" || return $?
  declare -g _NT_INSTALL_MASTER_ID="$plan"
  _nt_master_review "$folder" "$plan" || return $?
  python3 "$root/lib/install_master_plan.py" capacity "$folder" "$plan" || return $?
  _nt_window_stage 'Apply | Native packages + reviewed system upgrades' 'Approved combined plan; live APT output'
  native_id="$(_nt_master_id "$folder/native.part.json")" || return 1
  if [ -n "$native_id" ]; then
    TERNUXX_WIZARD_ACTIVE=1 _nt_window_run nt_cmd_install apply --profile custom --components "$components" --yes --plan-id "$native_id" || return $?
  fi
  _nt_master_verify "$root" "$folder" "$plan" || return $?
  _nt_window_stage 'Apply | Shared command and management client' 'Approved combined plan'
  entry_id="$(_nt_master_id "$folder/entrypoint.part.json")" || return 1
  if python3 -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1]))["data"]["changed"] else 1)' "$folder/entrypoint.part.json"; then
    python3 "$root/scripts/cli_entrypoint.py" apply --yes --plan-id "$entry_id" || return $?
  else
    nt_info 'Reviewed tx command is already current; no launcher write.'
  fi
  _nt_window_run bash "$root/scripts/install-management-center.sh" || return $?
  for distro in ${distros//,/ }; do
    _nt_master_verify "$root" "$folder" "$plan" || return $?
    _nt_window_stage "Apply | $distro reviewed guest packages and account" 'Approved combined plan; live guest APT output'
    _nt_master_apply_guest "$root" "$folder" "$distro" || return $?
  done
  _nt_master_verify "$root" "$folder" "$plan" || return $?
  if [ "$_NT_MASTER_BACKEND" != keep ]; then
    _nt_window_stage 'Apply | Reviewed Native graphics preference' 'No desktop restart or audio playback'
    if [ "$_NT_MASTER_BACKEND" = kgsl-freedreno ]; then
      _nt_window_run python3 "$root/lib/native_gpu_setup.py" apply --yes --plan-id "$(_nt_master_id "$folder/gpu.part.json")" || return $?
    else
      PYTHONPATH="$root/lib" python3 - "$_NT_MASTER_BACKEND" "$root" "$folder/choices.part.json" <<'PY'
import graphics_manager,native_gpu_setup,json,sys,os
backend,root,choices=sys.argv[1:]
if native_gpu_setup._selection(os.environ['TERNUXX_STATE_DIR']) != json.load(open(choices))['gpu_baseline']: raise SystemExit('GPU selection changed; replan before applying')
graphics_manager.configure_native(backend,home=os.environ['HOME'],state_dir=os.environ['TERNUXX_STATE_DIR'],repo_root=root,prefix=os.environ['PREFIX'])
PY
      [ "$?" = 0 ] || return 1
    fi
  fi
  nt_ok "Approved combined workstation plan completed. Report: $folder/report.txt"
  nt_info 'No desktop, SSH service or audio playback was started.'
}
