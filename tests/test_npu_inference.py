"""Tests for the pinned, fail-closed Native Hexagon HTP inference path."""
import io
import hashlib
import json
import os
from types import SimpleNamespace
import stat
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import npu_inference  # noqa: E402


class NpuInferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ternuxx-npu-")
        self.home = Path(self.temporary.name)
        self.state = self.home / ".local/share/ternuxx"
        self.home_patch = patch.object(npu_inference.Path, "home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.addCleanup(self.temporary.cleanup)

    def test_runtime_preview_plan_is_stable_when_free_space_changes(self):
        before = list(self.home.rglob("*"))
        with patch.object(npu_inference.shutil, "disk_usage",
                          side_effect=(SimpleNamespace(free=500_000_000),
                                       SimpleNamespace(free=499_000_000))):
            first = npu_inference.preview(home=self.home, state_dir=self.state)
            second = npu_inference.preview(home=self.home, state_dir=self.state)
        first_plan = {key: value for key, value in first.items() if key != "available_bytes"}
        second_plan = {key: value for key, value in second.items() if key != "available_bytes"}
        self.assertEqual(first_plan, second_plan)
        self.assertEqual(first["available_bytes"], 500_000_000)
        self.assertEqual(second["available_bytes"], 499_000_000)
        self.assertEqual(first["release"], "b11849")
        self.assertEqual(first["sha256"], npu_inference.ARCHIVE_SHA256)
        self.assertEqual(first["license"], "MIT")
        self.assertEqual(first["extraction_limit_bytes"], npu_inference.MAX_EXTRACTED_BYTES)
        self.assertTrue(first["read_only"])
        self.assertEqual(list(self.home.rglob("*")), before)

    def _make_removable_runtime(self):
        root = npu_inference.artifact_root(home=self.home, state_dir=self.state)
        runtime = npu_inference.runtime_path(home=self.home, state_dir=self.state)
        binary = runtime / "bin/llama-cli"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"runtime-fixture")
        os.chmod(binary, 0o600)
        npu_inference._write_manifest(root, {"bin/llama-cli": {
            "size_bytes": len(b"runtime-fixture"),
            "sha256": hashlib.sha256(b"runtime-fixture").hexdigest()}})
        return root, runtime

    def test_remove_runtime_requires_exact_preview_and_preserves_cached_archive(self):
        root, runtime = self._make_removable_runtime()
        archive = npu_inference.archive_path(home=self.home, state_dir=self.state)
        archive.write_bytes(b"cached archive")
        plan = npu_inference.preview("remove", home=self.home, state_dir=self.state)
        self.assertTrue(plan["removable"])
        with patch.object(npu_inference, "_active_runtime_processes", return_value=[]):
            with self.assertRaisesRegex(npu_inference.NpuInferenceError, "exact current preview"):
                npu_inference.remove_runtime(plan_id="stale", confirmed="REMOVE", home=self.home, state_dir=self.state)
            result = npu_inference.remove_runtime(plan_id=plan["plan_id"], confirmed="REMOVE",
                                                  home=self.home, state_dir=self.state)
        self.assertTrue(result["removed"])
        self.assertTrue(result["archive_retained"])
        self.assertTrue(archive.is_file())
        self.assertFalse(runtime.exists())
        self.assertFalse((root / "install-manifest.json").exists())

    def test_remove_runtime_preserves_tampered_or_in_use_tree(self):
        root, runtime = self._make_removable_runtime()
        (runtime / "extra.txt").write_text("owner file")
        plan = npu_inference.preview("remove", home=self.home, state_dir=self.state)
        self.assertFalse(plan["removable"])
        with self.assertRaisesRegex(npu_inference.NpuInferenceError, "unrecorded"):
            npu_inference.remove_runtime(plan_id=plan["plan_id"], confirmed="REMOVE",
                                         home=self.home, state_dir=self.state)
        (runtime / "extra.txt").unlink()
        plan = npu_inference.preview("remove", home=self.home, state_dir=self.state)
        with patch.object(npu_inference, "_active_runtime_processes", return_value=[123]):
            with self.assertRaisesRegex(npu_inference.NpuInferenceError, "idle"):
                npu_inference.remove_runtime(plan_id=plan["plan_id"], confirmed="REMOVE",
                                             home=self.home, state_dir=self.state)
        self.assertTrue(runtime.exists())

    def test_install_requires_exact_plan_and_install_confirmation_before_download(self):
        plan = npu_inference.preview(home=self.home, state_dir=self.state)
        with patch.object(npu_inference, "_download_archive") as download:
            with self.assertRaisesRegex(npu_inference.NpuInferenceError, "exact current preview"):
                npu_inference.install_runtime(plan_id="stale", confirmed="INSTALL",
                                              home=self.home, state_dir=self.state)
            with self.assertRaisesRegex(npu_inference.NpuInferenceError, "exact current preview"):
                npu_inference.install_runtime(plan_id=plan["plan_id"], confirmed="yes",
                                              home=self.home, state_dir=self.state)
        download.assert_not_called()
        self.assertEqual(list(self.home.rglob("*")), [])

    def test_archive_member_validation_rejects_path_traversal_and_links(self):
        for member in (tarfile.TarInfo("llama-b11849/../../escape"),
                       tarfile.TarInfo("llama-b11849/lib/libggml-htp-v73.so")):
            with self.subTest(name=member.name), tempfile.TemporaryFile() as stream:
                with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                    if ".." in member.name:
                        member.type = tarfile.REGTYPE
                        member.size = 1
                        archive.addfile(member, io.BytesIO(b"x"))
                    else:
                        member.type = tarfile.SYMTYPE
                        member.linkname = "/system/lib64/libbinder_ndk.so"
                        archive.addfile(member)
                stream.seek(0)
                with tarfile.open(fileobj=stream, mode="r:gz") as archive:
                    with self.assertRaises(npu_inference.NpuInferenceError):
                        npu_inference._required_members(archive)

    def test_archive_member_validation_keeps_older_archive_compatible_without_notice(self):
        required = ("bin/llama-cli", "LICENSE", "lib/libggml-hexagon.so",
                    "lib/libggml-htp-v73.so", "lib/libggml-opencl.so")
        with tempfile.TemporaryFile() as stream:
            with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                for relative in required:
                    member = tarfile.TarInfo(f"{npu_inference.ROOT_NAME}/{relative}")
                    member.size = 1
                    archive.addfile(member, io.BytesIO(b"x"))
            stream.seek(0)
            with tarfile.open(fileobj=stream, mode="r:gz") as archive:
                selected = npu_inference._required_members(archive)
        self.assertNotIn("llama-b11849/THIRD_PARTY_NOTICES.txt", {item.name for item in selected})

    def test_archive_member_validation_preserves_third_party_notices(self):
        required = ("bin/llama-cli", "LICENSE", "lib/libggml-hexagon.so",
                    "lib/libggml-htp-v73.so", "lib/libggml-opencl.so",
                    "THIRD_PARTY_NOTICES.txt")
        with tempfile.TemporaryFile() as stream:
            with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                for relative in required:
                    body = b"notice" if relative == "THIRD_PARTY_NOTICES.txt" else b"x"
                    member = tarfile.TarInfo(f"{npu_inference.ROOT_NAME}/{relative}")
                    member.size = len(body)
                    archive.addfile(member, io.BytesIO(body))
            stream.seek(0)
            with tarfile.open(fileobj=stream, mode="r:gz") as archive:
                selected = npu_inference._required_members(archive)
        self.assertIn("llama-b11849/THIRD_PARTY_NOTICES.txt", {item.name for item in selected})

    def test_runtime_env_is_fixed_and_drops_inherited_loader_injection(self):
        runtime = self.home / "runtime"
        with patch.dict(os.environ, {"LD_LIBRARY_PATH": "/untrusted/lib", "LD_PRELOAD": "/tmp/injected.so",
                                     "GGML_HEXAGON_MM_SELECT": "0", "ADSP_LIBRARY_PATH": "/tmp"}):
            env = npu_inference._runtime_env(runtime, prefix="/termux")
        self.assertEqual(env["LD_LIBRARY_PATH"],
                         f"{runtime}/lib:/system/lib64:/vendor/lib64:/termux/lib")
        self.assertEqual(env["GGML_HEXAGON_MM_SELECT"], "1")
        self.assertEqual(env["GGML_HEXAGON_FA_SELECT"], "0")
        self.assertNotIn("/untrusted", env["LD_LIBRARY_PATH"])
        self.assertNotIn("LD_PRELOAD", env)

    def test_status_requires_the_exact_qualified_soc_before_device_probe(self):
        with patch.object(npu_inference, "runtime_path", return_value=self.home / "runtime"), \
                patch.object(npu_inference, "_runtime_valid", return_value=(True, "verified")), \
                patch.object(npu_inference, "_soc_model", return_value="SM8850"), \
                patch.object(npu_inference.subprocess, "run") as run:
            result = npu_inference.status(home=self.home, state_dir=self.state)
        self.assertFalse(result["available"])
        self.assertIn("only on Qualcomm SM8735", result["reason"])
        run.assert_not_called()

    def test_status_requires_runtime_reported_htp_device(self):
        runtime = self.home / "runtime"
        completed = npu_inference.subprocess.CompletedProcess(
            ["llama-cli", "--list-devices"], 0, "Available devices:\n  GPUOpenCL: Adreno 825\n", "")
        with patch.object(npu_inference, "runtime_path", return_value=runtime), \
                patch.object(npu_inference, "_runtime_valid", return_value=(True, "verified")), \
                patch.object(npu_inference, "_soc_model", return_value="SM8735"), \
                patch.object(npu_inference.subprocess, "run", return_value=completed):
            result = npu_inference.status(home=self.home, state_dir=self.state)
        self.assertFalse(result["available"])
        self.assertIsNone(result["device"])

    def test_run_requires_both_htp_layer_and_model_buffer_proof(self):
        model = self.state / "models" / npu_inference.cpu_inference.MODEL.filename
        model.parent.mkdir(parents=True)
        model.write_bytes(b"fixture")
        stdout = "> <|im_start|>user\nWhat is 2 + 2?<|im_end|>\n<|im_start|>assistant\n\n4\n[ Prompt: 1 t/s | Generation: 1 t/s ]\n"
        completed = npu_inference.subprocess.CompletedProcess(
            ["llama-cli"], 0, stdout,
            "load_tensors: offloaded 29/29 layers to GPU\nload_tensors: HTP0 model buffer size = 319.96 MiB\n")
        with patch.object(npu_inference, "status", return_value={"available": True}), \
                patch.object(npu_inference.cpu_inference, "_valid_model", return_value=True), \
                patch.object(npu_inference.cpu_inference, "_model_lock"), \
                patch.object(npu_inference, "_runtime_valid", return_value=(True, "verified")), \
                patch.object(npu_inference, "_execute", return_value=completed) as execute:
            result = npu_inference.run_inference("What is 2 + 2?", home=self.home,
                                                 state_dir=self.state, max_tokens=8)
        self.assertEqual(result["backend"], "Hexagon HTP")
        self.assertEqual(result["output"], "4")
        self.assertEqual(result["npu_layers"], 29)
        self.assertEqual(result["npu_model_buffer_mib"], 319.96)
        self.assertFalse(result["silent_fallback"])
        self.assertIn("HTP0", execute.call_args.args[0])
        self.assertIn("all", execute.call_args.args[0])

    def test_run_rejects_partial_htp_layer_offload(self):
        model = self.state / "models" / npu_inference.cpu_inference.MODEL.filename
        model.parent.mkdir(parents=True)
        model.write_bytes(b"fixture")
        stdout = "> <|im_start|>user\nhello<|im_end|>\n<|im_start|>assistant\n\nhello\n"
        completed = npu_inference.subprocess.CompletedProcess(
            ["llama-cli"], 0, stdout,
            "load_tensors: offloaded 28/29 layers to GPU\nHTP0 model buffer size = 319.96 MiB\n")
        with patch.object(npu_inference, "status", return_value={"available": True}), \
                patch.object(npu_inference.cpu_inference, "_valid_model", return_value=True), \
                patch.object(npu_inference.cpu_inference, "_model_lock"), \
                patch.object(npu_inference, "_runtime_valid", return_value=(True, "verified")), \
                patch.object(npu_inference, "_execute", return_value=completed):
            with self.assertRaisesRegex(npu_inference.NpuInferenceError, "complete HTP layer"):
                npu_inference.run_inference("hello", home=self.home, state_dir=self.state)

    def test_run_fails_closed_without_htp_delegation_proof(self):
        model = self.state / "models" / npu_inference.cpu_inference.MODEL.filename
        model.parent.mkdir(parents=True)
        model.write_bytes(b"fixture")
        completed = npu_inference.subprocess.CompletedProcess(["llama-cli"], 0, "not output", "")
        with patch.object(npu_inference, "status", return_value={"available": True}), \
                patch.object(npu_inference.cpu_inference, "_valid_model", return_value=True), \
                patch.object(npu_inference.cpu_inference, "_model_lock"), \
                patch.object(npu_inference, "_runtime_valid", return_value=(True, "verified")), \
                patch.object(npu_inference, "_execute", return_value=completed):
            with self.assertRaisesRegex(npu_inference.NpuInferenceError, "complete HTP layer"):
                npu_inference.run_inference("hello", home=self.home, state_dir=self.state)

    def test_run_rejects_multiline_prompt_and_unavailable_device_before_launch(self):
        with patch.object(npu_inference, "_execute") as execute, \
                patch.object(npu_inference, "status", return_value={"available": False, "reason": "no HTP0"}):
            with self.assertRaisesRegex(npu_inference.NpuInferenceError, "one line"):
                npu_inference.run_inference("one\ntwo", home=self.home, state_dir=self.state)
            with self.assertRaisesRegex(npu_inference.NpuInferenceError, "no HTP0"):
                npu_inference.run_inference("hello", home=self.home, state_dir=self.state)
        execute.assert_not_called()

    def test_runtime_manifest_rejects_same_size_hash_tampering_and_missing_files(self):
        root = self.home / "artifact" / "runtime" / "llama-b11849"
        root.mkdir(parents=True)
        manifest = {"release": "b11849", "asset": npu_inference.ASSET,
                    "sha256": npu_inference.ARCHIVE_SHA256,
                    "files": {}}
        for relative in ("bin/llama-cli", "lib/libggml-hexagon.so", "lib/libggml-htp-v73.so",
                         "lib/libggml-opencl.so", "LICENSE", "THIRD_PARTY_NOTICES.txt"):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"x")
            target.chmod(0o600)
            manifest["files"][relative] = {"size_bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
        marker = root.parent.parent / "install-manifest.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(manifest))
        marker.chmod(0o600)
        self.assertTrue(npu_inference._runtime_valid(root)[0])
        tampered = root / "lib/libggml-htp-v73.so"
        tampered.write_bytes(b"y")
        self.assertFalse(npu_inference._runtime_valid(root)[0])
        tampered.write_bytes(b"x")
        tampered.unlink()
        self.assertFalse(npu_inference._runtime_valid(root)[0])
        tampered.write_bytes(b"x")
        notice = root / "THIRD_PARTY_NOTICES.txt"
        notice.write_bytes(b"y")
        self.assertFalse(npu_inference._runtime_valid(root)[0])
        notice.write_bytes(b"x")
        tampered.unlink()
        outside = self.home / "replacement.so"
        outside.write_bytes(b"x")
        tampered.symlink_to(outside)
        self.assertFalse(npu_inference._runtime_valid(root)[0])


if __name__ == "__main__":
    unittest.main()
