import bpy, gpu, json, os
from pathlib import Path
scene=bpy.context.scene
objs=list(scene.objects)
info={
 'file': bpy.data.filepath,
 'version': bpy.app.version_string,
 'scene': scene.name,
 'objects': len(objs),
 'mesh_objects': sum(o.type=='MESH' for o in objs),
 'vertices': sum(len(o.data.vertices) for o in objs if o.type=='MESH'),
 'resolution': [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
 'engine': scene.render.engine,
 'viewport_shading': [a.spaces.active.shading.type for s in bpy.data.screens for a in s.areas if a.type=='VIEW_3D'],
 'renderer': gpu.platform.renderer_get(),
 'vendor': gpu.platform.vendor_get(),
 'version_gl': gpu.platform.version_get(),
 'gpu_backend': bpy.context.preferences.system.gpu_backend,
 'display': os.environ.get('DISPLAY'),
 'gallium_driver': os.environ.get('GALLIUM_DRIVER'),
 'mesa_gl_version_override': os.environ.get('MESA_GL_VERSION_OVERRIDE'),
}
Path('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-runtime-probe.json').write_text(json.dumps(info,indent=2)+'\n')
print(json.dumps(info))
