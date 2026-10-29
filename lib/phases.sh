# =============================================================================
#  Ternuxx package setup
#
#  Installation begins with a repository and dependency preview.
#  Apply requires --yes or an explicit attached-terminal confirmation.
# =============================================================================
# shellcheck source=lib/core.sh
. "$(dirname "${BASH_SOURCE[0]}")/core.sh"

# Native host packages include Debian PRoot support, graphical diagnostics, and
# X11 test utilities. Heavy applications and Mesa providers remain optional.
declare -gA _NT_GUEST_READY _NT_GUEST_USER _NT_GUEST_SUDO _NT_GUEST_DESKTOPS _NT_GUEST_APPS _NT_GUEST_PASSWORD _NT_GUEST_ACCOUNT_NEEDED
. "$(dirname "${BASH_SOURCE[0]}")/install_catalog.sh"
_NT_CORE_PACKAGES=(python)
_NT_DESKTOP_PACKAGES=(
  termux-x11-nightly dbus xfce4-session xfce4-panel xfce4-settings xfwm4
  xfdesktop xfconf thunar xfce4-terminal xdotool xorg-xprop
)
_NT_MATE_PACKAGES=(mate)
_NT_PLASMA_PACKAGES=(plasma-desktop)
_NT_AUDIO_PACKAGES=(pulseaudio)
_NT_PROOT_PACKAGES=(proot-distro)
_NT_GRAPHICS_PACKAGES=(glmark2 mesa-demos mesa-vulkan-icd-freedreno vulkan-tools xorg-server-xvfb xdotool)
_NT_DEVELOPER_PACKAGES=(clang cmake gdb make pkg-config)
_NT_TERMINAL_PACKAGES=(util-linux git openssh curl wget rsync nano vim tmux htop tree unzip zip ripgrep less)
_NT_GUI_PACKAGES=(termux-x11-nightly dbus gtk4 libvte)
_NT_NESTED_PACKAGES=(xorg-server-xephyr)
_NT_BASE_PACKAGES=(
  termux-x11-nightly
  dbus
  pulseaudio
  proot-distro
  python
  xfce4-session
  xfce4-panel
  xfce4-settings
  xfwm4
  xfdesktop
  xfconf
  thunar
  xfce4-terminal
  glmark2
  mesa-demos
  mesa-vulkan-icd-freedreno
  vulkan-tools
  xorg-server-xvfb
  xdotool
  xorg-xprop
)
_NT_FULL_NATIVE_PACKAGES=("${_NT_BASE_PACKAGES[@]}")
_NT_ACTIVE_PROFILE=full-native
_NT_ACTIVE_COMPONENTS=""
_NT_ACTIVE_SKIPPED_COMPONENTS=""
_NT_PLAN_MODE=install
_NT_PLAN_RESOURCE_ESTIMATES='{"schema_version":1,"complete":false,"packages":[]}'
_NT_PLAN_ALLOW_VLC_REPLACEMENT=0
_NT_PLAN_REMOVALS=()

_nt_capture_install_resource_estimates() {
  if [ ${#_NT_PLAN_TRANSACTION[@]} -eq 0 ]; then
    _NT_PLAN_RESOURCE_ESTIMATES='{"schema_version":1,"complete":true,"download_bytes":0,"installed_kib":0,"packages":[]}'
    return 0
  fi
  local estimate_helper="${_TN_LIB_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)}/package_estimates.py"
  _NT_PLAN_RESOURCE_ESTIMATES="$(python3 "$estimate_helper" -- "${_NT_PLAN_TRANSACTION[@]}")" || {
    _NT_PLAN_RESOURCE_ESTIMATES='{"schema_version":1,"complete":false,"packages":[]}';
  }
}

_nt_print_install_resource_estimates() {
  python3 - "$_NT_PLAN_RESOURCE_ESTIMATES" "${TERNUXX_VERBOSE:-0}" <<'PYESTIMATEPRINT'
import json, sys
try:
    data = json.loads(sys.argv[1])
except (ValueError, TypeError):
    print("[INFO]  Resource estimates unavailable.", file=sys.stderr)
    raise SystemExit(0)
def mib(value): return f"{value / 1048576:.1f} MiB"
def gib(value): return f"{value / 1073741824:.1f} GiB"
if data.get("complete"):
    print(f"[INFO]  Estimated package download: {mib(data['download_bytes'])}; installed payload: {mib(data['installed_kib'] * 1024)} (APT metadata; approximate).", file=sys.stderr)
else:
    print("[WARN]  Complete package size estimates are unavailable from the current APT metadata.", file=sys.stderr)
free = data.get("filesystem_free_bytes")
if isinstance(free, int):
    print(f"[INFO]  Current free space on the Termux prefix filesystem: {gib(free)}.", file=sys.stderr)
memory = data.get("memory", {})
total, available = memory.get("total_bytes"), memory.get("available_bytes")
if isinstance(total, int) and isinstance(available, int):
    print(f"[INFO]  Host memory snapshot: {gib(available)} available of {gib(total)} total; this is not a workload guarantee.", file=sys.stderr)
if sys.argv[2] == "1":
    for package in data.get("packages", []):
        size = package.get("download_bytes")
        installed = package.get("installed_kib")
        if isinstance(size, int) and isinstance(installed, int):
            print(f"[INFO]  {package['package']}={package['version']}: {mib(size)} download, {mib(installed * 1024)} installed.", file=sys.stderr)
        else:
            print(f"[INFO]  {package.get('package', '?')}: size estimate unavailable.", file=sys.stderr)
PYESTIMATEPRINT
}

_nt_install_capacity_preflight() {
  python3 - "$_NT_PLAN_RESOURCE_ESTIMATES" <<'PYESTIMATECAPACITY'
import json, sys
try:
    data = json.loads(sys.argv[1])
except (ValueError, TypeError):
    raise SystemExit(0)
needed = data.get("installed_kib")
free = data.get("filesystem_free_bytes")
if not isinstance(needed, int) or not isinstance(free, int):
    raise SystemExit(0)
needed *= 1024
if free < needed:
    print(f"Estimated installed payload ({needed} bytes) exceeds current free Termux-prefix storage ({free} bytes); refusing to start APT.", file=sys.stderr)
    raise SystemExit(1)
if data.get("download_bytes") is not None and free < needed + data["download_bytes"]:
    print("Warning: free space is below the estimated download-plus-installed peak; APT may run out of storage during unpack.", file=sys.stderr)
PYESTIMATECAPACITY
}

_nt_select_install_profile() {
  local profile="${1:-}" components="${2:-}" group package
  local -a selected=() groups=()
  local -A seen=()
  case "$profile" in
    minimal-native) selected=("${_NT_CORE_PACKAGES[@]}") ;;
    full-native)
      [ -z "$components" ] || { nt_fail "--components is valid only with --profile custom."; return 2; }
      selected=("${_NT_FULL_NATIVE_PACKAGES[@]}") ;;
    graphical)
      [ -z "$components" ] || { nt_fail "--components is valid only with --profile custom."; return 2; }
      selected=("${_NT_CORE_PACKAGES[@]}" "${_NT_DESKTOP_PACKAGES[@]}" "${_NT_AUDIO_PACKAGES[@]}" "${_NT_GRAPHICS_PACKAGES[@]}") ;;
    developer)
      [ -z "$components" ] || { nt_fail "--components is valid only with --profile custom."; return 2; }
      selected=("${_NT_CORE_PACKAGES[@]}" "${_NT_DEVELOPER_PACKAGES[@]}") ;;
    native-proot-provider)
      [ -z "$components" ] || { nt_fail "--components is valid only with --profile custom."; return 2; }
      selected=("${_NT_CORE_PACKAGES[@]}" "${_NT_PROOT_PACKAGES[@]}") ;;
    native-debian)
      [ -z "$components" ] || { nt_fail "--components is valid only with --profile custom."; return 2; }
      selected=("${_NT_FULL_NATIVE_PACKAGES[@]}") ;;
    custom)
      selected=("${_NT_CORE_PACKAGES[@]}")
      [ -n "$components" ] || { nt_fail "Custom profile requires --components GROUPS."; return 2; }
      IFS=',' read -r -a groups <<< "$components"
      for group in "${groups[@]}"; do
        case "$group" in
          system-upgrade) : ;; # resolved together with selected packages below
          services) selected+=(termux-services openssh) ;;
          terminal) selected+=("${_NT_TERMINAL_PACKAGES[@]}") ;;
          sound-controls) selected+=(pavucontrol) ;;
          gui) selected+=("${_NT_GUI_PACKAGES[@]}") ;;
          guest-display) selected+=(termux-x11-nightly dbus pulseaudio xorg-server-xephyr) ;;
          nested) selected+=("${_NT_NESTED_PACKAGES[@]}") ;;
          desktop) selected+=("${_NT_DESKTOP_PACKAGES[@]}") ;;
          audio) selected+=("${_NT_AUDIO_PACKAGES[@]}") ;;
          proot) selected+=("${_NT_PROOT_PACKAGES[@]}") ;;
          graphics) selected+=("${_NT_GRAPHICS_PACKAGES[@]}") ;;
          ai-cpu) selected+=(llama-cpp) ;;
          ai-vulkan) selected+=(llama-cpp llama-cpp-backend-vulkan) ;;
          developer) selected+=("${_NT_DEVELOPER_PACKAGES[@]}") ;;
          mate) selected+=("${_NT_MATE_PACKAGES[@]}") ;;
          plasma) selected+=("${_NT_PLASMA_PACKAGES[@]}") ;;
          *)
            if _nt_native_app_lookup "$group"; then
              selected+=("${_NT_OPTIONAL_PACKAGES[@]}")
            else
              nt_fail "Unknown component group '$group'. Use a documented built-in group or curated Native app ID."
              return 2
            fi ;;
        esac
      done ;;
    *) nt_fail "Unknown install profile '$profile'. Choose minimal-native, full-native, graphical, developer, native-proot-provider, native-debian, or custom."; return 2 ;;
  esac
  _NT_BASE_PACKAGES=()
  for package in "${selected[@]}"; do
    if [ -z "${seen[$package]+x}" ]; then
      _NT_BASE_PACKAGES+=("$package")
      seen[$package]=1
    fi
  done
  _NT_ACTIVE_PROFILE="$profile"
  _NT_ACTIVE_COMPONENTS="$components"
  local -a omitted=()
  for group in desktop audio proot graphics developer mate plasma terminal gui services sound-controls nested guest-display browser music images pdf editor archive video ai-cpu ai-vulkan; do
    case "$profile" in
      full-native) [[ "$group" == developer ]] && omitted+=("$group") ;;
      graphical) [[ "$group" == proot || "$group" == developer ]] && omitted+=("$group") ;;
      developer) [[ "$group" != developer ]] && omitted+=("$group") ;;
      native-proot-provider) [[ "$group" != proot ]] && omitted+=("$group") ;;
      native-debian) [[ "$group" == developer ]] && omitted+=("$group") ;;
      minimal-native) omitted+=("$group") ;;
      custom)
        case ",$components," in *",$group,"*) ;; *) omitted+=("$group") ;; esac ;;
    esac
  done
  [ "$profile" = native-debian ] || omitted+=(guest)
  _NT_ACTIVE_SKIPPED_COMPONENTS="$(IFS=,; printf '%s' "${omitted[*]}")"
}

