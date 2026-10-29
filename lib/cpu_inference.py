#!/usr/bin/env python3
"""Pinned, bounded Native Termux CPU inference workflow."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass
from typing import BinaryIO, Callable


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    filename: str
    url: str
    size_bytes: int
    sha256: str
    license: str


MODEL = ModelSpec(
    model_id="qwen2.5-1.5b-instruct-q4_k_m",
    filename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
    url="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    size_bytes=1_117_320_736,
    sha256="6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e",
    license="Apache-2.0",
)
MAX_PROMPT_BYTES = 4096
MAX_OUTPUT_TOKENS = 128
DEFAULT_OUTPUT_TOKENS = 64
RUN_TIMEOUT_SECONDS = 120
_DEVICE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


class InferenceError(RuntimeError):
    pass


def _state_dir(home: Path, state_dir: str | Path | None) -> Path:
    if state_dir is not None:
        path = Path(state_dir)
    else:
        path = Path(os.environ.get("TERNUXX_STATE_DIR", home / ".local/share/ternuxx"))
    if not path.is_absolute():
        raise InferenceError("Ternuxx state directory must be absolute")
    return path / "models"


def _check_owned_path(path: Path, *, allow_missing: bool = True) -> None:
    """Reject symlinked or foreign-owned existing components below the home root."""
    home = Path.home()
    try:
        relative = path.absolute().relative_to(home.absolute())
    except ValueError as exc:
        raise InferenceError("model state must remain inside the Termux home directory") from exc
    current = home
    for part in relative.parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if allow_missing:
                continue
            raise InferenceError("model file is missing")
        except OSError as exc:
            raise InferenceError("cannot inspect model path") from exc
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
            raise InferenceError("model path contains a symlink or foreign-owned entry")
        if current != path and not stat.S_ISDIR(info.st_mode):
            raise InferenceError("model state ancestor is not a directory")


def model_path(*, home: Path | None = None, state_dir: str | Path | None = None,
               spec: ModelSpec = MODEL) -> Path:
    base_home = home or Path.home()
    models = _state_dir(base_home, state_dir)
    return models / spec.filename


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_model(path: Path, spec: ModelSpec = MODEL) -> bool:
    try:
        _check_owned_path(path, allow_missing=False)
        info = path.stat()
        return (stat.S_ISREG(info.st_mode) and info.st_size == spec.size_bytes
                and info.st_mode & 0o077 == 0 and _sha256(path) == spec.sha256)
    except (OSError, InferenceError):
        return False


def _runtime(prefix: str | None = None) -> str | None:
    search_path = os.environ.get("PATH", "")
    if prefix:
        search_path = str(Path(prefix) / "bin") + os.pathsep + search_path
    return shutil.which("llama-cli", path=search_path)


def _runtime_env(prefix: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    actual_prefix = prefix or env.get("PREFIX", "/data/data/com.termux/files/usr")
    termux_lib = str(Path(actual_prefix) / "lib")
    inherited = env.get("LD_LIBRARY_PATH", "").split(os.pathsep)
    env["LD_LIBRARY_PATH"] = os.pathsep.join(dict.fromkeys(
        item for item in [termux_lib, *inherited] if item))
    env.pop("LD_PRELOAD", None)
    env["LC_ALL"] = "C"
    return env


def status(*, home: Path | None = None, state_dir: str | Path | None = None,
           prefix: str | None = None) -> dict[str, object]:
    home = home or Path.home()
    path = model_path(home=home, state_dir=state_dir)
    runtime = _runtime(prefix)
    version = "unavailable"
    if runtime:
        try:
            completed = subprocess.run([runtime, "--version"], capture_output=True, text=True,
                                       timeout=5, check=False, env=_runtime_env(prefix))
            version = (completed.stdout or completed.stderr).strip().splitlines()[0][:160]
        except (OSError, subprocess.TimeoutExpired, IndexError):
            version = "installed; version probe failed"
    try:
        _check_owned_path(path)
        info = path.lstat() if path.exists() else None
        present = bool(info and stat.S_ISREG(info.st_mode))
        if info and not stat.S_ISREG(info.st_mode):
            model_state = "unsafe"
        elif not info:
            model_state = "missing"
        elif info.st_size != MODEL.size_bytes:
            model_state = "invalid-size"
        elif info.st_mode & 0o077:
            model_state = "unsafe-permissions"
        else:
            model_state = "present-unverified"
    except InferenceError:
        present, model_state = False, "unsafe"
    return {
        "runtime": {"available": bool(runtime), "path": runtime, "version": version,
                    "package": "llama-cpp", "package_preview_command": "apt-get -s install llama-cpp",
                    "package_install_command": "pkg install llama-cpp"},
        "model": {"id": MODEL.model_id, "path": str(path), "available": present,
                  "state": model_state, "size_bytes": MODEL.size_bytes,
                  "sha256": MODEL.sha256, "license": MODEL.license},
        "execution": {"backend": "CPU", "gpu_layers": 0, "max_output_tokens": MAX_OUTPUT_TOKENS},
    }


def _gpu_runtime_env(*, prefix: str | None = None, home: Path | None = None,
                     state_dir: str | Path | None = None) -> dict[str, str]:
    """Use the selected Native graphics ICD and the version-matched Termux backend."""
    env = _runtime_env(prefix)
    base_home = home or Path.home()
    runtime_state = Path(state_dir) if state_dir is not None else Path(
        os.environ.get("TERNUXX_STATE_DIR", base_home / ".local/share/ternuxx"))
    try:
        import graphics_manager
        env = graphics_manager.native_process_environment(
            home=str(base_home), state_dir=str(runtime_state), process_env=env)
    except ImportError:
        pass
    # Never let an inherited path select an arbitrary native library.
    env.pop("GGML_BACKEND_PATH", None)
    actual_prefix = prefix or env.get("PREFIX")
    if actual_prefix:
        backend = Path(actual_prefix) / "lib/libggml-vulkan.so"
        try:
            info = backend.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid():
                env["GGML_BACKEND_PATH"] = str(backend)
        except OSError:
            pass
    return env


def gpu_status(*, prefix: str | None = None, home: Path | None = None,
               state_dir: str | Path | None = None) -> dict[str, object]:
    """List only Vulkan inference devices reported by the installed llama.cpp runtime."""
    runtime = _runtime(prefix)
    if not runtime:
        return {"available": False, "backend": "Vulkan", "devices": [],
                "reason": "llama-cli is unavailable"}
    try:
        result = subprocess.run([runtime, "--list-devices"], capture_output=True, text=True,
                                timeout=10, check=False,
                                env=_gpu_runtime_env(prefix=prefix, home=home, state_dir=state_dir))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "backend": "Vulkan", "devices": [],
                "reason": f"llama.cpp device listing failed ({type(exc).__name__})"}
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    devices = []
    for line in combined.splitlines():
        match = re.match(r"^\s*([A-Za-z][A-Za-z0-9_.-]{0,63}):\s*(.+?)\s*$", line)
        if match and match.group(1).casefold().startswith("vulkan"):
            devices.append({"id": match.group(1), "name": match.group(2)[:160]})
    available = result.returncode == 0 and bool(devices)
    return {"available": available, "backend": "Vulkan", "devices": devices,
            "runtime": runtime, "exit_code": result.returncode,
            "reason": None if available else "no Vulkan inference device reported; review `tx ai runtime preview vulkan` and the Native graphics provider"}


def preview(action: str = "install", *, home: Path | None = None,
            state_dir: str | Path | None = None, spec: ModelSpec = MODEL) -> dict[str, object]:
    if action not in {"install", "remove"}:
        raise InferenceError("unsupported model action")
    home = home or Path.home()
    target = model_path(home=home, state_dir=state_dir, spec=spec)
    payload = {"action": action, "model_id": spec.model_id, "url": spec.url,
               "target": str(target), "size_bytes": spec.size_bytes,
               "sha256": spec.sha256, "license": spec.license}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    current = target.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    try:
        available_bytes = shutil.disk_usage(current).free
    except OSError:
        available_bytes = None
    return {**payload, "plan_id": hashlib.sha256(encoded).hexdigest()[:24],
            "read_only": True, "network_required": action == "install",
            "available_bytes": available_bytes,
            "space_check": ("sufficient" if available_bytes is not None and available_bytes >= spec.size_bytes
                            else "insufficient" if available_bytes is not None else "unknown")}


def _private_models_dir(target: Path) -> None:
    _check_owned_path(target.parent)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _check_owned_path(target.parent, allow_missing=False)
    os.chmod(target.parent, 0o700)


@contextmanager
def _model_lock(models_dir: Path):
    _check_owned_path(models_dir, allow_missing=False)
    directory_info = models_dir.lstat()
    if not stat.S_ISDIR(directory_info.st_mode) or directory_info.st_mode & 0o077:
        raise InferenceError("model directory permissions must be private")
    lock_path = models_dir / ".model-operation.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError as exc:
        raise InferenceError("cannot open the private model operation lock") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise InferenceError("model operation lock is unsafe")
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise InferenceError("another model operation is active") from exc
        yield
    finally:
        os.close(fd)


def _recover_partial_downloads(models_dir: Path, spec: ModelSpec) -> int:
    recovered = 0
    for temporary in models_dir.glob(f".{spec.filename}.*.part"):
        try:
            info = temporary.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise InferenceError("stale model download path is unsafe; it was preserved")
        temporary.unlink()
        recovered += 1
    return recovered


def install_model(*, plan_id: str, confirmed: str, home: Path | None = None,
                  state_dir: str | Path | None = None, spec: ModelSpec = MODEL,
                  opener: Callable[..., BinaryIO] = urllib.request.urlopen,
                  cancel_event: threading.Event | None = None,
                  progress: Callable[[int, int], None] | None = None) -> dict[str, object]:
    plan = preview("install", home=home, state_dir=state_dir, spec=spec)
    if plan_id != plan["plan_id"] or confirmed != "DOWNLOAD":
        raise InferenceError("exact current preview ID and DOWNLOAD confirmation are required")
    target = Path(str(plan["target"]))
    _private_models_dir(target)
    if plan.get("space_check") != "sufficient":
        raise InferenceError("free storage cannot be confirmed as sufficient for the pinned model")
    with _model_lock(target.parent):
        recovered_partials = _recover_partial_downloads(target.parent, spec)
        if target.exists():
            if _valid_model(target, spec):
                return {"installed": True, "already_present": True, "path": str(target),
                        "sha256": spec.sha256, "recovered_partial_downloads": recovered_partials}
            raise InferenceError("existing model is invalid; it was preserved")
        temporary = target.parent / f".{spec.filename}.{os.getpid()}.part"
        return _download_and_install(target, temporary, spec, opener=opener,
                                     cancel_event=cancel_event, progress=progress,
                                     recovered_partials=recovered_partials)


def _download_and_install(target: Path, temporary: Path, spec: ModelSpec, *,
                          opener: Callable[..., BinaryIO], cancel_event: threading.Event | None,
                          progress: Callable[[int, int], None] | None,
                          recovered_partials: int) -> dict[str, object]:
    temporary = target.parent / f".{spec.filename}.{os.getpid()}.part"
    digest = hashlib.sha256()
    received = 0
    try:
        if target.exists():
            raise InferenceError("model appeared during installation; refusing to overwrite")
        request = urllib.request.Request(spec.url, headers={"User-Agent": "Ternuxx/0.1.0 CPU model installer"})
        with opener(request, timeout=30) as response, temporary.open("xb") as output:
            while True:
                if cancel_event and cancel_event.is_set():
                    raise InferenceError("model download cancelled")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > spec.size_bytes:
                    raise InferenceError("download exceeded the pinned model size")
                digest.update(chunk)
                output.write(chunk)
                if progress:
                    progress(received, spec.size_bytes)
            output.flush()
            os.fsync(output.fileno())
        if received != spec.size_bytes:
            raise InferenceError("download size did not match the pinned model")
        actual_digest = digest.hexdigest()
        if actual_digest != spec.sha256:
            raise InferenceError("download SHA-256 did not match the pinned model")
        os.chmod(temporary, 0o600)
        if target.exists():
            raise InferenceError("model appeared during installation; refusing to overwrite it")
        os.rename(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return {"installed": True, "already_present": False, "path": str(target),
                "size_bytes": received, "sha256": actual_digest, "license": spec.license,
                "recovered_partial_downloads": recovered_partials}
    except KeyboardInterrupt as exc:
        raise InferenceError("model download cancelled") from exc
    except OSError as exc:
        raise InferenceError("model download failed; temporary data was removed") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def remove_model(*, plan_id: str, confirmed: str, home: Path | None = None,
                 state_dir: str | Path | None = None, spec: ModelSpec = MODEL) -> dict[str, object]:
    plan = preview("remove", home=home, state_dir=state_dir, spec=spec)
    if plan_id != plan["plan_id"] or confirmed != "REMOVE":
        raise InferenceError("exact current preview ID and REMOVE confirmation are required")
    target = Path(str(plan["target"]))
    _check_owned_path(target, allow_missing=True)
    try:
        info = target.lstat()
    except FileNotFoundError:
        return {"removed": False, "already_absent": True, "path": str(target)}
    with _model_lock(target.parent):
        info = target.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise InferenceError("model path is unsafe; it was preserved")
        if not _valid_model(target, spec):
            raise InferenceError("model file does not match the pinned artifact; it was preserved")
        target.unlink()
    return {"removed": True, "path": str(target)}


def _response_text(stdout: str, prompt: str) -> str:
    """Return only the generated turn, stripping llama-cli's console framing."""
    lines = stdout.splitlines()
    try:
        start = lines.index("> " + prompt.strip()) + 1
    except ValueError as exc:
        raise InferenceError("llama-cli returned an unrecognized output format") from exc
    response = []
    for line in lines[start:]:
        if line.startswith("[ Prompt:") or line.strip() == "Exiting...":
            break
        response.append(line)
    result = "\n".join(response).strip()
    if not result:
        raise InferenceError("llama-cli returned an empty response")
    return result


