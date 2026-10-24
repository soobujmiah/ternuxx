"""Private local transport primitives for the optional interactive terminal broker.

This module deliberately provides no shell, argv, environment, or filesystem
operation. A product adapter must authenticate its user/session and provide a
typed dispatcher before requests can affect a terminal session.
"""
from __future__ import annotations

import json
import os
import base64
import binascii
import errno
import fcntl
import hashlib
import json
from pathlib import Path
import re
import secrets
import select
import signal
import socket
import stat
import struct
import threading
import time
import termios
from collections import deque
from dataclasses import dataclass
from collections.abc import Callable


API_VERSION = 1
MAX_FRAME = 64 * 1024
MAX_INPUT = 4096
MAX_OUTPUT_CHUNK = 24 * 1024
_FRAME_LENGTH = struct.Struct("!I")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_SESSION_ID = re.compile(r"^proot-[0-9a-f]{32}$")
_ATTACHMENT_ID = re.compile(r"^attach-[0-9a-f]{32}$")
_ALLOWED_OPERATIONS = {
    "broker.status", "terminal.start.preview", "terminal.start",
    "terminal.attach", "terminal.detach", "terminal.input",
    "terminal.resize", "terminal.output", "terminal.close.preview",
    "terminal.close",
}


class BrokerError(ValueError):
    """A broker endpoint or protocol request is invalid or unsafe."""


