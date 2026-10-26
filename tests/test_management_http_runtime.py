"""Tests for the explicit read-only management HTTP foreground runtime."""
from __future__ import annotations

import http.client
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import management_http_runtime  # noqa: E402
import management_authorization  # noqa: E402


PREFIX = "/data/data/com.termux/files/usr"
SECRET = "S" * 48


def native_env(home: str) -> dict[str, str]:
    return {
        "PREFIX": PREFIX,
        "TERMUX_VERSION": "test-termux",
        "HOME": home,
        "TERNUXX_STATE_DIR": str(Path(home) / ".local/share/ternuxx"),
        "PATH": f"{PREFIX}/bin:/usr/bin",
    }


class TernuxxManagementHTTPRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is optional on Native Termux")
    def test_inline_web_javascript_has_valid_syntax_when_node_is_available(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        inline = [match.group(2) for match in re.finditer(
            r"<script\b([^>]*)>(.*?)</script\s*>", page, re.IGNORECASE | re.DOTALL)
            if not re.search(r"\bsrc\s*=", match.group(1), re.IGNORECASE)]
        self.assertTrue(inline, "management page has no inline JavaScript")
        for script in inline:
            subprocess.run(["node", "--check"], input=script, text=True, check=True,
                           capture_output=True, env={k: v for k, v in __import__("os").environ.items() if k != "LD_LIBRARY_PATH"})

    def test_web_ssh_help_matches_publickey_only_service_policy(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        self.assertIn("public-key login only", ui)
        self.assertIn("password login is disabled", ui)
        self.assertNotIn("Keep password recovery", ui)

    def test_web_exposes_authorized_shared_broker_terminal(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn("proot.session.manage", ui)
        self.assertIn("applications.shortcuts.manage", ui)
        self.assertIn('id="terminal-dialog"', ui)
        self.assertIn('/assets/xterm-6.0.0/xterm.js', ui)
        self.assertIn('terminalCall("terminal.start.preview"', ui)
        self.assertIn('terminalCall("terminal.output"', ui)
        self.assertIn('terminalCall("terminal.detach"', ui)
        self.assertNotIn("/api/v1/terminal", ui)
        self.assertNotIn("arbitrary command", ui.lower())

    def test_web_resource_detail_uses_actions_instead_of_duplicate_capability_lists(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn('id="resource-actions"', ui)
        self.assertNotIn('Supported capabilities (', ui)
        self.assertNotIn('Planned capabilities (', ui)
        self.assertIn("Technical API response", ui)

    def test_web_operation_label_map_has_no_duplicate_keys(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        section = ui.split("function operationLabel(op){const known={", 1)[1].split("};return known[op]", 1)[0]
        keys = re.findall(r'"([^"\\]+)"\s*:', section)
        self.assertEqual(len(keys), len(set(keys)), "duplicate Web label silently overrides an earlier value")

    def test_authenticated_page_reconnect_contract_survives_reload(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        self.assertIn("/api/v1/session/reconnect", ui)
        self.assertIn('credentials:"same-origin"', ui)
        self.assertNotIn("document.cookie.indexOf(\'ternuxx_management_session\')", ui)

    def test_web_ui_uses_http_only_session_cookie_and_reconnects_after_reload(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        self.assertIn("/api/v1/session/reconnect", ui)
        self.assertIn('credentials:"same-origin"', ui)
        self.assertIn('function headers(){return {"X-Ternuxx-CSRF":session.csrf_token}}', ui)
        self.assertNotIn('Authorization:"Bearer "+session.bearer_token', ui)

    def test_bootstrap_secret_clipboard_copy_is_stdin_only_and_silent(self) -> None:
        completed = type("Completed", (), {"returncode": 0})()
        with patch.object(management_http_runtime.shutil, "which", return_value="/usr/bin/termux-clipboard-set"), \
             patch.object(management_http_runtime.subprocess, "run", return_value=completed) as run:
            self.assertTrue(management_http_runtime.copy_bootstrap_secret("one-time-private-secret"))
        args, kwargs = run.call_args
        self.assertEqual(args, (["/usr/bin/termux-clipboard-set"],))
        self.assertEqual(kwargs["input"], "one-time-private-secret")
        self.assertEqual(kwargs["stdout"], management_http_runtime.subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], management_http_runtime.subprocess.DEVNULL)
        self.assertNotIn("one-time-private-secret", repr(args))

    def test_default_clipboard_failure_stops_without_disclosing_secret(self) -> None:
        err = io.StringIO()
        err.isatty = lambda: True
        server = type("Server", (), {"port": 8765, "start": lambda self: None,
                                    "close": lambda self, **kwargs: True})()
        with patch.object(management_http_runtime.management_sessions, "new_bootstrap_secret", return_value=SECRET), \
             patch.object(management_http_runtime, "build_server", return_value=server), \
             patch.object(management_http_runtime, "copy_bootstrap_secret", return_value=False), \
             patch.object(management_http_runtime.sys, "stderr", err), \
             patch.object(management_http_runtime.signal, "signal"), \
             patch.object(management_http_runtime.threading, "Event") as event:
            self.assertEqual(management_http_runtime.main(["--port", "8765", "--web", "--browser", "android"]), 1)
        self.assertNotIn(SECRET, err.getvalue())
        self.assertIn("Clipboard copy failed", err.getvalue())
        event.return_value.wait.assert_not_called()

    def test_native_browser_detection_and_interactive_choices(self) -> None:
        with patch.object(management_http_runtime.shutil, "which", return_value="/native/firefox"):
            self.assertEqual(management_http_runtime.detect_native_browser(), ("/native/firefox", "Firefox"))
        native = ("/native/firefox", "Firefox")
        for text in ("3\n", "auto\n", "\n"):
            stream = io.StringIO(text)
            stream.isatty = lambda: True
            with self.subTest(text=text):
                self.assertEqual(management_http_runtime.choose_browser(
                    "choose", native=native, stdin=stream, stderr=io.StringIO()), "native")
        stream = io.StringIO("2\n")
        stream.isatty = lambda: True
        self.assertEqual(management_http_runtime.choose_browser(
            "choose", native=None, stdin=stream, stderr=io.StringIO()), "android")

    def test_failed_browser_and_clipboard_handoffs_stop_or_use_explicit_fallback(self) -> None:
        for explicit in (False, True):
            err = io.StringIO()
            err.isatty = lambda: True
            server = type("Server", (), {"port": 8765, "start": lambda self: None,
                                        "close": lambda self, **kwargs: True})()
            with self.subTest(explicit=explicit), \
                 patch.object(management_http_runtime, "detect_native_browser",
                              return_value=("/native/firefox", "Firefox")), \
                 patch.object(management_http_runtime.management_sessions, "new_bootstrap_secret", return_value=SECRET), \
                 patch.object(management_http_runtime, "build_server", return_value=server) as build, \
                 patch.object(management_http_runtime, "copy_bootstrap_secret", return_value=False), \
                 patch.object(management_http_runtime, "open_browser", return_value=(False, False)), \
                 patch.object(management_http_runtime.sys, "stderr", err), \
                 patch.object(management_http_runtime.signal, "signal"), \
                 patch.object(management_http_runtime.threading, "Event") as event:
                argv = ["--port", "8765", "--web", "--browser", "native"]
                if explicit:
                    argv.append("--show-secret-on-clipboard-failure")
                self.assertEqual(management_http_runtime.main(argv), 0 if explicit else 1)
                self.assertEqual(SECRET in err.getvalue(), explicit)
                self.assertEqual(build.call_args.kwargs["env"]["TERNUXX_WEB_MODE"], "1")
                self.assertEqual(event.return_value.wait.called, explicit)

    def test_readonly_command_cannot_inherit_web_mutation_mode(self) -> None:
        err = io.StringIO()
        err.isatty = lambda: True
        server = type("Server", (), {"port": 8765, "start": lambda self: None,
                                    "close": lambda self, **kwargs: True})()
        with patch.dict(management_http_runtime.os.environ, {"TERNUXX_WEB_MODE": "1"}), (
             patch.object(management_http_runtime, "build_server", return_value=server)) as build, (
             patch.object(management_http_runtime.sys, "stderr", err)), (
             patch.object(management_http_runtime.signal, "signal")), (
             patch.object(management_http_runtime.threading, "Event")):
            self.assertEqual(management_http_runtime.main(["--port", "8765"]), 0)
            self.assertEqual(build.call_args.kwargs["env"]["TERNUXX_WEB_MODE"], "0")
            self.assertEqual(management_http_runtime.os.environ["TERNUXX_WEB_MODE"], "1")

    def test_clipboard_copy_failure_is_reported_as_boolean_only(self) -> None:
        with patch.object(management_http_runtime.shutil, "which", return_value=None):
            self.assertFalse(management_http_runtime.copy_bootstrap_secret("secret"))

    def test_web_page_has_compact_portfolio_branding(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        self.assertIn("Workstation in your pocket — by Sobuj Miah", page)
        self.assertIn('href="https://soobujmiah.github.io/"', page)
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-http-runtime-")
        self.env = native_env(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_requires_native_termux_and_valid_bootstrap_secret(self) -> None:
        with self.assertRaises(ValueError):
            management_http_runtime.build_server(
                port=0, bootstrap_secret=SECRET, env={"HOME": self.temp.name})
        invalid = dict(self.env)
        invalid["PREFIX"] = "/usr"
        with self.assertRaises(ValueError):
            management_http_runtime.build_server(
                port=0, bootstrap_secret=SECRET, env=invalid)
        with self.assertRaises(ValueError):
            management_http_runtime.build_server(
                port=0, bootstrap_secret="short", env=self.env)

    def test_runtime_bootstrap_is_read_only_and_mutations_stay_disabled(self) -> None:
        server = management_http_runtime.build_server(
            port=0, bootstrap_secret=SECRET, env=self.env)
        self.assertEqual(server.address[0], "127.0.0.1")
        self.assertFalse(server.adapter._allow_mutations)
        self.assertNotIn("applications.launch", server.adapter.sessions._bootstrap_capabilities)
        server.start()
        connection = http.client.HTTPConnection(*server.address, timeout=3)
        try:
            body = json.dumps({
                "bootstrap_secret": SECRET,
                "capabilities": ["services.manage"],
            }).encode()
            connection.request("POST", "/api/v1/session", body=body, headers={
                "Host": f"127.0.0.1:{server.port}",
                "Origin": f"http://127.0.0.1:{server.port}",
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(body)),
            })
            response = connection.getresponse()
            rejection = json.loads(response.read())
            self.assertEqual(response.status, 401)
            self.assertEqual(rejection["error"], "authentication_failed")
            connection.close()

            connection = http.client.HTTPConnection(*server.address, timeout=3)
            body = json.dumps({
                "bootstrap_secret": SECRET,
                "capabilities": ["diagnostics.read"],
            }).encode()
            connection.request("POST", "/api/v1/session", body=body, headers={
                "Host": f"127.0.0.1:{server.port}",
                "Origin": f"http://127.0.0.1:{server.port}",
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(body)),
            })
            response = connection.getresponse()
            cookie = response.getheader("Set-Cookie")
            issued = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertNotIn(SECRET, json.dumps(issued))
            self.assertNotIn("bearer_token", issued["session"])
            self.assertIsNotNone(cookie)
            cookie = cookie.split(";", 1)[0]
            self.assertIn("HttpOnly", response.getheader("Set-Cookie"))
            body = b"{}"
            connection.request("POST", "/api/v1/session/reconnect", body=body, headers={
                "Host": f"127.0.0.1:{server.port}",
                "Origin": f"http://127.0.0.1:{server.port}",
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(body)),
                "Cookie": cookie,
            })
            resumed_response = connection.getresponse()
            resumed = json.loads(resumed_response.read())
            self.assertEqual(resumed_response.status, 200)
            self.assertEqual(resumed["session"]["session_ref"], issued["session"]["session_ref"])
            self.assertNotIn("bearer_token", resumed["session"])
            self.assertNotEqual(resumed["session"]["csrf_token"], "")
            connection.close()
        finally:
            connection.close()
            self.assertTrue(server.close(grace_seconds=3))

    def test_web_ssh_key_inventory_control_uses_its_separate_capability(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn("ssh.credentials.read", ui)
        self.assertIn("View shared SSH key fingerprints", ui)
        self.assertIn('b.onclick=()=>run("ssh.keys.list")', ui)

    def test_web_ui_requests_authorized_backup_restore_and_curated_software_capabilities(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        for capability in ("state.backup", "state.restore", "recovery.manage", "software.manage"):
            with self.subTest(capability=capability):
                self.assertIn('"' + capability + '"', ui)
                self.assertIn(capability, management_http_runtime.WEB_CAPABILITIES)
        self.assertIn('"backup.create"', ui)
        self.assertIn('"restore.apply"', ui)
        self.assertIn('"recovery.resolve"', ui)
        self.assertIn('"recovery.rollback.apply"', ui)

    def test_web_replay_guest_controls_use_narrow_capability_and_exact_preview(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        for capability in ("proot.replay.manage",):
            self.assertIn('"' + capability + '"', ui)
            self.assertIn(capability, management_http_runtime.WEB_CAPABILITIES)
        self.assertNotIn("proot.guest.manage", management_http_runtime.WEB_CAPABILITIES)
        self.assertIn("proot.install.manage", management_http_runtime.WEB_CAPABILITIES)
        for operation in ("proot.setup.retire.preview", "proot.setup.retire.apply",
                          "proot.setup.restore.preview", "proot.setup.restore.apply"):
            with self.subTest(operation=operation):
                self.assertIn(operation, management_http_runtime._WEB_MUTATING_OPERATIONS)
        self.assertTrue({"proot.setup.icd-migrate.preview", "proot.setup.icd-migrate.apply",
                         "proot.setup.icd-migrate.rollback.preview",
                         "proot.setup.icd-migrate.rollback.apply"}.isdisjoint(
                             management_http_runtime._WEB_MUTATING_OPERATIONS))
        for contract in ("async function manageReplayGuest()", 'r.id==="proot.replay-guests"',
                         'previewOperation="proot.setup.retire.preview"',
                         'previewOperation="proot.setup.restore.preview"',
                         'const preview=await run(previewOperation,previewArgs)',
                         'operation?.alias!==target', 'operation?.confirmation_required!==true',
                         'action==="restore"&&operation?.backup_id!==backupId',
                         'run(applyOperation,args)', 'Type "+token+" to apply'):
            with self.subTest(contract=contract):
                self.assertIn(contract, ui)

    def test_web_replay_guest_mutations_require_narrow_scope_csrf_and_idempotency(self) -> None:
        env = dict(self.env, TERNUXX_WEB_MODE="1")
        Path(env["TERNUXX_STATE_DIR"]).mkdir(parents=True, mode=0o700)
        Path(env["TERNUXX_STATE_DIR"]).chmod(0o700)
        alias, plan_id = "ternuxx-replay-p4", "a" * 64
        with patch.object(management_http_runtime.management_service, "dispatch") as dispatch:
            server = management_http_runtime.build_server(port=0, bootstrap_secret=SECRET, env=env)
            try:
                session = server.adapter.sessions.exchange_bootstrap(SECRET, ["proot.replay.manage"])
                host = "127.0.0.1:%s" % server.port

                def post(operation: str, request_id: str, args: dict[str, object], *, csrf: bool = True):
                    body = json.dumps({"api_version": 1, "request_id": request_id,
                                       "operation": operation, "args": args}).encode()
                    headers = {"Host": host, "Origin": "http://" + host,
                               "Content-Type": "application/json", "Content-Length": str(len(body)),
                               "Authorization": "Bearer " + session.bearer_token,
                               "Idempotency-Key": "replay-key-" + request_id}
                    if csrf:
                        headers["X-Ternuxx-CSRF"] = session.csrf_token
                    return server.adapter.handle(method="POST", path="/api/v1/operations",
                                                 headers=headers, body=body)

                status, _headers, body = post("proot.setup.retire.preview", "replay-preview-001",
                    {"alias": alias}, csrf=False)
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(body)["error"], "csrf_rejected")
                dispatch.assert_not_called()

                dispatch.return_value = {"api_version": 1, "request_id": "replay-preview-001",
                    "ok": True, "operation": "proot.setup.retire.preview",
                    "data": {"plan_id": plan_id, "operation": {"alias": alias}}}
                status, _headers, body = post("proot.setup.retire.preview", "replay-preview-002",
                    {"alias": alias})
                self.assertEqual(status, 200, body)
                self.assertEqual(dispatch.call_args.args[0]["operation"], "proot.setup.retire.preview")
                self.assertEqual(dispatch.call_args.args[0]["args"], {"alias": alias})

                dispatch.return_value = {"api_version": 1, "request_id": "replay-apply-001",
                    "ok": True, "operation": "proot.setup.retire.apply",
                    "data": {"status": "retired", "files_deleted": False}}
                status, _headers, body = post("proot.setup.retire.apply", "replay-apply-002",
                    {"alias": alias, "confirmed": True, "plan_id": plan_id})
                self.assertEqual(status, 200, body)
                self.assertEqual(dispatch.call_args.args[0]["operation"], "proot.setup.retire.apply")
                self.assertEqual(dispatch.call_args.args[0]["args"],
                    {"alias": alias, "confirmed": True, "plan_id": plan_id})
            finally:
                self.assertTrue(server.close(grace_seconds=3))

    def test_web_checkpoint_and_reboot_qualification_use_separate_scoped_capabilities(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        self.assertIn('"continuity.checkpoint.manage"', ui)
        self.assertIn("continuity.checkpoint.manage", management_http_runtime.WEB_CAPABILITIES)
        self.assertNotIn("continuity.manage", management_http_runtime.WEB_CAPABILITIES)
        self.assertIn('"continuity.reboot-test.manage"', ui)
        self.assertIn("continuity.reboot-test.manage", management_http_runtime.WEB_CAPABILITIES)
        self.assertIn('"continuity.prepare.preview"', ui)
        self.assertIn('"continuity.verify.preview"', ui)
        self.assertIn('"continuity.prepare-reboot-test.preview"', ui)
        self.assertIn('"continuity.verify-reboot-test.preview"', ui)
        self.assertIn("continuity.prepare-reboot-test", management_http_runtime._WEB_MUTATING_OPERATIONS)
        self.assertIn("continuity.verify-reboot-test", management_http_runtime._WEB_MUTATING_OPERATIONS)

    def test_web_mode_exposes_scoped_desktop_monitoring_and_managed_ssh_8023_mutations(self) -> None:
        env = dict(self.env, TERNUXX_WEB_MODE="1")
        Path(env["TERNUXX_STATE_DIR"]).mkdir(parents=True, mode=0o700)
        Path(env["TERNUXX_STATE_DIR"]).chmod(0o700)
        with patch.object(management_http_runtime.management_service, "dispatch") as dispatch:
            server = management_http_runtime.build_server(
                port=0, bootstrap_secret=SECRET, env=env)
            try:
                self.assertTrue(server.adapter._allow_mutations)
                self.assertTrue(server.adapter._request_store.durable)
                self.assertEqual(server.adapter.sessions._bootstrap_capabilities,
                                 management_http_runtime.WEB_CAPABILITIES)
                session = server.adapter.sessions.exchange_bootstrap(
                    SECRET, sorted(management_http_runtime.WEB_CAPABILITIES))
                host = "127.0.0.1:%s" % server.port

                def post(operation: str, request_id: str, key: str, args: dict[str, object], *, csrf: bool = True):
                    body = json.dumps({"api_version": 1, "request_id": request_id,
                                       "operation": operation, "args": args}).encode()
                    headers = {"Host": host, "Origin": "http://" + host,
                               "Content-Type": "application/json", "Content-Length": str(len(body)),
                               "Authorization": "Bearer " + session.bearer_token,
                               "Idempotency-Key": key}
                    if csrf:
                        headers["X-Ternuxx-CSRF"] = session.csrf_token
                    return server.adapter.handle(method="POST", path="/api/v1/operations",
                                                 headers=headers, body=body)

                dispatch.return_value = {"api_version": 1, "request_id": "web-start-result-1",
                    "ok": True, "operation": "desktop.start", "data": {"state": "running"}}
                status, _headers, response = post("desktop.start", "web-start-request-01",
                    "web-start-key-00000001", {"display": ":1"})
                self.assertEqual(status, 200, response)
                self.assertEqual(json.loads(response)["operation"], "desktop.start")
                dispatch.assert_called_once()

                status, _headers, response = post("desktop.stop", "web-stop-request-001",
                    "web-stop-key-000000001", {}, csrf=False)
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(response)["error"], "csrf_rejected")
                self.assertEqual(dispatch.call_count, 1)

                dispatch.return_value = {"api_version": 1, "request_id": "web-ssh-preview-001",
                    "ok": True, "operation": "ssh.service.stop", "data": {
                        "service_id": "ternuxx-sshd", "current_status": "running",
                        "requires_confirmation": True, "plan_id": "a" * 64,
                        "impact": "Stops only the managed SSH unit."}}
                status, _headers, response = post("ssh.service.stop", "web-ssh-request-001",
                    "web-ssh-key-000000001", {"confirmed": False, "plan_id": None})
                self.assertEqual(status, 200, response)
                self.assertEqual(json.loads(response)["operation"], "ssh.service.stop")
                self.assertEqual(dispatch.call_count, 2)

                self.assertIn("services.manage", management_http_runtime.WEB_CAPABILITIES)
                self.assertIn("ssh.service.deploy", management_http_runtime._WEB_MUTATING_OPERATIONS)
                self.assertIn("ssh.service.deploy.rollback.apply", management_http_runtime._WEB_MUTATING_OPERATIONS)
                dispatch.return_value = {"api_version": 1, "request_id": "web-ssh-deploy-result-001",
                    "ok": True, "operation": "ssh.service.deploy", "data": {
                        "service_id": "ternuxx-sshd", "changed": True,
                        "requires_confirmation": True, "plan_id": "d" * 64,
                        "impact": "Atomically replaces only the fixed Runit run definition."}}
                status, _headers, response = post("ssh.service.deploy", "web-ssh-deploy-001",
                    "web-ssh-deploy-key-0001", {"confirmed": False, "plan_id": None})
                self.assertEqual(status, 200, response)
                self.assertEqual(json.loads(response)["operation"], "ssh.service.deploy")
                self.assertEqual(dispatch.call_count, 3)

                dispatch.return_value = {"api_version": 1, "request_id": "web-ssh-deploy-apply-result-001",
                    "ok": True, "operation": "ssh.service.deploy", "data": {"status": "complete"}}
                status, _headers, response = post("ssh.service.deploy", "web-ssh-deploy-apply-01",
                    "web-ssh-deploy-apply-key", {"confirmed": True, "plan_id": "d" * 64})
                self.assertEqual(status, 200, response)
                self.assertEqual(dispatch.call_count, 4)

                dispatch.return_value = {"api_version": 1, "request_id": "web-history-read-001",
                    "ok": True, "operation": "recovery.status", "data": {
                        "operations": [{"kind": "service.start", "status": "complete"}],
                        "unresolved_count": 0, "read_only": True}}
                status, _headers, response = post("recovery.status", "web-history-request-01",
                    "web-history-key-00001", {})
                self.assertEqual(status, 200, response)
                self.assertEqual(json.loads(response)["operation"], "recovery.status")
                self.assertEqual(dispatch.call_count, 5)

                dispatch.return_value = {"api_version": 1, "request_id": "web-timezone-result-001",
                    "ok": True, "operation": "timezone.set", "data": {"timezone": "UTC"}}
                status, _headers, response = post("timezone.set", "web-timezone-request-001",
                    "web-timezone-key-00001", {"timezone": "UTC"})
                self.assertEqual(status, 200, response)
                self.assertEqual(json.loads(response)["operation"], "timezone.set")
                self.assertEqual(dispatch.call_count, 6)

                dispatch.return_value = {"api_version": 1, "request_id": "web-cron-start-result-01",
                    "ok": True, "operation": "cron.scheduler.start", "data": {"status": "running"}}
                status, _headers, response = post("cron.scheduler.start", "web-cron-start-request-01",
                    "web-cron-start-key-0001", {"poll_seconds": 10, "confirmed": True})
                self.assertEqual(status, 200, response)
                self.assertEqual(json.loads(response)["operation"], "cron.scheduler.start")
                self.assertEqual(dispatch.call_count, 7)

                dispatch.return_value = {"api_version": 1, "request_id": "web-cron-create-result-01",
                    "ok": True, "operation": "cron.jobs.mutation.preview", "data": {"plan": {"plan_id": "a" * 32}}}
                typed_cron = {"action": "create", "name": "web job", "action_id": "diagnostics.doctor",
                    "schedule_type": "one_time", "schedule": {"at": "2099-01-01T08:30:00+06:00"}}
                status, _headers, response = post("cron.jobs.mutation.preview", "web-cron-create-request-01",
                    "web-cron-create-key-0001", typed_cron)
                self.assertEqual(status, 200, response)
                dispatched = dispatch.call_args.args[0]
                self.assertEqual(dispatched["operation"], "cron.jobs.mutation.preview")
                self.assertEqual(dispatched["args"], typed_cron)
                self.assertEqual(dispatch.call_count, 8)

                status, _headers, response = post("proot.app.launch", "web-proot-launch-01",
                    "web-proot-launch-key1", {"app_id": "files"})
                self.assertEqual(status, 200)
                self.assertEqual(dispatch.call_count, 9)

                dispatch.return_value = {"api_version": 1, "request_id": "web-failure-result-1",
                    "ok": False, "error": {"code": "desktop_operation_failed", "message": "redacted"}}
                status, _headers, response = post("desktop.restart", "web-restart-request-01",
                    "web-restart-key-0000001", {"display": ":1"})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(response)["error"]["code"], "desktop_operation_failed")
                self.assertNotIn("redacted", response.decode())
            finally:
                self.assertTrue(server.close(grace_seconds=1))

    def test_ssh_definition_deploy_is_denied_without_opt_in_web_session_scope(self) -> None:
        env = dict(self.env, TERNUXX_WEB_MODE="1")
        Path(env["TERNUXX_STATE_DIR"]).mkdir(parents=True, mode=0o700)
        Path(env["TERNUXX_STATE_DIR"]).chmod(0o700)
        with patch.object(management_http_runtime.management_service, "dispatch") as dispatch:
            server = management_http_runtime.build_server(port=0, bootstrap_secret=SECRET, env=env)
            try:
                caps = sorted(management_http_runtime.WEB_CAPABILITIES - {"services.manage"})
                session = server.adapter.sessions.exchange_bootstrap(SECRET, caps)
                host = "127.0.0.1:%s" % server.port
                body = json.dumps({"api_version": 1, "request_id": "web-no-service-scope-001",
                    "operation": "ssh.service.deploy", "args": {"confirmed": False, "plan_id": None}}).encode()
                status, _headers, response = server.adapter.handle(method="POST", path="/api/v1/operations",
                    headers={"Host": host, "Origin": "http://" + host,
                        "Content-Type": "application/json", "Content-Length": str(len(body)),
                        "Authorization": "Bearer " + session.bearer_token,
                        "X-Ternuxx-CSRF": session.csrf_token,
                        "Idempotency-Key": "web-no-service-scope-key"}, body=body)
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(response)["error"], "permission_denied")
                dispatch.assert_not_called()
            finally:
                self.assertTrue(server.close(grace_seconds=1))

    def test_service_definition_scope_is_opt_in_and_controls_actions(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        self.assertIn('id="ssh-definition-scope" type="checkbox"', ui)
        self.assertIn('if($("#ssh-definition-scope").checked)capabilities.push("services.manage")', ui)
        self.assertIn('session?.capabilities?.includes("services.manage")', ui)
        self.assertIn("Review and deploy SSH service definition", ui)
        self.assertIn("Restore previous SSH service definition", ui)
        page = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn('id="categories"', page)
        self.assertIn('id="search"', page)
        self.assertIn('id="resource-detail"', page)
        self.assertIn("window.confirm", page)
        self.assertIn("Idempotency-Key", page)
        self.assertIn("desktop.monitor.manage", page)
        self.assertIn("proot.session.manage", page)
        self.assertIn("desktop.manage", page)
        self.assertIn("ai.local.run", page)
        self.assertIn("ai.local.manage", page)
        self.assertEqual(page.count('if(r.id==="inference.cpu.local"){'), 1)
        self.assertIn('run("inference.cpu.run"', page)
        self.assertIn('if(r.id==="inference.gpu.local"){', page)
        self.assertIn('run("inference.gpu.status"', page)
        self.assertIn('run("inference.gpu.run"', page)
        self.assertIn('if(r.id==="inference.npu.local"){', page)
        self.assertIn('run("inference.npu.status"', page)
        self.assertIn('run("inference.npu.runtime.preview"', page)
        self.assertIn('run("inference.npu.runtime.apply"', page)
        self.assertIn('run("inference.npu.run"', page)
        self.assertIn('Type INSTALL to apply this exact preview', page)
        self.assertIn('CPU fallback is disabled', page)
        self.assertIn('run("inference.cpu.model.preview"', page)
        self.assertIn('run("inference.cpu.model.apply"', page)
        self.assertIn("ssh.managed.lifecycle", page)
        self.assertIn("network.ssh.managed-8023", page)
        self.assertIn("Recent management activity", page)
        self.assertIn("Load recent activity", page)
        self.assertIn('run("recovery.status")', page)
        self.assertIn('id="logs-panel"', page)
        self.assertIn("management.logs.read", page)
        self.assertIn('id="monitor-panel" hidden', page)
        self.assertIn('monitorPanel.hidden=r?.id!=="native.gui.activity-monitor"', page)
        self.assertIn("grid-template-columns:repeat(auto-fit,minmax(min(100%,13rem),1fr))", page)
        self.assertIn("Use experimental KGSL candidate", page)
        self.assertIn("KGSL is experimental, must already be extracted", page)
        self.assertIn("offline behavior is unverified", page)
        self.assertIn("Technical API response", page)
        self.assertNotIn("network.ssh.external-native", page.split("manageSsh(operation)", 1)[-1].split("function drawCategories", 1)[0])
        self.assertIn("proot.session.manage", page)
        self.assertIn("xterm", page)
        self.assertIn('run("terminal.broker.status"', page)
        self.assertIn("Open Debian terminal", page)
        self.assertIn("terminal.start.preview", page)
        self.assertIn("terminal.broker.service.status", page)
        self.assertIn("terminal.broker.service.start.preview", page)
        self.assertIn("terminal.broker.service.start.apply", page)
        self.assertIn("async function prepareWebTerminalBroker", page)
        self.assertIn("applications.launch", page)
        self.assertIn("applications.shortcuts.manage", page)
        self.assertIn("Preview bounded headless guest probe", page)
        self.assertIn('id="proot-install-scope"', page)
        self.assertIn('capabilities.push("proot.install.manage")', page)
        self.assertIn('operations.includes("proot.setup.fresh.preview")', page)
        self.assertIn('run("proot.setup.fresh.apply",args)', page)

    def test_boot_cron_web_scope_is_opt_in_and_narrow(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        self.assertIn('id="boot-cron-scope" type="checkbox"', ui)
        self.assertIn('if($("#boot-cron-scope").checked)capabilities.push("boot.cron.manage")', ui)
        self.assertIn('session?.capabilities?.includes("boot.cron.manage")', ui)
        self.assertIn('manageBootCron(action)', ui)
        self.assertIn('operation==="boot.cron.preview"', ui)
        self.assertEqual(management_authorization.required_capability("boot.cron.enable"), "boot.cron.manage")
        self.assertEqual(management_authorization.required_capability("boot.cron.disable"), "boot.cron.manage")
        self.assertEqual({op for op, cap in management_authorization.OPERATION_CAPABILITIES.items()
                          if cap == "boot.cron.manage"}, {"boot.cron.enable", "boot.cron.disable"})
        self.assertTrue({"boot.cron.enable", "boot.cron.disable"} <=
                        management_http_runtime._WEB_MUTATING_OPERATIONS)

    def test_boot_helper_web_scope_is_opt_in_and_narrow(self) -> None:
        ui = (ROOT / "lib" / "management_web_ui.html").read_text(encoding="utf-8")
        self.assertIn('id="boot-helpers-scope" type="checkbox"', ui)
        self.assertIn('if($("#boot-helpers-scope").checked)capabilities.push("boot.helpers.manage")', ui)
        self.assertIn('session?.capabilities?.includes("boot.helpers.manage")', ui)
        self.assertIn('operation==="boot.helpers.preview"||operation==="boot.helpers.apply"', ui)
        self.assertIn('async function manageBootHelpers()', ui)
        self.assertEqual(management_authorization.required_capability("boot.helpers.preview"), "boot.helpers.manage")
        self.assertEqual(management_authorization.required_capability("boot.helpers.apply"), "boot.helpers.manage")
        self.assertEqual({op for op, cap in management_authorization.OPERATION_CAPABILITIES.items()
                          if cap == "boot.helpers.manage"}, {"boot.helpers.preview", "boot.helpers.apply"})
        self.assertTrue({"boot.helpers.preview", "boot.helpers.apply"} <=
                        management_http_runtime._WEB_MUTATING_OPERATIONS)

    def test_boot_helper_web_apply_is_denied_without_opt_in_scope(self) -> None:
        env = dict(self.env, TERNUXX_WEB_MODE="1")
        Path(env["TERNUXX_STATE_DIR"]).mkdir(parents=True, mode=0o700)
        Path(env["TERNUXX_STATE_DIR"]).chmod(0o700)
        with patch.object(management_http_runtime.management_service, "dispatch") as dispatch:
            server = management_http_runtime.build_server(port=0, bootstrap_secret=SECRET, env=env)
            try:
                session = server.adapter.sessions.exchange_bootstrap(
                    SECRET, sorted(management_http_runtime.WEB_CAPABILITIES - {"boot.helpers.manage"}))
                host = "127.0.0.1:%s" % server.port
                body = json.dumps({"api_version": 1, "request_id": "web-no-boot-helper-scope-001",
                    "operation": "boot.helpers.apply", "args": {"helper_id": "services", "action": "deploy",
                        "confirmed": True, "plan_id": "a" * 32}}).encode()
                status, _headers, response = server.adapter.handle(method="POST", path="/api/v1/operations",
                    headers={"Host": host, "Origin": "http://" + host,
                        "Content-Type": "application/json", "Content-Length": str(len(body)),
                        "Authorization": "Bearer " + session.bearer_token,
                        "X-Ternuxx-CSRF": session.csrf_token, "Idempotency-Key": "web-no-boot-helper-scope-key"},
                    body=body)
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(response)["error"], "permission_denied")
                dispatch.assert_not_called()
            finally:
                self.assertTrue(server.close(grace_seconds=1))

    def test_boot_helper_web_apply_dispatches_with_opt_in_scope(self) -> None:
        env = dict(self.env, TERNUXX_WEB_MODE="1")
        Path(env["TERNUXX_STATE_DIR"]).mkdir(parents=True, mode=0o700)
        Path(env["TERNUXX_STATE_DIR"]).chmod(0o700)
        with patch.object(management_http_runtime.management_service, "dispatch",
                          return_value={"api_version": 1, "request_id": "web-boot-helper-result-01",
                              "ok": True, "operation": "boot.helpers.apply", "data": {"changed": True}}) as dispatch:
            server = management_http_runtime.build_server(port=0, bootstrap_secret=SECRET, env=env)
            try:
                session = server.adapter.sessions.exchange_bootstrap(SECRET, ["diagnostics.read", "boot.helpers.manage"])
                host = "127.0.0.1:%s" % server.port
                body = json.dumps({"api_version": 1, "request_id": "web-boot-helper-request-001",
                    "operation": "boot.helpers.apply", "args": {"helper_id": "services", "action": "deploy",
                        "confirmed": True, "plan_id": "a" * 32}}).encode()
                status, _headers, response = server.adapter.handle(method="POST", path="/api/v1/operations",
                    headers={"Host": host, "Origin": "http://" + host,
                        "Content-Type": "application/json", "Content-Length": str(len(body)),
                        "Authorization": "Bearer " + session.bearer_token,
                        "X-Ternuxx-CSRF": session.csrf_token, "Idempotency-Key": "web-boot-helper-scope-key"},
                    body=body)
                self.assertEqual(status, 200, response)
                dispatch.assert_called_once()
                self.assertEqual(dispatch.call_args.args[0]["operation"], "boot.helpers.apply")
            finally:
                self.assertTrue(server.close(grace_seconds=1))

    def test_boot_cron_web_apply_is_denied_without_opt_in_scope(self) -> None:
        env = dict(self.env, TERNUXX_WEB_MODE="1")
        Path(env["TERNUXX_STATE_DIR"]).mkdir(parents=True, mode=0o700)
        Path(env["TERNUXX_STATE_DIR"]).chmod(0o700)
        with patch.object(management_http_runtime.management_service, "dispatch") as dispatch:
            server = management_http_runtime.build_server(port=0, bootstrap_secret=SECRET, env=env)
            try:
                session = server.adapter.sessions.exchange_bootstrap(
                    SECRET, sorted(management_http_runtime.WEB_CAPABILITIES - {"boot.cron.manage"}))
                host = "127.0.0.1:%s" % server.port
                body = json.dumps({"api_version": 1, "request_id": "web-no-boot-cron-scope-001",
                    "operation": "boot.cron.enable", "args": {"confirmed": True, "plan_id": "a" * 64}}).encode()
                status, _headers, response = server.adapter.handle(method="POST", path="/api/v1/operations",
                    headers={"Host": host, "Origin": "http://" + host,
                        "Content-Type": "application/json", "Content-Length": str(len(body)),
                        "Authorization": "Bearer " + session.bearer_token,
                        "X-Ternuxx-CSRF": session.csrf_token, "Idempotency-Key": "web-no-boot-cron-scope-key"},
                    body=body)
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(response)["error"], "permission_denied")
                dispatch.assert_not_called()
            finally:
                self.assertTrue(server.close(grace_seconds=1))

    def test_boot_cron_web_apply_dispatches_with_opt_in_scope(self) -> None:
        env = dict(self.env, TERNUXX_WEB_MODE="1")
        Path(env["TERNUXX_STATE_DIR"]).mkdir(parents=True, mode=0o700)
        Path(env["TERNUXX_STATE_DIR"]).chmod(0o700)
        with patch.object(management_http_runtime.management_service, "dispatch",
                          return_value={"api_version": 1, "request_id": "web-boot-cron-result-01",
                              "ok": True, "operation": "boot.cron.enable", "data": {"changed": True}}) as dispatch:
            server = management_http_runtime.build_server(port=0, bootstrap_secret=SECRET, env=env)
            try:
                session = server.adapter.sessions.exchange_bootstrap(SECRET, ["diagnostics.read", "boot.cron.manage"])
                host = "127.0.0.1:%s" % server.port
                body = json.dumps({"api_version": 1, "request_id": "web-boot-cron-request-001",
                    "operation": "boot.cron.enable", "args": {"confirmed": True, "plan_id": "a" * 64}}).encode()
                status, _headers, response = server.adapter.handle(method="POST", path="/api/v1/operations",
                    headers={"Host": host, "Origin": "http://" + host,
                        "Content-Type": "application/json", "Content-Length": str(len(body)),
                        "Authorization": "Bearer " + session.bearer_token,
                        "X-Ternuxx-CSRF": session.csrf_token, "Idempotency-Key": "web-boot-cron-scope-key"},
                    body=body)
                self.assertEqual(status, 200, response)
                dispatch.assert_called_once()
                self.assertEqual(dispatch.call_args.args[0]["operation"], "boot.cron.enable")
            finally:
                self.assertTrue(server.close(grace_seconds=1))

    def test_web_console_has_bounded_mobile_layout_and_touch_navigation_rules(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn('<meta name="viewport" content="width=device-width,initial-scale=1">', page)
        self.assertIn('@media(max-width:760px)', page)
        self.assertIn('grid-template-columns:minmax(0,1fr)', page)
        self.assertIn('max-width:100%', page)
        self.assertIn('min-height:44px', page)
        self.assertIn('overscroll-behavior-inline:contain', page)
        self.assertIn('max-width:min(42vw,17rem);white-space:normal', page)
        self.assertIn('window.addEventListener("resize",revealActiveCategory', page)
        self.assertIn('@media(max-width:380px)', page)
        self.assertIn('font:15px system-ui,sans-serif', page)
        for handler in ('$("#connect").onclick=connect', '$("#disconnect").onclick=',
                        '$("#refresh").onclick=', '$("#search").oninput=drawResources',
                        '$("#status").onchange=drawResources', '$("#save-monitor").onclick='):
            self.assertIn(handler, page)
        self.assertIn('document.querySelectorAll("[data-op]").forEach(button=>button.onclick=()=>run(button.dataset.op))', page)
        self.assertIn('card.onclick=()=>selectResource(resource)', page)
        self.assertIn('automation.cron-registry', page)
        self.assertIn('b.textContent="List saved jobs"', page)
        self.assertIn('b.onclick=()=>run("cron.jobs.list")', page)
        self.assertIn('async function inspectRecovery(kind)', page)
        self.assertIn('inspectRecovery(kind)', page)
        self.assertIn('"recovery.rollback.preview"', page)

    def test_web_proot_resource_has_one_shared_status_control(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertEqual(page.count('run("proot.status")'), 0)
        self.assertIn('statusOp==="proot.status"?"Check Debian and PRoot status"', page)
        self.assertIn('b.onclick=()=>run(statusOp)', page)

    def test_web_proot_stop_filters_verified_running_sessions_and_uses_exact_plan(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn('async function stopManagedProotSession()', page)
        self.assertIn('item.ownership==="ternuxx_verified"&&item.state==="running"', page)
        self.assertIn('run("proot.stop.preview",{session_id:sessionId})', page)
        self.assertIn('run("proot.stop",{session_id:sessionId,confirmed:true,plan_id:plan.plan_id})', page)

    def test_web_proot_reconciliation_requires_positive_exit_preview(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn('async function reconcileManagedProotSession()', page)
        self.assertIn('item.state!=="stopped"', page)
        self.assertIn('run("proot.recovery.inspect",{session_id:sessionId})', page)
        self.assertIn('run("proot.recovery.reconcile.preview",{session_id:sessionId})', page)
        self.assertIn('!/^plan-[0-9a-f]{64}$/.test(plan.plan_id)', page)
        self.assertIn('run("proot.recovery.reconcile",{session_id:sessionId,confirmed:true,plan_id:plan.plan_id})', page)
        self.assertIn('"continuity.status"', page)
        self.assertIn('inspectCronItem("job")', page)
        self.assertIn('previewCronRuns', page)
        self.assertIn('"cron.jobs.show"', page)
        self.assertIn('"cron.jobs.next_runs"', page)
        self.assertIn('"cron.executions.show"', page)
        self.assertIn('b.onclick=()=>run("cron.executions.list",{limit:20})', page)
        self.assertIn('b.onclick=()=>run("timezone.list")', page)

    def test_web_proot_shortcuts_use_inventory_exact_preview_and_typed_apply(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn('async function manageProotShortcut()', page)
        self.assertIn('item.shortcut_state==="absent"||item.shortcut_state==="installed"', page)
        self.assertIn('run("proot.shortcuts.preview",{action,app_id:item.id})', page)
        self.assertIn('const token=action==="add"?"ADD SHORTCUT":"REMOVE SHORTCUT"', page)
        self.assertIn('run("proot.shortcuts.apply",{action,app_id:item.id,confirmed:true,plan_id:plan.plan_id})', page)
        self.assertIn('Debian shortcuts · ', page)
        self.assertIn('function humanReport(value){if(value?.data?.resource_id==="proot.x11.shortcuts")', page)

    def test_web_proot_setup_runs_from_authenticated_ui_and_keeps_password_ephemeral(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text()
        self.assertIn('id="guest-password" type="password"', page)
        self.assertIn('id="proot-install-scope"', page)
        self.assertIn('async function installManagedGuest()', page)
        self.assertIn('run("proot.setup.fresh.preview"', page)
        self.assertIn('run("proot.setup.fresh.apply",args)', page)
        self.assertIn('args.password=""', page)
        self.assertIn('existing_guests_are_preserved', page) if 'existing_guests_are_preserved' in page else self.assertIn('Existing guests are preserved.', page)
        self.assertIn('Ubuntu currently offers XFCE; Debian offers the wider desktop catalog', page)

    def test_web_proot_shortcut_sync_and_rollback_are_preview_confirmed(self) -> None:
        page = (ROOT / "lib" / "management_web_ui.html").read_text()
        for contract in ('async function syncProotShortcuts()',
                         'run("proot.shortcuts.sync.preview")',
                         'run("proot.shortcuts.sync.apply",{confirmed:true,plan_id:plan.plan_id})',
                         'async function rollbackProotShortcutSync()',
                         'item.integrity==="valid"&&item.status==="applied"',
                         'run("proot.shortcuts.sync.rollback.preview",{rollback_id:rollbackId})',
                         'run("proot.shortcuts.sync.rollback.apply",{rollback_id:rollbackId,confirmed:true,plan_id:plan.plan_id})'):
            self.assertIn(contract, page)
        self.assertIn("timezone.status", page)
        self.assertIn("timezone.set", page)
        self.assertIn('schedule_type:scheduleType,schedule', page)
        self.assertIn("Schedule type: cron, interval, calendar, one_time", page)
        self.assertNotIn('job_id:"job-"', page)
        self.assertIn("timezone.manage", management_http_runtime.WEB_CAPABILITIES)
        self.assertIn("cron.scheduler.start", page)
        self.assertIn("cron.scheduler.stop", page)
        self.assertIn("cron.scheduler.manage", management_http_runtime.WEB_CAPABILITIES)

    def test_liveness_and_readiness_are_distinct_and_readiness_tracks_listener(self) -> None:
        server = management_http_runtime.build_server(
            port=0, bootstrap_secret=SECRET, env=self.env)
        host = f"127.0.0.1:{server.port}"
        headers = {"Host": host, "Origin": f"http://{host}"}
        before_status, _, before_body = server.adapter.handle(
            method="GET", path="/ready", headers=headers, body=b"")
        self.assertEqual(before_status, 503)
        self.assertFalse(json.loads(before_body)["ready"])
        self.assertFalse(server.is_ready())

        server.start()
        self.assertTrue(server.is_ready())
        connection = http.client.HTTPConnection(*server.address, timeout=3)
        try:
            connection.request("GET", "/health", headers=headers)
            live = connection.getresponse()
            self.assertEqual(live.status, 200)
            self.assertEqual(json.loads(live.read())["status"], "alive")
            connection.close()

            connection = http.client.HTTPConnection(*server.address, timeout=3)
            connection.request("GET", "/ready", headers=headers)
            ready = connection.getresponse()
            ready_body = json.loads(ready.read())
            self.assertEqual(ready.status, 200)
            self.assertTrue(ready_body["ready"])
            self.assertEqual(ready_body["status"], "ready")
            connection.close()

            connection = http.client.HTTPConnection(*server.address, timeout=3)
            connection.request("GET", "/ready", headers={
                "Host": host,
                "Origin": "http://untrusted.invalid",
            })
            rejected = connection.getresponse()
            self.assertEqual(rejected.status, 403)
            connection.close()
        finally:
            connection.close()
            self.assertTrue(server.close(grace_seconds=3))
        self.assertFalse(server.is_ready())
        closed_status, _, closed_body = server.adapter.handle(
            method="GET", path="/ready", headers=headers, body=b"")
        self.assertEqual(closed_status, 503)
        self.assertFalse(json.loads(closed_body)["ready"])

    def test_web_root_serves_the_real_category_console_with_same_origin_policy(self) -> None:
        env = dict(self.env, TERNUXX_WEB_MODE="1")
        Path(env["TERNUXX_STATE_DIR"]).mkdir(parents=True, mode=0o700)
        Path(env["TERNUXX_STATE_DIR"]).chmod(0o700)
        server = management_http_runtime.build_server(port=0, bootstrap_secret=SECRET, env=env)
        server.start()
        connection = http.client.HTTPConnection(*server.address, timeout=3)
        host = f"127.0.0.1:{server.port}"
        try:
            connection.request("GET", "/", headers={"Host": host, "Origin": "http://" + host})
            response = connection.getresponse()
            page = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "text/html; charset=utf-8")
            self.assertIn('id="categories"', page)
            self.assertIn('id="resource-list"', page)
            self.assertIn('id="resource-detail"', page)
            connection.close()
            connection = http.client.HTTPConnection(*server.address, timeout=3)
            connection.request("GET", "/", headers={"Host": host, "Origin": "http://untrusted.invalid"})
            rejected = connection.getresponse()
            self.assertEqual(rejected.status, 403)
        finally:
            connection.close()
            self.assertTrue(server.close(grace_seconds=3))

    def test_noninteractive_main_refuses_before_generating_or_binding(self) -> None:
        err = io.StringIO()
        with patch.object(management_http_runtime.sys, "stderr", err), \
                patch.object(management_http_runtime.management_sessions,
                             "new_bootstrap_secret") as secret_factory:
            result = management_http_runtime.main(["--port", "8765"])
        self.assertEqual(result, 2)
        self.assertIn("TTY is required", err.getvalue())
        secret_factory.assert_not_called()

    def test_cli_port_is_unprivileged(self) -> None:
        err = io.StringIO()
        with patch.object(management_http_runtime.sys, "stderr", err):
            result = management_http_runtime.main(["--port", "80"])
        self.assertEqual(result, 2)
        self.assertIn("1024 to 65535", err.getvalue())


if __name__ == "__main__":
    unittest.main()
