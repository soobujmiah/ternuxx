"""Read-only, redacted inventory of Native Termux authorized SSH keys."""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import re
import stat
import struct

_MAX_FILE_BYTES = 256 * 1024
_MAX_LINES = 1000
_MAX_COMMENT = 96
_KEY_TYPE = re.compile(r"^(?:ssh-(?:ed25519|rsa|dss)|ecdsa-sha2-[A-Za-z0-9-]+|sk-(?:ssh-ed25519|ecdsa-sha2-[A-Za-z0-9-]+)@openssh\.com)$")


def _safe_comment(value: str) -> str:
    return "".join(ch if ch.isprintable() else " " for ch in value)[:_MAX_COMMENT].strip()


def _parse_line(line: str) -> dict[str, str] | None:
    """Parse one authorized_keys record without invoking a shell or sshd."""
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    # authorized_keys options may contain quoted spaces; shlex keeps them in
    # one token and never executes the text.
    import shlex
    try:
        fields = shlex.split(line, comments=False, posix=True)
    except ValueError:
        return {"status": "invalid", "key_type": "unknown", "fingerprint": "", "label": "Invalid entry"}
    # OpenSSH permits one leading options token; the key type must be the
    # first or second token, never text in a comment or later malformed data.
    for index in range(min(2, len(fields) - 1)):
        key_type = fields[index]
        if not _KEY_TYPE.fullmatch(key_type):
            continue
        encoded = fields[index + 1]
        try:
            blob = base64.b64decode(encoded.encode("ascii"), validate=True)
            if len(blob) < 4:
                continue
            name_length = struct.unpack(">I", blob[:4])[0]
            if name_length < 1 or name_length > len(blob) - 4:
                continue
            blob_type = blob[4:4 + name_length].decode("ascii")
            if blob_type != key_type:
                continue
        except (UnicodeEncodeError, ValueError, struct.error):
            continue
        digest = base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
        return {"status": "valid", "key_type": key_type,
                "fingerprint": "SHA256:" + digest,
                "label": _safe_comment(" ".join(fields[index + 2:])) or "No comment"}
    return {"status": "invalid", "key_type": "unknown", "fingerprint": "", "label": "Invalid entry"}


def list_authorized_keys(*, home: str | os.PathLike[str], uid: int | None = None,
                         relative_path: str = ".ssh/authorized_keys") -> dict[str, object]:
    """Read one allowlisted authorized_keys path; fail closed on links."""
    expected_uid = os.getuid() if uid is None else uid
    home_path = Path(home)
    if not home_path.is_absolute() or ".." in home_path.parts:
        return {"status": "unavailable", "reason": "invalid_home", "keys": [], "invalid_entries": 0}
    allowed = {".ssh/authorized_keys", ".ssh/ternuxx-keys/authorized_keys"}
    if relative_path not in allowed:
        return {"status": "unavailable", "reason": "authorized_keys_path_not_allowlisted", "keys": [], "invalid_entries": 0}
    ssh_dir = home_path / ".ssh"
    path = home_path / relative_path
    try:
        home_stat = home_path.lstat()
        dir_stat = ssh_dir.lstat()
        if (stat.S_ISLNK(home_stat.st_mode) or not stat.S_ISDIR(home_stat.st_mode)
                or home_stat.st_uid != expected_uid):
            return {"status": "unsafe_path", "reason": "home_identity_unverified", "keys": [], "invalid_entries": 0}
        if stat.S_ISLNK(dir_stat.st_mode) or not stat.S_ISDIR(dir_stat.st_mode) or dir_stat.st_uid != expected_uid:
            return {"status": "unsafe_path", "reason": "ssh_directory_untrusted", "keys": [], "invalid_entries": 0}
        if relative_path == ".ssh/ternuxx-keys/authorized_keys":
            key_dir = home_path / ".ssh/ternuxx-keys"
            key_info = key_dir.lstat()
            if (stat.S_ISLNK(key_info.st_mode) or not stat.S_ISDIR(key_info.st_mode)
                    or key_info.st_uid != expected_uid or stat.S_IMODE(key_info.st_mode) & 0o077):
                return {"status": "unsafe_path", "reason": "ternuxx_key_directory_untrusted", "keys": [], "invalid_entries": 0}
        file_stat = path.lstat()
    except FileNotFoundError:
        return {"status": "missing", "reason": "authorized_keys_not_present", "keys": [], "invalid_entries": 0}
    except OSError:
        return {"status": "unavailable", "reason": "authorized_keys_unreadable", "keys": [], "invalid_entries": 0}
    if (stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid != expected_uid):
        return {"status": "unsafe_path", "reason": "authorized_keys_identity_unverified", "keys": [], "invalid_entries": 0}
    if file_stat.st_size > _MAX_FILE_BYTES:
        return {"status": "too_large", "reason": "authorized_keys_exceeds_limit", "keys": [], "invalid_entries": 0}
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_ino != file_stat.st_ino
                    or opened.st_dev != file_stat.st_dev or opened.st_uid != expected_uid
                    or opened.st_size > _MAX_FILE_BYTES):
                return {"status": "unsafe_path", "reason": "authorized_keys_changed_during_read", "keys": [], "invalid_entries": 0}
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(_MAX_FILE_BYTES + 1)
        finally:
            os.close(fd)
        if len(raw) > _MAX_FILE_BYTES:
            return {"status": "too_large", "reason": "authorized_keys_exceeds_limit", "keys": [], "invalid_entries": 0}
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeError):
        return {"status": "unavailable", "reason": "authorized_keys_unreadable", "keys": [], "invalid_entries": 0}
    lines = text.splitlines()
    if len(lines) > _MAX_LINES:
        return {"status": "too_many_entries", "reason": "authorized_keys_entry_limit_exceeded", "keys": [], "invalid_entries": 0}
    keys: list[dict[str, str]] = []
    invalid = 0
    for line in lines:
        parsed = _parse_line(line)
        if parsed is None:
            continue
        if parsed["status"] != "valid":
            invalid += 1
            continue
        keys.append({"key_type": parsed["key_type"], "fingerprint": parsed["fingerprint"],
                     "label": parsed["label"]})
    return {"status": "available", "reason": "inventory_read_only", "keys": keys,
            "key_count": len(keys), "invalid_entries": invalid,
            "permissions": oct(stat.S_IMODE(file_stat.st_mode))}


