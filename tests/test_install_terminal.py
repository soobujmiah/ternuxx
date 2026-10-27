"""Real PTY input/mode regressions; package managers and services never run."""
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import termios
import time
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TerminalFixture:
    def __init__(self, script, rows=28, columns=90):
        self.master, self.slave = pty.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))
        self.original = termios.tcgetattr(self.slave)
        self.output = bytearray()
        self.process = subprocess.Popen(
            ['bash', '-uc', script], stdin=self.slave, stdout=self.slave, stderr=self.slave,
            env={**os.environ, 'TERM': 'xterm-256color', 'TERNUXX_JSON': '0', 'TERNUXX_QUIET': '0'},
            start_new_session=True, preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0))

    def wait_for(self, marker, timeout=5, after=0):
        deadline = time.monotonic() + timeout
        while marker not in self.output[after:] and time.monotonic() < deadline:
            if select.select([self.master], [], [], .05)[0]:
                self.output.extend(os.read(self.master, 65536))
            if self.process.poll() is not None:
                break
        if marker not in self.output[after:]:
            raise AssertionError(f'{marker!r} missing: {self.output.decode(errors="replace")}')

    def send(self, keys):
        os.write(self.master, keys)

    def finish(self):
        self.process.wait(timeout=5)
        while select.select([self.master], [], [], 0)[0]:
            try:
                self.output.extend(os.read(self.master, 65536))
            except OSError:
                break
        return self.output.decode(errors='replace')

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        os.close(self.master)
        os.close(self.slave)


