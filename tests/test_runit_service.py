"""Preview-first service-action tests with a synthetic Runit adapter."""

from __future__ import annotations

from pathlib import Path
import subprocess
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import runit_service  # noqa: E402
import operation_journal  # noqa: E402


class FakeRunit:
    def __init__(self, state: str = "stopped", *, fail_action: bool = False, status_path: str | None = None):
        self.state = state
        self.calls: list[list[str]] = []
        self.fail_action = fail_action
        self.status_path = status_path or "ternuxx-sshd"

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[1] == "status":
            prefix = "run" if self.state == "running" else "down"
            return subprocess.CompletedProcess(args, 0, f"{prefix}: {self.status_path}: fixture\n", "")
        if self.fail_action:
            raise subprocess.TimeoutExpired(args, 8)
        self.state = "running" if args[1] == "up" else "stopped"
        return subprocess.CompletedProcess(args, 0, "", "")


class RunitServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-runit-action-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.state = self.home / ".local/share/ternuxx"
        self.prefix = self.root / "prefix"
        (self.prefix / "var/service/ternuxx-sshd").mkdir(parents=True)
        (self.prefix / "bin").mkdir()
        (self.prefix / "bin/sv").write_text("fixture manager\n", encoding="utf-8")
        (self.prefix / "bin/sv").chmod(0o700)
        self.source = self.root / "source-run"
        self.source.write_text("#!/bin/sh\nexec sshd\n", encoding="utf-8")
        installed = self.prefix / "var/service/ternuxx-sshd/run"
        installed.write_bytes(self.source.read_bytes())
        installed.chmod(0o700)
        self.runner = FakeRunit()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_preview_and_apply_response_fields_match_schema_variants(self) -> None:
        schema = json.loads((ROOT / "schemas/native-ssh-service-action.schema.json").read_text())
        preview_schema, applied_schema = schema["oneOf"]
        preview = runit_service.preview("start", prefix=self.prefix, source=self.source, runner=self.runner)
        self.assertEqual(set(preview), set(preview_schema["required"]))
        self.assertEqual(preview["service_id"], preview_schema["properties"]["service_id"]["const"])
        self.assertRegex(str(preview["plan_id"]), preview_schema["properties"]["plan_id"]["pattern"])

        applied = runit_service.apply(
            "start", prefix=self.prefix, home=self.home, state_dir=self.state,
            confirmed=True, plan_id=str(preview["plan_id"]), source=self.source, runner=self.runner,
        )
        self.assertEqual(set(applied), set(applied_schema["required"]))
        self.assertRegex(applied["operation_id"], applied_schema["properties"]["operation_id"]["pattern"])

    def test_start_preview_apply_and_journal_are_exact_and_fixed(self) -> None:
        plan = runit_service.preview("start", prefix=self.prefix, source=self.source, runner=self.runner)
        self.assertEqual(plan["service_id"], "ternuxx-sshd")
        self.assertEqual(plan["current_status"], "stopped")
        self.assertTrue(plan["requires_confirmation"])
        self.assertFalse(plan["changed"])
        self.assertFalse(any(call[1] in {"up", "down"} for call in self.runner.calls))

        preview_result = runit_service.apply(
            "start", prefix=self.prefix, home=self.home, state_dir=self.state,
            confirmed=False, plan_id=None, source=self.source, runner=self.runner,
        )
        self.assertEqual(preview_result["plan_id"], plan["plan_id"])
        self.assertEqual(self.runner.state, "stopped")

        result = runit_service.apply(
            "start", prefix=self.prefix, home=self.home, state_dir=self.state,
            confirmed=True, plan_id=str(plan["plan_id"]), source=self.source, runner=self.runner,
        )
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["service_id"], "ternuxx-sshd")
        actions = [call[1:] for call in self.runner.calls if call[1] in {"up", "down"}]
        self.assertEqual(actions, [["up", str(self.prefix / "var/service/ternuxx-sshd")]])
        record = operation_journal.inspect_record(str(self.state), result["operation_id"], home_dir=self.home)
        self.assertEqual(record["kind"], "service.start")
        self.assertEqual(record["status"], "complete")

    def test_stop_controls_only_fixed_unit_and_records_stopped_state(self) -> None:
        self.runner.state = "running"
        plan = runit_service.preview("stop", prefix=self.prefix, source=self.source, runner=self.runner)
        result = runit_service.apply(
            "stop", prefix=self.prefix, home=self.home, state_dir=self.state,
            confirmed=True, plan_id=str(plan["plan_id"]), source=self.source, runner=self.runner,
        )
        self.assertEqual(result["status"], "stopped")
        self.assertEqual([call[1:] for call in self.runner.calls if call[1] in {"up", "down"}],
                         [["down", str(self.prefix / "var/service/ternuxx-sshd")]])
        record = operation_journal.inspect_record(str(self.state), result["operation_id"], home_dir=self.home)
        self.assertEqual(record["kind"], "service.stop")
        self.assertEqual(record["status"], "complete")

    def test_status_accepts_exact_native_absolute_service_path(self) -> None:
        full_path = str(self.prefix / "var/service/ternuxx-sshd")
        runner = FakeRunit("running", status_path=full_path)
        plan = runit_service.preview("restart", prefix=self.prefix, source=self.source, runner=runner)
        self.assertEqual(plan["current_status"], "running")
        runner.status_path = str(self.prefix / "var/service/other-service")
        with self.assertRaisesRegex(runit_service.ServiceActionError, "unknown service state"):
            runit_service.preview("restart", prefix=self.prefix, source=self.source, runner=runner)

    def test_restart_always_requires_confirmation_and_only_restarts_fixed_unit(self) -> None:
        self.runner.state = "running"
        plan = runit_service.preview("restart", prefix=self.prefix, source=self.source, runner=self.runner)
        self.assertEqual(plan["target_status"], "running")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("Other Native SSH services are excluded", plan["impact"])
        result = runit_service.apply(
            "restart", prefix=self.prefix, home=self.home, state_dir=self.state,
            confirmed=True, plan_id=str(plan["plan_id"]), source=self.source, runner=self.runner,
        )
        self.assertEqual(result["status"], "running")
        actions = [call[1:] for call in self.runner.calls if call[1] in {"up", "down"}]
        self.assertEqual(actions, [["down", str(self.prefix / "var/service/ternuxx-sshd")], ["up", str(self.prefix / "var/service/ternuxx-sshd")]])
        record = operation_journal.inspect_record(str(self.state), result["operation_id"], home_dir=self.home)
        self.assertEqual(record["kind"], "service.restart")
        self.assertEqual(record["status"], "complete")

    def test_plan_state_change_and_definition_mismatch_fail_before_action(self) -> None:
        plan = runit_service.preview("start", prefix=self.prefix, source=self.source, runner=self.runner)
        self.runner.state = "running"
        with self.assertRaises(runit_service.ServiceActionError):
            runit_service.apply(
                "start", prefix=self.prefix, home=self.home, state_dir=self.state,
                confirmed=True, plan_id=str(plan["plan_id"]), source=self.source, runner=self.runner,
            )
        self.assertFalse(any(call[1] in {"up", "down"} for call in self.runner.calls))

        self.runner.state = "stopped"
        installed = self.prefix / "var/service/ternuxx-sshd/run"
        installed.write_text("#!/bin/sh\necho changed\n", encoding="utf-8")
        with self.assertRaises(runit_service.ServiceActionError):
            runit_service.preview("start", prefix=self.prefix, source=self.source, runner=self.runner)
        self.assertFalse(any(call[1] in {"up", "down"} for call in self.runner.calls))

    def test_missing_confirmation_wrong_plan_and_noop_never_mutate(self) -> None:
        plan = runit_service.preview("start", prefix=self.prefix, source=self.source, runner=self.runner)
        with self.assertRaises(runit_service.ServiceActionError):
            runit_service.apply(
                "start", prefix=self.prefix, home=self.home, state_dir=self.state,
                confirmed=True, plan_id="0" * 64, source=self.source, runner=self.runner,
            )
        no_op_state = FakeRunit("running")
        no_op = runit_service.preview("start", prefix=self.prefix, source=self.source, runner=no_op_state)
        self.assertFalse(no_op["requires_confirmation"])
        self.assertIsNone(no_op["plan_id"])
        self.assertEqual(no_op_state.calls, [[str(self.prefix / "bin/sv"), "status", str(self.prefix / "var/service/ternuxx-sshd")]])
        noop_result = runit_service.apply(
            "start", prefix=self.prefix, home=self.home, state_dir=self.state,
            confirmed=False, plan_id=None, source=self.source, runner=no_op_state,
        )
        self.assertFalse(noop_result["requires_confirmation"])
        self.assertFalse((self.state / "operations").exists())
        self.assertFalse(any(call[1] in {"up", "down"} for call in self.runner.calls))
        self.assertFalse(any(call[1] in {"up", "down"} for call in no_op_state.calls))

    def test_uncertain_timeout_is_journaled_for_recovery_and_blocks_retry(self) -> None:
        runner = FakeRunit(fail_action=True)
        plan = runit_service.preview("start", prefix=self.prefix, source=self.source, runner=runner)
        with self.assertRaises(runit_service.ServiceActionError):
            runit_service.apply(
                "start", prefix=self.prefix, home=self.home, state_dir=self.state,
                confirmed=True, plan_id=str(plan["plan_id"]), source=self.source, runner=runner,
            )
        records = operation_journal.list_records(str(self.state), home_dir=self.home)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "service.start")
        self.assertEqual(records[0]["status"], "needs_recovery")
        self.assertEqual([call[1:] for call in runner.calls if call[1] in {"up", "down"}],
                         [["up", str(self.prefix / "var/service/ternuxx-sshd")]])
        retry_plan = runit_service.preview("start", prefix=self.prefix, source=self.source, runner=runner)
        with self.assertRaises(RuntimeError):
            runit_service.apply(
                "start", prefix=self.prefix, home=self.home, state_dir=self.state,
                confirmed=True, plan_id=str(retry_plan["plan_id"]), source=self.source, runner=runner,
            )
        self.assertEqual(len([call for call in runner.calls if call[1] in {"up", "down"}]), 1)


if __name__ == "__main__":
    unittest.main()
