from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import graphics_manager
import management_authorization
import management_service
import management_sessions


class GraphicsManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.repo = self.home / "ternuxx"
        self.state = self.home / ".local/share/ternuxx"
        self.provider = self.state / "graphics/providers/native-mesa-0219ff84"
        self.prefix = self.provider / "extracted/data/data/com.termux/files/usr"
        for relative in ("lib/dri/libdril_dri.so", "lib/libgallium-26.3.0-devel.so",
                        "share/glvnd/egl_vendor.d/50_mesa.json", "lib/libvulkan_freedreno.so"):
            target = self.prefix / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("qualified fixture", encoding="utf-8")
        manifest = self.provider / "freedreno-isolated.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"ICD": {"library_path": str(self.prefix / "lib/libvulkan_freedreno.so")}}), encoding="utf-8")
        profile = self.repo / "config/graphics/native-kgsl.json"
        profile.parent.mkdir(parents=True, exist_ok=True)
        verified = {
            relative: hashlib.sha256((self.prefix / relative).read_bytes()).hexdigest()
            for relative in ("lib/dri/libdril_dri.so", "lib/libgallium-26.3.0-devel.so",
                             "share/glvnd/egl_vendor.d/50_mesa.json", "lib/libvulkan_freedreno.so")
        }
        profile.write_text(json.dumps({"schema_version": 1, "provider": "native-termux-bionic",
                                       "verified_files": verified}), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_termux_freedreno(self, prefix: Path) -> None:
        for relative in ("lib/dri/libdril_dri.so", "lib/libgallium-26.2.5.so", "lib/libvulkan_freedreno.so"):
            target = prefix / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("termux package fixture", encoding="utf-8")
        icd = prefix / "share/vulkan/icd.d/freedreno_icd.aarch64.json"
        icd.parent.mkdir(parents=True, exist_ok=True)
        icd.write_text(json.dumps({"ICD": {"library_path": "libvulkan_freedreno.so"}}), encoding="utf-8")

    def test_termux_zink_requires_and_uses_the_installed_freedreno_icd(self) -> None:
        prefix = self.home / "termux"
        self.make_termux_freedreno(prefix)
        with patch.dict(os.environ, {"PREFIX": str(prefix)}), patch.object(
                graphics_manager, "_run", return_value=(0, "deviceName = Adreno 825\n")):
            result = graphics_manager.configure_native("termux-zink", home=str(self.home),
                state_dir=str(self.state), repo_root=str(self.repo), prefix=str(prefix))
        self.assertEqual(result["backend"], "termux-zink")
        selection = self.state / "native-graphics-backend"
        self.assertEqual(selection.read_text(), "termux-zink\n")
        self.assertEqual(selection.stat().st_mode & 0o777, 0o600)
        env = graphics_manager.native_process_environment(home=str(self.home), state_dir=str(self.state),
            process_env={"PATH": "/termux/bin", "PREFIX": str(prefix)})
        self.assertEqual(env["MESA_LOADER_DRIVER_OVERRIDE"], "zink")
        self.assertEqual(env["GALLIUM_DRIVER"], "zink")
        self.assertEqual(env["VK_ICD_FILENAMES"],
            str(prefix / "share/vulkan/icd.d/freedreno_icd.aarch64.json"))
        status = graphics_manager.status("native", home=str(self.home), state_dir=str(self.state),
            process_env={"PATH": "/termux/bin", "PREFIX": str(prefix)}, prefix=str(prefix))
        self.assertEqual(status["selected_backend"], "termux-zink")

    def test_termux_zink_refuses_missing_or_escaping_freedreno_icd(self) -> None:
        prefix = self.home / "termux"
        with self.assertRaisesRegex(ValueError, "unavailable"):
            graphics_manager.configure_native("termux-zink", home=str(self.home),
                state_dir=str(self.state), repo_root=str(self.repo), prefix=str(prefix))
        self.make_termux_freedreno(prefix)
        icd = prefix / "share/vulkan/icd.d/freedreno_icd.aarch64.json"
        icd.write_text(json.dumps({"ICD": {"library_path": "/tmp/foreign.so"}}), encoding="utf-8")
        with patch.object(graphics_manager, "_run", return_value=(0, "deviceName = Adreno 825\n")), self.assertRaisesRegex(ValueError, "points outside"):
            graphics_manager.configure_native("termux-zink", home=str(self.home),
                state_dir=str(self.state), repo_root=str(self.repo), prefix=str(prefix))
        self.assertFalse((self.state / "native-graphics-backend").exists())

    def test_termux_zink_selection_requires_a_supported_enumerated_gpu(self) -> None:
        prefix = self.home / "termux"
        self.make_termux_freedreno(prefix)
        with patch.object(graphics_manager, "_run", return_value=(1, "TU: device is unsupported\n")):
            with self.assertRaisesRegex(ValueError, "did not enumerate a supported Vulkan GPU"):
                graphics_manager.configure_native("termux-zink", home=str(self.home),
                    state_dir=str(self.state), repo_root=str(self.repo), prefix=str(prefix))
        self.assertFalse((self.state / "native-graphics-backend").exists())

    def test_system_selection_removes_termux_zink_preference(self) -> None:
        prefix = self.home / "termux"
        self.make_termux_freedreno(prefix)
        with patch.object(graphics_manager, "_run", return_value=(0, "deviceName = Adreno 825\n")):
            graphics_manager.configure_native("termux-zink", home=str(self.home), state_dir=str(self.state),
                repo_root=str(self.repo), prefix=str(prefix))
        result = graphics_manager.configure_native("system", home=str(self.home),
            state_dir=str(self.state), repo_root=str(self.repo))
        self.assertTrue(result["changed"])
        self.assertFalse((self.state / "native-graphics-backend").exists())
        env = graphics_manager.native_process_environment(home=str(self.home), state_dir=str(self.state),
            process_env={"PATH": "/termux/bin", "PREFIX": str(prefix)})
        self.assertNotIn("MESA_LOADER_DRIVER_OVERRIDE", env)

    def test_only_known_candidate_is_selected_and_file_is_private(self) -> None:
        result = graphics_manager.configure_native("kgsl-freedreno", home=str(self.home),
                                                   state_dir=str(self.state), repo_root=str(self.repo))
        config = self.state / "native-graphics-prefix"
        self.assertEqual(result["backend"], "kgsl-freedreno")
        self.assertEqual(config.read_text().strip(), str(self.prefix))
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_system_selection_is_reversible_and_unsafe_file_is_preserved(self) -> None:
        graphics_manager.configure_native("kgsl-freedreno", home=str(self.home),
                                           state_dir=str(self.state), repo_root=str(self.repo))
        graphics_manager.configure_native("system", home=str(self.home),
                                           state_dir=str(self.state), repo_root=str(self.repo))
        self.assertFalse((self.state / "native-graphics-prefix").exists())
        link = self.state / "native-graphics-prefix"
        link.symlink_to(self.repo)
        with self.assertRaisesRegex(ValueError, "preserved"):
            graphics_manager.configure_native("system", home=str(self.home),
                                               state_dir=str(self.state), repo_root=str(self.repo))
        self.assertTrue(link.is_symlink())
        link.unlink()
        link.symlink_to(self.repo / "missing-target")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            graphics_manager.configure_native("kgsl-freedreno", home=str(self.home),
                                               state_dir=str(self.state), repo_root=str(self.repo))
        self.assertTrue(link.is_symlink())

    def test_system_environment_prioritizes_termux_runtime_over_injected_loader_paths(self) -> None:
        env = graphics_manager.native_process_environment(
            home=str(self.home), state_dir=str(self.state),
            process_env={"PATH": "/termux/bin", "PREFIX": "/termux",
                         "LD_LIBRARY_PATH": "/codex/lib:/custom/lib"},
        )
        self.assertEqual(env["LD_LIBRARY_PATH"], "/termux/lib:/codex/lib:/custom/lib")

    def test_candidate_environment_prioritizes_termux_runtime_over_injected_loader_paths(self) -> None:
        graphics_manager.configure_native("kgsl-freedreno", home=str(self.home),
                                           state_dir=str(self.state), repo_root=str(self.repo))
        env = graphics_manager._native_env(
            home=str(self.home), state_dir=str(self.state),
            process_env={"PATH": "/fixture", "PREFIX": "/termux",
                         "LD_LIBRARY_PATH": "/codex/bin:/custom/lib"},
        )
        self.assertEqual(env["LD_LIBRARY_PATH"],
                         f"{self.prefix}/lib:/termux/lib:/codex/bin:/custom/lib")

    def test_gles_is_not_reported_from_an_opengl_only_probe(self) -> None:
        native = graphics_manager.verify("native", "gles", home=str(self.home), state_dir=str(self.state),
                                         process_env={"PATH": "", "PREFIX": "/termux"}, prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(native["status"], "unavailable")
        self.assertFalse(native["render_verified"])

    def test_gles_context_renderer_name_does_not_claim_acceleration(self) -> None:
        with patch.object(graphics_manager.shutil, "which", return_value="/fixture/es2_info"), \
             patch.object(graphics_manager, "_run", return_value=(
                 0, "GL_RENDERER: zink Vulkan (Adreno 825 / MESA_TURNIP)\nGL_VERSION: OpenGL ES 3.2 Mesa\n")):
            result = graphics_manager._gles_context({"PATH": "/fixture"})
        self.assertTrue(result["context_verified"])
        self.assertFalse(result["render_verified"])
        self.assertIsNone(result["accelerated"])
        self.assertIn("acceleration unverified", result["proof"])

    def test_gles_draw_verification_reports_real_frames_and_renderer(self) -> None:
        with patch.object(graphics_manager, "_gles_draw", return_value={
                "status": "rendered", "context_verified": True, "render_verified": True,
                "renderer": "Adreno (TM) 825", "version": "OpenGL ES 3.2", "accelerated": True,
                "frames": 120, "throughput_fps": 24.0}):
            result = graphics_manager.verify("native", "gles", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"},
                                             prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["status"], "rendered")
        self.assertTrue(result["render_verified"])
        self.assertEqual(result["renderer"], "Adreno (TM) 825")
        self.assertEqual(result["frames"], 120)

    def test_gles_draw_runner_reports_hardware_shader_frames_and_cleans_up(self) -> None:
        source = self.repo / "docs/evidence/graphics/native-mesa-0219ff84/offscreen-gles.c"
        source.parent.mkdir(parents=True)
        source.write_text("eglCreatePbufferSurface glDrawArrays glFinish", encoding="utf-8")
        self.state.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.state.chmod(0o700)
        outputs = [(0, "compiler ok"), (0, "EGL=1.5 | GLES=OpenGL ES 3.2 | renderer=Adreno (TM) 825 | pbuffer=1280x720\nelapsed=5.000 seconds frames=240 throughput=48.00 frames/sec\n")]
        with patch.object(graphics_manager.shutil, "which", return_value="/fixture/clang"), \
             patch.object(graphics_manager, "_run", side_effect=outputs) as runner:
            result = graphics_manager._gles_draw({"PATH": "/fixture"}, repo_root=str(self.repo),
                                                 state_dir=str(self.state))
        self.assertEqual(result["status"], "rendered")
        self.assertTrue(result["render_verified"])
        self.assertTrue(result["accelerated"])
        self.assertEqual(result["frames"], 240)
        self.assertEqual(runner.call_count, 2)
        self.assertFalse(Path(runner.call_args_list[0].args[0][5]).exists())

    def test_gles_draw_runner_rejects_zero_frames(self) -> None:
        source = self.repo / "docs/evidence/graphics/native-mesa-0219ff84/offscreen-gles.c"
        source.parent.mkdir(parents=True)
        source.write_text("eglCreatePbufferSurface glDrawArrays glFinish", encoding="utf-8")
        self.state.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.state.chmod(0o700)
        with patch.object(graphics_manager.shutil, "which", return_value="/fixture/clang"), \
             patch.object(graphics_manager, "_run", side_effect=[
                 (0, "compiler ok"),
                 (0, "EGL=1.5 | GLES=OpenGL ES 3.2 | renderer=llvmpipe (LLVM fixture)\nelapsed=5 seconds frames=0 throughput=0 frames/sec\n")]):
            result = graphics_manager._gles_draw({"PATH": "/fixture"}, repo_root=str(self.repo),
                                                 state_dir=str(self.state))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["render_verified"])
        self.assertFalse(result["accelerated"])

    def test_opengl_verification_draws_to_the_running_native_x11_display(self) -> None:
        self.state.mkdir(parents=True, mode=0o700, exist_ok=True)
        (self.state / "session.json").write_text('{"display":":1"}', encoding="utf-8")
        with patch.object(graphics_manager.shutil, "which", return_value="/fixture/glmark2"), \
             patch.object(graphics_manager, "_run", return_value=(
                 0, "GL_RENDERER: Adreno (TM) 825\nglmark2 Score: 456\n")) as runner:
            result = graphics_manager.verify("native", "opengl", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"},
                                             prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["display"], ":1")
        self.assertEqual(result["render_target"], "x11-window")
        self.assertTrue(result["render_verified"])
        self.assertNotIn("--off-screen", runner.call_args.args[0])
        self.assertEqual(runner.call_args.args[1]["DISPLAY"], ":1")

    def test_opengl_failed_primary_tries_llvmpipe_and_reports_software(self) -> None:
        with patch.object(graphics_manager.shutil, "which", return_value="/fixture/glmark2"), \
             patch.object(graphics_manager, "_run", side_effect=[
                 (1, "primary backend failed"),
                 (0, "GL_RENDERER: llvmpipe (LLVM fixture)\nglmark2 Score: 123\n"),
             ]) as runner:
            result = graphics_manager.verify("native", "opengl", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"}, prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["status"], "fallback-rendered")
        self.assertTrue(result["render_verified"])
        self.assertFalse(result["accelerated"])
        self.assertEqual(result["renderer"], "llvmpipe (LLVM fixture)")
        self.assertEqual(result["fallback_attempts"][0]["backend"], "llvmpipe")
        self.assertEqual(runner.call_args_list[1].args[1]["LIBGL_ALWAYS_SOFTWARE"], "true")
        self.assertEqual(runner.call_args_list[1].args[1]["GALLIUM_DRIVER"], "llvmpipe")

    def test_opengl_tries_softpipe_when_llvmpipe_cannot_render(self) -> None:
        with patch.object(graphics_manager.shutil, "which", return_value="/fixture/glmark2"), \
             patch.object(graphics_manager, "_run", side_effect=[
                 (1, "primary Zink failed"),
                 (1, "GL_RENDERER: llvmpipe (LLVM fixture)\n"),
                 (0, "GL_RENDERER: softpipe (LLVM fixture)\nglmark2 Score: 33\n"),
             ]) as runner:
            result = graphics_manager.verify("native", "opengl", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"}, prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["status"], "fallback-rendered")
        self.assertEqual(result["fallback_order"], ["llvmpipe", "softpipe"])
        self.assertEqual([item["backend"] for item in result["fallback_attempts"]], ["llvmpipe", "softpipe"])
        self.assertEqual(runner.call_args_list[1].args[1]["GALLIUM_DRIVER"], "llvmpipe")
        self.assertEqual(runner.call_args_list[2].args[1]["GALLIUM_DRIVER"], "softpipe")

    def test_opengl_fallback_does_not_accept_an_unqualified_renderer(self) -> None:
        with patch.object(graphics_manager.shutil, "which", return_value="/fixture/glmark2"), \
             patch.object(graphics_manager, "_run", side_effect=[
                 (1, "primary backend failed"),
                 (0, "GL_RENDERER: unknown virtual renderer\nglmark2 Score: 123\n"),
                 (0, "GL_RENDERER: another virtual renderer\nglmark2 Score: 100\n"),
             ]):
            result = graphics_manager.verify("native", "opengl", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"}, prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["render_verified"])
        self.assertFalse(result["fallback_attempts"][0]["status"] == "rendered")

    def test_vulkan_verification_requires_bounded_draw_on_enumerated_device(self) -> None:
        with patch.object(graphics_manager.shutil, "which", side_effect=["/fixture/vulkaninfo", "/fixture/vkcube"]), \
             patch.object(graphics_manager, "_native_env", return_value={"PATH": "/fixture", "DISPLAY": ":1"}), \
             patch.object(graphics_manager, "_run", side_effect=[
                 (0, "deviceName = Adreno (TM) 825\n"),
                 (0, "Selected WSI platform: xcb\nSelected GPU 0: Adreno (TM) 825, type: IntegratedGpu\n"),
             ]):
            result = graphics_manager.verify("native", "vulkan", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"}, prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["status"], "rendered")
        self.assertTrue(result["render_verified"])
        self.assertEqual(result["draw_frames"], 120)

    def test_vulkan_verification_rejects_draw_from_a_different_device(self) -> None:
        with patch.object(graphics_manager.shutil, "which", side_effect=["/fixture/vulkaninfo", "/fixture/vkcube"]), \
             patch.object(graphics_manager, "_native_env", return_value={"PATH": "/fixture", "DISPLAY": ":1"}), \
             patch.object(graphics_manager, "_run", side_effect=[
                 (0, "deviceName = Adreno (TM) 825\n"),
                 (0, "Selected GPU 0: llvmpipe (LLVM fixture), type: Cpu\n"),
             ]):
            result = graphics_manager.verify("native", "vulkan", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"}, prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["render_verified"])

    def test_vulkan_enumeration_failure_returns_bounded_linker_diagnostic_without_draw(self) -> None:
        detail = 'CANNOT LINK EXECUTABLE "vulkaninfo": cannot locate symbol "fixture"'
        with patch.object(graphics_manager.shutil, "which", return_value="/fixture/vulkaninfo"), \
             patch.object(graphics_manager, "_native_env", return_value={"PATH": "/fixture", "DISPLAY": ":1"}), \
             patch.object(graphics_manager, "_run", return_value=(1, detail)) as runner:
            result = graphics_manager.verify("native", "vulkan", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"},
                                             prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["diagnostic"], detail)
        self.assertFalse(result["render_verified"])
        self.assertEqual(runner.call_count, 1)

    def test_vulkan_enumeration_without_display_does_not_claim_a_draw(self) -> None:
        with patch.object(graphics_manager.shutil, "which", side_effect=["/fixture/vulkaninfo", "/fixture/vkcube"]), \
             patch.object(graphics_manager, "_native_env", return_value={"PATH": "/fixture"}), \
             patch.object(graphics_manager, "_run", return_value=(0, "deviceName = Adreno (TM) 825\n")) as runner:
            result = graphics_manager.verify("native", "vulkan", home=str(self.home), state_dir=str(self.state),
                                             process_env={"PATH": "/fixture", "PREFIX": "/termux"}, prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["status"], "enumerated")
        self.assertFalse(result["render_verified"])
        self.assertEqual(runner.call_count, 1)

    def test_modified_candidate_file_fails_hash_validation(self) -> None:
        driver = self.prefix / "lib/libvulkan_freedreno.so"
        driver.write_text("modified candidate", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "file hash does not match"):
            graphics_manager.configure_native("kgsl-freedreno", home=str(self.home),
                                               state_dir=str(self.state), repo_root=str(self.repo))

    def test_unqualified_backend_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "backend must be"):
            graphics_manager.configure_native("virgl", home=str(self.home),
                                               state_dir=str(self.state), repo_root=str(self.repo))

    def test_selection_requires_confirmation_and_has_narrow_mutation_scope(self) -> None:
        request = {"api_version": 1, "request_id": "graphics-test-0001",
                   "operation": "graphics.provider.select",
                   "args": {"provider": "native", "backend": "system", "confirmed": False}}
        response = management_service.dispatch(request, env={"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr", "HOME": str(self.home)})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "confirmation_required")
        self.assertEqual(management_authorization.required_capability("graphics.provider.select"), "graphics.manage")
        self.assertIn("graphics.provider.select", management_sessions.MUTATING_OPERATIONS)
        self.assertNotIn("graphics.provider.select", management_sessions.READ_ONLY_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
