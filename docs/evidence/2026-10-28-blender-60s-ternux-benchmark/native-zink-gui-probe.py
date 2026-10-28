import bpy, gpu, json, os
from pathlib import Path
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'SOLID'
def report():
    d = {'pid': os.getpid(), 'file': bpy.data.filepath, 'version': bpy.app.version_string,
         'renderer': gpu.platform.renderer_get(), 'vendor': gpu.platform.vendor_get(),
         'gl_version': gpu.platform.version_get(), 'objects': len(bpy.context.scene.objects)}
    Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/native-zink-gui-probe.json').write_text(json.dumps(d,indent=2)+'\n')
    print(json.dumps(d), flush=True)
    return None
bpy.app.timers.register(report, first_interval=6.0)
