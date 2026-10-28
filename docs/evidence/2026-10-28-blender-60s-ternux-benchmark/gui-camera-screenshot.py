import bpy, gpu, json
from pathlib import Path
out='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.shading.type='SOLID'
            if space.region_3d and bpy.context.scene.camera:
                space.region_3d.view_perspective='CAMERA'
    for area in screen.areas:
        if area.type=='VIEW_3D': area.tag_redraw()
bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=out+'/zink-turnip-camera.png',check_existing=False)
info={'renderer':gpu.platform.renderer_get(),'version':bpy.app.version_string,'file':bpy.data.filepath,'scene':bpy.context.scene.name,'screenshot':out+'/zink-turnip-camera.png'}
Path(out+'/zink-camera-info.json').write_text(json.dumps(info,indent=2)+'\n')
