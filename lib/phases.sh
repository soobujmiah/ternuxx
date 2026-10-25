# =============================================================================
#  Ternuxx package setup
#
#  Installation always begins with a repository and dependency preview.
#  Nothing is installed unless the caller explicitly passes --yes.
# =============================================================================
# shellcheck source=lib/core.sh
. "$(dirname "${BASH_SOURCE[0]}")/core.sh"

# Native host packages include Debian PRoot support, graphical diagnostics, and
# X11 test utilities. Heavy applications and Mesa providers remain optional.
_NT_CORE_PACKAGES=(python)
_NT_DESKTOP_PACKAGES=(
  termux-x11-nightly dbus xfce4-session xfce4-panel xfce4-settings xfwm4
  xfdesktop xfconf thunar xfce4-terminal
)
_NT_AUDIO_PACKAGES=(pulseaudio)
_NT_PROOT_PACKAGES=(proot-distro)
_NT_GRAPHICS_PACKAGES=(glmark2 mesa-demos vulkan-tools xorg-server-xvfb xdotool)
_NT_DEVELOPER_PACKAGES=(clang cmake gdb make pkg-config)
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
  vulkan-tools
  xorg-server-xvfb
  xdotool
)
_NT_FULL_NATIVE_PACKAGES=("${_NT_BASE_PACKAGES[@]}")
_NT_ACTIVE_PROFILE=full-native
_NT_ACTIVE_COMPONENTS=""
_NT_ACTIVE_SKIPPED_COMPONENTS=""
_NT_PLAN_MODE=install
_NT_PLAN_RESOURCE_ESTIMATES='{"schema_version":1,"complete":false,"packages":[]}'

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
    custom)
      selected=("${_NT_CORE_PACKAGES[@]}")
      [ -n "$components" ] || { nt_fail "Custom profile requires --components GROUPS."; return 2; }
      IFS=',' read -r -a groups <<< "$components"
      for group in "${groups[@]}"; do
        case "$group" in
          desktop) selected+=("${_NT_DESKTOP_PACKAGES[@]}") ;;
          audio) selected+=("${_NT_AUDIO_PACKAGES[@]}") ;;
          proot) selected+=("${_NT_PROOT_PACKAGES[@]}") ;;
          graphics) selected+=("${_NT_GRAPHICS_PACKAGES[@]}") ;;
          developer) selected+=("${_NT_DEVELOPER_PACKAGES[@]}") ;;
          *) nt_fail "Unknown component group '$group'. Choose desktop,audio,proot,graphics,developer."; return 2 ;;
        esac
      done ;;
    *) nt_fail "Unknown install profile '$profile'. Choose minimal-native, full-native, graphical, developer, native-proot-provider, or custom."; return 2 ;;
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
  for group in desktop audio proot graphics developer; do
    case "$profile" in
      full-native) [[ "$group" == developer ]] && omitted+=("$group") ;;
      graphical) [[ "$group" == proot || "$group" == developer ]] && omitted+=("$group") ;;
      developer) [[ "$group" != developer ]] && omitted+=("$group") ;;
      native-proot-provider) [[ "$group" != proot ]] && omitted+=("$group") ;;
      minimal-native) omitted+=("$group") ;;
      custom)
        case ",$components," in *",$group,"*) ;; *) omitted+=("$group") ;; esac ;;
    esac
  done
  omitted+=(guest)
  _NT_ACTIVE_SKIPPED_COMPONENTS="$(IFS=,; printf '%s' "${omitted[*]}")"
}

_nt_choose_install_profile() {
  local choice components
  [ -t 0 ] || { nt_fail "Interactive install needs a terminal; use tx install preview --profile NAME for automatic selection."; return 2; }
  printf '%s\n' \
    'Choose a Native workstation profile:' \
    '  1) Minimal Native Workstation (CLI management core)' \
    '  2) Full Native Workstation (XFCE, audio, diagnostics, PRoot provider)' \
    '  3) Graphical Workstation (XFCE, audio, graphics diagnostics)' \
    '  4) Developer Workstation (CLI core + compiler/debug tools)' \
    '  5) Native + PRoot provider (guest installation is a separate reviewed operation)' \
    '  6) Custom component groups'
  read -r -p 'Selection [1-6]: ' choice || return 2
  case "$choice" in
    1) _nt_select_install_profile minimal-native ;;
    2) _nt_select_install_profile full-native ;;
    3) _nt_select_install_profile graphical ;;
    4) _nt_select_install_profile developer ;;
    5) _nt_select_install_profile native-proot-provider ;;
    6)
      read -r -p 'Groups (desktop,audio,proot,graphics,developer): ' components || return 2
      _nt_select_install_profile custom "$components" ;;
    *) nt_fail "Choose a profile number from 1 to 6."; return 2 ;;
  esac
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

