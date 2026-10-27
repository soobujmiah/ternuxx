import bpy
name = "Agent GUI Bridge Test"
mesh = bpy.data.meshes.new(name + "Mesh")
mesh.from_pydata([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)], [], [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)])
mesh.update()
obj = bpy.data.objects.new(name, mesh)
bpy.context.scene.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
print("VISIBLE_GUI_BRIDGE_TEST_CREATED", name)
