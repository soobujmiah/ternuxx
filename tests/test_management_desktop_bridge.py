from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import os
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))
import management_desktop_bridge as bridge


class ManagementDesktopBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        # The GTK bridge is deliberately Native-Termux-only. Unit tests run on
        # Linux CI as well, so model the host contract instead of inheriting the
        # runner's unrelated environment.
        env = mock.patch.dict(os.environ, {
            "TERMUX_VERSION": "fixture",
            "PREFIX": "/data/data/com.termux/files/usr",
        })
        env.start()
        self.addCleanup(env.stop)

    def test_native_environment_gate_rejects_non_termux_host(self):
        with mock.patch.dict(os.environ, {"TERMUX_VERSION": "", "PREFIX": "/usr"}), \
                mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()), \
                mock.patch("sys.stderr", StringIO()):
            self.assertEqual(bridge.main(["catalog"]), 2)
        dispatch.assert_not_called()

    def test_cpu_prompt_is_sent_on_stdin_to_shared_management_service(self):
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"output": "ok"}}) as dispatch, \
                mock.patch("sys.stdin", StringIO("one line")), redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["cpu-run"]), 0)
        dispatch.assert_called_once_with("inference.cpu.run", {"prompt": "one line", "max_tokens": 64})
        self.assertIn("ok", output.getvalue().casefold())

    def test_vulkan_inference_bridge_uses_shared_status_and_stdin_prompt(self):
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"available": False}}) as dispatch, \
                redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["gpu-status"]), 0)
        dispatch.assert_called_once_with("inference.gpu.status")
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"output": "ok"}}) as dispatch, \
                mock.patch("sys.stdin", StringIO("one line")), redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["gpu-run"]), 0)
        dispatch.assert_called_once_with("inference.gpu.run", {"prompt": "one line", "max_tokens": 64})
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, \
                mock.patch("sys.stdin", StringIO("prompt")), redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["gpu-run", "Vulkan1"]), 0)
        dispatch.assert_called_once_with("inference.gpu.run", {
            "prompt": "prompt", "max_tokens": 64, "device_id": "Vulkan1"})
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["gpu-run", "../outside"]), 2)
        dispatch.assert_not_called()

    def test_npu_bridge_previews_exact_runtime_and_gates_prompt_on_htp_status(self):
        preview = {"ok": True, "data": {"plan_id": "a" * 24, "release": "b11849"}}
        with mock.patch.object(bridge, "call", return_value=preview) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["npu-runtime-preview"]), 0)
        dispatch.assert_called_once_with("inference.npu.runtime.preview")
        self.assertIn("P\t" + "a" * 24, output.getvalue())
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"installed": True}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["npu-runtime-apply", "a" * 24, "INSTALL"]), 0)
        dispatch.assert_called_once_with("inference.npu.runtime.apply", {"plan_id": "a" * 24, "confirmed": True})
        with mock.patch.object(bridge, "call", side_effect=[{"ok": True, "data": {"available": False, "reason": "HTP absent"}}]) as dispatch, \
                mock.patch("sys.stdin", StringIO("one line")), redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["npu-run"]), 1)
        dispatch.assert_called_once_with("inference.npu.status")
        with mock.patch.object(bridge, "call", side_effect=[{"ok": True, "data": {"available": True}},
                {"ok": True, "data": {"output": "ok", "backend": "HTP0"}}]) as dispatch, \
                mock.patch("sys.stdin", StringIO("one line")), redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["npu-run"]), 0)
        self.assertEqual(dispatch.call_args_list, [mock.call("inference.npu.status"), mock.call(
            "inference.npu.run", {"prompt": "one line", "max_tokens": 64})])

    def test_cron_create_bridge_encodes_all_supported_schedule_types_as_typed_service_args(self):
        cases = [
            (["cron", "0 8 * * *", "", "Asia/Dhaka"],
             {"expression": "0 8 * * *", "timezone": "Asia/Dhaka"}),
            (["interval", "3600", "2026-10-24T00:00:00Z"],
             {"interval_seconds": 3600, "anchor_at": "2026-10-24T00:00:00Z"}),
            (["calendar", "08:30", "daily", "Asia/Dhaka"],
             {"mode": "daily", "time": "08:30", "timezone": "Asia/Dhaka"}),
            (["calendar", "2099-01-01T08:30:00+06:00", "specific"],
             {"mode": "specific", "datetime": "2099-01-01T08:30:00+06:00"}),
            (["one_time", "2099-01-01T08:30:00+06:00", ""],
             {"at": "2099-01-01T08:30:00+06:00"}),
        ]
        for fields, schedule in cases:
            with self.subTest(schedule=schedule), \
                    mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"plan": {"plan_id": "a" * 32}}}) as dispatch, \
                    redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(["cron-preview", "create", "job", "diagnostics.doctor", *fields]), 0)
                self.assertEqual(dispatch.call_args.args[1]["schedule"], schedule)
                self.assertEqual(dispatch.call_args.args[1]["schedule_type"], fields[0])

    def test_recovery_inspection_bridge_uses_only_allowlisted_read_operations(self):
        operation_id = "a" * 32
        cases = [
            (["recovery-status"], "recovery.status", None),
            (["backup-list"], "backup.list", None),
            (["backup-inspect", "daily"], "backup.inspect", {"backup_id": "daily"}),
            (["restore-preview", "daily"], "restore.preview", {"backup_id": "daily"}),
            (["recovery-inspect", operation_id], "recovery.inspect", {"operation_id": operation_id}),
            (["recovery-rollback-preview", operation_id], "recovery.rollback.preview", {"operation_id": operation_id}),
            (["continuity-status"], "continuity.status", None),
        ]
        for argv, operation, payload in cases:
            with self.subTest(argv=argv), mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(argv), 0)
            if payload is None:
                dispatch.assert_called_once_with(operation)
            else:
                dispatch.assert_called_once_with(operation, payload)
        for argv in (["backup-inspect", "../secret"], ["recovery-inspect", "../" + operation_id]):
            with self.subTest(argv=argv), mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(argv), 2)
            dispatch.assert_not_called()

    def test_continuity_checkpoint_bridge_uses_typed_preview_and_confirmed_plan(self):
        plan_id = "e" * 64
        cases = (("continuity-prepare-preview", "continuity.prepare.preview", "release-audit"),
                 ("continuity-verify-preview", "continuity.verify.preview", "a" * 32))
        for action, operation, reference in cases:
            with self.subTest(action=action), mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"plan_id": plan_id}}) as dispatch, redirect_stdout(StringIO()) as output:
                self.assertEqual(bridge.main([action, reference]), 0)
            args = {"test_id": reference} if "prepare" in action else {"checkpoint_id": reference}
            dispatch.assert_called_once_with(operation, args)
            self.assertEqual(output.getvalue().strip().split("\t", 2)[:2], ["P", plan_id])
        for action, operation, reference in (("continuity-prepare-apply", "continuity.prepare", "release-audit"),
                                             ("continuity-verify-apply", "continuity.verify", "a" * 32)):
            with self.subTest(action=action), mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
                self.assertEqual(bridge.main([action, reference, plan_id, "confirmed"]), 0)
            args = {"test_id": reference} if "prepare" in action else {"checkpoint_id": reference}
            dispatch.assert_called_once_with(operation, {**args, "confirmed": True, "plan_id": plan_id})
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["continuity-verify-preview", "../bad"]), 2)
            self.assertEqual(bridge.main(["continuity-verify-apply", "a" * 32, "bad", "confirmed"]), 2)
        dispatch.assert_not_called()

    def test_backup_create_preview_and_apply_use_exact_saved_plan(self):
        plan = {"plan_id": "a" * 64, "entries": [{"path": "profile", "present": True}]}
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": plan}) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["backup-create-preview", "daily"]), 0)
        dispatch.assert_called_once_with("backup.create", {"name": "daily"})
        self.assertEqual(output.getvalue().strip().split("\t", 2)[:2], ["P", "a" * 64])
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"created": True}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["backup-create-apply", "daily", "a" * 64, "confirmed"]), 0)
        dispatch.assert_called_once_with("backup.create", {"name": "daily", "confirmed": True, "plan_id": "a" * 64})

    def test_restore_apply_preview_and_apply_use_exact_saved_plan(self):
        plan = {"plan_id": "b" * 64, "entries": [{"path": "profile", "action": "replace"}]}
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": plan}) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["restore-apply-preview", "daily"]), 0)
        dispatch.assert_called_once_with("restore.preview", {"backup_id": "daily"})
        self.assertEqual(output.getvalue().strip().split("\t", 2)[:2], ["P", "b" * 64])
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"restored": True}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["restore-apply", "daily", "b" * 64, "confirmed"]), 0)
        dispatch.assert_called_once_with("restore.apply", {"backup_id": "daily", "confirmed": True, "plan_id": "b" * 64})

    def test_backup_restore_bridge_rejects_bad_ids_and_plan_ids(self):
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["backup-create-preview", "../bad"]), 2)
            self.assertEqual(bridge.main(["backup-create-apply", "daily", "bad", "confirmed"]), 2)
            self.assertEqual(bridge.main(["restore-apply-preview", "../bad"]), 2)
            self.assertEqual(bridge.main(["restore-apply", "daily", "bad", "confirmed"]), 2)
        dispatch.assert_not_called()

    def test_recovery_resolution_and_rollback_apply_use_exact_preview_plans(self):
        operation_id = "c" * 32
        plan_id = "d" * 64
        for action, service_operation in (("recovery-resolve-preview", "recovery.resolve"),
                                         ("recovery-rollback-apply-preview", "recovery.rollback.preview")):
            with self.subTest(action=action), mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"plan_id": plan_id}}) as dispatch, redirect_stdout(StringIO()) as output:
                self.assertEqual(bridge.main([action, operation_id]), 0)
            dispatch.assert_called_once_with(service_operation, {"operation_id": operation_id})
            self.assertEqual(output.getvalue().strip().split("\t", 3)[:3], ["P", plan_id, operation_id])
        for action, service_operation in (("recovery-resolve-apply", "recovery.resolve"),
                                         ("recovery-rollback-apply", "recovery.rollback.apply")):
            with self.subTest(action=action), mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
                self.assertEqual(bridge.main([action, operation_id, plan_id, "confirmed"]), 0)
            dispatch.assert_called_once_with(service_operation, {"operation_id": operation_id, "confirmed": True, "plan_id": plan_id})

    def test_recovery_apply_bridge_rejects_malformed_operation_and_plan_ids(self):
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["recovery-resolve-preview", "../bad"]), 2)
            self.assertEqual(bridge.main(["recovery-rollback-apply-preview", "../bad"]), 2)
            self.assertEqual(bridge.main(["recovery-resolve-apply", "a" * 32, "bad", "confirmed"]), 2)
            self.assertEqual(bridge.main(["recovery-rollback-apply", "bad", "b" * 64, "confirmed"]), 2)
        dispatch.assert_not_called()

    def test_cron_inspection_bridge_allows_only_typed_read_operations(self):
        job_id = "job-" + "a" * 32
        execution_id = "exec-" + "b" * 32
        for args, operation, payload in (
            (["cron-inspect", "job", job_id], "cron.jobs.show", {"job_id": job_id}),
            (["cron-inspect", "next", job_id], "cron.jobs.next_runs", {"job_id": job_id, "count": 5}),
            (["cron-inspect", "execution", execution_id], "cron.executions.show", {"execution_id": execution_id}),
        ):
            with self.subTest(args=args), mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(args), 0)
            dispatch.assert_called_once_with(operation, payload)
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["cron-inspect", "job", "../../state"]), 2)
        dispatch.assert_not_called()

    def test_cron_scheduler_actions_use_shared_operations_and_bounded_interval(self):
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"state": "running"}}) as dispatch, \
                redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["cron-scheduler", "start", "10"]), 0)
        dispatch.assert_called_once_with("cron.scheduler.start", {"poll_seconds": 10, "confirmed": True})
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"state": "stopped"}}) as dispatch, \
                redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["cron-scheduler", "stop"]), 0)
        dispatch.assert_called_once_with("cron.scheduler.stop", {"confirmed": True})
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["cron-scheduler", "start", "0"]), 2)
        dispatch.assert_not_called()

    def test_directory_tree_file_handoff_uses_fixed_shared_operation(self):
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
                "path": "~/Documents", "output": "notes.txt", "read_only": True}}) as dispatch, \
                redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["software-run", "Documents"]), 0)
        dispatch.assert_called_once_with("software.app.run", {"app_id": "directory-tree", "path": "Documents"})
        self.assertIn("Notes.txt", output.getvalue())

    def test_proot_replay_guest_preview_apply_use_exact_shared_plans(self):
        alias, backup_id, plan_id = "ternuxx-replay-p4", "b" * 32, "a" * 64
        retire = {"ok": True, "data": {"plan_id": plan_id, "operation": {
            "alias": alias, "confirmation_required": True, "impact": "No files deleted."}}}
        with mock.patch.object(bridge, "call", return_value=retire) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["proot-replay-retire-preview", alias]), 0)
        dispatch.assert_called_once_with("proot.setup.retire.preview", {"alias": alias})
        self.assertEqual(output.getvalue().strip().split("\t")[:3], ["P", plan_id, alias])

        restore = {"ok": True, "data": {"plan_id": plan_id, "operation": {
            "alias": alias, "backup_id": backup_id, "confirmation_required": True,
            "impact": "Restore exact guest."}}}
        with mock.patch.object(bridge, "call", return_value=restore) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["proot-replay-restore-preview", alias, backup_id]), 0)
        dispatch.assert_called_once_with("proot.setup.restore.preview", {"alias": alias, "backup_id": backup_id})
        self.assertEqual(output.getvalue().strip().split("\t")[:4], ["P", plan_id, alias, backup_id])

        for action, args, operation, payload in (
            ("proot-replay-retire-apply", [alias, plan_id], "proot.setup.retire.apply",
             {"alias": alias, "confirmed": True, "plan_id": plan_id}),
            ("proot-replay-restore-apply", [alias, backup_id, plan_id], "proot.setup.restore.apply",
             {"alias": alias, "backup_id": backup_id, "confirmed": True, "plan_id": plan_id}),
        ):
            with self.subTest(action=action), mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
                self.assertEqual(bridge.main([action, *args]), 0)
            dispatch.assert_called_once_with(operation, payload)

    def test_proot_replay_guest_bridge_rejects_unowned_alias_and_bad_ids(self):
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-replay-retire-preview", "debian"]), 2)
            self.assertEqual(bridge.main(["proot-replay-restore-preview", "ternuxx-replay-p4", "bad"]), 2)
            self.assertEqual(bridge.main(["proot-replay-retire-apply", "ternuxx-replay-p4", "bad"]), 2)
            self.assertEqual(bridge.main(["proot-replay-restore-apply", "ternuxx-replay-p4", "b" * 32, "bad"]), 2)
        dispatch.assert_not_called()

    def test_curated_software_preview_and_apply_use_exact_shared_plan(self):
        preview = {"ok": True, "data": {"plan_id": "a" * 64, "changes": [{"action": "install", "package": "htop"}]}}
        with mock.patch.object(bridge, "call", return_value=preview) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["software-preview", "process-monitor", "install"]), 0)
        dispatch.assert_called_once_with("software.app.preview", {"app_id": "process-monitor", "action": "install"})
        fields = output.getvalue().strip().split("\t", 4)
        self.assertEqual(fields[:4], ["P", "a" * 64, "process-monitor", "install"])
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"applied": True}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["software-apply", "process-monitor", "install", "a" * 64, "INSTALL"]), 0)
        dispatch.assert_called_once_with("software.app.apply", {
            "app_id": "process-monitor", "action": "install", "plan_id": "a" * 64, "confirmation": "INSTALL"})

    def test_curated_software_bridge_rejects_unknown_id_and_bad_plan(self):
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["software-preview", "arbitrary", "install"]), 2)
            self.assertEqual(bridge.main(["software-apply", "tree", "remove", "bad", "REMOVE"]), 2)
        dispatch.assert_not_called()

    def test_cpu_model_preview_and_apply_use_exact_shared_plan(self):
        payload = {"plan_id": "a" * 24, "size_bytes": 123, "sha256": "b" * 64}
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": payload}) as dispatch, \
                redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["cpu-model-preview", "install"]), 0)
        dispatch.assert_called_once_with("inference.cpu.model.preview", {"action": "install"})
        self.assertTrue(output.getvalue().startswith("P\t" + "a" * 24 + "\t"))
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"installed": True}}) as dispatch, \
                redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["cpu-model-apply", "install", "a" * 24, "confirmed"]), 0)
        dispatch.assert_called_once_with("inference.cpu.model.apply", {
            "action": "install", "plan_id": "a" * 24, "confirmed": True})

    def test_ssh_key_previews_and_applies_use_shared_service_with_exact_plan(self) -> None:
        preview = {"ok": True, "data": {"plan_id": "a" * 24,
                  "fingerprint": "SHA256:" + "b" * 43}}
        with mock.patch.object(bridge, "call", return_value=preview) as dispatch, \
             redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["ssh-key-add-preview", "ssh-ed25519 AAAA test"]), 0)
        dispatch.assert_called_once_with("ssh.keys.add.preview", {"public_key": "ssh-ed25519 AAAA test"})
        fields = output.getvalue().strip().split(chr(9))
        self.assertEqual(fields[:3], ["P", "a" * 24, "SHA256:" + "b" * 43])
        self.assertIn("8022", fields[3]); self.assertIn("8023", fields[3])
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"changed": True}}) as dispatch, \
             redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["ssh-key-add-apply", "confirmed", "ssh-ed25519 AAAA test", "a" * 24]), 0)
        dispatch.assert_called_once_with("ssh.keys.add.apply", {
            "public_key": "ssh-ed25519 AAAA test", "confirmed": True, "plan_id": "a" * 24,
        })

    def test_ssh_autostart_status_preview_and_apply_share_typed_service(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"enabled": True}}) as dispatch, \
             redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["ssh-autostart-status"]), 0)
        dispatch.assert_called_once_with("ssh.service.autostart.status")
        self.assertEqual(output.getvalue().strip(), "S\ttrue")
        preview = {"ok": True, "data": {"changed": True, "plan_id": "d" * 32,
                   "effect": "next supervisor starts with sshd down; current service unchanged"}}
        with mock.patch.object(bridge, "call", return_value=preview) as dispatch, \
             redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["ssh-autostart-preview", "disabled"]), 0)
        dispatch.assert_called_once_with("ssh.service.autostart.preview", {"enabled": False})
        self.assertEqual(output.getvalue().strip().split(chr(9))[:3], ["P", "d" * 32, "false"])
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"enabled": False}}) as dispatch, \
             redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["ssh-autostart-apply", "confirmed", "false", "d" * 32]), 0)
        dispatch.assert_called_once_with("ssh.service.autostart.apply", {
            "enabled": False, "confirmed": True, "plan_id": "d" * 32})

    def test_ssh_wakelock_policy_bridge_uses_shared_preview_and_apply(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
                "persistent_lease_enabled": True}}) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["ssh-wakelock-status"]), 0)
        dispatch.assert_called_once_with("wakelock.ssh-policy.status")
        self.assertEqual(output.getvalue().strip(), "S\ttrue")
        preview = {"ok": True, "data": {"changed": True, "plan_id": "e" * 32,
                   "effect": "current SSH lease remains unchanged"}}
        with mock.patch.object(bridge, "call", return_value=preview) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["ssh-wakelock-preview", "disabled"]), 0)
        dispatch.assert_called_once_with("wakelock.ssh-policy.preview", {"enabled": False})
        self.assertEqual(output.getvalue().strip().split(chr(9))[:3], ["P", "e" * 32, "false"])
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"status": "updated"}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["ssh-wakelock-apply", "confirmed", "false", "e" * 32]), 0)
        dispatch.assert_called_once_with("wakelock.ssh-policy.apply", {
            "enabled": False, "confirmed": True, "plan_id": "e" * 32})

    def test_ssh_autostart_apply_rejects_malformed_plan(self) -> None:
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["ssh-autostart-apply", "confirmed", "false", "bad"]), 2)
        dispatch.assert_not_called()

    def test_native_ssh_client_key_preview_and_apply_use_exact_shared_plan(self) -> None:
        preview = {"ok": True, "data": {"changed": True, "plan_id": "c" * 32,
                   "name": "recovery8023", "private_key_path": "/tmp/native/.ssh/ternuxx-keys/recovery8023"}}
        with mock.patch.object(bridge, "call", return_value=preview) as dispatch, \
             redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["ssh-client-key-preview", "recovery8023"]), 0)
        dispatch.assert_called_once_with("ssh.client-key.create.preview", {"name": "recovery8023"})
        fields = output.getvalue().strip().split(chr(9))
        self.assertEqual(fields[:4], ["P", "c" * 32, "recovery8023", "/tmp/native/.ssh/ternuxx-keys/recovery8023"])
        self.assertIn("not enrolled", fields[4])
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"created": True}}) as dispatch, \
             redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["ssh-client-key-apply", "confirmed", "recovery8023", "c" * 32]), 0)
        dispatch.assert_called_once_with("ssh.client-key.create.apply", {
            "name": "recovery8023", "confirmed": True, "plan_id": "c" * 32,
        })

    def test_native_ssh_client_key_apply_rejects_malformed_plan_before_dispatch(self) -> None:
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["ssh-client-key-apply", "confirmed", "recovery8023", "bad"]), 2)
        dispatch.assert_not_called()

    def test_ssh_key_apply_rejects_malformed_plan_before_dispatch(self) -> None:
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["ssh-key-remove-apply", "confirmed", "SHA256:x", "bad"]), 2)
        dispatch.assert_not_called()

    def test_ssh_key_inventory_uses_the_shared_read_operation(self) -> None:
        report = {"ok": True, "data": {"status": "available", "key_count": 1,
                  "keys": [{"key_type": "ssh-ed25519", "fingerprint": "SHA256:abc", "label": "laptop"}]}}
        with mock.patch.object(bridge, "call", return_value=report) as dispatch, \
             redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["ssh-keys-list"]), 0)
        dispatch.assert_called_once_with("ssh.keys.list")

    def test_catalog_bridge_emits_catalog_categories_and_resources(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = bridge.main(["catalog"])
        self.assertEqual(code, 0)
        lines = output.getvalue().splitlines()
        categories = [line.split(chr(9)) for line in lines if line.startswith("C" + chr(9))]
        resources = [line.split(chr(9)) for line in lines if line.startswith("R" + chr(9))]
        self.assertGreaterEqual(len(categories), 10)
        self.assertIn("native.desktop.session", {row[1] for row in resources})
        self.assertIn("native.gui.activity-monitor", {row[1] for row in resources})
        desktop = next(row for row in resources if row[1] == "native.desktop.session")
        graphics = next(row for row in resources if row[1] == "graphics.native")
        self.assertGreaterEqual(len(desktop), 8)
        self.assertIn("Start desktop", desktop[7])
        self.assertIn("Graphics provider verify", graphics[7])

    def test_inspection_is_selected_from_resource_supported_read_operation(self) -> None:
        output = StringIO()
        original = bridge.call
        with mock.patch.object(bridge, "call", side_effect=lambda op, args=None:
                               original(op, args) if op == "management.catalog" else
                               {"ok": True, "data": {"state": "unknown"}}) as dispatch:
            with redirect_stdout(output):
                result = bridge.main(["inspect", "native.desktop.session"])
        self.assertEqual(result, 0)
        self.assertIn(mock.call("desktop.status"), dispatch.call_args_list)

    def test_acceleration_resource_runs_only_read_only_display_qualification(self) -> None:
        payload = {"ok": True, "data": {"findings": [
            {"id": "NTX-CPU-001"}, {"id": "NTX-GPU-103"}, {"id": "NTX-NPU-001"}]}}
        with mock.patch.object(bridge, "call", return_value=payload) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                result = bridge.main(["inspect", "native.acceleration.qualification"])
        self.assertEqual(result, 0)
        dispatch.assert_called_once_with("doctor.report", {"graphics": True})
        self.assertIn("NTX-NPU-001", output.getvalue())

    def test_audio_resource_inspection_uses_read_only_doctor_report(self) -> None:
        original = bridge.call
        payload = {"ok": True, "data": {"findings": [
            {"id": "NTX-AUDIO-001", "summary": "ready"}]}}
        with mock.patch.object(bridge, "call", side_effect=lambda op, args=None:
                               original(op, args) if op == "management.catalog" else payload) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                result = bridge.main(["inspect", "native.audio.pulseaudio"])
        self.assertEqual(result, 0)
        self.assertIn(mock.call("doctor.report", {"graphics": False}), dispatch.call_args_list)
        self.assertIn("NTX-AUDIO-001", output.getvalue())

    def test_health_resource_uses_doctor_report_without_graphics_probe(self) -> None:
        original = bridge.call
        payload = {"ok": True, "data": {"findings": []}}
        with mock.patch.object(bridge, "call", side_effect=lambda op, args=None:
                               original(op, args) if op == "management.catalog" else payload) as dispatch:
            with redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(["inspect", "native.system.health"]), 0)
        self.assertIn(mock.call("doctor.report", {"graphics": False}), dispatch.call_args_list)

    def test_port_8022_uses_read_only_ssh_inspection(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch:
            with redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(["inspect", "network.ssh.manual-8022"]), 0)
        dispatch.assert_called_once_with("ssh.inspect")

    def test_managed_ssh_resource_uses_the_same_canonical_inspection_operation(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch:
            with redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(["inspect", "network.ssh.managed-8023"]), 0)
        dispatch.assert_called_once_with("ssh.inspect")

    def test_gui_monitoring_status_only_reads_policy(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
            "enabled": False, "interval_seconds": 300, "focus_check": False, "activity_launch": False,
        }}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["monitor"]), 0)
        dispatch.assert_called_once_with("desktop.monitor.status")
        self.assertIn("M" + chr(9) + "False" + chr(9) + "300" + chr(9) + "False" + chr(9) + "False", output.getvalue())

    def test_cron_bridge_lists_registry_through_shared_service(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"jobs": []}}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["cron-jobs"]), 0)
        dispatch.assert_called_once_with("cron.jobs.list")
        self.assertIn("Jobs: None", output.getvalue())

    def test_cron_preview_and_apply_bridge_use_shared_saved_plan(self) -> None:
        preview_result = {"ok": True, "data": {"plan": {
            "plan_id": "a" * 32, "action": "create", "before": None, "after": {"name": "daily"},
        }}}
        with mock.patch.object(bridge, "call", return_value=preview_result) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["cron-preview", "create", "daily", "diagnostics.doctor",
                                             "cron", "0 8 * * *", "", "Asia/Dhaka"]), 0)
        request = dispatch.call_args.args[0]
        self.assertEqual(request, "cron.jobs.mutation.preview")
        self.assertEqual(dispatch.call_args.args[1], {
            "action": "create", "name": "daily", "action_id": "diagnostics.doctor",
            "schedule_type": "cron", "schedule": {"expression": "0 8 * * *", "timezone": "Asia/Dhaka"}})
        self.assertIn("P" + chr(9) + "a" * 32, output.getvalue())
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"applied": True}}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["cron-apply", "a" * 32]), 0)
        dispatch.assert_called_once_with("cron.jobs.mutation.apply", {"plan_id": "a" * 32, "confirmed": True})



















    def test_ssh_key_rollback_bridge_lists_and_uses_exact_preview(self) -> None:
        listing = {"ok": True, "data": {"entries": [{"rollback_id": "a" * 32,
            "fingerprint": "SHA256:" + "b" * 43, "action": "remove", "status": "applied"}]}}
        with mock.patch.object(bridge, "call", return_value=listing) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["ssh-key-rollback-list"]), 0)
        dispatch.assert_called_once_with("ssh.keys.rollback.list")
        self.assertTrue(output.getvalue().startswith("R\t" + "a" * 32))
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
                "plan_id": "c" * 24, "rollback_id": "a" * 32,
                "effect": "Restore exact prior file."}}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["ssh-key-rollback-preview", "a" * 32]), 0)
        dispatch.assert_called_once_with("ssh.keys.rollback.preview", {"rollback_id": "a" * 32})
        self.assertTrue(output.getvalue().startswith("P\t" + "c" * 24 + "\t" + "a" * 32))

    def test_timezone_set_bridge_calls_typed_preference_operation(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"timezone": "UTC"}}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["timezone-set", "UTC"]), 0)
        dispatch.assert_called_once_with("timezone.set", {"timezone": "UTC"})
        self.assertIn("UTC", output.getvalue())

    def test_cron_history_bridge_reads_bounded_shared_execution_history(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"executions": []}}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["cron-history"]), 0)
        dispatch.assert_called_once_with("cron.executions.list", {"limit": 20})
        self.assertIn("Executions: None", output.getvalue())

    def test_history_bridge_reads_the_shared_recovery_journal(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
            "operations": [], "unresolved_count": 0, "read_only": True}}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["history"]), 0)
        dispatch.assert_called_once_with("recovery.status")
        self.assertIn("Items needing attention: 0", output.getvalue())

    def test_history_bridge_hides_internal_ids_and_formats_timestamps(self) -> None:
        payload = {"ok": True, "data": {"unresolved_count": 0, "operations": [{
            "operation_id": "a" * 32, "kind": "service.deploy", "status": "complete",
            "created_at": "2026-10-18T23:04:19.753138+00:00",
            "updated_at": "2026-10-18T23:04:19.782579+00:00",
            "detail": "Definition deployed; rollback=" + "b" * 64,
        }]}}
        with mock.patch.object(bridge, "call", return_value=payload) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["history"]), 0)
        dispatch.assert_called_once_with("recovery.status")
        rendered = output.getvalue()
        self.assertIn("Deploy service definition - Complete", rendered)
        self.assertIn("Items needing attention: 0", rendered)
        self.assertIn("Definition deployed", rendered)
        self.assertIn("reference hidden", rendered)
        self.assertNotIn("2026-10-18T", rendered)
        self.assertNotIn("b" * 32, rendered)
        self.assertNotIn("a" * 32, rendered)

    def test_managed_ssh_preview_is_typed_and_targets_only_8023(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
            "plan_id": "c" * 64, "requires_confirmation": True,
            "impact": "Starts only the fixed managed unit."}}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["ssh-preview-start"]), 0)
        dispatch.assert_called_once_with("ssh.service.start", {"confirmed": False, "plan_id": None})
        self.assertIn("P\t" + "c" * 64 + "\ttrue", output.getvalue())

    def test_managed_ssh_restart_bridge_uses_shared_preview_and_apply(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
            "plan_id": "e" * 64, "requires_confirmation": True,
            "impact": "Restart may disconnect 8023 clients."}}) as dispatch:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(bridge.main(["ssh-preview-restart"]), 0)
        dispatch.assert_called_once_with("ssh.service.restart", {"confirmed": False, "plan_id": None})
        self.assertIn("P\t" + "e" * 64 + "\ttrue", output.getvalue())
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"status": "running"}}) as dispatch:
            with redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(["ssh-apply-restart", "confirmed", "e" * 64]), 0)
        dispatch.assert_called_once_with("ssh.service.restart", {"confirmed": True, "plan_id": "e" * 64})

    def test_managed_ssh_apply_requires_exact_plan_and_confirmation(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"status": "stopped"}}) as dispatch:
            with redirect_stdout(StringIO()):
                self.assertEqual(bridge.main(["ssh-apply-stop", "confirmed", "d" * 64]), 0)
        dispatch.assert_called_once_with("ssh.service.stop", {"confirmed": True, "plan_id": "d" * 64})
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["ssh-apply-stop", "confirmed", "bad-plan"]), 2)
        dispatch.assert_not_called()

    def test_unknown_bridge_action_cannot_become_a_shell_command(self) -> None:
        error = StringIO()
        with mock.patch("sys.stderr", error):
            self.assertEqual(bridge.main(["run", "arbitrary command"]), 2)
        self.assertIn("Unsupported typed management action", error.getvalue())

    def test_proot_bridge_status_and_session_actions_use_shared_service(self) -> None:
        for action, operation in (("proot-status", "proot.status"),
                                  ("proot-profile-list", "proot.profiles.list"),
                                  ("proot-session-list", "proot.sessions.list")):
            with self.subTest(action=action), mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as call:
                self.assertEqual(bridge.main([action]), 0)
                self.assertEqual(call.call_args.args[0], operation)

    def test_terminal_service_controls_use_exact_shared_previews_and_confirmation(self):
        with mock.patch.object(bridge, "call", side_effect=[
                {"ok": True, "data": {"installed": True, "status": "stopped"}},
                {"ok": True, "data": {"plan_id": "a" * 64, "impact": "Starts broker"}}]) as dispatch, \
                redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["terminal-service-prepare"]), 0)
        self.assertEqual([item.args[0] for item in dispatch.call_args_list], [
            "terminal.broker.service.status", "terminal.broker.service.start.preview"])
        self.assertIn("P\t" + "a" * 64 + "\tstart\t", output.getvalue())
        with mock.patch.object(bridge, "call", side_effect=[
                {"ok": True, "data": {"installed": False}},
                {"ok": True, "data": {"plan_id": "c" * 64, "impact": "Installs broker"}}]) as dispatch, \
                redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["terminal-service-prepare"]), 0)
        self.assertEqual(dispatch.call_args.args[0], "terminal.broker.service.install.preview")
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"installed": True, "status": "running"}}) as dispatch, \
                redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["terminal-service-prepare"]), 0)
        self.assertEqual(dispatch.call_args.args[0], "terminal.broker.service.status")
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"status": "running"}}) as dispatch, \
                redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["terminal-service-apply", "confirmed", "start", "b" * 64]), 0)
        dispatch.assert_called_once_with("terminal.broker.service.start.apply", {"confirmed": True, "plan_id": "b" * 64})
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["terminal-service-apply", "confirmed", "start", "../bad"]), 2)
        dispatch.assert_not_called()

    def test_gtk_guest_app_launch_uses_shared_typed_service_and_rejects_bad_ids(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-app-launch", "firefox"]), 0)
        dispatch.assert_called_once_with("proot.app.launch", {"app_id": "firefox", "display": ":1"})
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-app-launch", "../../x"]), 2)
        dispatch.assert_not_called()

    def test_gtk_guest_shortcut_list_uses_shared_service(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"shortcuts": []}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-shortcut-list"]), 0)
        dispatch.assert_called_once_with("proot.shortcuts.list")

    def test_gtk_guest_shortcut_uses_preview_confirmation_plan(self) -> None:
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
                "plan_id": "a" * 24, "changed": True, "name": "Firefox",
                "affected_resources": [{"path": "applications/firefox.desktop"}]}}) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["proot-shortcut-preview", "add", "firefox"]), 0)
        dispatch.assert_called_once_with("proot.shortcuts.preview", {"action": "add", "app_id": "firefox"})
        self.assertEqual(output.getvalue().strip(), "P\t" + "a" * 24 + "\tFirefox\tapplications/firefox.desktop")
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-shortcut-apply", "remove", "firefox", "b" * 24]), 0)
        dispatch.assert_called_once_with("proot.shortcuts.apply", {"action": "remove", "app_id": "firefox", "confirmed": True, "plan_id": "b" * 24})

    def test_gtk_shortcut_sync_preview_apply_and_rollback_use_exact_service_plans(self) -> None:
        sync_preview = {"ok": True, "data": {"plan_id": "a" * 24, "changed": True,
                        "discovered": 5, "changes": [{}, {}], "conflicts": [{}]}}
        with mock.patch.object(bridge, "call", return_value=sync_preview) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["proot-shortcut-sync-preview"]), 0)
        dispatch.assert_called_once_with("proot.shortcuts.sync.preview")
        self.assertEqual(output.getvalue().strip(), "P\t" + "a" * 24 + "\t5\t2\t1")
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-shortcut-sync-apply", "confirmed", "a" * 24]), 0)
        dispatch.assert_called_once_with("proot.shortcuts.sync.apply", {"confirmed": True, "plan_id": "a" * 24})

        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {"rollbacks": [
                {"rollback_id": "b" * 32, "status": "applied", "integrity": "valid", "entry_count": 2}]}}) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["proot-shortcut-rollback-list"]), 0)
        dispatch.assert_called_once_with("proot.shortcuts.sync.rollback.list")
        self.assertEqual(output.getvalue().strip(), "R\t" + "b" * 32 + "\tapplied\tvalid\t2")
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
                "plan_id": "c" * 24, "requires_confirmation": True, "changes": [{}, {}]}}) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["proot-shortcut-rollback-preview", "b" * 32]), 0)
        dispatch.assert_called_once_with("proot.shortcuts.sync.rollback.preview", {"rollback_id": "b" * 32})
        self.assertEqual(output.getvalue().strip(), "Q\t" + "c" * 24 + "\t" + "b" * 32 + "\t2")
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-shortcut-rollback-apply", "confirmed", "b" * 32, "c" * 24]), 0)
        dispatch.assert_called_once_with("proot.shortcuts.sync.rollback.apply", {"rollback_id": "b" * 32,
            "confirmed": True, "plan_id": "c" * 24})

    def test_gtk_guest_session_stop_requires_verified_preview_plan(self) -> None:
        session_id = "proot-" + "c" * 32
        plan_id = "plan-" + "d" * 64
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {
                "plan_id": plan_id, "impact": "Stop only owned session"}}) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["proot-stop-preview", session_id]), 0)
        dispatch.assert_called_once_with("proot.stop.preview", {"session_id": session_id})
        self.assertEqual(output.getvalue().strip(), "P\t" + plan_id + "\tStop only owned session")
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-stop-apply", session_id, plan_id]), 0)
        dispatch.assert_called_once_with("proot.stop", {"session_id": session_id, "confirmed": True, "plan_id": plan_id})
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-stop-apply", session_id, "plan-" + "d" * 24]), 2)
        dispatch.assert_not_called()
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-stop-preview", "../foreign"]), 2)
        dispatch.assert_not_called()
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-stop-preview", "s-" + "c" * 24]), 2)
        dispatch.assert_not_called()

    def test_gtk_guest_session_reconciliation_uses_exit_evidence_and_exact_plan(self) -> None:
        session_id, plan_id = "proot-" + "e" * 32, "plan-" + "f" * 64
        calls = [{"ok": True, "data": {"status": "unverified"}},
                 {"ok": True, "data": {"plan_id": plan_id, "observed_state": "failed",
                                         "evidence": "process_absent", "action": "mark_exited_without_signal"}},
                 {"ok": True, "data": {"state": "stopped", "signal_sent": False}}]
        with mock.patch.object(bridge, "call", side_effect=calls) as dispatch, redirect_stdout(StringIO()) as output:
            self.assertEqual(bridge.main(["proot-reconcile-preview", session_id]), 0)
        self.assertEqual(dispatch.call_args_list, [mock.call("proot.recovery.inspect", {"session_id": session_id}),
            mock.call("proot.recovery.reconcile.preview", {"session_id": session_id})])
        self.assertIn("P\t" + plan_id, output.getvalue())
        with mock.patch.object(bridge, "call", return_value={"ok": True, "data": {}}) as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-reconcile-apply", session_id, plan_id]), 0)
        dispatch.assert_called_once_with("proot.recovery.reconcile", {"session_id": session_id,
            "confirmed": True, "plan_id": plan_id})
        with mock.patch.object(bridge, "call") as dispatch, redirect_stdout(StringIO()):
            self.assertEqual(bridge.main(["proot-reconcile-apply", session_id, "plan-" + "f" * 24]), 2)
        dispatch.assert_not_called()

    def test_unregistered_guest_bridge_actions_fail_closed(self) -> None:
        self.assertEqual(bridge.main(["guest-lifecycle-preview"]), 2)



if __name__ == "__main__":
    unittest.main()
