"""Authenticated HTTP request adapter; deliberately does not bind a socket.

The foreground server binds to 127.0.0.1 and enforces worker, request, and time
bounds before passing each request here. After session authentication, this
adapter dispatches typed operations through the shared application service and
does not expose generic shell or ADB forwarding. The default management API keeps mutation dispatch disabled. Web mode may enable
a fixed, explicitly scoped set of typed operations.
"""
from __future__ import annotations

from collections.abc import Mapping, Iterable
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from typing import Callable

import management_request_policy
import management_service
import management_sessions


REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{16,96}$")
_MISSING = object()
SESSION_COOKIE_NAME = "ternuxx_management_session"
SESSION_COOKIE_PATH = "/api/v1"

def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> object:
    raise ValueError("invalid JSON constant")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")

def _fingerprint_request(payload: dict[str, object]) -> str:
    """Hash an idempotency identity without persisting any guest password material."""
    identity: object = payload
    if payload.get("operation") == "proot.setup.fresh.apply":
        identity = dict(payload)
        raw_args = payload.get("args")
        if isinstance(raw_args, dict):
            args = dict(raw_args)
            had_password = "password" in args
            args.pop("password", None)
            args["password_supplied"] = had_password
            identity["args"] = args
    return hashlib.sha256(_canonical_json(identity)).hexdigest()



