"""Exercise the shell package-plan parser with synthetic APT output."""
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASES = ROOT / "lib" / "phases.sh"


class PackagePlanTest(unittest.TestCase):
    def _apt_cache_fixture(self, output):
        temporary = tempfile.TemporaryDirectory(prefix="ternuxx-apt-cache-")
        path = Path(temporary.name) / "apt-cache"
        path.write_text("#!/bin/sh\ncat <<'APT_POLICY'\n" + output + "\nAPT_POLICY\n", encoding="utf-8")
        path.chmod(0o700)
        return temporary, path.parent

    def _candidate(self, output, repository):
        temporary, fixture_bin = self._apt_cache_fixture(output)
        try:
            result = subprocess.run(
                ["bash", "-c", 'source "$1"; _nt_package_candidate_from_official_repo xfce4-session "$2"',
                 "bash", str(PHASES), repository],
                env={**os.environ, "PATH": f"{fixture_bin}:{os.environ['PATH']}"},
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            return result
        finally:
            temporary.cleanup()

    def _update_plan(self, simulation, installed_versions=None):
        temporary = tempfile.TemporaryDirectory(prefix="ternuxx-apt-update-plan-")
        fixture_bin = Path(temporary.name)
        apt_get = fixture_bin / "apt-get"
        apt_get.write_text(
            "#!/bin/sh\ncat <<'APT_SIMULATION'\n" + simulation.rstrip() + "\nAPT_SIMULATION\n",
            encoding="utf-8",
        )
        apt_get.chmod(0o700)
        versions = installed_versions or {
            "python": "3.14.6-1", "pulseaudio": "17.0-4",
            "xfce4-session": "4.20.4-1", "python-ensurepip-wheels": "3.14.6-1",
        }
        query = fixture_bin / "dpkg-query"
        query.write_text(
            "#!/bin/sh\n"
            "format= package=\n"
            "for arg in \"$@\"; do case \"$arg\" in -f=*) format=${arg#-f=} ;; *) package=$arg ;; esac; done\n"
            "if [ \"$format\" = '${Version}' ]; then\n"
            "  case \"$package\" in\n" +
            "\n".join(f"    {name}) printf '%s\\n' '{version}' ;;" for name, version in versions.items()) +
            "\n    *) exit 1 ;;\n  esac\n"
            "else printf 'install ok installed\\n'; fi\n",
            encoding="utf-8",
        )
        query.chmod(0o700)
        command = "\n".join([
            'source "$1"',
            '_NT_BASE_PACKAGES=(python pulseaudio xfce4-session)',
            '_nt_package_installed() { return 0; }',
            '_nt_package_candidate_from_official_repo() { case "$1" in python) printf "3.14.8\\n";; pulseaudio) printf "17.0-5\\n";; xfce4-session) printf "4.20.4-1\\n";; esac; }',
            'if _nt_make_update_plan; then plan_rc=0; else plan_rc=$?; fi',
            'printf "MODE %s\\n" "$_NT_PLAN_MODE"',
            'printf "REQUEST %s\\n" "${_NT_PLAN_VERSIONS[*]}"',
            'printf "TRANSACTION %s\\n" "${_NT_PLAN_TRANSACTION[*]}"',
            'exit "$plan_rc"',
        ])
        result = subprocess.run(
            ["bash", "-c", command, "bash", str(PHASES)],
            env={**os.environ, "PATH": f"{fixture_bin}:{os.environ['PATH']}"},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        return temporary, result

    def test_install_profiles_resolve_to_explicit_shared_package_sets(self):
        command = """source "$1"
_nt_select_install_profile minimal-native
printf 'MIN %s\n' "${_NT_BASE_PACKAGES[*]}"
_nt_select_install_profile full-native
printf 'FULL %s\n' "${_NT_BASE_PACKAGES[*]}"
_nt_select_install_profile graphical
printf 'GUI %s\n' "${_NT_BASE_PACKAGES[*]}"
_nt_select_install_profile developer
printf 'DEV %s\n' "${_NT_BASE_PACKAGES[*]}"
_nt_select_install_profile native-proot-provider
printf 'PROOT %s\n' "${_NT_BASE_PACKAGES[*]}"
_nt_select_install_profile native-debian
printf 'COMBINED %s\n' "${_NT_BASE_PACKAGES[*]}"
printf 'COMBINED_SKIP %s\n' "$_NT_ACTIVE_SKIPPED_COMPONENTS"
_nt_select_install_profile custom 'desktop,proot,developer,desktop'
printf 'CUSTOM %s\n' "${_NT_BASE_PACKAGES[*]}"
_nt_select_install_profile custom 'mate,plasma'
printf 'ALT %s\n' "${_NT_BASE_PACKAGES[*]}"
printf 'ALT_SKIP %s\n' "$_NT_ACTIVE_SKIPPED_COMPONENTS"
"""
        result = subprocess.run(
            ["bash", "-c", command, "bash", str(PHASES)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MIN python\n", result.stdout)
        self.assertIn("FULL termux-x11-nightly dbus pulseaudio proot-distro python", result.stdout)
        self.assertIn("GUI python termux-x11-nightly dbus", result.stdout)
        self.assertIn("DEV python clang cmake gdb make pkg-config", result.stdout)
        self.assertIn("PROOT python proot-distro", result.stdout)
        self.assertIn("CUSTOM python termux-x11-nightly dbus xfce4-session", result.stdout)
        custom = result.stdout.split("CUSTOM ", 1)[1].splitlines()[0].split()
        self.assertEqual(len(custom), len(set(custom)))
        self.assertIn("ALT python mate plasma-desktop\n", result.stdout)
        self.assertIn("ALT_SKIP desktop,audio,proot,graphics,developer,terminal,gui,services,sound-controls,nested,guest-display,browser,music,images,pdf,editor,archive,video,guest\n", result.stdout)

    def test_native_debian_combined_preview_contains_both_exact_plans(self):
        script = """source "$1"
nt_require_termux() { return 0; }
nt_require_command() { return 0; }
_nt_package_index_fresh() { return 0; }
_nt_make_install_plan() {
  _NT_PLAN_PACKAGES=(python)
  _NT_PLAN_VERSIONS=(python=3.14.8)
  _NT_PLAN_TRANSACTION=(python=3.14.8)
  _NT_PLAN_SIMULATION='Inst python (3.14.8 termux-main stable/main [aarch64])'
  _NT_PLAN_RESOURCE_ESTIMATES='{"schema_version":1,"complete":true,"download_bytes":100,"installed_kib":200,"packages":[]}'
}
_nt_write_install_record() { return 0; }
_nt_compute_plan_id() { printf '%s\n' "$NATIVE_PLAN"; }
_nt_combined_guest_preview() {
  _NT_COMBINED_GUEST_PLAN_ID="$GUEST_PLAN"
  printf -v _NT_COMBINED_GUEST_JSON '{"status":"preview","plan_id":"%s"}' "$GUEST_PLAN"
}
nt_cmd_install preview --profile native-debian --user sobuj
"""
        env = {**os.environ, "TERNUXX_JSON": "1", "NATIVE_PLAN": "a" * 64, "GUEST_PLAN": "b" * 64}
        result = subprocess.run(
            ["bash", "-c", script, "bash", str(PHASES)], env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["install"], "combined_preview")
        self.assertEqual(payload["profile"], "native-debian")
        self.assertEqual(payload["native_plan_id"], "a" * 64)
        self.assertEqual(payload["guest"]["plan_id"], "b" * 64)

    def test_native_debian_combined_apply_runs_native_before_guest(self):
        script = """source "$1"
nt_require_termux() { return 0; }
nt_require_command() { return 0; }
_nt_package_index_fresh() { return 0; }
_nt_make_install_plan() {
  _NT_PLAN_PACKAGES=(python)
  _NT_PLAN_VERSIONS=(python=3.14.8)
  _NT_PLAN_TRANSACTION=(python=3.14.8)
  _NT_PLAN_SIMULATION='Inst python (3.14.8 termux-main stable/main [aarch64])'
  _NT_PLAN_RESOURCE_ESTIMATES='{"schema_version":1,"complete":true,"download_bytes":100,"installed_kib":200,"packages":[]}'
}
_nt_reviewed_preview_matches() { [[ "$1" = "$NATIVE_PLAN" ]]; }
_nt_install_capacity_preflight() { return 0; }
_nt_write_install_record() { return 0; }
_nt_apply_install_transaction() { printf 'native\n' >> "$ORDER_FILE"; }
_nt_apply_combined_guest() { printf 'guest\n' >> "$ORDER_FILE"; _NT_COMBINED_GUEST_RESULT='{"status":"complete"}'; }
nt_cmd_install apply --profile native-debian --user sobuj --yes --plan-id "$NATIVE_PLAN" --guest-plan-id "$GUEST_PLAN"
"""
        with tempfile.TemporaryDirectory(prefix="ternuxx-native-debian-apply-") as temporary:
            order_file = Path(temporary) / "order"
            env = {**os.environ, "TERNUXX_STATE_DIR": temporary,
                   "NATIVE_PLAN": "a" * 64, "GUEST_PLAN": "b" * 64,
                   "ORDER_FILE": str(order_file)}
            result = subprocess.run(
                ["bash", "-c", script, "bash", str(PHASES)], env=env,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(order_file.read_text().splitlines(), ["native", "guest"])

    def test_native_debian_apply_skips_native_phase_when_packages_are_present(self):
        script = """source "$1"
nt_require_termux() { return 0; }
nt_require_command() { return 0; }
_nt_package_index_fresh() { return 0; }
_nt_make_install_plan() {
  _NT_PLAN_PACKAGES=()
  _NT_PLAN_VERSIONS=()
  _NT_PLAN_TRANSACTION=()
  _NT_PLAN_SIMULATION='0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.'
}
_nt_apply_combined_guest() { printf 'guest:%s\n' "$_NT_COMBINED_GUEST_PLAN_ID" >> "$ORDER_FILE"; }
nt_cmd_install apply --profile native-debian --user sobuj --yes --guest-plan-id "$GUEST_PLAN"
"""
        with tempfile.TemporaryDirectory(prefix="ternuxx-native-debian-present-") as temporary:
            order_file = Path(temporary) / "order"
            env = {**os.environ, "TERNUXX_STATE_DIR": temporary,
                   "GUEST_PLAN": "b" * 64, "ORDER_FILE": str(order_file)}
            result = subprocess.run(
                ["bash", "-c", script, "bash", str(PHASES)], env=env,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(order_file.read_text().splitlines(), [f"guest:{'b' * 64}"])

    def test_distro_named_debian_preview_uses_one_pinned_guest_plan(self):
        script = """source "$1"
nt_require_termux() { return 0; }
nt_require_command() { return 0; }
python3() {
  printf '%s\n' "$*" >> "$ARGS_FILE"
  printf '{"status":"preview","plan_id":"%s"}\n' "$PLAN_ID"
}
nt_cmd_install debian --user sobuj
"""
        env = {**os.environ, "TERNUXX_JSON": "1", "PLAN_ID": "c" * 64,
               "ARGS_FILE": str(Path(tempfile.gettempdir()) / f"tx-install-args-{os.getpid()}")}
        args_file = Path(env["ARGS_FILE"])
        try:
            result = subprocess.run(
                ["bash", "-c", script, "bash", str(PHASES)], env=env,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["plan_id"], "c" * 64)
            forwarded = args_file.read_text()
            self.assertIn("fresh-preview", forwarded)
            self.assertIn("--user sobuj", forwarded)
            self.assertIn("--sudo-mode password", forwarded)
            self.assertIn("--desktops xfce", forwarded)
            self.assertIn("--json", forwarded)
        finally:
            args_file.unlink(missing_ok=True)

    def test_distro_named_guest_apply_requires_explicit_consent_and_exact_plan(self):
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_require_command() { return 0; }; nt_cmd_install debian apply --user sobuj --plan-id "' + "a" * 64 + '"',
             "bash", str(PHASES)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Apply requires --yes", result.stderr)

    def test_native_debian_profile_requires_user_before_package_probes(self):
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; nt_cmd_install preview --profile native-debian',
             "bash", str(PHASES)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --user NAME", result.stderr)

    def test_empty_install_plan_skips_package_estimator(self):
        command = """source "$1"
_NT_PLAN_TRANSACTION=()
_nt_capture_install_resource_estimates
printf '%s\n' "$_NT_PLAN_RESOURCE_ESTIMATES"
"""
        result = subprocess.run(
            ["bash", "-c", command, "bash", str(PHASES)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("usage:", result.stderr)
        estimate = json.loads(result.stdout)
        self.assertTrue(estimate["complete"])
        self.assertEqual(estimate["download_bytes"], 0)
        self.assertEqual(estimate["installed_kib"], 0)
        self.assertEqual(estimate["packages"], [])

    def test_custom_install_profile_rejects_unknown_and_unverified_desktop_groups(self):
        for group in ("arbitrary", "lxqt", "cinnamon"):
            with self.subTest(group=group):
                result = subprocess.run(
                    ["bash", "-c", 'source "$1"; _nt_select_install_profile custom "desktop,' + group + '"',
                     "bash", str(PHASES)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("Unknown component group", result.stderr)

    def test_update_plan_pins_direct_candidates_and_parses_upgrade_closure(self):
        simulation = "\n".join([
            "Inst python [3.14.6-1] (3.14.8 termux-main stable/main [aarch64])",
            "Inst pulseaudio [17.0-4] (17.0-5 termux-main stable/main [aarch64])",
            "Inst python-ensurepip-wheels [3.14.6-1] (3.14.8 termux-main stable/main [all])",
            "0 upgraded, 4 newly installed, 0 to remove and 0 not upgraded.",
        ])
        temporary, result = self._update_plan(simulation)
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("MODE update", result.stdout)
            self.assertIn("REQUEST python=3.14.8 pulseaudio=17.0-5", result.stdout)
            self.assertIn("TRANSACTION python=3.14.8 pulseaudio=17.0-5 python-ensurepip-wheels=3.14.8", result.stdout)
        finally:
            temporary.cleanup()

    def test_update_plan_rejects_removal_and_nonofficial_dependency(self):
        cases = [
            ("Inst python [3.14.6-1] (3.14.8 termux-main stable/main [aarch64])\nRemv unrelated [1] [1]", "removes packages"),
            ("Inst python [3.14.6-1] (3.14.8 termux-main stable/main [aarch64])\nInst dep (1 tur-packages/tur [aarch64])", "outside the official Termux repositories"),
        ]
        for simulation, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                temporary, result = self._update_plan(simulation)
                try:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected_error, result.stderr)
                finally:
                    temporary.cleanup()

    def test_base_workstation_plan_includes_previewed_proot_runtime(self):
        temporary = tempfile.TemporaryDirectory(prefix="ternuxx-native-plan-")
        fixture_bin = Path(temporary.name)
        apt_get = fixture_bin / "apt-get"
        apt_get.write_text("#!/bin/sh\nprintf 'Inst xfce4-session (4.20.4-1 termux-x11 stable/main [aarch64])\\n0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\\n'\n", encoding="utf-8")
        apt_get.chmod(0o700)
        command = "\n".join([
            'source "$1"',
            '_nt_package_installed() { [[ "$1" != xfce4-session ]]; }',
            '_nt_package_candidate_from_official_repo() { [[ "$1" = xfce4-session && "$2" = termux-x11 ]] || return 1; printf "4.20.4-1\\n"; }',
            '_nt_make_install_plan',
            'printf "ROOTS %s\\n" "${_NT_BASE_PACKAGES[*]}"',
            'printf "REQUEST %s\\n" "${_NT_PLAN_VERSIONS[*]}"',
        ])
        result = subprocess.run(
            ["bash", "-c", command, "bash", str(PHASES)],
            env={**os.environ, "PATH": f"{fixture_bin}:{os.environ['PATH']}"},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        temporary.cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        roots = result.stdout.split("ROOTS ", 1)[1].splitlines()[0].split()
        self.assertIn("proot-distro", roots)
        self.assertNotIn("virglrenderer-android", roots)
        self.assertIn("xfce4-session", roots)
        self.assertIn("mesa-demos", roots)
        self.assertIn("vulkan-tools", roots)

    def test_candidate_repository_is_checked_from_policy_origin_lines(self):
        policy = """xfce4-session:
  Installed: (none)
  Candidate: 4.20.4-1
  Version table:
     4.20.4-1 500
        500 https://grimler.se/termux/termux-x11 x11/main aarch64 Packages"""
        accepted = self._candidate(policy, "termux-x11")
        rejected = self._candidate(policy, "termux-main")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(accepted.stdout.strip(), "4.20.4-1")
        self.assertNotEqual(rejected.returncode, 0)

    def test_candidate_policy_with_installed_marker_is_parsed(self):
        policy = """xfce4-session:
  Installed: 4.20.4-1
  Candidate: 4.20.4-1
  Version table:
 *** 4.20.4-1 100
        100 https://grimler.se/termux/termux-x11 x11/main aarch64 Packages"""
        result = self._candidate(policy, "termux-x11")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "4.20.4-1")

    def test_signed_index_age_check_uses_shell_tools_without_python(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-index-") as temporary:
            prefix = Path(temporary) / "usr"
            lists = prefix / "var/lib/apt/lists"
            lists.mkdir(parents=True)
            now = datetime.now(timezone.utc)
            fresh = (now - timedelta(days=1)).strftime("%a, %d %b %Y %H:%M:%S UTC")
            stale = (now - timedelta(days=20)).strftime("%a, %d %b %Y %H:%M:%S UTC")
            for marker in ("termux-main", "termux-x11"):
                (lists / f"mirror_{marker}_InRelease").write_text(f"Date: {fresh}\n", encoding="utf-8")
            env = {**os.environ, "PREFIX": str(prefix)}
            command = f'source "{PHASES}"; _nt_package_index_fresh'
            self.assertEqual(subprocess.run(["bash", "-c", command], env=env, check=False).returncode, 0)
            for marker in ("termux-main", "termux-x11"):
                (lists / f"mirror_{marker}_InRelease").write_text(f"Date: {stale}\n", encoding="utf-8")
            self.assertNotEqual(subprocess.run(["bash", "-c", command], env=env, check=False).returncode, 0)


    def _plan_with_simulation(self, simulation):
        temporary = tempfile.TemporaryDirectory(prefix="ternuxx-apt-plan-")
        fixture_bin = Path(temporary.name)
        apt_get = fixture_bin / "apt-get"
        apt_get.write_text(
            "#!/bin/sh\ncat <<'APT_SIMULATION'\n" + simulation.rstrip() + "\nAPT_SIMULATION\n",
            encoding="utf-8",
        )
        apt_get.chmod(0o700)
        command = "source \"$1\"\n_NT_BASE_PACKAGES=(xfce4-session)\n_nt_package_installed() { return 1; }\n_nt_package_candidate_from_official_repo() { printf '4.20.4-1'; }\nif _nt_make_install_plan; then\n  printf 'PLAN-OK\\n'\n  printf 'TRANSACTION %s\\n' \"${_NT_PLAN_TRANSACTION[*]}\"\n  printf 'SIMULATION-BEGIN\\n%s\\nSIMULATION-END\\n' \"$_NT_PLAN_SIMULATION\"\nelse\n  exit 9\nfi"
        result = subprocess.run(
            ["bash", "-c", command, "bash", str(PHASES)],
            env={**os.environ, "PATH": f"{fixture_bin}:{os.environ['PATH']}"},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        temporary.cleanup()
        return result

    def test_install_plan_exposes_full_dependency_transaction(self):
        simulation = "\n".join([
            "NOTE: This is only a simulation!",
            "      apt needs root privileges for real execution.",
            "",
            "Reading package lists... Done",
            "The following additional packages will be installed:",
            "  dep-a dep-b",
            "The following NEW packages will be installed:",
            "  xfce4-session dep-a dep-b",
            "0 upgraded, 3 newly installed, 0 to remove and 12 not upgraded.",
            "Inst xfce4-session (4.20.4-1 termux-x11 x11/main [aarch64])",
            "Inst dep-a (1 termux-main stable/main [aarch64])",
            "Inst dep-b (2 termux-x11 x11/main [aarch64])",
            "Conf xfce4-session (4.20.4-1 termux-x11 x11/main [aarch64])",
        ])
        result = self._plan_with_simulation(simulation)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TRANSACTION xfce4-session=4.20.4-1 dep-a=1 dep-b=2", result.stdout)
        self.assertIn("Inst dep-a (1 termux-main", result.stdout)
        self.assertIn("0 upgraded, 3 newly installed, 0 to remove", result.stdout)

    def _install_command_fixture(self, temporary):
        root = Path(temporary)
        home = root / "home"
        prefix = root / "prefix"
        fixture_bin = root / "bin"
        index_dir = prefix / "var/lib/apt/lists"
        home.mkdir()
        index_dir.mkdir(parents=True)
        fixture_bin.mkdir()
        now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S UTC")
        for marker in ("termux-main", "termux-x11"):
            (index_dir / f"mirror_{marker}_InRelease").write_text(f"Date: {now}\n", encoding="utf-8")
        (fixture_bin / "apt-cache").write_text("""#!/bin/sh
case "$2" in
  python) cat <<'POLICY'
python:
  Installed: (none)
  Candidate: 3.14.8
  Version table:
     3.14.8 500
        500 https://packages-cf.termux.dev/apt/termux-main stable/main aarch64 Packages
POLICY
    ;;
  *) cat <<'POLICY'
xfce4-session:
  Installed: (none)
  Candidate: 4.20.4-1
  Version table:
     4.20.4-1 500
        500 https://grimler.se/termux/termux-x11 x11/main aarch64 Packages
POLICY
    ;;
esac
""", encoding="utf-8")
        (fixture_bin / "apt-get").write_text("""#!/bin/sh
if [ "$1" = "-s" ]; then
  case " $* " in
    *" python "*) printf 'Reading package lists... Done\nInst python (3.14.8 termux-main stable/main [aarch64])\n0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\n' ;;
    *) printf 'Reading package lists... Done\nInst xfce4-session (%s termux-x11 x11/main [aarch64])\n0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\n' "${FIXTURE_VERSION:-4.20.4-1}" ;;
  esac
  [ -z "${SIM_SUFFIX:-}" ] || printf '%s\n' "$SIM_SUFFIX"
  exit 0
fi
printf '%s\n' "$@" >> "$APT_APPLY_CAPTURE"
exit "${FIXTURE_APPLY_EXIT:-0}"
""", encoding="utf-8")
        (fixture_bin / "dpkg-query").write_text("""#!/bin/sh
for package in "$@"; do :; done
if [ "$package" = "xfce4-session" ] || { [ "$package" = "python" ] && [ "${FIXTURE_MINIMAL:-0}" = "1" ]; }; then echo 'deinstall ok config-files'; exit 1; fi
echo 'install ok installed'
""", encoding="utf-8")
        for tool in ("apt-cache", "apt-get", "dpkg-query"):
            (fixture_bin / tool).chmod(0o700)
        capture = root / "apt-apply-args.txt"
        env = {
            **os.environ,
            "HOME": str(home),
            "PREFIX": str(prefix),
            "TERMUX_VERSION": "fixture",
            "TERNUXX_STATE_DIR": str(home / ".local/share/ternuxx"),
            "APT_APPLY_CAPTURE": str(capture),
            "PATH": f"{fixture_bin}:{os.environ['PATH']}",
        }
        return env, capture

    def test_preview_id_applies_only_exact_full_closure_in_fixture(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-flow-") as temporary:
            env, capture = self._install_command_fixture(temporary)
            preview = subprocess.run(["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_cmd_install preview', "bash", str(PHASES)], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            import re
            match = re.search(r"Preview ID: ([0-9a-f]{64})", preview.stderr)
            self.assertIsNotNone(match, preview.stderr)
            applied = subprocess.run(["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_cmd_install apply "$2"', "bash", str(PHASES), match.group(1)], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertIn("install", capture.read_text(encoding="utf-8"))
            self.assertIn("xfce4-session=4.20.4-1", capture.read_text(encoding="utf-8"))
            records = list((Path(temporary) / "home/.local/share/ternuxx/install-transactions").glob("*.json"))
            self.assertEqual({json.loads(item.read_text())["outcome"] for item in records}, {"preview", "applying", "applied"})

    def test_minimal_profile_uses_the_same_preview_and_exact_apply_engine(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-profile-flow-") as temporary:
            env, capture = self._install_command_fixture(temporary)
            env["FIXTURE_MINIMAL"] = "1"
            env["TERNUXX_JSON"] = "1"
            base = ["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; shift; nt_cmd_install "$@"', "bash", str(PHASES)]
            preview = subprocess.run([*base, "preview", "--profile", "minimal-native"], env=env,
                                     text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertIn("Profile: minimal-native", preview.stderr)
            self.assertIn("Apply after review: tx install apply --profile minimal-native", preview.stderr)
            preview_json = json.loads(preview.stdout)
            self.assertEqual(preview_json["profile"], "minimal-native")
            self.assertIn("resource_estimates", preview_json)
            self.assertEqual(preview_json["resource_estimates"]["schema_version"], 1)
            self.assertFalse(preview_json["resource_estimates"]["complete"])
            import re
            match = re.search(r"Preview ID: ([0-9a-f]{64})", preview.stderr)
            self.assertIsNotNone(match, preview.stderr)
            applied = subprocess.run([*base, "apply", "--profile", "minimal-native", "--yes", "--plan-id", match.group(1)], env=env,
                                     text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            applied_args = capture.read_text(encoding="utf-8")
            self.assertIn("python=3.14.8", applied_args)
            self.assertNotIn("xfce4-session", applied_args)

    def test_failed_apply_records_partial_state_and_recommends_fresh_preview(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-failed-flow-") as temporary:
            env, _capture = self._install_command_fixture(temporary)
            env["FIXTURE_MINIMAL"] = "1"
            preview = subprocess.run(
                ["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_cmd_install preview --profile minimal-native',
                 "bash", str(PHASES)], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            import re
            match = re.search(r"Preview ID: ([0-9a-f]{64})", preview.stderr)
            self.assertIsNotNone(match, preview.stderr)
            env["FIXTURE_APPLY_EXIT"] = "42"
            applied = subprocess.run(
                ["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_cmd_install apply --profile minimal-native --yes --plan-id "$2"',
                 "bash", str(PHASES), match.group(1)], env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(applied.returncode, 1)
            self.assertIn("some packages may have changed", applied.stderr)
            self.assertIn("fresh plan", applied.stderr)
            records = [json.loads(item.read_text()) for item in
                       (Path(temporary) / "home/.local/share/ternuxx/install-transactions").glob("*.json")]
            self.assertEqual({record["outcome"] for record in records}, {"preview", "applying", "failed"})

    def test_install_capacity_preflight_refuses_estimated_payload_larger_than_free_space(self):
        estimates = json.dumps({"installed_kib": 5, "filesystem_free_bytes": 4096,
                                "download_bytes": 1000, "complete": True})
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; _NT_PLAN_RESOURCE_ESTIMATES="$2"; _nt_install_capacity_preflight',
             "bash", str(PHASES), estimates],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to start APT", result.stderr)

    def test_low_storage_apply_refuses_before_apt_or_applying_record(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-low-space-") as temporary:
            env, capture = self._install_command_fixture(temporary)
            env["FIXTURE_MINIMAL"] = "1"
            preview = subprocess.run(
                ["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_cmd_install preview --profile minimal-native',
                 "bash", str(PHASES)], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            import re
            match = re.search(r"Preview ID: ([0-9a-f]{64})", preview.stderr)
            self.assertIsNotNone(match, preview.stderr)
            env["FIXTURE_RESOURCE_JSON"] = json.dumps({
                "schema_version": 1, "complete": True, "installed_kib": 5,
                "download_bytes": 1000, "filesystem_free_bytes": 4096, "packages": [],
            })
            apply_script = "\n".join([
                'source "$1"',
                '_nt_capture_install_resource_estimates() { _NT_PLAN_RESOURCE_ESTIMATES="$FIXTURE_RESOURCE_JSON"; }',
                "nt_require_termux() { return 0; }",
                'nt_cmd_install apply --profile minimal-native --yes --plan-id "$2"',
            ])
            applied = subprocess.run(
                ["bash", "-c", apply_script, "bash", str(PHASES), match.group(1)], env=env,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(applied.returncode, 1)
            self.assertIn("Insufficient estimated storage", applied.stderr)
            self.assertFalse(capture.exists(), "APT must not run when the estimated payload cannot fit")
            records = [json.loads(item.read_text()) for item in
                       (Path(temporary) / "home/.local/share/ternuxx/install-transactions").glob("*.json")]
            self.assertEqual([record["outcome"] for record in records], ["preview"])

    def test_global_cli_verbose_flag_reaches_install_transaction_preview(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-global-verbose-") as temporary:
            env, _capture = self._install_command_fixture(temporary)
            env["TERNUXX_VERBOSE"] = "1"
            result = subprocess.run(
                ["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_cmd_install preview',
                 "bash", str(PHASES)],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Reading package lists", result.stdout)
            self.assertIn("Resolved APT transaction", result.stderr)

    def test_install_preview_is_concise_and_verbose_mode_shows_simulation(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-output-") as temporary:
            env, _capture = self._install_command_fixture(temporary)
            base = ["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; shift; nt_cmd_install "$@"', "bash", str(PHASES)]
            short = subprocess.run([*base, "preview"], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(short.returncode, 0, short.stderr)
            self.assertIn("Requested packages:", short.stderr)
            self.assertIn("Resolved changes:", short.stderr)
            self.assertIn("Preview only; no package changes", short.stderr)
            self.assertIn("Apply after review: tx install apply", short.stderr)
            self.assertNotIn("Reading package lists", short.stderr)

            verbose = subprocess.run([*base, "preview", "--verbose"], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(verbose.returncode, 0, verbose.stderr)
            self.assertIn("Reading package lists", verbose.stdout)
            self.assertIn("Resolved APT transaction", verbose.stderr)

    def test_changed_simulation_is_refused_before_apt_apply(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-mismatch-") as temporary:
            env, capture = self._install_command_fixture(temporary)
            preview = subprocess.run(["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_cmd_install --preview', "bash", str(PHASES)], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            import re
            match = re.search(r"Preview ID: ([0-9a-f]{64})", preview.stderr)
            self.assertIsNotNone(match, preview.stderr)
            changed_env = {**env, "SIM_SUFFIX": "Changed repository metadata"}
            applied = subprocess.run(["bash", "-c", 'source "$1"; nt_require_termux() { return 0; }; nt_cmd_install --yes --plan-id "$2"', "bash", str(PHASES), match.group(1)], env=changed_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertNotEqual(applied.returncode, 0)
            self.assertFalse(capture.exists(), "APT apply path must not run for a changed preview")

    def test_apply_uses_exact_version_pinned_full_transaction(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-apt-apply-") as temporary:
            fixture_bin = Path(temporary)
            apt_get = fixture_bin / "apt-get"
            apt_get.write_text("#!/bin/sh\ntest -z \"${LD_LIBRARY_PATH+x}\" || exit 77\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
            apt_get.chmod(0o700)
            command = 'source "$1"; _NT_PLAN_TRANSACTION=(xfce4-session=4.20.4-1 dep-a=2); _nt_apply_install_transaction'
            result = subprocess.run(["bash", "-c", command, "bash", str(PHASES)], env={**os.environ, "PATH": f"{fixture_bin}:{os.environ['PATH']}"}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("xfce4-session=4.20.4-1", result.stdout)
            self.assertIn("dep-a=2", result.stdout)
            self.assertIn("--no-upgrade", result.stdout)

    def test_update_apply_uses_only_the_exact_reviewed_transaction(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-apt-update-apply-") as temporary:
            fixture_bin = Path(temporary)
            apt_get = fixture_bin / "apt-get"
            apt_get.write_text("#!/bin/sh\ntest -z \"${LD_LIBRARY_PATH+x}\" || exit 77\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
            apt_get.chmod(0o700)
            command = 'source "$1"; _NT_PLAN_MODE=update; _NT_PLAN_TRANSACTION=(python=3.14.8 dependency=2); _nt_apply_install_transaction'
            result = subprocess.run(["bash", "-c", command, "bash", str(PHASES)], env={**os.environ, "PATH": f"{fixture_bin}:{os.environ['PATH']}"}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("python=3.14.8", result.stdout)
            self.assertIn("dependency=2", result.stdout)
            self.assertIn("--no-remove", result.stdout)
            self.assertNotIn("--no-upgrade", result.stdout)

    def test_install_plan_fails_closed_without_inst_records(self):
        simulation = "Reading package lists... Done\n0 upgraded, 0 newly installed, 0 to remove."
        result = self._plan_with_simulation(simulation)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APT did not return a complete install transaction", result.stderr)

    def test_apply_without_saved_preview_id_is_rejected_before_package_probes(self):
        command = "source \"$1\"; nt_fail() { :; }; TERNUXX_QUIET=1; TERNUXX_JSON=0; TERMUX_VERSION=test; PREFIX=/data/data/com.termux/files/usr; nt_cmd_install --yes"
        result = subprocess.run(["bash", "-c", command, "bash", str(PHASES)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 2)

    def test_install_record_path_rejects_outside_home_and_symlink(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-path-") as temporary, tempfile.TemporaryDirectory(prefix="ternuxx-outside-") as outside:
            home = Path(temporary)
            state = home / "state"
            command = 'source "$1"; _nt_install_state_dir_safe'
            result = subprocess.run(["bash", "-c", command, "bash", str(PHASES)], env={**os.environ, "HOME": str(home), "TERNUXX_STATE_DIR": outside}, check=False)
            self.assertNotEqual(result.returncode, 0)
            target = home / "linked"
            target.symlink_to(Path(outside), target_is_directory=True)
            result = subprocess.run(["bash", "-c", command, "bash", str(PHASES)], env={**os.environ, "HOME": str(home), "TERNUXX_STATE_DIR": str(target / "state")}, check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_transaction_record_persists_exact_preview_and_permissions(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-install-record-") as temporary:
            state = Path(temporary) / "state"
            command = "\n".join([
                'source "$1"',
                'TERNUXX_STATE_DIR="$2"',
                '_NT_PLAN_SIMULATION="$SIMULATION"',
                '_NT_PLAN_VERSIONS=(xfce4-session=4.20.4-1)',
                '_NT_PLAN_TRANSACTION=(xfce4-session=4.20.4-1 dep-a=1)',
                '_nt_write_install_record preview',
                'plan_id="$(_nt_compute_plan_id)"',
                'printf "PLAN_ID %s\\n" "$plan_id"',
                '_nt_reviewed_preview_matches "$plan_id" >/dev/null || exit 8',
                '_NT_PLAN_TRANSACTION+=(changed=1)',
                'if _nt_reviewed_preview_matches "$plan_id" >/dev/null 2>&1; then exit 9; fi',
            ])
            result = subprocess.run(
                ["bash", "-c", command, "bash", str(PHASES), str(state)],
                env={**os.environ, "HOME": temporary, "SIMULATION": "Inst xfce4-session (4.20.4-1 termux-x11 x11/main [aarch64])\nInst dep-a (1 termux-main stable/main [aarch64])"},
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            records = list((state / "install-transactions").glob("*.json"))
            self.assertEqual(len(records), 1)
            payload = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["outcome"], "preview")
            self.assertRegex(payload["plan_id"], r"^[0-9a-f]{64}$")
            self.assertEqual(payload["requested_candidates"], ["xfce4-session=4.20.4-1"])
            self.assertEqual(payload["resolved_transaction"], ["xfce4-session=4.20.4-1", "dep-a=1"])
            self.assertIn("termux-main stable/main [aarch64]", payload["apt_simulation"])
            self.assertEqual(records[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual((state / "install-transactions").stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
