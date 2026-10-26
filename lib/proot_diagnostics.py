"""Read-only discovery and qualification of Native Termux PRoot guests."""
from __future__ import annotations

import json
import os
import re
import errno
import stat
from pathlib import Path
import shutil
import subprocess
from typing import Callable

import proot_fresh_setup
import proot_profiles


_ANSI = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_DISTRO = re.compile(r"^\s*\*\s+([A-Za-z0-9][A-Za-z0-9_-]{0,31})\s*$")
_GUEST_USER = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


class GuestProfileError(ValueError):
    """A PRoot guest profile cannot be safely used for bounded discovery."""


def _read_proot_guest_passwd(*, distro: str, prefix: str) -> tuple[Path, list[str]]:
    valid_upstream_name = isinstance(distro, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", distro)
    valid_replay_alias = isinstance(distro, str) and re.fullmatch(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", distro)
    if not (valid_upstream_name or valid_replay_alias):
        raise GuestProfileError("distro name is invalid")
    root = Path(prefix) / "var/lib/proot-distro/containers" / distro / "rootfs"
    passwd = root / "etc/passwd"
    try:
        for directory in (root.parent.parent, root.parent, root, root / "etc"):
            info = directory.lstat()
            if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                    or info.st_uid != os.getuid()):
                raise GuestProfileError("installed rootfs identity is unsafe")
        info = passwd.lstat()
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.getuid() or info.st_size > 1024 * 1024):
            raise GuestProfileError("guest account database identity is unsafe")
        lines = passwd.read_text(encoding="utf-8").splitlines()
    except GuestProfileError:
        raise
    except (OSError, UnicodeError) as exc:
        raise GuestProfileError("installed guest account database is unavailable") from exc
    return root, lines


def resolve_proot_guest_user(*, distro: str, prefix: str) -> str:
    """Resolve the receipted user for managed guests, otherwise inspect passwd."""
    if distro == "ubuntu":
        receipt = verify_managed_guest_alias(distro, prefix)
        user = receipt.get("guest_user")
        if isinstance(user, str) and _GUEST_USER.fullmatch(user) and user != "root":
            return user
        raise GuestProfileError("managed Ubuntu receipt has no ordinary guest account")
    _root, lines = _read_proot_guest_passwd(distro=distro, prefix=prefix)
    users = []
    for line in lines:
        fields = line.split(":")
        if len(fields) != 7:
            continue
        name, _password, uid_text, _gid, _gecos, home, shell = fields
        if (not _GUEST_USER.fullmatch(name) or name == "root" or not uid_text.isdecimal()
                or len(uid_text) > 5 or not 1000 <= int(uid_text) < 60000
                or home != f"/home/{name}" or not _valid_guest_shell(shell)):
            continue
        users.append(name)
    if len(users) != 1:
        raise GuestProfileError("guest account is ambiguous; pass --user NAME")
    return users[0]


def _valid_guest_shell(shell: str) -> bool:
    return (isinstance(shell, str)
            and re.fullmatch(r"/[A-Za-z0-9_.+-]+(?:/[A-Za-z0-9_.+-]+)*", shell) is not None
            and all(part not in {".", ".."} for part in shell.split("/")[1:]))


def resolve_proot_guest_shell(*, distro: str, user: str, prefix: str) -> str:
    """Read one account's absolute shell path without entering or changing its rootfs."""
    if not isinstance(user, str) or (user != "root" and not _GUEST_USER.fullmatch(user)):
        raise GuestProfileError("guest user name is invalid")
    _root, lines = _read_proot_guest_passwd(distro=distro, prefix=prefix)
    matches = []
    for line in lines:
        fields = line.split(":")
        if len(fields) == 7 and fields[0] == user:
            matches.append(fields[6])
    if len(matches) != 1 or not _valid_guest_shell(matches[0]):
        raise GuestProfileError("guest login shell is unavailable or ambiguous")
    return matches[0]


_DISPLAY = re.compile(r"^:(?:[0-9]|10)$")
_GUEST_SOURCE = "https://github.com/soobujmiah/ternux"
_PULSE_SERVER = "tcp:127.0.0.1:4713"
_PULSE_INFO_VALUE = re.compile(r"^[A-Za-z0-9_.:+-]{1,128}$")
_X11_DISPLAY_TOKEN = re.compile(r"^:(?:[0-9]|10)$")


