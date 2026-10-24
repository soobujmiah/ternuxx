#!/usr/bin/env python3
"""Stop only a verified PRoot desktop whose lifecycle supervisor vanished."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time

import desktop_session_state


class OrphanStopError(RuntimeError):
    pass


def _identity(role: str, value: object, proc_root: Path) -> tuple[int, int]:
    if not isinstance(value, dict):
        raise OrphanStopError(f"recorded {role} process identity is malformed")
    pid, ticks, marker = value.get("pid"), value.get("start_ticks"), value.get("command_marker")
    expected = "termux-x11" if role == "x11" else "proot-display0"
    if type(pid) is not int or pid < 2 or not isinstance(ticks, str) or not ticks.isdigit() or marker != expected:
        raise OrphanStopError(f"recorded {role} identity is invalid")
    if value.get("pgid") != pid or value.get("sid") != pid:
        raise OrphanStopError(f"recorded {role} process group is not privately owned")
    root = proc_root / str(pid)
    try:
        raw = (root / "stat").read_text(encoding="ascii")
        cmdline = (root / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        status = (root / "status").read_text(encoding="ascii")
    except OSError as exc:
        raise OrphanStopError(f"recorded {role} process cannot be inspected") from exc
    _comm, separator, tail = raw.rpartition(")")
    fields = tail.strip().split() if separator else []
    if len(fields) < 20 or fields[19] != ticks or fields[2] != str(pid) or fields[3] != str(pid):
        raise OrphanStopError(f"recorded {role} PID, start time, or session identity changed")
    if marker not in cmdline:
        raise OrphanStopError(f"recorded {role} command marker does not match")
    uid_line = next((line for line in status.splitlines() if line.startswith("Uid:")), "")
    try:
        uid = int(uid_line.split()[1])
    except (IndexError, ValueError) as exc:
        raise OrphanStopError(f"recorded {role} UID cannot be verified") from exc
    if uid != os.getuid():
        raise OrphanStopError(f"recorded {role} process belongs to another UID")
    return pid, pid


def _group_has_live_member(pgid: int, proc_root: Path) -> bool:
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "stat").read_text(encoding="ascii")
        except OSError:
            continue
        _comm, separator, tail = raw.rpartition(")")
        fields = tail.strip().split() if separator else []
        if len(fields) >= 3 and fields[0] not in {"Z", "X"} and fields[2] == str(pgid):
            return True
    return False


def _terminate_group(pid: int, proc_root: Path) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if not _group_has_live_member(pid, proc_root):
            return
        time.sleep(0.1)
    raise OrphanStopError(f"owned process group {pid} did not exit after SIGTERM; no SIGKILL was sent")


def stop_orphaned(home: Path, state_dir: Path, tmp_root: Path, display_tool: Path,
                  proc_root: Path = Path("/proc")) -> dict:
    session_path = state_dir / "session.json"
    lock = state_dir / ".session.lock"
    lock_stat = lock.lstat()
    if (not stat.S_ISDIR(lock_stat.st_mode) or lock_stat.st_uid != os.getuid()
            or stat.S_IMODE(lock_stat.st_mode) & 0o077):
        raise OrphanStopError("private lifecycle lock is missing or unsafe")
    before, metadata = desktop_session_state._read_session_file(session_path)
    data = json.loads(before.decode("utf-8"))
    report = desktop_session_state.inspect(home, state_dir, proc_root, tmp_root)
    if (data.get("provider") != "proot" or data.get("display") != ":0"
            or data.get("status") != "running" or report.get("state") != "failed"
            or report.get("display_state") != "ready"
            or report.get("processes") != {"supervisor": "absent", "x11": "live", "desktop": "live"}):
        raise OrphanStopError("session is not the exact verified orphaned PRoot :0 desktop")
    x11_pid, _ = _identity("x11", data.get("x11"), proc_root)
    desktop_pid, _ = _identity("desktop", data.get("desktop"), proc_root)
    if x11_pid == desktop_pid:
        raise OrphanStopError("X server and Debian desktop unexpectedly share a process group")
    if desktop_session_state._read_session_file(session_path)[0] != before:
        raise OrphanStopError("session record changed during orphan verification")

    # Terminate only the two process groups whose PID, start time, command, UID,
    # PGID, and SID match the private session record. Leave the Native server/audio alone.
    _terminate_group(desktop_pid, proc_root)
    _terminate_group(x11_pid, proc_root)
    recovery = subprocess.run([sys.executable, str(display_tool), "recover", str(tmp_root), "0", str(x11_pid)],
                              check=True, capture_output=True, text=True, timeout=5).stdout.strip()
    if recovery not in {"recovered", "available"}:
        raise OrphanStopError("verified :0 display artifacts could not be reconciled safely")

    current, current_meta = desktop_session_state._read_session_file(session_path)
    if (current != before or (current_meta.st_dev, current_meta.st_ino, current_meta.st_mtime_ns)
            != (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns)):
        raise OrphanStopError("session record changed before stop could be recorded")
    archive = state_dir / f"session.orphaned.{time.time_ns()}.json"
    fd, archive_tmp = tempfile.mkstemp(prefix=".orphaned.", dir=state_dir)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(before)
        os.chmod(archive_tmp, 0o600)
        os.replace(archive_tmp, archive)
    finally:
        try:
            os.unlink(archive_tmp)
        except FileNotFoundError:
            pass
    data["status"] = "stopped"
    data["error"] = "orphaned PRoot session stopped after exact process identity verification"
    fd, state_tmp = tempfile.mkstemp(prefix=".session.", dir=state_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.chmod(state_tmp, 0o600)
        os.replace(state_tmp, session_path)
    finally:
        try:
            os.unlink(state_tmp)
        except FileNotFoundError:
            pass
    final = desktop_session_state.inspect(home, state_dir, proc_root, tmp_root)
    if final.get("state") != "stopped":
        raise OrphanStopError(f"stop finished but final evidence is {final.get('state')}")
    return {"state": "stopped", "display": ":0", "archive": archive.name}


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(2)
    try:
        print(json.dumps(stop_orphaned(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])), sort_keys=True))
    except (OSError, ValueError, OrphanStopError, subprocess.SubprocessError) as exc:
        print(f"desktop_orphan_stop: {exc}", file=sys.stderr)
        raise SystemExit(1)
