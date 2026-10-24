"""Ownership-aware disposable PRoot session lifecycle for Ternuxx.

The isolated probe is a bounded background profile. The debian-interactive
profile enters the installed Debian guest in a foreground terminal session,
matching the existing db login semantics while recording independent Ternuxx
ownership. Neither profile starts GUI or services.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time
import uuid

import proot_diagnostics

SCHEMA = 3
PROFILES = {
    "isolated-probe": {"version": 1, "mode": "background", "purpose": "bounded diagnostic process", "user": None},
    "debian-interactive": {"version": 1, "mode": "foreground-tty", "purpose": "interactive Debian login shell", "user": None},
}
_MAX_RECORDS = 256
_SESSION_ID = re.compile(r"proot-[0-9a-f]{32}")
_MARKER_PREFIX = "TERNUXX_PROOT_SESSION="


class SessionError(ValueError):
    pass


def _paths(state_dir: str | os.PathLike[str], *, create: bool):
    state = Path(state_dir).absolute()
    if create:
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not state.exists() and not state.is_symlink() and not create:
        root = state / "proot"
        return root, root / "sessions.json", root / ".sessions.lock"
    st = state.lstat()
    if state.is_symlink() or not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise SessionError("Ternuxx state directory identity or permissions are unsafe")
    root = state / "proot"
    if create:
        root.mkdir(mode=0o700, exist_ok=True)
    if not root.exists() and not root.is_symlink():
        return root, root / "sessions.json", root / ".sessions.lock"
    rst = root.lstat()
    if root.is_symlink() or not stat.S_ISDIR(rst.st_mode) or rst.st_uid != os.getuid() or rst.st_mode & 0o077:
        raise SessionError("PRoot session directory identity or permissions are unsafe")
    return root, root / "sessions.json", root / ".sessions.lock"


def _read_registry(path: Path) -> list[dict[str, object]]:
    if not path.exists() and not path.is_symlink():
        return []
    st = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise SessionError("PRoot session registry identity or permissions are unsafe")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SessionError("PRoot session registry is corrupt") from exc
    if (not isinstance(data, dict) or set(data) != {"schema_version", "sessions"}
            or type(data["schema_version"]) is not int or data["schema_version"] not in {1, 2, SCHEMA}
            or not isinstance(data["sessions"], list) or len(data["sessions"]) > _MAX_RECORDS):
        raise SessionError("PRoot session registry schema is unsupported")
    sessions = []
    for original in data["sessions"]:
        record = dict(original) if isinstance(original, dict) else original
        if isinstance(record, dict) and record.get("schema_version") in {1, 2}:
            old_version = record["schema_version"]
            if old_version == 1:
                record.update({"profile_version": 1,
                               "purpose": "bounded diagnostic process", "mode": "background",
                               "working_directory": "guest-default", "environment_profile": "inherited-approved",
                               "transitions": [{"state": record.get("state", "unknown"),
                                                "at": record.get("created_at", ""), "source": "schema-migration-v1"}]})
            record.update({"schema_version": SCHEMA, "last_exit_code": None})
        _validate_record(record)
        sessions.append(record)
    if len({record["session_id"] for record in sessions}) != len(sessions):
        raise SessionError("PRoot session registry has duplicate identities")
    return sessions


def _validate_record(record: object) -> None:
    required = {"schema_version", "session_id", "profile", "profile_version", "purpose", "mode",
                "rootfs", "rootfs_device", "rootfs_inode", "launcher", "launcher_device",
                "launcher_inode", "pid", "process_start", "process_group", "marker",
                 "expected_argv", "working_directory", "environment_profile", "created_at",
                "state", "last_verified_at", "last_exit_code", "transitions"}
    if not isinstance(record, dict) or set(record) != required or record["schema_version"] != SCHEMA:
        raise SessionError("PRoot session record fields are malformed")
    if not isinstance(record["session_id"], str) or not _SESSION_ID.fullmatch(record["session_id"]):
        raise SessionError("PRoot session identity is invalid")
    profile = record["profile"]
    if (not isinstance(profile, str) or profile not in PROFILES
            or type(record["profile_version"]) is not int
            or record["profile_version"] != PROFILES[profile]["version"]
            or record["mode"] != PROFILES[profile]["mode"]):
        raise SessionError("PRoot session profile is unsupported")
    for key in ("purpose", "working_directory", "environment_profile", "rootfs", "launcher", "process_start", "marker", "created_at", "state"):
        if not isinstance(record[key], str) or len(record[key]) > 512:
            raise SessionError(f"PRoot session {key} is invalid")
    for key in ("rootfs_device", "rootfs_inode", "launcher_device", "launcher_inode", "pid", "process_group"):
        if type(record[key]) is not int or record[key] < 0:
            raise SessionError(f"PRoot session {key} is invalid")
    if record["state"] not in {"starting", "running", "stopping", "stopped", "failed", "unknown", "unverified"}:
        raise SessionError("PRoot session state is invalid")
    if record["pid"] == 0:
        if (record["state"] not in {"starting", "unverified"}
                or record["process_group"] != 0 or record["process_start"] != ""):
            raise SessionError("PRoot session without a process identity is invalid")
    elif record["pid"] <= 0 or record["process_group"] != record["pid"] or not record["process_start"]:
        raise SessionError("PRoot process ownership identity is invalid")
    if not isinstance(record["expected_argv"], list) or any(
            not isinstance(arg, str) or len(arg) > 256 for arg in record["expected_argv"]):
        raise SessionError("PRoot expected arguments are invalid")
    if record["last_verified_at"] is not None and not isinstance(record["last_verified_at"], str):
        raise SessionError("PRoot verification timestamp is invalid")
    if record["last_exit_code"] is not None and (type(record["last_exit_code"]) is not int
                                                   or not -255 <= record["last_exit_code"] <= 255):
        raise SessionError("PRoot exit status is invalid")
    if not isinstance(record["transitions"], list) or len(record["transitions"]) > 128:
        raise SessionError("PRoot transition history is invalid")
    if any(not isinstance(item, dict) or set(item) != {"state", "at", "source"}
           or not isinstance(item.get("state"), str)
           or item.get("state") not in {"starting", "running", "stopping", "stopped", "failed", "unknown", "unverified"}
           or any(not isinstance(item.get(key), str) or len(item[key]) > 128 for key in ("at", "source"))
           for item in record["transitions"]):
        raise SessionError("PRoot transition history entry is invalid")


def _write_registry(root: Path, path: Path, records: list[dict[str, object]]) -> None:
    upgraded = []
    for old in records[-_MAX_RECORDS:]:
        rec = dict(old)
        if rec.get("schema_version") in {1, 2}:
            old_version = rec["schema_version"]
            if old_version == 1:
                rec.update({"profile_version": 1,
                            "purpose": "bounded diagnostic process", "mode": "background",
                            "working_directory": "guest-default", "environment_profile": "inherited-approved",
                            "transitions": [{"state": rec.get("state", "unknown"),
                                             "at": rec.get("created_at", ""), "source": "schema-migration-v1"}]})
            rec.update({"schema_version": SCHEMA, "last_exit_code": None})
        upgraded.append(rec)
    payload = json.dumps({"schema_version": SCHEMA, "sessions": upgraded},
                         sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    temp = root / (".sessions." + uuid.uuid4().hex + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        os.chmod(path, 0o600)
        dfd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


class _RegistryLock:
    def __init__(self, path: Path):
        if path.is_symlink():
            raise SessionError("PRoot session lock is a symlink")
        self.fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        st = os.fstat(self.fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            os.close(self.fd)
            raise SessionError("PRoot session lock identity or permissions are unsafe")
        fcntl.flock(self.fd, fcntl.LOCK_EX)

    def close(self):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


def _proc(pid: int):
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        fields = raw[raw.rfind(")") + 2:].split()
        if len(fields) <= 19:
            return None
        return {"state": fields[0], "pgrp": int(fields[2]), "session": int(fields[3]),
                "start": fields[19]}
    except (OSError, ValueError, IndexError):
        return None


def _members(session_id: int) -> list[tuple[int, str]]:
    found = []
    try:
        children = list(Path("/proc").iterdir())
    except OSError:
        return found
    for child in children:
        if not child.name.isdigit():
            continue
        identity = _proc(int(child.name))
        if identity and identity["session"] == session_id and identity["state"] not in {"Z", "X"}:
            found.append((int(child.name), identity["state"]))
    return found


def _proc_cwd_matches_rootfs(proc: Path, rootfs: Path) -> bool:
    """Compare cwd directory identity, not the pathname shown by procfs.

    PRoot can expose its rootfs through a procfs magic link printed as `/`.
    The pathname may differ while both names identify the same directory.
    """
    try:
        if rootfs.is_symlink():
            return False
        cwd_stat = (proc / "cwd").stat()
        rootfs_stat = rootfs.stat()
    except OSError:
        return False
    return (cwd_stat.st_dev, cwd_stat.st_ino) == (rootfs_stat.st_dev, rootfs_stat.st_ino)


def _await_verified_login(record: dict[str, object], pid: int, *, timeout: float = 5.0) -> bool:
    """Wait briefly for proot-distro's launcher to exec the actual PRoot process."""
    deadline = time.monotonic() + timeout
    while True:
        identity = _proc(pid)
        if (identity is None or identity["state"] in {"Z", "X"}
                or identity["start"] != record["process_start"]
                or identity["pgrp"] != record["process_group"]
                or identity["session"] != record["process_group"]):
            return False
        if _verified(record):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def _record_guest_user(record: dict[str, object]) -> str:
    argv = record.get("expected_argv")
    try:
        user = argv[argv.index("--user") + 1]
    except (AttributeError, ValueError, IndexError, TypeError) as exc:
        raise SessionError("interactive session record has no selected guest account") from exc
    if not isinstance(user, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user):
        raise SessionError("interactive session record has an invalid guest account")
    return user