def _native_pulse_cookie_path() -> Path | None:
    """Return the existing private cookie only when its owner/path is safe."""
    cookie = Path.home() / ".config" / "pulse" / "cookie"
    directory = cookie.parent
    try:
        directory_info = directory.lstat()
        cookie_info = cookie.lstat()
    except OSError:
        return None
    if (not stat.S_ISDIR(directory_info.st_mode) or directory_info.st_uid != os.getuid()
            or directory_info.st_mode & 0o077 or directory.is_symlink()
            or directory.absolute() != directory.resolve(strict=False)):
        return None
    if (not stat.S_ISREG(cookie_info.st_mode) or cookie_info.st_uid != os.getuid()
            or cookie_info.st_mode & 0o077 or cookie_info.st_size != 256
            or cookie.is_symlink() or cookie.absolute() != cookie.resolve(strict=False)):
        return None
    return cookie


def inspect_native_pulseaudio_endpoint(
        *, which: Callable[[str], str | None] = shutil.which,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        ) -> dict[str, str | None]:
    """Read native pactl endpoint state without starting a stream or service."""
    unknown = {"status": "unknown", "server_name": None, "default_sink": None}
    command = which("pactl")
    if not command:
        return {**unknown, "status": "unavailable"}
    try:
        cookie = str(Path.home() / ".config/pulse/cookie")
        result = runner([command, "--server", _PULSE_SERVER, "info"], capture_output=True, text=True,
                        timeout=5, check=False,
                        env={**os.environ, "PULSE_SERVER": _PULSE_SERVER,
                             "PULSE_COOKIE": cookie, "LC_ALL": "C"})
    except subprocess.TimeoutExpired:
        return unknown
    except OSError:
        return {**unknown, "status": "unavailable"}
    if result.returncode != 0:
        return {**unknown, "status": "unavailable"}
    if not isinstance(result.stdout, str):
        return unknown
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(":")
        if separator and key in {"Server Name", "Default Sink"}:
            value = value.strip()
            if _PULSE_INFO_VALUE.fullmatch(value):
                values[key] = value
    server_name = values.get("Server Name")
    if not server_name:
        return unknown
    return {"status": "available", "server_name": server_name,
            "default_sink": values.get("Default Sink")}


def inspect_termux_x11_process_displays(
        *, which: Callable[[str], str | None] = shutil.which,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        ) -> dict[str, object]:
    """Summarize visible Termux:X11 display arguments without returning PIDs/argv."""
    command = which("ps")
    if not command:
        return {"status": "unavailable", "observed_displays": []}
    try:
        result = runner([command, "-A", "-o", "pid=,comm="],
                        capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unknown", "observed_displays": []}
    if result.returncode != 0 or not isinstance(getattr(result, "stdout", None), str):
        return {"status": "unknown", "observed_displays": []}

    candidate_pids: list[str] = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 1)
        if (len(fields) != 2 or not fields[0].isdigit()
                or fields[1].rsplit("/", 1)[-1] != "termux-x11"):
            continue
        candidate_pids.append(fields[0])
    if len(candidate_pids) > 8:
        return {"status": "unknown", "observed_displays": []}

    displays: set[str] = set()
    for pid in candidate_pids:
        try:
            args_result = runner([command, "-p", pid, "-o", "args="],
                                 capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "unknown", "observed_displays": []}
        if args_result.returncode != 0 or not isinstance(getattr(args_result, "stdout", None), str):
            return {"status": "unknown", "observed_displays": []}
        arguments = args_result.stdout.split()
        displays.update(token for token in arguments if _X11_DISPLAY_TOKEN.fullmatch(token))
    return {"status": "available", "observed_displays": sorted(displays)}


def _installed_names(output: str) -> list[str] | None:
    clean = _ANSI.sub("", output).replace("\r", "")
    if any(line.strip().lower() == "no containers are installed."
           for line in clean.splitlines()):
        return []
    in_installed = False
    names: list[str] = []
    for line in clean.splitlines():
        value = line.strip()
        if value.lower() == "installed containers:":
            in_installed = True
            continue
        if not in_installed:
            continue
        if value.lower().startswith("log in with:"):
            break
        match = _DISTRO.fullmatch(line)
        if match:
            names.append(match.group(1).lower())
    if not in_installed:
        return None
    return sorted(set(names))


