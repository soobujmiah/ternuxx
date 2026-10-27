import bpy, gpu, json, time
from pathlib import Path
p = bpy.ops.wm.redraw_timer.get_rna_type().properties['type']
Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-redraw-enums.json').write_text(json.dumps([e.identifier for e in p.enum_items],indent=2)+'\n')

def measure(n):
    t=time.perf_counter()
    result=bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=n)
    elapsed=time.perf_counter()-t
    return {'iterations':n,'elapsed_s':elapsed,'ms_per_redraw':elapsed*1000/n,'operator_result':list(result)}
# Discard warm-up draws, then measure three short batches for variability.
warm=measure(30)
batches=[measure(60) for _ in range(3)]
data={'backend':'zink-turnip','blender':bpy.app.version_string,'renderer':gpu.platform.renderer_get(),'vendor':gpu.platform.vendor_get(),'file':bpy.data.filepath,'scene':bpy.context.scene.name,'objects':len(bpy.context.scene.objects),'solid_viewports':sum(a.type=='VIEW_3D' and a.spaces.active.shading.type=='SOLID' for s in bpy.data.screens for a in s.areas),'warmup':warm,'batches':batches}
Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-redraw-zink.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data))
