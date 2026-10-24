from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import terminal_broker_service as service


class TerminalBrokerAssemblyTests(unittest.TestCase):
    def test_selected_alias_reaches_both_preview_callbacks_and_spawn(self):
        with mock.patch.dict(os.environ, {"TERMUX_VERSION": "fixture"}), \
             mock.patch.object(service.terminal_broker, "TerminalPTYRuntime") as runtime, \
             mock.patch.object(service.terminal_broker, "TerminalBrokerDispatcher") as dispatcher, \
             mock.patch.object(service.terminal_broker, "UnixBrokerServer"), \
             mock.patch.object(service.proot_sessions, "preview_start") as preview, \
             mock.patch.object(service.proot_sessions, "spawn_login_interactive") as spawn:
            service.build_service(guest_alias="ternuxx-replay-test")
            runtime.call_args.kwargs["preview_start"]()
            dispatcher.call_args.kwargs["start_preview"]()
            self.assertEqual(preview.call_count, 2)
            self.assertTrue(all(call.kwargs["alias"] == "ternuxx-replay-test"
                                for call in preview.call_args_list))
            runtime.call_args.kwargs["spawn_login"]("plan-fixture")
            self.assertEqual(spawn.call_args.kwargs["alias"], "ternuxx-replay-test")
            self.assertEqual(spawn.call_args.kwargs["plan_id"], "plan-fixture")

    def test_close_accepts_already_completed_cleanup_but_not_another_live_pty(self):
        for status in ("not_connected", "running"):
            with self.subTest(status=status), \
                 mock.patch.dict(os.environ, {"TERMUX_VERSION": "fixture"}), \
                 mock.patch.object(service.terminal_broker, "TerminalPTYRuntime") as runtime, \
                 mock.patch.object(service.terminal_broker, "TerminalBrokerDispatcher") as dispatcher, \
                 mock.patch.object(service.terminal_broker, "UnixBrokerServer"), \
                 mock.patch.object(service.proot_sessions, "stop_session", return_value={"state": "stopped", "stopped": True}):
                runtime.return_value.release_after_stop.side_effect = service.terminal_broker.BrokerError("already released")
                runtime.return_value.status.return_value = status
                service.build_service()
                close = dispatcher.call_args.kwargs["close_apply"]
                if status == "running":
                    with self.assertRaises(service.terminal_broker.BrokerError):
                        close("proot-fixture", "plan-fixture")
                else:
                    self.assertEqual(close("proot-fixture", "plan-fixture")["state"], "stopped")

    def test_invalid_alias_refused_before_runtime_construction(self):
        with mock.patch.dict(os.environ, {"TERMUX_VERSION": "fixture"}), \
             mock.patch.object(service.terminal_broker, "TerminalPTYRuntime") as runtime:
            with self.assertRaises(service.proot_sessions.SessionError):
                service.build_service(guest_alias="../debian")
            runtime.assert_not_called()

    def test_cli_default_and_explicit_alias_are_passed_to_service(self):
        with mock.patch.object(service, "serve", return_value=0) as serve:
            self.assertEqual(service.main(["serve"]), 0)
            serve.assert_called_with(guest_alias="debian")
            self.assertEqual(service.main(["serve", "--guest-alias", "ternuxx-replay-test"]), 0)
            serve.assert_called_with(guest_alias="ternuxx-replay-test")


if __name__ == "__main__":
    unittest.main()
