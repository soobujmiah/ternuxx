import bpy, json
from pathlib import Path
s=bpy.context.scene
areas=[]
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':
            q=a.spaces.active
            areas.append({'screen':screen.name,'perspective':q.region_3d.view_perspective,'shading':q.shading.type,'camera':s.camera.name if s.camera else None})
d={'scene_camera':s.camera.name if s.camera else None,'camera_count':sum(o.type=='CAMERA' for o in bpy.data.objects),'areas':areas[:12],'file':bpy.data.filepath}
Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/camera-state.json').write_text(json.dumps(d,indent=2)+'\n')
def capture():
 p='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-turnip-camera.png'
 bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=p,check_existing=False)
 return None
bpy.app.timers.register(capture,first_interval=2.0)