_nt_combined_guest_preview() {
  local repo_root output
  repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
  output="$(python3 "$repo_root/lib/proot_setup.py" fresh-preview --repo-root "$repo_root" --user "$_NT_INSTALL_GUEST_USER" --json)" || {
    nt_fail "Fresh Debian guest preview failed; no package or guest changes were applied."
    return 1
  }
  _NT_COMBINED_GUEST_JSON="$output"
  _NT_COMBINED_GUEST_PLAN_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["plan_id"])' "$output")" || return 1
  nt_info "Fresh Debian target: alias=debian, user=$_NT_INSTALL_GUEST_USER."
  nt_info "Pinned guest preview ID: $_NT_COMBINED_GUEST_PLAN_ID"
}

_nt_apply_combined_guest() {
  local repo_root output
  repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
  output="$(python3 "$repo_root/lib/proot_setup.py" fresh-install --repo-root "$repo_root" --user "$_NT_INSTALL_GUEST_USER" --plan-id "$_NT_INSTALL_GUEST_PLAN_ID" --yes --json)" || {
    nt_fail "Native package phase completed, but fresh Debian setup failed. Inspect the guest setup journal before using fresh-resume-preview."
    [ -z "$output" ] || printf '%s\n' "$output" >&2
    return 1
  }
  _NT_COMBINED_GUEST_RESULT="$output"
  nt_ok "The fresh Debian guest setup completed and returned its verification record."
}

_nt_package_installed() {
  local status
  status="$(dpkg-query -W -f='${Status}' "$1" 2>/dev/null || true)"
  [ "$status" = "install ok installed" ]
}