_nt_make_install_plan() {
  _NT_PLAN_MODE=install
  local package expected_repo candidate simulation
  _NT_PLAN_PACKAGES=()
  _NT_PLAN_VERSIONS=()
  _NT_PLAN_TRANSACTION=()

  for package in "${_NT_BASE_PACKAGES[@]}"; do
    if _nt_package_installed "$package"; then
      continue
    fi
    case "$package" in
      dbus|pulseaudio|python|proot-distro|vulkan-tools|clang|cmake|gdb|make|pkg-config) expected_repo="termux-main" ;;
      *) expected_repo="termux-x11" ;;
    esac
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

  simulation="$(apt-get -s --no-install-recommends --no-remove --no-upgrade install "${_NT_PLAN_PACKAGES[@]}" 2>&1)" || {
    nt_fail "APT could not resolve the preview. No packages were changed."
    printf '%s\n' "$simulation" >&2
    return 1
  }
  if printf '%s\n' "$simulation" | grep -Eq '^(Remv|The following packages will be REMOVED:)'; then
    nt_fail "The proposed transaction removes packages; refusing it. No packages were changed."
    return 1
  fi
  if ! printf '%s\n' "$simulation" | awk '/^(Inst|Conf) / && $0 !~ /termux-main|termux-x11/ { bad=1 } END { exit bad ? 1 : 0 }'; then
    nt_fail "The dependency plan includes a package outside the official Termux repositories; refusing it."
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
    if ! printf '%s\n' "$simulation" | awk -v package="$package" -v version="$expected_version" '$1 == "Inst" && $2 == package && (($3 == "(" && $4 == version) || (substr($3, 1, 1) == "(" && substr($3, 2) == version)) { found=1 } END { exit !found }'; then
      nt_fail "APT transaction did not include the reviewed candidate for $package; refusing it. No packages were changed."
      return 1
    fi
  done
  _NT_PLAN_TRANSACTION=()
  while IFS=' ' read -r package expected_version; do
    [ -n "$package" ] && _NT_PLAN_TRANSACTION+=("$package=$expected_version")
  done < <(printf '%s\n' "$simulation" | awk '$1 == "Inst" { version=$3; if (version == "(") version=$4; if (substr(version, 1, 1) == "(") version=substr(version, 2); print $2, version }')
  _NT_PLAN_SIMULATION="$simulation"
  _nt_capture_install_resource_estimates
}

_nt_make_update_plan() {
  _NT_PLAN_MODE=update
  local package expected_repo candidate installed simulation index expected_version
  _NT_PLAN_PACKAGES=()
  _NT_PLAN_VERSIONS=()
  _NT_PLAN_TRANSACTION=()
  _NT_PLAN_SIMULATION=""

  for package in "${_NT_BASE_PACKAGES[@]}"; do
    _nt_package_installed "$package" || continue
    case "$package" in
      dbus|pulseaudio|python|proot-distro|vulkan-tools) expected_repo="termux-main" ;;
      *) expected_repo="termux-x11" ;;
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
  if [ "${_NT_PLAN_MODE:-install}" = "update" ]; then
    apt-get --assume-yes --no-install-recommends --no-remove install "${_NT_PLAN_TRANSACTION[@]}"
  else
    apt-get --assume-yes --no-install-recommends --no-remove --no-upgrade install "${_NT_PLAN_TRANSACTION[@]}"
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

