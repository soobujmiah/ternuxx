"""Guard the repository's GitHub Actions against mutable dependency refs."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ROOT / ".github/workflows/repo-contract.yml",
    ROOT / ".github/workflows/repo-knowledge-sync.yml",
)
EXPECTED = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    "actions/setup-python": ("6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", "v7.1.0"),
}
USE_LINE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)(?:\s+#\s*(\S+))?\s*$", re.MULTILINE)


class WorkflowActionPinTests(unittest.TestCase):
    def test_all_workflow_actions_use_reviewed_full_commit_shas(self):
        references = []
        for workflow in WORKFLOWS:
            content = workflow.read_text(encoding="utf-8")
            for ref, version in USE_LINE.findall(content):
                self.assertIn("@", ref, f"{workflow}: action ref has no commit")
                action, commit = ref.rsplit("@", 1)
                self.assertIn(action, EXPECTED, f"{workflow}: unreviewed action {action}")
                expected_commit, expected_version = EXPECTED[action]
                self.assertEqual(commit, expected_commit, f"{workflow}: unexpected {action} ref")
                self.assertEqual(version, expected_version, f"{workflow}: update release comment")
                self.assertRegex(commit, r"^[0-9a-f]{40}$", f"{workflow}: ref is not an immutable SHA")
                references.append(action)

        self.assertEqual(references.count("actions/checkout"), 3)
        self.assertEqual(references.count("actions/setup-python"), 3)
        self.assertEqual(len(references), 6)


if __name__ == "__main__":
    unittest.main()