def inspect_host_proot_processes(*, proc_root: str | os.PathLike[str] = "/proc") -> dict[str, object]:
    """Observe readable host PRoot executables without inferring guest ownership."""
    root = Path(proc_root)
    matches: list[dict[str, object]] = []
    denied = False
    try:
        entries = list(root.iterdir())
    except OSError:
        return {"status": "unknown", "processes": [], "visibility": "unavailable",
                "ownership": "unverified"}
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        try:
            comm = (entry / "comm").read_text(errors="replace").strip()
            raw = (entry / "cmdline").read_bytes()
        except FileNotFoundError:
            continue  # Process exited during the bounded snapshot.
        except PermissionError:
            denied = True
            continue
        except OSError as exc:
            if exc.errno in {errno.ESRCH, errno.ENOENT}:
                continue
            if exc.errno in {errno.EACCES, errno.EPERM}:
                denied = True
            continue
        argv0 = raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")
        if comm != "proot" and Path(argv0).name != "proot":
            continue
        try:
            status_text = (entry / "status").read_text(errors="replace")
        except OSError:
            status_text = ""
            denied = True
        parent_match = re.search(r"^PPid:\s*(\d+)$", status_text, re.MULTILINE)
        matches.append({"pid": int(entry.name),
                        "parent_pid": int(parent_match.group(1)) if parent_match else None,
                        "association": "unverified"})
    visibility = "partial" if denied else "complete"
    status = "unknown" if denied and not matches else "observed" if matches else "none"
    return {"status": status, "processes": sorted(matches, key=lambda item: item["pid"]),
            "visibility": visibility, "ownership": "unverified"}


def _managed_replay_aliases(*, prefix: str, home: str, state_dir: str | None) -> list[str]:
    """List only receipt-verified Ternuxx distro aliases with matching rootfs identities."""
    state_path = state_dir or os.environ.get("TERNUXX_STATE_DIR") or str(Path(home) / ".local/share/ternuxx")
    try:
        setup_state = proot_fresh_setup._state_root(home, state_path, create=False)
        receipts = sorted(setup_state.glob("fresh-provider-ternuxx-replay-*.json"))
    except (OSError, ValueError):
        return []
    aliases = []
    for receipt_path in receipts:
        alias = receipt_path.name.removeprefix("fresh-provider-").removesuffix(".json")
        try:
            receipt = verify_managed_replay_alias(alias, prefix, home=home, state_dir=state_path)
            aliases.append(alias)
        except (OSError, ValueError, KeyError):
            continue
    return aliases


