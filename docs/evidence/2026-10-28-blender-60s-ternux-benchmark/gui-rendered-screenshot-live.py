import bpy, gpu, json
from pathlib import Path
screen=bpy.context.screen
for area in screen.areas if screen else []:
    if area.type=='VIEW_3D':
        sp=area.spaces.active
        sp.shading.type='RENDERED'
        sp.region_3d.view_perspective='CAMERA'
        sp.overlay.show_overlays=False
        area.tag_redraw()
bpy.ops.wm.redraw_timer('EXEC_DEFAULT',type='DRAW_WIN_SWAP',iterations=30)
def capture():
    renderer=gpu.platform.renderer_get()
    backend='zink-turnip' if 'zink' in renderer.lower() else 'kgsl-direct'
    out=f'/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/{backend}-rendered.png'
    result=bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=out,check_existing=False)
    data={'renderer':renderer,'version':bpy.app.version_string,'file':bpy.data.filepath,'scene':bpy.context.scene.name,'workspace':bpy.context.workspace.name,'camera':bpy.context.scene.camera.name if bpy.context.scene.camera else None,'viewport_mode':'RENDERED','overlays':False,'wait_after_open_s':12,'result':list(result),'screenshot':out}
    Path(out.replace('.png','-info.json')).write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data),flush=True)
    return None
bpy.app.timers.register(capture,first_interval=12.0)