class InstallerTerminalTests(unittest.TestCase):
    def fixture(self, body, **kwargs):
        term = TerminalFixture(f'source "{ROOT}/lib/install_picker.sh"\n' + body, **kwargs)
        self.addCleanup(term.close)
        return term

    def test_fragmented_arrows_after_idle_are_not_echoed_and_restore_termios(self):
        term = self.fixture('result=$(_nt_pick "Confirm existing guest additions" single "" "no|Cancel" "yes|Continue"); echo RESULT=$result')
        term.wait_for(b'1/2 |')
        mode = termios.tcgetattr(term.slave)
        self.assertFalse(mode[3] & termios.ICANON)
        self.assertFalse(mode[3] & termios.ECHO)
        # Idle across the refresh timeout, then receive a keyboard sequence in pieces.
        time.sleep(1.1)
        for piece in (b'\x1b', b'[', b'B'):
            term.send(piece)
            time.sleep(.22)
        term.send(b'\n')
        out = term.finish()
        self.assertEqual(term.process.returncode, 0, out)
        self.assertIn('RESULT=yes', out)
        self.assertNotIn('^[[', out)
        self.assertEqual(termios.tcgetattr(term.slave), term.original)

    def test_sequential_command_substitution_menus_use_tty_even_with_redirected_stdin(self):
        term = self.fixture('''exec </dev/null
first=$(_nt_pick 'First menu' single '' 'a|Alpha' 'b|Beta') || exit $?
echo FIRST=$first
second=$(_nt_pick 'Second menu' single '' 'no|Cancel' 'yes|Continue') || exit $?
echo SECOND=$second''')
        term.wait_for(b'1/2 |')
        term.send(b'\x1b[B\n')
        term.wait_for(b'Second menu')
        term.send(b'\x1bOB\n')
        out = term.finish()
        self.assertIn('FIRST=b', out)
        self.assertIn('SECOND=yes', out)
        self.assertNotIn('^[[', out)
        self.assertEqual(termios.tcgetattr(term.slave), term.original)

    def test_long_list_pages_resizes_and_preserves_multiselect(self):
        term = self.fixture('''items=()
for ((i=1;i<=60;i++)); do items+=("app$i|Optional application $i"); done
result=$(_nt_pick 'Optional apps' multi '' "${items[@]}") || exit $?
echo RESULT=$result''', rows=24, columns=70)
        term.wait_for(b'1/60 |')
        term.send(b' \x1b[6~')
        term.wait_for(b'18/60 |')
        # The selected first item remains selected after page/size changes.
        fcntl.ioctl(term.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 85, 0, 0))
        os.killpg(term.process.pid, signal.SIGWINCH)
        term.send(b'\x1b[F \n')
        out = term.finish()
        self.assertEqual(term.process.returncode, 0, out)
        self.assertIn('RESULT=app1,app60', out)
        self.assertEqual(termios.tcgetattr(term.slave), term.original)

    def test_final_summary_needs_only_one_approval_keypress(self):
        term = self.fixture('''_NT_PICK_SUMMARY=('Native: terminal, graphics' 'Graphics: CPU + GPU' 'Download >= 12 MiB | extra disk >= 30 MiB' 'Additional sizes unknown: graphics/build scratch')
choice=$(_nt_pick 'Ready to install' single '' 'approve|Install everything shown' 'cancel|Cancel')
printf 'FINAL=%s\n' "$choice"
''', rows=24, columns=80)
        term.wait_for(b'Additional sizes unknown')
        term.send(b'\n')
        out = term.finish()
        self.assertIn('FINAL=approve', out)
        self.assertEqual(term.process.returncode, 0, out)
        self.assertEqual(termios.tcgetattr(term.slave), term.original)

    def test_existing_guest_confirmation_inside_fixed_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            term = self.fixture(f'''source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
export HOME="{tmp}" TERNUXX_STATE_DIR="{tmp}/state"
_nt_install_preflight() {{ :; }}
_nt_window_snapshot() {{
 _NT_WINDOW_DEVICE=FixturePhone; _NT_WINDOW_ANDROID=16; _NT_WINDOW_SOC=SM8735
 _NT_WINDOW_ABI=aarch64; _NT_WINDOW_RAM=8GiB; _NT_WINDOW_STORAGE=90GiB
 _NT_WINDOW_GPU=/dev/kgsl-fixture; _NT_WINDOW_AUDIO=PulseAudio; _NT_WINDOW_KERNEL=fixture
}}
scenario() {{
 _nt_window_stage '5/7 | Managed guest installation' 'Next: graphics and sound'
 _nt_confirm 'Add desktops/apps to existing debian (no rootfs replacement)?' || return $?
 if _nt_window_run bash -c "printf PARTIAL_PROMPT; sleep 1.2; printf '\\nWORKER_DONE\\n'; exit 7"; then
   return 99
 else
   echo WORKER_EXIT=$?
 fi
 echo CONFIRMED
}}
_nt_window_session scenario
''')
            term.wait_for(b'1/2 |')
            self.assertFalse(termios.tcgetattr(term.slave)[3] & termios.ECHO)
            # Keyboard pop-up can shrink a phone terminal: pause choices, then recover.
            start = len(term.output)
            fcntl.ioctl(term.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 18, 60, 0, 0))
            os.killpg(term.process.pid, signal.SIGWINCH)
            term.wait_for(b'Enlarge terminal', after=start)
            term.send(b'\n')
            start = len(term.output)
            fcntl.ioctl(term.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 28, 90, 0, 0))
            os.killpg(term.process.pid, signal.SIGWINCH)
            term.wait_for(b'1/2 |', after=start)
            term.send(b'\x1b[B\n')
            term.wait_for(b'TERNUXX installation finished')
            out = term.finish()
            self.assertEqual(term.process.returncode, 0, out)
            self.assertIn('CONFIRMED', out)
            self.assertIn('PARTIAL_PROMPT', out)
            self.assertIn('WORKER_DONE', out)
            self.assertIn('WORKER_EXIT=7', out)
            self.assertNotIn('^[[', out)
            self.assertNotIn('Installation log', out.split('5/7 |')[0])
            self.assertEqual(out.count('\x1b[?1049h'), 1)
            self.assertEqual(out.count('\x1b[?1049l'), 1)
            self.assertEqual(termios.tcgetattr(term.slave), term.original)

    def test_root_only_guest_account_form_arrows_password_and_resize(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / 'prefix'
            etc = prefix / 'var/lib/proot-distro/containers/debian/rootfs/etc'
            etc.mkdir(parents=True)
            (etc / 'passwd').write_text('root:x:0:0:root:/root:/bin/bash\n')
            term = self.fixture(f'''source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
export PREFIX="{prefix}"
_NT_WINDOW_ACTIVE=1; _NT_WINDOW_INSTALLING=0; _NT_WINDOW_STARTED=$SECONDS
_nt_window_snapshot
_nt_window_draw
_nt_collect_guest_account debian "{ROOT}" || exit $?
echo USER=${{_NT_GUEST_USER[debian]}} MODE=${{_NT_GUEST_SUDO[debian]}}
[ "${{_NT_GUEST_PASSWORD[debian]}}" = fixture-secret ] || exit 9
echo ACCOUNT_FORM_DONE
''')
            term.wait_for(b'Type text |')
            self.assertFalse(termios.tcgetattr(term.slave)[3] & termios.ECHO)
            term.send(b'\x1b[B\x1b[AaliceX\x7f')
            term.wait_for(b'> alice')
            term.send(b'\n')
            term.wait_for(b'1/2 |')
            term.send(b'\n')
            term.wait_for(b'Create guest sudo password')
            term.send(b'fixture-secret\n')
            term.wait_for(b'Confirm guest sudo password')
            # Keyboard resize retains the private input buffer and switches compact mode.
            term.send(b'fixture-')
            fcntl.ioctl(term.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 60, 0, 0))
            os.killpg(term.process.pid, signal.SIGWINCH)
            term.wait_for(b'TERNUXX')
            term.send(b'secret\n')
            term.wait_for(b'ACCOUNT_FORM_DONE')
            out = term.finish()
            self.assertEqual(term.process.returncode, 0, out)
            self.assertIn('USER=alice MODE=password', out)
            self.assertIn('ACCOUNT_FORM_DONE', out)
            self.assertNotIn('fixture-secret', out)
            self.assertNotIn('^[[', out)
            self.assertNotIn('Installation log', out)
            self.assertIn('╺┳╸ ┏━╸ ┏━┓', out)
            self.assertEqual(termios.tcgetattr(term.slave), term.original)

    def test_slow_guest_query_is_visible_silent_input_and_json_clean(self):
        term = self.fixture(f'''source "{ROOT}/lib/install_window.sh"
_NT_WINDOW_ACTIVE=1; _NT_WINDOW_INSTALLING=1; _NT_WINDOW_STARTED=$SECONDS
_nt_window_snapshot
_nt_window_draw
response=$(_nt_window_query 'Review debian packages' bash -c 'sleep 1.3; printf "{{\\"ok\\":true}}"') || exit $?
printf 'RESPONSE=%s\\n' "$response"
next=$(_nt_pick 'Next choice' single '' 'a|Alpha' 'b|Beta'); echo NEXT=$next
''')
        term.wait_for(b'Working: Review debian packages')
        self.assertFalse(termios.tcgetattr(term.slave)[3] & termios.ECHO)
        term.send(b'\x1b[B\x1b[B')
        term.wait_for(b'1/2 |')
        term.send(b'\n')
        out = term.finish()
        self.assertIn('RESPONSE={"ok":true}', out)
        self.assertNotIn('^[[', out)
        # Keys typed during a busy query must not select Beta in the next menu.
        self.assertIn('NEXT=a', out)
        self.assertEqual(term.process.returncode, 0, out)
        self.assertEqual(termios.tcgetattr(term.slave), term.original)

    def test_phase_review_large_brand_centered_info_and_real_output_mode(self):
        term = self.fixture(f'''source "{ROOT}/lib/install_window.sh"
_NT_WINDOW_ACTIVE=1; _NT_WINDOW_INSTALLING=0; _NT_WINDOW_STARTED=$SECONDS
_nt_window_snapshot
_NT_WINDOW_ADDONS='Boot · API · Styling · X11'
_nt_window_draw
_nt_window_stage '5/7 | Managed guest review' 'Review debian before applying'
printf 'REVIEW_BOUNDARY\\n'
_nt_window_run bash -c 'echo FIXTURE_INSTALL_OUTPUT'
echo FRAME_DONE
''', rows=40, columns=90)
        term.wait_for(b'FRAME_DONE')
        out = term.finish()
        before = out.split('REVIEW_BOUNDARY')[0]
        self.assertIn('Review and confirmation', before)
        self.assertNotIn('Installation output', before)
        self.assertNotIn('Installation log', out)
        self.assertIn('█████ █████ ████', out)
        self.assertIn('W o r k s t a t i o n', out)
        self.assertIn('Boot · API · Styling · X11', out)
        self.assertIn('Installation output', out)
        self.assertIn('FIXTURE_INSTALL_OUTPUT', out)
        self.assertEqual(term.process.returncode, 0, out)

    def test_install_event_types_have_distinct_colors(self):
        term = self.fixture(f'''source "{ROOT}/lib/install_window.sh"
_NT_WINDOW_ACTIVE=1; _NT_WINDOW_STARTED=$SECONDS
_nt_window_snapshot; _nt_window_draw
_nt_window_run printf '%s\\n' '[DOWNLOAD] payload' '[UNPACK] payload' '[CONFIGURE] payload' '[WARNING] fixture' '[ERROR] fixture'
echo COLORS_DONE
''')
        term.wait_for(b'COLORS_DONE')
        out = term.finish()
        for code,label in ((81,'DOWNLOAD'),(141,'UNPACK'),(82,'CONFIGURE'),(220,'WARNING'),(203,'ERROR')):
            self.assertIn(f'\x1b[38;5;{code}m[{label}]', out)
        self.assertEqual(term.process.returncode,0,out)

    def test_nested_commands_share_one_terminal_writer(self):
        term = self.fixture(f'''source "{ROOT}/lib/install_window.sh"
_NT_WINDOW_ACTIVE=1; _NT_WINDOW_STARTED=$SECONDS
_nt_window_snapshot; _nt_window_draw
worker() {{ _nt_window_run echo NESTED_ONE; _nt_window_run echo NESTED_TWO; }}
_nt_window_run worker
echo NESTED_DONE
''')
        term.wait_for(b'NESTED_DONE')
        out=term.finish()
        self.assertEqual(out.count('Running: '),1,out)
        self.assertIn('NESTED_ONE',out)
        self.assertIn('NESTED_TWO',out)
        self.assertEqual(term.process.returncode,0,out)

    def test_plan_report_is_read_only_and_space_cannot_select_rows(self):
        term=self.fixture("_nt_pick 'Plan report' view '' 'one|First dependency' 'two|Second dependency'; echo REPORT_RETURNED")
        term.wait_for(b'Read-only')
        term.send(b' \x1b[B \n')
        out=term.finish()
        self.assertIn('REPORT_RETURNED',out)
        self.assertNotIn('[ ]',out)
        self.assertNotIn('[x]',out)
        self.assertNotIn('selected',out)
        self.assertNotIn('Space: select',out)
        self.assertEqual(termios.tcgetattr(term.slave),term.original)

    def test_text_form_escape_restores_terminal(self):
        term = self.fixture('_nt_input "Guest username"; exit $?')
        term.wait_for(b'Guest username')
        term.send(b'\x1b')
        out = term.finish()
        self.assertEqual(term.process.returncode, 130, out)
        self.assertEqual(termios.tcgetattr(term.slave), term.original)

    def test_cancel_and_interrupt_restore_terminal(self):
        for key, expected in ((b'\x1b', 130), (b'\x03', 130)):
            with self.subTest(key=key):
                term = self.fixture('_nt_pick Fixture single "" "a|Alpha"; exit $?')
                term.wait_for(b'1/1 |')
                term.send(key)
                out = term.finish()
                self.assertEqual(term.process.returncode, expected, out)
                self.assertEqual(termios.tcgetattr(term.slave), term.original)
