"""Pinned, experimental Native Termux Snapdragon HTP inference path."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from typing import Callable

import cpu_inference


RELEASE = "b11849"
ASSET = "llama-b11849-bin-android-arm64-snapdragon.tar.gz"
URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{RELEASE}/{ASSET}"
ARCHIVE_SIZE = 61_622_667
ARCHIVE_SHA256 = "2d0f1a989a8f0c4329839c3bb85b6fb70edb03e0b017fee0be4cf55b7ece8f6c"
ROOT_NAME = "llama-b11849"
RUNTIME_TIMEOUT_SECONDS = 120
INSTALL_TIMEOUT_SECONDS = 120
MAX_EXTRACTED_BYTES = 260_000_000
_PLAN_CONFIRMATIONS = {"install": "INSTALL", "remove": "REMOVE"}
_OFFLOAD = re.compile(r"offloaded\s+(\d+)\s*/\s*(\d+)\s+layers?\s+to GPU", re.I)


class NpuInferenceError(RuntimeError):
    pass


def _home_path(path: Path) -> Path:
    home = Path.home().resolve()
    candidate = path.absolute()
    try:
        candidate.relative_to(home)
    except ValueError as exc:
        raise NpuInferenceError("NPU runtime state must remain inside the Termux home directory") from exc
    current = home
    for part in candidate.relative_to(home).parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise NpuInferenceError("cannot inspect NPU runtime state") from exc
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
            raise NpuInferenceError("NPU runtime path contains a symlink or foreign-owned entry")
    return candidate


def artifact_root(*, home: Path | None = None, state_dir: str | Path | None = None) -> Path:
    base_home = home or Path.home()
    state = Path(state_dir) if state_dir is not None else Path(
        os.environ.get("TERNUXX_STATE_DIR", base_home / ".local/share/ternuxx"))
    if not state.is_absolute():
        raise NpuInferenceError("Ternuxx state directory must be absolute")
    return _home_path(state / "artifacts" / "llama.cpp-snapdragon-b11849")


def archive_path(*, home: Path | None = None, state_dir: str | Path | None = None) -> Path:
    return artifact_root(home=home, state_dir=state_dir) / ASSET


def runtime_path(*, home: Path | None = None, state_dir: str | Path | None = None) -> Path:
    return artifact_root(home=home, state_dir=state_dir) / "runtime" / ROOT_NAME


def _required_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    chosen: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != ROOT_NAME:
            raise NpuInferenceError("Snapdragon artifact contains an unsafe archive path")
        if not (member.isfile() or member.isdir()):
            raise NpuInferenceError("Snapdragon artifact contains a link or unsupported archive entry")
        relative = path.relative_to(ROOT_NAME)
        selected = (relative == PurePosixPath("bin/llama-cli")
                    or relative == PurePosixPath("LICENSE")
                    or relative == PurePosixPath("THIRD_PARTY_NOTICES.txt")
                    or (len(relative.parts) == 2 and relative.parts[0] == "lib"
                        and relative.name.endswith(".so")))
        if selected:
            if not member.isfile():
                raise NpuInferenceError("Snapdragon artifact runtime entry is not a regular file")
            chosen.append(member)
    names = {PurePosixPath(member.name).relative_to(ROOT_NAME).as_posix() for member in chosen}
    if "bin/llama-cli" not in names or "LICENSE" not in names:
        raise NpuInferenceError("Snapdragon artifact is missing its fixed CLI or license")
    for required in ("lib/libggml-hexagon.so", "lib/libggml-htp-v73.so", "lib/libggml-opencl.so"):
        if required not in names:
            raise NpuInferenceError(f"Snapdragon artifact is missing required runtime file: {required}")
    if sum(member.size for member in chosen) > MAX_EXTRACTED_BYTES:
        raise NpuInferenceError("Snapdragon artifact runtime exceeds the fixed extraction limit")
    return chosen


def _digest_stream(stream) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def _archive_is_valid(path: Path) -> bool:
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_size != ARCHIVE_SIZE or info.st_mode & 0o077):
            return False
        return cpu_inference._sha256(path) == ARCHIVE_SHA256
    except OSError:
        return False


def _current_runtime_matches(archive: tarfile.TarFile, root: Path,
                             members: list[tarfile.TarInfo]) -> dict[str, dict[str, object]] | None:
    hashes: dict[str, dict[str, object]] = {}
    for member in members:
        relative = PurePosixPath(member.name).relative_to(ROOT_NAME).as_posix()
        target = root / relative
        try:
            info = target.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                return None
            extracted = archive.extractfile(member)
            if extracted is None:
                return None
            expected_size, expected_hash = _digest_stream(extracted)
            if info.st_size != expected_size:
                return None
            size, digest = _digest_stream(target.open("rb"))
        except (OSError, NpuInferenceError, tarfile.TarError):
            return None
        if size != expected_size or digest != expected_hash:
            return None
        hashes[relative] = {"size_bytes": size, "sha256": digest}
    return hashes


def _read_manifest(root: Path) -> dict[str, object] | None:
    marker = root / "install-manifest.json"
    try:
        info = marker.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            return None
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if (not isinstance(data, dict) or data.get("release") != RELEASE or data.get("asset") != ASSET
            or data.get("sha256") != ARCHIVE_SHA256 or not isinstance(data.get("files"), dict)):
        return None
    return data


def _runtime_valid(root: Path) -> tuple[bool, str]:
    manifest = _read_manifest(root.parent.parent)
    if manifest is None:
        return False, "pinned Snapdragon runtime has not been verified by the Ternuxx installer"
    recorded = manifest["files"]
    required_files = ["bin/llama-cli", "lib/libggml-hexagon.so", "lib/libggml-htp-v73.so",
                      "lib/libggml-opencl.so", "LICENSE"]
    if "THIRD_PARTY_NOTICES.txt" in recorded:
        required_files.append("THIRD_PARTY_NOTICES.txt")
    for relative in required_files:
        entry = recorded.get(relative)
        target = root / relative
        expected_size = entry.get("size_bytes") if isinstance(entry, dict) else None
        expected_hash = entry.get("sha256") if isinstance(entry, dict) else None
        if (type(expected_size) is not int or expected_size < 0
                or not isinstance(expected_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)):
            return False, "pinned Snapdragon runtime manifest has invalid file metadata"
        try:
            fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or info.st_mode & 0o022 or info.st_size != expected_size):
                    return False, "pinned Snapdragon runtime files do not match its verified manifest"
                actual_size, actual_hash = _digest_stream(stream)
        except OSError:
            return False, "pinned Snapdragon runtime is incomplete"
        if actual_size != expected_size or actual_hash != expected_hash:
            return False, "pinned Snapdragon runtime files do not match its verified manifest"
    return True, "verified upstream llama.cpp Android Snapdragon release b11849"


def _runtime_removal_state(root: Path, runtime: Path) -> tuple[bool, str, int, str | None]:
    marker = root / "install-manifest.json"
    manifest = _read_manifest(root)
    if manifest is None or not isinstance(manifest.get("files"), dict):
        return False, "a verified runtime install manifest is not present", 0, None
    expected: dict[str, dict[str, object]] = manifest["files"]
    expected_directories = {""}
    total_remaining = 0
    expected_paths = set()
    for relative, entry in expected.items():
        path = PurePosixPath(relative)
        if (path.is_absolute() or not path.parts or ".." in path.parts
                or path.as_posix() != relative or not isinstance(entry, dict)
                or type(entry.get("size_bytes")) is not int
                or not isinstance(entry.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
            return False, "runtime manifest contains unsafe or invalid file metadata; runtime was preserved", 0, None
        expected_paths.add(relative)
        for depth in range(1, len(path.parts)):
            expected_directories.add("/".join(path.parts[:depth]))
    actual_files: set[str] = set()
    actual_directories = {""}
    if runtime.exists():
        try:
            root_info = runtime.lstat()
            if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid():
                return False, "runtime root is unsafe; runtime was preserved", 0, None
            for current, dirs, files in os.walk(runtime, followlinks=False):
                current_path = Path(current)
                relative_dir = current_path.relative_to(runtime).as_posix()
                actual_directories.add("" if relative_dir == "." else relative_dir)
                for name in dirs:
                    item = current_path / name
                    info = item.lstat()
                    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                        return False, "runtime contains an unsafe directory; runtime was preserved", 0, None
                    actual_directories.add(item.relative_to(runtime).as_posix())
                for name in files:
                    item = current_path / name
                    relative = item.relative_to(runtime).as_posix()
                    info = item.lstat()
                    if (relative not in expected or not stat.S_ISREG(info.st_mode)
                            or info.st_uid != os.getuid() or info.st_mode & 0o022):
                        return False, "runtime contains unrecorded or unsafe files; runtime was preserved", 0, None
                    fd = os.open(item, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                    with os.fdopen(fd, "rb") as stream:
                        opened = os.fstat(stream.fileno())
                        size, digest = _digest_stream(stream)
                    entry = expected[relative]
                    if (not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.getuid()
                            or size != entry["size_bytes"] or digest != entry["sha256"]):
                        return False, "runtime files differ from their verified manifest; runtime was preserved", 0, None
                    total_remaining += size
                    actual_files.add(relative)
        except OSError:
            return False, "runtime could not be inventoried safely; runtime was preserved", 0, None
    if not actual_files <= expected_paths or not actual_directories <= expected_directories:
        return False, "runtime contains unrecorded files or directories; runtime was preserved", 0, None
    try:
        marker_hash = hashlib.sha256(marker.read_bytes()).hexdigest()
    except OSError:
        return False, "runtime manifest could not be read safely; runtime was preserved", 0, None
    return True, "verified runtime files can be removed; pinned download cache will be retained", total_remaining, marker_hash


def _active_runtime_processes(runtime: Path) -> list[int] | None:
    """Return matching CLI PIDs; None means the process table could not be checked safely."""
    proc = Path("/proc")
    expected = str(runtime / "bin/llama-cli")
    matches = []
    try:
        entries = list(proc.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if (entry / "comm").read_text(encoding="ascii").strip() != "llama-cli":
                continue
            executable = os.readlink(entry / "exe").removesuffix(" (deleted)")
            if executable == expected:
                matches.append(int(entry.name))
        except FileNotFoundError:
            continue
        except OSError:
            return None
    return sorted(matches)


def preview(action: str = "install", *, home: Path | None = None,
            state_dir: str | Path | None = None) -> dict[str, object]:
    if action not in _PLAN_CONFIRMATIONS:
        raise NpuInferenceError("NPU runtime action must be install or remove")
    root = artifact_root(home=home, state_dir=state_dir)
    archive = archive_path(home=home, state_dir=state_dir)
    runtime = runtime_path(home=home, state_dir=state_dir)
    current, current_reason = _runtime_valid(runtime)
    cache_ready = _archive_is_valid(archive)
    removable, remove_reason, runtime_size, manifest_hash = _runtime_removal_state(root, runtime)
    payload = {"action": action, "release": RELEASE, "asset": ASSET,
               "url": URL, "sha256": ARCHIVE_SHA256, "license": "MIT", "archive_size_bytes": ARCHIVE_SIZE,
               "archive_path": str(archive), "runtime_path": str(runtime),
               "network_required": action == "install" and not cache_ready,
               "already_installed": current, "removable": removable,
               "remove_reason": remove_reason, "runtime_size_bytes": runtime_size,
               "archive_retained_on_remove": action == "remove" and cache_ready,
               "runtime_manifest_sha256": manifest_hash,
               "extraction_limit_bytes": MAX_EXTRACTED_BYTES,
               "runtime_state": "ready" if current else current_reason}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    parent = root.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    try:
        free = shutil.disk_usage(parent).free
    except OSError:
        free = None
    required = ARCHIVE_SIZE + MAX_EXTRACTED_BYTES if action == "install" else 0
    return {**payload, "plan_id": hashlib.sha256(encoded).hexdigest()[:24],
            "read_only": True, "available_bytes": free,
            "space_check": ("sufficient" if free is not None and free >= required
                            else "insufficient" if free is not None else "unknown")}


def _private_directory(path: Path) -> None:
    _home_path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise NpuInferenceError("NPU artifact directory is unsafe")
    os.chmod(path, 0o700)


@contextmanager
def _runtime_operation_lock(root: Path, *, shared: bool):
    _private_directory(root)
    lock_path = root / ".runtime-operation.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise NpuInferenceError("NPU runtime operation lock is unsafe")
        os.fchmod(fd, 0o600)
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        try:
            fcntl.flock(fd, mode | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise NpuInferenceError("another NPU runtime operation is active") from exc
        try:
            yield
        finally:
            os.close(fd)
    except NpuInferenceError:
        raise
    except OSError as exc:
        raise NpuInferenceError("cannot safely lock the private NPU runtime") from exc


def _download_archive(path: Path, *, opener: Callable = urllib.request.urlopen,
                      progress: Callable[[int, int], None] | None = None) -> None:
    request = urllib.request.Request(URL, headers={"User-Agent": "Ternuxx-Native-HTP/1"})
    temporary = path.with_name(f".{path.name}.{os.getpid()}.part")
    digest = hashlib.sha256()
    received = 0
    try:
        with opener(request, timeout=45) as response, temporary.open("xb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > ARCHIVE_SIZE:
                    raise NpuInferenceError("Snapdragon artifact exceeds its pinned size")
                output.write(chunk)
                digest.update(chunk)
                if progress:
                    progress(received, ARCHIVE_SIZE)
            output.flush()
            os.fsync(output.fileno())
        if received != ARCHIVE_SIZE or digest.hexdigest() != ARCHIVE_SHA256:
            raise NpuInferenceError("Snapdragon artifact size or SHA-256 did not match the pinned release")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _write_manifest(root: Path, files: dict[str, dict[str, object]]) -> dict[str, object]:
    payload = {"release": RELEASE, "asset": ASSET, "url": URL,
               "sha256": ARCHIVE_SHA256, "license": "MIT",
               "files": files, "accelerator": "Hexagon HTP0",
               "settings": {"GGML_HEXAGON_MM_SELECT": "1", "GGML_HEXAGON_FA_SELECT": "0"}}
    target = root / "install-manifest.json"
    temporary = root / f".install-manifest.{os.getpid()}.tmp"
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    return payload


def install_runtime(*, plan_id: str, confirmed: str, home: Path | None = None,
                    state_dir: str | Path | None = None,
                    opener: Callable = urllib.request.urlopen,
                    progress: Callable[[int, int], None] | None = None) -> dict[str, object]:
    plan = preview("install", home=home, state_dir=state_dir)
    if confirmed != _PLAN_CONFIRMATIONS["install"] or plan_id != plan["plan_id"]:
        raise NpuInferenceError("NPU runtime installation requires the exact current preview and INSTALL confirmation")
    if plan["space_check"] == "insufficient":
        raise NpuInferenceError("insufficient free storage for the pinned Snapdragon runtime")
    root = artifact_root(home=home, state_dir=state_dir)
    archive_file = archive_path(home=home, state_dir=state_dir)
    runtime = runtime_path(home=home, state_dir=state_dir)
    _private_directory(root)
    lock_path = root / ".runtime-operation.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        lock_info = os.fstat(fd)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid():
            raise NpuInferenceError("NPU runtime operation lock is unsafe")
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise NpuInferenceError("another NPU runtime operation is active") from exc
        if not _archive_is_valid(archive_file):
            try:
                existing = archive_file.lstat()
            except FileNotFoundError:
                existing = None
            if existing is not None:
                raise NpuInferenceError("an unverified NPU artifact already exists; it was preserved")
            _download_archive(archive_file, opener=opener, progress=progress)
        try:
            with tarfile.open(archive_file, "r:gz") as archive:
                if cpu_inference._sha256(archive_file) != ARCHIVE_SHA256:
                    raise NpuInferenceError("cached Snapdragon artifact failed SHA-256 verification")
                members = _required_members(archive)
                runtime_root = runtime.parent
                if runtime.exists():
                    files = _current_runtime_matches(archive, runtime, members)
                    if files is None:
                        raise NpuInferenceError("existing Snapdragon runtime does not match its pinned archive; it was preserved")
                else:
                    files: dict[str, dict[str, object]] = {}
                    _private_directory(runtime_root)
                    temporary = Path(tempfile.mkdtemp(prefix=".llama-b11849-", dir=runtime_root))
                    try:
                        extracted = temporary / ROOT_NAME
                        for member in members:
                            relative = PurePosixPath(member.name).relative_to(ROOT_NAME)
                            destination = extracted.joinpath(*relative.parts)
                            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                            source = archive.extractfile(member)
                            if source is None:
                                raise NpuInferenceError("cannot read a pinned Snapdragon runtime file")
                            digest = hashlib.sha256()
                            size = 0
                            with source, destination.open("xb") as output:
                                while True:
                                    chunk = source.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    size += len(chunk)
                                    digest.update(chunk)
                                    output.write(chunk)
                                output.flush()
                                os.fsync(output.fileno())
                            expected = {"size_bytes": size, "sha256": digest.hexdigest()}
                            files[relative.as_posix()] = expected
                            os.chmod(destination, 0o700 if relative.as_posix() == "bin/llama-cli" else 0o600)
                        if runtime.exists() or runtime.is_symlink():
                            raise NpuInferenceError("NPU runtime destination appeared during installation")
                        os.chmod(extracted, 0o700)
                        os.replace(extracted, runtime)
                    finally:
                        shutil.rmtree(temporary, ignore_errors=True)
                _write_manifest(root, files)
        except (OSError, tarfile.TarError) as exc:
            raise NpuInferenceError("pinned Snapdragon runtime could not be safely extracted") from exc
    finally:
        os.close(fd)
    valid, reason = _runtime_valid(runtime)
    if not valid:
        raise NpuInferenceError(reason)
    return {"installed": True, "release": RELEASE, "runtime_path": str(runtime),
            "sha256": ARCHIVE_SHA256, "network_used": plan["network_required"]}


def remove_runtime(*, plan_id: str, confirmed: str, home: Path | None = None,
                   state_dir: str | Path | None = None) -> dict[str, object]:
    plan = preview("remove", home=home, state_dir=state_dir)
    if confirmed != _PLAN_CONFIRMATIONS["remove"] or plan_id != plan["plan_id"]:
        raise NpuInferenceError("NPU runtime removal requires the exact current preview and REMOVE confirmation")
    if plan["removable"] is not True:
        raise NpuInferenceError(str(plan["remove_reason"]))
    root = artifact_root(home=home, state_dir=state_dir)
    runtime = runtime_path(home=home, state_dir=state_dir)
    with _runtime_operation_lock(root, shared=False):
        current = preview("remove", home=home, state_dir=state_dir)
        if current["plan_id"] != plan_id or current["removable"] is not True:
            raise NpuInferenceError("NPU runtime changed after preview; it was preserved")
        if current["runtime_manifest_sha256"] != plan["runtime_manifest_sha256"]:
            raise NpuInferenceError("NPU runtime manifest changed after preview; it was preserved")
        pids = _active_runtime_processes(runtime)
        if pids is None or pids:
            raise NpuInferenceError("cannot verify that the NPU runtime is idle; runtime was preserved")
        allowed, reason, reclaimed, _ = _runtime_removal_state(root, runtime)
        if not allowed:
            raise NpuInferenceError(reason)
        if runtime.exists():
            shutil.rmtree(runtime)
        (root / "install-manifest.json").unlink(missing_ok=True)
    return {"removed": True, "runtime_path": str(runtime),
            "reclaimed_bytes": reclaimed, "archive_retained": archive_path(
                home=home, state_dir=state_dir).is_file()}


def _runtime_env(runtime: Path, *, prefix: str | None = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if key not in {"LD_LIBRARY_PATH", "LD_PRELOAD", "GGML_BACKEND_PATH",
                          "ADSP_LIBRARY_PATH", "CDSP_LIBRARY_PATH",
                          "GGML_HEXAGON_MM_SELECT", "GGML_HEXAGON_FA_SELECT"}}
    env["PREFIX"] = prefix or os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    env["LC_ALL"] = "C"
    env["LD_LIBRARY_PATH"] = os.pathsep.join((str(runtime / "lib"), "/system/lib64",
                                               "/vendor/lib64", str(Path(env["PREFIX"]) / "lib")))
    remote_paths = (str(runtime / "lib"), "/vendor/lib/rfsa/adsp", "/vendor/lib64")
    env["ADSP_LIBRARY_PATH"] = ";".join(remote_paths)
    env["CDSP_LIBRARY_PATH"] = ";".join(remote_paths)
    env["GGML_HEXAGON_MM_SELECT"] = "1"
    env["GGML_HEXAGON_FA_SELECT"] = "0"
    return env


def _soc_model() -> str:
    try:
        result = subprocess.run(["getprop", "ro.soc.model"], capture_output=True,
                                text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (result.stdout or "").strip()[:80] if result.returncode == 0 else ""


def status(*, home: Path | None = None, state_dir: str | Path | None = None,
           prefix: str | None = None) -> dict[str, object]:
    runtime = runtime_path(home=home, state_dir=state_dir)
    valid, reason = _runtime_valid(runtime)
    soc = _soc_model()
    if not valid:
        return {"available": False, "backend": "Hexagon HTP", "device": None,
                "reason": reason, "release": RELEASE, "soc_model": soc}
    if "SM8735" not in soc:
        return {"available": False, "backend": "Hexagon HTP", "device": None,
                "reason": "experimental HTP route is qualified only on Qualcomm SM8735",
                "release": RELEASE, "soc_model": soc or "unknown"}
    executable = runtime / "bin/llama-cli"
    try:
        result = subprocess.run([str(executable), "--list-devices"], capture_output=True,
                                text=True, timeout=10, check=False,
                                env=_runtime_env(runtime, prefix=prefix))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "backend": "Hexagon HTP", "device": None,
                "reason": f"HTP device discovery failed ({type(exc).__name__})",
                "release": RELEASE, "soc_model": soc}
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    found = any(re.match(r"^\s*HTP0:\s*Hexagon\b", line, re.I)
                for line in combined.splitlines())
    available = result.returncode == 0 and found
    return {"available": available, "backend": "Hexagon HTP", "device": "HTP0" if available else None,
            "soc_model": soc, "release": RELEASE, "runtime_path": str(executable),
            "exit_code": result.returncode,
            "reason": None if available else "no HTP0 device reported; CPU and Vulkan remain separate backends",
            "experimental": True, "silent_fallback": False}


def _response_text(stdout: str, prompt: str) -> str:
    formatted = f"<|im_start|>user\n{prompt.strip()}<|im_end|>\n<|im_start|>assistant\n"
    marker = "> " + formatted
    start = stdout.find(marker)
    if start < 0:
        raise NpuInferenceError("llama.cpp returned an unrecognized HTP output format")
    response = stdout[start + len(marker):].split("[ Prompt:", 1)[0].split("Exiting...", 1)[0].strip()
    response = response.strip()
    if not response:
        raise NpuInferenceError("HTP inference returned an empty response")
    return response


def _execute(argv: list[str], *, timeout: int, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    process = None
    try:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=env, start_new_session=True)
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
                stdout, stderr = process.communicate(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    stdout, stderr = process.communicate(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    stdout, stderr = process.communicate()
        raise NpuInferenceError("HTP inference timed out; its owned process group received a bounded interrupt") from exc
    except KeyboardInterrupt as exc:
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
                process.communicate(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.communicate(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate()
        raise NpuInferenceError("HTP inference cancelled; its owned process group received a bounded interrupt") from exc
    except OSError as exc:
        raise NpuInferenceError("pinned llama.cpp Snapdragon runtime could not be started") from exc
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def run_inference(prompt: str, *, home: Path | None = None,
                  state_dir: str | Path | None = None, prefix: str | None = None,
                  max_tokens: int = cpu_inference.DEFAULT_OUTPUT_TOKENS,
                  timeout: int = RUNTIME_TIMEOUT_SECONDS,
                  model_id: str | None = None) -> dict[str, object]:
    if (not isinstance(prompt, str) or not prompt.strip() or "\n" in prompt or "\r" in prompt
            or len(prompt.encode("utf-8")) > cpu_inference.MAX_PROMPT_BYTES):
        raise NpuInferenceError("prompt must be one line of 1 to 4096 UTF-8 bytes")
    if type(max_tokens) is not int or not 1 <= max_tokens <= cpu_inference.MAX_OUTPUT_TOKENS:
        raise NpuInferenceError("output token limit must be between 1 and 128")
    if type(timeout) is not int or not 1 <= timeout <= RUNTIME_TIMEOUT_SECONDS:
        raise NpuInferenceError("timeout must be between 1 and 120 seconds")
    inventory = status(home=home, state_dir=state_dir, prefix=prefix)
    if inventory.get("available") is not True:
        raise NpuInferenceError(str(inventory.get("reason") or "HTP0 is unavailable"))
    spec = cpu_inference.resolve_model(model_id)
    model = cpu_inference.model_path(home=home, state_dir=state_dir, spec=spec)
    cpu_inference._check_owned_path(model, allow_missing=False)
    if not cpu_inference._valid_model(model, spec):
        raise NpuInferenceError("selected model is missing, unsafe, or failed SHA-256 verification")
    lock = (cpu_inference.nullcontext() if spec.model_id == cpu_inference.OWNER_QWEN25.model_id
            else cpu_inference._model_lock(model.parent))
    with lock:
        if not cpu_inference._valid_model(model, spec):
            raise NpuInferenceError("selected model is missing, unsafe, or failed SHA-256 verification")
        runtime = runtime_path(home=home, state_dir=state_dir)
        formatted_prompt = (f"<|im_start|>user\n{prompt.strip()}<|im_end|>\n"
                            "<|im_start|>assistant\n")
        argv = [str(runtime / "bin/llama-cli"), "-m", str(model), "--device", "HTP0",
                "-ngl", "all", "-t", "4", "-tb", "4", "-c", "512", "-n", str(max_tokens),
                "--seed", "42", "--temp", "0", "--reasoning", "off", "--single-turn",
                "--simple-io", "--no-display-prompt", "--no-warmup", "-p", formatted_prompt, "-lv", "4"]
        root = artifact_root(home=home, state_dir=state_dir)
        with _runtime_operation_lock(root, shared=True):
            valid, reason = _runtime_valid(runtime)
            if not valid:
                raise NpuInferenceError(reason)
            started = time.monotonic()
            completed = _execute(argv, timeout=timeout,
                                 env=_runtime_env(runtime, prefix=prefix))
            elapsed = time.monotonic() - started
        if completed.returncode != 0:
            detail = " ".join((completed.stderr or completed.stdout).split())[:500]
            raise NpuInferenceError(f"HTP inference failed with exit {completed.returncode}: {detail}")
        match = _OFFLOAD.search(completed.stderr or "")
        buffer = re.search(r"HTP0 model buffer size\s*=\s*([\d.]+)\s*MiB",
                           completed.stderr or "", re.I)
        if (not match or int(match.group(1)) <= 0 or int(match.group(1)) != int(match.group(2))
                or not buffer or float(buffer.group(1)) <= 0):
            raise NpuInferenceError("HTP runtime exited without verifiable complete HTP layer and memory-buffer proof")
        return {"backend": "Hexagon HTP", "device_id": "HTP0",
                "npu_layers": int(match.group(1)), "total_layers": int(match.group(2)),
                "npu_model_buffer_mib": round(float(buffer.group(1)), 2),
                "gpu_layers": 0, "elapsed_seconds": round(elapsed, 3),
                "model_id": spec.model_id,
                "output": _response_text(completed.stdout or "", prompt),
                "exit_code": completed.returncode, "max_output_tokens": max_tokens,
                "experimental": True, "silent_fallback": False}
