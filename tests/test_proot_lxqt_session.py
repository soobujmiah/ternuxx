from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "lib/proot-lxqt-session.sh"


class ProotLxqtSessionDefaultsTests(unittest.TestCase):
    def run_helper(self, config_home: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", 'source "$1"; nt_proot_lxqt_session_defaults "$2"',
             "test", str(HELPER), str(config_home)],
            capture_output=True, text=True, check=False, timeout=10)

    def test_missing_lxqt_config_gets_non_compositing_openbox_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_home = Path(temp) / "config"
            result = self.run_helper(config_home)
            self.assertEqual(result.returncode, 0, result.stderr)
            session = config_home / "lxqt/session.conf"
            self.assertEqual(session.read_text(),
                             "[General]\n__userfile__=true\nwindow_manager=openbox\n")
            self.assertEqual(session.stat().st_mode & 0o777, 0o600)

    def test_existing_user_lxqt_preferences_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_home = Path(temp) / "config"
            session = config_home / "lxqt/session.conf"
            session.parent.mkdir(parents=True)
            original = "[General]\n__userfile__=true\nwindow_manager=kwin\n"
            session.write_text(original)
            result = self.run_helper(config_home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(session.read_text(), original)

    def test_symlinked_session_config_is_refused_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_home = Path(temp) / "config"
            lxqt = config_home / "lxqt"
            lxqt.mkdir(parents=True)
            target = Path(temp) / "target.conf"
            target.write_text("owner config\n")
            (lxqt / "session.conf").symlink_to(target)
            result = self.run_helper(config_home)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(), "owner config\n")

    def test_relative_config_home_is_refused(self) -> None:
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; nt_proot_lxqt_session_defaults relative',
             "test", str(HELPER)],
            capture_output=True, text=True, check=False, timeout=10)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
