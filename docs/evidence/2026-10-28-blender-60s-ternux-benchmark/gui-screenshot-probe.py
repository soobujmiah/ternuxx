import bpy, json
from pathlib import Path
try:
    op=bpy.ops.screen.screenshot
    info={'available':True,'properties':[p.identifier for p in op.get_rna_type().properties]}
except Exception as e:
    info={'available':False,'error':str(e)}
Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-screenshot-operator.json').write_text(json.dumps(info,indent=2)+'\n')
