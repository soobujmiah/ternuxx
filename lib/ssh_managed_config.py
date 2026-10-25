#!/usr/bin/env python3
"""Preview-first, loopback-only configuration for Ternuxx's OpenSSH service."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import tempfile
from typing import Callable

import operation_journal

CONFIG_RELATIVE = Path(".config/ternuxx/sshd_recovery.conf")
AUTHORIZED_KEYS_RELATIVE = ".ssh/ternuxx-keys/authorized_keys"
SERVICE_ID = "ternuxx-sshd"
PORT = 8023


class ManagedSshConfigError(RuntimeError):
    pass


def _regular(path: Path, uid: int, *, private: bool = False, executable: bool = False) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ManagedSshConfigError(f"required SSH path is unavailable: {path.name}") from exc
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_uid != uid
            or (private and stat.S_IMODE(info.st_mode) != 0o600)
            or (executable and not info.st_mode & 0o100)):
        raise ManagedSshConfigError(f"SSH file identity or permissions are unsafe: {path.name}")
    return info


def _directories(home: Path, uid: int) -> None:
    if not home.is_absolute() or ".." in home.parts:
        raise ManagedSshConfigError("Native HOME path is invalid")
    current = Path(home.anchor)
    for part in home.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except OSError as exc:
            raise ManagedSshConfigError("Native HOME path is unavailable") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ManagedSshConfigError("Native HOME path contains a non-directory or symbolic link")
    home_info = home.lstat()
    if home_info.st_uid != uid:
        raise ManagedSshConfigError("Native HOME ownership is unverified")


def _host_key(prefix: Path, uid: int) -> Path:
    key = prefix / "etc/ssh/ssh_host_ed25519_key"
    _regular(key, uid, private=True)
    public = Path(str(key) + ".pub")
    _regular(public, uid)
    return key


def _candidate(prefix: Path, home: Path, username: str, host_key: Path) -> bytes:
    values = [str(prefix / "bin/sshd"), str(host_key), username]
    if any(any(ch.isspace() for ch in value) or "#" in value for value in values):
        raise ManagedSshConfigError("SSH paths or account name cannot be represented safely")
    lines = [
        "Port 8023",
        "AddressFamily inet",
        "ListenAddress 127.0.0.1",
        f"HostKey {host_key}",
        "PermitRootLogin no",
        "PermitEmptyPasswords no",
        "PasswordAuthentication no",
        "KbdInteractiveAuthentication no",
        "PubkeyAuthentication yes",
        "AuthenticationMethods publickey",
        f"AllowUsers {username}",
        "AuthorizedKeysFile .ssh/ternuxx-keys/authorized_keys",
        "StrictModes yes",
        "AllowTcpForwarding no",
        "AllowAgentForwarding no",
        "X11Forwarding no",
        "PermitTunnel no",
        "GatewayPorts no",
        "PermitTTY yes",
        "PermitUserEnvironment no",
        "UseDNS no",
        "MaxAuthTries 3",
        "MaxSessions 5",
        "LoginGraceTime 30",
        "LogLevel VERBOSE",
        "Subsystem sftp internal-sftp",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _effective_policy(config_bytes: bytes, prefix: Path, username: str,
                      runner: Callable[..., subprocess.CompletedProcess[str]]) -> dict[str, str]:
    sshd = prefix / "bin/sshd"
    _regular(sshd, os.getuid(), executable=True)
    temp_root = prefix / "tmp"
    try:
        info = temp_root.lstat()
    except OSError as exc:
        raise ManagedSshConfigError("Native Termux temporary directory is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ManagedSshConfigError("Native Termux temporary directory identity is unsafe")
    try:
        with tempfile.TemporaryDirectory(prefix="ternuxx-sshd-check-", dir=temp_root) as temporary:
            config = Path(temporary) / "sshd_config"
            fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(config_bytes)
            syntax = runner([str(sshd), "-t", "-f", str(config)], capture_output=True,
                            text=True, timeout=5, check=False)
            if syntax.returncode != 0:
                raise ManagedSshConfigError("generated Ternuxx SSH configuration failed sshd -t")
            result = runner([str(sshd), "-T", "-f", str(config), "-C",
                             f"user={username},host=localhost,addr=127.0.0.1"],
                            capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ManagedSshConfigError("OpenSSH configuration verification could not run") from exc
    if result.returncode != 0:
        raise ManagedSshConfigError("generated Ternuxx SSH configuration failed effective-policy verification")
    selected = {}
    required = {"port": "8023", "addressfamily": "inet", "listenaddress": "127.0.0.1:8023",
                "passwordauthentication": "no", "kbdinteractiveauthentication": "no",
                "pubkeyauthentication": "yes", "authenticationmethods": "publickey",
                "permitrootlogin": "no", "authorizedkeysfile": ".ssh/ternuxx-keys/authorized_keys"}
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].lower() in required:
            selected[parts[0].lower()] = parts[1]
    if any(selected.get(key) != value for key, value in required.items()):
        raise ManagedSshConfigError("effective SSH policy did not match the fixed loopback/public-key policy")
    return selected


def _port_available(probe: Callable[..., object] = socket.create_connection) -> bool:
    try:
        connection = probe(("127.0.0.1", PORT), timeout=0.25)
    except OSError as exc:
        if exc.errno in {111, 61, 10061}:  # ECONNREFUSED on Linux, Darwin, Windows
            return True
        raise ManagedSshConfigError("could not establish that loopback port 8023 is free") from exc
    try:
        connection.close()
    except Exception:
        pass
    return False


def _core(prefix: Path, home: Path, uid: int, runner, probe) -> tuple[dict[str, object], bytes]:
    _directories(home, uid)
    try:
        username = pwd.getpwuid(uid).pw_name
    except KeyError as exc:
        raise ManagedSshConfigError("Native account name could not be verified") from exc
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username):
        raise ManagedSshConfigError("Native account name is invalid for SSH policy")
    ssh_dir = home / ".ssh"
    ssh_info = ssh_dir.lstat()
    if (stat.S_ISLNK(ssh_info.st_mode) or not stat.S_ISDIR(ssh_info.st_mode)
            or ssh_info.st_uid != uid or stat.S_IMODE(ssh_info.st_mode) & 0o077):
        raise ManagedSshConfigError("Native .ssh directory must be owned by the account and mode 0700")
    key_dir = ssh_dir / "ternuxx-keys"
    try:
        key_dir_info = key_dir.lstat()
    except FileNotFoundError:
        key_dir_state: object = "absent"
    except OSError as exc:
        raise ManagedSshConfigError("Ternuxx SSH key directory cannot be inspected") from exc
    else:
        if (stat.S_ISLNK(key_dir_info.st_mode) or not stat.S_ISDIR(key_dir_info.st_mode)
                or key_dir_info.st_uid != uid or stat.S_IMODE(key_dir_info.st_mode) & 0o077):
            raise ManagedSshConfigError("Ternuxx SSH key directory identity is unsafe")
        key_dir_state = (key_dir_info.st_dev, key_dir_info.st_ino, stat.S_IMODE(key_dir_info.st_mode))
    host_key = _host_key(prefix, uid)
    config = home / CONFIG_RELATIVE
    desired = _candidate(prefix, home, username, host_key)
    parent_states = []
    current = home
    for component in (".config", "ternuxx"):
        current /= component
        try:
            info = current.lstat()
        except FileNotFoundError:
            parent_states.append((str(current), "absent"))
        except OSError as exc:
            raise ManagedSshConfigError("Ternuxx SSH configuration directory is unsafe") from exc
        else:
            if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != uid or stat.S_IMODE(info.st_mode) & 0o077):
                raise ManagedSshConfigError("Ternuxx SSH configuration directory identity is unsafe")
            parent_states.append((str(current), info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode)))
    try:
        metadata = config.lstat()
    except FileNotFoundError:
        before = None
        changed = True
    except OSError as exc:
        raise ManagedSshConfigError("Ternuxx SSH configuration cannot be inspected") from exc
    else:
        if (stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != uid or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise ManagedSshConfigError("existing Ternuxx SSH configuration identity is unsafe")
        if metadata.st_size > 64 * 1024:
            raise ManagedSshConfigError("existing Ternuxx SSH configuration is too large")
        before = config.read_bytes()
        if before != desired:
            raise ManagedSshConfigError("an existing Ternuxx SSH configuration differs; automatic overwrite is refused")
        changed = False
    available = _port_available(probe)
    if not available and changed:
        raise ManagedSshConfigError("loopback port 8023 is already accepting connections")
    policy = _effective_policy(desired, prefix, username, runner)
    core: dict[str, object] = {
        "service_id": SERVICE_ID, "action": "create_loopback_publickey_config",
        "target": str(config), "target_state": "absent" if before is None else "verified-current",
        "before_sha256": hashlib.sha256(before).hexdigest() if before is not None else None,
        "after_sha256": hashlib.sha256(desired).hexdigest(), "mode": "0600",
        "username": username, "authorized_keys": AUTHORIZED_KEYS_RELATIVE,
        "host_key": str(host_key), "host_key_sha256": hashlib.sha256(Path(str(host_key) + ".pub").read_bytes()).hexdigest(),
        "parent_states": parent_states, "key_directory_state": key_dir_state,
        "port_8023_available": available,
        "effective_policy": policy, "sshd_sha256": hashlib.sha256((prefix / "bin/sshd").read_bytes()).hexdigest(),
        "changed": changed,
    }
    return core, desired


def preview(*, prefix: str | os.PathLike[str], home: str | os.PathLike[str], uid: int | None = None,
            runner=subprocess.run, port_probe=socket.create_connection) -> dict[str, object]:
    expected_uid = os.getuid() if uid is None else uid
    core, desired = _core(Path(prefix), Path(home), expected_uid, runner, port_probe)
    plan_id = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**core, "plan_id": plan_id if core["changed"] else None,
            "requires_confirmation": bool(core["changed"]), "read_only": True,
            "diff": ["Create a dedicated mode-0600 config for loopback 127.0.0.1:8023; password auth disabled.",
                     "Use only the Ternuxx key file under .ssh/ternuxx-keys; leave shared .ssh/authorized_keys untouched.",
                     "Do not modify external Native SSH configuration."],
            "impact": "Creates only the fixed Ternuxx SSH configuration. It does not install/start a service or change the external Native SSH configuration.",
            "candidate_sha256": hashlib.sha256(desired).hexdigest()}


def apply(*, prefix: str | os.PathLike[str], home: str | os.PathLike[str], state_dir: str | os.PathLike[str],
          uid: int | None = None, confirmed: bool, plan_id: str | None,
          runner=subprocess.run, port_probe=socket.create_connection) -> dict[str, object]:
    if confirmed is not True:
        raise ManagedSshConfigError("explicit confirmation is required")
    expected_uid = os.getuid() if uid is None else uid
    current = preview(prefix=prefix, home=home, uid=expected_uid, runner=runner, port_probe=port_probe)
    if (not current["requires_confirmation"] or not isinstance(plan_id, str)
            or plan_id != current["plan_id"]):
        raise ManagedSshConfigError("fresh exact SSH configuration preview and plan ID are required")
    home_path = Path(home)
    config = home_path / CONFIG_RELATIVE
    parent = config.parent
    created_dirs: list[Path] = []
    config_identity: tuple[int, int] | None = None
    key_dir = home_path / ".ssh/ternuxx-keys"
    key_dir_created = False
    operation_id: str | None = None
    lock = home_path / ".ssh/.ternuxx-sshd-config.lock"
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError as exc:
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise ManagedSshConfigError("could not acquire the private SSH configuration lock") from exc
    try:
        lock_info = os.fstat(lock_fd)
        if (not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != expected_uid
                or stat.S_IMODE(lock_info.st_mode) != 0o600):
            raise ManagedSshConfigError("Ternuxx SSH config lock identity is unsafe")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = preview(prefix=prefix, home=home, uid=expected_uid, runner=runner, port_probe=port_probe)
        if locked["plan_id"] != plan_id or not locked["requires_confirmation"]:
            raise ManagedSshConfigError("SSH configuration state changed after preview")
        current_dir = home_path
        for component in (".config", "ternuxx"):
            current_dir /= component
            try:
                current_dir.mkdir(mode=0o700)
                created_dirs.append(current_dir)
            except FileExistsError:
                info = current_dir.lstat()
                if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
                        or info.st_uid != expected_uid or stat.S_IMODE(info.st_mode) & 0o077):
                    raise ManagedSshConfigError("Ternuxx SSH directory changed after preview")
        operation_id = operation_journal.begin(
            state_dir, "service.deploy", "configure loopback Ternuxx SSH", home_dir=home_path)
        try:
            try:
                key_dir.mkdir(mode=0o700)
                key_dir_created = True
            except FileExistsError:
                key_info = key_dir.lstat()
                if (stat.S_ISLNK(key_info.st_mode) or not stat.S_ISDIR(key_info.st_mode)
                        or key_info.st_uid != expected_uid or stat.S_IMODE(key_info.st_mode) & 0o077):
                    raise ManagedSshConfigError("Ternuxx SSH key directory changed after preview")
            fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            info = os.fstat(fd)
            config_identity = (info.st_dev, info.st_ino)
            with os.fdopen(fd, "wb") as stream:
                stream.write(_candidate(Path(prefix), home_path, str(current["username"]), Path(str(current["host_key"]))))
                stream.flush()
                os.fsync(stream.fileno())
            effective = _effective_policy(config.read_bytes(), Path(prefix), str(current["username"]), runner)
            if effective != current["effective_policy"]:
                raise ManagedSshConfigError("published SSH config policy differs from its preview")
            operation_journal.update(state_dir, operation_id, "complete",
                                     "loopback public-key SSH policy configured; service not started", home_dir=home_path)
            return {"status": "configured", "service_id": SERVICE_ID, "operation_id": operation_id,
                    "config": str(config), "config_sha256": current["after_sha256"], "mode": "0600",
                    "authorized_keys": AUTHORIZED_KEYS_RELATIVE, "effective_policy": effective,
                    "service_started": False, "read_only": False}
        except BaseException:
            try:
                if config_identity is not None:
                    check = config.lstat()
                    if ((check.st_dev, check.st_ino) == config_identity and stat.S_ISREG(check.st_mode)):
                        config.unlink()
            except OSError:
                pass
            if key_dir_created:
                try:
                    key_dir.rmdir()
                except OSError:
                    pass
            for directory in reversed(created_dirs):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            try:
                operation_journal.update(state_dir, operation_id, "failed",
                                         "SSH config publication failed; owned partial files rolled back", home_dir=home_path)
            except Exception:
                pass
            raise
    except OSError as exc:
        raise ManagedSshConfigError("could not safely publish the Ternuxx SSH configuration") from exc
    finally:
        os.close(lock_fd)
