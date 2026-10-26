"""Fixed installer handoff from authenticated management clients; no shell API."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import stat
import subprocess

TARGETS = {"workstation": ("install",), "gpu": ("install", "gpu")}


def command(target: str, *, prefix: str) -> list[str]:
    if target not in TARGETS:
        raise ValueError("choose workstation or gpu installer")
    if prefix != "/data/data/com.termux/files/usr":
        raise ValueError("Native Termux is required")
    executable = Path(prefix) / "bin/tx"
    info = executable.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or not os.access(executable, os.X_OK):
        raise ValueError("installed Native tx command is unavailable or unsafe")
    return [str(executable), *TARGETS[target]]


def open_terminal(target: str, *, home: str, prefix: str, runner=subprocess.run) -> dict:
    argv = command(target, prefix=prefix)
    properties = Path(home) / ".termux/termux.properties"
    allowed = False
    if properties.is_file() and not properties.is_symlink() and properties.stat().st_size < 256 * 1024:
        for line in properties.read_text(errors="replace").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "allow-external-apps":
                allowed = value.strip().lower() == "true"
    fallback = "tx " + " ".join(TARGETS[target])
    if not allowed:
        return {"status": "manual_action_required", "command": fallback,
                "message": "Native terminal handoff needs the owner's allow-external-apps setting. It was not changed. Run the displayed command in Termux, or explicitly enable that bridge."}
    am = shutil.which("am", path=prefix + "/bin:/system/bin")
    if not am:
        raise ValueError("Android terminal handoff is unavailable; run " + fallback)
    result = runner([am, "startservice", "-n", "com.termux/com.termux.app.RunCommandService",
        "-a", "com.termux.RUN_COMMAND", "--es", "com.termux.RUN_COMMAND_PATH", argv[0],
        "--esa", "com.termux.RUN_COMMAND_ARGUMENTS", ",".join(argv[1:]),
        "--es", "com.termux.RUN_COMMAND_WORKDIR", home,
        "--ez", "com.termux.RUN_COMMAND_BACKGROUND", "false",
        "--es", "com.termux.RUN_COMMAND_SESSION_ACTION", "0"],
        capture_output=True, text=True, timeout=15, check=False)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode or "error" in output.lower() or "exception" in output.lower():
        raise ValueError("Termux declined the terminal handoff; run " + fallback)
    return {"status": "launch_requested", "command": fallback,
            "message": "Continue in the Native installer terminal. No package result is claimed by this handoff."}
