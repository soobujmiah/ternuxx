import bpy
import math
import sys
from pathlib import Path

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = Path(args[0]) if args else Path("/tmp/blender-smoke.png")
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(out)
scene.render.film_transparent = False
scene.world.color = (0.03, 0.03, 0.03)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=(0, 0, 0))
sphere = bpy.context.object
sphere.name = "GPU smoke sphere"
mat = bpy.data.materials.new("Smoke material")
mat.diffuse_color = (0.12, 0.36, 0.72, 1)
sphere.data.materials.append(mat)
light_data = bpy.data.lights.new("Key", "AREA")
light_data.energy = 450
light = bpy.data.objects.new("Key", light_data)
scene.collection.objects.link(light)
light.location = (3, -4, 5)
light.rotation_euler = (math.radians(25), 0, math.radians(30))
cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
cam.location = (3, -5, 2.5)
cam.rotation_euler = (math.radians(73), 0, math.radians(31))
scene.camera = cam
scene.render.image_settings.color_mode = "RGBA"
bpy.ops.render.render(write_still=True)
print("SMOKE_OUTPUT:", out)
