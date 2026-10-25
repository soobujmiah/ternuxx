"""Preview-first generation of a Native Termux client key for managed SSH recovery."""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

import ssh_key_inventory


_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_KEY_DIR = "ternuxx-keys"
_LOCK = ".ternuxx-client-key.lock"


class ClientKeyError(RuntimeError):
    pass


def _paths(home: str | os.PathLike[str], uid: int, name: str) -> tuple[Path, Path, Path | None]:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ClientKeyError("key name must use 1-32 lowercase letters, numbers, hyphens, or underscores")
    root = Path(home)
    if not root.is_absolute() or ".." in root.parts:
        raise ClientKeyError("Native home path is invalid")
    try:
        root_stat = root.lstat()
        ssh_dir = root / ".ssh"
        ssh_stat = ssh_dir.lstat()
    except OSError as exc:
        raise ClientKeyError("the existing Native .ssh directory is unavailable") from exc
    if (stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != uid):
        raise ClientKeyError("Native home ownership or path is unverified")
    if (stat.S_ISLNK(ssh_stat.st_mode) or not stat.S_ISDIR(ssh_stat.st_mode)
            or ssh_stat.st_uid != uid or stat.S_IMODE(ssh_stat.st_mode) & 0o077):
        raise ClientKeyError("Native .ssh directory must be owned by this account and private")
    key_dir = ssh_dir / _KEY_DIR
    try:
        key_stat = key_dir.lstat()
    except FileNotFoundError:
        key_stat = None
    except OSError as exc:
        raise ClientKeyError("Native SSH key directory cannot be inspected safely") from exc
    if key_stat is not None and (
            stat.S_ISLNK(key_stat.st_mode) or not stat.S_ISDIR(key_stat.st_mode)
            or key_stat.st_uid != uid or stat.S_IMODE(key_stat.st_mode) & 0o077):
        raise ClientKeyError("Native Ternuxx key directory must be owned by this account and mode 0700")
    target = key_dir / name
    return ssh_dir, target, key_dir if key_stat is not None else None


def _public_fingerprint(path: Path, uid: int) -> tuple[str, str, str] | None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_size > 16_384):
                return None
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw_bytes = stream.read(16_385)
        finally:
            os.close(fd)
        if len(raw_bytes) > 16_384:
            return None
        raw = raw_bytes.decode("utf-8").strip()
    except (OSError, UnicodeError):
        return None
    parsed = ssh_key_inventory._parse_line(raw)
    if not parsed or parsed.get("status") != "valid":
        return None
    try:
        result = subprocess.run(["ssh-keygen", "-lf", "-"], input=raw + "\n",
                                capture_output=True, text=True, timeout=3, check=False,
                                env={"HOME": os.environ.get("HOME", ""), "LANG": "C",
                                     "LC_ALL": "C", "PATH": os.environ.get("PATH", "")})
    except (OSError, subprocess.TimeoutExpired):
        return None
    fields = result.stdout.split()
    if result.returncode != 0 or len(fields) < 2 or fields[1] != parsed.get("fingerprint"):
        return None
    return raw, parsed["fingerprint"], parsed["key_type"]



def _publish_new_file(source: Path, target: Path, uid: int, mode: int) -> tuple[int, int]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(target, flags, mode)
    identity: tuple[int, int] | None = None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid:
            raise ClientKeyError("new key file ownership is unverified")
        identity = (info.st_dev, info.st_ino)
        with source.open("rb") as stream:
            while True:
                chunk = stream.read(16_384)
                if not chunk:
                    break
                view = memoryview(chunk)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise ClientKeyError("key file write did not complete")
                    view = view[written:]
        os.fchmod(fd, mode)
        os.fsync(fd)
        return identity
    except BaseException:
        if identity is not None:
            try:
                current = target.lstat()
                if (current.st_dev, current.st_ino) == identity and stat.S_ISREG(current.st_mode):
                    target.unlink()
            except OSError:
                pass
        raise
    finally:
        os.close(fd)

def preview(*, home: str | os.PathLike[str], uid: int, name: str) -> dict[str, object]:
    ssh_dir, target, key_dir = _paths(home, uid, name)
    private_path = target
    public_path = target.with_name(target.name + ".pub")
    state = []
    for path in (private_path, public_path):
        try:
            info = path.lstat()
            state.append(("present", info.st_dev, info.st_ino, info.st_mode, info.st_uid))
        except FileNotFoundError:
            state.append(("absent",))
        except OSError as exc:
            raise ClientKeyError("key destination cannot be inspected safely") from exc
    if state[0][0] == "present" or state[1][0] == "present":
        existing = _public_fingerprint(public_path, uid)
        return {"status": "already_exists", "changed": False, "requires_confirmation": False,
                "name": name, "private_key_path": f"~/.ssh/{_KEY_DIR}/{name}",
                "public_key_path": f"~/.ssh/{_KEY_DIR}/{name}.pub",
                "fingerprint": existing[1] if existing else None,
                "public_key": existing[0] if existing else None,
                "private_key_valid": bool(existing and state[0][0] == "present"
                    and stat.S_ISREG(state[0][3]) and state[0][4] == uid
                    and stat.S_IMODE(state[0][3]) == 0o600),
                "secret_values_returned": False}
    ssh_info = ssh_dir.lstat()
    key_identity = ("absent",) if key_dir is None else (
        "present", key_dir.lstat().st_dev, key_dir.lstat().st_ino)
    material = repr(("ed25519-create-v1", name, uid, ssh_info.st_dev, ssh_info.st_ino,
                     key_identity, "both-destinations-absent")).encode()
    plan_id = hashlib.sha256(material).hexdigest()[:32]
    return {"status": "ready", "changed": True, "requires_confirmation": True,
            "action": "create_ed25519_client_key", "name": name,
            "private_key_path": f"~/.ssh/{_KEY_DIR}/{name}",
            "public_key_path": f"~/.ssh/{_KEY_DIR}/{name}.pub",
            "algorithm": "Ed25519", "passphrase": "none; protected by Native app sandbox and mode 0600",
            "shared_account_impact": "Enrollment target is determined and shown by the later SSH key preview.",
            "plan_id": plan_id, "secret_values_returned": False}


