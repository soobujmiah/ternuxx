from __future__ import annotations

from pathlib import Path
import subprocess
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import fixed_service_deployment  # noqa: E402


class FixtureRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if args[1:2] == ["status"]:
            target = Path(args[2])
            run_file = target / "run"
            if run_file.is_file():
                return subprocess.CompletedProcess(
                    args, 0, f"run: {target}: (pid 123) 2s\n", "")
            return subprocess.CompletedProcess(
                args, 1, f"down: {target}: 1s, normally up, want up\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")


class FixedNativeServiceDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-fixed-service-")
        self.root = Path(self.temp.name)
        self.prefix = self.root / "prefix"
        service_root = self.prefix / "var/service"
        service_root.mkdir(parents=True)
        bin_dir = self.prefix / "bin"
        bin_dir.mkdir()
        self.sv = bin_dir / "sv"
        self.sv.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.sv.chmod(0o700)
        self.source = self.root / "run"
        self.source.write_text("#!/bin/sh\nexec python3 gui_monitoring.py run\n", encoding="utf-8")
        self.source.chmod(0o700)
        self.target = service_root / fixed_service_deployment.MONITOR_SERVICE_ID
        self.runner = FixtureRunner()

    def tearDown(self):
        self.temp.cleanup()

    def preview(self):
        return fixed_service_deployment.preview_install(
            prefix=self.prefix, source=self.source)

    def test_preview_is_read_only_and_requires_exact_confirmation(self):
        plan = self.preview()
        self.assertTrue(plan["read_only"])
        self.assertTrue(plan["requires_confirmation"])
        self.assertEqual(plan["target_state"], "absent")
        self.assertFalse(self.target.exists())
        with self.assertRaises(fixed_service_deployment.ServiceInstallError):
            fixed_service_deployment.install(
                prefix=self.prefix, source=self.source, confirmed=False,
                plan_id=plan["plan_id"], runner=self.runner)
        self.assertFalse(self.target.exists())
        with self.assertRaisesRegex(fixed_service_deployment.ServiceInstallError, "fresh exact"):
            fixed_service_deployment.install(
                prefix=self.prefix, source=self.source, confirmed=True,
                plan_id="wrong", runner=self.runner)
        self.assertFalse(self.target.exists())

    def test_install_creates_only_fixed_service_and_verifies_running(self):
        plan = self.preview()
        result = fixed_service_deployment.install(
            prefix=self.prefix, source=self.source, confirmed=True,
            plan_id=plan["plan_id"], runner=self.runner)
        self.assertEqual(result["status"], "installed")
        self.assertTrue(result["service_started"])
        self.assertFalse(result["guest_started"])
        self.assertFalse(result["wakeup_enabled"])
        self.assertEqual((self.target / "run").read_bytes(), self.source.read_bytes())
        self.assertEqual(fixed_service_deployment.status(
            prefix=self.prefix, runner=self.runner)["status"], "running")

    def test_publish_race_preserves_competing_identical_definition(self):
        plan = self.preview()
        original_open = os.open
        def competitor(path, *args, **kwargs):
            if path != "run":
                return original_open(path, *args, **kwargs)
            self.target.mkdir(exist_ok=True)
            (self.target / "run").write_bytes(self.source.read_bytes())
            (self.target / "user-data").write_text("preserve")
            raise FileExistsError("competing registration")
        with patch.object(fixed_service_deployment.os, "open", side_effect=competitor):
            with self.assertRaises((OSError, fixed_service_deployment.ServiceInstallError)):
                fixed_service_deployment.install(
                    prefix=self.prefix, source=self.source, confirmed=True,
                    plan_id=plan["plan_id"], runner=self.runner)
        self.assertEqual((self.target / "run").read_bytes(), self.source.read_bytes())
        self.assertEqual((self.target / "user-data").read_text(), "preserve")
        self.assertFalse(any(call[1] == "down" for call in self.runner.calls))

    def test_monitor_is_fixed_allowlisted_and_does_not_change_policy(self):
        monitor = fixed_service_deployment.MONITOR_SERVICE_ID
        policy = self.root / "gui-monitoring.json"
        policy.write_text('{"enabled":false}')
        plan = fixed_service_deployment.preview_install(
            prefix=self.prefix, source=self.source, service_id=monitor)
        result = fixed_service_deployment.install(
            prefix=self.prefix, source=self.source, service_id=monitor,
            confirmed=True, plan_id=plan["plan_id"], runner=self.runner)
        self.assertEqual(result["service_id"], monitor)
        self.assertTrue(self.target.is_dir())
        self.assertEqual(policy.read_text(), '{"enabled":false}')
        for service_id in ("ssh", "../ternuxx-gui-monitor", "custom", "/tmp/service"):
            with self.subTest(service=service_id), self.assertRaisesRegex(
                    fixed_service_deployment.ServiceInstallError, "unsupported"):
                fixed_service_deployment.preview_install(
                    prefix=self.prefix, source=self.source, service_id=service_id)

    def test_terminal_broker_service_uses_the_shared_fixed_service_installer(self):
        service_id = fixed_service_deployment.TERMINAL_BROKER_SERVICE_ID
        source = ROOT / "scripts/termux-services" / service_id / "run"
        plan = fixed_service_deployment.preview_install(prefix=self.prefix, service_id=service_id)
        self.assertEqual(plan["service_id"], service_id)
        self.assertTrue(plan["read_only"])
        result = fixed_service_deployment.install(prefix=self.prefix, service_id=service_id,
            confirmed=True, plan_id=plan["plan_id"], runner=self.runner)
        self.assertEqual(result["status"], "installed")
        self.assertFalse(result["guest_started"])
        target = self.prefix / "var/service" / service_id / "run"
        self.assertEqual(target.read_bytes(), source.read_bytes())
        status = fixed_service_deployment.status(prefix=self.prefix, runner=self.runner, service_id=service_id)
        self.assertEqual(status["status"], "running")

    def test_terminal_broker_start_requires_exact_preview_and_does_not_start_guest(self):
        service_id = fixed_service_deployment.TERMINAL_BROKER_SERVICE_ID
        source = ROOT / "scripts/termux-services" / service_id / "run"
        target = self.prefix / "var/service" / service_id
        target.mkdir(mode=0o700)
        (target / "run").write_bytes(source.read_bytes())
        (target / "run").chmod(0o700)
        supervise = target / "supervise"
        supervise.mkdir(mode=0o700)
        for name in ("control", "ok"):
            (supervise / name).touch(mode=0o600)
        running = False
        calls = []
        def runner(args, **kwargs):
            nonlocal running
            calls.append(args)
            if args[1] == "up":
                running = True
                return subprocess.CompletedProcess(args, 0, "", "")
            state = "run" if running else "down"
            return subprocess.CompletedProcess(args, 0 if running else 1,
                f"{state}: {target}: (pid 123) 2s\n", "")
        plan = fixed_service_deployment.preview_start(prefix=self.prefix, runner=runner,
            service_id=service_id)
        self.assertEqual(plan["current_status"], "stopped")
        with self.assertRaisesRegex(fixed_service_deployment.ServiceInstallError, "stale"):
            fixed_service_deployment.start_service(prefix=self.prefix, runner=runner,
                service_id=service_id, confirmed=True, plan_id="stale")
        result = fixed_service_deployment.start_service(prefix=self.prefix, runner=runner,
            service_id=service_id, confirmed=True, plan_id=plan["plan_id"])
        self.assertEqual(result["status"], "running")
        self.assertFalse(result["guest_started"])
        self.assertIn([str(self.prefix / "bin/sv"), "up", str(target)], calls)
        self.assertEqual((target / "run").read_bytes(), source.read_bytes())

    def test_changed_source_invalidates_preview(self):
        plan = self.preview()
        self.source.write_text("#!/bin/sh\nexit 1\n")
        with self.assertRaisesRegex(fixed_service_deployment.ServiceInstallError, "fresh exact"):
            fixed_service_deployment.install(
                prefix=self.prefix, source=self.source, confirmed=True,
                plan_id=plan["plan_id"], runner=self.runner)
        self.assertFalse(self.target.exists())

    def test_failed_start_rolls_back_only_own_run_and_retains_when_stop_fails(self):
        for stop_fails in (False, True):
            with self.subTest(stop_fails=stop_fails):
                plan = self.preview()
                def fail(args, **kwargs):
                    return subprocess.CompletedProcess(args, int(args[1] == "up" or stop_fails), "", "")
                with patch.object(fixed_service_deployment.time, "sleep"), \
                     self.assertRaisesRegex(fixed_service_deployment.ServiceInstallError, "start"):
                    fixed_service_deployment.install(
                        prefix=self.prefix, source=self.source, confirmed=True,
                        plan_id=plan["plan_id"], runner=fail)
                self.assertEqual((self.target / "run").exists(), stop_fails)

    def test_runit_discovery_delay_is_retried_before_reporting_failure(self):
        plan = self.preview()
        calls = []
        def runner(args, **kwargs):
            if args[1] == "up":
                calls.append(args)
                if len(calls) < 3:
                    return subprocess.CompletedProcess(args, 1, "", "supervisor not yet discovered")
            return self.runner(args, **kwargs)
        with patch.object(fixed_service_deployment.time, "sleep"):
            result = fixed_service_deployment.install(prefix=self.prefix, source=self.source,
                confirmed=True, plan_id=plan["plan_id"], runner=runner)
        self.assertTrue(result["service_started"])
        self.assertEqual(len(calls), 3)

    def test_install_lock_prevents_reentrant_registration(self):
        plan = self.preview()
        def runner(args, **kwargs):
            if args[1] == "up":
                with self.assertRaisesRegex(fixed_service_deployment.ServiceInstallError, "holds.*lock"):
                    fixed_service_deployment.install(
                        prefix=self.prefix, source=self.source, confirmed=True,
                        plan_id=plan["plan_id"], runner=self.runner)
            return self.runner(args, **kwargs)
        fixed_service_deployment.install(prefix=self.prefix, source=self.source,
            confirmed=True, plan_id=plan["plan_id"], runner=runner)

    def test_symlink_target_is_refused_in_status_and_preview(self):
        other = self.root / "other"
        other.mkdir()
        self.target.symlink_to(other, target_is_directory=True)
        for call in (self.preview, lambda: fixed_service_deployment.status(
                prefix=self.prefix, runner=self.runner)):
            with self.assertRaisesRegex(fixed_service_deployment.ServiceInstallError, "identity"):
                call()
        self.assertEqual(list(other.iterdir()), [])

    def test_shell_syntax_is_checked_on_actual_source_content(self):
        self.source.write_text("#!/bin/sh\nif then\n")
        with self.assertRaisesRegex(fixed_service_deployment.ServiceInstallError, "syntax"):
            self.preview()

    def test_existing_non_supervisor_target_is_never_adopted(self):
        self.target.mkdir()
        (self.target / "user-data").write_text("preserve", encoding="utf-8")
        before = (self.target / "user-data").read_bytes()
        with self.assertRaisesRegex(fixed_service_deployment.ServiceInstallError, "not an empty Runit supervisor"):
            self.preview()
        self.assertEqual((self.target / "user-data").read_bytes(), before)
        self.assertFalse((self.target / "run").exists())


if __name__ == "__main__":
    unittest.main()
