from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_setup_present


class ProotSetupPresentationTests(unittest.TestCase):
    def test_preview_summary_distinguishes_file_presence_from_acceleration(self) -> None:
        result = {
            "status": "preview", "plan_id": "a" * 64,
            "operation": {
                "guest_release": {"VERSION_ID": "13", "VERSION_CODENAME": "trixie"},
                "guest_user": "sbj", "rootfs": "/guest/debian/rootfs",
                "observed_graphics_files": {
                    "turnip_driver": {"status": "present"},
                    "turnip_icd": {"status": "missing"},
                },
                "observed_other_icd_configs": [{"name": "vendor-driver.json"}],
                "observed_package_groups": {"base": {"requested": 14, "installed": 14,
                    "missing": [], "held": ["libgl1-mesa-dri"], "versions": {}}},
                "guest_mutations": [], "package_changes": [], "service_changes": [],
            },
        }
        summary = proot_setup_present.summarize(result)
        self.assertIn("Ternuxx Turnip files: driver present; ICD missing (file presence only)", summary)
        self.assertIn("Other ICD configs (not selected by Ternuxx): vendor-driver.json", summary)
        self.assertIn("Manifest packages: base 14/14", summary)
        self.assertIn("APT-held manifest packages: 1 (not upgraded)", summary)
        self.assertTrue(any("unchanged" in line for line in summary))
        self.assertFalse(any("acceleration verified" in line for line in summary))

    def test_stale_prior_record_suppresses_apply_command(self) -> None:
        result = {"status": "preview", "plan_id": "b" * 64,
            "operation": {"guest_release": {"VERSION_ID": "13", "VERSION_CODENAME": "trixie"},
                "guest_user": "workuser", "rootfs": "/guest",
                "apply_blocked_reason": "old record",
                "observed_graphics_files": {}, "observed_package_groups": {},
                "guest_mutations": [], "package_changes": [], "service_changes": []}}
        summary = proot_setup_present.summarize(result)
        self.assertTrue(any("Apply blocked" in line for line in summary))
        self.assertFalse(any(line.startswith("Apply after review:") for line in summary))

    def test_refresh_preview_and_record_show_rollback_path(self) -> None:
        preview = {"status": "preview", "plan_id": "a" * 64, "operation": {
            "guest_release": {}, "guest_user": "workuser", "rootfs": "/guest",
            "refresh_existing_record": True, "rollback_backup_id": "b" * 64,
            "guest_mutations": [], "package_changes": [], "service_changes": []}}
        summary = proot_setup_present.summarize(preview)
        self.assertTrue(any("exact prior bytes will be backed up" in line for line in summary))
        self.assertTrue(any(line.startswith("Apply after review:") for line in summary))
        recorded = {"status": "adopted", "record": {"rollback_backup_id": "b" * 64}}
        summary = proot_setup_present.summarize(recorded)
        self.assertTrue(any(line.startswith("Rollback preview:") for line in summary))

    def test_invalid_user_plan_and_terminal_controls_are_rejected(self) -> None:
        base = {"status": "preview", "plan_id": "a" * 64,
                "operation": {"guest_release": {}, "guest_user": "sbj", "rootfs": "/guest"}}
        for mutate in (
            lambda obj: obj.update(plan_id="bad"),
            lambda obj: obj["operation"].update(guest_user="\x1b[31mroot"),
            lambda obj: obj["operation"].update(rootfs="/guest\nforged"),
        ):
            import copy
            invalid = copy.deepcopy(base)
            mutate(invalid)
            with self.assertRaises(ValueError):
                proot_setup_present.summarize(invalid)


if __name__ == "__main__":
    unittest.main()
