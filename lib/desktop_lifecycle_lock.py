#!/usr/bin/env python3
"""Crash-safe private lifecycle lock with verified stale-lock recovery."""
from __future__ import annotations
import fcntl
import json
import os
from pathlib import Path
import stat
import sys
import time

import desktop_session_state


def _ticks(proc_root: Path, pid: int) -> str | None:
    try:
        raw=(proc_root/str(pid)/"stat").read_text(encoding="ascii")
        _comm, sep, tail=raw.rpartition(")")
        fields=tail.strip().split() if sep else []
        return fields[19] if len(fields)>19 else None
    except (OSError, ValueError):
        return None


def _private_dir(path: Path) -> None:
    st=path.lstat()
    if (stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode)
            or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o700):
        raise RuntimeError("lifecycle state directory ownership or mode is unsafe")


def _guard(state_dir: Path):
    path=state_dir/".session-lock.guard"
    flags=os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0)|getattr(os,"O_CLOEXEC",0)
    fd=os.open(path,flags,0o600)
    st=os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o600:
        os.close(fd);raise RuntimeError("lifecycle lock guard is unsafe")
    fcntl.flock(fd,fcntl.LOCK_EX)
    return fd


def _legacy_lifecycle_running(proc_root: Path, exclude_pid: int) -> bool:
    try: entries=list(proc_root.iterdir())
    except OSError: return True
    for entry in entries:
        if not entry.name.isdigit() or int(entry.name)==exclude_pid: continue
        try: args=(entry/"cmdline").read_bytes().decode("utf-8","replace").split("\0")
        except OSError: continue
        for index,arg in enumerate(args):
            name=Path(arg).name
            if name=="tx" and index+1<len(args) and args[index+1] in {"start","stop","restart","pgui"}:
                return True
            if name=="proot-gui0.sh" and index+1<len(args) and args[index+1] in {"start","stop"}:
                return True
    return False


def _session_recoverable(state_dir: Path, home: Path, proc_root: Path, tmp_root: Path) -> bool:
    report=desktop_session_state.inspect(home,state_dir,proc_root,tmp_root)
    state=report.get("state")
    display=report.get("display_state","absent")
    processes=report.get("processes",{})
    no_live=all(value=="absent" for value in processes.values())
    if not no_live:return False
    if state in {"stopped","stale"}:
        return display in {"absent","stale"}
    # Existing start/stop handlers already archive a failed record only after
    # independently checking every owned process and display artifact.
    return state=="failed" and display=="absent"


def acquire(state_dir: Path, home: Path, proc_root: Path, tmp_root: Path,
            pid: int, operation: str) -> None:
    _private_dir(state_dir)
    guard=_guard(state_dir)
    lock=state_dir/".session.lock"
    try:
        try: st=lock.lstat()
        except FileNotFoundError: st=None
        if st is not None:
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o700:
                raise RuntimeError("lifecycle session lock is unsafe")
            owner=lock/"owner.json"
            try:
                owner_st=owner.lstat()
                if (stat.S_ISLNK(owner_st.st_mode) or not stat.S_ISREG(owner_st.st_mode)
                        or owner_st.st_uid!=os.getuid() or stat.S_IMODE(owner_st.st_mode)!=0o600):
                    raise RuntimeError("lifecycle lock owner record is unsafe")
                record=json.loads(owner.read_text(encoding="utf-8"))
                owner_pid=record.get("pid");owner_ticks=record.get("start_ticks")
                if type(owner_pid) is not int or not isinstance(owner_ticks,str) or not owner_ticks.isdigit():
                    raise RuntimeError("lifecycle lock owner record is invalid")
                if _ticks(proc_root,owner_pid)==owner_ticks:
                    raise RuntimeError("Another Ternuxx desktop lifecycle operation is active")
            except FileNotFoundError:
                # Upgrade from older mkdir-only locks. Only reclaim an old,
                # empty directory after verifying that no managed session runs.
                if (any(lock.iterdir()) or time.time()-st.st_mtime<120
                        or _legacy_lifecycle_running(proc_root,pid)):
                    raise RuntimeError("Another Ternuxx desktop lifecycle operation is active")
            if not _session_recoverable(state_dir,home,proc_root,tmp_root):
                raise RuntimeError("Lifecycle lock owner ended, but desktop state is live or uncertain; preserving the lock")
            try: owner.unlink()
            except FileNotFoundError: pass
            lock.rmdir()
        lock.mkdir(mode=0o700)
        start_ticks=_ticks(proc_root,pid)
        if start_ticks is None:
            lock.rmdir();raise RuntimeError("cannot verify lifecycle process identity")
        record={"pid":pid,"start_ticks":start_ticks,"operation":operation}
        path=lock/"owner.json"
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(record,stream,separators=(",",":"));stream.write("\n");stream.flush();os.fsync(stream.fileno())
    finally:
        fcntl.flock(guard,fcntl.LOCK_UN);os.close(guard)


def release(state_dir: Path, proc_root: Path, pid: int) -> None:
    _private_dir(state_dir)
    guard=_guard(state_dir)
    lock=state_dir/".session.lock"
    try:
        owner=lock/"owner.json"
        record=json.loads(owner.read_text(encoding="utf-8"))
        if record.get("pid")!=pid or record.get("start_ticks")!=_ticks(proc_root,pid):
            raise RuntimeError("lifecycle lock ownership changed; preserving it")
        owner.unlink();lock.rmdir()
    finally:
        fcntl.flock(guard,fcntl.LOCK_UN);os.close(guard)


def main(argv: list[str]) -> int:
    try:
        action=argv[1]
        if action=="acquire":
            state_dir,home,proc,tmp,pid,operation=argv[2:]
            acquire(Path(state_dir),Path(home),Path(proc),Path(tmp),int(pid),operation)
        elif action=="release":
            state_dir,proc,pid=argv[2:]
            release(Path(state_dir),Path(proc),int(pid))
        else: raise RuntimeError("unsupported lifecycle lock action")
        return 0
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        print(f"Ternuxx lifecycle lock: {exc}",file=sys.stderr);return 1

if __name__=="__main__":raise SystemExit(main(sys.argv))
