import os
import fcntl
import pty
import select
import tempfile
import termios
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "tx"


class DistroNamedInstallCLITests(unittest.TestCase):
    def test_debian_install_route_requests_account_before_running_preview(self):
        result = subprocess.run(
            ["bash", str(CLI), "install", "debian"],
            env={**os.environ, "TERMUX_VERSION": "fixture"},
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Choose a Debian Trixie guest account with --user NAME", result.stderr)
        self.assertNotIn("Unknown install option", result.stderr)

    def test_ubuntu_install_route_requests_account_before_running_preview(self):
        result = subprocess.run(
            ["bash", str(CLI), "install", "ubuntu"],
            env={**os.environ, "TERMUX_VERSION": "fixture"},
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Choose a Ubuntu Noble guest account with --user NAME", result.stderr)
        self.assertNotIn("Unknown install option", result.stderr)

    def test_guided_install_applies_the_exact_plan_after_terminal_confirmation(self):
        plan_id = "c" * 64
        with tempfile.TemporaryDirectory(prefix="ternuxx-guided-debian-") as tmp:
            log = Path(tmp) / "calls.log"
            script = '''source "$1"
nt_require_termux() { return 0; }
nt_require_command() { return 0; }
python3() {
  if [[ "$1" == */proot_setup_present.py ]]; then cat; return; fi
  printf '%s\n' "$*" >> "$CALL_LOG"
  case " $* " in
    *" fresh-preview "*) printf '{"status":"preview","plan_id":"%s","operation":{"apply_blocked_reason":null}}\n' "$PLAN_ID" ;;
    *) printf '{"status":"installed"}\n' ;;
  esac
}
nt_cmd_install debian --user sobuj
'''
            master, slave = pty.openpty()
            process = subprocess.Popen(
                ["bash", "-c", script, "bash", str(ROOT / "lib" / "phases.sh")],
                stdin=slave, stdout=slave, stderr=slave,
                env={**os.environ, "CALL_LOG": str(log), "PLAN_ID": plan_id,
                     "TERNUXX_JSON": "0", "TERMUX_VERSION": "fixture"},
                close_fds=True, start_new_session=True,
                preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),
            )
            os.close(slave)
            output = bytearray()
            try:
                while b"Install this exact Debian Trixie plan" not in output:
                    ready, _, _ = select.select([master], [], [], 8)
                    self.assertTrue(ready, "guided install did not reach confirmation")
                    output.extend(os.read(master, 8192))
                os.write(master, b"y\n")
                while process.poll() is None:
                    ready, _, _ = select.select([master], [], [], 8)
                    if ready:
                        try:
                            output.extend(os.read(master, 8192))
                        except OSError:
                            break
            finally:
                os.close(master)
                if process.poll() is None:
                    process.kill()
                    process.wait()
            self.assertEqual(process.returncode, 0, output.decode(errors="replace"))
            calls = log.read_text().splitlines()
            self.assertEqual(len(calls), 2)
            self.assertIn("fresh-preview", calls[0])
            self.assertIn("fresh-install", calls[1])
            self.assertIn(plan_id, calls[1])

    def test_interactive_native_install_confirms_and_applies_without_plan_id_copy(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-guided-native-") as tmp:
            log = Path(tmp) / "calls.log"
            script = '''source "$1"
nt_require_termux() { return 0; }
nt_require_command() { return 0; }
_nt_package_index_fresh() { return 0; }
_nt_choose_install_profile() { _nt_select_install_profile minimal-native; }
_nt_make_install_plan() {
  _NT_PLAN_PACKAGES=(python)
  _NT_PLAN_VERSIONS=(python=3.14.8)
  _NT_PLAN_TRANSACTION=(python=3.14.8)
  _NT_PLAN_SIMULATION='Inst python (3.14.8 termux-main stable/main [aarch64])'
  _NT_PLAN_RESOURCE_ESTIMATES='{"schema_version":1,"complete":true,"download_bytes":100,"installed_kib":200,"packages":[]}'
}
_nt_print_install_resource_estimates() { :; }
_nt_write_install_record() { printf 'record:%s\n' "$1" >> "$CALL_LOG"; }
_nt_compute_plan_id() { printf '%s\n' "$PLAN_ID"; }
_nt_reviewed_preview_matches() { test "$1" = "$PLAN_ID"; }
_nt_install_capacity_preflight() { return 0; }
_nt_apply_install_transaction() { printf 'apply\n' >> "$CALL_LOG"; }
_nt_offer_managed_guest() { printf 'guest-offer\n' >> "$CALL_LOG"; }
nt_cmd_install interactive
'''
            master, slave = pty.openpty()
            process = subprocess.Popen(
                ["bash", "-c", script, "bash", str(ROOT / "lib" / "phases.sh")],
                stdin=slave, stdout=slave, stderr=slave,
                env={**os.environ, "CALL_LOG": str(log), "PLAN_ID": "d" * 64,
                     "TERNUXX_JSON": "0", "TERMUX_VERSION": "fixture"},
                close_fds=True, start_new_session=True,
                preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),
            )
            os.close(slave)
            output = bytearray()
            try:
                while b"Install this Native workstation profile now?" not in output:
                    ready, _, _ = select.select([master], [], [], 8)
                    self.assertTrue(ready, "guided Native install did not reach confirmation")
                    output.extend(os.read(master, 8192))
                os.write(master, b"y\n")
                while process.poll() is None:
                    ready, _, _ = select.select([master], [], [], 8)
                    if ready:
                        try:
                            output.extend(os.read(master, 8192))
                        except OSError:
                            break
            finally:
                os.close(master)
                if process.poll() is None:
                    process.kill()
                    process.wait()
            self.assertEqual(process.returncode, 0, output.decode(errors="replace"))
            rendered = output.decode(errors="replace")
            self.assertIn("Native preview: minimal-native", rendered)
            self.assertNotIn("--plan-id", rendered)
            self.assertEqual(log.read_text().splitlines(), ["record:preview", "record:applying", "apply", "record:applied", "guest-offer"])

    def test_unknown_generic_guest_route_is_rejected_before_package_probes(self):
        env = {
            **os.environ,
            "TERMUX_VERSION": "fixture",
            "PREFIX": "/tmp/ternuxx-no-guest-install",
            "HOME": "/tmp/ternuxx-no-guest-install-home",
        }
        result = subprocess.run(
            ["bash", str(CLI), "install", "proot", "preview"],
            env=env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown install option", result.stderr)
        self.assertNotIn("proot_setup_present", result.stderr)


if __name__ == "__main__":
    unittest.main()
