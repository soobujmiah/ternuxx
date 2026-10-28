import bpy, json
from pathlib import Path
engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
payload = {
  "blender": bpy.app.version_string,
  "engine_ids": [item.identifier for item in engines],
  "has_eevee_scene_settings": hasattr(bpy.context.scene, "eevee"),
  "has_eevee_next_scene_settings": hasattr(bpy.context.scene, "eevee_next"),
  "render_resolution": [bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y],
  "visible_preview_objects": [obj.name for obj in bpy.data.collections.get("__TERNux_Benchmark_Preview__", ()).objects] if bpy.data.collections.get("__TERNux_Benchmark_Preview__") else [],
}
Path("/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-blender-60s-ternux-benchmark/gui-capability.json").write_text(json.dumps(payload, indent=2) + "\n")
