# Three-profile guided setup; package changes retain exact-plan apply semantics.
. "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_picker.sh"

_nt_install_system_info() {
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
  env -u LD_LIBRARY_PATH pkg update -y || return $?
  if ! _nt_package_installed x11-repo; then
    env -u LD_LIBRARY_PATH pkg install -y x11-repo || return $?
    env -u LD_LIBRARY_PATH pkg update -y || return $?
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    env -u LD_LIBRARY_PATH pkg install -y python || return $?
  fi
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
  if ! _nt_apply_install_transaction; then _nt_write_install_record failed; return 1; fi
  _nt_write_install_record applied
}

_nt_wizard_native() {
  local components="$1" output plan_id status
  # Exact selection is shared with advanced preview/apply, not a second resolver.
  output="$(TERNUXX_JSON=1 nt_cmd_install preview --profile custom --components "$components")" || return $?
  printf '%s\n' "$output" | python3 -m json.tool || return 1
  status="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["install"])' <<<"$output")" || return 1
  [ "$status" != already_installed ] || return 0
  plan_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_id"])' <<<"$output")" || return 1
  _nt_confirm 'Install the displayed Native package selection?' || return $?
  TERNUXX_WIZARD_ACTIVE=1 nt_cmd_install apply --profile custom --components "$components" --yes --plan-id "$plan_id"
}

_nt_wizard_entrypoint() {
  local root="$1" output plan_id changed
  output="$(python3 "$root/scripts/cli_entrypoint.py" preview)" || return $?
  changed="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["changed"])' <<<"$output")" || return 1
  [ "$changed" = True ] || return 0
  printf '%s\n' "$output"
  plan_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_id"])' <<<"$output")" || return 1
  _nt_confirm 'Install / update the tx command shim for this checkout?' || return $?
  python3 "$root/scripts/cli_entrypoint.py" apply --yes --plan-id "$plan_id"
}

_nt_install_wizard() {
  [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] || { nt_fail 'Run tx install in an attached terminal; automation uses tx install preview.'; return 2; }
  nt_require_termux || return 1
  local profile components=terminal,developer,proot desktops apps distros distro root answer
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
    apps="$(_nt_pick 'Optional Native apps (select none to skip extras)' multi none \
      'none|No optional apps' 'browser|Firefox browser' 'music|Audacious music player' \
      'images|Ristretto image viewer' 'pdf|Evince PDF viewer' 'editor|Mousepad text editor' \
      'archive|Xarchiver archive manager' 'video|VLC media player')" || return $?
    for answer in ${apps//,/ }; do [ "$answer" = none ] || components+=,"$answer"; done
  fi
  if [ "$profile" = proot ]; then
    components+=,nested
    distros="$(_nt_pick 'Managed PRoot distributions (one or more)' multi debian \
      'debian|Debian Trixie' 'ubuntu|Ubuntu Noble')" || return $?
  fi
  _nt_wizard_prepare || return $?
  _nt_wizard_native "$components" || return $?
  _nt_wizard_entrypoint "$root" || return $?
  if [ "$profile" != minimal ]; then
    nt_info 'Building the Native GTK management center from the selected checkout.'
    bash "$root/scripts/install-management-center.sh" || return $?
    # Selection alone never claims acceleration. Probe through the same manager.
    if [ -c /dev/kgsl-3d0 ]; then
      nt_info 'Adreno/KGSL detected. Future-start Zink selection still requires a successful Vulkan probe.'
      if _nt_confirm 'Probe and select the Native termux-zink graphics backend?'; then
        "$root/tx" mng graphics select native termux-zink || return $?
      fi
    fi
  fi
  for distro in ${distros//,/ }; do
    _nt_install_managed_guest "$distro" || return $?
  done
  nt_ok 'Selected setup stages completed. No desktop was started.'
  nt_info 'Commands: tx tui | tx web | tx gui | tx start --desktop ID'
  nt_info 'Guest: tx pgui [DE] (Debian XFCE default); tx pgui start --alias ubuntu --desktop xfce'
  nt_info 'Install/open the matching Termux:X11 Android app separately. GPU rendering and desktop visibility need live verification.'
}

_nt_choose_guest_desktops() {
  local distro="$1" root="$2" choices choice
  local -a items=()
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
  apps=",$apps,"; apps="${apps//,none,/,}"; apps="${apps#,}"; apps="${apps%,}"
  local -a args=(desktop-preview --repo-root "$root" --alias "$distro" --desktops "$desktops" --json)
  [ -z "$apps" ] || args+=(--apps "$apps")
  output="$(python3 "$root/lib/proot_setup.py" "${args[@]}")" || return $?
  printf '%s\n' "$output" | command python3 -m json.tool || return 1
  status="$(command python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$output")" || return 1
  [ "$status" != already_installed ] || { nt_ok 'Selected guest desktops/apps are already installed.'; return 0; }
  plan_id="$(command python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_id"])' <<<"$output")" || return 1
  _nt_confirm "Add the displayed desktops/apps to existing $distro (no rootfs replacement)?" || return $?
  python3 "$root/lib/proot_setup.py" desktop-install --repo-root "$root" --yes --plan-id "$plan_id" --json
}

_nt_install_native_desktop() {
  local desktop="${1/xfce4/xfce}" root="${_TN_LIB_DIR%/lib}" components=gui,developer,audio,sound-controls,graphics
  shift
  [ $# -eq 0 ] || { nt_fail 'Use tx install NATIVE_DE; guest desktops use tx install proot DISTRO DE.'; return 2; }
  case "$desktop" in
    xfce) components+=,desktop ;;
    mate|plasma) components+=,"$desktop" ;;
    *) nt_fail 'Supported Native desktops: xfce, mate, plasma.'; return 2 ;;
  esac
  nt_require_termux || return 1
  _nt_wizard_native "$components" || return $?
  bash "$root/scripts/install-management-center.sh"
}

_nt_install_proot_short() {
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
if sys.argv[2] not in available:
    print("Supported guest desktops: " + ", ".join(available), file=sys.stderr)
    raise SystemExit(2)
PYSHORTDESKTOP
  fi
  _nt_wizard_native proot,guest-display || return $?
  local -a args=()
  [ -z "$desktop" ] || args+=(--desktops "${desktop/xfce4/xfce}")
  _nt_install_managed_guest "$distro" "${args[@]}"
}
