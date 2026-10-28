import bpy, gpu, json
from pathlib import Path
out='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/kgsl-rendered-clean.png'
def capture():
    result=bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=out,check_existing=False)
    info={'renderer':gpu.platform.renderer_get(),'version':bpy.app.version_string,'file':bpy.data.filepath,'scene':bpy.context.scene.name,'workspace':bpy.context.workspace.name,'viewport':'RENDERED','result':list(result),'path':out}
    Path(out.replace('.png','-info.json')).write_text(json.dumps(info,indent=2)+'\n')
    return None
bpy.app.timers.register(capture,first_interval=12.0)
