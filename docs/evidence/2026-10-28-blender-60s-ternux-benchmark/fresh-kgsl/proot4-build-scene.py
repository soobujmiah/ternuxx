import bpy, gpu, json
from pathlib import Path

ROOT = Path('/tmp/proot4-blender-test')
ROOT.mkdir(parents=True, exist_ok=True)
# Start from Blender defaults so this scene contains no imported project data.
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene = bpy.context.scene
engines=[item.identifier for item in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in engines else 'BLENDER_EEVEE'
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.fps = 24
scene.render.filepath = str(ROOT / 'still.png')
scene.frame_end = 48
scene.world = bpy.data.worlds.new('Fresh GPU test world')
scene.world.color = (0.035, 0.045, 0.07)

def mat(name, color, metallic=0.0, roughness=0.4, emission=0.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    if emission:
        key = 'Emission Color' if 'Emission Color' in p.inputs else 'Emission'
        p.inputs[key].default_value = (*color, 1)
        p.inputs['Emission Strength'].default_value = emission
    return m

navy=mat('Midnight blue', (0.025,0.08,0.20), 0.28, 0.32)
teal=mat('Teal enamel', (0.02,0.65,0.60), 0.18, 0.28)
coral=mat('Coral', (0.95,0.16,0.12), 0.05, 0.36)
gold=mat('Warm brass', (0.9,0.48,0.08), 0.72, 0.25)
cream=mat('Porcelain', (0.8,0.82,0.72), 0.0, 0.42)

def assign(obj, material):
    obj.data.materials.append(material)
    return obj

# Ground plane + plinth and a deliberately varied but modest test set.
bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-0.18)); assign(bpy.context.object, navy)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=2.45, depth=0.28, location=(0,0,0)); assign(bpy.context.object, gold)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=2.25, depth=0.22, location=(0,0,0.20)); assign(bpy.context.object, teal)
bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=24, radius=0.75, location=(-0.9,0,1.15)); assign(bpy.context.object, coral)
bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=24, radius=0.48, location=(0.65,0,0.92)); assign(bpy.context.object, cream)
bpy.ops.mesh.primitive_torus_add(major_radius=0.75, minor_radius=0.095, major_segments=64, minor_segments=16, location=(-0.9,0,1.2), rotation=(0.9,0.25,0.0)); assign(bpy.context.object, gold)
bpy.ops.mesh.primitive_cube_add(size=0.9, location=(1.35,0.25,0.72), rotation=(0.2,0.15,0.35)); assign(bpy.context.object, navy)
bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.42, radius2=0, depth=1.2, location=(0.25,0.1,1.05)); assign(bpy.context.object, teal)

# Color test bars and emissive markers.
for i, material in enumerate((coral, gold, cream, teal)):
    bpy.ops.mesh.primitive_cube_add(size=0.32, location=(-1.5+i*0.5, -1.65, 0.42))
    cube=bpy.context.object; cube.scale=(0.55,0.25,0.22); assign(cube, material)

# Animation proves this is an actual small project, not only a still.
hero = next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('Sphere'))
hero.location.z=1.0; hero.keyframe_insert(data_path='location', frame=1)
hero.location.z=1.65; hero.keyframe_insert(data_path='location', frame=24)
hero.location.z=1.0; hero.keyframe_insert(data_path='location', frame=48)
scene.frame_set(24)

# Camera and lights.
bpy.ops.object.camera_add(location=(5.8,-8.5,5.3)); camera=bpy.context.object
camera.name='FreshTestCamera'; scene.camera=camera
camera.rotation_euler=(__import__('mathutils').Vector((0,0,0.75))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.lens=48

def area(name, loc, power, color, size):
    bpy.ops.object.light_add(type='AREA', location=loc)
    o=bpy.context.object; o.name=name; o.data.energy=power; o.data.color=color; o.data.shape='DISK'; o.data.size=size
    direction=__import__('mathutils').Vector((0,0,0.6))-o.location
    o.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()
area('Key softbox',(1,-4,7),900,(0.72,0.86,1.0),5.0)
area('Warm fill',(-4,-1,3.5),650,(1.0,0.42,0.2),4.0)
area('Rim light',(2,4,5),1100,(0.15,0.55,1.0),3.0)
scene.camera.data.dof.use_dof=False
scene.view_settings.view_transform='Standard'
scene.view_settings.look='Medium High Contrast'

# Save an independent reproducible project and put the GUI in rendered camera view.
blend = ROOT / 'proot4_fresh_gpu_test.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for screen in bpy.data.screens:
    for area_ in screen.areas:
        if area_.type == 'VIEW_3D':
            area_.spaces.active.region_3d.view_perspective='CAMERA'
            area_.spaces.active.shading.type='RENDERED'
            area_.spaces.active.overlay.show_overlays=False
            area_.tag_redraw()

# Capture after Eevee/viewport shaders have had time to settle.
def capture():
    info={'renderer':gpu.platform.renderer_get(),'vendor':gpu.platform.vendor_get(),'version':bpy.app.version_string,
          'engine':scene.render.engine,'project':str(blend),'scene':scene.name,'objects':len(scene.objects),
          'frame':scene.frame_current,'viewport':'RENDERED','camera':'FreshTestCamera'}
    (ROOT/'proot4_gui_probe.json').write_text(json.dumps(info,indent=2)+'\n')
    try: bpy.ops.screen.screenshot('EXEC_DEFAULT', filepath=str(ROOT/'proot4-rendered.png'), check_existing=False)
    except Exception as e: info['screenshot_error']=repr(e)
    (ROOT/'proot4_gui_probe.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info), flush=True)
    return None
bpy.app.timers.register(capture, first_interval=18.0)
