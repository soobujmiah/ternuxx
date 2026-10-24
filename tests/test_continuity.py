"""Host-side tests for private native continuity checkpoints and lease policy."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import continuity  # noqa: E402
from resource_ownership import ResourceOwnership  # noqa: E402


BOOT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
BOOT_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class ContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-continuity-")
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir(mode=0o700)
        self.state = self.home / ".local/share/ternuxx"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def prepare(self, **kwargs: object) -> dict[str, object]:
        boot_id = kwargs.pop("boot_id", BOOT_A)
        test_id = kwargs.pop("test_id", "reboot-native-independence")
        pending_tests = kwargs.pop("pending_tests", ["native-ssh-without-proot", "owner-verifies-reboot"])
        return continuity.prepare(
            home=self.home,
            state_dir=self.state,
            test_id=test_id,
            repository="soobujmiah/ternuxx",
            commit="abcdef0123456",
            worktree_state="dirty",
            boot_id=boot_id,
            pending_tests=pending_tests,
            **kwargs,
        )

    def checkpoint_path(self, checkpoint_id: str) -> Path:
        return self.state / "continuity/checkpoints" / f"{checkpoint_id}.json"

    def test_checkpoint_is_private_unique_and_never_resumes_tasks(self) -> None:
        result = self.prepare()
        checkpoint = self.checkpoint_path(str(result["checkpoint_id"]))
        record = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(checkpoint.stat().st_mode & 0o777, 0o600)
        self.assertEqual(checkpoint.parent.stat().st_mode & 0o777, 0o700)
        self.assertGreaterEqual(len(record["nonce"]), 32)
        self.assertEqual(record["task"]["automatic_resume"], False)
        self.assertEqual(record["task"]["pending_tests"], ["native-ssh-without-proot", "owner-verifies-reboot"])

    def test_checkpoint_previews_are_readonly_and_verification_plan_binds_record(self) -> None:
        plan = continuity.prepare_preview(home=self.home, state_dir=self.state, test_id="preview-checkpoint", boot_id=BOOT_A)
        self.assertTrue(plan["read_only"])
        self.assertFalse((self.state / "continuity/checkpoints").exists())
        created = continuity.prepare(home=self.home, state_dir=self.state, test_id="preview-checkpoint", boot_id=BOOT_A)
        checkpoint_id = str(created["checkpoint_id"])
        preview = continuity.verify_preview(home=self.home, state_dir=self.state, checkpoint_id=checkpoint_id,
                                            current_boot_id=BOOT_B)
        self.assertEqual(preview["details"]["outcome"], "reboot_detected")
        self.assertFalse((self.state / "continuity/checkpoints/verification").exists())
        checkpoint = self.checkpoint_path(checkpoint_id)
        record = json.loads(checkpoint.read_text(encoding="utf-8"))
        record["task"]["pending_tests"] = ["changed-after-preview"]
        checkpoint.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(continuity.CheckpointError, "changed after preview"):
            continuity.verify(home=self.home, state_dir=self.state, checkpoint_id=checkpoint_id,
                              current_boot_id=BOOT_B, expected_record_sha256=preview["details"]["record_sha256"])
        self.assertFalse((self.state / "continuity/checkpoints/verification").exists())

    def test_verify_distinguishes_reboot_and_records_no_automatic_resume(self) -> None:
        result = self.prepare()
        verified = continuity.verify(
            home=self.home,
            state_dir=self.state,
            checkpoint_id=str(result["checkpoint_id"]),
            current_boot_id=BOOT_B,
        )
        self.assertEqual(verified["outcome"], "reboot_detected")
        self.assertFalse(verified["automatic_resume"])
        evidence = list((self.state / "continuity/checkpoints/verification").glob("*.json"))
        self.assertEqual(len(evidence), 1)
        record = json.loads(evidence[0].read_text(encoding="utf-8"))
        self.assertEqual(record["service_readiness"], "not_collected")
        self.assertEqual(record["current_boot_id"], BOOT_B)

    def test_same_boot_and_missing_boot_id_are_not_misreported_as_reboot(self) -> None:
        same = self.prepare(test_id="same-boot")
        same_result = continuity.verify(
            home=self.home, state_dir=self.state,
            checkpoint_id=str(same["checkpoint_id"]), current_boot_id=BOOT_A,
        )
        self.assertEqual(same_result["outcome"], "same_boot")

        unknown = self.prepare(test_id="unknown-boot", boot_id=None)
        # This call injects no current ID but read_boot_id() may exist on the
        # host, so directly assert the pure decision through unavailable IDs.
        old_reader = continuity.read_boot_id
        continuity.read_boot_id = lambda: None
        try:
            unknown_result = continuity.verify(
                home=self.home, state_dir=self.state,
                checkpoint_id=str(unknown["checkpoint_id"]), current_boot_id=None,
            )
        finally:
            continuity.read_boot_id = old_reader
        self.assertEqual(unknown_result["outcome"], "boot_id_unavailable")

    def test_duplicate_or_invalid_checkpoint_is_rejected(self) -> None:
        result = self.prepare()
        checkpoint = self.checkpoint_path(str(result["checkpoint_id"]))
        original = checkpoint.read_bytes()
        with self.assertRaises(continuity.CheckpointError):
            continuity._atomic_write(checkpoint, {"different": True}, exclusive=True)
        self.assertEqual(checkpoint.read_bytes(), original)
        with self.assertRaises(continuity.CheckpointError):
            self.prepare(test_id="invalid id")
        with self.assertRaises(continuity.CheckpointError):
            self.prepare(pending_tests=["duplicate", "duplicate"])

    def test_corrupt_checkpoint_is_rejected_before_evidence_is_written(self) -> None:
        result = self.prepare()
        checkpoint = self.checkpoint_path(str(result["checkpoint_id"]))
        record = json.loads(checkpoint.read_text(encoding="utf-8"))
        record["task"]["automatic_resume"] = True
        checkpoint.write_text(json.dumps(record), encoding="utf-8")
        checkpoint.chmod(0o600)
        with self.assertRaises(continuity.CheckpointError):
            continuity.verify(
                home=self.home, state_dir=self.state,
                checkpoint_id=str(result["checkpoint_id"]), current_boot_id=BOOT_B,
            )
        evidence_dir = self.state / "continuity/checkpoints/verification"
        self.assertFalse(evidence_dir.exists())

    def test_symlinked_state_path_is_rejected(self) -> None:
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        linked = self.home / "linked"
        linked.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(continuity.CheckpointError):
            continuity.prepare(
                home=self.home, state_dir=linked / "state", test_id="symlink-check",
                boot_id=BOOT_A,
            )
        internal_target = self.home / "real-state"
        internal_target.mkdir()
        internal_link = self.home / "linked-inside"
        internal_link.symlink_to(internal_target, target_is_directory=True)
        with self.assertRaises(continuity.CheckpointError):
            continuity.prepare(
                home=self.home, state_dir=internal_link / "state", test_id="symlink-inside",
                boot_id=BOOT_A,
            )


class ResourceOwnershipTests(unittest.TestCase):
    def test_one_environment_cannot_release_another_environments_lease(self) -> None:
        leases = ResourceOwnership()
        self.assertTrue(leases.acquire("wake-lock", "native-ssh"))
        self.assertTrue(leases.acquire("wake-lock", "proot-workload"))
        self.assertFalse(leases.acquire("wake-lock", "native-ssh"))
        self.assertFalse(leases.release("wake-lock", "unknown-owner"))
        self.assertTrue(leases.release("wake-lock", "proot-workload"))
        self.assertTrue(leases.is_required("wake-lock"))
        self.assertEqual(leases.owners("wake-lock"), ("native-ssh",))
        self.assertTrue(leases.release("wake-lock", "native-ssh"))
        self.assertFalse(leases.is_required("wake-lock"))


if __name__ == "__main__":
    unittest.main()
