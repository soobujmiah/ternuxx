import bpy, json
from pathlib import Path
p='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/kgsl-direct.png'
try:
    result=bpy.ops.screen.screenshot('EXEC_DEFAULT', filepath=p, check_existing=False)
    payload={'result':list(result),'exists':Path(p).exists(),'path':p}
except Exception as e:
    payload={'error':repr(e),'path':p}
Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/kgsl-capture-result.json').write_text(json.dumps(payload,indent=2)+'\n')
