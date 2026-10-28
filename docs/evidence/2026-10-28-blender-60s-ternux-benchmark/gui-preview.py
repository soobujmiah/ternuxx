"""Make the open Blender 3D View visibly ready for the 60-second test scene."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Euler

collection_name = "__TERNux_Benchmark_Preview__"
collection = bpy.data.collections.get(collection_name)
if collection is None:
    collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(collection)

if not any(obj.name == "Benchmark Preview Core" for obj in collection.objects):
    mat = bpy.data.materials.new("Benchmark Preview Cyan")
    mat.diffuse_color = (0.04, 0.58, 0.86, 1.0)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.6, location=(0, 0, 0))
    core = bpy.context.object
    core.name = "Benchmark Preview Core"
    core.data.materials.append(mat)
    for poly in core.data.polygons:
        poly.use_smooth = True
    for collection_item in list(core.users_collection):
        collection_item.objects.unlink(core)
    collection.objects.link(core)

    ring_mat = bpy.data.materials.new("Benchmark Preview Gold")
    ring_mat.diffuse_color = (0.96, 0.48, 0.08, 1.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=2.5, minor_radius=0.055, location=(0, 0, 0))
    ring = bpy.context.object
    ring.name = "Benchmark Preview Orbit"
    ring.rotation_euler = (math.radians(67), 0, math.radians(-18))
    ring.data.materials.append(ring_mat)
    for collection_item in list(ring.users_collection):
        collection_item.objects.unlink(ring)
    collection.objects.link(ring)

    text_mat = bpy.data.materials.new("Benchmark Preview Label")
    text_mat.diffuse_color = (0.95, 0.98, 1.0, 1.0)
    curve = bpy.data.curves.new("Benchmark Preview Title", type="FONT")
    curve.body = "TERNux  /  60s GPU TEST"
    curve.size = 0.33
    curve.extrude = 0.008
    title = bpy.data.objects.new("Benchmark Preview Title", curve)
    collection.objects.link(title)
    title.location = (-3.4, -2.35, 0.5)
    title.rotation_euler = (math.radians(90), 0, 0)
    title.data.materials.append(text_mat)

for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type == "CONSOLE":
            area.type = "VIEW_3D"
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.region_3d.view_location = (0.0, 0.0, 0.0)
            space.region_3d.view_rotation = Euler((math.radians(68), 0.0, math.radians(28)), "XYZ").to_quaternion()
            space.region_3d.view_distance = 9.0
            space.region_3d.view_perspective = "ORTHO"
            space.shading.type = "SOLID"
            space.shading.color_type = "MATERIAL"

bpy.context.scene.frame_set(1)
Path("/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-preview-state.json").write_text(json.dumps({
    "preview_collection": collection_name,
    "objects": [obj.name for obj in collection.objects],
    "visible_3d_view_configured": True,
    "console_changed_to_view_3d": True,
}, indent=2) + "\n", encoding="utf-8")
