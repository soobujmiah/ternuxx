#!/data/data/com.termux/files/usr/bin/python3
"""Run the same visible GLX glmark2 scenes through Native KGSL or Native Zink/Turnip."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
ROOT = HOME / "ternuxx"
STATE = HOME / ".local/share/ternuxx"
PREFIX = Path(os.environ["PREFIX"])
PROVIDER = STATE / "graphics/providers/native-mesa-0219ff84"
MESA = PROVIDER / "extracted/data/data/com.termux/files/usr"
ICD = PROVIDER / "freedreno-isolated.json"
sys.path.insert(0, str(ROOT / "lib"))
import graphics_manager

p = argparse.ArgumentParser()
p.add_argument("backend", choices=["kgsl", "zink"])
p.add_argument("--duration", type=int, default=4)
a = p.parse_args()
base = dict(os.environ)
base.update({"PREFIX": str(PREFIX), "DISPLAY": ":1"})
env = graphics_manager.native_process_environment(
    home=str(HOME), state_dir=str(STATE), process_env=base)
env["DISPLAY"] = ":1"
env["MESA_SHADER_CACHE_DISABLE"] = "true"
if a.backend == "zink":
    env.pop("LIBGL_ALWAYS_SOFTWARE", None)
    env.pop("VK_DRIVER_FILES", None)
    env["MESA_LOADER_DRIVER_OVERRIDE"] = "zink"
    env["GALLIUM_DRIVER"] = "zink"
    env["TU_DEBUG"] = "noconform"
    env["MESA_VK_WSI_DEBUG"] = "sw"
    env["VK_ICD_FILENAMES"] = str(ICD)
    expected = "zink"
else:
    env["MESA_LOADER_DRIVER_OVERRIDE"] = "kgsl"
    env.pop("GALLIUM_DRIVER", None)
    expected = "Adreno (TM) 825"

probe = subprocess.run([str(PREFIX / "bin/glxinfo"), "-B"], env=env,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=20, check=False)
renderer = next((line.split(":", 1)[1].strip() for line in probe.stdout.splitlines()
                if line.strip().startswith("OpenGL renderer string:")), "")
if probe.returncode or expected.lower() not in renderer.lower():
    print(f"BACKEND PRECHECK FAILED: expected={expected!r}, renderer={renderer!r}, rc={probe.returncode}", flush=True)
    print(probe.stdout, flush=True)
    raise SystemExit(20)
print(f"Visible glmark2 A/B; requested={a.backend}; display=:1; renderer={renderer}; duration={a.duration}s/scene", flush=True)
cmd = [str(PREFIX / "bin/glmark2"), "--size", "640x360", "--frame-end", "finish",
       "--swap-mode", "immediate", "--annotate",
       "--benchmark", f"build:duration={a.duration}",
       "--benchmark", f"texture:duration={a.duration}",
       "--benchmark", f"shading:duration={a.duration}"]
started = time.monotonic()
proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1)
lines = []
assert proc.stdout is not None
for line in proc.stdout:
    lines.append(line)
    print(line, end="", flush=True)
rc = proc.wait()
print(f"EXIT={rc} WALL_SECONDS={time.monotonic()-started:.2f} REQUESTED_BACKEND={a.backend}", flush=True)
raise SystemExit(rc)
