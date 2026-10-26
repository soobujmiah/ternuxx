"""Keyboard/flow regression tests; no package changes or desktop sessions."""
import fcntl
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WizardTests(unittest.TestCase):
    def terminal(self, script, keys):
        master, slave = pty.openpty()
        process = subprocess.Popen(
            ['bash', '-c', script], stdin=slave, stdout=slave, stderr=slave,
            env={**os.environ, 'TERM': 'xterm', 'TERNUXX_JSON': '0'},
            start_new_session=True,
            preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),
        )
        os.close(slave)
        output = bytearray()
        try:
            deadline = time.monotonic() + 8
            sent = False
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], .2)
                if ready:
                    try:
                        output.extend(os.read(master, 65536))
                    except OSError:
                        break
                if not sent and b'Arrow keys:' in output:
                    os.write(master, keys)
                    sent = True
                if process.poll() is not None:
                    break
            process.wait(timeout=2)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        return process.returncode, output.decode(errors='replace')

    def picker(self, mode, defaults, keys):
        return self.terminal(
            f'source "{ROOT}/lib/install_picker.sh"; '
            f'result=$(_nt_pick "Fixture" {mode} "{defaults}" "a|Alpha" "b|Beta" "c|Gamma"); '
            'rc=$?; printf "RESULT=%s RC=%s\\n" "$result" "$rc"; exit "$rc"', keys)

    def test_arrow_selects_without_typing_id(self):
        rc, out = self.picker('single', '', b'\x1b[B\n')
        self.assertEqual(rc, 0, out)
        self.assertIn('RESULT=b RC=0', out)
        self.assertIn('\x1b[?1049l', out)

    def test_space_toggles_multiple_and_deselects_default(self):
        rc, out = self.picker('multi', 'a', b' \x1b[B \x1b[B \n')
        self.assertEqual(rc, 0, out)
        self.assertIn('RESULT=b,c RC=0', out)

    def test_escape_cancels_and_restores_screen(self):
        rc, out = self.picker('single', '', b'\x1b')
        self.assertEqual(rc, 130, out)
        self.assertIn('\x1b[?1049l', out)

    def test_none_choice_excludes_other_multiselect_entries(self):
        rc, out = self.terminal(
            f'source "{ROOT}/lib/install_picker.sh"; '
            'result=$(_nt_pick "Fixture" multi xfce "none|CLI only" "xfce|XFCE"); '
            'printf "RESULT=%s\\n" "$result"', b' \n')
        self.assertEqual(rc, 0, out)
        self.assertIn('RESULT=none', out)
        self.assertNotIn('RESULT=none,xfce', out)

    def test_gpu_menu_skip_does_not_touch_packages_or_backends(self):
        script = f'''source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
_nt_pick() {{ echo none; }}
_nt_wizard_native() {{ echo UNEXPECTED_INSTALL; }}
_nt_gpu_setup "{ROOT}" 1
'''
        rc, out = self.terminal(script, b'')
        self.assertEqual(rc, 0, out)
        self.assertNotIn('UNEXPECTED_INSTALL', out)

    def test_gpu_menu_does_not_offer_failed_native_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'options'
            script = f'''source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
_nt_gpu_probe() {{ echo 'unavailable|fixture unsupported GPU'; }}
_nt_pick() {{
  case "$1" in
    'Graphics/sound'*) echo native ;;
    'Native backend'*) printf '%s\\n' "$@" > "{log}"; echo keep ;;
  esac
}}
_nt_gpu_setup "{ROOT}"
'''
            rc, out = self.terminal(script, b'')
            options = log.read_text()
        self.assertEqual(rc, 0, out)
        self.assertIn('system|', options)
        self.assertNotIn('termux-zink|', options)
        self.assertIn('No accelerated backend is advertised', out)

    def test_entrypoint_uses_real_preview_envelope_and_handles_reinstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / 'prefix'
            (prefix / 'bin').mkdir(parents=True)
            home = Path(tmp) / 'home'
            home.mkdir()
            script = f'''source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
_nt_confirm() {{ return 0; }}
_nt_wizard_entrypoint "{ROOT}" || exit $?
_nt_wizard_entrypoint "{ROOT}"
'''
            result = subprocess.run(['bash', '-c', script], capture_output=True, text=True,
                env={**os.environ, 'PREFIX': str(prefix), 'HOME': str(home),
                      'TERNUXX_JSON': '0', 'TERNUXX_QUIET': '0'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((prefix / 'bin/tx').read_bytes(), (ROOT / 'scripts/tx-installed').read_bytes())
            self.assertIn('already current', result.stderr)
            self.assertNotIn('KeyError', result.stderr)

    def test_fixed_window_keeps_brand_system_header_and_restores_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = f'''source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
export HOME="{tmp}" TERNUXX_STATE_DIR="{tmp}/state"
stty rows 28 cols 90
_nt_install_preflight() {{ :; }}
_nt_window_snapshot() {{
  _NT_WINDOW_DEVICE=FixturePhone; _NT_WINDOW_ANDROID=16; _NT_WINDOW_SOC=FixtureCPU
  _NT_WINDOW_ABI=aarch64; _NT_WINDOW_RAM='8 GiB'; _NT_WINDOW_STORAGE='90 GiB'
  _NT_WINDOW_GPU='/dev/kgsl-fixture (readable)'; _NT_WINDOW_AUDIO='PulseAudio installed'
  _NT_WINDOW_KERNEL=fixture
}}
scenario() {{
  _nt_window_stage '1/7 | Fixture stage' 'Next: fixture choices'
  _nt_pick 'Choose your workstation' single '' 'minimal|Shared management'
}}
_nt_window_session scenario
'''
            rc, out = self.terminal(script, b'\n\n')
        self.assertEqual(rc, 0, out)
        for text in ('Ternuxx | Mobile workstation', 'Your phone. Your workstation.',
                     'FixturePhone', '/dev/kgsl-fixture', 'PulseAudio installed',
                     'Choose your workstation', 'Copyright (c) 2026 Sobuj Miah',
                     '1/7 | Fixture stage'):
            self.assertIn(text, out)
        self.assertEqual(out.count('\x1b[?1049h'), 1)
        self.assertEqual(out.count('\x1b[?1049l'), 1)
        self.assertIn('\x1b[r', out)

    def test_no_terminal_refuses_before_package_actions(self):
        result = subprocess.run(['bash', str(ROOT / 'tx'), 'install'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('attached terminal', result.stderr)

    def flow(self, profile):
        # Selectors, package tools, builds and probes are fixtures. Assert the
        # orchestration feeds only selected components to the exact-plan engine.
        script = f'''source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
nt_require_termux() {{ :; }}
_nt_install_system_info() {{ echo DEVICE; }}
_nt_pick() {{
  case "$1" in
    'Choose your workstation') echo {profile} ;;
    'Native desktops'*) echo mate,plasma ;;
    'Optional Native apps'*) echo browser,pdf ;;
    'Managed PRoot'*) echo debian,ubuntu ;;
  esac
}}
_nt_wizard_prepare() {{ echo PREPARE; }}
_nt_wizard_upgrade() {{ echo UPGRADE; }}
_nt_collect_guest() {{ echo COLLECT="$1"; }}
_nt_wizard_native() {{ echo PACKAGES="$1"; }}
_nt_wizard_entrypoint() {{ echo SHIM; }}
_nt_gpu_setup() {{ echo GPU_MENU; }}
_nt_confirm() {{ return 1; }}
_nt_install_managed_guest() {{ echo GUEST="$1"; }}
bash() {{ echo GUI_BUILD; }}
_nt_install_wizard
'''
        return self.terminal(script, b'')

    def test_minimal_has_terminal_and_development_without_gui_or_guest(self):
        rc, out = self.flow('minimal')
        self.assertEqual(rc, 0, out)
        self.assertIn('PACKAGES=terminal,developer', out)
        self.assertIn('GUI_BUILD', out)
        self.assertNotIn('GUEST=', out)
        self.assertLess(out.index('DEVICE'), out.index('PREPARE'))

    def test_native_selects_multiple_desktops_apps_and_management(self):
        rc, out = self.flow('native')
        self.assertEqual(rc, 0, out)
        self.assertIn('PACKAGES=terminal,developer,proot,audio,graphics,gui,services,gui,audio,sound-controls,graphics,mate,plasma,browser,pdf', out)
        self.assertIn('GUI_BUILD', out)
        self.assertNotIn('GUEST=', out)

    def test_full_installs_each_selected_guest_after_native(self):
        rc, out = self.flow('proot')
        self.assertEqual(rc, 0, out)
        self.assertIn('GUEST=debian', out)
        self.assertIn('GUEST=ubuntu', out)
        self.assertIn(',nested', out)
        self.assertIn('PACKAGES=terminal,developer,proot', out)
        self.assertLess(out.index('PACKAGES='), out.index('GUEST=debian'))

    def test_new_components_are_deduplicated_and_no_office_suite_is_added(self):
        result = subprocess.run(['bash', '-c', f'''source "{ROOT}/lib/phases.sh"
_nt_select_install_profile custom terminal,developer,gui,browser,pdf,music,images,terminal
printf '%s\\n' "${{_NT_BASE_PACKAGES[@]}}"
'''], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        packages = result.stdout.splitlines()
        self.assertEqual(len(packages), len(set(packages)))
        for package in ('git', 'clang', 'tmux', 'python', 'libvte', 'firefox', 'evince', 'audacious', 'ristretto'):
            self.assertIn(package, packages)
        self.assertNotIn('libreoffice', packages)

    def upgrade_fixture(self, simulation, changed=False):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'calls'
            script = f'''source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
_nt_confirm() {{ return 0; }}
_nt_package_installed() {{ return 0; }}
_nt_write_install_record() {{ echo record:$1 >> "{log}"; }}
_nt_compute_plan_id() {{ printf '%064d' 0; }}
_nt_reviewed_preview_matches() {{ return 0; }}
_nt_apply_install_transaction() {{ echo APPLY:"${{_NT_PLAN_TRANSACTION[*]}}" >> "{log}"; }}
env() {{
  case " $* " in
    *' pkg update '*) echo refresh >> "{log}"; return 0 ;;
    *' apt-get -s '*)
      if [ -f "{log}.sim" ] && [ "{int(changed)}" = 1 ]; then echo changed; else printf '%s\\n' '{simulation}'; fi
      touch "{log}.sim" ;;
    *) return 91 ;;
  esac
}}
_nt_wizard_prepare && _nt_wizard_upgrade
'''
            result = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
            return result, log.read_text() if log.exists() else ''

    def test_system_upgrade_applies_only_pinned_preview(self):
        result, log = self.upgrade_fixture('Inst python [3.1] (3.2 termux-main stable [aarch64])')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('APPLY:python=3.2', log)
        self.assertIn('record:preview', log)
        self.assertIn('record:applied', log)

    def test_system_upgrade_refuses_changed_transaction(self):
        result, log = self.upgrade_fixture('Inst python [3.1] (3.2 termux-main stable [aarch64])', changed=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('APPLY:', log)
        self.assertIn('Upgrade changed', result.stderr)

    def test_system_upgrade_refuses_nonofficial_candidates(self):
        result, log = self.upgrade_fixture('Inst other (1.0 third-party stable [aarch64])')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('APPLY:', log)

    def test_install_shortcuts_dispatch_native_and_guest_without_installing(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp)
            (lib / 'install_wizard.sh').write_text('''_nt_window_session() { "$@"; }
_nt_install_native_desktop() { echo NATIVE:"$*"; }
_nt_install_proot_short() { echo GUEST:"$*"; }
''')
            result = subprocess.run(['bash', '-c', f'''source "{ROOT}/lib/phases.sh"
_TN_LIB_DIR="{lib}"
nt_cmd_install xfce
nt_cmd_install mate
nt_cmd_install proot debian
nt_cmd_install proot debian xfce
nt_cmd_install proot ubuntu xfce
'''], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['NATIVE:xfce', 'NATIVE:mate',
                         'GUEST:debian', 'GUEST:debian xfce', 'GUEST:ubuntu xfce'])

    def test_pgui_short_desktop_routes_to_existing_supervisor(self):
        result = subprocess.run(['bash', '-c', f'''source "{ROOT}/lib/proot.sh"
_nt_proot_gui() {{ printf '%s\\n' "$*"; }}
nt_cmd_pgui xfce4
nt_cmd_pgui mate
nt_cmd_pgui
nt_cmd_pgui --alias ubuntu --desktop xfce
'''], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['start --desktop xfce', 'start --desktop mate', 'start', 'start --alias ubuntu --desktop xfce'])


if __name__ == '__main__':
    unittest.main()
