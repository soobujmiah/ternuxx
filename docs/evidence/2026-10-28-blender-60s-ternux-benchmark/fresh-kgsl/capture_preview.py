import bpy, gpu, json
from pathlib import Path
ROOT=Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl')
for s in bpy.data.screens:
    for a in s.areas:
        if a.type=='VIEW_3D':
            a.spaces.active.region_3d.view_perspective='CAMERA'
            a.spaces.active.shading.type='RENDERED'
            a.spaces.active.overlay.show_overlays=False
            a.tag_redraw()
def cap():
    d={'renderer':gpu.platform.renderer_get(),'vendor':gpu.platform.vendor_get(),'version':bpy.app.version_string,
       'engine':bpy.context.scene.render.engine,'project':bpy.data.filepath,'scene':bpy.context.scene.name,
       'objects':len(bpy.context.scene.objects),'frame':bpy.context.scene.frame_current,'viewport':'RENDERED'}
    try: bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=str(ROOT/'zink-rendered.png'),check_existing=False)
    except Exception as e: d['screenshot_error']=repr(e)
    (ROOT/'zink_gui_probe.json').write_text(json.dumps(d,indent=2)+'\n')
    print(json.dumps(d),flush=True)
    return None
bpy.app.timers.register(cap,first_interval=25.0)
