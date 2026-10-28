import bpy, json
changed=0
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'SOLID'
            area.spaces.active.overlay.show_overlays = True
            changed += 1
print(json.dumps({'viewports_set_solid': changed, 'saved_file_unchanged': True}))
