"""Secure saved graphics preference for future managed PRoot desktop starts."""
from __future__ import annotations
import os
from pathlib import Path
import stat
import tempfile

NAME = "proot-graphics-backend"
VALID = {"cpu", "zink"}


def _path(home: str, state_dir: str | None = None, *, create: bool = False) -> Path:
    root = Path(state_dir) if state_dir else Path(home) / ".local/share/ternuxx"
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("PRoot graphics state directory is unsafe")
    if root.exists():
        meta = root.stat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
            raise ValueError("PRoot graphics state directory owner or mode is unsafe")
    elif create:
        root.mkdir(mode=0o700, parents=True)
    return root / NAME


def status(*, home: str, state_dir: str | None = None) -> dict[str, str]:
    path = _path(home, state_dir)
    try:
        meta = path.lstat()
    except FileNotFoundError:
        return {"backend": "zink" if os.access("/dev/kgsl-3d0", os.R_OK) else "cpu",
                "source": "legacy-default", "applies": "future PRoot desktop starts"}
    if not stat.S_ISREG(meta.st_mode) or stat.S_ISLNK(meta.st_mode) or meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600:
        raise ValueError("saved PRoot graphics preference is unsafe")
    value = path.read_text(encoding="ascii")
    if value not in {"cpu\n", "zink\n"}:
        raise ValueError("saved PRoot graphics preference is invalid")
    return {"backend": value.strip(), "source": "saved", "applies": "future PRoot desktop starts"}


def select(backend: str, *, home: str, state_dir: str | None = None) -> dict[str, object]:
    if backend not in VALID:
        raise ValueError("PRoot backend must be cpu or zink")
    path = _path(home, state_dir, create=True)
    current = status(home=home, state_dir=state_dir)
    if current["backend"] == backend and current["source"] == "saved":
        return {**current, "changed": False}
    fd, temporary = tempfile.mkstemp(prefix=".proot-graphics-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(backend + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return {"backend": backend, "source": "saved", "changed": True,
            "applies": "future PRoot desktop starts"}


if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "select"))
    parser.add_argument("backend", nargs="?", choices=sorted(VALID))
    args = parser.parse_args()
    home = os.environ["HOME"]
    state = os.environ.get("TERNUXX_STATE_DIR")
    result = status(home=home, state_dir=state) if args.action == "status" else select(args.backend, home=home, state_dir=state)
    print(json.dumps(result, sort_keys=True))