def _verified(record: dict[str, object], *, proc_root: Path | None = None) -> bool:
    proc_root = Path("/proc") if proc_root is None else Path(proc_root)
    identity = _proc(record["pid"])
    if (identity is None or identity["state"] in {"Z", "X"}
            or identity["start"] != record["process_start"]
            or identity["pgrp"] != record["process_group"]
            or identity["session"] != record["process_group"]):
        return False
    proc = proc_root / str(record["pid"])
    try:
        env = (proc / "environ").read_bytes().split(b"\0")
        argv = [x.decode("utf-8", "replace") for x in (proc / "cmdline").read_bytes().split(b"\0") if x]
        status = (proc / "status").read_text(encoding="ascii")
    except OSError:
        return False
    uid_line = next((line for line in status.splitlines() if line.startswith("Uid:")), "")
    try:
        if int(uid_line.split()[1]) != os.getuid():
            return False
    except (IndexError, ValueError):
        return False
    # Ternuxx marker, PID start identity, isolated session/group identity,
    # launcher inode and profile-specific argv are jointly required.
    text = " ".join(argv).lower()
    try:
        launcher = Path(record["launcher"])
        st = launcher.stat()
        if launcher.is_symlink() or (st.st_dev, st.st_ino) != (record["launcher_device"], record["launcher_inode"]):
            return False
        rootfs = Path(record["rootfs"])
        rst = rootfs.stat()
        if rootfs.is_symlink() or (rst.st_dev, rst.st_ino) != (record["rootfs_device"], record["rootfs_inode"]):
            return False
    except OSError:
        return False
    # proot-distro sanitizes the inherited host environment before exec. The
    # random per-session marker is also passed as a guest env argv value.
    marker_token = record["marker"].split("=", 1)[-1]
    marker_present = record["marker"].encode() in env or marker_token in text
    if "proot" not in text or not marker_present:
        return False
    if record["profile"] == "isolated-probe":
        return "/bin/sleep" in text and str(record["expected_argv"][-1]) in text
    # proot-distro transforms its public login arguments into a proot argv:
    # distro name and --user disappear, while rootfs cwd, numeric guest IDs,
    # and the fixed login command remain observable.
    try:
        passwd = (Path(record["rootfs"]) / "etc/passwd").read_text(
            encoding="utf-8", errors="replace")
        user = _record_guest_user(record)
        account = next(line.split(":") for line in passwd.splitlines()
                       if line.split(":", 1)[0] == user)
        expected_ids = f"--change-id={int(account[2])}:{int(account[3])}"
    except (OSError, ValueError, IndexError, StopIteration):
        return False
    return (_proc_cwd_matches_rootfs(proc, Path(record["rootfs"]))
            and expected_ids in argv and "/usr/bin/env" in text
            and marker_token in text and "/bin/bash --login" in text)


def _contains_sequence(argv: list[str], expected: list[str]) -> bool:
    if not expected:
        return False
    for start in range(len(argv) - len(expected) + 1):
        if argv[start:start + len(expected)] == expected:
            return True
    return False


