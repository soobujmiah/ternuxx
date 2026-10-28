import bpy, gpu, json, time
from pathlib import Path
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        sp=area.spaces.active
        sp.shading.type='RENDERED'
        sp.region_3d.view_perspective='CAMERA'
        sp.overlay.show_overlays=False
        area.tag_redraw()
def measure(n):
    t=time.perf_counter()
    result=bpy.ops.wm.redraw_timer('EXEC_DEFAULT',type='DRAW_WIN_SWAP',iterations=n)
    elapsed=time.perf_counter()-t
    return {'iterations':n,'elapsed_s':elapsed,'ms_per_redraw':elapsed*1000/n,'operator_result':list(result)}
def run():
    renderer=gpu.platform.renderer_get()
    warm=measure(5)
    batches=[measure(10) for _ in range(3)]
    screenshot='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-rendered-clean.png'
    result=bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=screenshot,check_existing=False)
    data={'backend':'zink-turnip','blender':bpy.app.version_string,'renderer':renderer,'file':bpy.data.filepath,'scene':bpy.context.scene.name,'workspace':bpy.context.workspace.name,'viewport':'RENDERED','camera':bpy.context.scene.camera.name if bpy.context.scene.camera else None,'overlays':False,'warmup':warm,'batches':batches,'screenshot_result':list(result),'screenshot':screenshot}
    Path(screenshot.replace('.png','-info.json')).write_text(json.dumps(data,indent=2)+'\n')
    Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-rendered-redraw-zink-turnip.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data),flush=True)
    return None
bpy.app.timers.register(run,first_interval=15.0)
