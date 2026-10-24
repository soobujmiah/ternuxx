from __future__ import annotations

import os
import base64
from pathlib import Path
import socket
import stat
import sys
import tempfile
import threading
import time
import pty
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import terminal_broker  # noqa: E402


def request(**changes):
    value = {
        "api_version": 1,
        "request_id": "request_0001",
        "operation": "broker.status",
        "session_id": None,
        "generation": None,
        "attachment_id": None,
        "args": {},
    }
    value.update(changes)
    return value


class TerminalBrokerTransportTests(unittest.TestCase):
    def test_dispatcher_binds_channels_to_auth_and_previewed_close_callbacks(self):
        session = "proot-" + "c" * 32
        registry = terminal_broker.TerminalAttachmentRegistry(generation=17)
        input_data = []
        resized = []
        closed = []
        dispatcher = terminal_broker.TerminalBrokerDispatcher(
            registry,
            authorize=lambda _request, uid: "web-session" if uid == os.getuid() else None,
            verify_session=lambda selected: selected == session,
            write_input=lambda selected, data: input_data.append((selected, data)),
            resize_pty=lambda selected, columns, rows: resized.append((selected, columns, rows)),
            close_preview=lambda selected: {"session_id": selected, "plan_id": "plan-1"},
            close_apply=lambda selected, plan: (closed.append((selected, plan)) or {"state": "stopped"}),
        )
        attached = dispatcher(request(operation="terminal.attach", session_id=session), os.getuid())
        attachment = attached["attachment_id"]
        shared = {"session_id": session, "generation": 17, "attachment_id": attachment}
        result = dispatcher(request(**{
            **shared, "operation": "terminal.input",
            "args": {"data_base64": base64.b64encode(b"echo hi\
").decode("ascii")},
        }), os.getuid())
        self.assertTrue(result["ok"])
        self.assertEqual(input_data, [(session, b"echo hi\
")])
        dispatcher(request(**{**shared, "operation": "terminal.resize",
                              "args": {"columns": 100, "rows": 35}}), os.getuid())
        self.assertEqual(resized, [(session, 100, 35)])
        plan = dispatcher(request(**{**shared, "operation": "terminal.close.preview"}), os.getuid())
        self.assertEqual(plan["plan"]["plan_id"], "plan-1")
        closed_result = dispatcher(request(**{
            **shared, "operation": "terminal.close",
            "args": {"confirmed": True, "plan_id": "plan-1"},
        }), os.getuid())
        self.assertEqual(closed_result["result"]["state"], "stopped")
        self.assertEqual(closed, [(session, "plan-1")])
        with self.assertRaisesRegex(terminal_broker.BrokerError, "unauthorized"):
            dispatcher(request(**{**shared, "operation": "terminal.detach"}), os.getuid() + 1)

    def test_close_operations_reject_stale_or_foreign_attachments_before_callbacks(self):
        from unittest import mock
        session = "proot-" + "d" * 32
        for operation in ("terminal.close.preview", "terminal.close"):
            for invalid in ("generation", "attachment", "principal"):
                with self.subTest(operation=operation, invalid=invalid):
                    registry = terminal_broker.TerminalAttachmentRegistry(generation=41)
                    lease = registry.attach(session, "owner")
                    preview, apply = mock.Mock(), mock.Mock(return_value={"state": "stopped"})
                    dispatcher = terminal_broker.TerminalBrokerDispatcher(
                        registry, authorize=lambda _r, _uid: "other" if invalid == "principal" else "owner",
                        verify_session=lambda _s: True, write_input=mock.Mock(), resize_pty=mock.Mock(),
                        close_preview=preview, close_apply=apply)
                    args = {} if operation.endswith("preview") else {"confirmed": True, "plan_id": "plan-exact"}
                    envelope = request(operation=operation, session_id=session,
                        generation=40 if invalid == "generation" else 41,
                        attachment_id="attach-" + "0" * 32 if invalid == "attachment" else lease["attachment_id"],
                        args=args)
                    with self.assertRaises(terminal_broker.BrokerError):
                        dispatcher(envelope, os.getuid())
                    preview.assert_not_called()
                    apply.assert_not_called()
                    # Rejected requests must not revoke the real writer.
                    registry.validate_resize(session, 41, lease["attachment_id"], "owner", 80, 24)

    def test_single_writer_input_resize_output_and_detach_contract(self):
        registry = terminal_broker.TerminalAttachmentRegistry(
            generation=42, max_output_bytes=4096)
        session = "proot-" + "a" * 32
        lease = registry.attach(session, "web-session-1")
        attachment = lease["attachment_id"]
        with self.assertRaisesRegex(terminal_broker.BrokerError, "already has a writer"):
            registry.attach(session, "gtk-user")
        self.assertEqual(registry.accept_input(session, 42, attachment,
                          "web-session-1", b"hello"), b"hello")
        self.assertEqual(registry.validate_resize(session, 42, attachment,
                          "web-session-1", 120, 40), (120, 40))
        with self.assertRaisesRegex(terminal_broker.BrokerError, "unauthorized"):
            registry.accept_input(session, 42, attachment, "other-session", b"x")
        registry.publish_output(session, 42, b"a" * 3000)
        registry.publish_output(session, 42, b"b" * 2000)
        output = registry.read_output(session, 42, attachment, "web-session-1", 0)
        self.assertTrue(output["truncated"])
        self.assertEqual(output["chunks"][0]["sequence"], 2)
        paged = terminal_broker.TerminalAttachmentRegistry(generation=43, max_output_bytes=100_000)
        page_lease = paged.attach(session, "web-session-1")
        paged.publish_output(session, 43, b"c" * (terminal_broker.MAX_OUTPUT_CHUNK * 2 + 3))
        cursor = 0
        received = []
        while True:
            page = paged.read_output(session, 43, page_lease["attachment_id"],
                                     "web-session-1", cursor)
            if not page["chunks"]:
                break
            chunk = page["chunks"][0]
            self.assertLessEqual(len(chunk["data"]), terminal_broker.MAX_OUTPUT_CHUNK)
            received.append(chunk["data"])
            self.assertEqual(page["next_sequence"], chunk["sequence"])
            cursor = page["next_sequence"]
        self.assertEqual(b"".join(received), b"c" * (terminal_broker.MAX_OUTPUT_CHUNK * 2 + 3))
        paged = terminal_broker.TerminalAttachmentRegistry(generation=43, max_output_bytes=100_000)
        page_lease = paged.attach(session, "web-session-1")
        paged.publish_output(session, 43, b"c" * (terminal_broker.MAX_OUTPUT_CHUNK * 2 + 3))
        cursor = 0
        received = []
        while True:
            page = paged.read_output(session, 43, page_lease["attachment_id"],
                                     "web-session-1", cursor)
            if not page["chunks"]:
                break
            chunk = page["chunks"][0]
            self.assertLessEqual(len(chunk["data"]), terminal_broker.MAX_OUTPUT_CHUNK)
            received.append(chunk["data"])
            self.assertEqual(page["next_sequence"], chunk["sequence"])
            cursor = page["next_sequence"]
        self.assertEqual(b"".join(received), b"c" * (terminal_broker.MAX_OUTPUT_CHUNK * 2 + 3))
        detached = registry.detach(session, 42, attachment, "web-session-1")
        self.assertFalse(detached["writer_attached"])
        self.assertFalse(detached["session_closed"])

    def test_generation_restart_invalidates_old_attachment_and_input_is_bounded(self):
        session = "proot-" + "b" * 32
        old = terminal_broker.TerminalAttachmentRegistry(generation=7)
        lease = old.attach(session, "cli")
        restarted = terminal_broker.TerminalAttachmentRegistry(generation=8)
        with self.assertRaisesRegex(terminal_broker.BrokerError, "generation is stale"):
            restarted.accept_input(session, 7, lease["attachment_id"], "cli", b"x")
        with self.assertRaisesRegex(terminal_broker.BrokerError, "size"):
            old.accept_input(session, 7, lease["attachment_id"], "cli",
                             b"x" * (terminal_broker.MAX_INPUT + 1))

    def test_frame_round_trip_is_bounded_and_json_only(self):
        left, right = socket.socketpair()
        try:
            left.sendall(terminal_broker.encode_frame({"status": "ready", "bytes": 3}))
            self.assertEqual(terminal_broker.read_frame(right), {"status": "ready", "bytes": 3})
        finally:
            left.close()
            right.close()
        with self.assertRaises(terminal_broker.BrokerError):
            terminal_broker.encode_frame("x" * (terminal_broker.MAX_FRAME + 1))
        left, right = socket.socketpair()
        try:
            left.sendall(b"\0\0\0\x11{\"key\":1,\"key\":2}")
            with self.assertRaisesRegex(terminal_broker.BrokerError, "duplicate"):
                terminal_broker.read_frame(right)
        finally:
            left.close()
            right.close()

    def test_protocol_rejects_generic_shell_and_extra_fields(self):
        with self.assertRaisesRegex(terminal_broker.BrokerError, "not supported"):
            terminal_broker.validate_request(request(operation="shell.exec"))
        for malformed in ([], {}, None):
            with self.subTest(operation=malformed):
                with self.assertRaisesRegex(terminal_broker.BrokerError, "not supported"):
                    terminal_broker.validate_request(request(operation=malformed))
        for malformed in ([], {}, None):
            with self.subTest(operation=malformed):
                with self.assertRaisesRegex(terminal_broker.BrokerError, "not supported"):
                    terminal_broker.validate_request(request(operation=malformed))
        with self.assertRaisesRegex(terminal_broker.BrokerError, "fields"):
            terminal_broker.validate_request({**request(), "command": "id"})
        with self.assertRaisesRegex(terminal_broker.BrokerError, "session ID"):
            terminal_broker.validate_request(request(
                operation="terminal.input", session_id="proot-../../etc/passwd"))

    def test_private_unix_socket_checks_peer_and_dispatches_typed_envelope(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-terminal-broker-") as temp:
            state = Path(temp) / "state"
            state.mkdir(mode=0o700)
            seen = []
            server = terminal_broker.UnixBrokerServer(
                state, lambda message, uid: (seen.append((message, uid)) or {"ok": True}))
            server.open()
            path = terminal_broker.broker_socket_path(state)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

            outcome = []
            def serve():
                outcome.append(server.serve_one())
            thread = threading.Thread(target=serve)
            thread.start()
            client = terminal_broker.UnixBrokerClient(state)
            self.assertEqual(client.request("broker.status"), {"ok": True})
            thread.join(timeout=2)
            self.assertEqual(outcome, [True])
            self.assertEqual(seen[0][0]["operation"], "broker.status")
            self.assertEqual(seen[0][1], os.getuid())
            server.close()
            self.assertFalse(path.exists())

    def test_existing_socket_is_never_replaced_or_unlinked(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-terminal-existing-") as temp:
            state = Path(temp) / "state"
            state.mkdir(mode=0o700)
            path = terminal_broker.broker_socket_path(state)
            original = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            original.bind(str(path))
            identity = path.lstat().st_ino
            server = terminal_broker.UnixBrokerServer(state, lambda _request, _uid: {})
            try:
                with self.assertRaisesRegex(terminal_broker.BrokerError, "already exists"):
                    server.open()
                self.assertEqual(path.lstat().st_ino, identity)
            finally:
                original.close()
                path.unlink()

    def test_stale_socket_recovery_is_exact_preview_bound_and_private(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-terminal-stale-") as temp:
            state = Path(temp) / "state"
            state.mkdir(mode=0o700)
            path = terminal_broker.broker_socket_path(state)
            original = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            original.bind(str(path))
            original.close()
            os.chmod(path, 0o600)
            before = path.lstat()

            preview = terminal_broker.preview_stale_socket_recovery(state)
            self.assertEqual(preview["status"], "stale")
            self.assertEqual(preview["probe"], "connection-refused")
            self.assertEqual(path.lstat().st_ino, before.st_ino)
            self.assertEqual(stat.S_IMODE(path.lstat().st_mode), 0o600)
            with self.assertRaisesRegex(terminal_broker.BrokerError, "explicit confirmation"):
                terminal_broker.recover_stale_socket(
                    state, confirmed=False, plan_id=preview["plan_id"])
            result = terminal_broker.recover_stale_socket(
                state, confirmed=True, plan_id=preview["plan_id"])
            self.assertEqual(result["status"], "recovered")
            self.assertFalse(path.exists())

    def test_stale_socket_recovery_refuses_live_listener_and_changed_preview(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-terminal-live-socket-") as temp:
            state = Path(temp) / "state"
            state.mkdir(mode=0o700)
            path = terminal_broker.broker_socket_path(state)
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            os.chmod(path, 0o600)
            listener.listen(1)
            with self.assertRaisesRegex(terminal_broker.BrokerError, "live listener"):
                terminal_broker.preview_stale_socket_recovery(state)
            listener.close()
            preview = terminal_broker.preview_stale_socket_recovery(state)
            os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000))
            with self.assertRaisesRegex(terminal_broker.BrokerError, "fresh exact"):
                terminal_broker.recover_stale_socket(
                    state, confirmed=True, plan_id=preview["plan_id"])
            self.assertTrue(path.exists())

    def test_server_start_and_socket_recovery_share_one_lifecycle_lock(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-terminal-lock-") as temp:
            state = Path(temp) / "state"
            state.mkdir(mode=0o700)
            lock_fd = terminal_broker._acquire_broker_socket_lock(state)
            server = terminal_broker.UnixBrokerServer(state, lambda _request, _uid: {"ok": True})
            try:
                with self.assertRaisesRegex(terminal_broker.BrokerError, "lifecycle operation"):
                    server.open()
            finally:
                os.close(lock_fd)
            server.open()
            server.close()


    def test_dispatcher_retains_and_marks_final_output_after_pty_exit(self):
        session = "proot-" + "f" * 32
        registry = terminal_broker.TerminalAttachmentRegistry(generation=18)
        dispatcher = terminal_broker.TerminalBrokerDispatcher(
            registry,
            authorize=lambda _request, uid: "local-cli" if uid == os.getuid() else None,
            verify_session=lambda selected: selected == session,
            write_input=lambda _session, _data: None,
            resize_pty=lambda _session, _columns, _rows: None,
            close_preview=lambda _session: {},
            close_apply=lambda _session, _plan: {"state": "stopped"},
            pty_relay_status=lambda: "not_connected",
        )
        lease = dispatcher(request(operation="terminal.attach", session_id=session), os.getuid())
        registry.publish_output(session, 18, b"final shell output")
        result = dispatcher(request(operation="terminal.output", session_id=session,
            generation=lease["generation"], attachment_id=lease["attachment_id"],
            args={"after_sequence": 0}), os.getuid())
        self.assertTrue(result["session_closed"])
        self.assertEqual(base64.b64decode(result["chunks"][0]["data_base64"]), b"final shell output")

    def test_dispatcher_preview_and_start_are_authenticated_and_plan_bound(self):
        registry = terminal_broker.TerminalAttachmentRegistry(generation=29)
        calls = []
        dispatcher = terminal_broker.TerminalBrokerDispatcher(
            registry,
            authorize=lambda _request, uid: "local-cli" if uid == os.getuid() else None,
            verify_session=lambda _session: True,
            write_input=lambda _session, _data: None,
            resize_pty=lambda _session, _columns, _rows: None,
            close_preview=lambda _session: {},
            close_apply=lambda _session, _plan: {"state": "stopped"},
            start_preview=lambda: {"plan_id": "plan-exact"},
            start_apply=lambda plan, principal: (calls.append((plan, principal)) or {
                "session_id": "proot-" + "d" * 32, "state": "running"}),
            pty_relay_status=lambda: "running",
        )
        preview = dispatcher(request(operation="terminal.start.preview"), os.getuid())
        self.assertEqual(preview["plan"]["plan_id"], "plan-exact")
        with self.assertRaisesRegex(terminal_broker.BrokerError, "confirmation"):
            dispatcher(request(operation="terminal.start", args={
                "confirmed": False, "plan_id": "plan-exact"}), os.getuid())
        started = dispatcher(request(operation="terminal.start", args={
            "confirmed": True, "plan_id": "plan-exact"}), os.getuid())
        self.assertEqual(calls, [("plan-exact", "local-cli")])
        self.assertEqual(started["result"]["state"], "running")
        self.assertEqual(dispatcher(request(operation="broker.status"), os.getuid())["pty_relay"], "running")

    def test_pty_runtime_owns_master_and_relays_only_bounded_terminal_bytes(self):
        master, slave = pty.openpty()
        session = "proot-" + "e" * 32
        record = {"session_id": session, "profile": "debian-interactive",
                  "pid": 424242, "state": "running"}
        exits = []
        registry = terminal_broker.TerminalAttachmentRegistry(generation=31)
        runtime = terminal_broker.TerminalPTYRuntime(
            registry, preview_start=lambda: {"plan_id": "plan-runtime"},
            spawn_login=lambda plan: (self.assertEqual(plan, "plan-runtime") or {
                "record": record, "master_fd": master, "child_pid": 424242}),
            verify_record=lambda selected: selected is record,
            session_members=lambda _pid: [],
            record_exit=lambda selected, state, code: exits.append((selected, state, code)),
            poll_interval=0.02,
        )
        try:
            started = runtime.start("plan-runtime", "test-client", confirmed=True)
            self.assertEqual(started["session_id"], session)
            self.assertTrue(runtime.is_verified(session))
            os.write(slave, b"pty-output")
            output = None
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                output = registry.read_output(session, registry.generation,
                                              started["attachment_id"], "test-client", 0)
                if output["chunks"]:
                    break
                time.sleep(0.02)
            self.assertEqual(output["chunks"][0]["data"], b"pty-output")
            runtime.write_input(session, b"typed-input\n")
            self.assertEqual(os.read(slave, len(b"typed-input\n")), b"typed-input\n")
            runtime.resize(session, 120, 40)
            self.assertEqual(runtime.status(), "running")
            runtime.close()
            self.assertFalse(runtime.is_verified(session))
            replacement = registry.attach(session, "replacement-client")
            self.assertTrue(replacement["writer_attached"])
            registry.detach(session, replacement["generation"],
                           replacement["attachment_id"], "replacement-client")
            self.assertEqual(exits, [(record, "unknown", None)])
            with self.assertRaises(OSError):
                os.fstat(master)
        finally:
            runtime.close()
            os.close(slave)

    def test_pty_runtime_rejects_stale_plan_before_spawning(self):
        registry = terminal_broker.TerminalAttachmentRegistry(generation=32)
        spawned = []
        runtime = terminal_broker.TerminalPTYRuntime(
            registry, preview_start=lambda: {"plan_id": "plan-current"},
            spawn_login=lambda plan: spawned.append(plan) or {},
            verify_record=lambda _record: False,
            session_members=lambda _pid: [], record_exit=lambda *_args: None,
        )
        with self.assertRaisesRegex(terminal_broker.BrokerError, "stale"):
            runtime.start("plan-old", "test-client", confirmed=True)
        self.assertEqual(spawned, [])

if __name__ == "__main__":
    unittest.main()
