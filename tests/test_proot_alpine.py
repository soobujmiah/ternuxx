from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_alpine


class AlpineCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-alpine-compat-")
        self.rootfs = Path(self.temp.name) / "rootfs"
        (self.rootfs / "usr/local/bin").mkdir(parents=True)
        (self.rootfs / "usr/libexec/glycin-loaders/2+").mkdir(parents=True)
        self.loader = self.rootfs / "usr/libexec/glycin-loaders/2+/glycin-image-rs"
        self.loader.write_text('''#!/bin/sh
printf '%s\\n' "$HOME" "$XDG_RUNTIME_DIR" "$*"
''')
        self.loader.chmod(0o755)
        self.shim = proot_alpine.install_glycin_bwrap_shim(self.rootfs)

    def tearDown(self):
        self.temp.cleanup()

    def test_shim_skips_proot_incompatible_sandbox_for_only_glycin_loader(self):
        test_shim = Path(self.temp.name) / "bwrap-test"
        source = self.shim.read_text().replace(
            "/usr/libexec/glycin-loaders/2+/glycin-*",
            str(self.rootfs / "usr/libexec/glycin-loaders/2+" / "glycin-*")
        )
        test_shim.write_text(source)
        test_shim.chmod(0o755)
        result = subprocess.run([
            str(test_shim), "--unshare-all", "--die-with-parent", "--chdir", "/",
            "--ro-bind", "/usr", "/usr", "--dev", "/dev", "--tmpfs", "/tmp-home",
            "--tmpfs", "/tmp-run", "--clearenv", "--setenv", "HOME", "/tmp-home",
            "--setenv", "XDG_RUNTIME_DIR", "/tmp-run", "--seccomp", "20",
            str(self.loader), "--dbus-fd", "9",
        ], check=False, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["/tmp-home", "/tmp-run", "--dbus-fd 9"])

    def test_shim_refuses_non_glycin_commands_and_unknown_options(self):
        self.assertEqual(subprocess.run(
            [str(self.shim), "--unshare-all", "/usr/bin/true"], check=False).returncode, 125)
        self.assertEqual(subprocess.run(
            [str(self.shim), "--unknown-option", "/usr/libexec/glycin-loaders/2+/glycin-image-rs"],
            check=False).returncode, 125)

    def test_install_is_idempotent_for_its_own_shim(self):
        self.assertEqual(proot_alpine.install_glycin_bwrap_shim(self.rootfs), self.shim)

    def test_install_refuses_to_replace_custom_guest_bwrap_path(self):
        self.shim.write_text("#!/bin/sh\nexit 1\n")
        with self.assertRaisesRegex(ValueError, "already exists"):
            proot_alpine.install_glycin_bwrap_shim(self.rootfs)

    def test_install_refuses_symlinked_local_bin(self):
        temp = Path(self.temp.name) / "unsafe"
        (temp / "usr/local").mkdir(parents=True)
        (temp / "usr/local/bin").symlink_to("/tmp", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            proot_alpine.install_glycin_bwrap_shim(temp)


if __name__ == "__main__":
    unittest.main()
