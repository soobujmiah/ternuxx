from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import boot_helpers  # noqa: E402


NOW = dt.datetime(2026, 10, 21, 10, 0, tzinfo=dt.timezone.utc)


class BootHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ternuxx-boot-helper-")
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.state = self.home / ".local/share/ternuxx"
        self.boot = self.home / ".termux/boot"
        self.boot.mkdir(parents=True)
        self.source_root = Path(self.tmp.name) / "repo"
        for helper_id, (filename, rel) in boot_helpers.HELPERS.items():
            source = self.source_root / rel
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("#!/bin/sh\n# current " + helper_id + "\n", encoding="utf-8")
            source.chmod(0o755)
            target = self.boot / filename
            target.write_text("#!/bin/sh\n# legacy " + helper_id + "\n", encoding="utf-8")
            target.chmod(0o700)
        self.legacy = {
            key: hashlib.sha256((self.boot / item[0]).read_bytes()).hexdigest()
            for key, item in boot_helpers.HELPERS.items()
        }
        self.allowlist = mock.patch.dict(boot_helpers.KNOWN_LEGACY, self.legacy)
        self.allowlist.start()

    def tearDown(self) -> None:
        self.allowlist.stop()
        self.tmp.cleanup()

    def call_preview(self, helper_id: str, action: str, snapshot_id: str | None = None, now=NOW):
        return boot_helpers.preview(helper_id=helper_id, action=action, home=self.home,
            state_dir=self.state, source_root=self.source_root, snapshot_id=snapshot_id, now=now)

    def call_apply(self, preview: dict, helper_id: str, action: str, snapshot_id: str | None = None, now=NOW):
        return boot_helpers.apply(helper_id=helper_id, action=action, home=self.home,
            state_dir=self.state, source_root=self.source_root, confirmed=True,
            plan_id=preview["plan"]["plan_id"], snapshot_id=snapshot_id, now=now)

    def test_deploy_creates_private_snapshot_then_exact_rollback_restores_original(self) -> None:
        original = (self.boot / boot_helpers.HELPERS["services"][0]).read_bytes()
        preview = self.call_preview("services", "deploy")
        plan = preview["plan"]
        self.assertEqual(preview["before"].encode(), original)
        self.assertIn("# current services", preview["after"])
        result = self.call_apply(preview, "services", "deploy", now=NOW + dt.timedelta(seconds=1))
        target = self.boot / boot_helpers.HELPERS["services"][0]
        self.assertEqual(target.read_text(), (self.source_root / boot_helpers.HELPERS["services"][1]).read_text())
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        snapshot = result["snapshot_id"]
        backup = self.state / "boot/helpers/snapshots" / f"services-{snapshot}.bin"
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        status = boot_helpers.status(home=self.home, state_dir=self.state, source_root=self.source_root)
        self.assertEqual(status["snapshot_count"], 1)
        self.assertEqual(status["snapshots"][0]["snapshot_id"], snapshot)
        self.assertEqual(status["snapshots"][0]["helper_id"], "services")
        self.assertEqual(status["snapshots"][0]["mode"], "0700")
        rollback = self.call_preview("services", "rollback", snapshot, NOW + dt.timedelta(seconds=2))
        restored = self.call_apply(rollback, "services", "rollback", snapshot, NOW + dt.timedelta(seconds=3))
        self.assertTrue(restored["changed"])
        self.assertEqual(target.read_bytes(), original)

    def test_unknown_target_stale_plan_and_source_drift_are_refused(self) -> None:
        target = self.boot / boot_helpers.HELPERS["recovery"][0]
        target.write_text("# owner customization\n")
        target.chmod(0o700)
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "unrecognized"):
            self.call_preview("recovery", "deploy")
        target.write_text("#!/bin/sh\n# legacy recovery\n")
        target.chmod(0o700)
        preview = self.call_preview("recovery", "deploy")
        target.write_text("# changed after preview\n")
        target.chmod(0o700)
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "target changed"):
            self.call_apply(preview, "recovery", "deploy")
        target.write_text("#!/bin/sh\n# legacy recovery\n")
        target.chmod(0o700)
        preview = self.call_preview("recovery", "deploy")
        (self.source_root / boot_helpers.HELPERS["recovery"][1]).write_text("# changed source\n")
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "helper changed"):
            self.call_apply(preview, "recovery", "deploy")

    def test_expired_plan_confirmation_and_symlink_are_refused(self) -> None:
        preview = self.call_preview("services", "deploy")
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "expired"):
            self.call_apply(preview, "services", "deploy",
                now=NOW + dt.timedelta(seconds=boot_helpers.PLAN_TTL + 1))
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "explicit confirmation"):
            boot_helpers.apply(helper_id="services", action="deploy", home=self.home,
                state_dir=self.state, source_root=self.source_root, confirmed=False,
                plan_id=preview["plan"]["plan_id"])
        target = self.boot / boot_helpers.HELPERS["services"][0]
        target.unlink()
        target.symlink_to(self.home / "outside")
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "same-user regular"):
            self.call_preview("services", "deploy")

    def test_state_ancestor_symlink_and_snapshot_path_traversal_are_refused(self) -> None:
        outside = Path(self.tmp.name) / "outside-state"
        outside.mkdir()
        (self.home / ".local").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "symbolic link"):
            self.call_preview("services", "deploy")
        (self.home / ".local").unlink()
        preview = self.call_preview("services", "deploy")
        deployed = self.call_apply(preview, "services", "deploy")
        index_path = self.state / "boot/helpers/snapshots.json"
        index = json.loads(index_path.read_text())
        index["items"][deployed["snapshot_id"]]["file"] = "../../outside"
        index_path.write_text(json.dumps(index))
        index_path.chmod(0o600)
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "snapshot path is invalid"):
            self.call_preview("services", "rollback", deployed["snapshot_id"])

    def test_corrupt_plan_index_fails_closed_and_original_mode_is_restored(self) -> None:
        target = self.boot / boot_helpers.HELPERS["services"][0]
        target.chmod(0o740)
        preview = self.call_preview("services", "deploy")
        deployed = self.call_apply(preview, "services", "deploy")
        rollback = self.call_preview("services", "rollback", deployed["snapshot_id"])
        plans_path = self.state / "boot/helpers/plans.json"
        plans_path.write_text("[]")
        plans_path.chmod(0o600)
        with self.assertRaisesRegex(boot_helpers.BootHelperError, "plan store is invalid"):
            self.call_apply(rollback, "services", "rollback", deployed["snapshot_id"])
        plans_path.write_text(json.dumps({"schema_version": 1, "items": []}))
        plans_path.chmod(0o600)
        rollback = self.call_preview("services", "rollback", deployed["snapshot_id"])
        restored = self.call_apply(rollback, "services", "rollback", deployed["snapshot_id"])
        self.assertTrue(restored["changed"])
        self.assertEqual(target.stat().st_mode & 0o777, 0o740)

    def test_concurrent_apply_of_same_preview_has_one_winner(self) -> None:
        preview = self.call_preview("services", "deploy")
        start = threading.Barrier(3)
        successes = []
        failures = []

        def apply_same_plan() -> None:
            start.wait(timeout=3)
            try:
                successes.append(self.call_apply(preview, "services", "deploy"))
            except boot_helpers.BootHelperError as exc:
                failures.append(exc)

        workers = [threading.Thread(target=apply_same_plan) for _ in range(2)]
        for worker in workers:
            worker.start()
        start.wait(timeout=3)
        for worker in workers:
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        target = self.boot / boot_helpers.HELPERS["services"][0]
        source = self.source_root / boot_helpers.HELPERS["services"][1]
        self.assertEqual(target.read_bytes(), source.read_bytes())
        snapshot_index = json.loads((self.state / "boot/helpers/snapshots.json").read_text())
        self.assertEqual(len(snapshot_index["items"]), 1)

    def test_status_reads_only_fixed_helpers_without_creating_state(self) -> None:
        result = boot_helpers.status(home=self.home, state_dir=self.state, source_root=self.source_root)
        self.assertEqual([row["identity"] for row in result["helpers"]], ["known-legacy", "known-legacy"])
        self.assertFalse(self.state.exists())
        self.assertTrue(result["read_only"])


if __name__ == "__main__":
    unittest.main()
