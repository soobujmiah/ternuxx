import bpy
obj = bpy.data.objects.get("Agent GUI Bridge Test")
if obj:
    mesh = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh and mesh.users == 0:
        bpy.data.meshes.remove(mesh)
print("VISIBLE_GUI_BRIDGE_TEST_CLEANED", bool(obj))