_nt_package_index_fresh() {
  local lists="${PREFIX:-/data/data/com.termux/files/usr}/var/lib/apt/lists"
  local now marker path stamp epoch newest matches
  now="$(date -u +%s 2>/dev/null)" || return 1
  [[ "$now" =~ ^[0-9]+$ ]] || return 1
  for marker in termux-main termux-x11; do
    newest=""
    matches=0
    for path in "$lists"/*"$marker"*_InRelease; do
      [ -f "$path" ] || continue
      matches=1
      stamp="$(awk 'index($0, "Date: ")==1 {sub(/^Date: /, ""); print; exit}' "$path" 2>/dev/null)"
      [ -n "$stamp" ] || continue
      epoch="$(date -u -d "$stamp" +%s 2>/dev/null || true)"
      [[ "$epoch" =~ ^[0-9]+$ ]] || continue
      if [ -z "$newest" ] || [ "$epoch" -gt "$newest" ]; then
        newest="$epoch"
      fi
    done
    [ "$matches" = "1" ] && [ -n "$newest" ] || {
      printf 'Missing or unreadable signed package index: %s\n' "$marker" >&2
      return 1
    }
    if [ "$newest" -gt "$((now + 900))" ] || [ "$((now - newest))" -gt 1209600 ]; then
      printf 'Package index is stale or future-dated: %s (epoch %s)\n' "$marker" "$newest" >&2
      return 1
    fi
  done
}

_nt_package_candidate_from_official_repo() {
  local package="$1" expected_repo="$2" policy candidate
  policy="$(apt-cache policy "$package" 2>/dev/null)" || return 1
  candidate="$(printf '%s\n' "$policy" | sed -n 's/^[[:space:]]*Candidate: //p' | head -1)"
  [ -n "$candidate" ] && [ "$candidate" != "(none)" ] || return 1
  printf '%s\n' "$policy" | awk -v version="$candidate" -v repo="$expected_repo" '
    $1 == "***" && $2 == version && $3 ~ /^[0-9]+$/ { in_candidate=1; next }
    $1 == version && $2 ~ /^[0-9]+$/ { in_candidate=1; next }
    in_candidate && $1 ~ /^[0-9]+$/ && $2 ~ /^https?:/ {
      if (index($0, repo)) found=1
      in_candidate=0
      next
    }
    END { exit !found }
  ' || return 1
  printf '%s\n' "$candidate"
}

_nt_package_transaction_origins_allowed() {
  local simulation="$1" allow_tur="${2:-0}"
  printf '%s\n' "$simulation" | awk -v allow_tur="$allow_tur" '
    /^(Inst|Conf) / && $0 !~ /termux-main|termux-x11/ {
      if (allow_tur == 1 && $0 ~ /Termux-user-repository tur-packages/) next
      bad=1
    }
    END { exit bad ? 1 : 0 }
  '
}

_nt_make_install_plan() {
  _NT_PLAN_MODE=install
  _NT_PLAN_ALLOW_VLC_REPLACEMENT=0
  _NT_PLAN_ALLOW_TUR=0
  _NT_PLAN_REMOVALS=()
  local package expected_repo candidate simulation upgrade_simulation
  local -A upgrade_names=()
  [[ ",${_NT_ACTIVE_COMPONENTS:-}," = *,blender,* ]] && _NT_PLAN_ALLOW_TUR=1
  local -a simulation_options=(--no-upgrade) plan_roots=("${_NT_BASE_PACKAGES[@]}")
  if [[ ",${_NT_ACTIVE_COMPONENTS:-}," = *,system-upgrade,* ]]; then
    _NT_PLAN_MODE=update; simulation_options=()
    upgrade_simulation="$(apt-get -s --no-remove upgrade 2>&1)" || return 1
    if ! printf '%s\n' "$upgrade_simulation" | awk '/^Remv / {bad=1} END {exit bad}' || ! _nt_package_transaction_origins_allowed "$upgrade_simulation" "$_NT_PLAN_ALLOW_TUR"; then
      nt_fail 'Upgrade includes an unapproved repository or removal.'; return 1
    fi
    while read -r package; do
      [ -n "$package" ] || continue
      upgrade_names[$package]=1; plan_roots+=("$package")
    done < <(printf '%s\n' "$upgrade_simulation" | awk '$1=="Inst" {print $2}')
  fi
  local -A planned=()
  _NT_PLAN_PACKAGES=()
  _NT_PLAN_VERSIONS=()
  _NT_PLAN_TRANSACTION=()

  for package in "${plan_roots[@]}"; do
    [ -z "${planned[$package]:-}" ] || continue
    planned[$package]=1
    if [ -z "${upgrade_names[$package]:-}" ] && _nt_package_installed "$package"; then
      continue
    fi
    case "$package" in
      dbus|pulseaudio|python|proot-distro|vulkan-tools|mesa-vulkan-icd-freedreno|clang|cmake|gdb|make|pkg-config|git|openssh|curl|wget|rsync|nano|vim|tmux|htop|tree|unzip|zip|ripgrep|less|vlc|termux-services|util-linux) expected_repo="termux-main" ;;
      *) expected_repo="$(_nt_native_app_repository "$package")" || expected_repo="termux-x11" ;;
    esac
    if [ -n "${upgrade_names[$package]:-}" ]; then
      if _nt_package_candidate_from_official_repo "$package" termux-main >/dev/null; then expected_repo=termux-main; else expected_repo=termux-x11; fi
    fi
    candidate="$(_nt_package_candidate_from_official_repo "$package" "$expected_repo")" || {
      nt_fail "No $expected_repo candidate found for $package. Enable/check the official repository and refresh package indexes yourself."
      return 1
    }
    _NT_PLAN_PACKAGES+=("$package")
    _NT_PLAN_VERSIONS+=("$package=$candidate")
  done

  if [ ${#_NT_PLAN_PACKAGES[@]} -eq 0 ]; then
    _NT_PLAN_SIMULATION=""
    _nt_capture_install_resource_estimates
    return 0
  fi

  local -a remove_policy=(--no-remove)
  if [[ " ${_NT_PLAN_PACKAGES[*]} " == *" vlc-qt "* ]] && _nt_package_installed vlc; then
    # Termux's `vlc` is CLI-only. Its GUI build `vlc-qt` explicitly replaces
    # it; allow that one named transition, while rejecting every other removal.
    _NT_PLAN_ALLOW_VLC_REPLACEMENT=1
    remove_policy=()
  fi
  simulation="$(apt-get -s --no-install-recommends "${remove_policy[@]}" "${simulation_options[@]}" install "${_NT_PLAN_PACKAGES[@]}" 2>&1)" || {
    nt_fail "APT could not resolve the preview. No packages were changed."
    printf '%s\n' "$simulation" >&2
    return 1
  }
  _NT_PLAN_REMOVALS=()
  while IFS= read -r package; do
    [ -n "$package" ] || continue
    if [ "$_NT_PLAN_ALLOW_VLC_REPLACEMENT" = 1 ] && [ "$package" = vlc ] && _nt_package_installed vlc; then
      _NT_PLAN_REMOVALS+=("$package")
    else
      nt_fail "The proposed transaction removes an unapproved package ($package); refusing it. No packages were changed."
      return 1
    fi
  done < <(printf '%s\n' "$simulation" | awk '$1 == "Remv" {print $2}')
  if [ "$_NT_PLAN_ALLOW_VLC_REPLACEMENT" = 1 ] && [ " ${_NT_PLAN_REMOVALS[*]} " != " vlc " ]; then
    nt_fail "The VLC GUI replacement did not resolve to the exact vlc-to-vlc-qt change; refusing it."
    return 1
  fi
  if ! _nt_package_transaction_origins_allowed "$simulation" "$_NT_PLAN_ALLOW_TUR"; then
    nt_fail "The dependency plan includes a package outside the repositories permitted for this explicit selection; refusing it."
    return 1
  fi
  if ! printf '%s\n' "$simulation" | grep -q '^Inst '; then
    nt_fail "APT did not return a complete install transaction; refusing to preview or apply it. No packages were changed."
    return 1
  fi
  local index expected_version
  for index in "${!_NT_PLAN_PACKAGES[@]}"; do
    package="${_NT_PLAN_PACKAGES[$index]}"
    expected_version="${_NT_PLAN_VERSIONS[$index]#*=}"
    if ! printf '%s\n' "$simulation" | awk -v package="$package" -v version="$expected_version" '$1 == "Inst" && $2 == package {for(i=3;i<=NF;i++) if(substr($i,1,1)=="(") {v=substr($i,2);if(v=="")v=$(i+1);sub(/[)]$/,"",v);if(v==version)found=1;break}} END { exit !found }'; then
      nt_fail "APT transaction did not include the reviewed candidate for $package; refusing it. No packages were changed."
      return 1
    fi
  done
  _NT_PLAN_TRANSACTION=()
  while IFS=' ' read -r package expected_version; do
    [ -n "$package" ] && _NT_PLAN_TRANSACTION+=("$package=$expected_version")
  done < <(printf '%s\n' "$simulation" | awk '$1 == "Inst" {for(i=3;i<=NF;i++) if(substr($i,1,1)=="(") {v=substr($i,2);if(v=="")v=$(i+1);sub(/[)]$/,"",v);print $2,v;break}}')
  _NT_PLAN_SIMULATION="$simulation"
  _nt_capture_install_resource_estimates
}

_nt_make_update_plan() {
  _NT_PLAN_MODE=update
  _NT_PLAN_ALLOW_VLC_REPLACEMENT=0
  _NT_PLAN_REMOVALS=()
  local package expected_repo candidate installed simulation index expected_version
  _NT_PLAN_PACKAGES=()
  _NT_PLAN_VERSIONS=()
  _NT_PLAN_TRANSACTION=()
  _NT_PLAN_SIMULATION=""

  for package in "${_NT_BASE_PACKAGES[@]}"; do
    _nt_package_installed "$package" || continue
    case "$package" in
      dbus|pulseaudio|python|proot-distro|vulkan-tools|mesa-vulkan-icd-freedreno) expected_repo="termux-main" ;;
      *) expected_repo="$(_nt_native_app_repository "$package")" || expected_repo="termux-x11" ;;
    esac
    installed="$(dpkg-query -W -f='${Version}' "$package" 2>/dev/null)" || {
      nt_fail "Could not read the installed version for $package; refusing an update plan."
      return 1
    }
    candidate="$(_nt_package_candidate_from_official_repo "$package" "$expected_repo")" || {
      nt_fail "No $expected_repo candidate found for $package. Check the official repository and refresh package indexes yourself."
      return 1
    }
    if dpkg --compare-versions "$candidate" eq "$installed" 2>/dev/null; then
      continue
    elif dpkg --compare-versions "$candidate" gt "$installed" 2>/dev/null; then
      _NT_PLAN_PACKAGES+=("$package")
      _NT_PLAN_VERSIONS+=("$package=$candidate")
    elif dpkg --compare-versions "$candidate" lt "$installed" 2>/dev/null; then
      nt_warn "$package is installed at $installed, newer than the selected $expected_repo candidate $candidate; it will not be downgraded."
    else
      nt_fail "Could not compare installed and candidate versions for $package; refusing an update plan."
      return 1
    fi
  done

  if [ ${#_NT_PLAN_PACKAGES[@]} -eq 0 ]; then
    return 0
  fi

  simulation="$(apt-get -s --no-install-recommends --no-remove install "${_NT_PLAN_VERSIONS[@]}" 2>&1)" || {
    nt_fail "APT could not resolve the exact update preview. No packages were changed."
    printf '%s\n' "$simulation" >&2
    return 1
  }
  if printf '%s\n' "$simulation" | grep -Eq '^(Remv|The following packages will be REMOVED:)'; then
    nt_fail "The proposed update removes packages; refusing it. No packages were changed."
    return 1
  fi
  if printf '%s\n' "$simulation" | grep -Eq '^Inst /'; then
    nt_fail "APT returned an invalid package identity in the update transaction."
    return 1
  fi
  if ! printf '%s\n' "$simulation" | awk '/^Inst / && $0 !~ /termux-main|termux-x11/ { bad=1 } END { exit bad ? 1 : 0 }'; then
    nt_fail "The update dependency plan includes a package outside the official Termux repositories; refusing it."
    return 1
  fi
  if ! printf '%s\n' "$simulation" | grep -q '^Inst '; then
    nt_fail "APT did not return an update transaction; refusing to preview or apply it."
    return 1
  fi
  for index in "${!_NT_PLAN_PACKAGES[@]}"; do
    package="${_NT_PLAN_PACKAGES[$index]}"
    expected_version="${_NT_PLAN_VERSIONS[$index]#*=}"
    if ! printf '%s\n' "$simulation" | awk -v package="$package" -v version="$expected_version" '$1 == "Inst" && $2 == package { for (i=3; i<=NF; i++) if (substr($i,1,1)=="(") { actual=substr($i,2); if (actual=="") actual=$(i+1); sub(/[)]$/, "", actual); if (actual==version) found=1; break } } END { exit !found }'; then
      nt_fail "APT transaction did not include the exact reviewed update for $package; refusing it."
      return 1
    fi
  done

  while IFS=' ' read -r package expected_version; do
    [ -n "$package" ] && _NT_PLAN_TRANSACTION+=("$package=$expected_version")
  done < <(printf '%s\n' "$simulation" | awk '$1 == "Inst" { for (i=3; i<=NF; i++) if (substr($i,1,1)=="(") { version=substr($i,2); if (version=="") version=$(i+1); sub(/[)]$/, "", version); print $2, version; break } }')

  # Reject a solver result that would downgrade any already installed
  # dependency, even when the requested direct package itself is an upgrade.
  local resolved current
  for resolved in "${_NT_PLAN_TRANSACTION[@]}"; do
    package="${resolved%%=*}"
    expected_version="${resolved#*=}"
    current="$(dpkg-query -W -f='${Version}' "$package" 2>/dev/null)" || continue
    if dpkg --compare-versions "$expected_version" lt "$current" 2>/dev/null; then
      nt_fail "The update transaction would downgrade $package from $current to $expected_version; refusing it."
      return 1
    fi
  done
  _NT_PLAN_SIMULATION="$simulation"
}

_nt_compute_plan_id() {
  python3 - "$_NT_PLAN_MODE" "$_NT_PLAN_SIMULATION" "${_NT_PLAN_VERSIONS[@]}" -- "${_NT_PLAN_TRANSACTION[@]}" <<'PYPLANID'
import hashlib, json, sys
mode, simulation = sys.argv[1:3]
separator = sys.argv.index("--", 3)
record = {"requested_candidates": sys.argv[3:separator], "resolved_transaction": sys.argv[separator + 1:], "apt_simulation": simulation}
if mode == "update":
    record["operation"] = mode
print(hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
PYPLANID
}

_nt_reviewed_preview_matches() {
  local plan_id="$1"
  [[ "$plan_id" =~ ^[0-9a-f]{64}$ ]] || return 1
  python3 - "$TERNUXX_STATE_DIR/install-transactions" "$plan_id" "$HOME" "$_NT_PLAN_MODE" "$_NT_PLAN_SIMULATION" "${_NT_PLAN_VERSIONS[@]}" -- "${_NT_PLAN_TRANSACTION[@]}" <<'PYCHECKPREVIEW'
import hashlib, json, os, pathlib, stat, sys
root = pathlib.Path(sys.argv[1])
plan_id, home, mode, simulation = sys.argv[2:6]
separator = sys.argv.index("--", 6)
requested = sys.argv[6:separator]
transaction = sys.argv[separator + 1:]
try:
    resolved_root = root.resolve(strict=True)
    resolved_home = pathlib.Path(home).resolve(strict=True)
    if resolved_root == resolved_home or resolved_home not in resolved_root.parents:
        raise ValueError("preview directory is outside HOME")
    root_metadata = root.lstat()
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("preview directory is not a regular directory")
    if stat.S_IMODE(root_metadata.st_mode) != 0o700:
        raise ValueError("preview directory permissions are not private")
    expected = {"requested_candidates": requested, "resolved_transaction": transaction, "apt_simulation": simulation}
    if mode == "update":
        expected["operation"] = mode
    digest = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != plan_id:
        raise ValueError("current transaction does not match the supplied preview ID")
    for path in resolved_root.glob("*.json"):
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if record.get("schema_version") != 1 or record.get("outcome") != "preview":
            continue
        if record.get("operation", "install") != mode:
            continue
        fields = {key: record.get(key) for key in expected}
        actual = hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if actual == plan_id and record.get("plan_id") == plan_id:
            if stat.S_IMODE(metadata.st_mode) != 0o600:
                raise ValueError("preview record permissions are not private")
            print(path)
            raise SystemExit(0)
except (OSError, ValueError) as exc:
    print(f"{exc}", file=sys.stderr)
sys.exit(1)
PYCHECKPREVIEW
}

_nt_apply_install_transaction() {
  local -a options=(--assume-yes --no-install-recommends)
  [ "${_NT_PLAN_ALLOW_VLC_REPLACEMENT:-0}" = 1 ] || options+=(--no-remove)
  [ "${_NT_PLAN_MODE:-install}" = update ] || options+=(--no-upgrade)
  if [ "${TERNUXX_WIZARD_ACTIVE:-0}" = 1 ]; then
    options+=(-o Dpkg::Use-Pty=0 -o Dpkg::Progress-Fancy=0)
    _nt_window_run _nt_network_retry 'Exact package download' env -u LD_LIBRARY_PATH apt-get "${options[@]}" --download-only install "${_NT_PLAN_TRANSACTION[@]}" || return $?
    # APT validates signed index/package hashes; mutation never fetches a different payload.
    options+=(--no-download)
  fi
  if [ "${TERNUXX_WIZARD_ACTIVE:-0}" = 1 ]; then
    _nt_window_run env -u LD_LIBRARY_PATH apt-get "${options[@]}" install "${_NT_PLAN_TRANSACTION[@]}"
  else
    env -u LD_LIBRARY_PATH apt-get "${options[@]}" install "${_NT_PLAN_TRANSACTION[@]}"
  fi
}

_nt_install_state_dir_safe() {
  python3 - "$TERNUXX_STATE_DIR" "$HOME" <<'PYSTATEPATH'
import pathlib, stat, sys
state = pathlib.Path(sys.argv[1]).expanduser()
home = pathlib.Path(sys.argv[2]).expanduser().resolve()
try:
    absolute = pathlib.Path(state.absolute())
    relative = absolute.relative_to(home)
    current = home
    for part in relative.parts:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                raise ValueError("state path contains a symbolic link")
        except FileNotFoundError:
            pass
    resolved = state.resolve(strict=False)
    if resolved == home or home not in resolved.parents:
        raise ValueError("state path must be inside HOME")
except (OSError, ValueError) as exc:
    print(f"unsafe installer state path: {exc}", file=sys.stderr)
    sys.exit(1)
PYSTATEPATH
}

_nt_write_install_record() {
  local outcome="$1" root stamp target
  _nt_install_state_dir_safe || return 1
  root="${TERNUXX_STATE_DIR}/install-transactions"
  mkdir -p "$root" || return 1
  chmod 700 "$root" || return 1
  stamp="$(date -u +%Y%m%dT%H%M%SZ)" || return 1
  target="$root/${stamp}-$$-${RANDOM}-${outcome}.json"
  local plan_id
  plan_id="$( _nt_compute_plan_id )" || return 1
  python3 - "$target" "$outcome" "$_NT_PLAN_MODE" "$plan_id" "$_NT_PLAN_SIMULATION" "${_NT_PLAN_VERSIONS[@]}" -- "${_NT_PLAN_TRANSACTION[@]}" <<'PYRECORD'
import json, os, pathlib, sys, tempfile
path = pathlib.Path(sys.argv[1])
outcome = sys.argv[2]
mode = sys.argv[3]
plan_id = sys.argv[4]
simulation = sys.argv[5]
separator = sys.argv.index("--", 6)
requested = sys.argv[6:separator]
transaction = sys.argv[separator + 1:]
record = {
    "schema_version": 1,
    "recorded_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    "outcome": outcome,
    "operation": mode,
    "plan_id": plan_id,
    "requested_candidates": requested,
    "resolved_transaction": transaction,
    "apt_simulation": simulation,
}
path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=".install-transaction-", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
finally:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
PYRECORD
}

_nt_offer_managed_guest() {
  [ "${TERNUXX_WIZARD_ACTIVE:-0}" != 1 ] || return 0
  [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] || return 0
  . "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_picker.sh"
  local answer distro
  answer="$(_nt_pick 'Optional managed guests' multi none 'none|Skip guest setup' 'debian|Debian Trixie' 'ubuntu|Ubuntu Noble')" || return $?
  for distro in ${answer//,/ }; do
    [ "$distro" = none ] || _nt_install_managed_guest "$distro" || return $?
  done
}

nt_cmd_install() {
  case "${1:-}" in
    gpu)
      shift
      [ $# -eq 0 ] || { nt_fail 'Use tx install gpu with no arguments.'; return 2; }
      . "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_wizard.sh"
      _nt_window_session _nt_install_gpu; return $? ;;
    xfce|xfce4|mate|plasma)
      . "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_wizard.sh"
      _nt_window_session _nt_install_native_desktop "$@"; return $? ;;
    proot)
      shift
      . "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_wizard.sh"
      _nt_window_session _nt_install_proot_short "$@"; return $? ;;
    debian|ubuntu)
      nt_fail "Use 'tx install proot $1 [DE]' for guided guest setup, or 'tx proot setup fresh-preview --user NAME' for explicit review."; return 2 ;;
  esac
  if [ $# -eq 0 ] || { [ $# -eq 1 ] && [[ "$1" = interactive || "$1" = --interactive ]]; }; then
    . "${_TN_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}/install_wizard.sh"
    _nt_window_session _nt_install_wizard
    return $?
  fi
  # `bin/tx` consumes --verbose as a global flag before dispatch, so carry its
  # value into this command as well as accepting the direct helper argument.
  local apply=0 consent=0 update=0 interactive=0 guided=0 profile="full-native" profile_set=0 components="" verbose="${TERNUXX_VERBOSE:-0}" arg plan_id="" guest_plan_id="" guest_user=""
  local combined_guest=0
  local profile_lib="${_TN_LIB_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)}"
  if [ -n "${1:-}" ] && command -v python3 >/dev/null 2>&1 \
      && PYTHONPATH="$profile_lib" command python3 -c 'import sys; from proot_profiles import installable_aliases; sys.exit(0 if sys.argv[1] in installable_aliases(sys.argv[2]) else 1)' "$1" "$(cd -- "$profile_lib/.." && pwd -P)"; then
    local distro="$1"
    shift
    _nt_install_managed_guest "$distro" "$@"
    return $?
  fi
  case "${1:-}" in
    alpine|archlinux|fedora|void|kali)
      nt_fail "Ternuxx does not yet have a managed ${1} setup profile."
      return 2 ;;
  esac
  _NT_INSTALL_GUEST_USER=""
  _NT_COMBINED_GUEST_JSON=""
  _NT_COMBINED_GUEST_PLAN_ID=""
  _NT_COMBINED_GUEST_RESULT=""
  while [ $# -gt 0 ]; do
    arg="$1"; shift
    case "$arg" in
      --yes) apply=1; consent=1 ;;
      --update) update=1 ;;
      --verbose) verbose=1 ;;
      --interactive|interactive) interactive=1 ;;
      --profile) [ $# -gt 0 ] || { nt_fail "--profile needs a named preset."; return 2; }; profile="$1"; profile_set=1; shift ;;
      --components) [ $# -gt 0 ] || { nt_fail "--components needs comma-separated component groups."; return 2; }; components="$1"; shift ;;
      --user) [ $# -gt 0 ] || { nt_fail "--user needs a guest username."; return 2; }; guest_user="$1"; shift ;;
      --guest-plan-id) [ $# -gt 0 ] || { nt_fail "--guest-plan-id needs the ID from a fresh Debian preview."; return 2; }; guest_plan_id="$1"; shift ;;
      preview) ;;
      update) update=1 ;;
      apply)
        apply=1; consent=1
        if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9a-f]{64}$ ]]; then plan_id="$1"; shift; fi
        ;;
      --plan-id) [ $# -gt 0 ] || { nt_fail "--plan-id requires an ID from a saved preview."; return 2; }; plan_id="$1"; shift ;;
      --preview) apply=0 ;;
      *) nt_fail "Unknown install option: $arg"; return 2 ;;
    esac
  done

  if [ "$interactive" = "1" ]; then
    [ "$profile_set" = "0" ] && [ -z "$components" ] && [ -z "$guest_user" ] && [ -z "$guest_plan_id" ] && [ "$update" = "0" ] && [ "$apply" = "0" ] || {
      nt_fail "Interactive selection is preview-only; do not combine it with a profile, components, update, or apply."; return 2;
    }
    nt_fail 'Use tx install or tx install interactive without additional options for guided setup.'
    return 2
  else
    _nt_select_install_profile "$profile" "$components" || return $?
  fi
  if [ "$profile" = native-debian ]; then
    combined_guest=1
    [ -n "$guest_user" ] || { nt_fail "The native-debian profile requires --user NAME."; return 2; }
    [[ "$guest_user" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || { nt_fail "Invalid Debian guest username."; return 2; }
    _NT_INSTALL_GUEST_USER="$guest_user"
  elif [ -n "$guest_user$guest_plan_id" ]; then
    nt_fail "--user and --guest-plan-id are only valid with --profile native-debian."
    return 2
  fi
  if [ "$combined_guest" = "1" ] && [ "$update" = "1" ]; then
    nt_fail "The native-debian profile is for a fresh initial setup, not package updates."
    return 2
  fi
  if [ "$update" = "1" ] && { [ "$profile" != "full-native" ] || [ "$profile_set" = "1" ] || [ -n "$components" ]; }; then
    nt_fail "Package updates use the fixed Ternuxx core set; install profiles apply only to initial setup."; return 2
  fi
  nt_require_termux || return 1
  if [ "$consent" = "1" ] && [ -z "$plan_id" ] && { [ "$combined_guest" != "1" ] || [ -z "$guest_plan_id" ]; }; then
    nt_fail "Apply requires the exact Native --plan-id and/or native-debian --guest-plan-id from the reviewed previews."
    return 2
  fi
  if [ "$consent" = "1" ] && [ "$combined_guest" = "1" ] && [[ ! "$guest_plan_id" =~ ^[0-9a-f]{64}$ ]]; then
    nt_fail "The native-debian profile requires --guest-plan-id from its fresh Debian preview."
    return 2
  fi
  if [ -n "$plan_id" ] && [ "$consent" != "1" ]; then
    nt_fail "--plan-id requires explicit --yes consent after preview review."
    return 2
  fi
  if [ "$consent" = "1" ] && [ -n "$plan_id" ] && [[ ! "$plan_id" =~ ^[0-9a-f]{64}$ ]]; then
    nt_fail "--plan-id must be the 64-character ID printed by a saved Native package preview."
    return 2
  fi
  if [ "$combined_guest" = "1" ] && [ -n "$guest_plan_id" ] && [ "$consent" != "1" ]; then
    nt_fail "--guest-plan-id is accepted only with --yes --plan-id after reviewing the combined preview."
    return 2
  fi
  for tool in apt-cache apt-get dpkg-query date; do
    nt_require_command "$tool" || return 1
  done
  if [ "$update" = "1" ]; then
    nt_require_command dpkg || return 1
  fi

  if ! _nt_package_index_fresh; then
    nt_fail "Official Termux package indexes are missing or older than 14 days. Refresh them with your normal Termux package workflow, then review the preview again. Ternuxx did not refresh them."
    return 1
  fi

  if [ "$update" = "1" ]; then
    _nt_make_update_plan || return 1
  else
    _nt_make_install_plan || return 1
  fi

  if [ ${#_NT_PLAN_PACKAGES[@]} -eq 0 ]; then
    if [ "$update" = "1" ]; then
      nt_ok "No applicable Ternuxx core package updates are available from the selected official repositories."
      [ "$TERNUXX_JSON" != "1" ] || printf '{"install":"up_to_date","packages_changed":false}\n'
      return 0
    fi
    nt_ok "Ternuxx profile $_NT_ACTIVE_PROFILE packages are already installed."
    [ "$combined_guest" = "1" ] || nt_info "Optional managed Debian/Ubuntu guest: tx install proot (choose a distro and guest options)."
    nt_info "Skipped components: $_NT_ACTIVE_SKIPPED_COMPONENTS"
    if [ "$combined_guest" = "1" ]; then
      if [ "$apply" = "1" ]; then
        [ -z "$plan_id" ] || { nt_fail "Native package state changed to already installed; discard the stale Native plan and preview the combined profile again."; return 1; }
        _NT_COMBINED_GUEST_PLAN_ID="$guest_plan_id"
        _nt_apply_combined_guest || return $?
        if [ "$TERNUXX_JSON" = "1" ]; then
          printf '{"install":"combined_complete","profile":"native-debian","native_packages_changed":false,"guest":%s}\n' "$_NT_COMBINED_GUEST_RESULT"
        fi
        return 0
      fi
      _nt_combined_guest_preview || return $?
      nt_info "Native package phase: already installed; no Native plan ID is needed."
      nt_info "Combined apply after review: tx install apply --profile native-debian --user $guest_user --guest-plan-id $_NT_COMBINED_GUEST_PLAN_ID --yes"
      if [ "$TERNUXX_JSON" = "1" ]; then
        printf '{"install":"combined_preview","profile":"native-debian","native_packages_changed":false,"guest":%s}\n' "$_NT_COMBINED_GUEST_JSON"
      fi
      return 0
    fi
    if [ "$TERNUXX_JSON" = "1" ]; then
      printf '{"install":"already_installed","profile":"%s","skipped_components":"%s","packages_changed":false}\n' "$_NT_ACTIVE_PROFILE" "$_NT_ACTIVE_SKIPPED_COMPONENTS"
    elif [ "$apply" = "1" ] && [ "$combined_guest" != "1" ] && [ "$update" != "1" ]; then
      _nt_offer_managed_guest || return $?
    elif [ "$guided" = "1" ] && [ "$TERNUXX_JSON" != "1" ]; then
      nt_info "Native workstation is already installed."
      _nt_offer_managed_guest || return $?
    fi
    return 0
  fi
  if [ "$combined_guest" = "1" ] && [ "$apply" = "1" ] && [ -z "$plan_id" ]; then
    nt_fail "Native packages still need changes; review and supply the exact Native --plan-id plus the guest --guest-plan-id."
    return 2
  fi

  if [ "$update" != "1" ]; then TERNUXX_VERBOSE="$verbose" _nt_print_install_resource_estimates; fi

  if [ "$guided" = "1" ]; then
    [ -t 0 ] || { nt_fail "Interactive installation needs an attached terminal."; return 2; }
    if ! _nt_write_install_record preview; then
      nt_fail "Could not save the exact Native package preview; no packages were installed."
      return 1
    fi
    plan_id="$( _nt_compute_plan_id )" || return 1
    nt_info "Native preview: $_NT_ACTIVE_PROFILE · ${#_NT_PLAN_VERSIONS[@]} requested packages · ${#_NT_PLAN_TRANSACTION[@]} total package changes."
    if [ "${_NT_PLAN_ALLOW_VLC_REPLACEMENT:-0}" = 1 ]; then
      nt_info "Only the exact vlc-to-vlc-qt GUI replacement and its displayed dependencies will be applied; no other removals are allowed."
    elif [ "${_NT_PLAN_ALLOW_TUR:-0}" = 1 ]; then
      nt_info "TUR packages are allowed only for the explicitly selected Blender package and its displayed dependency closure."
    else
      nt_info "Only the displayed transaction from official Termux repositories will be applied; upgrades and removals are refused."
    fi
    printf 'Install this Native workstation profile now? [y/N] ' >/dev/tty
    local guided_answer
    IFS= read -r guided_answer </dev/tty || return 2
    case "$guided_answer" in
      y|Y|yes|YES|Yes) apply=1; consent=1 ;;
      *) nt_info "Cancelled; no Native packages were changed."; return 0 ;;
    esac
  fi

  if { [ "$apply" = "1" ] && [ "${TERNUXX_WIZARD_ACTIVE:-0}" != 1 ]; } || [ "$verbose" = "1" ]; then
    if [ "$update" = "1" ]; then
      nt_info "Ternuxx Native core package update preview (official Termux repositories only):"
    else
      nt_info "Ternuxx Native package profile: $_NT_ACTIVE_PROFILE"
      nt_info "Skipped components: $_NT_ACTIVE_SKIPPED_COMPONENTS"
      if [ "${_NT_PLAN_ALLOW_TUR:-0}" = 1 ]; then
        nt_info "Ternuxx package preview (official Termux repositories + explicitly selected TUR Blender):"
      else
        nt_info "Ternuxx package preview (official Termux repositories only):"
      fi
    fi
    printf '  %s\n' "${_NT_PLAN_VERSIONS[@]}"
    nt_info "Resolved APT transaction (all changed packages, including dependencies):"
    printf '  %s\n' "${_NT_PLAN_TRANSACTION[@]}"
    nt_info "APT simulation only; no package state has changed."
    printf '%s\n' "$_NT_PLAN_SIMULATION"
    if [ "$update" = "1" ]; then
      nt_info "Only the displayed core-package updates and their exact simulated dependencies can change; removals, recommendations, and repository changes are refused."
    elif [ "${_NT_PLAN_ALLOW_VLC_REPLACEMENT:-0}" = 1 ]; then
      nt_info "This exact plan replaces CLI-only vlc with GUI-enabled vlc-qt; no other removals, upgrades, recommendations, or repository changes are allowed."
    elif [ "${_NT_PLAN_ALLOW_TUR:-0}" = 1 ]; then
      nt_info "This plan permits signed TUR packages only for the selected Blender and its displayed dependencies; no other repositories or removals are allowed."
    else
      nt_info "No upgrades, removals, recommendations, or repository changes are allowed by this plan."
    fi
  fi

  if [ "$apply" != "1" ]; then
    local record_path="${TERNUXX_STATE_DIR}/install-transactions"
    if _nt_write_install_record preview; then
      nt_info "Full dependency preview recorded under $record_path."
    else
      nt_fail "Could not persist the dependency preview; refusing to report a reproducible plan."
      return 1
    fi
    local plan_id
    plan_id="$( _nt_compute_plan_id )" || return 1
    if [ "$verbose" != "1" ]; then
      local operation_label="install"
      [ "$update" = "1" ] && operation_label="update"
      nt_info "Native package $operation_label preview"
      nt_info "Requested packages: ${#_NT_PLAN_VERSIONS[@]} · Resolved changes: ${#_NT_PLAN_TRANSACTION[@]}"
      nt_info "Profile: $_NT_ACTIVE_PROFILE"
      nt_info "Skipped components: $_NT_ACTIVE_SKIPPED_COMPONENTS"
      if [ "${_NT_PLAN_ALLOW_VLC_REPLACEMENT:-0}" = 1 ]; then
        nt_info "Exact replacement: remove CLI-only vlc and install GUI-enabled vlc-qt; no other removals are allowed."
        nt_info "Scope: official Termux repositories; no recommendations or unrelated upgrades."
      elif [ "${_NT_PLAN_ALLOW_TUR:-0}" = 1 ]; then
        nt_info "Scope: official Termux plus TUR only for selected Blender dependencies; no removals, recommendations, or unrelated upgrades."
      else
        nt_info "Scope: official Termux repositories; no removals, recommendations, or unrelated upgrades."
      fi
      nt_info "Preview only; no package changes have been made."
      nt_info "Run 'tx install $([ "$update" = "1" ] && printf 'update ')preview --verbose' to review package versions and the full APT simulation."
    fi
    nt_info "Preview ID: $plan_id"
    if [ "$combined_guest" = "1" ]; then
      _nt_combined_guest_preview || return $?
      nt_info "Combined apply after review: tx install apply --profile native-debian --user $guest_user --yes --plan-id $plan_id --guest-plan-id $_NT_COMBINED_GUEST_PLAN_ID"
    elif [ "$update" = "1" ]; then
      nt_info "Apply after review: tx install update apply $plan_id"
    elif [ "$_NT_ACTIVE_PROFILE" = "full-native" ]; then
      nt_info "Apply after review: tx install apply $plan_id"
    elif [ "$_NT_ACTIVE_PROFILE" = "custom" ]; then
      nt_info "Apply after review: tx install apply --profile custom --components $_NT_ACTIVE_COMPONENTS --yes --plan-id $plan_id"
    else
      nt_info "Apply after review: tx install apply --profile $_NT_ACTIVE_PROFILE --yes --plan-id $plan_id"
    fi
    [ "$combined_guest" = "1" ] || [ "$update" = "1" ] || nt_info "Optional managed Debian/Ubuntu guest: tx install proot (choose a distro and guest options)."
    if [ "$TERNUXX_JSON" = "1" ]; then
      local package_json
      package_json="$(nt_json_array "${_NT_PLAN_VERSIONS[@]}")"
      local transaction_json
      transaction_json="$(nt_json_array "${_NT_PLAN_TRANSACTION[@]}")"
      if [ "$update" = "1" ]; then
        printf '{"install":"update_preview","plan_id":"%s","packages":%s,"transaction":%s}\n' "$plan_id" "$package_json" "$transaction_json"
      elif [ "$combined_guest" = "1" ]; then
        printf '{"install":"combined_preview","profile":"native-debian","native_plan_id":"%s","native_packages":%s,"native_transaction":%s,"resource_estimates":%s,"guest":%s}\n' "$plan_id" "$package_json" "$transaction_json" "$_NT_PLAN_RESOURCE_ESTIMATES" "$_NT_COMBINED_GUEST_JSON"
      else
        printf '{"install":"preview","profile":"%s","skipped_components":"%s","plan_id":"%s","packages":%s,"transaction":%s,"resource_estimates":%s}\n' "$_NT_ACTIVE_PROFILE" "$_NT_ACTIVE_SKIPPED_COMPONENTS" "$plan_id" "$package_json" "$transaction_json" "$_NT_PLAN_RESOURCE_ESTIMATES"
      fi
    fi
    return 0
  fi

  # Rebuild the plan immediately before applying it and require an exact
  # match to a private saved preview explicitly named by the caller.
  if ! _nt_package_index_fresh; then
    nt_fail "Package state changed since the preview. Review a fresh preview; nothing was installed."
    return 1
  fi
  if [ "$update" = "1" ]; then
    _nt_make_update_plan || { nt_fail "Package state changed since the preview. Review a fresh preview; nothing was installed."; return 1; }
  elif ! _nt_make_install_plan; then
    nt_fail "Package state changed since the preview. Review a fresh preview; nothing was installed."
    return 1
  fi
  if [ ${#_NT_PLAN_PACKAGES[@]} -gt 0 ]; then
    if ! _nt_reviewed_preview_matches "$plan_id" >/dev/null; then
      nt_fail "The saved preview is missing, invalid, or does not match the current APT transaction. Nothing was installed; create and review a fresh preview."
      return 1
    fi
  elif [ "$combined_guest" != "1" ] || [ -n "$plan_id" ]; then
    nt_fail "The Native package transaction changed after preview. Create and review a fresh plan."
    return 1
  fi
  if [ ${#_NT_PLAN_PACKAGES[@]} -eq 0 ]; then
    nt_ok "Ternuxx profile $_NT_ACTIVE_PROFILE packages are already installed."
    [ "$combined_guest" = "1" ] || nt_info "Optional managed Debian/Ubuntu guest: tx install proot (choose a distro and guest options)."
    nt_info "Skipped components: $_NT_ACTIVE_SKIPPED_COMPONENTS"
    _NT_COMBINED_GUEST_PLAN_ID="$guest_plan_id"
    _nt_apply_combined_guest || return $?
    if [ "$TERNUXX_JSON" = "1" ]; then
      printf '{"install":"combined_complete","profile":"native-debian","native_packages_changed":false,"guest":%s}\n' "$_NT_COMBINED_GUEST_RESULT"
    fi
    return 0
  fi

  if [ "$update" != "1" ] && ! _nt_install_capacity_preflight; then
    nt_fail "Insufficient estimated storage; no package changes were started."
    return 1
  fi

  if ! _nt_write_install_record applying; then
    nt_fail "Could not record the start of this package transaction; refusing to invoke APT."
    return 1
  fi
  if [ "$update" = "1" ]; then
    nt_step "Applying the reviewed Ternuxx core package update (preview $plan_id)..."
  else
    nt_step "Installing the reviewed Ternuxx Native profile $_NT_ACTIVE_PROFILE (preview $plan_id)..."
  fi
  if ! _nt_apply_install_transaction; then
    if ! _nt_write_install_record failed; then
      nt_warn "APT failed and the failure record could not be saved under $TERNUXX_STATE_DIR/install-transactions."
    fi
    local retry_preview="tx install update preview"
    if [ "$update" != "1" ]; then
      retry_preview="tx install preview --profile $_NT_ACTIVE_PROFILE"
      [ "$_NT_ACTIVE_PROFILE" != "custom" ] || retry_preview="$retry_preview --components $_NT_ACTIVE_COMPONENTS"
    fi
    nt_fail "APT reported failure; some packages may have changed. Create and review a fresh plan with '$retry_preview', then apply its new ID. Do not assume the old plan still matches."
    return 1
  fi
  if ! _nt_write_install_record applied; then
    nt_warn "Packages were installed, but the transaction record could not be persisted under $TERNUXX_STATE_DIR/install-transactions."
  fi
  if [ "$update" = "1" ]; then
    nt_ok "The reviewed Ternuxx core package update completed."
  elif [ "$combined_guest" = "1" ]; then
    nt_ok "Ternuxx Native profile native-debian installed; beginning the reviewed fresh Debian guest phase."
    _NT_COMBINED_GUEST_PLAN_ID="$guest_plan_id"
    _nt_apply_combined_guest || return $?
  else
    if [ "${TERNUXX_WIZARD_ACTIVE:-0}" = 1 ]; then
      nt_ok 'Native management/workstation components installed.'
    else
      nt_ok "Ternuxx Native profile $_NT_ACTIVE_PROFILE installed. The Termux:X11 Android app still must be installed separately if absent."
    fi
    nt_info "Optional managed Debian/Ubuntu guest: tx install proot (choose a distro and guest options)."
  fi
  if [ "$combined_guest" != "1" ] && [ "$update" != "1" ] && [ "$TERNUXX_JSON" != "1" ]; then
    _nt_offer_managed_guest || return $?
  fi
  if [ "$TERNUXX_JSON" = "1" ]; then
    local package_json
    package_json="$(nt_json_array "${_NT_PLAN_VERSIONS[@]}")"
    local transaction_json
    transaction_json="$(nt_json_array "${_NT_PLAN_TRANSACTION[@]}")"
    if [ "$update" = "1" ]; then
      printf '{"install":"updated","packages":%s,"transaction":%s}\n' "$package_json" "$transaction_json"
    elif [ "$combined_guest" = "1" ]; then
      printf '{"install":"combined_complete","profile":"native-debian","native_packages_changed":true,"packages":%s,"transaction":%s,"resource_estimates":%s,"guest":%s}\n' "$package_json" "$transaction_json" "$_NT_PLAN_RESOURCE_ESTIMATES" "$_NT_COMBINED_GUEST_RESULT"
    else
      printf '{"install":"complete","profile":"%s","skipped_components":"%s","packages":%s,"transaction":%s,"resource_estimates":%s}\n' "$_NT_ACTIVE_PROFILE" "$_NT_ACTIVE_SKIPPED_COMPONENTS" "$package_json" "$transaction_json" "$_NT_PLAN_RESOURCE_ESTIMATES"
    fi
  fi
  return 0
}


# Short distro-named entrypoint for the managed guest installer. It retains
# the same exact preview/apply plan and hidden password prompt as proot setup.
_nt_managed_desktop_choices() {
  local distro="$1" repo_root="$2"
  PYTHONPATH="$repo_root/lib" python3 - "$distro" "$repo_root" <<'PYDESKTOPS'
import sys
import proot_desktops
import proot_profiles
alias, repo_root = sys.argv[1:]
profile = proot_profiles.install_profile(repo_root, alias)
for desktop_id, item in proot_desktops.PROVIDERS[profile["profile_id"]].items():
    routes = sorted(proot_desktops.DESKTOP_ROUTES.get(desktop_id, ()))
    route_label = "+".join(routes) if routes else "catalog-only; no accepted route"
    print(f"{desktop_id}: {item['name']} ({route_label})")
PYDESKTOPS
}

_nt_install_managed_guest() {
  local distro="$1"; shift
  local label action=guided consent=0 user="" plan_id="" sudo_mode=password desktops="xfce" desktops_set=0 apps="" apps_set=0 groups=base arg repo_root output answer
  repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
  command -v python3 >/dev/null 2>&1 || { nt_fail "Python is required to load managed guest profiles."; return 1; }
  . "$repo_root/lib/install_window.sh"
  label="$(_nt_window_query "Load $distro managed profile" env PYTHONPATH="$repo_root/lib" python3 -c 'import sys,proot_profiles; print(proot_profiles.install_profile(sys.argv[2],sys.argv[1])["label"])' "$distro" "$repo_root"
  )" || { nt_fail "Unsupported managed distro: $distro."; return 2; }
  while [ $# -gt 0 ]; do
    arg="$1"; shift
    case "$arg" in
      preview) action=preview ;;
      apply) action=apply ;;
      --user) [ $# -gt 0 ] || { nt_fail "--user needs the ${label} guest username."; return 2; }; user="$1"; shift ;;
      --plan-id) [ $# -gt 0 ] || { nt_fail "--plan-id needs the exact ID from the ${label} preview."; return 2; }; plan_id="$1"; shift ;;
      --sudo-mode) [ $# -gt 0 ] || { nt_fail "--sudo-mode needs password or passwordless."; return 2; }; sudo_mode="$1"; shift ;;
      --apps) [ $# -gt 0 ] || { nt_fail "--apps needs comma-separated guest app IDs."; return 2; }; apps="$1"; apps_set=1; shift ;;
      --desktops) [ $# -gt 0 ] || { nt_fail "--desktops needs comma-separated desktop IDs."; return 2; }; desktops="$1"; desktops_set=1; shift ;;
      --yes) action=apply; consent=1 ;;
      *) nt_fail "Unknown ${label} install option: $arg"; return 2 ;;
    esac
  done
  local password_fd=""
  if [ "${_NT_USE_COLLECTED:-0}" = 1 ] && [ "${_NT_GUEST_READY[$distro]:-0}" = 1 ]; then
    user="${_NT_GUEST_USER[$distro]}"; sudo_mode="${_NT_GUEST_SUDO[$distro]}"
    desktops="${_NT_GUEST_DESKTOPS[$distro]}"; desktops_set=1
    apps="${_NT_GUEST_APPS[$distro]}"; apps_set=1
  fi
  if [ "$action" = guided ] && [ -t 0 ] && [ "${TERNUXX_JSON:-0}" != 1 ] && { [ -e "$PREFIX/var/lib/proot-distro/containers/$distro" ] || [ -L "$PREFIX/var/lib/proot-distro/containers/$distro" ]; }; then
    . "$repo_root/lib/install_wizard.sh"
    _nt_install_guest_addons "$distro" "$desktops" "$apps" "$desktops_set" "$apps_set" "$repo_root"
    return $?
  fi
  if [ -z "$user" ]; then
    [ -t 0 ] || { nt_fail "Choose a ${label} guest account with --user NAME."; return 2; }
    read -r -p "New ${label} guest username: " user || return 2
  fi
  [[ "$user" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || { nt_fail "Invalid guest username."; return 2; }
  case "$sudo_mode" in password|passwordless) ;; *) nt_fail "Choose --sudo-mode password or passwordless."; return 2 ;; esac
  nt_require_termux || return 1
  nt_require_command python3 || return 1
  if [ "$action" = guided ] && { [ ! -t 0 ] || [ "${TERNUXX_JSON:-0}" = 1 ]; }; then action=preview; fi
  if [ "$action" = guided ] && [ "$desktops_set" = 0 ]; then
    . "$repo_root/lib/install_wizard.sh"
    desktops="$(_nt_choose_guest_desktops "$distro" "$repo_root")" || return $?
  fi
  if [ "$action" = guided ] && [ "$apps_set" = 0 ]; then
    . "$repo_root/lib/install_wizard.sh"
    apps="$(_nt_choose_guest_apps "$distro" "$repo_root")" || return $?
  fi
  if [ "$action" = guided ]; then _nt_ai_guidance "$distro" "$apps"; fi
  local app
  for app in ${apps//,/ }; do
    [ "$app" = none ] || groups+=,app-"$app"
  done

  if [ "$action" = preview ]; then
    [ -z "$plan_id" ] || { nt_fail "A preview does not accept --plan-id."; return 2; }
    local -a args=(fresh-preview --repo-root "$repo_root" --alias "$distro" --user "$user" --sudo-mode "$sudo_mode" --desktops "$desktops" --groups "$groups")
    [ "${TERNUXX_JSON:-0}" = 1 ] && args+=(--json)
    output="$(python3 "$repo_root/lib/proot_setup.py" "${args[@]}")" || return $?
    printf '%s\n' "$output"
    if [ "${TERNUXX_JSON:-0}" != 1 ]; then
      local id
      id="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["plan_id"])' "$output")" || return 1
      nt_info "Apply after review: tx install $distro apply --user $user --sudo-mode $sudo_mode --yes --plan-id $id"
      nt_info "This installs the pinned $label profile with Ternuxx graphics/audio configuration. Existing guest data is preserved."
    fi
    return 0
  fi
  if [ "$action" = guided ]; then
    . "$repo_root/lib/install_window.sh"
    local -a preview_args=(fresh-preview --repo-root "$repo_root" --alias "$distro" --user "$user" --sudo-mode "$sudo_mode" --desktops "$desktops" --groups "$groups" --json)
    output="$(_nt_window_query "Review $distro rootfs and workstation plan" python3 "$repo_root/lib/proot_setup.py" "${preview_args[@]}")" || return $?
    printf '%s\n' "$output" | python3 "$repo_root/lib/proot_setup_present.py" || return $?
    local preview_id preview_status blocked
    preview_id="$(command python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("plan_id", ""))' <<<"$output")" || return 1
    preview_status="$(command python3 -c 'import json,sys; print(json.load(sys.stdin).get("status", ""))' <<<"$output")" || return 1
    blocked="$(command python3 -c 'import json,sys; print(json.load(sys.stdin).get("operation", {}).get("apply_blocked_reason") or "")' <<<"$output")" || return 1
    [[ "$preview_status" = preview && "$preview_id" =~ ^[0-9a-f]{64}$ && -z "$blocked" ]] || {
      nt_info "This $label setup preview cannot be applied as shown. No guest changes were made."
      return 0
    }
    . "$repo_root/lib/install_picker.sh"
    _nt_confirm "Install this exact $label plan for $user with ${desktops//,/ + }?" || { nt_info "Cancelled; no guest changes were made."; return 0; }
    plan_id="$preview_id"; consent=1; action=apply
  fi
  [ "$consent" = 1 ] || { nt_fail "Apply requires --yes after reviewing the exact preview."; return 2; }
  if [ "$sudo_mode" = password ] && [ ! -t 0 ]; then
    nt_fail "Password mode needs an attached Native terminal for hidden prompts; use --sudo-mode passwordless only if you want guest-only NOPASSWD sudo."
    return 2
  fi
  [ -n "$plan_id" ] || { nt_fail "Apply requires the exact --plan-id from a reviewed preview."; return 2; }
  [[ "$plan_id" =~ ^[0-9a-f]{64}$ ]] || { nt_fail "--plan-id must be the 64-character ID from a $label preview."; return 2; }
  local -a args=(fresh-install --repo-root "$repo_root" --alias "$distro" --user "$user" --sudo-mode "$sudo_mode" --plan-id "$plan_id" --yes)
  [ "${TERNUXX_JSON:-0}" = 1 ] && args+=(--json)
  if [ "${_NT_USE_COLLECTED:-0}" = 1 ] && [ "${_NT_GUEST_READY[$distro]:-0}" = 1 ] && [ "$sudo_mode" = password ]; then
    exec {password_fd}< <(printf '%s\n' "${_NT_GUEST_PASSWORD[$distro]}")
    args+=(--password-fd "$password_fd")
  fi
  if [ "${_NT_USE_COLLECTED:-0}" = 1 ] && [ "${_NT_WINDOW_ACTIVE:-0}" = 1 ]; then
    _nt_window_run python3 "$repo_root/lib/proot_setup.py" "${args[@]}"
  else
    python3 "$repo_root/lib/proot_setup.py" "${args[@]}"
  fi
  local result=$?
  [ -z "$password_fd" ] || exec {password_fd}<&-
  unset '_NT_GUEST_PASSWORD[$distro]'
  return "$result"
}
