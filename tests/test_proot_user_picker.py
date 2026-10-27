from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_user_picker


class ProotUserPickerTests(unittest.TestCase):
    def test_single_user_is_selected_without_prompt(self):
        output = io.StringIO()
        self.assertEqual(proot_user_picker.choose_user(["sbj"], output_stream=output), "sbj")
        self.assertEqual(output.getvalue(), "")

    def test_explicit_selection_bypasses_prompt(self):
        output = io.StringIO()
        self.assertEqual(proot_user_picker.choose_user(["sbj", "guest"], selected="guest",
                                                       output_stream=output), "guest")
        self.assertEqual(output.getvalue(), "")

    def test_multiple_users_are_interactive_and_invalid_choice_retries(self):
        input_stream = io.StringIO("x\n2\n")
        output = io.StringIO()
        selected = proot_user_picker.choose_user(["sbj", "guest"], input_stream=input_stream,
                                                 output_stream=output)
        self.assertEqual(selected, "guest")
        self.assertIn("1) sbj", output.getvalue())
        self.assertIn("2) guest", output.getvalue())
        self.assertIn("Choose a number from 1 to 2", output.getvalue())

    def test_cancel_does_not_choose_an_account(self):
        with self.assertRaises(proot_user_picker.UserPickerCancelled):
            proot_user_picker.choose_user(["sbj", "guest"], input_stream=io.StringIO("q\n"),
                                          output_stream=io.StringIO())

    def test_unknown_account_and_empty_inventory_fail_closed(self):
        with self.assertRaisesRegex(proot_user_picker.UserPickerError, "not an ordinary"):
            proot_user_picker.choose_user(["sbj"], selected="root")
        with self.assertRaisesRegex(proot_user_picker.UserPickerError, "no ordinary"):
            proot_user_picker.choose_user([])


if __name__ == "__main__":
    unittest.main()
