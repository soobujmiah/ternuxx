"""Bounded readers for exact Ternuxx-owned diagnostic logs."""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import re
import stat

MAX_TAIL_BYTES = 256 * 1024
ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
SOURCES = {
    "native-desktop": ("Native desktop session", ("desktop.log",)),
    "cron-scheduler": ("Cron scheduler", ("cron", "scheduler.log")),
    "management-api": ("Management API audit", ("management-api", "audit.jsonl")),
}

class LogReadError(ValueError):
    pass

def _root(state_dir: str, home: str) -> Path:
    home_path = Path(home).expanduser().resolve()
    lexical = Path(state_dir).expanduser()
    if not lexical.is_absolute():
        raise LogReadError("state directory must be absolute")
    absolute = lexical.absolute()
    try:
        relative = absolute.relative_to(home_path)
    except ValueError as exc:
        raise LogReadError("state directory must remain below HOME") from exc
    current = home_path
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                raise LogReadError("state directory contains a symbolic link")
        except OSError as exc:
            raise LogReadError("state directory cannot be inspected") from exc
    root = lexical.resolve(strict=False)
    if root == home_path or home_path not in root.parents:
        raise LogReadError("state directory must remain below HOME")
    try:
        info = root.lstat()
    except FileNotFoundError:
        return root
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise LogReadError("Ternuxx state directory is not private and owned")
    return root

def _inspect(root: Path, parts: tuple[str, ...]):
    current = root
    for part in parts[:-1]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return current / parts[-1], None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise LogReadError("log source directory is not private and owned")
    path = current / parts[-1]
    try:
        info = path.lstat()
    except FileNotFoundError:
        return path, None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise LogReadError("log source is not a private owned regular file")
    return path, info

def list_logs(state_dir: str, *, home: str) -> dict[str, object]:
    root = _root(state_dir, home)
    sources = []
    for source_id, (label, parts) in SOURCES.items():
        _, info = _inspect(root, parts)
        sources.append({"source_id": source_id, "label": label,
                        "status": "available" if info else "missing",
                        "size_bytes": info.st_size if info else 0,
                        "updated_at": dt.datetime.fromtimestamp(info.st_mtime, dt.timezone.utc).isoformat() if info else None,
                        "max_lines": 300})
    return {"sources": sources, "read_only": True}

def _clean_line(line: str) -> str:
    line = ANSI.sub("", line)
    return "".join(ch for ch in line if ch == "\t" or (ord(ch) >= 32 and ord(ch) != 127))[:4096]

def _native_desktop_label(root: Path) -> str:
    """Name the desktop recorded by the Native supervisor, defaulting to XFCE."""
    try:
        from native_desktops import NATIVE_DESKTOPS
        path, info = _inspect(root, ("session.json",))
        if info is not None:
            raw = path.read_text(encoding="utf-8")
            if len(raw) <= 64 * 1024:
                desktop_id = json.loads(raw).get("desktop_id")
                item = NATIVE_DESKTOPS.get(desktop_id)
                if item:
                    return f"Native desktop session ({item['name']})"
    except (OSError, ValueError, TypeError):
        pass
    return "Native desktop session (XFCE)"

def read_log(state_dir: str, *, home: str, source_id: str, limit: int = 100) -> dict[str, object]:
    if source_id not in SOURCES:
        raise LogReadError("unknown log source")
    if type(limit) is not int or not 1 <= limit <= 300:
        raise LogReadError("line limit must be between 1 and 300")
    label, parts = SOURCES[source_id]
    root = _root(state_dir, home)
    if source_id == "native-desktop":
        label = _native_desktop_label(root)
    path, before = _inspect(root, parts)
    if before is None:
        return {"source_id": source_id, "label": label, "status": "missing", "lines": [], "truncated": False, "read_only": True}
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise LogReadError("log source could not be opened safely") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise LogReadError("log source identity changed")
        start = max(0, info.st_size - MAX_TAIL_BYTES)
        os.lseek(fd, start, os.SEEK_SET)
        data = bytearray()
        while len(data) < MAX_TAIL_BYTES:
            chunk = os.read(fd, min(16384, MAX_TAIL_BYTES - len(data)))
            if not chunk:
                break
            data.extend(chunk)
    finally:
        os.close(fd)
    raw_lines = bytes(data).decode("utf-8", "replace").splitlines()
    truncated = start > 0
    if truncated and raw_lines:
        raw_lines = raw_lines[1:]
    if source_id == "management-api":
        lines = []
        for raw in raw_lines[-limit:]:
            try:
                item = json.loads(raw)
            except ValueError:
                lines.append("[invalid audit record omitted]")
                continue
            if isinstance(item, dict):
                fields = ("occurred_at_utc", "operation", "capability", "event", "http_status", "duration_ms")
                lines.append(" ".join(f"{key}={_clean_line(str(item.get(key, '')))}" for key in fields))
    else:
        lines = [_clean_line(line) for line in raw_lines[-limit:]]
    return {"source_id": source_id, "label": label, "status": "available", "lines": lines, "truncated": truncated, "read_only": True}