def list_managed_authorized_keys(
    *, home: str | os.PathLike[str], uid: int | None = None,
    which=shutil.which, runner=subprocess.run,
) -> dict[str, object]:
    """Verify the live managed sshd key path before listing its fixed file."""
    expected_uid = os.getuid() if uid is None else uid
    home_path = Path(home)
    config = home_path / ".config/ternuxx/sshd_recovery.conf"
    sshd = which("sshd")
    if not sshd:
        return {"status": "unavailable", "reason": "sshd_not_found", "keys": [], "invalid_entries": 0}
    try:
        config_stat = config.lstat()
        if (stat.S_ISLNK(config_stat.st_mode) or not stat.S_ISREG(config_stat.st_mode)
                or config_stat.st_uid != expected_uid):
            return {"status": "unsafe_path", "reason": "managed_ssh_config_untrusted", "keys": [], "invalid_entries": 0}
        username = pwd.getpwuid(expected_uid).pw_name
        result = runner([sshd, "-T", "-f", str(config), "-C",
                         f"user={username},host=localhost,addr=127.0.0.1"],
                        capture_output=True, text=True, timeout=5, check=False,
                        env={"HOME": str(home_path), "LANG": "C", "LC_ALL": "C",
                             "PATH": os.environ.get("PATH", "")})
    except (OSError, KeyError, subprocess.TimeoutExpired):
        return {"status": "unavailable", "reason": "managed_ssh_config_unreadable", "keys": [], "invalid_entries": 0}
    if result.returncode != 0:
        return {"status": "unavailable", "reason": "managed_ssh_config_invalid", "keys": [], "invalid_entries": 0}
    effective_paths: list[str] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0].casefold() == "authorizedkeysfile":
            effective_paths.extend(fields[1:])
    if len(effective_paths) != 1 or effective_paths[0] != ".ssh/ternuxx-keys/authorized_keys":
        return {"status": "unsupported_path", "reason": "managed_authorized_keys_path_not_ternuxx_owned",
                "keys": [], "invalid_entries": 0}
    relative_path = effective_paths[0]
    inventory = list_authorized_keys(home=home_path, uid=expected_uid, relative_path=relative_path)
    inventory["authorized_keys_path_verified"] = True
    inventory["authorized_keys_file"] = relative_path
    inventory["service_id"] = "ternuxx-sshd"
    return inventory