def _guest_alias(value: str) -> str:
    if (not isinstance(value, str) or (value != "debian"
            and not re.fullmatch(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", value))):
        raise SessionError("guest alias must be debian or an explicit ternuxx-replay-NAME")
    return value


def discover_debian(*, prefix: str, which=None, alias: str = "debian") -> dict[str, object]:
    alias = _guest_alias(alias)
    if which is None:
        import shutil
        which = shutil.which
    launcher = which("proot-distro", path=os.environ.get("PATH"))
    if not launcher:
        raise SessionError("proot-distro executable is unavailable")
    launcher_path = Path(launcher).absolute()
    if launcher_path.is_symlink() or not os.access(launcher_path, os.X_OK):
        raise SessionError("proot-distro executable identity is unsafe")
    launcher_stat = launcher_path.stat()
    rootfs = Path(prefix) / "var/lib/proot-distro/containers" / alias / "rootfs"
    if rootfs.is_symlink() or not rootfs.is_dir():
        raise SessionError("configured Debian rootfs is unavailable or symlinked")
    resolved = rootfs.resolve(strict=True)
    if resolved != rootfs.absolute():
        raise SessionError("configured Debian rootfs path resolves through a symlink")
    root_stat = rootfs.stat()
    return {"alias": alias, "rootfs": str(rootfs), "rootfs_device": root_stat.st_dev, "rootfs_inode": root_stat.st_ino,
            "launcher": str(launcher_path), "launcher_device": launcher_stat.st_dev,
            "launcher_inode": launcher_stat.st_ino}


def _same_discovery(left: dict[str, object], right: dict[str, object]) -> bool:
    keys = ("rootfs", "rootfs_device", "rootfs_inode", "launcher",
            "launcher_device", "launcher_inode")
    return all(left.get(key) == right.get(key) for key in keys)


def _observed_state(record: dict[str, object]) -> str:
    if record["state"] in {"stopped", "failed"}:
        return str(record["state"])
    return str(record["state"]) if _verified(record) else "unverified"


def list_sessions(state_dir: str | os.PathLike[str]) -> list[dict[str, object]]:
    root, path, _lock_path = _paths(state_dir, create=False)
    if not root.exists():
        return []
    # Writers replace the complete registry atomically. A lock here would
    # create .sessions.lock during a read-only inventory, so read the old or
    # new complete snapshot without creating state.
    result = []
    for record in _read_registry(path):
        item = {key: record[key] for key in ("session_id", "profile", "profile_version",
                                              "purpose", "mode", "rootfs", "pid",
                                              "created_at", "last_verified_at")}
        item["recorded_state"] = record["state"]
        item["state"] = _observed_state(record)
        item["ownership"] = ("released" if record["state"] == "stopped" else
                             "ternuxx_verified" if _verified(record) else "unverified")
        result.append(item)
    return result


def start_probe(state_dir: str | os.PathLike[str], *, prefix: str, timeout_seconds: int = 300,
                expected_plan_id: str | None = None) -> dict[str, object]:
    if type(timeout_seconds) is not int or not 30 <= timeout_seconds <= 1800:
        raise SessionError("probe lifetime must be between 30 and 1800 seconds")
    discovery = discover_debian(prefix=prefix)
    if expected_plan_id is not None and expected_plan_id != _start_plan("isolated-probe", discovery):
        raise SessionError("PRoot start preview is stale; rootfs or launcher identity changed")
    root, path, lock_path = _paths(state_dir, create=True)
    lock = _RegistryLock(lock_path)
    child_pid = None
    record = None
    try:
        records = _read_registry(path)
        for existing in records:
            if existing["profile"] == "isolated-probe" and existing["state"] in {"starting", "running", "stopping", "unverified", "failed"}:
                if _verified(existing):
                    raise SessionError("an isolated-probe session is already active")
                observation = _reconcile_observation(existing)
                if observation not in {"process_absent", "pid_reused_original_exited", "original_process_exited"}:
                    raise SessionError("an isolated-probe record has live or incomplete identity evidence; refusing a duplicate")
                # Proven exit permits a new unique session, but the old record
                # remains for explicit, preview-bound reconciliation.
        session_id = "proot-" + uuid.uuid4().hex
        token = uuid.uuid4().hex
        marker = _MARKER_PREFIX + token
        launcher = discovery["launcher"]
        argv = [launcher, "login", "--minimal", "debian", "--",
                "/usr/bin/env", marker, "/bin/sleep", str(timeout_seconds)]
        record = {"schema_version": SCHEMA, "session_id": session_id, "profile": "isolated-probe",
                  "profile_version": 1, "purpose": PROFILES["isolated-probe"]["purpose"],
                  "mode": PROFILES["isolated-probe"]["mode"], "working_directory": "guest-default",
                  "environment_profile": "isolated-no-host-home-or-display", "rootfs": discovery["rootfs"], "rootfs_device": discovery["rootfs_device"],
                  "rootfs_inode": discovery["rootfs_inode"], "launcher": launcher,
                  "launcher_device": discovery["launcher_device"], "launcher_inode": discovery["launcher_inode"],
                  "pid": 0, "process_start": "", "process_group": 0, "marker": marker,
                  "expected_argv": argv, "created_at": __import__("datetime").datetime.now(
                      __import__("datetime").timezone.utc).isoformat(),
                  "state": "starting", "last_verified_at": None, "last_exit_code": None,
                  "transitions": [{"state": "starting", "at": __import__("datetime").datetime.now(
                      __import__("datetime").timezone.utc).isoformat(), "source": "start"}]}
        records.append(record)
        _write_registry(root, path, records)
        env = _proot_host_environment()
        env[marker.split("=", 1)[0]] = token
        # A long-lived TUI/Web process can own this operation. Forking the
        # bounded background guest directly makes it a child of that client;
        # after a confirmed stop it would remain a zombie until the client
        # exits. Reparent the actual workload after a short-lived intermediate
        # child so the platform init process reaps it independently.
        pid_read, pid_write = os.pipe()
        helper_pid = os.fork()
        if helper_pid == 0:
            os.close(pid_read)
            try:
                child_pid = os.fork()
                if child_pid > 0:
                    os.write(pid_write, str(child_pid).encode("ascii"))
                    os.close(pid_write)
                    os._exit(0)
                os.close(pid_write)
                os.setsid()
                null_fd = os.open(os.devnull, os.O_RDWR)
                for stream_fd in (0, 1, 2):
                    os.dup2(null_fd, stream_fd)
                if null_fd > 2:
                    os.close(null_fd)
                current = discover_debian(prefix=prefix)
                if not _same_discovery(current, discovery):
                    os._exit(126)
                os.execve(launcher, argv, env)
            except BaseException:
                os._exit(127)
        os.close(pid_write)
        child_pid = None
        try:
            payload = b""
            while len(payload) < 32:
                chunk = os.read(pid_read, 32 - len(payload))
                if not chunk:
                    break
                payload += chunk
        finally:
            os.close(pid_read)
        _waited_helper, helper_status = os.waitpid(helper_pid, 0)
        if not os.WIFEXITED(helper_status) or os.WEXITSTATUS(helper_status) != 0:
            raise SessionError("isolated PRoot launcher helper failed")
        try:
            child_pid = int(payload.decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise SessionError("isolated PRoot launcher helper returned no process identity") from exc
        child_start = None
        identity = _proc(child_pid)
        child_start = identity["start"] if identity else None
        deadline = time.monotonic() + 10
        while (identity is None or identity["state"] in {"Z", "X"}
               or identity["session"] != child_pid or identity["pgrp"] != child_pid) and time.monotonic() < deadline:
            time.sleep(0.02)
            identity = _proc(child_pid)
        if identity is None or identity["state"] in {"Z", "X"}:
            raise SessionError("isolated PRoot probe exited before its process identity was recorded")
        if identity["session"] != child_pid or identity["pgrp"] != child_pid:
            raise SessionError("isolated PRoot process did not enter its private session")
        record["pid"] = child_pid
        record["process_start"] = identity["start"]
        record["process_group"] = child_pid
        record["transitions"].append({"state": "starting", "at": _timestamp(), "source": "process-identity-recorded"})
        records[-1] = record
        _write_registry(root, path, records)
        # Require a stable live PRoot command after startup, not just the
        # transient wrapper process observed immediately after fork.
        ready_deadline = time.monotonic() + 0.3
        while time.monotonic() < ready_deadline:
            identity = _proc(child_pid)
            if identity is None or identity["state"] in {"Z", "X"}:
                raise SessionError("isolated PRoot probe exited during startup")
            time.sleep(0.03)
        record["state"] = "running"
        record["transitions"].append({"state": "running", "at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(), "source": "start-verified"})
        record["last_verified_at"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat()
        records[-1] = record
        _write_registry(root, path, records)
        if not _verified(record):
            raise SessionError("isolated PRoot process ownership could not be verified")
        return {"session_id": session_id, "profile": record["profile"], "state": "running",
                "ownership": "ternuxx_verified", "rootfs_identity": {
                    "device": record["rootfs_device"], "inode": record["rootfs_inode"]}}
    except Exception:
        # A failed marker/profile check must not trigger cleanup of a process
        # that is not yet verified as an owned session. Preserve evidence for
        # explicit diagnosis and let bounded probes expire naturally.
        if record is not None:
            try:
                observation = _reconcile_observation(record)
                if observation in {"process_absent", "pid_reused_original_exited", "original_process_exited"}:
                    _append_transition(record, "stopped", "probe-start-failed-evidence:" + observation)
                else:
                    _append_transition(record, "unverified", _failure_evidence_source("probe-start-failed", record))
                _write_registry(root, path, records)
            except (OSError, SessionError):
                pass
        raise
    finally:
        lock.close()


def show_session(state_dir: str | os.PathLike[str], session_id: str, *, include_private: bool = False):
    if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
        raise SessionError("PRoot session ID is invalid")
    root, path, lock_path = _paths(state_dir, create=False)
    if not root.exists():
        raise SessionError("PRoot session was not found")
    lock = _RegistryLock(lock_path)
    try:
        record = next((r for r in _read_registry(path) if r["session_id"] == session_id), None)
        if record is None:
            raise SessionError("PRoot session was not found")
        result = dict(record)
        result["recorded_state"] = record["state"]
        result["state"] = _observed_state(record)
        result["ownership"] = ("released" if record["state"] == "stopped" else
                               "ternuxx_verified" if _verified(record) else "unverified")
        return result if include_private else {key: result[key] for key in (
            "session_id", "profile", "profile_version", "purpose", "mode", "rootfs",
            "rootfs_device", "rootfs_inode", "launcher", "pid", "process_start",
            "process_group", "working_directory", "environment_profile", "state",
            "recorded_state", "ownership", "created_at", "last_verified_at", "last_exit_code", "transitions")}
    finally:
        lock.close()


def _plan_id(record: dict[str, object]) -> str:
    selected = {key: record[key] for key in (
        "session_id", "pid", "process_start", "process_group", "rootfs",
        "rootfs_device", "rootfs_inode", "launcher", "launcher_device", "launcher_inode")}
    selected.update({"stop_contract": 2, "profile": record["profile"],
                     "signal": "SIGHUP" if record["profile"] == "debian-interactive" else "SIGTERM"})
    payload = json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()
    return "plan-" + __import__("hashlib").sha256(payload).hexdigest()


def preview_stop(state_dir: str | os.PathLike[str], session_id: str) -> dict[str, object]:
    record = show_session(state_dir, session_id, include_private=True)
    verified = record["ownership"] == "ternuxx_verified"
    interactive = record["profile"] == "debian-interactive"
    return {"session_id": session_id, "profile": record["profile"],
            "ownership": record["ownership"],
            "action": ("hangup_owned_terminal_session" if interactive else "signal_owned_process_group") if verified else "blocked",
            "signal": "SIGHUP" if interactive else "SIGTERM",
            "scope": "verified_private_session_job_groups" if interactive else "verified_process_group",
            "impact": ("Hang up this owned terminal and its verified private-session job groups; no force signal."
                       if interactive else "Request graceful termination of this owned diagnostic process group; no force signal."),
            "affected_process_group": record["process_group"] if verified else None,
            "rootfs": record["rootfs"], "plan_id": _plan_id(record) if verified else None,
            "confirmation_required": True}


def stop_session(state_dir: str | os.PathLike[str], session_id: str, *, confirmed: bool = False,
                 plan_id: str | None = None, timeout: float = 5.0) -> dict[str, object]:
    if confirmed is not True or not isinstance(plan_id, str):
        raise SessionError("PRoot stop requires an exact preview plan and explicit confirmation")
    root, path, lock_path = _paths(state_dir, create=False)
    lock = _RegistryLock(lock_path)
    try:
        records = _read_registry(path)
        record = next((r for r in records if r["session_id"] == session_id), None)
        if record is None:
            raise SessionError("PRoot session was not found")
        if not _verified(record):
            raise SessionError("PRoot session ownership is unknown; refusing to signal")
        if plan_id != _plan_id(record):
            raise SessionError("PRoot stop preview is stale or does not match the exact session")
        rootfs_path = Path(record["rootfs"])
        launcher_path = Path(record["launcher"])
        if (rootfs_path.is_symlink() or launcher_path.is_symlink()
                or rootfs_path.resolve(strict=True) != rootfs_path.absolute()):
            raise SessionError("PRoot rootfs or launcher path changed before stop")
        rst = rootfs_path.stat()
        lst = launcher_path.stat()
        if ((rst.st_dev, rst.st_ino) != (record["rootfs_device"], record["rootfs_inode"])
                or (lst.st_dev, lst.st_ino) != (record["launcher_device"], record["launcher_inode"])
                or not _verified(record)):
            raise SessionError("PRoot session identity changed before stop")
        pid, start = record["pid"], record["process_start"]
        _append_transition(record, "stopping", "confirmed-stop")
        _write_registry(root, path, records)
        if not _verified(record):
            raise SessionError("PRoot session identity changed immediately before stop")
        # Interactive shells normally ignore SIGTERM. Terminal hangup is
        # their graceful close signal; headless probes retain SIGTERM.
        interactive = record["profile"] == "debian-interactive"
        groups = {}
        if interactive:
            # Job control gives the login shell/jobs separate process groups
            # inside our newly created kernel session. The tracer ignores HUP;
            # closing only its group cannot hang up the foreground shell.
            for member_pid, _state in _members(record["process_group"]):
                member = _proc(member_pid)
                if (member and member["session"] == record["process_group"]
                        and member["pgrp"] > 0 and member["state"] not in {"Z", "X"}):
                    groups.setdefault(member["pgrp"], (member_pid, member["start"]))
        os.killpg(record["process_group"], signal.SIGHUP if interactive else signal.SIGTERM)
        for group, (member_pid, member_start) in groups.items():
            if group == record["process_group"]:
                continue
            member = _proc(member_pid)
            if (not _verified(record) or not member or member["start"] != member_start
                    or member["session"] != record["process_group"] or member["pgrp"] != group
                    or member["state"] in {"Z", "X"}):
                continue
            try:
                os.killpg(group, signal.SIGHUP)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and _members(record["process_group"]):
            time.sleep(0.05)
        if _members(record["process_group"]):
            return {"stopped": False, "state": "stopping", "stop_requested": True, "session_id": session_id,
                    "reason": "graceful stop timed out; no force signal was sent"}
        identity = _proc(pid)
        if identity is not None and identity["start"] == start and identity["state"] not in {"Z", "X"}:
            return {"stopped": False, "state": "stopping", "stop_requested": True, "session_id": session_id,
                    "reason": "owned process remains alive; no force signal was sent"}
        record["state"] = "stopped"
        record["transitions"].append({"state": "stopped", "at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(), "source": "stop-verified"})
        record["last_verified_at"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat()
        _write_registry(root, path, records)
        return {"stopped": True, "state": "stopped", "session_id": session_id, "ownership": "verified"}
    finally:
        lock.close()


def profile_inventory(*, prefix: str, alias: str = "debian") -> dict[str, object]:
    """Return the fixed, validated profiles and live guest discovery evidence."""
    try:
        found = discover_debian(prefix=prefix, alias=alias)
        rootfs_state = "available"
        root_identity = {"device": found["rootfs_device"], "inode": found["rootfs_inode"]}
        launcher = found["launcher"]
    except SessionError as exc:
        rootfs_state, root_identity, launcher = "unavailable", None, None
        diagnostic = str(exc)
    else:
        diagnostic = None
    selected_user = None
    user_error = None
    if rootfs_state == "available":
        try:
            selected_user = proot_diagnostics.resolve_proot_guest_user(distro=alias, prefix=prefix)
            after_user_read = discover_debian(prefix=prefix, alias=alias)
            if (after_user_read["rootfs_device"], after_user_read["rootfs_inode"]) != (
                    found["rootfs_device"], found["rootfs_inode"]):
                selected_user = None
                user_error = "guest rootfs identity changed during account discovery"
        except (proot_diagnostics.GuestProfileError, SessionError) as exc:
            user_error = str(exc)
    items = [
        {"id": "isolated-probe", **PROFILES["isolated-probe"],
         "available": rootfs_state == "available", "state_change": True,
         "description": "Bounded, headless Debian diagnostic sleep process; no host home or display binding."},
        {"id": "debian-interactive", **PROFILES["debian-interactive"], "user": selected_user,
         "available": rootfs_state == "available" and selected_user is not None, "state_change": True,
         "description": "Foreground login shell as the uniquely discovered ordinary guest account; no services or GUI are started."},
    ]
    if user_error and rootfs_state == "available":
        items[1]["unavailable_reason"] = user_error
    if rootfs_state == "available":
        for item in items:
            required = (["usr/bin/env", "bin/sleep"] if item["id"] == "isolated-probe"
                        else ["usr/bin/env", "bin/bash", "etc/passwd"])
            paths_ok = all(
                (Path(found["rootfs"]) / relative).is_file()
                and bool((Path(found["rootfs"]) / relative).stat().st_mode & 0o111)
                for relative in required if not relative.endswith("passwd")
            ) and ((Path(found["rootfs"]) / "etc/passwd").is_file() if item["id"] == "debian-interactive" else True)
            if item["id"] == "debian-interactive":
                paths_ok = paths_ok and selected_user is not None
            item["available"] = bool(paths_ok)
            if not paths_ok and "unavailable_reason" not in item:
                item["unavailable_reason"] = "configured guest executable or selected account is missing"
    return {"profiles": items, "rootfs_state": rootfs_state, "rootfs_identity": root_identity,
            "launcher": launcher, "diagnostic": diagnostic}


def show_profile(profile: str, *, prefix: str, alias: str = "debian") -> dict[str, object]:
    inventory = profile_inventory(prefix=prefix, alias=alias)
    item = next((entry for entry in inventory["profiles"] if entry["id"] == profile), None)
    if item is None:
        raise SessionError("PRoot profile is unsupported")
    return {"profile": item, "rootfs_state": inventory["rootfs_state"],
            "rootfs_identity": inventory["rootfs_identity"], "diagnostic": inventory["diagnostic"]}


def _start_plan(profile: str, discovery: dict[str, object], user: str | None = None) -> str:
    import hashlib
    spec = PROFILES[profile]
    content = {"profile": profile, "version": spec["version"], "mode": spec["mode"],
               "rootfs": discovery["rootfs"], "rootfs_device": discovery["rootfs_device"],
               "rootfs_inode": discovery["rootfs_inode"], "launcher": discovery["launcher"],
               "launcher_device": discovery["launcher_device"], "launcher_inode": discovery["launcher_inode"],
               "user": user if profile == "debian-interactive" else None}
    return "plan-" + hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def preview_start(profile: str, *, prefix: str, alias: str = "debian") -> dict[str, object]:
    if profile not in PROFILES:
        raise SessionError("PRoot profile is unsupported")
    discovery = discover_debian(prefix=prefix, alias=alias)
    detail = show_profile(profile, prefix=prefix, alias=alias)
    if not detail["profile"]["available"]:
        raise SessionError("PRoot profile preflight failed")
    spec = PROFILES[profile]
    user = detail["profile"].get("user") if profile == "debian-interactive" else None
    return {"alias": _guest_alias(alias), "profile": profile, "profile_version": spec["version"], "mode": spec["mode"],
            "user": user,
            "purpose": spec["purpose"], "rootfs": discovery["rootfs"],
            "rootfs_identity": {"device": discovery["rootfs_device"], "inode": discovery["rootfs_inode"]},
            "launcher": discovery["launcher"], "working_directory": "guest-default",
            "environment_profile": ("isolated-no-host-home-or-display" if profile == "isolated-probe"
                                    else "inherited-approved-proot-env"),
            "impact": ("Starts one bounded headless Debian diagnostic process."
                       if profile == "isolated-probe" else
                       "Enters a foreground login shell as the uniquely discovered guest account using shared-tmp. The installed proot-distro normal-login path can write the shared guest profile hook and its container sidecar state; Ternuxx does not snapshot or roll back those package-owned writes."),
            "confirmation_required": True, "plan_id": _start_plan(profile, discovery, user)}


def _timestamp() -> str:
    return __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()


def _failure_evidence_source(prefix: str, record: dict[str, object]) -> str:
    evidence = _recovery_evidence(record)
    checks = evidence.get("profile_checks") or {}
    values = {
        "entry": str(evidence["process_entry"]).replace("_", "-"),
        "grp": evidence["session_group_match"],
        "mark": evidence["marker_visible"],
        "pr": checks.get("proot"),
        "cwd": checks.get("cwd_rootfs"),
        "uid": checks.get("guest_ids"),
        "env": checks.get("guest_env"),
        "arg": checks.get("marker_argv"),
        "bash": checks.get("login_bash"),
        "fs": evidence["rootfs_identity_match"],
        "bin": evidence["launcher_identity_match"],
    }
    def compact(value):
        return "u" if value is None else "1" if value is True else "0" if value is False else value[:24]
    return (prefix + "-evidence:" + ";".join(f"{key}={compact(value)}" for key, value in values.items()))[:128]


def _historical_failure_evidence(record: dict[str, object]) -> dict[str, object] | None:
    for transition in reversed(record["transitions"]):
        source = transition["source"]
        if "-failed-evidence:" not in source:
            continue
        fields = dict(part.split("=", 1) for part in source.split(":", 1)[1].split(";") if "=" in part)
        def expand(value):
            return True if value == "1" else False if value == "0" else None if value == "u" else value
        return {"observed_at": transition["at"], **{key: expand(value) for key, value in fields.items()}}
    return None


def _append_transition(record: dict[str, object], state: str, source: str) -> None:
    record["state"] = state
    record["transitions"].append({"state": state, "at": _timestamp(), "source": source})
    record["transitions"] = record["transitions"][-128:]


def _proot_host_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Copy the host environment without dynamic-loader override variables.

    PRoot launchers are ordinary native executables. Inherited LD_* settings
    can alter the host-side Python/launcher before proot-distro sanitizes the
    guest environment, so none cross this process boundary.
    """
    result = dict(os.environ if source is None else source)
    for key in tuple(result):
        if key.startswith("LD_"):
            result.pop(key, None)
    return result


def _login_environment(marker: str, token: str,
                       source: dict[str, str] | None = None) -> dict[str, str]:
    # This is the environment of the Native proot-distro launcher. Keep the
    # small set its host-side runtime needs, then pass guest capabilities only
    # through explicit --env/--bind arguments. Never forward arbitrary Mesa,
    # Vulkan, PulseAudio, XDG, or Android library-path settings to Debian.
    source = _proot_host_environment(source)
    allowed = {"HOME", "PREFIX", "PATH", "TMPDIR", "TERM", "LANG", "LC_ALL", "COLORTERM"}
    result = {key: value for key, value in source.items()
              if key in allowed or key.startswith("LC_")}
    result[marker.split("=", 1)[0]] = token
    if (source.get("PREFIX") == "/data/data/com.termux/files/usr"
            and source.get("TERMUX_VERSION")):
        result.update({"DISPLAY": source.get("DISPLAY") or ":1",
                       "PULSE_SERVER": "tcp:127.0.0.1:4713",
                       "PULSE_COOKIE": "/tmp/.ternuxx-pulse-cookie",
                       "GALLIUM_DRIVER": "zink",
                       "MESA_LOADER_DRIVER_OVERRIDE": "zink",
                       "TU_DEBUG": "sysmem,noconform",
                       "MESA_VK_WSI_DEBUG": "sw",
                       "MESA_SHADER_CACHE_DISABLE": "true"})
    return result


def _native_pulse_login_args(source: dict[str, str] | None = None) -> list[str]:
    source = os.environ if source is None else source
    if (source.get("PREFIX") != "/data/data/com.termux/files/usr"
            or not source.get("TERMUX_VERSION")):
        return []
    cookie = Path(source.get("HOME", str(Path.home()))) / ".config/pulse/cookie"
    args = ["--env", "DISPLAY=" + (source.get("DISPLAY") or ":1"),
            "--env", "PULSE_SERVER=tcp:127.0.0.1:4713",
            "--env", "GALLIUM_DRIVER=zink",
            "--env", "MESA_LOADER_DRIVER_OVERRIDE=zink",
            "--env", "TU_DEBUG=sysmem,noconform",
            "--env", "MESA_VK_WSI_DEBUG=sw",
            "--env", "MESA_SHADER_CACHE_DISABLE=true"]
    try:
        info = cookie.lstat()
        if (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size == 256
                and not cookie.is_symlink()):
            args.extend(["--bind", f"{cookie}:/tmp/.ternuxx-pulse-cookie",
                         "--env", "PULSE_COOKIE=/tmp/.ternuxx-pulse-cookie"])
    except OSError:
        pass
    kgsl = Path("/dev/kgsl-3d0")
    try:
        if stat.S_ISCHR(kgsl.stat().st_mode):
            args.extend(["--bind", "/dev/kgsl-3d0:/dev/kgsl"])
    except OSError:
        pass
    if Path("/dev/dri").is_dir():
        args.extend(["--bind", "/dev/dri"])
    return args


def _create_login_record(state_dir: str | os.PathLike[str], discovery: dict[str, object], user: str):
    root, path, lock_path = _paths(state_dir, create=True)
    lock = _RegistryLock(lock_path)
    try:
        records = _read_registry(path)
        for existing in records:
            if existing["profile"] == "debian-interactive" and existing["state"] in {"starting", "running", "stopping", "unverified", "failed"}:
                if _verified(existing):
                    raise SessionError("a Ternuxx interactive Debian session is already active")
                observation = _reconcile_observation(existing)
                if observation not in {"process_absent", "pid_reused_original_exited", "original_process_exited"}:
                    raise SessionError("an interactive record has live or incomplete identity evidence; refusing a duplicate login")
                # Stale records are retained and never adopted or signalled.
        session_id, token = "proot-" + uuid.uuid4().hex, uuid.uuid4().hex
        marker = _MARKER_PREFIX + token
        argv = [discovery["launcher"], "login", _guest_alias(discovery.get("alias", "debian")), "--shared-tmp", "--user", user]
        argv.extend(_native_pulse_login_args())
        argv.extend(["--",
                "/usr/bin/env", marker, "/bin/bash", "--login"]
        )
        record = {"schema_version": SCHEMA, "session_id": session_id, "profile": "debian-interactive",
                  "profile_version": 1, "purpose": PROFILES["debian-interactive"]["purpose"],
                  "mode": PROFILES["debian-interactive"]["mode"], "working_directory": "guest-default",
                  "environment_profile": "inherited-approved-proot-env",
                  "rootfs": discovery["rootfs"], "rootfs_device": discovery["rootfs_device"],
                  "rootfs_inode": discovery["rootfs_inode"], "launcher": discovery["launcher"],
                  "launcher_device": discovery["launcher_device"], "launcher_inode": discovery["launcher_inode"],
                  "pid": 0, "process_start": "", "process_group": 0, "marker": marker,
                  "expected_argv": argv, "created_at": _timestamp(), "state": "starting",
                  "last_verified_at": None, "last_exit_code": None, "transitions": []}
        _append_transition(record, "starting", "login-request")
        records.append(record)
        _write_registry(root, path, records)
        return record, token
    finally:
        lock.close()


def _update_session(state_dir: str | os.PathLike[str], session_id: str, update) -> dict[str, object]:
    root, path, lock_path = _paths(state_dir, create=False)
    lock = _RegistryLock(lock_path)
    try:
        records = _read_registry(path)
        record = next((entry for entry in records if entry["session_id"] == session_id), None)
        if record is None:
            raise SessionError("PRoot session record disappeared")
        update(record)
        _write_registry(root, path, records)
        return record
    finally:
        lock.close()


def _relay_interactive_pty(master: int, child_pid: int, *, input_fd: int = 0,
                           output_fd: int = 1) -> int:
    """Relay one owned foreground PTY and always restore the caller terminal."""
    import errno
    import fcntl
    import select
    import termios
    import tty

    try:
        original_termios = termios.tcgetattr(input_fd)
    except BaseException:
        os.close(master)
        raise
    old_winch = signal.getsignal(signal.SIGWINCH)
    termios_changed = False
    winch_changed = False

    def resize(_signum=None, _frame=None):
        try:
            size = fcntl.ioctl(input_fd, termios.TIOCGWINSZ, b"\0" * 8)
            fcntl.ioctl(master, termios.TIOCSWINSZ, size)
        except OSError:
            pass

    status = None
    input_open = True
    try:
        termios_changed = True
        tty.setraw(input_fd)
        signal.signal(signal.SIGWINCH, resize)
        winch_changed = True
        resize()
        while True:
            ready, _, _ = select.select(
                [master] + ([input_fd] if input_open else []), [], [], 0.2)
            if input_fd in ready:
                data = os.read(input_fd, 4096)
                if data:
                    os.write(master, data)
                else:
                    input_open = False
                    try:
                        os.write(master, b"\x04")
                    except OSError:
                        pass
            if master in ready:
                try:
                    data = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        data = b""
                    else:
                        raise
                if not data:
                    break
                os.write(output_fd, data)
            if status is None:
                waited, wait_status = os.waitpid(child_pid, os.WNOHANG)
                if waited:
                    status = os.waitstatus_to_exitcode(wait_status)
            if status is not None and not _members(child_pid):
                try:
                    data = os.read(master, 65536)
                except OSError:
                    data = b""
                if data:
                    os.write(output_fd, data)
                break
        if status is None:
            _, wait_status = os.waitpid(child_pid, 0)
            status = os.waitstatus_to_exitcode(wait_status)
        return status
    finally:
        try:
            if termios_changed:
                termios.tcsetattr(input_fd, termios.TCSADRAIN, original_termios)
        finally:
            try:
                if winch_changed:
                    signal.signal(signal.SIGWINCH, old_winch)
            finally:
                os.close(master)


def spawn_login_interactive(state_dir: str | os.PathLike[str], *, prefix: str, confirmed: bool,
                           plan_id: str, alias: str = "debian") -> dict[str, object]:
    """Start the fixed interactive profile and transfer its verified PTY master to a broker.

    The caller owns the returned master FD and must retain, relay, and close it.
    No client TTY is required because this function does not perform a foreground relay.
    """
    if confirmed is not True or not isinstance(plan_id, str):
        raise SessionError("PRoot start requires an exact preview plan and explicit confirmation")
    preview = preview_start("debian-interactive", prefix=prefix, alias=alias)
    if plan_id != preview["plan_id"]:
        raise SessionError("PRoot start preview is stale or does not match the selected profile")
    discovery = discover_debian(prefix=prefix, alias=alias)
    user = preview["user"]
    current_user = proot_diagnostics.resolve_proot_guest_user(distro=alias, prefix=prefix)
    if current_user != user or plan_id != _start_plan("debian-interactive", discovery, user):
        raise SessionError("PRoot start preview is stale; rootfs, launcher, or guest account changed")
    record, token = _create_login_record(state_dir, discovery, user)
    env = _login_environment(record["marker"], token)
    child_pid = None
    master = None
    try:
        # Allocate a new controlling PTY so the guest login receives a real
        # foreground terminal with normal job-control semantics.
        import pty
        child_pid, master = pty.fork()
        if child_pid == 0:
            try:
                current = discover_debian(prefix=prefix, alias=alias)
                if not _same_discovery(current, discovery):
                    os._exit(126)
                os.execve(record["expected_argv"][0], record["expected_argv"], env)
            except BaseException:
                os._exit(127)
        identity = _proc(child_pid)
        deadline = time.monotonic() + 10
        while (identity is None or identity["state"] in {"Z", "X"
               } or identity["session"] != child_pid or identity["pgrp"] != child_pid) and time.monotonic() < deadline:
            time.sleep(0.02)
            identity = _proc(child_pid)
        if identity is None:
            raise SessionError("interactive Debian login process identity is unavailable")
        if identity["state"] in {"Z", "X"}:
            waited, wait_status = os.waitpid(child_pid, 0)
            exit_code = os.waitstatus_to_exitcode(wait_status) if waited else None
            def record_early_exit(saved):
                saved["pid"], saved["process_start"], saved["process_group"] = child_pid, identity["start"], child_pid
                _append_transition(saved, "stopped", "login-exited-during-startup")
                saved["last_exit_code"] = exit_code
            record = _update_session(state_dir, record["session_id"], record_early_exit)
            raise SessionError("interactive Debian login exited during startup")
        if identity["session"] != child_pid or identity["pgrp"] != child_pid:
            raise SessionError("interactive Debian process did not enter its private PTY session")
        def record_process_identity(saved):
            saved["pid"], saved["process_start"], saved["process_group"] = child_pid, identity["start"], child_pid
            _append_transition(saved, "starting", "process-identity-recorded")
        record = _update_session(state_dir, record["session_id"], record_process_identity)
        if not _await_verified_login(record, child_pid):
            raise SessionError("interactive Debian process ownership could not be verified")
        def mark_running(saved):
            _append_transition(saved, "running", "login-pty-verified")
            saved["last_verified_at"] = _timestamp()
        record = _update_session(state_dir, record["session_id"], mark_running)
        return {"record": record, "master_fd": master, "child_pid": child_pid}
    except Exception:
        if master is not None:
            try:
                os.close(master)
            except OSError:
                pass
        if child_pid is not None:
            identity = _proc(child_pid)
            if (identity and record.get("process_start")
                    and identity["start"] == record.get("process_start")
                    and identity["session"] == child_pid and identity["pgrp"] == child_pid
                    and _verified(record)):
                try:
                    os.killpg(child_pid, signal.SIGTERM)
                except OSError:
                    pass
                time.sleep(0.1)
        try:
            def record_start_failure(saved):
                observation = _reconcile_observation(saved)
                final = ("stopped" if observation in {"process_absent", "pid_reused_original_exited", "original_process_exited"}
                         else "unverified")
                source = ("login-start-failed-evidence:" + observation
                          if final == "stopped" else _failure_evidence_source("login-start-failed", saved))
                _append_transition(saved, final, source)
                saved["last_verified_at"] = _timestamp()
            record = _update_session(state_dir, record["session_id"], record_start_failure)
        except (OSError, SessionError):
            pass
        raise


def login_interactive(state_dir: str | os.PathLike[str], *, prefix: str, confirmed: bool,
                      plan_id: str) -> dict[str, object]:
    """Run the supported interactive Debian login on an owned controlling PTY."""
    if not os.isatty(0) or not os.isatty(1):
        raise SessionError("debian-interactive requires an attached terminal; use the headless profile otherwise")
    spawned = spawn_login_interactive(state_dir, prefix=prefix, confirmed=confirmed,
                                     plan_id=plan_id)
    record = spawned["record"]
    master = spawned["master_fd"]
    child_pid = spawned["child_pid"]
    try:
        print("Ternuxx Debian session " + record["session_id"] + " is attached. Type exit to leave.", file=sys.stderr)
        status = _relay_interactive_pty(master, child_pid)
        remaining = _members(child_pid)
        final_state = "stopped" if not remaining else "unknown"
        source = "login-exited" if not remaining else "login-exited-processes-remain"
        _update_session(state_dir, record["session_id"],
                        lambda saved: (_append_transition(saved, final_state, source),
                                       saved.update({"last_verified_at": _timestamp(),
                                                     "last_exit_code": status})))
        return {"session_id": record["session_id"], "profile": "debian-interactive",
                "state": final_state, "exit_code": status,
                "remaining_session_processes": len(remaining)}
    except Exception:
        try:
            os.close(master)
        except OSError:
            pass
        identity = _proc(child_pid)
        if (identity and record.get("process_start")
                and identity["start"] == record.get("process_start")
                and identity["session"] == child_pid and identity["pgrp"] == child_pid
                and _verified(record)):
            try:
                os.killpg(child_pid, signal.SIGTERM)
            except OSError:
                pass
        try:
            def record_relay_failure(saved):
                observation = _reconcile_observation(saved)
                final = ("stopped" if observation in {"process_absent", "pid_reused_original_exited", "original_process_exited"}
                         else "unverified")
                source = ("login-relay-failed-evidence:" + observation
                          if final == "stopped" else _failure_evidence_source("login-relay-failed", saved))
                _append_transition(saved, final, source)
                saved["last_verified_at"] = _timestamp()
            _update_session(state_dir, record["session_id"], record_relay_failure)
        except (OSError, SessionError):
            pass
        raise

def start_profile(state_dir: str | os.PathLike[str], *, prefix: str, profile: str,
                  confirmed: bool, plan_id: str, timeout_seconds: int = 300) -> dict[str, object]:
    if profile not in PROFILES:
        raise SessionError("PRoot profile is unsupported")
    if confirmed is not True or not isinstance(plan_id, str):
        raise SessionError("PRoot start requires an exact preview plan and explicit confirmation")
    preview = preview_start(profile, prefix=prefix)
    if plan_id != preview["plan_id"]:
        raise SessionError("PRoot start preview is stale or does not match the selected profile")
    if profile == "isolated-probe":
        return start_probe(state_dir, prefix=prefix, timeout_seconds=timeout_seconds,
                           expected_plan_id=plan_id)
    return login_interactive(state_dir, prefix=prefix, confirmed=confirmed, plan_id=plan_id)


def _reconcile_observation(record: dict[str, object]) -> str:
    pid = record["pid"]
    if pid <= 0 or not record["process_start"]:
        return "recorded_process_identity_missing"
    identity = _proc(pid)
    if identity is None:
        # /proc can hide entries. Signal 0 is a non-mutating existence check:
        # ESRCH proves absence; EPERM or other errors remain ambiguous.
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return "process_absent"
        except PermissionError:
            return "identity_unreadable"
        except OSError as exc:
            import errno
            return "process_absent" if exc.errno == errno.ESRCH else "identity_unreadable"
        return "identity_unreadable"
    if identity["start"] != record["process_start"]:
        return "pid_reused_original_exited"
    if identity["state"] in {"Z", "X"}:
        return "original_process_exited"
    if identity["pgrp"] != record["process_group"] or identity["session"] != record["process_group"]:
        return "same_process_identity_changed"
    return "same_process_live"


def _reconcile_plan(record: dict[str, object], observation: str) -> str:
    import hashlib
    body = {key: value for key, value in record.items()
            if key not in {"recorded_state", "ownership"}}
    body["state"] = record.get("recorded_state", record["state"])
    body["observation"] = observation
    return "plan-" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def preview_reconcile(state_dir: str | os.PathLike[str], session_id: str) -> dict[str, object]:
    record = show_session(state_dir, session_id, include_private=True)
    observation = _reconcile_observation(record)
    eligible = record["state"] != "stopped" and observation in {
        "process_absent", "pid_reused_original_exited", "original_process_exited"}
    return {"session_id": session_id, "recorded_state": record["recorded_state"],
            "observed_state": record["state"], "evidence": observation,
            "action": "mark_exited_without_signal" if eligible else "retain_record_no_signal",
            "confirmation_required": bool(eligible),
            "plan_id": _reconcile_plan(record, observation) if eligible else None,
            "signal_allowed": False}


def reconcile_session(state_dir: str | os.PathLike[str], session_id: str, *,
                      confirmed: bool, plan_id: str) -> dict[str, object]:
    if confirmed is not True or not isinstance(plan_id, str):
        raise SessionError("PRoot reconciliation requires a fresh plan and explicit confirmation")
    root, path, lock_path = _paths(state_dir, create=False)
    lock = _RegistryLock(lock_path)
    try:
        records = _read_registry(path)
        record = next((item for item in records if item["session_id"] == session_id), None)
        if record is None:
            raise SessionError("PRoot session was not found")
        observation = _reconcile_observation(record)
        if (record["state"] == "stopped"
                or observation not in {"process_absent", "pid_reused_original_exited", "original_process_exited"}):
            raise SessionError("process exit is not positively established; retaining the record")
        if plan_id != _reconcile_plan(record, observation):
            raise SessionError("PRoot reconciliation preview is stale")
        _append_transition(record, "stopped", "reconciled-" + observation)
        record["last_verified_at"] = _timestamp()
        record["last_exit_code"] = None
        _write_registry(root, path, records)
        return {"session_id": session_id, "state": "stopped", "exit_code": None,
                "evidence": observation, "signal_sent": False}
    finally:
        lock.close()


def session_health(state_dir: str | os.PathLike[str], session_id: str) -> dict[str, object]:
    """Return bounded liveness, ownership, exit, and attachment capability data."""
    record = show_session(state_dir, session_id, include_private=True)
    identity = _proc(record["pid"]) if record["pid"] > 0 else None
    same_start = bool(identity and identity["start"] == record["process_start"])
    return {
        "session_id": record["session_id"], "profile": record["profile"],
        "mode": record["mode"], "recorded_state": record["recorded_state"],
        "state": record["state"], "ownership": record["ownership"],
        "process_identity": ("matched" if same_start else
                             "missing" if record["pid"] <= 0 else
                             "unavailable_or_reused"),
        "process_state": identity["state"] if same_start else None,
        "session_group_match": bool(identity and identity["pgrp"] == record["process_group"]
                                     and identity["session"] == record["process_group"]),
        "exit_code": record["last_exit_code"],
        "attachment": "foreground-terminal-not-recoverable" if record["mode"] == "foreground-tty" else "none",
        "reattach_supported": False,
        "diagnostics": record["transitions"][-16:],
        "read_only": True,
    }


def _recovery_evidence(record: dict[str, object]) -> dict[str, object]:
    pid = record["pid"]
    identity = _proc(pid) if pid > 0 else None
    same_start = bool(identity and identity["start"] == record["process_start"])
    evidence: dict[str, object] = {
        "process_entry": _reconcile_observation(record),
        "process_start_match": same_start if identity else None,
        "session_group_match": (bool(identity and identity["pgrp"] == record["process_group"]
                                  and identity["session"] == record["process_group"]) if identity else None),
        "marker_visible": None,
        "profile_signature_match": None,
        "profile_checks": None,
        "rootfs_identity_match": False,
        "launcher_identity_match": False,
    }
    for label, key in (("rootfs_identity_match", "rootfs"), ("launcher_identity_match", "launcher")):
        try:
            path = Path(record[key])
            st = path.stat()
            expected = ((record[key + "_device"], record[key + "_inode"]))
            evidence[label] = not path.is_symlink() and (st.st_dev, st.st_ino) == expected
        except OSError:
            evidence[label] = False
    if same_start and identity and identity["state"] not in {"Z", "X"}:
        try:
            proc = Path(f"/proc/{pid}")
            argv = [x.decode("utf-8", "replace") for x in (proc / "cmdline").read_bytes().split(b"\0") if x]
            env = (proc / "environ").read_bytes().split(b"\0")
        except OSError:
            pass
        else:
            text = " ".join(argv).lower()
            marker_token = record["marker"].split("=", 1)[-1]
            marker_visible = record["marker"].encode() in env or marker_token in text
            evidence["marker_visible"] = marker_visible
            if record["profile"] == "isolated-probe":
                checks = {"proot": "proot" in text,
                          "sleep": ("/bin/sleep" in text and bool(record["expected_argv"])
                                    and str(record["expected_argv"][-1]) in text)}
                evidence["profile_checks"] = checks
                evidence["profile_signature_match"] = all(checks.values())
            else:
                try:
                    passwd = (Path(record["rootfs"]) / "etc/passwd").read_text(encoding="utf-8", errors="replace")
                    account = next(line.split(":") for line in passwd.splitlines()
                                   if line.split(":", 1)[0] == _record_guest_user(record))
                    expected_ids = f"--change-id={int(account[2])}:{int(account[3])}"
                    checks = {
                        "proot": "proot" in text,
                        "cwd_rootfs": _proc_cwd_matches_rootfs(proc, Path(record["rootfs"])),
                        "guest_ids": expected_ids in argv,
                        "guest_env": "/usr/bin/env" in text,
                        "marker_argv": marker_token in text,
                        "login_bash": "/bin/bash --login" in text,
                    }
                    evidence["profile_checks"] = checks
                    evidence["profile_signature_match"] = all(checks.values())
                except (OSError, ValueError, IndexError, StopIteration):
                    evidence["profile_checks"] = {"lookup": False}
                    evidence["profile_signature_match"] = False
    return evidence


def inspect_recovery(state_dir: str | os.PathLike[str], session_id: str) -> dict[str, object]:
    """Read-only classification of one saved record; never signals or repairs."""
    try:
        record = show_session(state_dir, session_id, include_private=True)
    except SessionError as exc:
        safe_id = session_id if isinstance(session_id, str) and _SESSION_ID.fullmatch(session_id) else None
        return {"session_id": safe_id,
                "status": "blocked", "reason": str(exc), "action": "none",
                "read_only": True, "signal_allowed": False}
    evidence = _recovery_evidence(record)
    verified = bool(record["ownership"] == "ternuxx_verified")
    observation = evidence["process_entry"]
    reasons = (["recorded_process_identity_missing"] if record["pid"] <= 0 else [])
    reasons.extend(name for name in ("process_start_match", "session_group_match", "marker_visible",
                                     "profile_signature_match", "rootfs_identity_match", "launcher_identity_match")
                   if evidence.get(name) is False)
    return {"session_id": record["session_id"], "profile": record["profile"],
            "recorded_state": record["recorded_state"], "observed_state": record["state"],
            "ownership": record["ownership"], "process_identity_match": evidence["process_start_match"],
            "process_state": observation, "evidence": evidence, "uncertainty_reasons": reasons,
            "historical_start_failure_evidence": _historical_failure_evidence(record),
            "exit_code": record["last_exit_code"], "diagnostics": record["transitions"][-16:],
            "status": "owned_live" if verified else (
                "stopped" if record["recorded_state"] == "stopped" else "unverified"),
            "action": "preview_exact_stop" if verified else "retain_record_no_signal",
            "signal_allowed": False, "read_only": True}