class ManagementHTTPAdapter:
    """Translate guarded, authenticated local HTTP requests into typed calls."""

    def __init__(
        self,
        *,
        expected_origin: str,
        bootstrap_secret: str,
        bootstrap_capabilities: Iterable[str],
        env: dict[str, str] | None = None,
        dispatcher: Callable[..., dict[str, object]] = management_service.dispatch,
        clock: Callable[[], float] = time.monotonic,
        allow_mutations: bool = False,
        request_store: object | None = None,
        readiness_probe: Callable[[], bool] | None = None,
    ) -> None:
        self.policy = management_request_policy.LoopbackRequestPolicy(expected_origin, clock=clock)
        self.sessions = management_sessions.ManagementSessionAuthority(
            bootstrap_secret, bootstrap_capabilities, clock=clock)
        self._env = env
        self._dispatcher = dispatcher
        self._request_store = request_store
        self._allow_mutations = (allow_mutations is True
                                 and getattr(request_store, "durable", False) is True)
        self._readiness_probe = readiness_probe

    def set_readiness_probe(self, probe: Callable[[], bool]) -> None:
        """Attach the owning HTTP listener's lifecycle readiness check."""
        if not callable(probe):
            raise ValueError("readiness probe must be callable")
        self._readiness_probe = probe

    def handle(
        self,
        *,
        method: str,
        path: str,
        headers: Mapping[str, object],
        body: bytes = b"",
    ) -> tuple[int, dict[str, str], bytes]:
        """Return (status, headers, JSON bytes); never emits request secrets."""
        if not isinstance(body, bytes):
            return self._response(400, {"ok": False, "error": "invalid_body"})
        normalized_headers: dict[str, object] = {}
        for name, value in headers.items():
            key = str(name).lower()
            if key in normalized_headers:
                return self._response(400, {"ok": False, "error": "duplicate_header"})
            normalized_headers[key] = value
        content_length = normalized_headers.get("content-length", _MISSING)
        if method == "GET" and content_length is _MISSING and not body:
            parsed_length: object = 0
        elif content_length is _MISSING or not isinstance(content_length, str) or not content_length.isdecimal():
            parsed_length: object = _MISSING
        else:
            parsed_length = int(content_length)
        if "transfer-encoding" in normalized_headers:
            return self._response(400, {"ok": False, "error": "transfer_encoding_rejected"})
        if parsed_length is _MISSING or parsed_length != len(body):
            return self._response(400, {"ok": False, "error": "content_length_mismatch"})

        decision = self.policy.check(
            host=normalized_headers.get("host"), method=method,
            origin=normalized_headers.get("origin"),
            content_type=normalized_headers.get("content-type"),
            content_length=parsed_length,
        )
        if not decision.allowed:
            status = 429 if decision.reason == "rate_limited" else 403
            return self._response(status, {"ok": False, "error": decision.reason})

        if method == "GET" and path == "/health":
            return self._response(200, {"ok": True, "api_version": 1, "status": "alive"})
        if method == "GET" and path == "/ready":
            ready = False
            if self._readiness_probe is not None:
                try:
                    ready = self._readiness_probe() is True
                except Exception:
                    ready = False
            return self._response(200 if ready else 503, {
                "ok": ready,
                "api_version": 1,
                "ready": ready,
                "status": "ready" if ready else "not_ready",
            })
        if not isinstance(path, str) or method != "POST" or "?" in path or "#" in path:
            return self._response(404, {"ok": False, "error": "route_not_found"})
        try:
            payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                                 parse_constant=_reject_json_constant)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return self._response(400, {"ok": False, "error": "invalid_json"})
        if not isinstance(payload, dict):
            return self._response(400, {"ok": False, "error": "invalid_request"})

        if path == "/api/v1/session":
            return self._bootstrap(payload)
        if path == "/api/v1/session/reconnect":
            return self._resume(normalized_headers, payload)
        if path == "/api/v1/session/revoke":
            return self._revoke(normalized_headers, payload)
        if path == "/api/v1/operations":
            return self._operation(normalized_headers, payload)
        return self._response(404, {"ok": False, "error": "route_not_found"})

    def _bootstrap(self, payload: dict[str, object]) -> tuple[int, dict[str, str], bytes]:
        if set(payload) != {"bootstrap_secret", "capabilities"}:
            return self._response(400, {"ok": False, "error": "invalid_request"})
        secret = payload.get("bootstrap_secret")
        requested = payload.get("capabilities")
        if not isinstance(requested, list) or any(not isinstance(scope, str) for scope in requested):
            return self._response(400, {"ok": False, "error": "invalid_capabilities"})
        try:
            issued = self.sessions.exchange_bootstrap(secret, requested)
        except PermissionError:
            return self._response(401, {"ok": False, "error": "authentication_failed"})
        except ValueError:
            return self._response(400, {"ok": False, "error": "invalid_capabilities"})
        response = self._response(200, {
            "ok": True,
            "session": {
                "session_ref": issued.session_ref,
                "csrf_token": issued.csrf_token,
                "capabilities": list(issued.capabilities),
                "idle_ttl_seconds": issued.idle_ttl_seconds,
                "absolute_ttl_seconds": issued.absolute_ttl_seconds,
            },
        })
        response[1]["Set-Cookie"] = self._session_cookie(issued.bearer_token)
        return response

    def _resume(self, headers: dict[str, object], payload: dict[str, object]) -> tuple[int, dict[str, str], bytes]:
        if payload:
            return self._response(400, {"ok": False, "error": "invalid_request"})
        if headers.get("origin") != self.policy.expected_origin:
            return self._response(403, {"ok": False, "error": "origin_rejected"})
        bearer = self._cookie_bearer(headers)
        if not bearer:
            response = self._response(401, {"ok": False, "error": "session_expired"})
            response[1]["Set-Cookie"] = self._clear_session_cookie()
            return response
        try:
            issued = self.sessions.resume_session(bearer)
        except PermissionError:
            response = self._response(401, {"ok": False, "error": "session_expired"})
            response[1]["Set-Cookie"] = self._clear_session_cookie()
            return response
        response = self._response(200, {
            "ok": True,
            "session": {
                "session_ref": issued.session_ref,
                "csrf_token": issued.csrf_token,
                "capabilities": list(issued.capabilities),
                "idle_ttl_seconds": issued.idle_ttl_seconds,
                "absolute_ttl_seconds": issued.absolute_ttl_seconds,
            },
        })
        response[1]["Set-Cookie"] = self._session_cookie(issued.bearer_token)
        return response

    def _revoke(self, headers: dict[str, object], payload: dict[str, object]) -> tuple[int, dict[str, str], bytes]:
        if payload:
            return self._response(400, {"ok": False, "error": "invalid_request"})
        bearer = self._bearer(headers)
        csrf = headers.get("x-ternuxx-csrf")
        if not bearer or not isinstance(csrf, str):
            return self._response(401, {"ok": False, "error": "authentication_failed"})
        auth = self.sessions.authorize_request(bearer, "management.catalog")
        if not auth.allowed or not self.sessions.revoke_session(bearer, csrf):
            return self._response(401, {"ok": False, "error": "authentication_failed"})
        response = self._response(200, {"ok": True, "revoked": True})
        response[1]["Set-Cookie"] = self._clear_session_cookie()
        return response

    def _operation(self, headers: dict[str, object], payload: dict[str, object]) -> tuple[int, dict[str, str], bytes]:
        operation = payload.get("operation")
        bearer = self._bearer(headers)
        csrf = headers.get("x-ternuxx-csrf")
        if not bearer:
            return self._response(401, {"ok": False, "error": "authentication_required"})
        auth = self.sessions.authorize_request(bearer, operation, csrf_token=csrf)
        if not auth.allowed:
            code = {"unauthenticated": "authentication_required", "session_expired": "session_expired",
                    "scope_denied": "permission_denied", "csrf_rejected": "csrf_rejected"}.get(
                        auth.reason, "permission_denied")
            return self._response(401 if auth.reason in {"unauthenticated", "session_expired"} else 403,
                                  {"ok": False, "error": code})

        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not REQUEST_ID_RE.fullmatch(request_id):
            return self._response(400, {"ok": False, "error": "invalid_request_id"})
        is_mutation = operation in management_sessions.MUTATING_OPERATIONS
        idempotency_key = headers.get("idempotency-key")
        fingerprint = ""
        if is_mutation:
            if not isinstance(idempotency_key, str) or not IDEMPOTENCY_KEY_RE.fullmatch(idempotency_key):
                return self._response(400, {"ok": False, "error": "idempotency_key_required"})
            fingerprint = _fingerprint_request(payload)
            if not self._allow_mutations:
                return self._response(403, {"ok": False, "error": "mutation_transport_disabled"})
            try:
                cache_status = self._request_store.begin(
                    session_ref=auth.session_ref or "", idempotency_key=idempotency_key,
                    fingerprint=fingerprint, request_id=request_id, operation=operation)
            except (OSError, RuntimeError, ValueError):
                return self._response(503, {"ok": False, "error": "durable_request_store_unavailable"})
            if cache_status == "conflict":
                return self._response(409, {"ok": False, "error": "idempotency_conflict"})
            if cache_status == "completed":
                return self._response(409, {"ok": False, "error": "request_already_completed"})
            if cache_status == "in_progress":
                return self._response(409, {"ok": False, "error": "operation_outcome_unknown"})
            if cache_status != "new":
                return self._response(503, {"ok": False, "error": "durable_request_store_unavailable"})

        started_at = time.monotonic()
        try:
            result = self._dispatcher(payload, caller="local_cli", env=self._env)
            if not isinstance(result, dict):
                raise TypeError("application service returned a non-object")
            # Strip free-form service messages from remote-capable transport errors.
            if result.get("ok") is False and isinstance(result.get("error"), dict):
                error = result["error"]
                safe = {"api_version": result.get("api_version", 1),
                        "request_id": result.get("request_id", request_id), "ok": False,
                        "error": {"code": error.get("code", "operation_failed")}}
                result = safe
            response = self._response(200 if result.get("ok") else 400, result)
        except Exception:
            response = self._response(500, {"ok": False, "error": "operation_failed",
                                            "request_id": request_id})
        if is_mutation:
            outcome = "succeeded" if response[0] < 400 else "failed"
            if response[0] >= 500:
                outcome = "unknown"
            try:
                self._request_store.complete(
                    session_ref=auth.session_ref or "", idempotency_key=str(idempotency_key),
                    fingerprint=fingerprint, http_status=response[0], outcome=outcome,
                    duration_ms=max(0, int((time.monotonic() - started_at) * 1000)))
            except (OSError, RuntimeError, ValueError):
                return self._response(503, {"ok": False, "error": "operation_outcome_requires_review",
                                            "request_id": request_id})
        return response

    @classmethod
    def _bearer(cls, headers: dict[str, object]) -> str | None:
        value = headers.get("authorization")
        authorization = None
        if value is not None:
            if not isinstance(value, str) or len(value) > management_sessions.MAX_TOKEN_LENGTH + 7:
                return None
            parts = value.split(" ")
            if len(parts) != 2 or parts[0] != "Bearer" or not parts[1]:
                return None
            authorization = parts[1]
        cookie = cls._cookie_bearer(headers)
        if authorization is not None and cookie is not None:
            if not hmac.compare_digest(authorization, cookie):
                return None
        return authorization or cookie

    @staticmethod
    def _cookie_bearer(headers: Mapping[str, object]) -> str | None:
        value = headers.get("cookie")
        if not isinstance(value, str) or len(value) > 4096:
            return None
        matches = []
        for field in value.split(";"):
            name, separator, token = field.strip().partition("=")
            if separator and name == SESSION_COOKIE_NAME:
                matches.append(token)
        if len(matches) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{40,256}", matches[0]):
            return None
        return matches[0]

    @staticmethod
    def _session_cookie(token: str) -> str:
        # This server binds to loopback HTTP only; SameSite and exact Origin checks
        # provide browser CSRF boundaries while HttpOnly hides the session token.
        return f"{SESSION_COOKIE_NAME}={token}; Path={SESSION_COOKIE_PATH}; HttpOnly; SameSite=Strict"

    @staticmethod
    def _clear_session_cookie() -> str:
        return f"{SESSION_COOKIE_NAME}=; Path={SESSION_COOKIE_PATH}; HttpOnly; SameSite=Strict; Max-Age=0"

    @staticmethod
    def _response(status: int, payload: dict[str, object]) -> tuple[int, dict[str, str], bytes]:
        try:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                              allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            status = 500
            body = b'{"ok":false,"error":"response_encoding_failed"}'
        return ManagementHTTPAdapter._base_headers(body, status=status)

    @staticmethod
    def _base_headers(body: bytes, *, status: int = 200) -> tuple[int, dict[str, str], bytes]:
        return status, {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
            "Connection": "close",
        }, body