def inspect_installed(*, which: Callable[[str], str | None] = shutil.which,
                      runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
                      proc_root: str | os.PathLike[str] = "/proc",
                      prefix: str = "/data/data/com.termux/files/usr",
                      home: str | None = None, state_dir: str | None = None) -> dict[str, object]:
    process_observation = inspect_host_proot_processes(proc_root=proc_root)
    home_path = str(Path(home).expanduser()) if home is not None else str(Path.home())
    include_managed_replays = home is not None or state_dir is not None
    manager = which("proot-distro")
    if not manager:
        return {
            "component": "proot_distribution_inventory",
            "status": "unavailable",
            "manager_available": False,
            "installed_distributions": [],
            "ownership": "unverified",
            "guest_entered": False,
            "read_only": True,
            "host_proot_processes": process_observation,
        }
    try:
        result = runner([manager, "list"], stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        result = None
    names = (_installed_names(result.stdout) if isinstance(getattr(result, "stdout", None), str)
             else None) if result is not None and result.returncode == 0 else None
    if names is not None and include_managed_replays:
        names = sorted(set(names) | set(_managed_replay_aliases(
            prefix=prefix, home=home_path, state_dir=state_dir)))
    status = "unknown" if names is None else "installed" if names else "none"
    return {
        "component": "proot_distribution_inventory",
        "status": status,
        "manager_available": True,
        "installed_distributions": names or [],
        "ownership": "unverified",
        "guest_entered": False,
        "read_only": True,
        "host_proot_processes": process_observation,
    }



def _verification_result(*, status: str, display: str, backend: str,
                         distro: str = "debian", guest_entered: bool = False,
                         observed_display: str | None = None, x11: str = "unknown", audio: str = "unknown",
                         renderer: str | None = None, renderer_class: str = "unavailable",
                         gles_context: str = "unknown", gles_renderer: str | None = None,
                         gles_version: str | None = None, glx_draw: str = "unavailable",
                         glx_draw_frames: int = 0, glx_draw_renderer: str | None = None,
                         vulkan_draw: str = "unavailable", vulkan_draw_device: str | None = None,
                         dri3_extension: str = "unknown", blockers: list[str] | None = None,
                         native_pulseaudio_endpoint: dict[str, str | None] | None = None
                         ) -> dict[str, object]:
    return {
        "component": "proot_guest_diagnostics",
        "status": status,
        "distro": distro,
        "display": display,
        "requested_backend": backend,
        "pulse_server": _PULSE_SERVER,
        "guest_entered": guest_entered,
        "profile_owner": "unverified",
        "native_pulseaudio_endpoint": native_pulseaudio_endpoint or {
            "status": "unknown", "server_name": None, "default_sink": None},
        "checks": {"observed_display": observed_display, "x11": x11, "audio": audio,
                   "renderer_class": renderer_class, "renderer": renderer,
                   "gles_context": gles_context, "gles_renderer": gles_renderer,
                   "gles_version": gles_version, "gles_draw_verified": False,
                   "glx_draw": glx_draw, "glx_draw_frames": glx_draw_frames,
                   "glx_draw_renderer": glx_draw_renderer, "vulkan_draw": vulkan_draw,
                   "vulkan_draw_device": vulkan_draw_device, "dri3_extension": dri3_extension},
        "blockers": blockers or [],
        "read_only": not guest_entered,
        "probe_payload_read_only": True,
        "safety": {"launcher_profile_write_possible": guest_entered,
                    "packages_changed": False, "guest_write_command_invoked": False,
                    "host_lifecycle_started": False, "host_lifecycle_stopped": False,
                    "services_started": False, "services_stopped": False,
                    "host_home_and_shared_storage_unbound": True},
    }


def _guest_command(manager: str, user: str, display: str, backend: str,
                   command: str, *, prefix: str = "/data/data/com.termux/files/usr",
                   cookie_path: str | Path | None = None, distro: str = "debian") -> list[str]:
    args = [manager, "login", "--isolated"]
    if backend == "zink":
        x11_host_dir = str(Path(prefix) / "tmp" / ".X11-unix")
        args.extend(["--bind", f"{x11_host_dir}:/tmp/.X11-unix",
                     "--bind", "/dev/kgsl-3d0:/dev/kgsl", "--bind", "/dev/dri"])
    else:
        # The VirGL server uses a socket under Termux TMPDIR; keep the guest
        # isolated from HOME/shared storage while preserving that documented route.
        args.append("--shared-tmp")
    guest_cookie = None
    if cookie_path is not None:
        cookie = Path(cookie_path)
        if not cookie.is_absolute() or ":" in str(cookie) or "\n" in str(cookie):
            raise ValueError("PulseAudio cookie bind path must be a safe absolute path")
        guest_cookie = "/tmp/.ternuxx-pulse-cookie"
        args.extend(["--bind", f"{cookie}:{guest_cookie}"])
    args.append(distro)
    args.extend(["--user", user, "--env", f"DISPLAY={display}",
                 "--env", f"PULSE_SERVER={_PULSE_SERVER}"])
    if guest_cookie:
        args.extend(["--env", f"PULSE_COOKIE={guest_cookie}"])
    if backend == "zink":
        args.extend(["--env", "MESA_LOADER_DRIVER_OVERRIDE=zink",
                     "--env", "GALLIUM_DRIVER=zink", "--env", "TU_DEBUG=sysmem,noconform",
                     "--env", "MESA_VK_WSI_DEBUG=sw", "--env", "MESA_SHADER_CACHE_DISABLE=true"])
    else:
        args.extend(["--env", "LIBGL_ALWAYS_SOFTWARE=true",
                     "--env", "GALLIUM_DRIVER=virpipe",
                     "--env", f"VTEST_SOCKET_NAME=/tmp/.ternuxx-virgl/virgl-{display[1:]}.sock",
                     "--env", "MESA_SHADER_CACHE_DISABLE=true"])
    args.extend(["--", "/bin/sh", "-c", command])
    return args


_GUEST_PROBE_SCRIPT = r"""
printf 'Display: %s\n' "${DISPLAY:-}"
x11=unavailable
if command -v xdpyinfo >/dev/null 2>&1 && xdpyinfo -display "${DISPLAY:-}" >/dev/null 2>&1; then
  x11=reachable
fi
renderer=
if [ "${GALLIUM_DRIVER:-}" != virpipe ] && command -v glxinfo >/dev/null 2>&1; then
  glx_output=$(glxinfo -B 2>/dev/null || true)
  renderer=$(printf '%s\n' "$glx_output" | sed -n 's/^OpenGL renderer string: //p' | head -n 1)
  [ -n "$renderer" ] && x11=reachable
fi
printf 'X11: %s\n' "$x11"
dri3_extension=unknown
if command -v xdpyinfo >/dev/null 2>&1; then
  if xdpyinfo -display "${DISPLAY:-}" -queryExtensions 2>/dev/null | awk '$1 == "DRI3" { found=1 } END { exit !found }'; then
    dri3_extension=available
  else
    dri3_extension=unavailable
  fi
fi
printf 'DRI3 extension: %s\n' "$dri3_extension"
printf 'Renderer: %s\n' "${renderer:-unavailable}"
glx_draw=unavailable
glx_draw_frames=0
glx_draw_renderer=
if command -v glxgears >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  glx_draw_output=$(timeout -s TERM 7s glxgears -info -geometry 180x100 2>&1 || true)
  glx_draw_frames=$(printf '%s\n' "$glx_draw_output" | awk '$2 == "frames" && $3 == "in" { frames=$1 } END { if (frames ~ /^[0-9]+$/) print frames; else print 0 }')
  glx_draw_renderer=$(printf '%s\n' "$glx_draw_output" | sed -n 's/^GL_RENDERER[[:space:]]*=[[:space:]]*//p' | head -n 1)
  if [ "$glx_draw_frames" -gt 0 ] && [ -n "$glx_draw_renderer" ]; then
    glx_draw=verified
  else
    glx_draw=failed
  fi
fi
printf 'GLX draw: %s\nGLX draw frames: %s\nGLX draw renderer: %s\n' "$glx_draw" "$glx_draw_frames" "${glx_draw_renderer:-unavailable}"
if [ -z "$renderer" ] && [ -n "$glx_draw_renderer" ]; then
  renderer="$glx_draw_renderer"
  printf 'Renderer: %s\n' "$renderer"
fi
gles_renderer=
gles_version=
if command -v es2_info >/dev/null 2>&1; then
  gles_output=$(es2_info 2>&1 || true)
  gles_renderer=$(printf '%s\n' "$gles_output" | sed -n 's/^GL_RENDERER: //p' | head -n 1)
  gles_version=$(printf '%s\n' "$gles_output" | sed -n 's/^GL_VERSION: //p' | head -n 1)
fi
if [ -n "$gles_renderer" ] && [ -n "$gles_version" ]; then
  printf 'GLES context: verified\nGLES renderer: %s\nGLES version: %s\n' "$gles_renderer" "$gles_version"
else
  printf 'GLES context: unavailable\nGLES renderer: unavailable\nGLES version: unavailable\n'
fi
vulkan_draw=skipped
vulkan_draw_device=
if [ "${GALLIUM_DRIVER:-}" = zink ]; then
  vulkan_draw=unavailable
  if command -v vkcube >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    vkcube_output=$(timeout -s TERM 15s vkcube --c 120 2>&1)
    vkcube_status=$?
    vulkan_draw_device=$(printf '%s\n' "$vkcube_output" | sed -n 's/^Selected GPU [0-9][0-9]*: //p' | head -n 1)
    if [ "$vkcube_status" -eq 0 ] && [ -n "$vulkan_draw_device" ]; then
      case "$vulkan_draw_device" in
        *Adreno*|*adreno*|*Turnip*|*turnip*) vulkan_draw=verified ;;
        *llvmpipe*|*lavapipe*|*softpipe*|*Software*) vulkan_draw=software ;;
        *) vulkan_draw=other ;;
      esac
    else
      vulkan_draw=failed
    fi
  fi
fi
printf 'Vulkan draw: %s\nVulkan draw device: %s\n' "$vulkan_draw" "${vulkan_draw_device:-unavailable}"
if command -v pactl >/dev/null 2>&1 && pactl --server "${PULSE_SERVER:-tcp:127.0.0.1:4713}" info >/dev/null 2>&1; then
  printf 'Audio: PulseAudio reachable\n'
else
  printf 'Audio: PulseAudio not reachable\n'
fi
"""


def verify_managed_guest_alias(distro: str, prefix: str = "/data/data/com.termux/files/usr", *,
                               home: str | None = None, state_dir: str | None = None) -> dict[str, object]:
    """Verify a receipt-bound non-Debian canonical guest or Ternuxx replay alias."""
    if isinstance(distro, str) and distro.startswith("ternuxx-replay-"):
        return verify_managed_replay_alias(distro, prefix, home=home, state_dir=state_dir)
    if distro != "ubuntu":
        raise ValueError("only Ubuntu and receipt-verified Ternuxx replay guests are managed here")
    home = str(Path(home).expanduser()) if home is not None else str(Path.home())
    state_dir = state_dir or os.environ.get("TERNUXX_STATE_DIR", str(Path(home) / ".local/share/ternuxx"))
    try:
        state = proot_fresh_setup._state_root(home, state_dir, create=False)
        receipt = proot_fresh_setup._read_private(state / "fresh-provider-ubuntu.json")
        if (receipt.get("schema_version") != 1 or receipt.get("alias") != "ubuntu"
                or receipt.get("release") != "Ubuntu 24.04 LTS (Noble)"
                or receipt.get("profile_id") not in {"ubuntu-noble", proot_profiles.PROFILE_IDS["ubuntu-noble"]}
                or not isinstance(receipt.get("guest_user"), str)
                or not _GUEST_USER.fullmatch(receipt["guest_user"]) or receipt["guest_user"] == "root"
                or receipt.get("requested_packages_verified_installed") is not True
                or receipt.get("package_versions_recorded") is not True
                or not isinstance(receipt.get("plan_id"), str)):
            raise ValueError("Ubuntu install receipt is incomplete")
        identity = receipt.get("rootfs_identity")
        proot_fresh_setup._verify_owned_target(prefix, "ubuntu", identity)
        return {"alias": "ubuntu", "profile_id": "ubuntu-noble", "plan_id": receipt["plan_id"],
                "guest_user": receipt["guest_user"], "release": receipt["release"], "rootfs_identity": identity}
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError("Ubuntu guest lacks an exact, valid Ternuxx install receipt") from exc


def verify_managed_replay_alias(distro: str, prefix: str = "/data/data/com.termux/files/usr", *,
                                home: str | None = None, state_dir: str | None = None) -> dict[str, object]:
    """Verify an exact replay receipt and current rootfs identity before routing."""
    if not isinstance(distro, str) or not re.fullmatch(
            r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", distro):
        raise ValueError("the managed guest operation supports only an exact Ternuxx replay alias")
    home = str(Path(home).expanduser()) if home is not None else str(Path.home())
    state_dir = state_dir or os.environ.get("TERNUXX_STATE_DIR", str(Path(home) / ".local/share/ternuxx"))
    try:
        state = proot_fresh_setup._state_root(home, state_dir, create=False)
        receipt = proot_fresh_setup._read_private(state / f"fresh-provider-{distro}.json")
        identity = receipt.get("rootfs_identity")
        profile_id = proot_profiles.profile_for_alias(distro)
        manifest, _digest, _raw = proot_profiles.load(Path(__file__).resolve().parent.parent, profile_id)
        expected_release = manifest.get("release_name", manifest.get("release"))
        expected_profile = proot_profiles.PROFILE_IDS[profile_id]
        if (receipt.get("schema_version") != 1 or receipt.get("alias") != distro
                or receipt.get("requested_packages_verified_installed") is not True
                or receipt.get("package_versions_recorded") is not True
                or receipt.get("release") != expected_release
                or (receipt.get("profile_id") is not None and receipt.get("profile_id") != expected_profile)
                or not isinstance(receipt.get("plan_id"), str)):
            raise ValueError("replay install receipt is incomplete")
        proot_fresh_setup._verify_owned_target(prefix, distro, identity)
        return {"alias": distro, "profile_id": profile_id, "plan_id": receipt["plan_id"],
                "release": receipt["release"], "rootfs_identity": identity}
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError("replay guest lacks an exact, valid Ternuxx install receipt") from exc


def verify_proot_guest(*, distro: str, user: str, display: str, backend: str,
                       prefix: str = "/data/data/com.termux/files/usr",
                       which: Callable[[str], str | None] = shutil.which,
                       runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> dict[str, object]:
    """Run a bounded probe against canonical Debian or a receipt-verified managed guest."""
    managed_profile_alias = distro != "debian"
    if managed_profile_alias:
        verify_managed_guest_alias(distro, prefix)
    if not isinstance(user, str) or not _GUEST_USER.fullmatch(user) or user == "root":
        raise ValueError("guest user must be a non-root managed guest username")
    if not isinstance(display, str) or not _DISPLAY.fullmatch(display):
        raise ValueError("display must be an explicit Termux:X11 display from :0 through :10")
    if backend not in {"zink", "virgl"}:
        raise ValueError("backend must be explicitly selected as zink or virgl")

    native_pulseaudio_endpoint = inspect_native_pulseaudio_endpoint(which=which, runner=runner)

    def verification_result(**values: object) -> dict[str, object]:
        values["distro"] = distro
        values["native_pulseaudio_endpoint"] = native_pulseaudio_endpoint
        return _verification_result(**values)

    manager = which("proot-distro")
    if not manager:
        return verification_result(status="unavailable", display=display, backend=backend,
                                  blockers=["proot-distro command is unavailable"])
    try:
        inventory = runner([manager, "list"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return verification_result(status="unknown", display=display, backend=backend,
                                  blockers=["installed PRoot distribution inventory could not be read"])
    installed = (_installed_names(inventory.stdout) if isinstance(getattr(inventory, "stdout", None), str)
                 else None) if inventory.returncode == 0 else None
    if installed is None:
        return verification_result(status="unknown", display=display, backend=backend,
                                  blockers=["installed PRoot distribution inventory is unavailable or unrecognized"])
    if distro not in installed and not managed_profile_alias:
        return verification_result(status="not_installed", display=display, backend=backend,
                                  blockers=[f"{distro} is not listed as an installed PRoot distribution"])

    cookie_path = _native_pulse_cookie_path()
    try:
        result = runner(_guest_command(manager, user, display, backend, _GUEST_PROBE_SCRIPT,
                                       prefix=prefix, cookie_path=cookie_path, distro=distro),
                        capture_output=True, text=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return verification_result(status="unknown", display=display, backend=backend,
                                  guest_entered=True,
                                  blockers=["read-only guest probe timed out or failed to start"])

    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip().lower(), value.strip()
        if key in {"display", "x11", "audio", "renderer", "gles context", "gles renderer", "gles version",
                   "glx draw", "glx draw frames", "glx draw renderer", "vulkan draw",
                   "vulkan draw device", "dri3 extension"}:
            values[key] = value
    observed_display = values.get("display")
    x11 = "reachable" if values.get("x11") == "reachable" else "unavailable" if "x11" in values else "unknown"
    audio = "reachable" if values.get("audio") == "PulseAudio reachable" else "unavailable" if "audio" in values else "unknown"
    renderer = values.get("renderer")
    if renderer and (len(renderer) > 1024 or any(ord(char) < 32 for char in renderer)):
        renderer = None
    if not renderer or renderer == "unavailable" or renderer == "unavailable (glxinfo missing)":
        renderer, renderer_class = None, "unavailable"
    elif "llvmpipe" in renderer.lower() or "softpipe" in renderer.lower():
        renderer_class = "software"
    elif "zink" in renderer.lower() and ("turnip" in renderer.lower() or "adreno" in renderer.lower()):
        renderer_class = "zink_turnip"
    elif "virpipe" in renderer.lower() or "virgl" in renderer.lower():
        renderer_class = "virgl"
    else:
        renderer_class = "other"
    gles_renderer = values.get("gles renderer")
    if gles_renderer and (len(gles_renderer) > 1024 or any(ord(char) < 32 for char in gles_renderer)):
        gles_renderer = None
    gles_version = values.get("gles version")
    if gles_version and (len(gles_version) > 256 or any(ord(char) < 32 for char in gles_version)):
        gles_version = None
    gles_context = "verified" if values.get("gles context") == "verified" and gles_renderer and gles_version else "unavailable" if values.get("gles context") == "unavailable" else "unknown"
    glx_draw_renderer = values.get("glx draw renderer")
    if glx_draw_renderer and (len(glx_draw_renderer) > 1024 or any(ord(char) < 32 for char in glx_draw_renderer)):
        glx_draw_renderer = None
    try:
        glx_draw_frames = int(values.get("glx draw frames", "0"))
    except ValueError:
        glx_draw_frames = 0
    if not 0 <= glx_draw_frames <= 1000000000:
        glx_draw_frames = 0
    dri3_extension = values.get("dri3 extension")
    if dri3_extension not in {"available", "unavailable"}:
        dri3_extension = "unknown"
    vulkan_draw = values.get("vulkan draw")
    if vulkan_draw not in {"verified", "software", "failed", "unavailable", "skipped", "other"}:
        vulkan_draw = "unknown"
    vulkan_draw_device = values.get("vulkan draw device")
    if vulkan_draw_device and (len(vulkan_draw_device) > 1024
                               or any(ord(char) < 32 for char in vulkan_draw_device)):
        vulkan_draw_device = None
    if vulkan_draw == "verified" and (
            not vulkan_draw_device or not any(token in vulkan_draw_device.lower()
                                               for token in ("adreno", "turnip"))):
        vulkan_draw = "failed"
    if vulkan_draw == "software" and (
            not vulkan_draw_device or not any(token in vulkan_draw_device.lower()
                                               for token in ("llvmpipe", "lavapipe", "softpipe", "software"))):
        vulkan_draw = "unknown"
    glx_draw_status = values.get("glx draw")
    if glx_draw_status not in {"verified", "failed", "unavailable"}:
        glx_draw_status = "unknown"
    if glx_draw_status == "verified" and (glx_draw_frames <= 0 or not glx_draw_renderer):
        glx_draw_status = "unknown"
    expected_renderer = "zink_turnip" if backend == "zink" else "virgl"
    if glx_draw_status == "verified":
        draw_lower = (glx_draw_renderer or "").lower()
        draw_matches = (
            ("zink" in draw_lower and ("turnip" in draw_lower or "adreno" in draw_lower))
            if expected_renderer == "zink_turnip" else
            ("virpipe" in draw_lower or "virgl" in draw_lower)
        )
        if not draw_matches:
            glx_draw_status = "failed"
    blockers = []
    if observed_display is not None and observed_display != display:
        blockers.append("guest reported display does not match the requested display")
    if x11 != "reachable":
        blockers.append("guest X11 connection is not verified")
    if audio != "reachable":
        blockers.append("guest PulseAudio connection is not verified")
    if backend == "zink" and vulkan_draw != "verified":
        blockers.append("bounded Vulkan draw did not verify an Adreno/Turnip device")
    if glx_draw_status != "verified":
        blockers.append("bounded GLX draw did not verify the requested backend")
    if renderer_class != expected_renderer:
        if renderer_class == "unavailable":
            if vulkan_draw == "verified":
                blockers.append("GLX renderer unavailable; bounded Vulkan draw verified, but GLX desktop rendering remains unverified")
            else:
                blockers.append("GLX renderer unavailable; GLES context does not verify a draw")
        else:
            blockers.append("observed renderer does not match the explicitly requested backend")
    if result.returncode != 0 and not blockers:
        blockers.append("guest probe reported one or more failed checks")
    if not result.stdout.strip() and len(blockers) < 8:
        blockers.append("guest probe returned no recognized output")
    if x11 == "unavailable" and observed_display == display and len(blockers) < 8:
        process_displays = inspect_termux_x11_process_displays(which=which, runner=runner)
        if (process_displays["status"] == "available"
                and display not in process_displays["observed_displays"]):
            blockers.append(f"requested display {display} not observed in the Termux-visible X11 process list")
    status = "complete" if not blockers and result.returncode == 0 else "partial" if values else "unknown"
    return verification_result(status=status, display=display, backend=backend,
                               guest_entered=True, observed_display=observed_display,
                               x11=x11, audio=audio, renderer=renderer,
                               renderer_class=renderer_class, gles_context=gles_context,
                               gles_renderer=gles_renderer, gles_version=gles_version,
                               glx_draw=glx_draw_status, glx_draw_frames=glx_draw_frames,
                               glx_draw_renderer=glx_draw_renderer, vulkan_draw=vulkan_draw,
                               vulkan_draw_device=vulkan_draw_device,
                               dri3_extension=dri3_extension, blockers=blockers)
