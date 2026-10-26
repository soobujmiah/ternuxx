"""Shared, provider-aware graphics inventory and bounded verification."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path


def _run(argv: list[str], env: dict[str, str], timeout: int = 20) -> tuple[int, str]:
    try:
        result = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, type(exc).__name__
    return result.returncode, result.stdout[-12000:]


def _failure_detail(output: str) -> str | None:
    """Return one bounded failure line without copying arbitrary tool output into API results."""
    for line in output.splitlines():
        candidate = line.strip()
        upper = candidate.upper()
        if ("CANNOT LINK EXECUTABLE" in upper or upper.startswith(("ERROR:", "ERROR "))
                or upper.startswith(("FATAL:", "FATAL "))):
            return candidate[:512]
    return None


def _candidate_hashes(repo_root: str) -> dict[str, str]:
    manifest = Path(repo_root) / "config/graphics/native-kgsl.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        hashes = data.get("verified_files")
    except (OSError, ValueError, AttributeError) as exc:
        raise ValueError("qualified KGSL profile manifest is unavailable") from exc
    if data.get("schema_version") != 1 or data.get("provider") != "native-termux-bionic" or not isinstance(hashes, dict):
        raise ValueError("qualified KGSL profile manifest is invalid")
    if any(not isinstance(key, str) or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
           for key, value in hashes.items()):
        raise ValueError("qualified KGSL profile hashes are invalid")
    return hashes


def _candidate_paths(state_dir: str) -> tuple[str, str]:
    root = Path(state_dir) / "graphics/providers/native-mesa-0219ff84"
    prefix = root / "extracted/data/data/com.termux/files/usr"
    return str(prefix), str(root / "freedreno-isolated.json")


def _termux_freedreno_paths(prefix: str) -> tuple[str, str]:
    return (os.path.join(prefix, "lib/libvulkan_freedreno.so"),
            os.path.join(prefix, "share/vulkan/icd.d/freedreno_icd.aarch64.json"))


def _termux_freedreno_ready(prefix: str) -> tuple[bool, str | None]:
    library, icd = _termux_freedreno_paths(prefix)
    required = [os.path.join(prefix, "lib/dri/libdril_dri.so"), library, icd]
    try:
        if not all(stat.S_ISREG(os.lstat(path).st_mode) and not os.path.islink(path) for path in required):
            return False, "Termux Mesa or Freedreno ICD files are missing or unsafe"
        gallium = [path for path in Path(prefix, "lib").glob("libgallium-*.so")
                   if path.is_file() and not path.is_symlink()]
        if len(gallium) != 1:
            return False, "Termux Mesa Gallium runtime is missing or ambiguous"
        manifest = json.loads(Path(icd).read_text(encoding="utf-8"))
        library_path = manifest.get("ICD", {}).get("library_path")
        if not isinstance(library_path, str):
            return False, "Termux Freedreno ICD descriptor is malformed"
        if os.path.isabs(library_path):
            if os.path.realpath(library_path) != os.path.realpath(library):
                return False, "Termux Freedreno ICD points outside its package library"
        elif library_path != "libvulkan_freedreno.so":
            return False, "Termux Freedreno ICD names an unexpected library"
    except (OSError, ValueError, AttributeError):
        return False, "Termux Mesa or Freedreno ICD files are unavailable"
    return True, None


def _termux_freedreno_device(prefix: str) -> tuple[bool, str | None, str | None]:
    """Require the installed Termux ICD to enumerate a supported Vulkan device."""
    env = dict(os.environ)
    env["PREFIX"] = prefix
    env["PATH"] = os.path.join(prefix, "bin") + os.pathsep + env.get("PATH", "")
    env["LD_LIBRARY_PATH"] = os.path.join(prefix, "lib")
    env["VK_ICD_FILENAMES"] = _termux_freedreno_paths(prefix)[1]
    code, output = _run(["vulkaninfo", "--summary"], env, 15)
    if code == 127:
        return False, None, "vulkaninfo is not installed; Freedreno device support is unverified"
    device = next((match.group(1).strip() for line in output.splitlines()
                   if (match := re.search(r"deviceName\s*=\s*(.*)", line))), None)
    if code == 0 and device:
        return True, device, None
    detail = next((line.strip()[:384] for line in output.splitlines()
                   if re.search(r"unsupported|incompatible.driver|failed to detect any valid GPUs", line, re.I)), None)
    return False, device, detail or "Freedreno ICD did not enumerate a supported Vulkan device"


def _native_env(*, home: str, state_dir: str, process_env: dict[str, str]) -> dict[str, str]:
    env = dict(process_env)
    termux_prefix = process_env.get("PREFIX")
    if termux_prefix and os.path.isabs(termux_prefix):
        # Launchers may inject an incompatible host libc++ before Termux's
        # Bionic runtime. Keep inherited paths available, but resolve Native
        # graphics tools against the active Termux runtime first.
        runtime_lib = os.path.join(termux_prefix, "lib")
        inherited = env.get("LD_LIBRARY_PATH", "").split(os.pathsep)
        env["LD_LIBRARY_PATH"] = os.pathsep.join(
            path for index, path in enumerate([runtime_lib, *inherited])
            if path and path not in [runtime_lib, *inherited][:index]
        )
    session = Path(state_dir) / "session.json"
    try:
        data = json.loads(session.read_text(encoding="utf-8"))
        display = data.get("display")
        if isinstance(display, str) and re.fullmatch(r":[0-9]{1,2}", display):
            env["DISPLAY"] = display
    except (OSError, ValueError, AttributeError):
        pass
    config = Path(state_dir) / "native-graphics-prefix"
    try:
        config_meta = config.lstat()
        prefix = config.read_text(encoding="utf-8").splitlines()[0]
        qualified_root, isolated = _candidate_paths(state_dir)
        if (config.is_file() and not config.is_symlink() and config_meta.st_uid == os.getuid()
                and stat.S_IMODE(config_meta.st_mode) == 0o600 and os.path.isabs(prefix)
                and os.path.realpath(prefix) == os.path.realpath(qualified_root)
                and os.path.isdir(prefix) and not os.path.islink(prefix)
                and os.path.isfile(os.path.join(prefix, "lib/dri/libdril_dri.so"))
                and os.path.isfile(os.path.join(prefix, "lib/libgallium-26.3.0-devel.so"))):
            # Keep the selected Mesa payload first, then the active Termux
            # runtime libraries, before inherited tool-specific paths. Codex and
            # other launchers may inject an incompatible libc++_shared.so into
            # LD_LIBRARY_PATH; placing that ahead of $PREFIX/lib breaks native
            # tools such as vulkaninfo even when the selected ICD is valid.
            library_paths = [prefix + "/lib"]
            termux_prefix = process_env.get("PREFIX")
            if termux_prefix and os.path.isabs(termux_prefix):
                library_paths.append(os.path.join(termux_prefix, "lib"))
            library_paths.extend(env.get("LD_LIBRARY_PATH", "").split(os.pathsep))
            env["LD_LIBRARY_PATH"] = os.pathsep.join(
                path for index, path in enumerate(library_paths) if path and path not in library_paths[:index]
            )
            for key in ("LIBGL_ALWAYS_SOFTWARE", "GALLIUM_DRIVER", "VK_DRIVER_FILES"):
                env.pop(key, None)
            env.update({
                "LIBGL_DRIVERS_PATH": prefix + "/lib/dri",
                "MESA_LOADER_DRIVER_OVERRIDE": "kgsl",
                "__EGL_VENDOR_LIBRARY_FILENAMES": prefix + "/share/glvnd/egl_vendor.d/50_mesa.json",
                "GLX_VENDOR_LIBRARY_NAME": "mesa",
            })
            # The candidate ICD manifest in private provider state is deliberately
            # generated only when its library is present at this checked path.
            try:
                manifest = json.loads(Path(isolated).read_text(encoding="utf-8"))
                library = manifest.get("ICD", {}).get("library_path")
                expected = os.path.join(prefix, "lib/libvulkan_freedreno.so")
                if library == expected and os.path.isfile(expected):
                    env["VK_ICD_FILENAMES"] = isolated
            except (OSError, ValueError, AttributeError):
                pass
    except (OSError, IndexError):
        pass
    backend_path = Path(state_dir) / "native-graphics-backend"
    candidate_path = Path(state_dir) / "native-graphics-prefix"
    try:
        metadata = backend_path.lstat()
        selected = backend_path.read_text(encoding="ascii")
        if (not candidate_path.exists() and stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode)
                and metadata.st_uid == os.getuid() and stat.S_IMODE(metadata.st_mode) == 0o600
                and selected == "termux-zink\n" and termux_prefix and os.path.isabs(termux_prefix)):
            ready, _reason = _termux_freedreno_ready(termux_prefix)
            if ready:
                _library, icd = _termux_freedreno_paths(termux_prefix)
                for key in ("LIBGL_ALWAYS_SOFTWARE", "VK_DRIVER_FILES"):
                    env.pop(key, None)
                env.update({"MESA_LOADER_DRIVER_OVERRIDE": "zink", "GALLIUM_DRIVER": "zink",
                            "TU_DEBUG": "noconform", "MESA_VK_WSI_DEBUG": "sw",
                            "VK_ICD_FILENAMES": icd})
    except (OSError, UnicodeError):
        pass
    if env.get("DISPLAY"):
        env.setdefault("XDG_RUNTIME_DIR", os.path.join(process_env.get("PREFIX", ""), "tmp"))
    return env


def native_process_environment(*, home: str, state_dir: str,
                               process_env: dict[str, str]) -> dict[str, str]:
    """Return the validated Native graphics environment for another workload."""
    return _native_env(home=home, state_dir=state_dir, process_env=process_env)


def _renderer_accelerated(renderer: str | None) -> bool | None:
    if not renderer:
        return None
    if re.search(r"llvmpipe|softpipe|swrast|software rasterizer", renderer, re.I):
        return False
    if re.search(r"adreno|turnip|freedreno|panfrost|mali|radeonsi|iris|nouveau", renderer, re.I):
        return True
    return None


def _gles_context(env: dict[str, str]) -> dict[str, object]:
    tool = shutil.which("es2_info", path=env.get("PATH"))
    if not tool:
        return {"status": "unavailable", "context_verified": False, "render_verified": False,
                "reason": "es2_info is not installed"}
    code, output = _run([tool], env, 15)
    renderer = next((line.split(":", 1)[1].strip() for line in output.splitlines()
                     if line.strip().startswith("GL_RENDERER:")), None)
    version = next((line.split(":", 1)[1].strip() for line in output.splitlines()
                    if line.strip().startswith("GL_VERSION:")), None)
    context_ok = code == 0 and bool(renderer and version)
    return {"status": "context-verified" if context_ok else ("failed" if code != 127 else "unavailable"),
            "context_verified": context_ok, "render_verified": False, "renderer": renderer,
            "version": version, "accelerated": None,
            "proof": "GLES context initialization only; no draw or presentation verified; acceleration unverified",
            "exit_code": code}


def status(provider: str, *, home: str, state_dir: str, process_env: dict[str, str], prefix: str) -> dict[str, object]:
    if provider == "native":
        env = _native_env(home=home, state_dir=state_dir, process_env=process_env)
        display = env.get("DISPLAY")
        gl = {"status": "unavailable", "renderer": None, "accelerated": None}
        if display and shutil.which("glxinfo", path=env.get("PATH")):
            code, output = _run([shutil.which("glxinfo", path=env.get("PATH")) or "glxinfo", "-B"], env)
            renderer = next((line.split(":", 1)[1].strip() for line in output.splitlines()
                             if line.strip().startswith("OpenGL renderer string:")), None)
            accel = next((line.split(":", 1)[1].strip().lower() == "yes" for line in output.splitlines()
                          if line.strip().startswith("Accelerated:")), None)
            gl = {"status": "verified" if code == 0 and renderer else "failed", "renderer": renderer,
                  "accelerated": accel, "display": display}
        vk = {"status": "unavailable", "device": None, "proof": "not-queried"}
        vkinfo = shutil.which("vulkaninfo", path=env.get("PATH"))
        if vkinfo:
            code, output = _run([vkinfo, "--summary"], env, 15)
            device = next((m.group(1).strip() for line in output.splitlines()
                           if (m := re.search(r"deviceName\s*=\s*(.*)", line))), None)
            vk = {"status": "enumerated" if code == 0 and device else "unavailable",
                  "device": device, "proof": "device-enumeration-only; no draw verified"}
        gles = _gles_context(env) if display else {"status": "unavailable", "context_verified": False,
                                                   "render_verified": False, "reason": "no active display"}
        selected_backend = "system"
        backend_reason = None
        candidate_path = Path(state_dir) / "native-graphics-prefix"
        if candidate_path.exists() or candidate_path.is_symlink():
            selected_backend = "kgsl-freedreno"
        else:
            selected_path = Path(state_dir) / "native-graphics-backend"
            try:
                selected_meta = selected_path.lstat()
                selected = selected_path.read_text(encoding="ascii")
                if (stat.S_ISREG(selected_meta.st_mode) and not stat.S_ISLNK(selected_meta.st_mode)
                        and selected_meta.st_uid == os.getuid() and stat.S_IMODE(selected_meta.st_mode) == 0o600
                        and selected == "termux-zink\n"):
                    ready, backend_reason = _termux_freedreno_ready(prefix)
                    selected_backend = "termux-zink" if ready else "termux-zink-unavailable"
                elif selected_path.exists() or selected_path.is_symlink():
                    selected_backend = "invalid-selection"
            except FileNotFoundError:
                pass
            except (OSError, UnicodeError):
                selected_backend = "invalid-selection"
        return {"provider": provider, "display": display, "opengl": gl, "gles": gles, "vulkan": vk,
                "selected_backend": selected_backend, "backend_reason": backend_reason,
                "saved_candidate": os.path.isfile(os.path.join(state_dir, "native-graphics-prefix")),
                "provider_boundary": "native Termux/Bionic"}
    if provider != "native":
        raise ValueError("Ternuxx supports Native Termux graphics only")
    raise ValueError("only the Native Termux provider is supported")


def _gles_draw(env: dict[str, str], *, repo_root: str, state_dir: str) -> dict[str, object]:
    source = Path(repo_root) / "docs/evidence/graphics/native-mesa-0219ff84/offscreen-gles.c"
    try:
        meta = source.lstat()
        if not source.is_file() or source.is_symlink() or meta.st_size > 32_768:
            return {"status": "unavailable", "context_verified": False, "render_verified": False,
                    "reason": "tracked GLES verification source is missing or unsafe"}
        source_text = source.read_text(encoding="utf-8")
    except OSError:
        return {"status": "unavailable", "context_verified": False, "render_verified": False,
                "reason": "tracked GLES verification source is unavailable"}
    if "glDrawArrays" not in source_text or "glFinish" not in source_text or "eglCreatePbufferSurface" not in source_text:
        return {"status": "unavailable", "context_verified": False, "render_verified": False,
                "reason": "tracked GLES source does not meet the draw-verification contract"}
    compiler = shutil.which("clang", path=env.get("PATH"))
    if not compiler:
        return {"status": "unavailable", "context_verified": False, "render_verified": False,
                "reason": "clang is not installed; cannot build the GLES verifier"}
    try:
        state = Path(state_dir)
        state_meta = state.lstat()
        if (not state.is_dir() or state.is_symlink() or state_meta.st_uid != os.getuid()
                or stat.S_IMODE(state_meta.st_mode) != 0o700):
            return {"status": "unavailable", "context_verified": False, "render_verified": False,
                    "reason": "Ternuxx state directory is not private"}
        with tempfile.TemporaryDirectory(prefix="gles-verify-", dir=str(state)) as temp_dir:
            binary = os.path.join(temp_dir, "offscreen-gles")
            compile_code, compile_output = _run(
                [compiler, "-O2", "-Wall", "-Wextra", "-o", binary, str(source), "-lEGL", "-lGLESv2"],
                env, 45)
            if compile_code != 0:
                return {"status": "unavailable" if compile_code == 127 else "failed",
                        "context_verified": False, "render_verified": False,
                        "compile_exit_code": compile_code, "reason": "GLES verifier compilation failed",
                        "detail": compile_output[-2000:]}
            code, output = _run([binary, "1280", "720", "5"], env, 15)
    except OSError:
        return {"status": "unavailable", "context_verified": False, "render_verified": False,
                "reason": "private GLES verifier workspace is unavailable"}
    renderer_match = re.search(r"renderer=([^|\n]+)", output)
    version_match = re.search(r"GLES=([^|\n]+)", output)
    frames_match = re.search(r"frames=(\d+)", output)
    fps_match = re.search(r"throughput=([0-9]+(?:\.[0-9]+)?) frames/sec", output)
    renderer = renderer_match.group(1).strip() if renderer_match else None
    version = version_match.group(1).strip() if version_match else None
    frames = int(frames_match.group(1)) if frames_match else 0
    throughput = float(fps_match.group(1)) if fps_match else 0.0
    context_ok = bool(version and re.search(r"OpenGL ES 3\.", version) and renderer)
    rendered = code == 0 and context_ok and frames > 0 and throughput > 0
    return {"status": "rendered" if rendered else ("failed" if code != 127 else "unavailable"),
            "context_verified": context_ok, "render_verified": rendered, "renderer": renderer,
            "version": version, "accelerated": _renderer_accelerated(renderer), "frames": frames or None,
            "throughput_fps": throughput or None, "resolution": "1280x720", "duration_seconds": 5,
            "display": "surfaceless EGL pbuffer", "exit_code": code,
            "proof": "GLES 3 shader draw with glFinish per frame" if rendered else "GLES draw was not verified"}


def verify(provider: str, api: str, *, home: str, state_dir: str, process_env: dict[str, str], prefix: str,
           repo_root: str) -> dict[str, object]:
    if provider != "native":
        raise ValueError("Ternuxx supports Native Termux graphics only")
    env = _native_env(home=home, state_dir=state_dir, process_env=process_env)
    if api == "gles":
        result = _gles_draw(env, repo_root=repo_root, state_dir=state_dir)
        return {"provider": provider, "api": api, **result}
    if api == "opengl":
        tool = shutil.which("glmark2", path=env.get("PATH"))
        if not tool:
            return {"provider": provider, "api": api, "status": "unavailable", "reason": "glmark2 is not installed"}
        display = env.get("DISPLAY")
        on_screen = isinstance(display, str) and re.fullmatch(r":(?:[0-9]|10)", display)
        workload = [tool]
        if not on_screen:
            workload.extend(["--off-screen", "--size", "1280x720"])
        workload.extend(["--frame-end", "finish", "--swap-mode", "immediate",
                         "--benchmark", "build:duration=4.0",
                         "--benchmark", "texture:duration=4.0",
                         "--benchmark", "shading:duration=4.0"])
        code, output = _run(workload, env, 30)
        renderer = next((line.split(":", 1)[1].strip() for line in output.splitlines()
                         if line.strip().startswith("GL_RENDERER:")), None)
        score = next((line.split(":", 1)[1].strip() for line in output.splitlines()
                      if line.strip().startswith("glmark2 Score:")), None)
        if code == 0 and renderer:
            return {"provider": provider, "api": api, "status": "rendered", "render_verified": True,
                    "renderer": renderer, "accelerated": _renderer_accelerated(renderer),
                    "score": score, "display": display if on_screen else "off-screen",
                    "render_target": "x11-window" if on_screen else "off-screen",
                    "exit_code": code,
                    "fallback_order": ["llvmpipe", "softpipe"], "fallback_attempts": []}
        attempts = []
        fallback_workload = [tool, "--off-screen", "--size", "1280x720",
                             "--frame-end", "finish", "--swap-mode", "immediate",
                             "--benchmark", "build:duration=4.0",
                             "--benchmark", "texture:duration=4.0",
                             "--benchmark", "shading:duration=4.0"]
        for backend in ("llvmpipe", "softpipe"):
            software_env = dict(env)
            software_env.pop("MESA_LOADER_DRIVER_OVERRIDE", None)
            software_env.pop("VK_ICD_FILENAMES", None)
            software_env["LIBGL_ALWAYS_SOFTWARE"] = "true"
            software_env["GALLIUM_DRIVER"] = backend
            fallback_code, fallback_output = _run(fallback_workload, software_env, 30)
            fallback_renderer = next((line.split(":", 1)[1].strip() for line in fallback_output.splitlines()
                                      if line.strip().startswith("GL_RENDERER:")), None)
            fallback_score = next((line.split(":", 1)[1].strip() for line in fallback_output.splitlines()
                                   if line.strip().startswith("glmark2 Score:")), None)
            renderer_matches = bool(fallback_renderer and re.search(rf"\b{backend}\b", fallback_renderer, re.I))
            fallback_ok = fallback_code == 0 and renderer_matches
            attempts.append({"backend": backend, "status": "rendered" if fallback_ok else "failed",
                             "renderer": fallback_renderer, "score": fallback_score,
                             "exit_code": fallback_code})
            if fallback_ok:
                return {"provider": provider, "api": api, "status": "fallback-rendered",
                        "render_verified": True, "renderer": fallback_renderer,
                        "accelerated": False, "score": fallback_score, "display": "off-screen",
                        "render_target": "off-screen", "exit_code": fallback_code,
                        "primary_attempt": {"status": "failed", "renderer": renderer,
                                            "display": display if on_screen else "off-screen",
                                            "render_target": "x11-window" if on_screen else "off-screen",
                                            "exit_code": code},
                        "fallback_order": ["llvmpipe", "softpipe"], "fallback_attempts": attempts}
        return {"provider": provider, "api": api, "status": "failed", "render_verified": False,
                "renderer": attempts[-1]["renderer"] if attempts else renderer,
                "accelerated": None, "display": "off-screen", "render_target": "off-screen", "exit_code": code,
                "primary_attempt": {"status": "failed", "renderer": renderer,
                                    "display": display if on_screen else "off-screen",
                                    "render_target": "x11-window" if on_screen else "off-screen",
                                    "exit_code": code},
                "fallback_order": ["llvmpipe", "softpipe"], "fallback_attempts": attempts}
    if api == "vulkan":
        tool = shutil.which("vulkaninfo", path=env.get("PATH"))
        if not tool:
            return {"provider": provider, "api": api, "status": "unavailable", "render_verified": False,
                    "reason": "vulkaninfo is not installed"}
        code, output = _run([tool, "--summary"], env, 15)
        device = next((m.group(1).strip() for line in output.splitlines()
                       if (m := re.search(r"deviceName\s*=\s*(.*)", line))), None)
        if code != 0 or not device:
            return {"provider": provider, "api": api, "status": "unavailable", "render_verified": False,
                    "device": device, "enumeration_exit_code": code,
                    "diagnostic": _failure_detail(output),
                    "proof": "Vulkan device enumeration failed; no draw was attempted"}
        cube = shutil.which("vkcube", path=env.get("PATH"))
        if not cube:
            return {"provider": provider, "api": api, "status": "enumerated", "render_verified": False,
                    "device": device, "proof": "Vulkan device enumerated; vkcube is not installed"}
        if not env.get("DISPLAY"):
            return {"provider": provider, "api": api, "status": "enumerated", "render_verified": False,
                    "device": device, "proof": "Vulkan device enumerated; no active X11 display for bounded vkcube draw"}
        draw_code, draw_output = _run([cube, "--c", "120"], env, 20)
        selected = next((m.group(1).strip() for line in draw_output.splitlines()
                         if (m := re.search(r"Selected GPU \d+: (.*?), type:", line))), None)
        same_device = bool(selected and re.sub(r"\s+", " ", selected).casefold()
                           == re.sub(r"\s+", " ", device).casefold())
        rendered = draw_code == 0 and same_device
        return {"provider": provider, "api": api, "status": "rendered" if rendered else "failed",
                "render_verified": rendered, "device": device, "draw_renderer": selected,
                "draw_frames": 120 if rendered else None, "display": env["DISPLAY"],
                "enumeration_exit_code": code, "draw_exit_code": draw_code,
                "diagnostic": None if rendered else _failure_detail(draw_output),
                "proof": "bounded vkcube X11 draw; selected GPU must match vulkaninfo device" if rendered
                         else "vkcube draw failed or selected a different device; no Vulkan success claimed"}
    raise ValueError("api must be opengl, gles, or vulkan")


def configure_native(backend: str, *, home: str, state_dir: str, repo_root: str,
                    prefix: str | None = None) -> dict[str, object]:
    """Select a validated Native stack for future desktop starts."""
    import stat
    import tempfile
    import desktop_session_state
    config = Path(state_dir) / "native-graphics-prefix"
    backend_file = Path(state_dir) / "native-graphics-backend"
    candidate, manifest_path = _candidate_paths(state_dir)
    candidate = os.path.realpath(candidate)
    if backend not in {"kgsl-freedreno", "termux-zink", "system"}:
        raise ValueError("backend must be kgsl-freedreno, termux-zink, or system")
    desktop_session_state.ensure_state_dir(Path(home), Path(state_dir))

    def remove_candidate() -> bool:
        try:
            metadata = config.lstat()
        except FileNotFoundError:
            return False
        if (not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise ValueError("saved graphics candidate selection is unsafe; it was preserved")
        try:
            saved = config.read_text(encoding="utf-8").splitlines()[0]
        except (OSError, IndexError):
            raise ValueError("saved graphics candidate selection is malformed; it was preserved")
        if saved != candidate:
            raise ValueError("saved graphics selection is not the qualified candidate; it was preserved")
        config.unlink()
        return True

    def read_backend_selection() -> bool:
        try:
            metadata = backend_file.lstat()
        except FileNotFoundError:
            return False
        if (not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600
                or backend_file.read_text(encoding="ascii") != "termux-zink\n"):
            raise ValueError("saved Native graphics selection is unsafe or unknown; it was preserved")
        return True

    def write_backend_selection() -> bool:
        current = read_backend_selection()
        if current:
            return False
        fd, temp_name = tempfile.mkstemp(prefix=".native-graphics-backend-", dir=state_dir)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="ascii") as stream:
                stream.write("termux-zink\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, backend_file)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
        return True

    if backend == "system":
        changed = remove_candidate()
        if read_backend_selection():
            backend_file.unlink()
            changed = True
        return {"provider": "native", "backend": backend, "changed": changed,
                "applies": "future desktop starts"}

    if backend == "termux-zink":
        prefix = prefix or os.environ.get("PREFIX", "")
        ready, reason = _termux_freedreno_ready(prefix) if prefix and os.path.isabs(prefix) else (
            False, "Native Termux PREFIX is unavailable")
        if not ready:
            raise ValueError(reason or "Termux Freedreno ICD is unavailable")
        supported, device, probe_reason = _termux_freedreno_device(prefix)
        if not supported:
            raise ValueError("Termux Freedreno did not enumerate a supported Vulkan GPU: "
                             + (probe_reason or "device unavailable"))
        changed = remove_candidate()
        changed = write_backend_selection() or changed
        return {"provider": "native", "backend": backend, "changed": changed,
                "applies": "future desktop starts", "icd": _termux_freedreno_paths(prefix)[1],
                "device": device}

    required = ["lib/dri/libdril_dri.so", "lib/libgallium-26.3.0-devel.so",
                "share/glvnd/egl_vendor.d/50_mesa.json", "lib/libvulkan_freedreno.so"]
    expected_hashes = _candidate_hashes(repo_root)
    for item in required:
        path = Path(candidate) / item
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise ValueError("qualified KGSL candidate is incomplete") from exc
        expected = expected_hashes.get(item)
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or not expected:
            raise ValueError("qualified KGSL candidate contains an unsafe or unpinned file")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("qualified KGSL candidate file hash does not match its profile")
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("qualified Turnip ICD manifest is unavailable") from exc
    if manifest.get("ICD", {}).get("library_path") != os.path.join(candidate, "lib/libvulkan_freedreno.so"):
        raise ValueError("Turnip ICD manifest does not match the qualified candidate")
    changed = read_backend_selection()
    if changed:
        backend_file.unlink()
    try:
        current_meta = config.lstat()
    except FileNotFoundError:
        current_meta = None
    if current_meta is not None and (not stat.S_ISREG(current_meta.st_mode) or stat.S_ISLNK(current_meta.st_mode)
                                     or current_meta.st_uid != os.getuid()
                                     or stat.S_IMODE(current_meta.st_mode) != 0o600):
        raise ValueError("saved graphics selection is unsafe; it was preserved")
    already_selected = current_meta is not None and config.read_text(encoding="utf-8") == candidate + "\n"
    if not already_selected:
        fd, temp_name = tempfile.mkstemp(prefix=".native-graphics-", dir=state_dir)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(candidate + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, config)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
        changed = True
    return {"provider": "native", "backend": backend, "changed": changed,
            "applies": "future desktop starts"}
