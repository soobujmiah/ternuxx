import bpy, gpu, json, time
from pathlib import Path
OUT=Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/fresh-kgsl')
area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
space=area.spaces.active
space.shading.type='RENDERED'
space.overlay.show_overlays=False
space.region_3d.view_perspective='CAMERA'
area.tag_redraw()
time.sleep(2)
measure=[]
for n in (5,20,20,20):
    t=time.perf_counter(); result=bpy.ops.wm.redraw_timer('EXEC_DEFAULT',type='DRAW_WIN_SWAP',iterations=n); elapsed=time.perf_counter()-t
    measure.append({'iterations':n,'elapsed_s':elapsed,'ms_per_redraw':elapsed*1000/n,'result':list(result)})
data={'renderer':gpu.platform.renderer_get(),'version':bpy.app.version_string,'engine':bpy.context.scene.render.engine,'file':bpy.data.filepath,'scene':bpy.context.scene.name,'objects':len(bpy.context.scene.objects),'frame':bpy.context.scene.frame_current,'viewport':space.region_3d.view_perspective,'camera':bpy.context.scene.camera.name if bpy.context.scene.camera else None,'measurements':measure}
bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=str(OUT/'proot4-camera-rendered.png'),check_existing=False)
(OUT/'proot4-gui-probe.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data),flush=True)
