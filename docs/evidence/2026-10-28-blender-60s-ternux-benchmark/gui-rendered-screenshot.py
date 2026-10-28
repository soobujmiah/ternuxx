import bpy, gpu, json
from pathlib import Path
screen=bpy.context.screen
changed=0
for area in screen.areas if screen else []:
    if area.type=='VIEW_3D':
        sp=area.spaces.active
        sp.shading.type='RENDERED'
        sp.region_3d.view_perspective='CAMERA'
        sp.overlay.show_overlays=False
        area.tag_redraw()
        changed+=1
bpy.ops.wm.redraw_timer('EXEC_DEFAULT',type='DRAW_WIN_SWAP',iterations=30)
def capture():
    out='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-rendered.png'
    result=bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=out,check_existing=False)
    data={'renderer':gpu.platform.renderer_get(),'version':bpy.app.version_string,'file':bpy.data.filepath,'scene':bpy.context.scene.name,'workspace':bpy.context.workspace.name,'rendered_areas_set':changed,'result':list(result),'screenshot':out}
    Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-rendered-info.json').write_text(json.dumps(data,indent=2)+'\n')
    return None
bpy.app.timers.register(capture,first_interval=8.0)
