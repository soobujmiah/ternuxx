import bpy, gpu, json, time
from pathlib import Path
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='RENDERED'
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.overlay.show_overlays=False
            area.tag_redraw()
def measure(n):
    t=time.perf_counter()
    result=bpy.ops.wm.redraw_timer('EXEC_DEFAULT',type='DRAW_WIN_SWAP',iterations=n)
    elapsed=time.perf_counter()-t
    return {'iterations':n,'elapsed_s':elapsed,'ms_per_redraw':elapsed*1000/n,'operator_result':list(result)}
renderer=gpu.platform.renderer_get()
backend='zink-turnip' if 'zink' in renderer.lower() else 'kgsl-direct'
warm=measure(5)
batches=[measure(10) for _ in range(3)]
data={'backend':backend,'blender':bpy.app.version_string,'renderer':renderer,'file':bpy.data.filepath,'scene':bpy.context.scene.name,'viewport':'RENDERED','camera':bpy.context.scene.camera.name if bpy.context.scene.camera else None,'overlays':False,'warmup':warm,'batches':batches}
out=f'/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-rendered-redraw-{backend}.json'
Path(out).write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data),flush=True)
