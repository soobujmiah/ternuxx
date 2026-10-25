"""In-process contract tests for authenticated management HTTP request routing."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import management_http_adapter  # noqa: E402
import management_service  # noqa: E402
import management_request_store  # noqa: E402
import management_sessions  # noqa: E402


BOOTSTRAP = "T" * 48
ORIGIN = "http://127.0.0.1:8765"


def payload_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def headers_for(body: bytes, **extra: str) -> dict[str, str]:
    return {
        "Host": "127.0.0.1:8765",
        "Origin": ORIGIN,
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(body)),
        **extra,
    }


def make_adapter(dispatcher=None, *, caps=None, allow_mutations=False, request_store=None):
    return management_http_adapter.ManagementHTTPAdapter(
        expected_origin=ORIGIN,
        bootstrap_secret=BOOTSTRAP,
        bootstrap_capabilities=caps if caps is not None else {"diagnostics.read", "ssh.managed.lifecycle"},
        env={"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr",
             "HOME": "/tmp/home", "TERNUXX_STATE_DIR": "/tmp/home/.state"},
        dispatcher=dispatcher or Mock(return_value={"ok": True, "api_version": 1,
                                                     "request_id": "request-1234", "data": {"state": "ready"}}),
        allow_mutations=allow_mutations,
        request_store=request_store,
    )


def bootstrap(adapter, capabilities):
    body = payload_bytes({"bootstrap_secret": BOOTSTRAP, "capabilities": capabilities})
    status, headers, response = adapter.handle(
        method="POST", path="/api/v1/session", headers=headers_for(body), body=body)
    decoded = json.loads(response)
    if status == 200:
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        decoded["session"]["bearer_token"] = cookie.split("=", 1)[1]
    return status, decoded


class ManagementHTTPAdapterTests(unittest.TestCase):
    def test_fresh_guest_idempotency_fingerprint_never_contains_password_material(self) -> None:
        base = {"api_version": 1, "request_id": "request-12345678",
                "operation": "proot.setup.fresh.apply",
                "args": {"user": "sobuj", "sudo_mode": "password", "plan_id": "a" * 64,
                         "confirmed": True, "password": "temporary-secret"}}
        other_password = json.loads(json.dumps(base))
        other_password["args"]["password"] = "different-secret"
        no_password = json.loads(json.dumps(base))
        no_password["args"].pop("password")
        self.assertEqual(management_http_adapter._fingerprint_request(base),
                         management_http_adapter._fingerprint_request(other_password))
        self.assertNotEqual(management_http_adapter._fingerprint_request(base),
                            management_http_adapter._fingerprint_request(no_password))
        serialized_identity = management_http_adapter._canonical_json({
            "password_supplied": True, "operation": "proot.setup.fresh.apply"})
        self.assertNotIn(b"temporary-secret", serialized_identity)

    def test_guest_password_reaches_dispatch_but_is_absent_from_durable_request_state(self) -> None:
        secret = "temporary-secret"
        dispatch = Mock(return_value={"ok": True, "api_version": 1,
                                      "request_id": "fresh-guest-apply", "data": {"status": "installed"}})
        with tempfile.TemporaryDirectory(prefix="ternuxx-guest-http-") as temp:
            home = Path(temp) / "home"; home.mkdir(mode=0o700)
            state = home / ".state"; state.mkdir(mode=0o700)
            store = management_request_store.ManagementRequestStore(home=home, state_dir=state)
            adapter = make_adapter(dispatcher=dispatch, caps={"proot.install.manage"},
                                   allow_mutations=True, request_store=store)
            _status, issued = bootstrap(adapter, ["proot.install.manage"])
            session = issued["session"]
            body = payload_bytes({"api_version": 1, "request_id": "fresh-guest-apply",
                "operation": "proot.setup.fresh.apply", "args": {"user": "sobuj",
                "sudo_mode": "password", "plan_id": "a" * 64, "confirmed": True,
                "password": secret}})
            status, _headers, response = adapter.handle(method="POST", path="/api/v1/operations",
                headers=headers_for(body, Authorization="Bearer " + session["bearer_token"],
                    **{"X-Ternuxx-CSRF": session["csrf_token"],
                       "Idempotency-Key": "fresh-guest-apply-key-01"}), body=body)
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(response)["ok"])
            self.assertEqual(dispatch.call_args.args[0]["args"]["password"], secret)
            for path in store.root.rglob("*"):
                if path.is_file():
                    self.assertNotIn(secret.encode(), path.read_bytes())

    def test_cpu_inference_requires_distinct_run_and_model_management_capabilities(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ternuxx-cpu-http-") as temp:
            home = Path(temp) / "home"; home.mkdir(mode=0o700)
            state = home / ".state"; state.mkdir(mode=0o700)
            store = management_request_store.ManagementRequestStore(home=home, state_dir=state)
            adapter = make_adapter(caps={"diagnostics.read", "ai.local.run"},
                                   allow_mutations=True, request_store=store)
            status, session = bootstrap(adapter, ["diagnostics.read", "ai.local.run"])
            self.assertEqual(status, 200)
            token = session["session"]["bearer_token"]
            csrf = session["session"]["csrf_token"]
            cookie = f"ternuxx_management_session={token}"
            body = payload_bytes({"api_version": 1, "request_id": "cpu-status-0001",
                                  "operation": "inference.cpu.status", "args": {}})
            code, _headers, response = adapter.handle(method="POST", path="/api/v1/operations",
                headers=headers_for(body, Cookie=cookie), body=body)
            self.assertEqual(code, 200); self.assertTrue(json.loads(response)["ok"])
            body = payload_bytes({"api_version": 1, "request_id": "cpu-run-request-01",
                                  "operation": "inference.cpu.run", "args": {"prompt": "hello"}})
            code, _headers, response = adapter.handle(method="POST", path="/api/v1/operations",
                headers=headers_for(body, Cookie=cookie, **{"X-Ternuxx-CSRF": csrf,
                                   "Idempotency-Key": "cpu-run-idempotency-0001"}), body=body)
            self.assertEqual(code, 200); self.assertTrue(json.loads(response)["ok"])
            preview = payload_bytes({"api_version": 1, "request_id": "cpu-model-prev-01",
                "operation": "inference.cpu.model.preview", "args": {"action": "install"}})
            code, _headers, response = adapter.handle(method="POST", path="/api/v1/operations",
                headers=headers_for(preview, Cookie=cookie), body=preview)
            self.assertEqual(code, 200); self.assertTrue(json.loads(response)["ok"])
            apply_body = payload_bytes({"api_version": 1, "request_id": "cpu-model-apply-01",
                "operation": "inference.cpu.model.apply", "args": {"action": "install",
                "plan_id": "a" * 24, "confirmed": True}})
            code, _headers, response = adapter.handle(method="POST", path="/api/v1/operations",
                headers=headers_for(apply_body, Cookie=cookie, **{"X-Ternuxx-CSRF": csrf,
                                   "Idempotency-Key": "cpu-model-apply-key-001"}), body=apply_body)
            self.assertEqual(code, 403)
            self.assertEqual(json.loads(response)["error"], "permission_denied")

    def test_health_is_minimal_and_responses_have_security_headers_without_cors(self) -> None:
        adapter = make_adapter()
        status, headers, body = adapter.handle(
            method="GET", path="/health", headers={"Host": "127.0.0.1:8765"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "alive")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_http_only_cookie_reconnect_restores_csrf_and_revocation_clears_it(self) -> None:
        dispatch = Mock(return_value={"ok": True, "api_version": 1,
                                      "request_id": "request-1234", "data": {"state": "ready"}})
        adapter = make_adapter(dispatcher=dispatch, caps={"diagnostics.read"})
        body = payload_bytes({"bootstrap_secret": BOOTSTRAP, "capabilities": ["diagnostics.read"]})
        status, response_headers, raw = adapter.handle(
            method="POST", path="/api/v1/session", headers=headers_for(body), body=body)
        issued = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertNotIn("bearer_token", issued["session"])
        cookie_header = response_headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=Strict", cookie_header)
        self.assertIn("Path=/api/v1", cookie_header)
        cookie = cookie_header.split(";", 1)[0]
        token = cookie.split("=", 1)[1]

        body = payload_bytes({})
        status, resumed_headers, resumed_raw = adapter.handle(
            method="POST", path="/api/v1/session/reconnect",
            headers=headers_for(body, Cookie=cookie), body=body)
        resumed = json.loads(resumed_raw)
        self.assertEqual(status, 200)
        self.assertNotIn("bearer_token", resumed["session"])
        self.assertEqual(resumed["session"]["session_ref"], issued["session"]["session_ref"])
        self.assertEqual(resumed["session"]["csrf_token"], issued["session"]["csrf_token"])

        body = payload_bytes({"api_version": 1, "request_id": "request-1234",
                              "operation": "ssh.inspect", "args": {}})
        status, _headers, response = adapter.handle(
            method="POST", path="/api/v1/operations",
            headers=headers_for(body, Cookie=cookie), body=body)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(response)["data"]["state"], "ready")

        body = payload_bytes({})
        status, logout_headers, response = adapter.handle(
            method="POST", path="/api/v1/session/revoke",
            headers=headers_for(body, Cookie=cookie,
                                **{"X-Ternuxx-CSRF": resumed["session"]["csrf_token"]}), body=body)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", logout_headers["Set-Cookie"])
        self.assertTrue(json.loads(response)["revoked"])
        status, cleared_headers, response = adapter.handle(
            method="POST", path="/api/v1/session/reconnect",
            headers=headers_for(body, Cookie=cookie), body=body)
        self.assertEqual(status, 401)
        self.assertIn("Max-Age=0", cleared_headers["Set-Cookie"])
        dispatch.assert_called_once()

    def test_reconnect_requires_exact_origin_and_rejects_duplicate_or_conflicting_cookies(self) -> None:
        adapter = make_adapter(caps={"diagnostics.read"})
        status, issued = bootstrap(adapter, ["diagnostics.read"])
        self.assertEqual(status, 200)
        token = issued["session"]["bearer_token"]
        cookie = f"{management_http_adapter.SESSION_COOKIE_NAME}={token}"
        body = payload_bytes({})
        status, _headers, response = adapter.handle(
            method="POST", path="/api/v1/session/reconnect",
            headers=headers_for(body, Cookie=cookie, Origin="http://evil.invalid"), body=body)
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(response)["error"], "origin_rejected")

        duplicated = cookie + "; " + cookie
        status, _headers, response = adapter.handle(
            method="POST", path="/api/v1/session/reconnect",
            headers=headers_for(body, Cookie=duplicated), body=body)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(response)["error"], "session_expired")

        self.assertIsNone(management_http_adapter.ManagementHTTPAdapter._bearer({
            "authorization": "Bearer " + "x" * 48, "cookie": cookie,
        }))

    def test_bootstrap_issues_scoped_tokens_once_and_never_echoes_bootstrap(self) -> None:
        adapter = make_adapter()
        status, response = bootstrap(adapter, ["diagnostics.read"])
        self.assertEqual(status, 200)
        self.assertTrue(response["ok"])
        session = response["session"]
        self.assertEqual(session["capabilities"], ["diagnostics.read"])
        self.assertNotIn(BOOTSTRAP, json.dumps(response))
        status, again = bootstrap(adapter, ["diagnostics.read"])
        self.assertEqual(status, 401)
        self.assertEqual(again["error"], "authentication_failed")

    def test_bootstrap_rejects_wider_scopes_and_duplicate_json_fields(self) -> None:
        adapter = make_adapter(caps={"diagnostics.read"})
        status, response = bootstrap(adapter, ["ssh.managed.lifecycle"])
        self.assertEqual(status, 401)
        self.assertEqual(response["error"], "authentication_failed")
        body = b'{"bootstrap_secret":"' + BOOTSTRAP.encode() + b'","bootstrap_secret":"x","capabilities":[]}'
        status, _headers, raw = adapter.handle(
            method="POST", path="/api/v1/session", headers=headers_for(body), body=body)
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw)["error"], "invalid_json")

    def test_authenticated_read_operation_dispatches_shared_service(self) -> None:
        dispatch = Mock(return_value={"ok": True, "api_version": 1,
                                      "request_id": "request-1234", "data": {"state": "ready"}})
        adapter = make_adapter(dispatcher=dispatch)
        _status, issued = bootstrap(adapter, ["diagnostics.read"])
        session = issued["session"]
        payload = {"api_version": 1, "request_id": "request-1234",
                   "operation": "ssh.inspect", "args": {}}
        body = payload_bytes(payload)
        headers = headers_for(body, Authorization=f"Bearer {session['bearer_token']}")
        status, _response_headers, raw = adapter.handle(
            method="POST", path="/api/v1/operations", headers=headers, body=body)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["data"]["state"], "ready")
        dispatch.assert_called_once_with(payload, caller="local_cli", env=adapter._env)

    def test_scope_denial_and_csrf_rejection_happen_before_dispatch(self) -> None:
        dispatch = Mock()
        adapter = make_adapter(dispatcher=dispatch, caps={"diagnostics.read"})
        _status, issued = bootstrap(adapter, ["diagnostics.read"])
        session = issued["session"]
        payload = {"api_version": 1, "request_id": "request-1234",
                   "operation": "ssh.service.stop", "args": {"confirmed": True}}
        body = payload_bytes(payload)
        headers = headers_for(body, Authorization=f"Bearer {session['bearer_token']}",
                              **{"X-Ternuxx-CSRF": session["csrf_token"],
                                 "Idempotency-Key": "mutation-key-0001"})
        status, _h, response = adapter.handle(method="POST", path="/api/v1/operations",
                                              headers=headers, body=body)
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(response)["error"], "permission_denied")
        dispatch.assert_not_called()

        adapter = make_adapter(dispatcher=dispatch)
        _status, issued = bootstrap(adapter, ["ssh.managed.lifecycle"])
        session = issued["session"]
        headers = headers_for(body, Authorization=f"Bearer {session['bearer_token']}",
                              **{"Idempotency-Key": "mutation-key-0001"})
        status, _h, response = adapter.handle(method="POST", path="/api/v1/operations",
                                              headers=headers, body=body)
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(response)["error"], "csrf_rejected")
        dispatch.assert_not_called()

    def test_mutation_transport_defaults_disabled(self) -> None:
        dispatch = Mock()
        adapter = make_adapter(dispatcher=dispatch, allow_mutations=True)
        _status, issued = bootstrap(adapter, ["ssh.managed.lifecycle"])
        session = issued["session"]
        payload = {"api_version": 1, "request_id": "request-1234",
                   "operation": "ssh.service.stop", "args": {"confirmed": True}}
        body = payload_bytes(payload)
        headers = headers_for(body, Authorization=f"Bearer {session['bearer_token']}",
                              **{"X-Ternuxx-CSRF": session["csrf_token"],
                                 "Idempotency-Key": "mutation-key-0001"})
        status, _h, response = adapter.handle(method="POST", path="/api/v1/operations",
                                              headers=headers, body=body)
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(response)["error"], "mutation_transport_disabled")
        dispatch.assert_not_called()

    def test_mutation_idempotency_replays_and_rejects_key_reuse(self) -> None:
        dispatch = Mock(return_value={"ok": True, "api_version": 1,
                                      "request_id": "request-1234", "data": {"started": True}})
        with tempfile.TemporaryDirectory(prefix="ternuxx-http-store-") as temp:
            home = Path(temp) / "home"
            home.mkdir(mode=0o700)
            state_dir = home / ".state"
            state_dir.mkdir(mode=0o700)
            store = management_request_store.ManagementRequestStore(home=home, state_dir=state_dir)
            adapter = make_adapter(dispatcher=dispatch, allow_mutations=True, request_store=store)
            self._assert_mutation_idempotency(adapter, dispatch)

    def _assert_mutation_idempotency(self, adapter, dispatch):
        _status, issued = bootstrap(adapter, ["ssh.managed.lifecycle"])
        session = issued["session"]
        payload = {"api_version": 1, "request_id": "request-1234",
                   "operation": "ssh.service.start", "args": {"confirmed": True}}
        body = payload_bytes(payload)
        headers = headers_for(body, Authorization=f"Bearer {session['bearer_token']}",
                              **{"X-Ternuxx-CSRF": session["csrf_token"],
                                 "Idempotency-Key": "mutation-key-0001"})
        first = adapter.handle(method="POST", path="/api/v1/operations", headers=headers, body=body)
        replay = adapter.handle(method="POST", path="/api/v1/operations", headers=headers, body=body)
        self.assertEqual(first[0], 200)
        self.assertEqual(replay[0], 409)
        self.assertEqual(json.loads(replay[2])["error"], "request_already_completed")
        dispatch.assert_called_once()

        changed = {**payload, "args": {"confirmed": False}}
        changed_body = payload_bytes(changed)
        changed_headers = headers_for(changed_body, Authorization=f"Bearer {session['bearer_token']}",
                                      **{"X-Ternuxx-CSRF": session["csrf_token"],
                                         "Idempotency-Key": "mutation-key-0001"})
        status, _h, response = adapter.handle(method="POST", path="/api/v1/operations",
                                              headers=changed_headers, body=changed_body)
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(response)["error"], "idempotency_conflict")
        dispatch.assert_called_once()

    def test_revoke_requires_token_and_csrf_and_invalidates_session(self) -> None:
        adapter = make_adapter()
        _status, issued = bootstrap(adapter, ["diagnostics.read"])
        session = issued["session"]
        body = b"{}"
        headers = headers_for(body, Authorization=f"Bearer {session['bearer_token']}")
        status, _h, _response = adapter.handle(method="POST", path="/api/v1/session/revoke",
                                              headers=headers, body=body)
        self.assertEqual(status, 401)
        headers["X-Ternuxx-CSRF"] = session["csrf_token"]
        status, _h, response = adapter.handle(method="POST", path="/api/v1/session/revoke",
                                              headers=headers, body=body)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(response)["revoked"])

    def test_bad_origin_length_transfer_encoding_and_route_rejected(self) -> None:
        adapter = make_adapter()
        body = b"{}"
        invalid = [
            (headers_for(body, **{"Origin": "http://evil.example"}), 403),
            ({**headers_for(body), "Content-Length": "99"}, 400),
            ({**headers_for(body), "Transfer-Encoding": "chunked"}, 400),
        ]
        for headers, expected in invalid:
            with self.subTest(headers=headers):
                status, _h, _raw = adapter.handle(method="POST", path="/api/v1/session",
                                                 headers=headers, body=body)
                self.assertEqual(status, expected)
        status, _h, response = adapter.handle(
            method="POST", path="/api/v1/operations?x=1", headers=headers_for(body), body=body)
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(response)["error"], "route_not_found")


    def test_unknown_legacy_route_is_not_in_the_api(self):
        adapter = make_adapter()
        status, _headers, raw = adapter.handle(method="POST", path="/api/v1/terminal",
                                               headers=headers_for(b"{}"), body=b"{}")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(raw)["error"], "route_not_found")



if __name__ == "__main__":
    unittest.main()
