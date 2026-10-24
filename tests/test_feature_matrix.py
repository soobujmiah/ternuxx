"""Contracts for the machine-readable feature and evidence matrix."""
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/testing/FEATURE-MATRIX.yaml"
REQUIRED_FIELDS = {
    "id", "name", "user_value", "implementation_status", "commercial_class",
    "runtime", "dependencies", "validation_status", "qualification", "evidence",
    "release_qualified", "limitations", "next_action", "owner_decision_required",
}


class FeatureMatrixTests(unittest.TestCase):
    def test_feature_rows_are_unique_typed_and_link_existing_evidence(self) -> None:
        document = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertIsInstance(document["features"], list)
        identifiers = []
        for feature in document["features"]:
            self.assertFalse(REQUIRED_FIELDS - feature.keys(), feature.get("id"))
            identifiers.append(feature["id"])
            self.assertIn(feature["commercial_class"], document["classification_values"])
            self.assertIn(feature["qualification"], document["qualification_values"])
            self.assertIsInstance(feature["release_qualified"], bool)
            self.assertIsInstance(feature["owner_decision_required"], bool)
            self.assertTrue(feature["evidence"], feature["id"])
            for reference in feature["evidence"]:
                target = (MATRIX.parent / reference).resolve()
                self.assertTrue(target.is_file(), f"{feature['id']}: missing evidence {reference}")
        self.assertEqual(len(identifiers), len(set(identifiers)))


if __name__ == "__main__":
    unittest.main()
