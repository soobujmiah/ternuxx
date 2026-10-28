import bpy, gpu, json, time
from pathlib import Path
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'SOLID'
def measure(n):
    t=time.perf_counter()
    result=bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=n)
    elapsed=time.perf_counter()-t
    return {'iterations':n,'elapsed_s':elapsed,'ms_per_redraw':elapsed*1000/n,'operator_result':list(result)}
def run():
    renderer=gpu.platform.renderer_get()
    backend='zink-turnip' if 'zink' in renderer.lower() else 'kgsl-direct'
    warm=measure(30)
    batches=[measure(60) for _ in range(3)]
    data={'backend':backend,'blender':bpy.app.version_string,'renderer':renderer,'vendor':gpu.platform.vendor_get(),'gl_version':gpu.platform.version_get(),'file':bpy.data.filepath,'scene':bpy.context.scene.name,'objects':len(bpy.context.scene.objects),'solid_viewports':sum(a.type=='VIEW_3D' and a.spaces.active.shading.type=='SOLID' for s in bpy.data.screens for a in s.areas),'warmup':warm,'batches':batches}
    out='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-redraw-'+backend+'.json'
    Path(out).write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data),flush=True)
    return None
bpy.app.timers.register(run, first_interval=8.0)
