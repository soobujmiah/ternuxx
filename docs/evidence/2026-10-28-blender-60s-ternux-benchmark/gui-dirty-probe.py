import bpy, json
from pathlib import Path
Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-dirty-state.json').write_text(json.dumps({'filepath': bpy.data.filepath, 'is_dirty': bpy.data.is_dirty, 'version': bpy.app.version_string},indent=2)+'\n')
