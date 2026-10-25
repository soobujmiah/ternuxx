#!/usr/bin/env python3
"""Identity-checked Native Termux PulseAudio service for Ternuxx."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time

OWNER = "ternuxx-native-pulseaudio-v1"
SERVER = "tcp:127.0.0.1:4713"
LISTEN = "127.0.0.1"
PORT = 4713
SCHEMA = 1
START_TIMEOUT = 12.0
_TCP_MODULE = re.compile(r"^\s*load-module\s+module-native-protocol-tcp(?:\s+.*)?$", re.I)
_LOAD_MODULE = re.compile(r"^\s*load-module\s+([^\s]+)", re.I)
_TERMUX_UNAVAILABLE_MODULES = {
    "module-console-kit", "module-systemd-login", "module-opensles-sink",
}


def _termux_audio_profile(source: str) -> str:
    """Drop desktop/system-bus modules and the obsolete OpenSL sink alias.

    Termux provides module-sles-sink (OpenSL_ES_sink); it does not provide
    module-opensles-sink or a system D-Bus service for ConsoleKit/systemd-login.
    """
    lines = source.splitlines()
    has_legacy_opensles = any(
        (match := _LOAD_MODULE.match(line))
        and match.group(1).lower() == "module-opensles-sink"
        for line in lines
    )
    kept = []
    for line in lines:
        match = _LOAD_MODULE.match(line)
        if match and match.group(1).lower() in _TERMUX_UNAVAILABLE_MODULES:
            continue
        if has_legacy_opensles and line.strip().lower() == "set-default-sink speaker":
            continue
        kept.append(line)
    return "\n".join(kept) + "\n"


class PulseError(RuntimeError):
    pass


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default))


def _native_paths() -> dict[str, Path]:
    prefix = _env_path("PREFIX", "/data/data/com.termux/files/usr")
    home = _env_path("HOME", str(Path.home()))
    state = _env_path("TERNUXX_STATE_DIR", str(home / ".local/share/ternuxx"))
    audio = state / "audio"
    return {
        "prefix": prefix, "home": home, "state": state, "audio": audio,
        "record": audio / "pulseaudio.json", "lock": audio / ".lifecycle.lock",
        "config": audio / "default.pa", "log": audio / "pulseaudio.log",
        "runtime": audio / "runtime", "source_config": prefix / "etc/pulse/default.pa",
        "cookie": home / ".config/pulse/cookie",
        "pulseaudio": prefix / "bin/pulseaudio", "pactl": prefix / "bin/pactl",
    }


def _require_native() -> None:
    if (not os.environ.get("TERMUX_VERSION")
            or os.environ.get("PREFIX") != "/data/data/com.termux/files/usr"):
        raise PulseError("Native PulseAudio lifecycle requires the Native Termux shell")


def _ensure_private_dir(path: Path, *, create: bool) -> None:
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077):
        raise PulseError(f"unsafe private audio state directory: {path}")


def _ensure_audio_dirs(paths: dict[str, Path]) -> None:
    state = paths["state"]
    audio = paths["audio"]
    if state.absolute() != state.resolve(strict=False):
        raise PulseError("Ternuxx state path contains a symbolic link")
    if not state.exists():
        state.mkdir(mode=0o700, parents=True)
    _ensure_private_dir(state, create=False)
    audio.mkdir(mode=0o700, exist_ok=True)
    _ensure_private_dir(audio, create=False)


class _Lock:
    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def __enter__(self):
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        self.fd = os.open(self.path, flags, 0o600)
        info = os.fstat(self.fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            os.close(self.fd)
            self.fd = None
            raise PulseError("PulseAudio lifecycle lock is unsafe")
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self.fd)
            self.fd = None
            raise PulseError("another PulseAudio lifecycle operation is in progress") from exc
        return self

    def __exit__(self, *_args):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)


def _read_private_file(path: Path, *, maximum: int) -> bytes:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or info.st_size > maximum):
        raise PulseError(f"unsafe private PulseAudio file: {path.name}")
    return path.read_bytes()


def _cookie(paths: dict[str, Path]) -> Path:
    config_dir = paths["cookie"].parent
    config_root = config_dir.parent
    for directory in (config_root, config_dir):
        try:
            info = directory.lstat()
        except FileNotFoundError:
            directory.mkdir(mode=0o700)
            info = directory.lstat()
        unsafe_mode = info.st_mode & (0o022 if directory == config_root else 0o077)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or unsafe_mode or directory.is_symlink()
                or directory.absolute() != directory.resolve(strict=False)):
            raise PulseError("Native PulseAudio cookie directory is unsafe")
    cookie = paths["cookie"]
    try:
        info = cookie.lstat()
    except FileNotFoundError:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(cookie, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as stream:
                stream.write(os.urandom(256))
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            raise
        info = cookie.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077):
        raise PulseError("unsafe private PulseAudio file: cookie")
    payload = _read_private_file(cookie, maximum=256)
    if len(payload) != 256:
        raise PulseError("PulseAudio cookie has an unexpected size")
    return cookie


def managed_config(source: str, cookie_path: str) -> str:
    """Build the Native Termux profile and replace its known loopback listener."""
    lines = _termux_audio_profile(source).splitlines()
    module_lines = [(index, line) for index, line in enumerate(lines)
                    if _TCP_MODULE.match(line)]
    secure = ("load-module module-native-protocol-tcp "
              f"listen={LISTEN} port={PORT} auth-anonymous=0 "
              f"auth-cookie-enabled=1 auth-cookie={cookie_path}")
    if len(module_lines) > 1:
        raise PulseError("multiple PulseAudio TCP protocol modules are configured; refusing ambiguous exposure")
    if module_lines:
        index, line = module_lines[0]
        try:
            tokens = shlex.split(line.strip())
        except ValueError as exc:
            raise PulseError("PulseAudio TCP module configuration is malformed") from exc
        args: dict[str, str] = {}
        for token in tokens[2:]:
            key, sep, value = token.partition("=")
            if not sep or key in args:
                raise PulseError("PulseAudio TCP module configuration has ambiguous arguments")
            args[key] = value
        expected = {"listen": LISTEN, "auth-ip-acl": LISTEN,
                    "auth-anonymous": "1", "port": str(PORT)}
        if args != expected:
            raise PulseError("existing PulseAudio TCP listener is not the known loopback-only profile; preserving it")
        lines[index] = secure
    else:
        lines.append(secure)
    return "\n".join(lines) + "\n"


def _write_config(paths: dict[str, Path]) -> None:
    source_path = paths["source_config"]
    source = _read_private_file(source_path, maximum=1024 * 1024).decode("utf-8")
    snippets = paths["prefix"] / "etc/pulse/default.pa.d"
    if snippets.exists() or snippets.is_symlink():
        info = snippets.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or snippets.is_symlink():
            raise PulseError("Native PulseAudio snippet directory is unsafe; configuration was preserved")
        for entry in snippets.iterdir():
            if entry.suffix != ".pa":
                continue
            if entry.is_symlink() or not entry.is_file():
                raise PulseError("Native PulseAudio snippet is not a regular file; configuration was preserved")
            snippet = _read_private_file(entry, maximum=1024 * 1024).decode("utf-8")
            if any(_TCP_MODULE.match(line) for line in snippet.splitlines()):
                raise PulseError("PulseAudio snippet contains another TCP listener; preserving all configuration")
    config = "# Generated by Ternuxx; source is the installed Native PulseAudio default.pa.\n"
    config += managed_config(source, str(_cookie(paths)))
    destination = paths["config"]
    if destination.exists() or destination.is_symlink():
        current = _read_private_file(destination, maximum=1024 * 1024).decode("utf-8")
        if not current.startswith("# Generated by Ternuxx; source is the installed Native PulseAudio default.pa.\n"):
            raise PulseError("audio config path contains an unrecognized file; it was preserved")
    fd, temporary = tempfile.mkstemp(prefix=".default.pa.", dir=paths["audio"])
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(config)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _proc(pid: int) -> dict[str, object] | None:
    root = Path("/proc") / str(pid)
    try:
        raw = (root / "stat").read_text()
        close = raw.rfind(")")
        fields = raw[close + 2:].split()
        ticks = fields[19]
        state = fields[0]
        pgrp = int(fields[2])
        sid = int(fields[3])
        uid = (root / "status").read_text().split("Uid:", 1)[1].splitlines()[0].split()[0]
        argv = (root / "cmdline").read_bytes().split(b"\0")
        command = [value.decode(errors="replace") for value in argv if value]
        environ = (root / "environ").read_bytes().split(b"\0")
        marker = any(value == f"TERNUXX_AUDIO_OWNER={OWNER}".encode() for value in environ)
        executable = os.readlink(root / "exe")
    except (OSError, ValueError, IndexError, PermissionError):
        return None
    return {"pid": pid, "ticks": ticks, "state": state, "pgid": pgrp, "sid": sid,
            "uid": int(uid), "argv": command, "marker": marker, "exe": executable}


def _record_read(path: Path) -> dict[str, object] | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or info.st_size > 16384):
        raise PulseError("PulseAudio owner record is unsafe; state was preserved")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PulseError("PulseAudio owner record is malformed; state was preserved") from exc
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("owner") != OWNER or not isinstance(data.get("pid"), int)
            or not isinstance(data.get("start_ticks"), str)
            or not isinstance(data.get("process_group"), int)):
        raise PulseError("PulseAudio owner record has an unsupported identity; state was preserved")
    return data


def _record_write(path: Path, data: dict[str, object]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".pulseaudio.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _matches(record: dict[str, object], paths: dict[str, Path]) -> dict[str, object] | None:
    process = _proc(record["pid"])
    if not process:
        return None
    command = process["argv"]
    if (process["uid"] != os.getuid() or process["ticks"] != record["start_ticks"]
            or process["pgid"] != record["process_group"] or process["sid"] != record["process_group"]
            or not process["marker"] or process["exe"] != str(paths["pulseaudio"])
            or not command or command[0] != str(paths["pulseaudio"])
            or "--daemonize=no" not in command or "--exit-idle-time=-1" not in command
            or "-n" not in command or str(paths["config"]) not in command
            or process["state"] in {"Z", "X"}):
        return None
    return process


def _pulse_info(paths: dict[str, Path], *, timeout: float = 1.0) -> dict[str, str] | None:
    env = dict(os.environ)
    env.update({"PULSE_SERVER": SERVER, "PULSE_COOKIE": str(paths["cookie"])})
    try:
        result = subprocess.run([str(paths["pactl"]), "--server", SERVER, "info"],
                                capture_output=True, text=True, timeout=timeout,
                                check=False, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition(":")
        if sep and key in {"Server Name", "Default Sink"}:
            value = value.strip()
            if re.fullmatch(r"[A-Za-z0-9_.:+-]{1,128}", value):
                values[key] = value
    return values if values.get("Server Name") and values.get("Default Sink") else None


def _existing_pulseaudio(paths: dict[str, Path]) -> list[int]:
    found: list[int] = []
    for child in Path("/proc").iterdir():
        if not child.name.isdigit():
            continue
        process = _proc(int(child.name))
        if process and process["uid"] == os.getuid() and process["exe"] == str(paths["pulseaudio"]):
            found.append(int(child.name))
    return found


def status() -> dict[str, object]:
    _require_native()
    paths = _native_paths()
    record = _record_read(paths["record"])
    if record:
        owned = _matches(record, paths)
        if owned:
            info = _pulse_info(paths)
            return {"owner": "ternuxx", "state": "running" if info else "degraded",
                    "server": SERVER, "default_sink": info.get("Default Sink") if info else None,
                    "identity": "matched", "read_only": True}
        if _proc(record["pid"]) is None:
            return {"owner": "ternuxx", "state": "stale", "server": SERVER,
                    "identity": "recorded-process-absent", "read_only": True}
        return {"owner": "unknown", "state": "unsafe", "server": SERVER,
                "identity": "record-does-not-match-live-process", "read_only": True}
    if _pulse_info(paths):
        return {"owner": "external", "state": "running", "server": SERVER,
                "identity": "no-ternuxx-owner-record", "read_only": True}
    return {"owner": "ternuxx", "state": "stopped", "server": SERVER,
            "identity": "no-responsive-loopback-server", "read_only": True}


def start() -> dict[str, object]:
    _require_native()
    paths = _native_paths()
    _ensure_audio_dirs(paths)
    with _Lock(paths["lock"]):
        record = _record_read(paths["record"])
        if record:
            owned = _matches(record, paths)
            if owned:
                info = _pulse_info(paths)
                if not info:
                    raise PulseError("Ternuxx PulseAudio process is live but its endpoint is not ready; refusing a duplicate")
                return {"owner": "ternuxx", "state": "running", "server": SERVER,
                        "default_sink": info["Default Sink"], "changed": False}
            if _proc(record["pid"]) is not None:
                raise PulseError("PulseAudio owner record conflicts with a live PID; process and state were preserved")
        external = _existing_pulseaudio(paths)
        if external:
            raise PulseError("a Native PulseAudio process exists without a matching Ternuxx record; refusing to start or stop it")
        if _pulse_info(paths):
            raise PulseError("the Native PulseAudio endpoint is already serving without a Ternuxx owner record; refusing to adopt it")
        if not paths["pulseaudio"].is_file() or not os.access(paths["pulseaudio"], os.X_OK):
            raise PulseError("Native pulseaudio executable is unavailable")
        if not paths["pactl"].is_file() or not os.access(paths["pactl"], os.X_OK):
            raise PulseError("Native pactl client is unavailable")
        _cookie(paths)
        _write_config(paths)
        paths["runtime"].mkdir(mode=0o700, exist_ok=True)
        _ensure_private_dir(paths["runtime"], create=False)
        if paths["log"].exists() or paths["log"].is_symlink():
            log_info = paths["log"].lstat()
            if (not stat.S_ISREG(log_info.st_mode) or log_info.st_uid != os.getuid()
                    or log_info.st_mode & 0o077):
                raise PulseError("PulseAudio log path is unsafe; existing file was preserved")
        log_flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            log_flags |= os.O_NOFOLLOW
        log_fd = os.open(paths["log"], log_flags, 0o600)
        os.fchmod(log_fd, 0o600)
        env = dict(os.environ)
        env.update({"HOME": str(paths["home"]), "PREFIX": str(paths["prefix"]),
                    "PATH": f"{paths['prefix'] / 'bin'}:{env.get('PATH', '')}",
                    "XDG_RUNTIME_DIR": str(paths["runtime"]),
                    "TERNUXX_AUDIO_OWNER": OWNER})
        env.pop("PULSE_SERVER", None)
        env.pop("PULSE_COOKIE", None)
        env.pop("PULSE_RUNTIME_PATH", None)
        # The server is a headless Native Termux service; do not inherit an
        # X11 or session-bus context that triggers desktop-only module autoload.
        env.pop("DISPLAY", None)
        env.pop("DBUS_SESSION_BUS_ADDRESS", None)
        env.pop("DBUS_SYSTEM_BUS_ADDRESS", None)
        command = [str(paths["pulseaudio"]), "--daemonize=no", "--exit-idle-time=-1",
                   "-n", "--file", str(paths["config"])]
        try:
            with os.fdopen(log_fd, "ab", closefd=True) as log:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=subprocess.STDOUT,
                                         env=env, close_fds=True, start_new_session=True)
        except OSError as exc:
            raise PulseError(f"could not start Native PulseAudio: {exc}") from exc
        process = None
        for _ in range(30):
            process = _proc(child.pid)
            if process and process["marker"] and process["pgid"] == child.pid and process["sid"] == child.pid:
                break
            if child.poll() is not None:
                raise PulseError(f"Native PulseAudio exited during startup (exit {child.returncode}); see the private audio log")
            time.sleep(0.05)
        if not process or not process["marker"] or process["pgid"] != child.pid or process["sid"] != child.pid:
            child.terminate()
            raise PulseError("Native PulseAudio process identity could not be verified; startup was stopped")
        record = {"schema": SCHEMA, "owner": OWNER, "pid": child.pid,
                  "start_ticks": str(process["ticks"]), "process_group": child.pid,
                  "server": SERVER, "config": str(paths["config"]), "status": "starting",
                  "started_at": int(time.time())}
        try:
            _record_write(paths["record"], record)
        except OSError:
            try:
                if _matches(record, paths):
                    os.kill(child.pid, signal.SIGTERM)
            except OSError:
                pass
            raise
        deadline = time.monotonic() + START_TIMEOUT
        info = None
        while time.monotonic() < deadline:
            if child.poll() is not None:
                record["status"] = "failed"
                _record_write(paths["record"], record)
                raise PulseError(f"Native PulseAudio exited during readiness (exit {child.returncode}); see the private audio log")
            info = _pulse_info(paths, timeout=0.5)
            if info:
                record["status"] = "running"
                record["default_sink"] = info["Default Sink"]
                _record_write(paths["record"], record)
                return {"owner": "ternuxx", "state": "running", "server": SERVER,
                        "default_sink": info["Default Sink"], "changed": True}
            time.sleep(0.2)
        try:
            current = _matches(record, paths)
            if current:
                os.kill(child.pid, signal.SIGTERM)
        except OSError:
            pass
        record["status"] = "failed"
        _record_write(paths["record"], record)
        raise PulseError("Native PulseAudio did not pass authenticated loopback readiness within 12 seconds; inspect the private audio log")


def stop() -> dict[str, object]:
    _require_native()
    paths = _native_paths()
    _ensure_audio_dirs(paths)
    with _Lock(paths["lock"]):
        record = _record_read(paths["record"])
        if not record:
            return {"owner": "unknown", "state": "unchanged", "server": SERVER,
                    "changed": False, "reason": "no Ternuxx owner record; no process was signaled"}
        process = _matches(record, paths)
        if not process:
            if _proc(record["pid"]) is not None:
                raise PulseError("PulseAudio owner identity is ambiguous; process was not signaled")
            record["status"] = "stopped"
            _record_write(paths["record"], record)
            return {"owner": "ternuxx", "state": "stopped", "changed": False,
                    "reason": "recorded process is absent; unrelated runtime artifacts were preserved"}
        record["status"] = "stopping"
        _record_write(paths["record"], record)
        os.kill(int(record["pid"]), signal.SIGTERM)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if _matches(record, paths) is None:
                record["status"] = "stopped"
                _record_write(paths["record"], record)
                return {"owner": "ternuxx", "state": "stopped", "changed": True}
            time.sleep(0.1)
        raise PulseError("verified Native PulseAudio process did not stop; state retained for recovery")


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in {"status", "start", "ensure", "stop", "restart"}:
        print("usage: pulse_lifecycle.py status|start|ensure|stop|restart", file=sys.stderr)
        return 2
    try:
        action = argv[0]
        if action == "status":
            result = status()
        elif action in {"start", "ensure"}:
            result = start()
        elif action == "stop":
            result = stop()
        else:
            stop()
            result = start()
        print(json.dumps({"command": "audio", **result}, sort_keys=True))
        return 0
    except (PulseError, OSError) as exc:
        print(json.dumps({"command": "audio", "state": "error", "message": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