def run_inference(prompt: str, *, home: Path | None = None, state_dir: str | Path | None = None,
                  prefix: str | None = None, max_tokens: int = DEFAULT_OUTPUT_TOKENS,
                  timeout: int = RUN_TIMEOUT_SECONDS, backend: str = "cpu",
                  device_id: str | None = None) -> dict[str, object]:
    if (not isinstance(prompt, str) or not prompt.strip() or "\n" in prompt or "\r" in prompt
            or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES):
        raise InferenceError("prompt must be one line of 1 to 4096 UTF-8 bytes")
    if type(max_tokens) is not int or not 1 <= max_tokens <= MAX_OUTPUT_TOKENS:
        raise InferenceError("output token limit must be between 1 and 128")
    if type(timeout) is not int or not 1 <= timeout <= RUN_TIMEOUT_SECONDS:
        raise InferenceError("timeout must be between 1 and 120 seconds")
    if backend not in {"cpu", "vulkan"}:
        raise InferenceError("backend must be cpu or vulkan")
    selected_device = None
    if backend == "vulkan":
        inventory = gpu_status(prefix=prefix, home=home, state_dir=state_dir)
        devices = inventory["devices"]
        if device_id is None and len(devices) == 1:
            selected_device = devices[0]["id"]
        elif isinstance(device_id, str) and _DEVICE_ID.fullmatch(device_id) and any(
                item["id"] == device_id for item in devices):
            selected_device = device_id
        else:
            raise InferenceError(inventory["reason"] or "select one exact Vulkan device from inference.gpu.status")
    elif device_id is not None:
        raise InferenceError("device_id is only valid with the Vulkan backend")
    prompt = prompt.strip()
    executable = _runtime(prefix)
    if not executable:
        raise InferenceError("llama-cli is unavailable; install the reviewed Termux llama-cpp package")
    model = model_path(home=home, state_dir=state_dir)
    _check_owned_path(model, allow_missing=True)
    if not model.exists():
        raise InferenceError("pinned model is missing, unsafe, or failed SHA-256 verification")
    with _model_lock(model.parent):
        if not _valid_model(model):
            raise InferenceError("pinned model is missing, unsafe, or failed SHA-256 verification")
        argv = [executable, "-m", str(model), "-ngl", "all" if backend == "vulkan" else "0",
                "--device", selected_device if selected_device else "none", "-t", "4", "-tb", "4",
                "-c", "512", "-n", str(max_tokens), "--seed", "42", "--temp", "0",
                "--reasoning", "off", "--single-turn", "--simple-io", "--no-display-prompt",
                "--no-warmup", "-p", prompt]
        if backend == "vulkan":
            argv.extend(("-lv", "4"))  # Emit the info-level GPU offload proof without debug prompt traces.
        started = time.monotonic()
        completed = _execute_cpu(argv, timeout=timeout, prefix=prefix,
                                 env=_gpu_runtime_env(prefix=prefix, home=home, state_dir=state_dir)
                                 if backend == "vulkan" else None)
        elapsed = time.monotonic() - started
        if completed.returncode != 0:
            detail = " ".join((completed.stderr or completed.stdout).split())[:500]
            raise InferenceError(f"{backend.upper()} inference failed with exit {completed.returncode}: {detail}")
        gpu_layers = 0
        if backend == "vulkan":
            delegated = re.search(r"offloaded\s+(\d+)\s*/\s*(\d+)\s+layers?\s+to\s+GPU",
                                  completed.stderr or "", re.I)
            if (not delegated or int(delegated.group(1)) <= 0
                    or int(delegated.group(1)) != int(delegated.group(2))):
                raise InferenceError("Vulkan runtime exited without verifiable complete GPU layer offload")
            gpu_layers = int(delegated.group(1))
            gpu_total_layers = int(delegated.group(2))
        else:
            gpu_total_layers = 0
        return {"backend": "CPU" if backend == "cpu" else "Vulkan", "device_id": selected_device,
                "gpu_layers": gpu_layers, "gpu_total_layers": gpu_total_layers,
                "elapsed_seconds": round(elapsed, 3), "model_id": MODEL.model_id,
                "output": _response_text(completed.stdout, prompt), "exit_code": completed.returncode,
                "max_output_tokens": max_tokens}


