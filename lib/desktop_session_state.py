#!/usr/bin/env python3
"""Read-only classification and narrowly safe stale-session reconciliation."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import tempfile

import native_desktops
import proot_desktops
import proot_profiles
import x11_display

MARKERS = {"supervisor": "desktop-supervisor.sh", "x11": "termux-x11", "desktop": "xfce4-session"}
DESKTOP_MARKERS = {"native": "xfce4-session", "proot": "proot-display0"}

class StateError(RuntimeError):
    pass

def _read_session_file(path: Path) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        metadata = os.fstat(fd)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise StateError("session record ownership or mode is unsafe")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read()
        return content, metadata
    finally:
        os.close(fd)

def _session_group_state(pgid: int, sid: int, proc: Path, *,
                         anchor_pid: int, anchor_ticks: str) -> str:
    """Verify a PRoot-owned session group after its original launcher execs/exits."""
    if pgid < 1 or sid != pgid or not proc.is_dir():
        return "unknown"
    uncertain = False
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "stat").read_text(encoding="ascii")
            _comm, sep, tail = raw.rpartition(")")
            fields = tail.strip().split() if sep else []
            if len(fields) < 4 or fields[0] in ("Z", "X"):
                continue
            if fields[2] != str(pgid) or fields[3] != str(sid):
                continue
            # A reused anchor PID can create a new same-numbered session after
            # the original group vanished. It is not evidence for this record.
            if int(entry.name) == anchor_pid and fields[19] != anchor_ticks:
                continue
            status = (entry / "status").read_text(encoding="ascii")
        except FileNotFoundError:
            continue
        except OSError:
            uncertain = True
            continue
        uid_match = re.search(r"^Uid:\s+(\d+)", status, re.M)
        if not uid_match:
            uncertain = True
        elif int(uid_match.group(1)) != os.getuid():
            return "unsafe"
        else:
            return "live"
    return "unknown" if uncertain else "absent"


def _proc_state(role: str, record: object, proc: Path, expected_marker: str | None = None,
                allow_exec_transition: bool = False) -> str:
    if not isinstance(record, dict):
        raise StateError(f"recorded {role} identity is malformed")
    external_x11 = role == "x11" and record.get("ownership") == "external"
    pid, ticks, marker = record.get("pid"), record.get("start_ticks"), record.get("command_marker")
    if pid is None and role in ("x11", "desktop"):
        return "absent"
    expected = expected_marker or MARKERS[role]
    if type(pid) is not int or pid < 1 or marker != expected:
        raise StateError(f"recorded {role} identity is invalid")
    if not isinstance(ticks, str) or not ticks.isdigit():
        # Failed startup may persist the expected marker/PID before proc identity
        # sampling completes. Treat it as absent only when that PID is gone;
        # a present or unreadable PID remains ambiguous and cannot be signaled.
        try:
            (proc / str(pid) / "stat").read_text(encoding="ascii")
        except FileNotFoundError:
            return "absent"
        except OSError:
            return "unknown"
        return "unknown"
    if role != "supervisor" and not external_x11 and (record.get("pgid") != pid or record.get("sid") != pid):
        raise StateError(f"recorded {role} group/session identity is unsafe")
    root = proc / str(pid)
    try:
        raw = (root / "stat").read_text(encoding="ascii")
    except FileNotFoundError:
        if allow_exec_transition and role == "desktop":
            return _session_group_state(record.get("pgid"), record.get("sid"), proc,
                                        anchor_pid=pid, anchor_ticks=ticks)
        return "absent"
    except OSError as exc:
        if exc.errno in (13, 1):
            return "unknown"
        raise StateError(f"cannot inspect {role} process identity") from exc
    _comm, sep, tail = raw.rpartition(")")
    fields = tail.strip().split() if sep else []
    if len(fields) < 20:
        return "unknown"
    try:
        cmd = (root / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        status = (root / "status").read_text(encoding="ascii")
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unknown"
    uid_match = re.search(r"^Uid:\s+(\d+)", status, re.M)
    if fields[19] != ticks:
        if allow_exec_transition and role == "desktop":
            return _session_group_state(record.get("pgid"), record.get("sid"), proc,
                                        anchor_pid=pid, anchor_ticks=ticks)
        return "absent"  # The recorded process ended or its PID was reused.
    if role != "supervisor" and not external_x11 and (fields[2] != str(pid) or fields[3] != str(pid)):
        if allow_exec_transition and role == "desktop":
            return _session_group_state(record.get("pgid"), record.get("sid"), proc,
                                        anchor_pid=pid, anchor_ticks=ticks)
        return "absent"
    if not uid_match or int(uid_match.group(1)) != os.getuid():
        if allow_exec_transition and role == "desktop":
            return _session_group_state(record.get("pgid"), record.get("sid"), proc,
                                        anchor_pid=pid, anchor_ticks=ticks)
        return "unsafe"
    # The initial PRoot wrapper is marker-checked when its process group is
    # captured. PRoot then execs through proot-distro into the guest launcher,
    # so argv can legitimately lose the marker while PID/start-time/group stay
    # fixed. Accept only that provider-specific, exact process identity.
    if marker not in cmd and allow_exec_transition and role == "desktop":
        return _session_group_state(record.get("pgid"), record.get("sid"), proc,
                                        anchor_pid=pid, anchor_ticks=ticks)
    if external_x11:
        args = (root / "cmdline").read_bytes().split(b"\0")
        # External Termux:X11 attachments must match the host activity's exact
        # argv shape or the Android app_process signature, never a substring.
        display_arg = record.get("display")
        native_argv = args == [b"termux-x11", b"com.termux.x11", str(display_arg).encode(), b""]
        if not native_argv:
            try:
                env = (root / "environ").read_bytes().split(b"\0")
                maps = (root / "maps").read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                return "unknown"
            native_app = (any(item.startswith(b"CLASSPATH=") and item.endswith(b"termux-x11/loader.apk") for item in env)
                          and any("/com.termux.x11-" in line and line.rstrip().endswith("/base.apk") for line in maps))
            if not native_app:
                return "unsafe"
    elif marker not in cmd:
        return "absent"
    return "live"

def _display_state(session: dict, tmp_root: Path, *, require_ready: bool, proc: Path = Path("/proc")) -> str:
    display = session["display"]
    number = display[1:]
    sock_dir = tmp_root / ".X11-unix"
    try:
        root_meta = tmp_root.lstat()
    except OSError:
        return "unknown"
    if (stat.S_ISLNK(root_meta.st_mode) or not stat.S_ISDIR(root_meta.st_mode)
            or root_meta.st_uid != os.getuid()):
        return "unsafe"
    try:
        dir_meta = sock_dir.lstat()
    except FileNotFoundError:
        # A missing X11 socket directory is a normal stopped state when the
        # matching display lock is also absent. Keep a lock without its socket
        # directory ambiguous below; never treat it as a clean display.
        dir_meta = None
    except OSError:
        return "unknown"
    if dir_meta is not None and (stat.S_ISLNK(dir_meta.st_mode)
            or not stat.S_ISDIR(dir_meta.st_mode) or dir_meta.st_uid != os.getuid()):
        return "unsafe"
    sock = sock_dir / f"X{number}"
    lock = tmp_root / f".X{number}-lock"
    external = session.get("x11", {}).get("ownership") == "external"
    if external:
        identity = x11_display.attachable(proc, tmp_root, number)
        recorded = session.get("x11", {})
        if identity == (recorded.get("pid"), recorded.get("start_ticks")):
            return "ready"
        # A live or ambiguous external endpoint remains protected. A recorded
        # external server is stale only when its exact PID is gone, its private
        # socket is owned by us, no X lock exists, and connect is refused.
        pid = recorded.get("pid")
        if type(pid) is not int or pid < 2:
            return "unknown"
        try:
            (proc / str(pid) / "stat").lstat()
            return "unknown"
        except FileNotFoundError:
            pass
        except OSError:
            return "unknown"
        if dir_meta is None:
            return "absent"
        try:
            socket_meta = sock.lstat()
        except FileNotFoundError:
            return "absent"
        except OSError:
            return "unknown"
        if (not stat.S_ISSOCK(socket_meta.st_mode)
                or socket_meta.st_uid != os.getuid()):
            return "unsafe"
        try:
            lock.lstat()
            return "unknown"
        except FileNotFoundError:
            pass
        except OSError:
            return "unknown"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.25)
                client.connect(str(sock))
            return "unknown"
        except ConnectionRefusedError:
            try:
                current = sock.lstat()
                (proc / str(pid) / "stat").lstat()
                return "unknown"
            except FileNotFoundError:
                if ((current.st_dev, current.st_ino) ==
                        (socket_meta.st_dev, socket_meta.st_ino)):
                    return "stale"
                return "unknown"
            except OSError:
                return "unknown"
        except OSError:
            return "unknown"
    found = []
    for index, path in enumerate((sock, lock)):
        if index == 0 and dir_meta is None:
            found.append(None)
            continue
        try:
            meta = path.lstat()
        except FileNotFoundError:
            found.append(None)
            continue
        except OSError:
            return "unknown"
        if stat.S_ISLNK(meta.st_mode) or meta.st_uid != os.getuid():
            return "unsafe"
        found.append(meta)
    if all(item is None for item in found):
        return "absent"
    if found[0] is not None and found[1] is None:
        identity = x11_display.attachable(proc, tmp_root, number)
        return "external" if identity is not None else "unknown"
    if found[0] is None or found[1] is None or not stat.S_ISSOCK(found[0].st_mode) or not stat.S_ISREG(found[1].st_mode):
        return "unknown"
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(lock, flags)
        try:
            lock_meta = os.fstat(fd)
            if (not stat.S_ISREG(lock_meta.st_mode) or lock_meta.st_uid != os.getuid()
                    or (lock_meta.st_dev, lock_meta.st_ino) != (found[1].st_dev, found[1].st_ino)):
                return "unsafe"
            with os.fdopen(fd, "r", encoding="ascii", closefd=False) as stream:
                lock_pid = stream.read(64).strip()
        finally:
            os.close(fd)
    except OSError:
        return "unknown"
    if lock_pid != str(session.get("x11", {}).get("pid")):
        return "unsafe"
    if not require_ready:
        return "ready"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.25)
            client.connect(str(sock))
        return "ready"
    except ConnectionRefusedError:
        # The socket path and exact lock identity are private and match this
        # session record, but the endpoint has no listener. Do not remove either
        # artifact; callers may reconcile only the record and choose a new display.
        return "stale"
    except OSError:
        return "unknown"

def _state_path_parts(home: Path, state_dir: Path) -> tuple[Path, tuple[str, ...]]:
    home_path = Path(os.path.abspath(home))
    home_meta = home_path.lstat()
    if stat.S_ISLNK(home_meta.st_mode) or not stat.S_ISDIR(home_meta.st_mode) or home_meta.st_uid != os.getuid():
        raise StateError("Termux HOME ownership or type is unsafe")
    target = Path(os.path.abspath(state_dir))
    try:
        relative = target.relative_to(home_path)
    except ValueError as exc:
        raise StateError("state directory must be inside Termux HOME") from exc
    if not relative.parts:
        raise StateError("state directory must be a child of Termux HOME")
    return home_path, relative.parts

def _validate_state_dir(home: Path, state_dir: Path) -> None:
    current, parts = _state_path_parts(home, state_dir)
    for index, part in enumerate(parts):
        current = current / part
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise StateError("state path component ownership or type is unsafe")
        if index == len(parts) - 1 and stat.S_IMODE(metadata.st_mode) != 0o700:
            raise StateError("state directory ownership or mode is unsafe")

def ensure_state_dir(home: Path, state_dir: Path) -> None:
    current, parts = _state_path_parts(home, state_dir)
    for index, part in enumerate(parts):
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o700)
            metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise StateError("state path component ownership or type is unsafe")
        if index == len(parts) - 1 and stat.S_IMODE(metadata.st_mode) != 0o700:
            os.chmod(current, 0o700, follow_symlinks=False)



def _proot_desktop_readiness(session: dict, proc: Path) -> dict[str, object]:
    """Check shell, WM, panel and desktop processes in the owned PRoot session group."""
    desktop_id = session.get("desktop_id", "xfce")
    if not isinstance(desktop_id, str):
        return {"state": "unknown", "desktop_id": "unknown",
                "required_processes": [], "observed_processes": [], "missing_processes": []}
    required = proot_desktops.DESKTOP_READY_PROCESSES.get(desktop_id)
    if required is None:
        return {"state": "unsupported", "desktop_id": desktop_id,
                "required_processes": [], "observed_processes": [], "missing_processes": []}
    identity = session.get("desktop")
    if not isinstance(identity, dict):
        return {"state": "unknown", "desktop_id": desktop_id,
                "required_processes": sorted(required), "observed_processes": [],
                "missing_processes": sorted(required)}
    pgid, sid = identity.get("pgid"), identity.get("sid")
    if type(pgid) is not int or pgid < 1 or sid != pgid:
        return {"state": "unknown", "desktop_id": desktop_id,
                "required_processes": sorted(required), "observed_processes": [],
                "missing_processes": sorted(required)}
    found: set[str] = set()
    uncertain = False
    visible = 0
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            raw = (entry / "stat").read_text(encoding="ascii")
        except FileNotFoundError:
            continue
        except OSError:
            uncertain = True
            continue
        _comm, separator, tail = raw.rpartition(")")
        fields = tail.strip().split() if separator else []
        if len(fields) < 4 or fields[0] in {"Z", "X"}:
            continue
        if fields[2] != str(pgid) or fields[3] != str(sid):
            continue
        visible += 1
        try:
            name = (entry / "comm").read_text(encoding="ascii").strip()
            status = (entry / "status").read_text(encoding="ascii")
        except FileNotFoundError:
            continue
        except OSError:
            uncertain = True
            continue
        uid_match = re.search(r"^Uid:\s+(\d+)", status, re.M)
        if not uid_match:
            uncertain = True
            continue
        if int(uid_match.group(1)) != os.getuid():
            return {"state": "unsafe", "desktop_id": desktop_id,
                    "required_processes": sorted(required),
                    "observed_processes": sorted(found),
                    "missing_processes": sorted(set(required) - found)}
        if name in required:
            found.add(name)
    missing = sorted(set(required) - found)
    if not visible or uncertain:
        state = "unknown"
    else:
        state = "ready" if not missing else "starting"
    return {"state": state, "desktop_id": desktop_id,
            "required_processes": sorted(required), "observed_processes": sorted(found),
            "missing_processes": missing}


def inspect(home: Path, state_dir: Path, proc: Path, tmp_root: Path) -> dict:
    try:
        _validate_state_dir(home, state_dir)
        record_path = state_dir / "session.json"
        _meta = record_path.lstat()
        if stat.S_ISLNK(_meta.st_mode):
            raise StateError("session record is a symlink")
        session_bytes, meta = _read_session_file(record_path)
        data = json.loads(session_bytes.decode("utf-8"))
        if not isinstance(data, dict) or data.get("schema") != 2 or data.get("owner") != "ternuxx" or data.get("provider") not in DESKTOP_MARKERS or data.get("status") not in {"running", "starting", "stopping", "failed", "stopped", "stop_incomplete"} or not isinstance(data.get("display"), str) or not re.fullmatch(r":[0-9]{1,2}", data["display"]):
            raise StateError("session record is not a recognized schema-v2 Ternuxx desktop session")
        if not proc.is_dir():
            return {"state": "unknown", "reason": "process inventory unavailable"}
        provider = data.get("provider")
        desktop_id = data.get("desktop_id", "xfce")
        guest_alias = data.get("guest_alias", "debian")
        if provider == "proot":
            try:
                proot_profiles.profile_for_alias(guest_alias)
            except (TypeError, ValueError) as exc:
                raise StateError("recorded PRoot guest alias is invalid") from exc
        if provider == "native":
            native_item = native_desktops.NATIVE_DESKTOPS.get(desktop_id)
            expected_desktop = native_item["command"] if native_item else None
        else:
            expected_desktop = DESKTOP_MARKERS.get(provider)
        recorded_desktop = data.get("desktop", {}).get("command_marker")
        if not expected_desktop or recorded_desktop != expected_desktop:
            raise StateError("recorded desktop marker is invalid")
        roles = {
            name: _proc_state(
                name, data.get(name), proc,
                expected_desktop if name == "desktop" else None,
                allow_exec_transition=(provider == "proot" and name == "desktop"),
            )
            for name in MARKERS
        }
        if "unsafe" in roles.values():
            return {"state": "unsafe", "reason": "recorded process identity belongs to a different owner", "processes": roles}
        if "unknown" in roles.values():
            return {"state": "unknown", "reason": "process identity cannot be verified", "processes": roles}
        any_live = "live" in roles.values()
        all_live = all(value == "live" for value in roles.values())
        display = _display_state(data, tmp_root, require_ready=all_live or not any_live, proc=proc)
        if display == "unsafe":
            return {"state": "unsafe", "reason": "display artifacts have unsafe ownership or identity", "processes": roles}
        if data["status"] == "running" and all_live and display == "ready":
            state = "running"
        elif data["status"] == "starting" and any_live:
            state = "starting"
        elif data["status"] == "stopping" and any_live:
            state = "stopping"
        elif (data["status"] == "stop_incomplete" and not any_live
              and display == "stale"):
            # A scoped stop can miss its final state write after every owned
            # PID exits. Permit only the existing dead-listener reconciliation
            # path to reclaim a socket/lock pair tied to that exact record.
            state = "stale"
        elif data["status"] in ("failed", "stop_incomplete"):
            state = "failed"
        elif not any_live and display in ("absent", "stale", "external"):
            state = "stopped" if data["status"] == "stopped" and display in ("absent", "external") else "stale"
        elif data["status"] == "running" and any_live:
            state = "failed"
        else:
            state = "unknown"
        result = {"state": state, "reason": "record and verified process/display evidence reconciled", "display": data["display"], "display_state": display, "processes": roles, "recorded_status": data["status"], "x11_ownership": data.get("x11", {}).get("ownership", "ternuxx")}
        if provider == "proot" and state == "running":
            readiness = _proot_desktop_readiness(data, proc)
            if readiness["state"] == "unsafe":
                return {"state": "unsafe", "reason": "PRoot desktop process group includes a different owner",
                        "display": data["display"], "display_state": display,
                        "processes": roles, "desktop_readiness": readiness}
            result["desktop_readiness"] = readiness
        return result
    except FileNotFoundError:
        return {"state": "stopped", "reason": "session record is absent", "processes": {name: "absent" for name in MARKERS}, "display": "absent"}
    except (OSError, ValueError, KeyError, StateError) as exc:
        return {"state": "unsafe", "reason": str(exc)}

def reconcile_stale(home: Path, state_dir: Path, proc: Path, tmp_root: Path) -> dict:
    # Sanctioned lifecycle writers are serialized by desktop.sh's private
    # mkdir lock. Refuse standalone reconciliation outside that contract.
    lock_path = state_dir / ".session.lock"
    try:
        lock_meta = lock_path.lstat()
    except FileNotFoundError as exc:
        raise StateError("stale reconciliation requires the lifecycle session lock") from exc
    if (not stat.S_ISDIR(lock_meta.st_mode) or lock_meta.st_uid != os.getuid()
            or stat.S_IMODE(lock_meta.st_mode) & 0o077):
        raise StateError("lifecycle session lock ownership or permissions are unsafe")
    current = inspect(home, state_dir, proc, tmp_root)
    if current["state"] != "stale":
        raise StateError(f"session is {current['state']}; stale reconciliation is not allowed")
    path = state_dir / "session.json"
    before, metadata = _read_session_file(path)
    data = json.loads(before.decode("utf-8"))
    data["status"] = "stopped"
    data["error"] = "reconciled stale record: recorded processes are absent and the matching private display endpoint refused a connection; display socket and lock artifacts were preserved"
    fd, temporary = tempfile.mkstemp(prefix=".session.", dir=state_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        current_meta = path.lstat()
        if (current_meta.st_dev, current_meta.st_ino, current_meta.st_mtime_ns, current_meta.st_size) != (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns, metadata.st_size) or _read_session_file(path)[0] != before:
            raise StateError("session record changed during reconciliation")
        verify = inspect(home, state_dir, proc, tmp_root)
        if verify["state"] != "stale":
            raise StateError("session evidence changed during reconciliation")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return inspect(home, state_dir, proc, tmp_root)

if __name__ == "__main__":
    if len(sys.argv) not in (4, 6):
        raise SystemExit(2)
    action, home, state = sys.argv[1:4]
    try:
        if action == "ensure-state" and len(sys.argv) == 4:
            ensure_state_dir(Path(home), Path(state))
            result = {"state": "ready", "reason": "private state path verified"}
        elif len(sys.argv) == 6:
            proc, tmp = sys.argv[4:6]
            result = inspect(Path(home), Path(state), Path(proc), Path(tmp)) if action == "inspect" else reconcile_stale(Path(home), Path(state), Path(proc), Path(tmp)) if action == "reconcile-stale" else None
        else:
            result = None
        if result is None:
            raise StateError("unsupported action")
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result["state"] not in ("unknown", "unsafe") else 1)
    except (OSError, ValueError, StateError) as exc:
        print(json.dumps({"state": "unsafe", "reason": str(exc)}, sort_keys=True))
        raise SystemExit(1)
