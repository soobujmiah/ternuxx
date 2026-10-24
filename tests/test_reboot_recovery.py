"""Mock tests for the Native Termux reboot recovery evidence lifecycle."""

from __future__ import annotations

import json
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import continuity  # noqa: E402
import reboot_recovery  # noqa: E402


BOOT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
BOOT_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def evidence() -> dict[str, object]:
    return {
        "native": {"termux_version": "test-version"},
        "repository": {"id": "soobujmiah/ternuxx", "branch": "main", "commit": "abcdef0123456",
                       "modified_paths": 42, "untracked_paths": 12},
        "stage": "native-diagnostics-and-checkpoint-implemented",
        "references": ["lib/reboot_recovery.py", "docs/architecture/SSH-LIFECYCLE.md"],
        "ssh": {"sshd_process": "present", "auth_modes": ["password", "publickey"],
                "config_syntax": "valid", "socket_binding": "unverified", "boot_policy": "not_configured"},
        "termux_boot": {"app": "installed", "script_directory": "absent", "startup_policy": "not_configured"},
        "wake_lock": {"cli_available": True, "launcher_acquire_request": True,
                       "launcher_global_release_request": True, "ownership": "global_unscoped"},
        "required_postboot_checks": ["boot_id_changed", "termux_boot_observed", "native_sshd_ready", "db_preserved"],
        "recovery_instructions": ["Open native Termux and inspect service readiness."],
        "rollback_instructions": ["Remove only the Ternuxx-owned boot observer after preserving its evidence."],
        "next_action": "resolve_boot_and_wakelock_blockers_before_reboot",
    }


class RebootRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ternuxx-reboot-test-")
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir(mode=0o700)
        self.state = self.home / ".local/share/ternuxx"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def prepare(self) -> dict[str, object]:
        return reboot_recovery.prepare(home=self.home, state_dir=self.state, test_id="owner-reboot-check",
                                      evidence=evidence(), boot_id=BOOT_A)

    def test_prepare_preview_is_private_nonwriting_and_bound_to_exact_baseline(self) -> None:
        first = reboot_recovery.prepare_preview(home=self.home, state_dir=self.state,
                                                test_id="owner-reboot-check", evidence=evidence(), boot_id=BOOT_A)
        again = reboot_recovery.prepare_preview(home=self.home, state_dir=self.state,
                                                test_id="owner-reboot-check", evidence=evidence(), boot_id=BOOT_A)
        self.assertEqual(first["plan_id"], again["plan_id"])
        self.assertTrue(first["read_only"])
        self.assertFalse(self.record_path().exists())
        self.assertNotIn("nonce", json.dumps(first))
        changed = evidence()
        changed["stage"] = "different-stage"
        changed_preview = reboot_recovery.prepare_preview(home=self.home, state_dir=self.state,
                                                          test_id="owner-reboot-check", evidence=changed, boot_id=BOOT_A)
        self.assertNotEqual(first["plan_id"], changed_preview["plan_id"])
        self.prepare()
        with self.assertRaises(reboot_recovery.RecoveryError):
            reboot_recovery.prepare_preview(home=self.home, state_dir=self.state,
                                            test_id="owner-reboot-check", evidence=evidence(), boot_id=BOOT_A)

    def test_verify_preview_is_readonly_and_plan_changes_with_boot_evidence(self) -> None:
        self.prepare()
        first = reboot_recovery.verify_preview(home=self.home, state_dir=self.state,
                                               test_id="owner-reboot-check", current_boot_id=BOOT_A)
        repeated = reboot_recovery.verify_preview(home=self.home, state_dir=self.state,
                                                  test_id="owner-reboot-check", current_boot_id=BOOT_A)
        self.assertEqual(first["plan_id"], repeated["plan_id"])
        self.assertEqual(first["details"]["expected_outcome"], "same_boot")
        self.assertNotIn("nonce", json.dumps(first))
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertNotIn("verification", record)
        record["baseline"]["stage"] = "stale-after-preview"
        self.record_path().write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(reboot_recovery.RecoveryError):
            reboot_recovery.verify_pending(home=self.home, state_dir=self.state,
                                           test_id="owner-reboot-check", current_boot_id=BOOT_A,
                                           expected_record_sha256=first["details"]["record_sha256"])
        different_boot = reboot_recovery.verify_preview(home=self.home, state_dir=self.state,
                                                        test_id="owner-reboot-check", current_boot_id=BOOT_B)
        self.assertNotEqual(first["plan_id"], different_boot["plan_id"])

    def test_tx_reboot_json_commands_only_preview(self) -> None:
        env = {
            **os.environ,
            "TERMUX_VERSION": "test-version",
            "PREFIX": "/data/data/com.termux/files/usr",
            "HOME": str(self.home),
            "TERNUXX_STATE_DIR": str(self.state),
        }
        prepare = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), "--json", "reboot", "prepare", "--test-id", "shell-check",
             "--baseline-json", json.dumps(evidence())],
            env=env, text=True, capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(prepare.returncode, 0, prepare.stderr)
        prepare_result = json.loads(prepare.stdout)
        self.assertTrue(prepare_result["ok"])
        self.assertTrue(prepare_result["data"]["read_only"])
        record_path = self.state / "continuity/reboot-tests/shell-check.json"
        self.assertFalse(record_path.exists())

        self.prepare()
        verify = subprocess.run(
            ["bash", str(ROOT / "bin/tx"), "--json", "reboot", "verify", "owner-reboot-check"],
            env=env, text=True, capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(verify.returncode, 0, verify.stderr)
        verify_result = json.loads(verify.stdout)
        self.assertTrue(verify_result["ok"])
        self.assertTrue(verify_result["data"]["read_only"])
        stored = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual(stored["verification_history"], [])

    def record_path(self) -> Path:
        return self.state / "continuity/reboot-tests/owner-reboot-check.json"

    def test_legacy_proot_check_is_readable_but_rejected_for_new_checkpoint(self) -> None:
        legacy_baseline = evidence()
        legacy_baseline["required_postboot_checks"] = ["boot_id_changed", "proot_independent"]
        with self.assertRaises(reboot_recovery.RecoveryError):
            reboot_recovery.prepare(home=self.home, state_dir=self.state, test_id="legacy-rejected",
                                    evidence=legacy_baseline, boot_id=BOOT_A)
        self.prepare()
        record_path = self.record_path()
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["baseline"]["required_postboot_checks"].append("proot_independent")
        record_path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(reboot_recovery.status(home=self.home, state_dir=self.state,
                                                test_id="owner-reboot-check")["state"], "prepared")

    def test_private_checkpoint_records_full_baseline_and_defaults_not_ready(self) -> None:
        result = self.prepare()
        self.assertEqual(result["state"], "prepared")
        self.assertEqual(result["readiness"], "NOT_READY")
        self.assertGreaterEqual(len(result["nonce"]), 32)
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual(self.record_path().stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.record_path().parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(record["previous_boot_id"], BOOT_A)
        self.assertEqual(record["baseline"]["ssh"]["socket_binding"], "unverified")
        self.assertFalse(record["automatic_resume"])
        with self.assertRaises(reboot_recovery.RecoveryError):
            self.prepare()

    def test_boot_observation_requires_nonce_and_does_not_erase_pending_marker(self) -> None:
        prepared = self.prepare()
        with self.assertRaises(reboot_recovery.RecoveryError):
            reboot_recovery.record_boot_observation(
                home=self.home, state_dir=self.state, test_id="owner-reboot-check", nonce="wrong-nonce-value-that-is-long-enough",
                termux_version="test", sshd_process="present", config_syntax="valid", current_boot_id=BOOT_B)
        observed = reboot_recovery.record_boot_observation(
            home=self.home, state_dir=self.state, test_id="owner-reboot-check", nonce=str(prepared["nonce"]),
            termux_version="test-version", sshd_process="present", config_syntax="valid", current_boot_id=BOOT_B)
        self.assertEqual(observed["state"], "boot_observed")
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual(record["state"], "boot_observed")
        self.assertEqual(record["boot_observations"][0]["current_boot_id"], BOOT_B)
        self.assertFalse(record["automatic_resume"])

    def test_verify_requires_changed_boot_and_matching_native_boot_observation(self) -> None:
        prepared = self.prepare()
        same = reboot_recovery.verify(home=self.home, state_dir=self.state, test_id="owner-reboot-check",
                                      nonce=str(prepared["nonce"]), current_boot_id=BOOT_A)
        self.assertEqual(same["outcome"], "same_boot")
        reboot_recovery.record_boot_observation(
            home=self.home, state_dir=self.state, test_id="owner-reboot-check", nonce=str(prepared["nonce"]),
            termux_version="test-version", sshd_process="present", config_syntax="valid", current_boot_id=BOOT_B)
        result = reboot_recovery.verify(home=self.home, state_dir=self.state, test_id="owner-reboot-check",
                                        nonce=str(prepared["nonce"]), current_boot_id=BOOT_B)
        self.assertEqual(result["outcome"], "verified_reboot_service_unqualified")
        self.assertEqual(reboot_recovery.status(home=self.home, state_dir=self.state, test_id="owner-reboot-check")["state"], "boot_observed")
        self.assertEqual(result["socket_binding"], "not_observed")
        self.assertFalse(result["automatic_resume"])

    def test_verify_pending_reads_nonce_privately(self) -> None:
        prepared = self.prepare()
        result = reboot_recovery.verify_pending(home=self.home, state_dir=self.state,
                                                test_id="owner-reboot-check", current_boot_id=BOOT_A)
        self.assertEqual(result["outcome"], "same_boot")
        self.assertNotIn("nonce", result)
        self.assertNotIn(str(prepared["nonce"]), json.dumps(result))

    def test_resume_info_replaces_stale_reboot_action_after_boot_observation(self) -> None:
        prepared = self.prepare()
        reboot_recovery.record_boot_observation(
            home=self.home, state_dir=self.state, test_id="owner-reboot-check", nonce=str(prepared["nonce"]),
            termux_version="test-version", sshd_process="unknown", config_syntax="unknown", current_boot_id=BOOT_B)

        pending_review = reboot_recovery.resume_info(
            home=self.home, state_dir=self.state, test_id="owner-reboot-check")
        self.assertIn("reboot verify", pending_review["next_action"])
        self.assertNotIn("Owner performs the manual reboot", pending_review["next_action"])
        self.assertEqual(pending_review["readiness"], "NOT_READY")
        self.assertFalse(pending_review["automatic_resume"])

        verification = reboot_recovery.verify_pending(
            home=self.home, state_dir=self.state, test_id="owner-reboot-check", current_boot_id=BOOT_B)
        self.assertEqual(verification["outcome"], "verified_reboot_partial")
        verified_review = reboot_recovery.resume_info(
            home=self.home, state_dir=self.state, test_id="owner-reboot-check")
        self.assertIn("verified_reboot_partial", verified_review["next_action"])
        self.assertIn("manually verify required service and connection evidence", verified_review["next_action"])
        self.assertEqual(verified_review["state"], "boot_observed")
        self.assertEqual(verified_review["readiness"], "NOT_READY")
        self.assertFalse(verified_review["automatic_resume"])

    def test_boot_observer_uses_readonly_diagnostics_and_never_claims_socket_or_lock_state(self) -> None:
        self.prepare()
        with patch.object(continuity, "read_boot_id", return_value=BOOT_B), \
             patch.object(reboot_recovery.ssh_diagnostics, "inspect_native", return_value={
                 "checks": {"daemon_process_present": True, "config_syntax": "valid"}
             }) as inspect:
            result = reboot_recovery.observe_latest_pending(home=self.home, state_dir=self.state,
                                                           prefix="/termux", termux_version="test-version")
        self.assertEqual(result["boot_id_transition"], "changed")
        inspect.assert_called_once()
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual(record["boot_observations"][0]["socket_binding"], "not_observed")
        self.assertEqual(record["boot_observations"][0]["wakelock_state"], "unknown")
        self.assertNotIn("proot_dependency", record["boot_observations"][0])
        observation = record["boot_observations"][0]
        self.assertEqual(observation["native_service_health"], "unknown")
        self.assertEqual(observation["managed_service_status"], "unknown")
        self.assertEqual(observation["listener_daemon_correlation"], "unknown")

    def test_managed_service_evidence_controls_native_health_not_generic_sshd(self) -> None:
        prepared = self.prepare()
        managed = {
            "status": "stopped", "config_syntax": "valid",
            "definition_identity": {"status": "verified"},
            "loopback_ssh_probe": {"status": "failed"},
        }
        report = {"checks": {"daemon_process_present": True, "config_syntax": "valid",
                             "managed_service": managed, "listener_daemon_correlation": "unknown"}}
        with patch.object(continuity, "read_boot_id", return_value=BOOT_B), \
             patch.object(reboot_recovery.ssh_diagnostics, "inspect_native", return_value=report), \
             patch.object(reboot_recovery.time, "sleep"):
            reboot_recovery.observe_latest_pending(home=self.home, state_dir=self.state,
                                                   prefix="/termux", termux_version="test-version")
        observation = json.loads(self.record_path().read_text(encoding="utf-8"))["boot_observations"][0]
        self.assertEqual(observation["sshd_process"], "present")
        self.assertEqual(observation["native_service_health"], "degraded")
        self.assertEqual(observation["managed_service_status"], "stopped")
        self.assertEqual(observation["managed_service_definition"], "verified")
        self.assertEqual(observation["listener_daemon_correlation"], "unknown")
        self.assertIn("managed_service_not_ready", observation["errors"])

    def test_verified_managed_service_and_loopback_banner_remain_unqualified(self) -> None:
        prepared = self.prepare()
        report = {"checks": {"daemon_process_present": True, "config_syntax": "valid",
                  "managed_service": {"status": "running", "config_syntax": "valid",
                    "definition_identity": {"status": "verified"},
                    "loopback_ssh_probe": {"status": "ssh_banner"}},
                  "listener_daemon_correlation": "unknown"}}
        with patch.object(continuity, "read_boot_id", return_value=BOOT_B), \
             patch.object(reboot_recovery.ssh_diagnostics, "inspect_native", return_value=report):
            reboot_recovery.observe_latest_pending(home=self.home, state_dir=self.state,
                                                   prefix="/termux", termux_version="test-version")
        observation = json.loads(self.record_path().read_text(encoding="utf-8"))["boot_observations"][0]
        self.assertEqual(observation["native_service_health"], "ready_unqualified")
        self.assertEqual(observation["managed_loopback_probe"], "ssh_banner")
        self.assertEqual(observation["listener_daemon_correlation"], "unknown")
        self.assertEqual(observation["sshd_authenticated_connectivity"], "not_tested")

    def test_boot_observer_retries_transient_managed_service_startup_race(self) -> None:
        self.prepare()
        delayed = {"checks": {"daemon_process_present": False, "config_syntax": "valid",
                   "managed_service": {"status": "unknown", "config_syntax": "valid",
                     "definition_identity": {"status": "verified"},
                     "loopback_ssh_probe": {"status": "unreachable"}},
                   "listener_daemon_correlation": "unknown"}}
        ready = {"checks": {"daemon_process_present": True, "config_syntax": "valid",
                 "managed_service": {"status": "running", "config_syntax": "valid",
                   "definition_identity": {"status": "verified"},
                   "loopback_ssh_probe": {"status": "ssh_banner"}},
                 "listener_daemon_correlation": "unknown"}}
        with patch.object(continuity, "read_boot_id", return_value=BOOT_B), \
             patch.object(reboot_recovery.ssh_diagnostics, "inspect_native", side_effect=[delayed, ready]) as inspect, \
             patch.object(reboot_recovery.time, "sleep") as sleep:
            reboot_recovery.observe_latest_pending(home=self.home, state_dir=self.state,
                                                   prefix="/termux", termux_version="test-version")
        self.assertEqual(inspect.call_count, 2)
        sleep.assert_called_once_with(reboot_recovery.OBSERVER_READINESS_POLL_SECONDS)
        observation = json.loads(self.record_path().read_text(encoding="utf-8"))["boot_observations"][0]
        self.assertEqual(observation["native_service_health"], "ready_unqualified")
        self.assertEqual(observation["managed_loopback_probe"], "ssh_banner")
        self.assertEqual(observation["errors"], [])

    def test_schema_v1_checkpoint_without_new_managed_fields_remains_readable(self) -> None:
        prepared = self.prepare()
        reboot_recovery.record_boot_observation(
            home=self.home, state_dir=self.state, test_id="owner-reboot-check", nonce=str(prepared["nonce"]),
            termux_version="test-version", sshd_process="present", config_syntax="valid", current_boot_id=BOOT_B)
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        for field in ("managed_service_status", "managed_service_definition", "managed_config_syntax",
                      "managed_loopback_probe", "listener_daemon_correlation"):
            record["boot_observations"][0].pop(field)
        self.record_path().write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(reboot_recovery.status(home=self.home, state_dir=self.state,
                                                test_id="owner-reboot-check")["state"], "boot_observed")

    def test_managed_evidence_validation_rejects_malformed_values_without_mutation(self) -> None:
        prepared = self.prepare()
        with self.assertRaises(reboot_recovery.RecoveryError):
            reboot_recovery.record_boot_observation(
                home=self.home, state_dir=self.state, test_id="owner-reboot-check", nonce=str(prepared["nonce"]),
                termux_version="test-version", sshd_process="present", config_syntax="valid",
                managed_service_status=[], current_boot_id=BOOT_B)
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual(record["boot_observations"], [])
        reboot_recovery.record_boot_observation(
            home=self.home, state_dir=self.state, test_id="owner-reboot-check", nonce=str(prepared["nonce"]),
            termux_version="test-version", sshd_process="present", config_syntax="valid", current_boot_id=BOOT_B)
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        record["boot_observations"][0]["managed_service_status"] = []
        self.record_path().write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(reboot_recovery.RecoveryError):
            reboot_recovery.status(home=self.home, state_dir=self.state, test_id="owner-reboot-check")

    def test_duplicate_boot_observer_is_rejected_while_owner_lock_is_held(self) -> None:
        self.prepare()
        lock = self.state / "continuity/reboot-tests/.boot-observer.lock"
        fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = reboot_recovery.observe_latest_pending(home=self.home, state_dir=self.state,
                                                           prefix="/termux", termux_version="test-version")
        finally:
            os.close(fd)
        self.assertEqual(result["state"], "observer_already_running")
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual(record["boot_observations"], [])

    def test_rejects_path_traversal_and_source_paths_outside_repository(self) -> None:
        with self.assertRaises(reboot_recovery.RecoveryError):
            reboot_recovery.status(home=self.home, state_dir=self.state, test_id="../outside")
        unsafe = evidence()
        unsafe["references"] = ["../../.ssh/id_ed25519"]
        with self.assertRaises(reboot_recovery.RecoveryError):
            reboot_recovery.prepare(home=self.home, state_dir=self.state, test_id="unsafe-reference", evidence=unsafe)


if __name__ == "__main__":
    unittest.main()
