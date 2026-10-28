import bpy
from pathlib import Path
p = Path('[external Blender project path redacted]')
assert p.is_file(), f'Missing project: {p}'
bpy.ops.wm.open_mainfile(filepath=str(p))
