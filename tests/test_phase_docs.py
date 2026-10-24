"""Phase evidence workflow validation."""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import phase_docs  # noqa: E402


class PhaseDocsTests(unittest.TestCase):
    def test_readme_phase_status_stays_compact_and_links_to_authoritative_details(self):
        rendered = phase_docs.render({
            "phases": [
                {"id": "P0", "title": "Foundation", "status": "completed", "completed_on": "2026-10-01",
                 "summary": "An old gate passed.", "evidence": []},
                {"id": "P1", "title": "Active work", "status": "in_progress",
                 "summary": "Long detailed summary belongs elsewhere.",
                 "next_action": "Perform the detailed next action.", "evidence": []},
            ]
        })
        readme = rendered[phase_docs.README]
        body = readme.split(phase_docs.README_START, 1)[1].split(phase_docs.README_END, 1)[0]
        self.assertIn("Current phase:** P1", body)
        self.assertIn("Roadmap and active work", body)
        self.assertIn("Phase status and evidence", body)
        self.assertNotIn("Long detailed summary", body)
        self.assertNotIn("Perform the detailed next action", body)

    def test_phase_date_uses_utc_calendar_not_host_local_date(self):
        real_datetime = dt.datetime
        seen = []

        class FixedDateTime:
            @classmethod
            def now(cls, tz=None):
                seen.append(tz)
                return real_datetime(2026, 10, 24, 0, 10, tzinfo=tz)

        with patch.object(phase_docs.dt, "datetime", FixedDateTime):
            self.assertEqual(phase_docs.utc_date(), "2026-10-24")
        self.assertEqual(seen, [dt.timezone.utc])

    def test_incremental_evidence_can_record_a_blocked_gate(self):
        path = "docs/evidence/2026-10-19-native-ui-management-audit.md"
        recorded, resolved = phase_docs.evidence_path(path, "P3", completion=False)
        self.assertEqual(recorded, path)
        self.assertTrue(resolved.is_file())
        with self.assertRaises(ValueError):
            phase_docs.evidence_path(path, "P3", completion=True)

    def test_optional_phase_skip_advances_to_next_planned_phase(self):
        state = {
            "active_phase": "P9",
            "phases": [
                {"id": "P8", "status": "completed"},
                {"id": "P9", "status": "in_progress", "optional": True},
                {"id": "P10", "status": "planned"},
            ],
        }
        phase_docs.skip_optional_phase(
            state, "P9", "No owner-approved workload gap remains.",
            ["docs/evidence/2026-10-20-phase-roadmap-audit.md"], skipped_on="2026-10-20",
        )
        self.assertEqual(state["phases"][1]["status"], "skipped")
        self.assertEqual(state["phases"][1]["skipped_on"], "2026-10-20")
        self.assertEqual(state["phases"][2]["status"], "in_progress")
        self.assertEqual(state["active_phase"], "P10")

    def test_resolved_phase_metadata_revision_preserves_gate_and_records_reason(self):
        state = {"phases": [{"id": "P5", "status": "completed", "completed_on": "2026-10-23",
                             "summary": "old", "next_action": "stale", "evidence": ["report.md"]}]}
        phase_docs.revise_resolved_phase(state, "P5", title="Native profile compatibility",
            summary="Direct profile recorded.", clear_next_action=True, reason="Profile gate is complete.")
        phase = state["phases"][0]
        self.assertEqual(phase["status"], "completed")
        self.assertEqual(phase["completed_on"], "2026-10-23")
        self.assertEqual(phase["evidence"], ["report.md"])
        self.assertNotIn("next_action", phase)
        self.assertEqual(phase["revision_notes"][-1]["reason"], "Profile gate is complete.")

    def test_resolved_phase_metadata_revision_cannot_reopen_active_phase(self):
        state = {"phases": [{"id": "P6", "status": "in_progress"}]}
        with self.assertRaisesRegex(ValueError, "completed or skipped"):
            phase_docs.revise_resolved_phase(state, "P6", summary="wrong", reason="not closed")

    def test_start_planned_phase_only_after_prior_gates_resolve(self):
        state = {"active_phase": None, "phases": [
            {"id": "P10", "status": "completed"},
            {"id": "P11", "status": "planned"},
        ]}
        phase_docs.start_planned_phase(state, "P11")
        self.assertEqual(state["active_phase"], "P11")
        self.assertEqual(state["phases"][1]["status"], "in_progress")

    def test_start_planned_phase_rejects_unresolved_prior_gate(self):
        state = {"active_phase": None, "phases": [
            {"id": "P10", "status": "in_progress"},
            {"id": "P11", "status": "planned"},
        ]}
        with self.assertRaisesRegex(ValueError, "earlier phase"):
            phase_docs.start_planned_phase(state, "P11")

    def test_only_active_optional_phase_can_be_skipped(self):
        state = {"active_phase": "P8", "phases": [
            {"id": "P8", "status": "in_progress"},
            {"id": "P9", "status": "planned", "optional": True},
        ]}
        with self.assertRaisesRegex(ValueError, "active phase explicitly marked optional"):
            phase_docs.skip_optional_phase(state, "P8", "skip", [])

    def test_skip_evidence_requires_explicit_skip_gate(self):
        invalid = "Phase: \x60P9\x60\n## Acceptance criteria\n## Evidence\n"
        valid = "Phase: \x60P9\x60\nGate: SKIP\n## Acceptance criteria\n## Evidence\n"
        with self.assertRaisesRegex(ValueError, "Gate: SKIP"):
            phase_docs.validate_evidence_content(invalid, "P9", completion=False, skip=True)
        phase_docs.validate_evidence_content(valid, "P9", completion=False, skip=True)

    def test_phase_order_requires_all_prior_gates_to_resolve(self):
        phases = [
            {"id": "P3", "status": "in_progress"},
            {"id": "P4", "status": "planned"},
        ]
        with self.assertRaisesRegex(ValueError, "earlier phase"):
            phase_docs.validate_phase_order(phases, "P4")
        phase_docs.validate_phase_order([
            {"id": "P3", "status": "completed"},
            {"id": "P4", "status": "in_progress"},
            {"id": "P5", "status": "planned"},
        ], "P4")

    def test_skipped_phase_must_be_marked_optional(self):
        phases = [
            {"id": "P3", "status": "skipped"},
            {"id": "P4", "status": "in_progress"},
        ]
        with self.assertRaisesRegex(ValueError, "Only explicitly optional"):
            phase_docs.validate_phase_order(phases, "P4")
        phases[0]["optional"] = True
        phase_docs.validate_phase_order(phases, "P4")


if __name__ == "__main__":
    unittest.main()