nt_cmd_install() {
  # `bin/tx` consumes --verbose as a global flag before dispatch, so carry its
  # value into this command as well as accepting the direct helper argument.
  local apply=0 consent=0 update=0 interactive=0 profile="full-native" profile_set=0 components="" verbose="${TERNUXX_VERBOSE:-0}" arg plan_id=""
  while [ $# -gt 0 ]; do
    arg="$1"; shift
    case "$arg" in
      --yes) apply=1; consent=1 ;;
      --update) update=1 ;;
      --verbose) verbose=1 ;;
      --interactive|interactive) interactive=1 ;;
      --profile) [ $# -gt 0 ] || { nt_fail "--profile needs a named preset."; return 2; }; profile="$1"; profile_set=1; shift ;;
      --components) [ $# -gt 0 ] || { nt_fail "--components needs comma-separated component groups."; return 2; }; components="$1"; shift ;;
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
    [ "$profile_set" = "0" ] && [ -z "$components" ] && [ "$update" = "0" ] && [ "$apply" = "0" ] || {
      nt_fail "Interactive selection is preview-only; do not combine it with a profile, components, update, or apply."; return 2;
    }
    _nt_choose_install_profile || return $?
  else
    _nt_select_install_profile "$profile" "$components" || return $?
  fi
  if [ "$update" = "1" ] && { [ "$profile" != "full-native" ] || [ "$profile_set" = "1" ] || [ -n "$components" ]; }; then
    nt_fail "Package updates use the fixed Ternuxx core set; install profiles apply only to initial setup."; return 2
  fi
  nt_require_termux || return 1
  if [ "$consent" = "1" ] && [ -z "$plan_id" ]; then
    nt_fail "Apply requires the ID from a saved preview: run 'tx install --preview' or 'tx install --update --preview', review it, then pass --yes --plan-id ID."
    return 2
  fi
  if [ -n "$plan_id" ] && [ "$consent" != "1" ]; then
    nt_fail "--plan-id requires explicit --yes consent after preview review."
    return 2
  fi
  if [ "$consent" = "1" ] && [[ ! "$plan_id" =~ ^[0-9a-f]{64}$ ]]; then
    nt_fail "--plan-id must be the 64-character ID printed by a saved preview."
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
    else
      nt_ok "Ternuxx profile $_NT_ACTIVE_PROFILE packages are already installed."
      nt_info "Skipped components: $_NT_ACTIVE_SKIPPED_COMPONENTS"
    fi
    if [ "$TERNUXX_JSON" = "1" ]; then
      if [ "$update" = "1" ]; then
        printf '{"install":"up_to_date","packages_changed":false}\n'
      else
        printf '{"install":"already_installed","profile":"%s","skipped_components":"%s","packages_changed":false}\n' "$_NT_ACTIVE_PROFILE" "$_NT_ACTIVE_SKIPPED_COMPONENTS"
      fi
    fi
    return 0
  fi

  if [ "$update" != "1" ]; then TERNUXX_VERBOSE="$verbose" _nt_print_install_resource_estimates; fi

  if [ "$apply" = "1" ] || [ "$verbose" = "1" ]; then
    if [ "$update" = "1" ]; then
      nt_info "Ternuxx Native core package update preview (official Termux repositories only):"
    else
      nt_info "Ternuxx Native package profile: $_NT_ACTIVE_PROFILE"
      nt_info "Skipped components: $_NT_ACTIVE_SKIPPED_COMPONENTS"
      nt_info "Ternuxx package preview (official Termux repositories only):"
    fi
    printf '  %s\n' "${_NT_PLAN_VERSIONS[@]}"
    nt_info "Resolved APT transaction (all changed packages, including dependencies):"
    printf '  %s\n' "${_NT_PLAN_TRANSACTION[@]}"
    nt_info "APT simulation only; no package state has changed."
    printf '%s\n' "$_NT_PLAN_SIMULATION"
    if [ "$update" = "1" ]; then
      nt_info "Only the displayed core-package updates and their exact simulated dependencies can change; removals, recommendations, and repository changes are refused."
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
      nt_info "Scope: official Termux repositories; no removals, recommendations, or unrelated upgrades."
      nt_info "Preview only; no package changes have been made."
      nt_info "Run 'tx install $([ "$update" = "1" ] && printf 'update ')preview --verbose' to review package versions and the full APT simulation."
    fi
    nt_info "Preview ID: $plan_id"
    if [ "$update" = "1" ]; then
      nt_info "Apply after review: tx install update apply $plan_id"
    elif [ "$_NT_ACTIVE_PROFILE" = "full-native" ]; then
      nt_info "Apply after review: tx install apply $plan_id"
    elif [ "$_NT_ACTIVE_PROFILE" = "custom" ]; then
      nt_info "Apply after review: tx install apply --profile custom --components $_NT_ACTIVE_COMPONENTS --yes --plan-id $plan_id"
    else
      nt_info "Apply after review: tx install apply --profile $_NT_ACTIVE_PROFILE --yes --plan-id $plan_id"
    fi
    if [ "$TERNUXX_JSON" = "1" ]; then
      local package_json
      package_json="$(nt_json_array "${_NT_PLAN_VERSIONS[@]}")"
      local transaction_json
      transaction_json="$(nt_json_array "${_NT_PLAN_TRANSACTION[@]}")"
      if [ "$update" = "1" ]; then
        printf '{"install":"update_preview","plan_id":"%s","packages":%s,"transaction":%s}\n' "$plan_id" "$package_json" "$transaction_json"
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
  if ! _nt_reviewed_preview_matches "$plan_id" >/dev/null; then
    nt_fail "The saved preview is missing, invalid, or does not match the current APT transaction. Nothing was installed; create and review a fresh preview."
    return 1
  fi
  if [ ${#_NT_PLAN_PACKAGES[@]} -eq 0 ]; then
    nt_ok "Ternuxx profile $_NT_ACTIVE_PROFILE packages are already installed."
    nt_info "Skipped components: $_NT_ACTIVE_SKIPPED_COMPONENTS"
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
  else
    nt_ok "Ternuxx Native profile $_NT_ACTIVE_PROFILE installed. The Termux:X11 Android app still must be installed separately if absent."
  fi
  if [ "$TERNUXX_JSON" = "1" ]; then
    local package_json
    package_json="$(nt_json_array "${_NT_PLAN_VERSIONS[@]}")"
    local transaction_json
    transaction_json="$(nt_json_array "${_NT_PLAN_TRANSACTION[@]}")"
    if [ "$update" = "1" ]; then
      printf '{"install":"updated","packages":%s,"transaction":%s}\n' "$package_json" "$transaction_json"
    else
      printf '{"install":"complete","profile":"%s","skipped_components":"%s","packages":%s,"transaction":%s,"resource_estimates":%s}\n' "$_NT_ACTIVE_PROFILE" "$_NT_ACTIVE_SKIPPED_COMPONENTS" "$package_json" "$transaction_json" "$_NT_PLAN_RESOURCE_ESTIMATES"
    fi
  fi
  return 0
}
