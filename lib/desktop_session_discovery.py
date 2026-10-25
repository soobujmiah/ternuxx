#!/usr/bin/env python3
"""Resolve a live desktop state directory only from its verified supervisor."""
import json
from pathlib import Path
import sys
import stat
if len(sys.argv) != 4:
    raise SystemExit(2)
script=Path(sys.argv[1]).resolve()
home=Path(sys.argv[2]).resolve()
default=Path(sys.argv[3]).resolve()
if (default/"session.json").is_file():
    raise SystemExit(1)
def ticks(pid):
    raw=Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    return raw[raw.rfind(")")+2:].split()[19]
found=set()
for entry in Path("/proc").iterdir():
    if not entry.name.isdigit():
        continue
    try:
        pid=int(entry.name)
        argv=[x.decode("utf-8","surrogateescape") for x in (entry/"cmdline").read_bytes().split(b"\0") if x]
        if len(argv)<4 or Path(argv[1]).resolve()!=script:
            continue
        candidate=Path(argv[3]).resolve()
        candidate.relative_to(home)
        if candidate.stat().st_mode & 0o077:
            continue
        state_path=candidate/"session.json"
        state_info=state_path.lstat()
        if not stat.S_ISREG(state_info.st_mode) or state_info.st_mode & 0o077:
            continue
        state=json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("owner")!="ternuxx" or state.get("provider") not in ("native", "proot"):
            continue
        role=state.get("supervisor",{})
        if (state.get("status")!="running" or role.get("pid")!=pid
            or role.get("command_marker")!=script.name or role.get("start_ticks")!=ticks(pid)):
            continue
        valid=True
        desktop_marker = "xfce4-session" if state.get("provider") == "native" else "proot-display0"
        for name,marker in (("x11","termux-x11"),("desktop",desktop_marker)):
            item=state.get(name,{})
            child=item.get("pid")
            if (not isinstance(child,int) or item.get("command_marker")!=marker
                or item.get("pgid")!=child or item.get("sid")!=child
                or item.get("start_ticks")!=ticks(child)
                or (marker not in Path(f"/proc/{child}/cmdline").read_bytes().decode("utf-8","replace")
                    and not (state.get("provider") == "proot" and name == "desktop"))):
                valid=False
                break
        if valid:
            found.add(str(candidate))
    except (OSError,ValueError,KeyError,TypeError):
        continue
if len(found)!=1:
    raise SystemExit(1)
print(found.pop())
