import bpy, gpu, json, time
from pathlib import Path
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D': area.spaces.active.shading.type='SOLID'
def capture():
    p='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-turnip.png'
    result=bpy.ops.screen.screenshot('EXEC_DEFAULT', filepath=p, check_existing=False)
    info={'renderer':gpu.platform.renderer_get(),'vendor':gpu.platform.vendor_get(),'version':bpy.app.version_string,'file':bpy.data.filepath,'scene':bpy.context.scene.name,'result':list(result),'screenshot':p,'exists':Path(p).exists()}
    Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-capture-result.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info),flush=True)
    return None
bpy.app.timers.register(capture, first_interval=8.0)
