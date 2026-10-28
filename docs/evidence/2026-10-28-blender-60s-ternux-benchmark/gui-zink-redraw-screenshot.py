import bpy, gpu, json
from pathlib import Path
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.shading.type='SOLID'
   if area.spaces.active.region_3d and bpy.context.scene.camera:
    area.spaces.active.region_3d.view_perspective='CAMERA'
   area.tag_redraw()
bpy.ops.wm.redraw_timer('EXEC_DEFAULT',type='DRAW_WIN_SWAP',iterations=30)
p='/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-turnip-camera.png'
r=bpy.ops.screen.screenshot('EXEC_DEFAULT',filepath=p,check_existing=False)
Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/screenshots/zink-capture-result.json').write_text(json.dumps({'result':list(r),'renderer':gpu.platform.renderer_get(),'camera':bpy.context.scene.camera.name if bpy.context.scene.camera else None},indent=2)+'\n')
