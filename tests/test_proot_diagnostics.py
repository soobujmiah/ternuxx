"""Tests for bounded, read-only PRoot distribution discovery."""

from __future__ import annotations

from types import SimpleNamespace
import json
import os
import stat
import subprocess
import tempfile
import sys
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_diagnostics  # noqa: E402
import proot_fresh_setup  # noqa: E402


class ProotDiagnosticsTests(unittest.TestCase):
    def _rootfs_fixture(self, base: Path, passwd: str) -> Path:
        root = base / "prefix" / "var/lib/proot-distro/containers/debian/rootfs"
        (root / "etc").mkdir(parents=True)
        (root / "etc/passwd").write_text(passwd)
        return base / "prefix"

    def test_resolves_account_from_long_receipt_scoped_replay_alias(self):
        alias = "ternuxx-replay-cleanroom-20261026"
        with tempfile.TemporaryDirectory(prefix="ternuxx-replay-account-") as temporary:
            prefix = Path(temporary)
            root = prefix / "var/lib/proot-distro/containers" / alias / "rootfs"
            (root / "etc").mkdir(parents=True)
            (root / "etc/passwd").write_text(
                "root:x:0:0:root:/root:/bin/bash\nsobuj:x:1000:1000:Sobuj:/home/sobuj:/bin/bash\n",
                encoding="utf-8",
            )
            self.assertEqual(proot_diagnostics.resolve_proot_guest_user(distro=alias, prefix=str(prefix)), "sobuj")

    def test_resolves_unique_regular_guest_account_from_rootfs_without_ternux(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-rootfs-user-") as temp:
            prefix = self._rootfs_fixture(Path(temp),
                "root:x:0:0:root:/root:/bin/bash\n"
                "sbj:x:1000:1000:Owner:/home/sbj:/bin/bash\n"
                "nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n")
            self.assertEqual(proot_diagnostics.resolve_proot_guest_user(
                distro="debian", prefix=str(prefix)), "sbj")

    def test_resolves_selected_guest_login_shell_without_entering_rootfs(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-rootfs-shell-") as temp:
            prefix = self._rootfs_fixture(Path(temp),
                "root:x:0:0:root:/root:/bin/bash\n"
                "sbj:x:1000:1000:Owner:/home/sbj:/usr/bin/zsh\n")
            self.assertEqual(proot_diagnostics.resolve_proot_guest_shell(
                distro="debian", user="sbj", prefix=str(prefix)), "/usr/bin/zsh")
            self.assertEqual(proot_diagnostics.resolve_proot_guest_shell(
                distro="debian", user="root", prefix=str(prefix)), "/bin/bash")

    def test_guest_login_shell_resolution_rejects_unsafe_or_ambiguous_entries(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-rootfs-shell-") as temp:
            prefix = self._rootfs_fixture(Path(temp),
                "root:x:0:0:root:/root:/bin/bash\n"
                "sbj:x:1000:1000:Owner:/home/sbj:/bin/bash;touch\n")
            with self.assertRaisesRegex(proot_diagnostics.GuestProfileError, "unavailable or ambiguous"):
                proot_diagnostics.resolve_proot_guest_shell(
                    distro="debian", user="sbj", prefix=str(prefix))
            passwd = prefix / "var/lib/proot-distro/containers/debian/rootfs/etc/passwd"
            passwd.write_text("root:x:0:0:root:/root:/bin/bash\n"
                              "sbj:x:1000:1000:Owner:/home/sbj:/bin/bash\n"
                              "sbj:x:1001:1001:Duplicate:/home/sbj:/bin/zsh\n")
            with self.assertRaisesRegex(proot_diagnostics.GuestProfileError, "unavailable or ambiguous"):
                proot_diagnostics.resolve_proot_guest_shell(
                    distro="debian", user="sbj", prefix=str(prefix))
            with self.assertRaisesRegex(proot_diagnostics.GuestProfileError, "invalid"):
                proot_diagnostics.resolve_proot_guest_shell(
                    distro="debian", user="../sbj", prefix=str(prefix))

    def test_guest_user_resolution_rejects_ambiguous_or_unsafe_rootfs(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-rootfs-user-") as temp:
            prefix = self._rootfs_fixture(Path(temp),
                "one:x:1000:1000:One:/home/one:/bin/bash\n"
                "two:x:1001:1001:Two:/home/two:/bin/bash\n")
            with self.assertRaisesRegex(proot_diagnostics.GuestProfileError, "ambiguous"):
                proot_diagnostics.resolve_proot_guest_user(distro="debian", prefix=str(prefix))
            with self.assertRaises(proot_diagnostics.GuestProfileError):
                proot_diagnostics.resolve_proot_guest_user(distro="../debian", prefix=str(prefix))
            passwd = prefix / "var/lib/proot-distro/containers/debian/rootfs/etc/passwd"
            passwd.unlink()
            passwd.symlink_to(Path(temp) / "outside")
            with self.assertRaisesRegex(proot_diagnostics.GuestProfileError, "identity"):
                proot_diagnostics.resolve_proot_guest_user(distro="debian", prefix=str(prefix))

    def test_host_proot_process_observation_reports_candidate_without_ownership(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-proc-") as temp:
            root = Path(temp)
            proc = root / "4242"
            proc.mkdir()
            (proc / "comm").write_text("proot\n")
            (proc / "cmdline").write_bytes(b"/prefix/bin/proot\0--rootfs=.\0/bin/bash\0")
            (proc / "status").write_text("Name:\tproot\nPPid:\t41\n")
            other = root / "4243"
            other.mkdir()
            (other / "comm").write_text("bash\n")
            (other / "cmdline").write_bytes(b"/bin/bash\0")
            report = proot_diagnostics.inspect_host_proot_processes(proc_root=root)
        self.assertEqual(report, {"status": "observed", "visibility": "complete",
            "ownership": "unverified", "processes": [
                {"pid": 4242, "parent_pid": 41, "association": "unverified"}]})

    def test_host_proot_observation_handles_empty_and_unreadable_proc(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-proc-") as temp:
            root = Path(temp)
            self.assertEqual(proot_diagnostics.inspect_host_proot_processes(proc_root=root),
                {"status": "none", "visibility": "complete", "ownership": "unverified", "processes": []})
        missing = proot_diagnostics.inspect_host_proot_processes(proc_root="/path/not/present")
        self.assertEqual(missing["status"], "unknown")
        self.assertEqual(missing["visibility"], "unavailable")

    def test_parses_installed_names_and_never_enters_guest(self):
        calls = []
        output = "Installed containers:\n  \x1b[32m* \x1b[0mDebian\nLog in with: proot-distro login <name>\n"
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout=output)
        report = proot_diagnostics.inspect_installed(
            which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
            runner=runner,
        )
        self.assertEqual(report["status"], "installed")
        self.assertEqual(report["installed_distributions"], ["debian"])
        self.assertEqual(report["ownership"], "unverified")
        self.assertEqual(report["host_proot_processes"]["ownership"], "unverified")
        self.assertFalse(report["guest_entered"])
        self.assertTrue(report["read_only"])
        self.assertEqual(calls[0][0], ["/prefix/bin/proot-distro", "list"])
        self.assertIs(calls[0][1]["stderr"], subprocess.STDOUT)

    def test_current_proot_distro_empty_inventory_message_is_recognized(self):
        output = "\nNo containers are installed.\n\nInstall one with: proot-distro install ubuntu:24.04\n"
        report = proot_diagnostics.inspect_installed(
            which=lambda _name: "/prefix/bin/proot-distro",
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=output),
        )
        self.assertEqual(report["status"], "none")
        self.assertEqual(report["installed_distributions"], [])
        self.assertTrue(report["manager_available"])

    def test_empty_inventory_is_distinct_from_query_failure(self):
        report = proot_diagnostics.inspect_installed(
            which=lambda _name: "/prefix/bin/proot-distro",
            runner=lambda *_args, **_kwargs: SimpleNamespace(
                returncode=0, stdout="Installed containers:\nLog in with: proot-distro login <name>\n"),
        )
        self.assertEqual(report["status"], "none")
        self.assertEqual(report["installed_distributions"], [])

    def test_all_inventory_outcomes_match_strict_response_schema(self):
        schema = json.loads((ROOT / "schemas/proot-distribution-inventory.schema.json").read_text())
        expected = set(schema["properties"])
        reports = [
            proot_diagnostics.inspect_installed(which=lambda _name: None),
            proot_diagnostics.inspect_installed(
                which=lambda _name: "/prefix/bin/proot-distro",
                runner=lambda *_args, **_kwargs: SimpleNamespace(
                    returncode=0, stdout="Installed containers:\nLog in with: proot-distro login <name>\n")),
            proot_diagnostics.inspect_installed(
                which=lambda _name: "/prefix/bin/proot-distro",
                runner=lambda *_args, **_kwargs: SimpleNamespace(
                    returncode=0, stdout="Installed containers:\n * Debian\nLog in with: proot-distro login <name>\n")),
            proot_diagnostics.inspect_installed(
                which=lambda _name: "/prefix/bin/proot-distro",
                runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("proot-distro", 5))),
        ]
        for report in reports:
            self.assertEqual(set(report), expected)
            self.assertEqual(report["component"], schema["properties"]["component"]["const"])
            self.assertIn(report["status"], schema["properties"]["status"]["enum"])
            self.assertEqual(report["ownership"], "unverified")
            self.assertIs(report["guest_entered"], False)
            self.assertIs(report["read_only"], True)
            self.assertIsInstance(report["manager_available"], bool)
            self.assertIsInstance(report["installed_distributions"], list)
            self.assertEqual(report["installed_distributions"], sorted(set(report["installed_distributions"])))

    def test_ubuntu_guest_requires_matching_managed_receipt_and_rootfs_identity(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-ubuntu-receipt-") as temporary:
            base = Path(temporary)
            home = base / "home"
            home.mkdir()
            state = home / ".local/share/ternuxx"
            state.mkdir(parents=True, mode=0o700)
            state.chmod(0o700)
            setup_state = state / "proot-setup"
            (setup_state / "previews").mkdir(parents=True, mode=0o700)
            setup_state.chmod(0o700)
            prefix = base / "prefix"
            container = prefix / "var/lib/proot-distro/containers/ubuntu"
            root = container / "rootfs"
            (root / "etc").mkdir(parents=True)
            identity = proot_fresh_setup._root_identity(container, root)
            receipt = {"schema_version": 1, "alias": "ubuntu", "plan_id": "d" * 64,
                       "rootfs_identity": identity, "package_versions_recorded": True,
                       "requested_packages_verified_installed": True, "guest_user": "sobuj",
                       "release": "Ubuntu 24.04 LTS (Noble)", "profile_id": "ubuntu-noble"}
            receipt_path = setup_state / "fresh-provider-ubuntu.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            receipt_path.chmod(0o600)
            report = proot_diagnostics.verify_managed_guest_alias(
                "ubuntu", str(prefix), home=str(home), state_dir=str(state))
            self.assertEqual(report["alias"], "ubuntu")
            self.assertEqual(report["profile_id"], "ubuntu-noble")
            receipt["profile_id"] = "ternuxx-debian-trixie-workstation"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact, valid Ternuxx install receipt"):
                proot_diagnostics.verify_managed_guest_alias(
                    "ubuntu", str(prefix), home=str(home), state_dir=str(state))

    def test_resolves_ubuntu_user_from_the_install_receipt(self):
        with mock.patch.object(proot_diagnostics, "verify_managed_guest_alias",
                               return_value={"guest_user": "sobuj"}):
            self.assertEqual(proot_diagnostics.resolve_proot_guest_user(
                distro="ubuntu", prefix="/prefix"), "sobuj")

    def test_receipt_verified_replay_guest_can_run_the_same_readonly_graphics_probe(self):
        alias = "ternuxx-replay-cleanroom-20261026"
        with tempfile.TemporaryDirectory(prefix="ternuxx-replay-probe-") as temporary:
            base = Path(temporary)
            home = base / "home"
            home.mkdir()
            state = home / ".local/share/ternuxx"
            state.mkdir(parents=True, mode=0o700)
            state.chmod(0o700)
            setup_state = state / "proot-setup"
            (setup_state / "previews").mkdir(parents=True, mode=0o700)
            setup_state.chmod(0o700)
            prefix = base / "prefix"
            containers = prefix / "var/lib/proot-distro/containers"
            container = containers / alias
            root = container / "rootfs"
            (root / "etc").mkdir(parents=True)
            external_release = base / "external-os-release"
            external_release.write_text("ID=ubuntu\nVERSION_CODENAME=noble\n", encoding="utf-8")
            (root / "etc/os-release").symlink_to(external_release)
            unreceipted = containers / "ternuxx-replay-unreceipted" / "rootfs"
            (unreceipted / "etc").mkdir(parents=True)
            (unreceipted / "etc/os-release").write_text("ID=debian\nVERSION_CODENAME=trixie\n", encoding="utf-8")
            identity = proot_fresh_setup._root_identity(container, root)
            receipt = {"schema_version": 1, "alias": alias, "plan_id": "a" * 64,
                       "rootfs_identity": identity, "package_versions_recorded": True,
                       "requested_packages_verified_installed": True, "release": "Debian Trixie"}
            receipt_path = setup_state / f"fresh-provider-{alias}.json"
            receipt_path.write_text(json.dumps(receipt))
            receipt_path.chmod(0o600)
            outputs = [
                SimpleNamespace(returncode=0, stdout="Installed containers:\n * Debian\nLog in with: proot-distro login <name>\n"),
                SimpleNamespace(returncode=0, stdout="Display: :1\nX11: reachable\nRenderer: zink Vulkan (Turnip)\nGLX draw: verified\nGLX draw frames: 10\nGLX draw renderer: zink Turnip\nVulkan draw: verified\nVulkan draw device: Adreno 825\n"),
            ]
            calls = []
            def runner(args, **kwargs):
                calls.append((args, kwargs))
                return outputs.pop(0)
            inventory = proot_diagnostics.inspect_installed(
                prefix=str(prefix), home=str(home), state_dir=str(state),
                which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
                runner=lambda *_args, **_kwargs: SimpleNamespace(
                    returncode=0, stdout="Installed containers:\n * Debian\nLog in with: proot-distro login <name>\n"),
            )
            self.assertEqual(inventory["installed_distributions"], ["debian", alias])
            schema = json.loads((ROOT / "schemas/proot-distribution-inventory.schema.json").read_text())
            alias_pattern = schema["properties"]["installed_distributions"]["items"]["pattern"]
            self.assertRegex(alias, alias_pattern)
            self.assertFalse(inventory["guest_entered"])
            with mock.patch.object(proot_diagnostics.Path, "home", return_value=home), \
                 mock.patch.dict(os.environ, {"TERNUXX_STATE_DIR": str(state)}), \
                 mock.patch.object(proot_diagnostics, "_native_pulse_cookie_path", return_value=None):
                report = proot_diagnostics.verify_proot_guest(
                    distro=alias, user="sbj", display=":1", backend="zink",
                    prefix=str(prefix),
                    which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
                    runner=runner)
            self.assertEqual(report["distro"], alias)
            self.assertEqual(report["status"], "partial")
            self.assertIn(alias, calls[1][0])
            self.assertEqual(calls[0][0], ["/prefix/bin/proot-distro", "list"])

    def test_replay_graphics_probe_rejects_missing_or_replaced_receipt_rootfs(self):
        with self.assertRaisesRegex(ValueError, "valid Ternuxx install receipt"):
            proot_diagnostics.verify_proot_guest(
                distro="ternuxx-replay-missing", user="sbj", display=":1", backend="zink",
                prefix="/nonexistent/prefix", which=lambda _name: self.fail("must fail before probing"))

    def test_proot_guest_verify_uses_fixed_readonly_probe_and_no_ternux_cli(self):
        calls = []
        outputs = [
            SimpleNamespace(returncode=0, stdout="Installed containers:\n * Debian\nLog in with: proot-distro login <name>\n"),
            SimpleNamespace(returncode=0, stdout="Display: :1\nX11: reachable\nAudio: PulseAudio reachable\nRenderer: zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))\nGLX draw: verified\nGLX draw frames: 214\nGLX draw renderer: zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))\nVulkan draw: verified\nVulkan draw device: Adreno (TM) 825\n"),
        ]
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return outputs.pop(0)
        with mock.patch.object(proot_diagnostics, "_native_pulse_cookie_path",
                               return_value=Path("/native/private/pulse-cookie")):
            report = proot_diagnostics.verify_proot_guest(
                distro="debian", user="sbj", display=":1", backend="zink",
                which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
                runner=runner,
            )
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["component"], "proot_guest_diagnostics")
        self.assertTrue(report["guest_entered"])
        self.assertEqual(len(calls), 2)
        command = calls[1][0]
        self.assertIn("--isolated", command)
        self.assertNotIn("--shared-tmp", command)
        self.assertIn("/data/data/com.termux/files/usr/tmp/.X11-unix:/tmp/.X11-unix", command)
        self.assertIn("/dev/kgsl-3d0:/dev/kgsl", command)
        self.assertIn("DISPLAY=:1", command)
        self.assertIn("PULSE_SERVER=tcp:127.0.0.1:4713", command)
        self.assertIn("MESA_SHADER_CACHE_DISABLE=true", command)
        self.assertEqual(command[-3], "/bin/sh")
        self.assertEqual(command[-2], "-c")
        self.assertIn("glxinfo -B", command[-1])
        self.assertIn("glxgears -info -geometry 180x100", command[-1])
        self.assertIn("xdpyinfo -display", command[-1])
        self.assertIn("-queryExtensions", command[-1])
        self.assertIn("timeout -s TERM 7s", command[-1])
        self.assertEqual(report["checks"]["glx_draw"], "verified")
        self.assertEqual(report["checks"]["glx_draw_frames"], 214)
        self.assertIn("zink Vulkan", report["checks"]["glx_draw_renderer"])
        self.assertEqual(report["checks"]["vulkan_draw"], "verified")
        self.assertIn("Adreno (TM) 825", report["checks"]["vulkan_draw_device"])
        self.assertFalse(any(item == "ternux" or item.endswith("/ternux") for item in command))
        self.assertIn("/native/private/pulse-cookie:/tmp/.ternuxx-pulse-cookie", command)
        self.assertIn("PULSE_COOKIE=/tmp/.ternuxx-pulse-cookie", command)
        self.assertFalse(report["read_only"])
        self.assertTrue(report["probe_payload_read_only"])
        self.assertTrue(report["safety"]["launcher_profile_write_possible"])
        self.assertTrue(report["safety"]["host_home_and_shared_storage_unbound"])
        self.assertTrue(all(value is False for key, value in report["safety"].items()
                            if key not in {"host_home_and_shared_storage_unbound", "launcher_profile_write_possible"}))

    def test_nested_gles_context_does_not_claim_glx_or_draw_success(self):
        outputs = [
            "Installed containers:\n * Debian\n",
            "Display: :2\nX11: reachable\nAudio: PulseAudio reachable\n"
            "Renderer: unavailable\nGLES context: verified\n"
            "GLES renderer: zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))\n"
            "GLES version: OpenGL ES 3.2 Mesa\nDRI3 extension: unavailable\n"
            "Vulkan draw: verified\nVulkan draw device: Adreno (TM) 825\n",
        ]
        def runner(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=outputs.pop(0))
        report = proot_diagnostics.verify_proot_guest(
            distro="debian", user="sbj", display=":2", backend="zink",
            which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
            runner=runner,
        )
        self.assertEqual(report["status"], "partial")
        checks = report["checks"]
        self.assertEqual(checks["x11"], "reachable")
        self.assertEqual(checks["renderer_class"], "unavailable")
        self.assertIsNone(checks["renderer"])
        self.assertEqual(checks["gles_context"], "verified")
        self.assertIn("zink Vulkan", checks["gles_renderer"])
        self.assertEqual(checks["gles_version"], "OpenGL ES 3.2 Mesa")
        self.assertFalse(checks["gles_draw_verified"])
        self.assertEqual(checks["dri3_extension"], "unavailable")
        self.assertEqual(checks["glx_draw"], "unknown")
        self.assertEqual(checks["glx_draw_frames"], 0)
        self.assertIsNone(checks["glx_draw_renderer"])
        self.assertTrue(any("GLX renderer unavailable" in blocker for blocker in report["blockers"]))
        self.assertEqual(checks["vulkan_draw"], "verified")

    def test_vulkan_context_is_not_a_draw_without_successful_adreno_workload(self):
        outputs = [
            SimpleNamespace(returncode=0, stdout="Installed containers:\n * Debian\n"),
            SimpleNamespace(returncode=0, stdout=(
                "Display: :2\nX11: reachable\nAudio: PulseAudio reachable\n"
                "Renderer: unavailable\nGLES context: verified\n"
                "GLES renderer: zink Vulkan 1.4 (Adreno 825)\nGLES version: OpenGL ES 3.2\n"
                "Vulkan draw: failed\nVulkan draw device: unavailable\n")),
        ]
        report = proot_diagnostics.verify_proot_guest(
            distro="debian", user="sbj", display=":2", backend="zink",
            which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
            runner=lambda *_args, **_kwargs: outputs.pop(0),
        )
        self.assertEqual(report["checks"]["gles_context"], "verified")
        self.assertEqual(report["checks"]["vulkan_draw"], "failed")
        self.assertIn("bounded Vulkan draw did not verify", " ".join(report["blockers"]))
        self.assertNotEqual(report["status"], "complete")

    def test_glx_draw_requires_frames_and_the_requested_renderer(self):
        outputs = [
            "Installed containers:\n * Debian\n",
            "Display: :1\nX11: reachable\nAudio: PulseAudio reachable\n"
            "Renderer: zink Vulkan (Adreno 825)\nGLX draw: verified\n"
            "GLX draw frames: 214\nGLX draw renderer: llvmpipe (LLVM fixture)\n"
            "Vulkan draw: verified\nVulkan draw device: Adreno 825\n",
        ]
        def runner(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=outputs.pop(0))
        report = proot_diagnostics.verify_proot_guest(
            distro="debian", user="sbj", display=":1", backend="zink",
            which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
            runner=runner,
        )
        self.assertEqual(report["checks"]["renderer_class"], "zink_turnip")
        self.assertEqual(report["checks"]["glx_draw"], "failed")
        self.assertEqual(report["checks"]["glx_draw_frames"], 214)
        self.assertIn("llvmpipe", report["checks"]["glx_draw_renderer"])

    def test_proot_guest_verification_does_not_probe_legacy_ternux_status(self):
        calls = []
        which_calls = []
        outputs = [
            SimpleNamespace(returncode=0, stdout="Installed containers:\n * Debian\n"),
            SimpleNamespace(returncode=0, stdout=("Display: :1\nX11: reachable\nAudio: PulseAudio reachable\n"
                "Renderer: zink Turnip\nGLX draw: verified\nGLX draw frames: 120\n"
                "GLX draw renderer: zink Turnip\nVulkan draw: verified\nVulkan draw device: Adreno 825\n")),
        ]
        def runner(args, **kwargs):
            calls.append(args)
            return outputs.pop(0)
        def which(name):
            which_calls.append(name)
            return "/prefix/bin/proot-distro" if name == "proot-distro" else (
                "/prefix/bin/ternux" if name == "ternux" else None)
        report = proot_diagnostics.verify_proot_guest(
            distro="debian", user="sbj", display=":1", backend="zink",
            which=which,
            runner=runner,
        )
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("ternux", which_calls)
        self.assertNotIn("native_ternux_status", report)
        self.assertNotIn("companion_version", report)

    def test_guest_verification_reports_missing_distribution_without_guest_login(self):
        calls = []
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout=(
                "Installed containers:\nLog in with: proot-distro login <name>\n"))
        with mock.patch.object(proot_diagnostics, "_native_pulse_cookie_path", return_value=None):
            report = proot_diagnostics.verify_proot_guest(
                distro="debian", user="sbj", display=":1", backend="zink",
                which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
                runner=runner)
        self.assertEqual(report["status"], "not_installed")
        self.assertFalse(report["guest_entered"])
        self.assertFalse(report["safety"]["guest_write_command_invoked"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], ["/prefix/bin/proot-distro", "list"])

    def test_failed_guest_login_stays_unknown_and_discloses_possible_profile_write(self):
        calls = []
        outputs = [
            SimpleNamespace(returncode=0, stdout=(
                "Installed containers:\n * Debian\nLog in with: proot-distro login <name>\n")),
            SimpleNamespace(returncode=127, stdout=""),
        ]
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return outputs.pop(0)
        with mock.patch.object(proot_diagnostics, "_native_pulse_cookie_path", return_value=None):
            report = proot_diagnostics.verify_proot_guest(
                distro="debian", user="sbj", display=":1", backend="zink",
                which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None,
                runner=runner)
        self.assertEqual(report["status"], "unknown")
        self.assertTrue(report["guest_entered"])
        self.assertTrue(report["safety"]["launcher_profile_write_possible"])
        self.assertFalse(report["safety"]["guest_write_command_invoked"])
        self.assertFalse(report["safety"]["packages_changed"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0][0:3], ["/prefix/bin/proot-distro", "login", "--isolated"])

    def test_guest_verify_fails_closed_for_unsafe_or_unsupported_inputs(self):
        calls = []
        with mock.patch.object(proot_diagnostics, "verify_managed_guest_alias",
                               side_effect=ValueError("guest receipt unavailable")):
            for values in (
                {"distro": "ubuntu", "user": "sbj", "display": ":1", "backend": "zink"},
                {"distro": "debian", "user": "root", "display": ":1", "backend": "zink"},
                {"distro": "debian", "user": "sbj;id", "display": ":1", "backend": "zink"},
                {"distro": "debian", "user": "sbj", "display": ":1;id", "backend": "zink"},
                {"distro": "debian", "user": "sbj", "display": ":1", "backend": "auto"},
            ):
                with self.subTest(values=values), self.assertRaises(ValueError):
                    proot_diagnostics.verify_proot_guest(**values, runner=lambda *a, **k: calls.append(a))
        self.assertEqual(calls, [])

    def test_guest_diagnostic_outcomes_match_strict_response_schema(self):
        schema = json.loads((ROOT / "schemas/proot-guest-diagnostics.schema.json").read_text())
        inventory = "Installed containers:\n * Debian\nLog in with: proot-distro login <name>\n"
        status = ("Display: :1\nX11: reachable\nAudio: PulseAudio reachable\n"
                  "Renderer: zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))\n"
                  "GLX draw: verified\nGLX draw frames: 214\n"
                  "GLX draw renderer: zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))\n"
                  "Vulkan draw: verified\nVulkan draw device: Adreno (TM) 825\n")
        outputs = [inventory, status]
        def runner(args, **kwargs):
            output = outputs.pop(0)
            return SimpleNamespace(returncode=0, stdout=output)
        complete = proot_diagnostics.verify_proot_guest(
            distro="debian", user="sbj", display=":1", backend="zink",
            which=lambda name: "/prefix/bin/proot-distro" if name == "proot-distro" else None, runner=runner)
        absent = proot_diagnostics.verify_proot_guest(
            distro="debian", user="sbj", display=":1", backend="zink", which=lambda _name: None)
        for report in (complete, absent):
            self.assertEqual(set(report), set(schema["required"]))
            self.assertEqual(report["component"], schema["properties"]["component"]["const"])
            self.assertIn(report["status"], schema["properties"]["status"]["enum"])
            self.assertEqual(set(report["checks"]), set(schema["properties"]["checks"]["required"]))
            self.assertEqual(set(report["safety"]), set(schema["properties"]["safety"]["required"]))
            self.assertTrue(report["safety"]["host_home_and_shared_storage_unbound"])
            self.assertTrue(all(value is False for key, value in report["safety"].items()
                                if key not in {"host_home_and_shared_storage_unbound", "launcher_profile_write_possible"}))
        self.assertEqual(complete["status"], "complete")
        self.assertEqual(absent["status"], "unavailable")

    def test_launcher_side_effect_metadata_includes_failed_login_attempts(self):
        for entered in (False, True):
            report = proot_diagnostics._verification_result(
                status="unknown", display=":1", backend="zink", guest_entered=entered)
            self.assertEqual(report["read_only"], not entered)
            self.assertEqual(report["safety"]["launcher_profile_write_possible"], entered)
            self.assertTrue(report["probe_payload_read_only"])

    def test_guest_command_rejects_unsafe_cookie_bind_paths(self):
        for path in ("relative/cookie", "/tmp/cookie:guest", "/tmp/cookie\n--env=BAD=1"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                proot_diagnostics._guest_command(
                    "/prefix/bin/proot-distro", "sbj", ":1", "zink", "status",
                    prefix="/prefix", cookie_path=path)

    def test_guest_command_disables_default_host_mounts_and_scopes_zink_bindings(self):
        zink = proot_diagnostics._guest_command(
            "/prefix/bin/proot-distro", "sbj", ":1", "zink", "status", prefix="/prefix",
            cookie_path="/native/home/.config/pulse/cookie")
        self.assertIn("--isolated", zink)
        self.assertNotIn("--shared-home", zink)
        self.assertNotIn("--shared-tmp", zink)
        self.assertIn("/prefix/tmp/.X11-unix:/tmp/.X11-unix", zink)
        self.assertIn("/dev/kgsl-3d0:/dev/kgsl", zink)
        self.assertIn("/dev/dri", zink)
        self.assertIn("/native/home/.config/pulse/cookie:/tmp/.ternuxx-pulse-cookie", zink)
        self.assertIn("PULSE_COOKIE=/tmp/.ternuxx-pulse-cookie", zink)
        self.assertNotIn("/data/data/com.termux", zink)
        virgl = proot_diagnostics._guest_command(
            "/prefix/bin/proot-distro", "sbj", ":1", "virgl", "status", prefix="/prefix")
        self.assertIn("--isolated", virgl)
        self.assertIn("--shared-tmp", virgl)
        self.assertNotIn("--shared-home", virgl)
        self.assertNotIn("/data/data/com.termux", virgl)
        self.assertIn("LIBGL_ALWAYS_SOFTWARE=true", virgl)
        self.assertIn("GALLIUM_DRIVER=virpipe", virgl)
        self.assertIn("VTEST_SOCKET_NAME=/tmp/.ternuxx-virgl/virgl-1.sock", virgl)

    def test_native_pulseaudio_endpoint_is_read_only_and_typed(self):
        calls = []
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout="Server Name: pulseaudio\nDefault Sink: OpenSL_ES_sink\n")
        report = proot_diagnostics.inspect_native_pulseaudio_endpoint(
            which=lambda name: "/prefix/bin/pactl" if name == "pactl" else None, runner=runner)
        self.assertEqual(report, {"status": "available", "server_name": "pulseaudio",
                                  "default_sink": "OpenSL_ES_sink"})
        self.assertEqual(calls[0][0], ["/prefix/bin/pactl", "--server", "tcp:127.0.0.1:4713", "info"])
        self.assertEqual(calls[0][1]["timeout"], 5)
        self.assertTrue(calls[0][1]["capture_output"])
        self.assertTrue(calls[0][1]["env"]["PULSE_COOKIE"].endswith("/.config/pulse/cookie"))

    def test_native_pulse_cookie_path_rejects_symlink_and_unsafe_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            pulse = home / ".config" / "pulse"
            pulse.mkdir(parents=True, mode=0o700)
            (home / ".config").chmod(0o700)
            pulse.chmod(0o700)
            cookie = pulse / "cookie"
            cookie.write_bytes(b"x" * 256)
            cookie.chmod(0o600)
            with mock.patch.object(proot_diagnostics.Path, "home", return_value=home):
                self.assertEqual(proot_diagnostics._native_pulse_cookie_path(), cookie)
                cookie.chmod(0o640)
                self.assertIsNone(proot_diagnostics._native_pulse_cookie_path())
                cookie.chmod(0o600)
                cookie.unlink()
                target = pulse / "target"
                target.write_bytes(b"x" * 256)
                target.chmod(0o600)
                cookie.symlink_to(target)
                self.assertIsNone(proot_diagnostics._native_pulse_cookie_path())

    def test_native_pulseaudio_endpoint_distinguishes_unavailable_and_unknown(self):
        missing = proot_diagnostics.inspect_native_pulseaudio_endpoint(which=lambda _name: None)
        failed = proot_diagnostics.inspect_native_pulseaudio_endpoint(
            which=lambda _name: "/prefix/bin/pactl",
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""))
        malformed = proot_diagnostics.inspect_native_pulseaudio_endpoint(
            which=lambda _name: "/prefix/bin/pactl",
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="Server Name: bad value!\n"))
        timed_out = proot_diagnostics.inspect_native_pulseaudio_endpoint(
            which=lambda _name: "/prefix/bin/pactl",
            runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                subprocess.TimeoutExpired("pactl", 5)))
        self.assertEqual(missing["status"], "unavailable")
        self.assertEqual(failed["status"], "unavailable")
        self.assertEqual(malformed["status"], "unknown")
        self.assertIsNone(malformed["server_name"])
        self.assertEqual(timed_out["status"], "unknown")

    def test_termux_x11_process_inspection_returns_displays_without_pid_or_argv(self):
        calls = []
        outputs = [
            "16032 termux-x11\n16040 proot\n16050 termux-x11\n",
            "/data/data/com.termux/files/usr/bin/termux-x11 :1 -ac\n",
            "/data/data/com.termux/files/usr/bin/termux-x11 invalid\n",
        ]
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout=outputs.pop(0))
        report = proot_diagnostics.inspect_termux_x11_process_displays(
            which=lambda name: "/prefix/bin/ps" if name == "ps" else None, runner=runner)
        self.assertEqual(report, {"status": "available", "observed_displays": [":1"]})
        self.assertEqual(calls[0][0], ["/prefix/bin/ps", "-A", "-o", "pid=,comm="])
        self.assertEqual(calls[1][0], ["/prefix/bin/ps", "-p", "16032", "-o", "args="])
        self.assertEqual(calls[2][0], ["/prefix/bin/ps", "-p", "16050", "-o", "args="])
        self.assertEqual(calls[0][1]["timeout"], 5)
        unavailable = proot_diagnostics.inspect_termux_x11_process_displays(which=lambda _name: None)
        unknown = proot_diagnostics.inspect_termux_x11_process_displays(
            which=lambda _name: "/prefix/bin/ps",
            runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                subprocess.TimeoutExpired("ps", 5)))
        self.assertEqual(unavailable["status"], "unavailable")
        self.assertEqual(unknown["status"], "unknown")

    def test_failed_guest_display_reports_visible_host_display_mismatch_without_identity_claim(self):
        outputs = [
            SimpleNamespace(returncode=0, stdout="Installed containers:\n * Debian\nLog in with: proot-distro login <name>\n"),
            SimpleNamespace(returncode=1, stdout="Display: :0\nX11: unavailable\nAudio: PulseAudio reachable\nRenderer: unavailable\n"),
            SimpleNamespace(returncode=0, stdout="16032 termux-x11\n"),
            SimpleNamespace(returncode=0, stdout="termux-x11 :1 -ac\n"),
        ]
        calls = []
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return outputs.pop(0)
        report = proot_diagnostics.verify_proot_guest(
            distro="debian", user="sbj", display=":0", backend="zink",
            which=lambda name: {"proot-distro": "/prefix/bin/proot-distro",
                                "ps": "/prefix/bin/ps"}.get(name),
            runner=runner,
        )
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["checks"]["observed_display"], ":0")
        self.assertIn("requested display :0 not observed in the Termux-visible X11 process list",
                      report["blockers"])
        self.assertLessEqual(len(report["blockers"]), 8)
        self.assertEqual(calls[-2][0], ["/prefix/bin/ps", "-A", "-o", "pid=,comm="])
        self.assertEqual(calls[-1][0], ["/prefix/bin/ps", "-p", "16032", "-o", "args="])
        self.assertNotIn("16032", json.dumps(report))
        self.assertNotIn("termux-x11", json.dumps(report))
        self.assertEqual(report["profile_owner"], "unverified")

    def test_unavailable_manager_and_unrecognized_output_remain_unknown(self):
        absent = proot_diagnostics.inspect_installed(which=lambda _name: None)
        failed = proot_diagnostics.inspect_installed(
            which=lambda _name: "/prefix/bin/proot-distro",
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="private error"),
        )
        malformed = proot_diagnostics.inspect_installed(
            which=lambda _name: "/prefix/bin/proot-distro",
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="unexpected format"),
        )
        self.assertEqual(absent["status"], "unavailable")
        self.assertEqual(failed["status"], "unknown")
        self.assertEqual(malformed["status"], "unknown")
        self.assertNotIn("private error", str(failed))


if __name__ == "__main__":
    unittest.main()
