from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProotGuiRoutingTests(unittest.TestCase):
    def test_status_reports_stopped_when_no_managed_session_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ternuxx-proot-status-") as temp:
            home = Path(temp)
            env = {**os.environ, "HOME": str(home), "PREFIX": str(home / "prefix"),
                   "TMPDIR": str(home / "tmp")}
            result = subprocess.run(["bash", str(ROOT / "scripts/proot-gui0.sh"), "status"],
                                    capture_output=True, text=True, env=env, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Standalone Debian GUI: stopped; target display :0", result.stdout)
            self.assertIn("Nested display :2 socket is absent.", result.stdout)

    def test_live_status_and_start_copy_distinguish_session_liveness_from_desktop_readiness(self) -> None:
        script = (ROOT / "scripts/proot-gui0.sh").read_text(encoding="utf-8")
        self.assertIn("process group live on %s; desktop shell/panel readiness not checked", script)
        self.assertIn("session processes are live on standalone display :0", script)
        self.assertIn("Desktop shell/panel readiness and Android visibility are not verified", script)

    def test_guest_desktop_launchers_drop_the_native_termux_path(self) -> None:
        expected = "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        for path in (ROOT / "scripts/proot-gui0.sh", ROOT / "lib/proot-xfce-wrapper.sh"):
            with self.subTest(path=path.name):
                self.assertIn(expected, path.read_text(encoding="utf-8"))

    def test_nested_route_matches_native_orientation_and_resizes(self) -> None:
        script = (ROOT / "scripts/proot-gui0.sh").read_text(encoding="utf-8")
        self.assertIn('query_display_geometry(os.environ["DISPLAY"])', script)
        self.assertIn('/usr/bin/Xephyr :2 -glamor_gles2 -screen "$native_geometry" -resizeable', script)
        self.assertIn('--env TERNUXX_REPO_ROOT="$ROOT"', script)
        self.assertIn('gnome) desktop_argv=(gnome-session --session=gnome-xorg)', script)
        self.assertIn('plasma) desktop_argv=(startplasma-x11); export XDG_CURRENT_DESKTOP=KDE XDG_SESSION_DESKTOP=KDE DESKTOP_SESSION=plasma KWIN_COMPOSE=N', script)
        self.assertIn('cinnamon) desktop_argv=(cinnamon-session)', script)
        self.assertIn('DISPLAY=:2 dbus-launch --exit-with-session "${desktop_argv[@]}" &', script)
        self.assertIn('dbus-daemon --session --address="$system_bus_address" --nofork', script)
        self.assertIn('export DBUS_SYSTEM_BUS_ADDRESS="$system_bus_address"', script)
        self.assertIn('trap cleanup EXIT', script)
        self.assertIn('rm -f -- "$system_bus_dir/bus"', script)
        self.assertIn('rmdir "$system_bus_dir" 2>/dev/null || true', script)
        self.assertIn('export XDG_SESSION_TYPE=x11', script)
        self.assertIn('cinnamon) desktop_argv=(cinnamon-session); export XDG_CURRENT_DESKTOP=X-Cinnamon', script)
        self.assertIn('env -u DBUS_SYSTEM_BUS_ADDRESS -u DBUS_SESSION_BUS_ADDRESS', script)
        self.assertIn('--desktop) [ "$#" -ge 2 ]', script)
        self.assertIn('DISPLAY=:2 es2_info 2>&1 | sed', script)
        self.assertIn('Use Termux:X11 fullscreen/orientation controls', script)

    def test_nested_route_starts_xfce_session_on_existing_xephyr_server(self) -> None:
        script = (ROOT / "scripts/proot-gui0.sh").read_text(encoding="utf-8")
        self.assertIn("/usr/bin/Xephyr :2 -glamor_gles2 -screen", script)
        self.assertIn('gnome) desktop_argv=(gnome-session --session=gnome-xorg)', script)
        self.assertIn('plasma) desktop_argv=(startplasma-x11)', script)
        self.assertIn('cinnamon) desktop_argv=(cinnamon-session)', script)
        self.assertIn('DISPLAY=:2 dbus-launch --exit-with-session "${desktop_argv[@]}" &', script)
        self.assertIn('--desktop) [ "$#" -ge 2 ]', script)

    def test_nested_route_refuses_an_unverified_display_before_guest_side_effects(self) -> None:
        script = (ROOT / "scripts/proot-gui0.sh").read_text(encoding="utf-8")
        preflight = script.index('nested_display_state="$(python3 "$DISPLAY_TOOL" "$TMP_ROOT" 2')
        guest_check = script.index('resolve_proot_guest_shell', preflight)
        audio_start = script.index('"$ROOT/tx" audio start', preflight)
        self.assertLess(preflight, guest_check)
        self.assertLess(preflight, audio_start)
        self.assertIn('refusing startup because existing display ownership cannot be verified', script)
        self.assertIn('recover-proot "$TMP_ROOT" 2 "$PREFIX/var/lib/proot-distro/containers/debian/rootfs"', script)
        self.assertIn('nested_recovery" = recovered', script)

    def test_standalone_supervisor_is_detached_from_terminal_lifecycle(self) -> None:
        script = (ROOT / "scripts/proot-gui0.sh").read_text(encoding="utf-8")
        self.assertIn('nohup setsid env TERNUXX_PULSE_COOKIE="$cookie" TERNUXX_DESKTOP_ID="$DESKTOP_ID"', script)

    def test_standalone_desktop_gets_private_system_bus_and_session_identity(self) -> None:
        wrapper = (ROOT / "lib/proot-xfce-wrapper.sh").read_text(encoding="utf-8")
        self.assertIn('dbus-daemon --session --address="$system_bus_address" --nofork', wrapper)
        self.assertIn('export DBUS_SYSTEM_BUS_ADDRESS="$system_bus_address"', wrapper)
        self.assertIn('export XDG_SESSION_TYPE=x11', wrapper)
        self.assertIn('cinnamon) desktop_argv=(cinnamon-session); export XDG_CURRENT_DESKTOP=X-Cinnamon', wrapper)
        self.assertIn('-u DBUS_SYSTEM_BUS_ADDRESS', wrapper)
        self.assertIn('Ternuxx PRoot guest launcher entered', wrapper)
        self.assertIn('Ternuxx PRoot desktop command exited', wrapper)
        self.assertIn('Ternuxx PRoot host launcher', wrapper)
        self.assertIn('rm -f -- "$system_bus_dir/bus"', wrapper)
        payload = wrapper.split("/bin/bash -c '", 1)[1].split("\n  ')\nexec env", 1)[0]
        self.assertIn('trap "exit 130" INT', payload)
        self.assertIn('trap "exit 143" TERM', payload)
        self.assertNotIn("trap 'exit", payload)

    def test_debian_xfce_gets_cpu_model_names_from_native_lscpu(self) -> None:
        wrapper = (ROOT / "lib/proot-xfce-wrapper.sh").read_text(encoding="utf-8")
        self.assertIn('proot_cpuinfo.py" "$CPUINFO_PATH"', wrapper)
        self.assertIn('--bind "$CPUINFO_PATH:/proc/cpuinfo"', wrapper)

    def test_standalone_app_launcher_binds_the_cpu_model_name_view(self) -> None:
        wrapper = (ROOT / "scripts/proot-x11-app.sh").read_text(encoding="utf-8")
        self.assertIn('proot_cpuinfo.py" "$CPUINFO_PATH"', wrapper)
        self.assertIn('--bind "$CPUINFO_PATH:/proc/cpuinfo"', wrapper)
        self.assertIn('"$pgui_provider" = proot', wrapper)

    def test_guest_graphics_verification_requires_running_display_and_limits_claims(self) -> None:
        script = (ROOT / "scripts/proot-gui0.sh").read_text(encoding="utf-8")
        self.assertIn('Usage: tx pgui graphics verify', script)
        self.assertIn('d.get("state")!="running" or d.get("display")!=":0"', script)
        self.assertIn('es2_info 2>&1', script)
        self.assertIn('glxinfo -B 2>&1', script)
        self.assertIn('vulkaninfo --summary 2>&1', script)
        self.assertIn('do not prove frame presentation or inference offload', script)

    def test_invalid_mode_is_rejected_before_state_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ternuxx-shared-gui-") as temp:
            home = Path(temp)
            env = {**os.environ, "HOME": str(home), "PREFIX": str(home / "prefix"),
                   "TMPDIR": str(home / "tmp")}
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/proot-gui0.sh"), "start", "--mode", "unsupported"],
                capture_output=True, text=True, env=env, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--mode must be auto, standalone, or nested", result.stderr)
            self.assertFalse((home / ".local/share/ternuxx").exists())

    def test_nested_gui_creates_each_private_xdg_directory_before_chmod(self):
        source = (ROOT / "scripts/proot-gui0.sh").read_text(encoding="utf-8")
        self.assertIn('mkdir -p "$state" "$state/config" "$state/cache" "$state/data" "$state/runtime"', source)
        self.assertIn('chmod 700 "$state" "$state/config" "$state/cache" "$state/data" "$state/runtime"', source)

if __name__ == "__main__":
    unittest.main()