def encode_frame(value: object) -> bytes:
    try:
        body = json.dumps(value, ensure_ascii=True, separators=(",", ":"),
                          allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise BrokerError("broker message is not JSON encodable") from exc
    if not body or len(body) > MAX_FRAME:
        raise BrokerError("broker message exceeds the frame limit")
    return _FRAME_LENGTH.pack(len(body)) + body


def _read_exact(stream: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        chunk = stream.recv(count - len(chunks))
        if not chunk:
            raise BrokerError("broker connection ended mid-frame")
        chunks.extend(chunk)
    return bytes(chunks)


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BrokerError("broker frame contains a duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str):
    raise BrokerError("broker frame contains a non-JSON numeric constant")


def read_frame(stream: socket.socket) -> object:
    size = _FRAME_LENGTH.unpack(_read_exact(stream, _FRAME_LENGTH.size))[0]
    if not 1 <= size <= MAX_FRAME:
        raise BrokerError("broker frame length is invalid")
    body = _read_exact(stream, size)
    try:
        return json.loads(body.decode("ascii"), object_pairs_hook=_strict_object,
                          parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise BrokerError("broker frame is not valid JSON") from exc


def validate_request(request: object) -> dict[str, object]:
    """Validate the common envelope; operation-specific args stay typed by the dispatcher."""
    required = {"api_version", "request_id", "operation", "session_id",
                "generation", "attachment_id", "args"}
    if not isinstance(request, dict) or set(request) != required:
        raise BrokerError("broker request fields are invalid")
    if type(request["api_version"]) is not int or request["api_version"] != API_VERSION:
        raise BrokerError("broker API version is unsupported")
    request_id = request["request_id"]
    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        raise BrokerError("broker request ID is invalid")
    if not isinstance(request["operation"], str) or request["operation"] not in _ALLOWED_OPERATIONS:
        raise BrokerError("broker operation is not supported")
    if not (request["session_id"] is None or
            isinstance(request["session_id"], str) and _SESSION_ID.fullmatch(request["session_id"])):
        raise BrokerError("broker session ID is invalid")
    if not (request["generation"] is None or
            type(request["generation"]) is int and request["generation"] > 0):
        raise BrokerError("broker generation is invalid")
    if not (request["attachment_id"] is None or
            isinstance(request["attachment_id"], str) and _ATTACHMENT_ID.fullmatch(request["attachment_id"])):
        raise BrokerError("broker attachment ID is invalid")
    if not isinstance(request["args"], dict):
        raise BrokerError("broker arguments must be an object")
    return request


def _private_state(state_dir: str | os.PathLike[str], *, create: bool) -> Path:
    state = Path(state_dir).absolute()
    if create:
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        info = state.lstat()
    except OSError as exc:
        raise BrokerError("Ternuxx state directory is unavailable") from exc
    if (state.is_symlink() or state.resolve(strict=True) != state
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise BrokerError("Ternuxx state directory identity or permissions are unsafe")
    return state


def broker_socket_path(state_dir: str | os.PathLike[str], *, create: bool = False) -> Path:
    state = _private_state(state_dir, create=create)
    path = state / "terminal-broker.sock"
    # Linux sockaddr_un.sun_path is 108 bytes including NUL.
    if len(os.fsencode(path)) >= 108:
        raise BrokerError("Ternuxx state path is too long for a local socket")
    return path


def _acquire_broker_socket_lock(state_dir: str | os.PathLike[str]) -> int:
    state = _private_state(state_dir, create=False)
    lock_path = state / "terminal-broker-recovery.lock"
    try:
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError as exc:
        raise BrokerError("broker socket coordination lock is unavailable") from exc
    info = os.fstat(lock_fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        os.close(lock_fd)
        raise BrokerError("broker socket coordination lock is unsafe")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(lock_fd)
        raise BrokerError("another broker socket lifecycle operation is in progress") from exc
    return lock_fd


def preview_stale_socket_recovery(state_dir: str | os.PathLike[str]) -> dict[str, object]:
    """Describe one exact refused Unix socket without changing it."""
    path = broker_socket_path(state_dir)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"status": "absent", "path": str(path), "changed": False}
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        raise BrokerError("broker socket identity or permissions are unsafe")
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(0.5)
        result = probe.connect_ex(str(path))
    finally:
        probe.close()
    try:
        current = path.lstat()
    except FileNotFoundError as exc:
        raise BrokerError("broker socket changed during its liveness check") from exc
    if (current.st_dev, current.st_ino, current.st_uid, current.st_mode,
            current.st_mtime_ns, current.st_ctime_ns) != (
            info.st_dev, info.st_ino, info.st_uid, info.st_mode,
            info.st_mtime_ns, info.st_ctime_ns):
        raise BrokerError("broker socket changed during its liveness check")
    if result == 0:
        raise BrokerError("broker socket has a live listener; refusing recovery")
    if result != errno.ECONNREFUSED:
        raise BrokerError(f"broker socket liveness is unknown (connect result {result})")
    snapshot = {
        "operation": "terminal-broker-stale-socket-recovery",
        "path": str(path),
        "device": info.st_dev,
        "inode": info.st_ino,
        "uid": info.st_uid,
        "mode": stat.S_IMODE(info.st_mode),
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
        "probe": "connection-refused",
    }
    plan_id = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"status": "stale", **snapshot, "changed": True, "plan_id": plan_id}


def recover_stale_socket(state_dir: str | os.PathLike[str], *,
                         confirmed: bool, plan_id: str | None) -> dict[str, object]:
    """Remove only the unchanged private socket whose exact probe was refused."""
    if confirmed is not True or not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
        raise BrokerError("explicit confirmation and a fresh socket recovery plan ID are required")
    state = _private_state(state_dir, create=False)
    lock_fd = _acquire_broker_socket_lock(state)
    try:
        preview = preview_stale_socket_recovery(state)
        if preview.get("status") != "stale" or preview.get("plan_id") != plan_id:
            raise BrokerError("fresh exact socket recovery preview and plan ID are required")
        path = broker_socket_path(state)
        directory_fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            current = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
            if (not stat.S_ISSOCK(current.st_mode)
                    or current.st_uid != os.getuid()
                    or current.st_dev != preview["device"]
                    or current.st_ino != preview["inode"]
                    or stat.S_IMODE(current.st_mode) != 0o600):
                raise BrokerError("broker socket changed after preview")
            confirmation = preview_stale_socket_recovery(state)
            if confirmation.get("plan_id") != plan_id:
                raise BrokerError("broker socket liveness or identity changed after preview")
            os.unlink(path.name, dir_fd=directory_fd)
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return {"status": "recovered", "path": str(path), "plan_id": plan_id,
                "removed_device": preview["device"], "removed_inode": preview["inode"]}
    finally:
        os.close(lock_fd)


class UnixBrokerServer:
    """One-request-per-connection Unix socket server with same-UID peer checks."""

    def __init__(self, state_dir: str | os.PathLike[str],
                 dispatcher: Callable[[dict[str, object], int], object], *,
                 expected_uid: int | None = None):
        self.path = broker_socket_path(state_dir, create=True)
        self.dispatcher = dispatcher
        self.expected_uid = os.getuid() if expected_uid is None else expected_uid
        if type(self.expected_uid) is not int or self.expected_uid < 0:
            raise BrokerError("expected broker UID is invalid")
        self.listener: socket.socket | None = None
        self._socket_identity: tuple[int, int] | None = None

    def open(self, *, backlog: int = 8) -> None:
        if type(backlog) is not int or not 1 <= backlog <= 32:
            raise BrokerError("broker backlog is outside the allowed range")
        lock_fd = _acquire_broker_socket_lock(self.path.parent)
        try:
            try:
                info = self.path.lstat()
            except FileNotFoundError:
                info = None
            if info is not None:
                # Recovery remains explicit; startup never adopts or unlinks
                # an existing socket, even after liveness checks.
                raise BrokerError("broker socket path already exists")
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            bound = False
            try:
                listener.bind(str(self.path))
                bound = True
                os.chmod(self.path, 0o600)
                info = self.path.lstat()
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                    raise BrokerError("broker socket identity is unsafe")
                self._socket_identity = (info.st_dev, info.st_ino)
                listener.listen(backlog)
                listener.settimeout(0.5)
            except BaseException:
                listener.close()
                if bound:
                    self._unlink_owned_socket()
                raise
            self.listener = listener
        finally:
            os.close(lock_fd)

    def serve_one(self) -> bool:
        if self.listener is None:
            raise BrokerError("broker listener is not open")
        try:
            connection, _address = self.listener.accept()
        except TimeoutError:
            return False
        with connection:
            connection.settimeout(5.0)
            peer_uid = self._peer_uid(connection)
            if peer_uid != self.expected_uid:
                return True
            try:
                request = validate_request(read_frame(connection))
                response = self.dispatcher(request, peer_uid)
            except BrokerError:
                response = {"ok": False, "error": {"code": "invalid_or_unauthorized_request"}}
            except Exception:
                response = {"ok": False, "error": {"code": "broker_operation_failed"}}
            connection.sendall(encode_frame(response))
        return True

    @staticmethod
    def _peer_uid(connection: socket.socket) -> int:
        if not hasattr(socket, "SO_PEERCRED"):
            raise BrokerError("kernel peer credential checks are unavailable")
        credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", credentials)
        return uid

    def close(self) -> None:
        if self.listener is not None:
            self.listener.close()
            self.listener = None
        self._unlink_owned_socket()

    def _unlink_owned_socket(self) -> None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return
        if (self._socket_identity is not None and stat.S_ISSOCK(info.st_mode)
                and info.st_uid == os.getuid()
                and (info.st_dev, info.st_ino) == self._socket_identity):
            self.path.unlink()
        self._socket_identity = None


class UnixBrokerClient:
    """Short-lived typed request client for local CLI/TUI and UI adapters."""

    def __init__(self, state_dir: str | os.PathLike[str], *, timeout: float = 5.0):
        if (type(timeout) not in {int, float} or not 0.1 <= timeout <= 30):
            raise BrokerError("broker client timeout is invalid")
        self.path = broker_socket_path(state_dir)
        self.timeout = float(timeout)

    def request(self, operation: str, *, session_id: str | None = None,
                generation: int | None = None, attachment_id: str | None = None,
                args: dict[str, object] | None = None) -> dict[str, object]:
        import uuid
        envelope = validate_request({
            "api_version": API_VERSION,
            "request_id": uuid.uuid4().hex,
            "operation": operation,
            "session_id": session_id,
            "generation": generation,
            "attachment_id": attachment_id,
            "args": {} if args is None else args,
        })
        try:
            before = self.path.lstat()
        except FileNotFoundError as exc:
            raise BrokerError("terminal broker is not running") from exc
        if (not stat.S_ISSOCK(before.st_mode) or before.st_uid != os.getuid()
                or before.st_mode & 0o077):
            raise BrokerError("terminal broker socket identity or permissions are unsafe")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(self.timeout)
            try:
                connection.connect(str(self.path))
                after = self.path.lstat()
                if (not stat.S_ISSOCK(after.st_mode) or after.st_uid != os.getuid()
                        or (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)):
                    raise BrokerError("terminal broker socket changed during connect")
                connection.sendall(encode_frame(envelope))
                response = read_frame(connection)
            except (OSError, BrokerError) as exc:
                if isinstance(exc, BrokerError):
                    raise
                raise BrokerError("terminal broker is unavailable") from exc
        if not isinstance(response, dict):
            raise BrokerError("terminal broker returned an invalid response")
        return response


@dataclass
class _Attachment:
    session_id: str
    attachment_id: str
    principal: str
    output: deque[tuple[int, bytes]]
    output_size: int = 0
    output_sequence: int = 0


class TerminalAttachmentRegistry:
    """In-memory single-writer channel leases; process ownership stays external."""

    def __init__(self, *, generation: int | None = None,
                 max_output_bytes: int = 256 * 1024):
        if type(max_output_bytes) is not int or not 4096 <= max_output_bytes <= 1024 * 1024:
            raise BrokerError("terminal output retention limit is invalid")
        self.generation = secrets.randbits(63) + 1 if generation is None else generation
        if type(self.generation) is not int or self.generation <= 0:
            raise BrokerError("broker generation is invalid")
        self.max_output_bytes = max_output_bytes
        self._attachments: dict[str, _Attachment] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _session_id(value: object) -> str:
        if not isinstance(value, str) or not _SESSION_ID.fullmatch(value):
            raise BrokerError("terminal session ID is invalid")
        return value

    @staticmethod
    def _principal(value: object) -> str:
        if not isinstance(value, str) or not 1 <= len(value) <= 256:
            raise BrokerError("terminal authorization principal is invalid")
        return value

    def attach(self, session_id: str, principal: str) -> dict[str, object]:
        session_id = self._session_id(session_id)
        principal = self._principal(principal)
        with self._lock:
            if session_id in self._attachments:
                raise BrokerError("terminal session already has a writer")
            attachment_id = "attach-" + secrets.token_hex(16)
            self._attachments[session_id] = _Attachment(
                session_id, attachment_id, principal, deque())
            return {"session_id": session_id, "generation": self.generation,
                    "attachment_id": attachment_id, "writer_attached": True}

    def _require(self, session_id: str, generation: int,
                 attachment_id: str, principal: str) -> _Attachment:
        session_id = self._session_id(session_id)
        principal = self._principal(principal)
        if type(generation) is not int or generation != self.generation:
            raise BrokerError("terminal broker generation is stale")
        if not isinstance(attachment_id, str) or not _ATTACHMENT_ID.fullmatch(attachment_id):
            raise BrokerError("terminal attachment ID is invalid")
        attachment = self._attachments.get(session_id)
        if (attachment is None or attachment.attachment_id != attachment_id
                or attachment.principal != principal):
            raise BrokerError("terminal attachment is unauthorized or stale")
        return attachment

    def validate_attachment(self, session_id: str, generation: int,
                            attachment_id: str, principal: str) -> None:
        """Require the current exact writer before previewing or closing."""
        with self._lock:
            self._require(session_id, generation, attachment_id, principal)

    def accept_input(self, session_id: str, generation: int, attachment_id: str,
                     principal: str, data: bytes) -> bytes:
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_INPUT:
            raise BrokerError("terminal input frame is outside the allowed size")
        with self._lock:
            self._require(session_id, generation, attachment_id, principal)
            return data

    def validate_resize(self, session_id: str, generation: int, attachment_id: str,
                        principal: str, columns: int, rows: int) -> tuple[int, int]:
        if (type(columns) is not int or type(rows) is not int
                or not 1 <= columns <= 500 or not 1 <= rows <= 300):
            raise BrokerError("terminal dimensions are outside the allowed range")
        with self._lock:
            self._require(session_id, generation, attachment_id, principal)
            return columns, rows

    def publish_output(self, session_id: str, generation: int, data: bytes) -> int:
        session_id = self._session_id(session_id)
        if not isinstance(data, bytes) or not data:
            raise BrokerError("terminal output chunk is invalid")
        if len(data) > self.max_output_bytes:
            data = data[-self.max_output_bytes:]
        with self._lock:
            if type(generation) is not int or generation != self.generation:
                raise BrokerError("terminal broker generation is stale")
            attachment = self._attachments.get(session_id)
            if attachment is None:
                return 0
            for offset in range(0, len(data), MAX_OUTPUT_CHUNK):
                chunk = data[offset:offset + MAX_OUTPUT_CHUNK]
                attachment.output_sequence += 1
                attachment.output.append((attachment.output_sequence, chunk))
                attachment.output_size += len(chunk)
                while attachment.output and attachment.output_size > self.max_output_bytes:
                    _sequence, old = attachment.output.popleft()
                    attachment.output_size -= len(old)
            return attachment.output_sequence

    def read_output(self, session_id: str, generation: int, attachment_id: str,
                    principal: str, after_sequence: int) -> dict[str, object]:
        if type(after_sequence) is not int or after_sequence < 0:
            raise BrokerError("terminal output cursor is invalid")
        with self._lock:
            attachment = self._require(session_id, generation, attachment_id, principal)
            first = attachment.output[0][0] if attachment.output else attachment.output_sequence + 1
            available = next(((sequence, data) for sequence, data in attachment.output
                              if sequence > after_sequence), None)
            return {
                "chunks": ([] if available is None else [
                    {"sequence": available[0], "data": available[1]}]),
                "next_sequence": (available[0] if available is not None
                                  else attachment.output_sequence),
                "truncated": after_sequence + 1 < first,
            }

    def detach(self, session_id: str, generation: int, attachment_id: str,
               principal: str) -> dict[str, object]:
        with self._lock:
            self._require(session_id, generation, attachment_id, principal)
            del self._attachments[session_id]
        return {"session_id": session_id, "writer_attached": False,
                "session_closed": False}


class TerminalBrokerDispatcher:
    """Typed terminal channel operations layered over an authenticated adapter.

    The callbacks must perform current session ownership checks and bind any
    close action to the existing exact-preview stop operation.
    """

    def __init__(self, registry: TerminalAttachmentRegistry, *,
                 authorize: Callable[[dict[str, object], int], str | None],
                 verify_session: Callable[[str], bool],
                 write_input: Callable[[str, bytes], None],
                 resize_pty: Callable[[str, int, int], None],
                 close_preview: Callable[[str], dict[str, object]],
                 close_apply: Callable[[str, str], dict[str, object]],
                 start_preview: Callable[[], dict[str, object]] | None = None,
                 start_apply: Callable[[str, str], dict[str, object]] | None = None,
                 pty_relay_status: Callable[[], str] | None = None):
        self.registry = registry
        self.authorize = authorize
        self.verify_session = verify_session
        self.write_input = write_input
        self.resize_pty = resize_pty
        self.close_preview = close_preview
        self.close_apply = close_apply
        self.start_preview = start_preview
        self.start_apply = start_apply
        self.pty_relay_status = pty_relay_status or (lambda: "not_connected")

    @staticmethod
    def _args(request: dict[str, object], expected: set[str]) -> dict[str, object]:
        args = request["args"]
        if not isinstance(args, dict) or set(args) != expected:
            raise BrokerError("terminal operation arguments are invalid")
        return args

    def __call__(self, request: dict[str, object], peer_uid: int) -> dict[str, object]:
        operation = request["operation"]
        if operation == "broker.status":
            self._args(request, set())
            return {"ok": True, "generation": self.registry.generation,
                    "pty_relay": self.pty_relay_status()}
        operation = request["operation"]
        if operation in {"terminal.start.preview", "terminal.start"}:
            principal = self.authorize(request, peer_uid)
            if not principal:
                raise BrokerError("terminal operation is unauthorized")
            if operation == "terminal.start.preview":
                self._args(request, set())
                if self.start_preview is None:
                    raise BrokerError("interactive PTY start is unavailable")
                return {"ok": True, "plan": self.start_preview()}
            args = self._args(request, {"confirmed", "plan_id"})
            if args["confirmed"] is not True or not isinstance(args["plan_id"], str):
                raise BrokerError("terminal start requires its exact preview and confirmation")
            if self.start_apply is None:
                raise BrokerError("interactive PTY start is unavailable")
            return {"ok": True, "result": self.start_apply(args["plan_id"], principal)}
        session_id = request["session_id"]
        if not isinstance(session_id, str):
            raise BrokerError("terminal operation requires a session ID")
        principal = self.authorize(request, peer_uid)
        if not principal:
            raise BrokerError("terminal operation is unauthorized")

        if operation == "terminal.attach":
            self._args(request, set())
            if not self.verify_session(session_id):
                raise BrokerError("PRoot session identity is not verified")
            lease = self.registry.attach(session_id, principal)
            return {"ok": True, **lease}

        generation = request["generation"]
        attachment_id = request["attachment_id"]
        if type(generation) is not int or not isinstance(attachment_id, str):
            raise BrokerError("terminal attachment identity is required")
        if operation == "terminal.input":
            args = self._args(request, {"data_base64"})
            encoded = args["data_base64"]
            if not isinstance(encoded, str) or len(encoded) > ((MAX_INPUT + 2) // 3) * 4:
                raise BrokerError("terminal input encoding is invalid")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise BrokerError("terminal input encoding is invalid") from exc
            data = self.registry.accept_input(session_id, generation, attachment_id,
                                              principal, data)
            self.write_input(session_id, data)
            return {"ok": True, "accepted_bytes": len(data)}
        if operation == "terminal.resize":
            args = self._args(request, {"columns", "rows"})
            columns, rows = self.registry.validate_resize(
                session_id, generation, attachment_id, principal,
                args["columns"], args["rows"])
            self.resize_pty(session_id, columns, rows)
            return {"ok": True, "columns": columns, "rows": rows}
        if operation == "terminal.output":
            args = self._args(request, {"after_sequence"})
            output = self.registry.read_output(session_id, generation, attachment_id,
                                               principal, args["after_sequence"])
            return {"ok": True, "session_id": session_id,
                    "next_sequence": output["next_sequence"],
                    "truncated": output["truncated"],
                    "session_closed": self.pty_relay_status() == "not_connected",
                    "chunks": [{"sequence": item["sequence"],
                                "data_base64": base64.b64encode(item["data"]).decode("ascii")}
                               for item in output["chunks"]]}
        if operation == "terminal.detach":
            self._args(request, set())
            return {"ok": True, **self.registry.detach(
                session_id, generation, attachment_id, principal)}
        if operation == "terminal.close.preview":
            self.registry.validate_attachment(session_id, generation, attachment_id, principal)
            self._args(request, set())
            if not self.verify_session(session_id):
                raise BrokerError("PRoot session identity is not verified")
            return {"ok": True, "plan": self.close_preview(session_id)}
        if operation == "terminal.close":
            self.registry.validate_attachment(session_id, generation, attachment_id, principal)
            args = self._args(request, {"confirmed", "plan_id"})
            if args["confirmed"] is not True or not isinstance(args["plan_id"], str):
                raise BrokerError("terminal close requires its exact preview and confirmation")
            if not self.verify_session(session_id):
                raise BrokerError("PRoot session identity is not verified")
            result = self.close_apply(session_id, args["plan_id"])
            if result.get("state") == "stopped":
                try:
                    self.registry.detach(session_id, generation, attachment_id,
                                         principal)
                except BrokerError:
                    pass
            return {"ok": True, "result": result}
        raise BrokerError("terminal operation is not supported")

@dataclass
class _PTYProcess:
    record: dict[str, object]
    child_pid: int
    master_fd: int
    eof: bool = False
    exit_code: int | None = None
    wait_status_unknown: bool = False
    exit_recorded: bool = False
    attachment_generation: int = 0
    attachment_id: str = ""
    attachment_principal: str = ""
    closed: bool = False


class TerminalPTYRuntime:
    """Single-session owner for the fixed Debian interactive PTY.

    The callbacks must use the existing exact-preview PRoot session manager.
    This class never accepts a command, argv, environment, user, or rootfs.
    """

    def __init__(self, registry: TerminalAttachmentRegistry, *,
                 preview_start: Callable[[], dict[str, object]],
                 spawn_login: Callable[[str], dict[str, object]],
                 verify_record: Callable[[dict[str, object]], bool],
                 session_members: Callable[[int], list[object]],
                 record_exit: Callable[[dict[str, object], str, int | None], None],
                 poll_interval: float = 0.1):
        if type(poll_interval) not in {int, float} or not 0.02 <= poll_interval <= 1.0:
            raise BrokerError("PTY broker polling interval is outside the allowed range")
        self.registry = registry
        self.preview_start = preview_start
        self.spawn_login = spawn_login
        self.verify_record = verify_record
        self.session_members = session_members
        self.record_exit = record_exit
        self.poll_interval = float(poll_interval)
        self._process: _PTYProcess | None = None
        self._lock = threading.RLock()
        self._closed = False
        self._thread: threading.Thread | None = None

    def start(self, plan_id: str, principal: str, *, confirmed: bool) -> dict[str, object]:
        if confirmed is not True or not isinstance(plan_id, str):
            raise BrokerError("interactive start requires an exact preview and confirmation")
        with self._lock:
            if self._closed:
                raise BrokerError("terminal broker is shutting down")
            if self._process is not None:
                raise BrokerError("broker already owns an interactive PRoot PTY")
            preview = self.preview_start()
            if not isinstance(preview, dict) or preview.get("plan_id") != plan_id:
                raise BrokerError("interactive PRoot preview is stale")
            spawned = self.spawn_login(plan_id)
            if not isinstance(spawned, dict) or set(spawned) != {"record", "master_fd", "child_pid"}:
                raise BrokerError("fixed-profile PTY spawner returned an invalid result")
            record, master_fd, child_pid = spawned["record"], spawned["master_fd"], spawned["child_pid"]
            valid_record = (isinstance(record, dict) and isinstance(record.get("session_id"), str)
                            and _SESSION_ID.fullmatch(record["session_id"])
                            and type(master_fd) is int and master_fd >= 0
                            and type(child_pid) is int and child_pid > 0
                            and record.get("profile") == "debian-interactive"
                            and record.get("pid") == child_pid)
            try:
                verified = bool(valid_record and self.verify_record(record))
            except Exception:
                verified = False
            if not verified:
                if type(master_fd) is int and master_fd >= 0:
                    try:
                        os.close(master_fd)
                    except OSError:
                        pass
                if isinstance(record, dict) and isinstance(record.get("session_id"), str):
                    try:
                        self.record_exit(record, "unknown", None)
                    except Exception:
                        pass
                raise BrokerError("spawned PRoot session identity is not verified")
            try:
                attachment = self.registry.attach(record["session_id"], principal)
            except Exception as exc:
                try:
                    os.close(master_fd)
                except OSError:
                    pass
                try:
                    self.record_exit(record, "unknown", None)
                except Exception:
                    pass
                raise BrokerError("terminal writer could not be attached to the new PTY") from exc
            process = _PTYProcess(
                record, child_pid, master_fd,
                attachment_generation=attachment["generation"],
                attachment_id=attachment["attachment_id"],
                attachment_principal=principal)
            self._process = process
            thread = threading.Thread(target=self._poll, args=(process,),
                                      name="ternuxx-terminal-pty", daemon=True)
            self._thread = thread
            try:
                thread.start()
            except Exception:
                self._process = None
                self._thread = None
                try:
                    self.registry.detach(record["session_id"], self.registry.generation,
                                         attachment["attachment_id"], principal)
                except BrokerError:
                    pass
                os.close(master_fd)
                self.record_exit(record, "unknown", None)
                raise BrokerError("PTY output relay could not start")
            return {"session_id": record["session_id"], "profile": "debian-interactive",
                    "state": "running", **attachment}

    def is_verified(self, session_id: str) -> bool:
        with self._lock:
            process = self._process
            return bool(process and not process.closed
                        and process.record.get("session_id") == session_id
                        and self.verify_record(process.record))

    def write_input(self, session_id: str, data: bytes, *, timeout: float = 1.0) -> None:
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_INPUT:
            raise BrokerError("terminal input is outside the allowed size")
        deadline = time.monotonic() + timeout
        with self._lock:
            process = self._require_process(session_id)
            view = memoryview(data)
            while view:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BrokerError("PTY input backpressure limit was reached")
                try:
                    _readable, writable, _exceptional = select.select([], [process.master_fd], [], remaining)
                    if not writable:
                        raise BrokerError("PTY input backpressure limit was reached")
                    written = os.write(process.master_fd, view)
                except (OSError, ValueError) as exc:
                    raise BrokerError("PTY input relay is unavailable") from exc
                if written <= 0:
                    raise BrokerError("PTY input relay accepted no data")
                view = view[written:]

    def resize(self, session_id: str, columns: int, rows: int) -> None:
        if (type(columns) is not int or type(rows) is not int
                or not 1 <= columns <= 500 or not 1 <= rows <= 300):
            raise BrokerError("terminal dimensions are outside the allowed range")
        with self._lock:
            process = self._require_process(session_id)
            try:
                fcntl.ioctl(process.master_fd, termios.TIOCSWINSZ,
                            struct.pack("HHHH", rows, columns, 0, 0))
            except OSError as exc:
                raise BrokerError("PTY resize relay is unavailable") from exc

    def release_after_stop(self, session_id: str) -> None:
        with self._lock:
            process = self._process
            if (process is None or process.closed
                    or process.record.get("session_id") != session_id):
                raise BrokerError("terminal PRoot session is not owned by this broker")
            self._close_process(process)
            self._process = None
            self._thread = None
        self._detach_process(process)

    def status(self) -> str:
        with self._lock:
            return "running" if self._process is not None and not self._process.closed else "not_connected"

    def close(self) -> None:
        """Close the broker's PTY without signaling or adopting its guest process."""
        with self._lock:
            self._closed = True
            process = self._process
            self._process = None
            self._thread = None
            if process is None or process.closed:
                return
            self._close_process(process)
        self._detach_process(process)
        self._record_exit_once(process, "unknown", process.exit_code)

    def _require_process(self, session_id: str) -> _PTYProcess:
        process = self._process
        if (process is None or process.closed
                or process.record.get("session_id") != session_id
                or not self.verify_record(process.record)):
            raise BrokerError("terminal PRoot session identity is not verified by this broker")
        return process

    def _record_exit_once(self, process: _PTYProcess, state: str, code: int | None) -> None:
        with self._lock:
            if process.exit_recorded:
                return
            process.exit_recorded = True
        try:
            self.record_exit(process.record, state, code)
        except Exception:
            pass

    def _detach_process(self, process: _PTYProcess) -> None:
        if not process.attachment_id:
            return
        try:
            session_id = process.record.get("session_id")
            self.registry.detach(session_id, process.attachment_generation,
                                process.attachment_id, process.attachment_principal)
        except BrokerError:
            pass
        process.attachment_id = ""

    def _close_process(self, process: _PTYProcess) -> None:
        if process.closed:
            return
        process.closed = True
        try:
            os.close(process.master_fd)
        except OSError:
            pass

    def _poll(self, process: _PTYProcess) -> None:
        while True:
            with self._lock:
                if self._closed or process.closed or self._process is not process:
                    return
            if not process.eof:
                try:
                    ready, _, _ = select.select([process.master_fd], [], [], self.poll_interval)
                except (OSError, ValueError):
                    ready = [process.master_fd]
                if ready:
                    try:
                        data = os.read(process.master_fd, 65536)
                    except OSError as exc:
                        if exc.errno == errno.EIO:
                            data = b""
                        elif exc.errno in {errno.EAGAIN, errno.EWOULDBLOCK}:
                            data = None
                        else:
                            data = b""
                    if data == b"":
                        process.eof = True
                    elif data:
                        try:
                            self.registry.publish_output(process.record["session_id"],
                                                         self.registry.generation, data)
                        except BrokerError:
                            pass
            if process.exit_code is None:
                try:
                    waited, status = os.waitpid(process.child_pid, os.WNOHANG)
                    if waited:
                        process.exit_code = os.waitstatus_to_exitcode(status)
                except ChildProcessError:
                    process.wait_status_unknown = True
            try:
                remaining = self.session_members(process.child_pid)
            except Exception:
                remaining = [(process.child_pid, "unknown")]
            if (process.eof and (process.exit_code is not None or process.wait_status_unknown)
                    and not remaining):
                final_state = "stopped" if process.exit_code is not None else "unknown"
                try:
                    self._record_exit_once(process, final_state, process.exit_code)
                except Exception:
                    pass
                with self._lock:
                    self._close_process(process)
                    if self._process is process:
                        self._process = None
                    self._thread = None
                return
            if process.eof:
                time.sleep(self.poll_interval)