def apply(*, home: str | os.PathLike[str], uid: int, name: str,
          confirmed: bool, plan_id: str) -> dict[str, object]:
    ssh_dir, _target, _key_dir = _paths(home, uid, name)
    lock_path = ssh_dir / _LOCK
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise ClientKeyError("could not acquire the private Native SSH key lock") from exc
    try:
        lock_info = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != uid:
            raise ClientKeyError("Native SSH key lock ownership is unverified")
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        plan = preview(home=home, uid=uid, name=name)
        if not plan["changed"]:
            return plan
        if not confirmed:
            return {**plan, "status": "confirmation_required"}
        if not isinstance(plan_id, str) or plan_id != plan["plan_id"]:
            return {**plan, "status": "stale_plan", "changed": False}
        key_dir = ssh_dir / _KEY_DIR
        try:
            os.mkdir(key_dir, 0o700)
            made_dir = True
        except FileExistsError:
            made_dir = False
        key_dir_info = key_dir.lstat()
        if (stat.S_ISLNK(key_dir_info.st_mode) or not stat.S_ISDIR(key_dir_info.st_mode)
                or key_dir_info.st_uid != uid or stat.S_IMODE(key_dir_info.st_mode) & 0o077):
            raise ClientKeyError("Native Ternuxx key directory must be private and owned")
        target = key_dir / name
        public_path = key_dir / (name + ".pub")
        temp_dir = Path(tempfile.mkdtemp(prefix=".create-", dir=key_dir))
        os.chmod(temp_dir, 0o700)
        temp_key = temp_dir / "key"
        linked_private: tuple[int, int] | None = None
        linked_public: tuple[int, int] | None = None
        completed = False
        try:
            executable = shutil.which("ssh-keygen")
            if not executable:
                raise ClientKeyError("ssh-keygen is unavailable")
            result = subprocess.run(
                [executable, "-q", "-t", "ed25519", "-N", "", "-C",
                 "Ternuxx SSH 8023 recovery", "-f", str(temp_key)],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20,
                check=False, env={"HOME": str(home), "LANG": "C", "LC_ALL": "C",
                                  "PATH": os.environ.get("PATH", "")})
            if result.returncode != 0:
                raise ClientKeyError("ssh-keygen could not create the recovery keypair")
            os.chmod(temp_key, 0o600)
            os.chmod(Path(str(temp_key) + ".pub"), 0o644)
            public = _public_fingerprint(Path(str(temp_key) + ".pub"), uid)
            if not public:
                raise ClientKeyError("generated public key failed OpenSSH verification")
            with temp_key.open("rb") as stream:
                os.fsync(stream.fileno())
            with Path(str(temp_key) + ".pub").open("rb") as stream:
                os.fsync(stream.fileno())
            linked_private = _publish_new_file(temp_key, target, uid, 0o600)
            linked_public = _publish_new_file(Path(str(temp_key) + ".pub"), public_path, uid, 0o644)
            dir_fd = os.open(key_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            response = {"status": "created", "changed": True, "name": name,
                    "algorithm": "Ed25519", "private_key_path": f"~/.ssh/{_KEY_DIR}/{name}",
                    "public_key_path": f"~/.ssh/{_KEY_DIR}/{name}.pub",
                    "private_key_mode": "0600", "public_key_mode": "0644",
                    "fingerprint": public[1], "key_type": public[2], "public_key": public[0],
                    "enrollment_required": True,
                    "shared_account_impact": "The public key is not enrolled; the enrollment preview determines which service will receive it.",
                    "secret_values_returned": False}
            completed = True
            return response
        finally:
            if not completed:
                for path, identity in ((target, linked_private), (public_path, linked_public)):
                    if identity is None:
                        continue
                    try:
                        current = path.lstat()
                        if (current.st_dev, current.st_ino) == identity and stat.S_ISREG(current.st_mode):
                            path.unlink()
                    except OSError:
                        pass
            shutil.rmtree(temp_dir)
            if not completed and made_dir:
                try:
                    key_dir.rmdir()
                    fd = os.open(ssh_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                except OSError:
                    pass
    except FileExistsError as exc:
        raise ClientKeyError("key destination already exists; it was not overwritten") from exc
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