def _execute_cpu(argv: list[str], *, timeout: int, prefix: str | None,
                 env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    process = None
    try:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=env or _runtime_env(prefix), start_new_session=True)
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
        raise InferenceError("Inference timed out; its child process group was terminated") from exc
    except KeyboardInterrupt as exc:
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.communicate(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
        raise InferenceError("Inference cancelled; its child process group was terminated") from exc
    except OSError as exc:
        raise InferenceError("llama-cli could not be started") from exc
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pinned Native Termux CPU inference")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    plan = commands.add_parser("preview")
    plan.add_argument("action", choices=("install", "remove"), default="install", nargs="?")
    install = commands.add_parser("install")
    install.add_argument("--plan-id", required=True)
    install.add_argument("--confirm", required=True)
    remove = commands.add_parser("remove")
    remove.add_argument("--plan-id", required=True)
    remove.add_argument("--confirm", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--max-tokens", type=int, default=DEFAULT_OUTPUT_TOKENS)
    run_parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    run_parser.add_argument("--device", help="exact Vulkan device ID from --list-devices")
    run_parser.add_argument("--stdin", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status()
        elif args.command == "preview":
            result = preview(args.action)
        elif args.command == "install":
            last_percent = [-1]
            def report_progress(received: int, total: int) -> None:
                percent = min(100, received * 100 // max(total, 1))
                if percent >= last_percent[0] + 5 or percent == 100:
                    print(f"CPU model download: {percent}%", file=sys.stderr, flush=True)
                    last_percent[0] = percent
            result = install_model(plan_id=args.plan_id, confirmed=args.confirm, progress=report_progress)
        elif args.command == "remove":
            result = remove_model(plan_id=args.plan_id, confirmed=args.confirm)
        else:
            prompt = sys.stdin.read(MAX_PROMPT_BYTES + 1) if args.stdin else ""
            result = run_inference(prompt, max_tokens=args.max_tokens, backend=args.backend, device_id=args.device)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))
        return 0
    except InferenceError as exc:
        print(json.dumps({"ok": False, "error": {"code": "inference_failed", "message": str(exc)}},
                         ensure_ascii=False), file=sys.stderr if args.command == "run" else sys.stdout)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
