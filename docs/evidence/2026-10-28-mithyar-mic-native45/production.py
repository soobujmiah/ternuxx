import bpy, math, os
from mathutils import Matrix, Vector
R='/sdcard/Blender/bangla-short-films/mithyar-mic-2026-10-14/'
sc=bpy.context.scene
sc.frame_start=1;sc.frame_end=1440
# Clear only objects/markers from a previous pass of this task script.
for ob in list(bpy.data.objects):
    if ob.name.startswith(('SHOT_','SUBTITLE_','ENDCARD_','Youth_Filming_Phone','Youth_Phone_','Microphone_Gain_Knob')):bpy.data.objects.remove(ob,do_unlink=True)
for m in list(sc.timeline_markers):
    if m.name.startswith('SHOT_') or m.name=='END_CARD':sc.timeline_markers.remove(m)
def aim(cam,target):cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
def camera(name,loc,target,lens):
    data=bpy.data.cameras.new(name+'_Lens');ob=bpy.data.objects.new(name,data);sc.collection.objects.link(ob);ob.location=loc;aim(ob,target);data.lens=lens;data.sensor_width=36
    data.dof.use_dof=False
    return ob
shots={
 'SHOT_WIDE':camera('SHOT_WIDE',(0,-10.8,3.2),(0,.7,1.15),49),
 'SHOT_LEADER':camera('SHOT_LEADER',(-3,-4.6,2.35),(-3,-.2,1.42),55),
 'SHOT_REPORTER':camera('SHOT_REPORTER',(-1.45,-4.7,1.95),(-1.25,-.15,1.02),52),
 'SHOT_LEAK':camera('SHOT_LEAK',(-.35,-5.5,1.55),(-.15,-.35,.48),52),
 'SHOT_BANNER':camera('SHOT_BANNER',(-2.5,-6.6,2.8),(-2.5,.9,2.05),52),
 'SHOT_FAMILY':camera('SHOT_FAMILY',(2.32,-4.7,1.65),(2.32,-.1,1.00),52),
 'SHOT_END_CARD':camera('SHOT_END_CARD',(0,-12,1.5),(0,0,1.5),50),
}
# Retire the old one-angle camera but keep it in the file for later comparison.
old=bpy.data.objects.get('Main_Camera')
if old:old.hide_render=True
# Camera cuts preserve the requested original story beats exactly.
cuts=[(1,'SHOT_WIDE'),(109,'SHOT_LEADER'),(275,'SHOT_LEADER'),(529,'SHOT_LEAK'),(643,'SHOT_REPORTER'),(724,'SHOT_LEADER'),(865,'SHOT_LEADER'),(961,'SHOT_BANNER'),(1084,'SHOT_FAMILY'),(1364,'SHOT_END_CARD')]
for frame,name in cuts:
    marker=sc.timeline_markers.new('SHOT_'+name.replace('SHOT_',''),frame=frame);marker.camera=shots[name]
sc.camera=shots['SHOT_WIDE']
# Helpers used only by the Bengali moral end card image; no dialogue subtitle cards are created.
def image_material(name,path):
    im=bpy.data.images.load(path,check_existing=False)
    if im.packed_file is None:im.pack()
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
    out=nt.nodes.new('ShaderNodeOutputMaterial');p=nt.nodes.new('ShaderNodeBsdfPrincipled');tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im
    p.inputs['Roughness'].default_value=1
    if 'Emission Color' in p.inputs:p.inputs['Emission Color'].default_value=(1,1,1,1);p.inputs['Emission Strength'].default_value=1
    nt.links.new(tex.outputs['Color'],p.inputs['Base Color'])
    if 'Emission Color' in p.inputs:nt.links.new(tex.outputs['Color'],p.inputs['Emission Color'])
    nt.links.new(tex.outputs['Alpha'],p.inputs['Alpha']);nt.links.new(p.outputs['BSDF'],out.inputs['Surface'])
    try:m.surface_render_method='DITHERED'
    except Exception:pass
    return m
def make_plane(name,cam,mat,w,h,local_loc):
    me=bpy.data.meshes.new(name+'Mesh');me.from_pydata([(-w/2,-h/2,0),(w/2,-h/2,0),(w/2,h/2,0),(-w/2,h/2,0)],[],[(0,1,2,3)]);me.update()
    uv=me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi=me.loops[li].vertex_index;uv.data[li].uv=[(0,0),(1,0),(1,1),(0,1)][vi]
    ob=bpy.data.objects.new(name,me);sc.collection.objects.link(ob);ob.data.materials.append(mat);ob.parent=cam;ob.location=local_loc;ob.rotation_euler=(0,0,0);ob.scale=(0,0,0);return ob
def visibility(obj,start,end):
    for frame,val in ((1,0),(max(1,start-1),0),(start,1),(end,1),(min(sc.frame_end,end+1),0)):
        obj.scale=(val,val,val);obj.keyframe_insert(data_path='scale',frame=frame)
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:kp.interpolation='CONSTANT'
# Final message card on black, with a separate emissive Bengali image plane.
end=shots['SHOT_END_CARD']
bgmat=bpy.data.materials.new('End card matte black');bgmat.diffuse_color=(.006,.008,.012,1);bgmat.use_nodes=True;bs=bgmat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.006,.008,.012,1);bs.inputs['Roughness'].default_value=1
bg=make_plane('ENDCARD_Black',end,bgmat,40,24,(0,0,-6))
endmat=image_material('Bengali_Moral_EndCard',R+'captions/end_card.png');card=make_plane('ENDCARD_Moral_Bengali',end,endmat,3.7,1.04,(0,0,-5.8))
for ob in (bg,card):
    for fr,val in ((1363,0),(1364,1),(1440,1)):
        ob.scale=(val,val,val);ob.keyframe_insert(data_path='scale',frame=fr)
    if ob.animation_data and ob.animation_data.action:
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:kp.interpolation='CONSTANT'
# Rounded, two-sided smartphone seated at Youth's lifted left palm; rear cameras face the shot.
yrig=bpy.data.objects['Youth_RIG']
phone_mat=bpy.data.materials.get('Phone graphite') or bpy.data.materials.new('Phone graphite')
phone_mat.diffuse_color=(.025,.035,.045,1);phone_mat.use_nodes=True
phone_mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.025,.035,.045,1)
phone_mat.node_tree.nodes.get('Principled BSDF').inputs['Metallic'].default_value=.48
phone_mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.28
glass_mat=bpy.data.materials.get('Phone glass display') or bpy.data.materials.new('Phone glass display')
glass_mat.diffuse_color=(.012,.022,.032,1);glass_mat.use_nodes=True
gbs=glass_mat.node_tree.nodes.get('Principled BSDF');gbs.inputs['Base Color'].default_value=(.012,.022,.032,1);gbs.inputs['Metallic'].default_value=.12;gbs.inputs['Roughness'].default_value=.2
lens_mat=bpy.data.materials.get('Phone camera glass') or bpy.data.materials.new('Phone camera glass')
lens_mat.diffuse_color=(.008,.018,.032,1);lens_mat.use_nodes=True
lbs=lens_mat.node_tree.nodes.get('Principled BSDF');lbs.inputs['Base Color'].default_value=(.008,.018,.032,1);lbs.inputs['Metallic'].default_value=.35;lbs.inputs['Roughness'].default_value=.16
chrome_mat=bpy.data.materials.get('Phone camera rim') or bpy.data.materials.new('Phone camera rim')
chrome_mat.diffuse_color=(.22,.27,.31,1);chrome_mat.use_nodes=True
chrome_mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.22,.27,.31,1)
chrome_mat.node_tree.nodes.get('Principled BSDF').inputs['Metallic'].default_value=.7
phone_center=(.45,-.205,.955)
def phone_box(name,half,offset,mat,bevel=0):
    x,y,z=half;verts=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    me=bpy.data.meshes.new(name+'Mesh');me.from_pydata(verts,[],faces);me.update()
    ob=bpy.data.objects.new(name,me);sc.collection.objects.link(ob);ob.data.materials.append(mat)
    if name=='Youth_Filming_Phone':ob.parent=yrig;ob.location=phone_center
    else:ob.parent=phone;ob.location=offset
    if bevel:
        mod=ob.modifiers.new('Soft phone corners','BEVEL');mod.width=bevel;mod.segments=4
        mod=ob.modifiers.new('Clean corner normals','WEIGHTED_NORMAL')
    return ob
phone=phone_box('Youth_Filming_Phone',(.038,.007,.074),(0,0,0),phone_mat,.006)
bpy.context.view_layer.update()
phone_world=phone.matrix_world.copy();phone.parent_type='BONE';phone.parent_bone='wrist.L';phone.matrix_parent_inverse=Matrix.Identity(4);phone.matrix_world=phone_world
bpy.context.view_layer.update()
# Dark inset screen faces the youth; the camera-facing rear has a triple-lens module.
phone_box('Youth_Phone_Screen',(.033,.0012,.064),(0,.0076,0),glass_mat,.004)
phone_box('Youth_Phone_Camera_Island',(.014,.002,.019),(-.021,-.008,.047),chrome_mat,.004)
for i,(ox,oz) in enumerate([(-.027,.055),(-.015,.055),(-.027,.039)]):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=1,location=(0,0,0))
    lens=bpy.context.object;lens.name='Youth_Phone_Lens_%02d'%i;lens.parent=phone;lens.location=(ox,-.0105,oz);lens.scale=(.0045,.0018,.0045);lens.data.materials.append(lens_mat)
# Small side controls and a front-facing sensor make the prop read as a real handset.
phone_box('Youth_Phone_Volume_Button',(.0015,.002,.009),(.0395,-.0005,.026),chrome_mat,.0015)
phone_box('Youth_Phone_Power_Button',(.0015,.002,.006),(.0395,-.0005,.004),chrome_mat,.0015)
phone_box('Youth_Phone_Front_Sensor',(.002,.0008,.0015),(0,.009,.061),lens_mat,.001)
# Move mother and child into a believable paired composition for the final scene.
bpy.data.objects['Mother_RIG'].location.x=1.95
bpy.data.objects['Child_RIG'].location.x=2.68
# Natural idle pose: relax the default A-pose, then add restrained, story-timed gestures.
FRAMES=sc.frame_end=1440
sc.frame_start=1
for name in ('Politician','Journalist','Citizen','Youth','Mother','Child'):
    rig=bpy.data.objects[name+'_RIG']
    for side,sgn in (('L',-1),('R',1)):
        p=rig.pose.bones.get('upperarm02.'+side)
        if p:p.rotation_mode='XYZ';p.rotation_euler[2]=sgn*.48;p.keyframe_insert(data_path='rotation_euler',index=2,frame=1);p.keyframe_insert(data_path='rotation_euler',index=2,frame=FRAMES)
        f=rig.pose.bones.get('lowerarm02.'+side)
        if f:f.rotation_mode='XYZ';f.rotation_euler[2]=-sgn*.08;f.keyframe_insert(data_path='rotation_euler',index=2,frame=1);f.keyframe_insert(data_path='rotation_euler',index=2,frame=FRAMES)
    head=rig.pose.bones.get('head')
    if head:head.rotation_mode='XYZ';head.rotation_euler=(0,0,0);head.keyframe_insert(data_path='rotation_euler',frame=1);head.keyframe_insert(data_path='rotation_euler',frame=FRAMES)
def rotkey(character,bone,frame,value,axis=2):
    p=bpy.data.objects[character+'_RIG'].pose.bones.get(bone)
    if p:p.rotation_mode='XYZ';p.rotation_euler[axis]=value;p.keyframe_insert(data_path='rotation_euler',index=axis,frame=frame)
# Youth keeps the phone seated in the lifted left hand throughout the recording.
for fr in (1,109,529,643,865,1084,1195,1440):
    rotkey('Youth','upperarm02.L',fr,.30)
# Leader's measured pauses and open-hand campaign gestures.
for fr,val in [(1,.48),(109,.48),(132,.20),(158,.42),(190,.22),(220,.44),(240,.48),(275,.48),(320,.20),(350,.42),(390,.22),(430,.44),(510,.48),(724,.48),(770,.20),(800,.42),(840,.48),(865,.48),(905,.18),(935,.38),(960,.48),(1000,.20),(1050,.42),(1083,.48),(1440,.48)]:rotkey('Politician','upperarm02.R',fr,val)
for fr,val in [(1,-.08),(130,-.12),(158,-.35),(190,-.1),(220,-.3),(240,-.08),(320,-.15),(350,-.38),(390,-.1),(430,-.30),(905,-.30),(935,-.08)]:rotkey('Politician','lowerarm02.R',fr,val)
for fr,val in [(1,0),(109,0),(140,.045),(190,-.035),(240,0),(320,.04),(390,-.03),(510,0),(750,.04),(820,-.025),(960,0)]:rotkey('Politician','head',fr,val,1)
# Citizen points at the leak; the reporter leans in and gestures with one hand.
for fr,val in [(1,.48),(529,.48),(555,.08),(610,.16),(642,.48)]:rotkey('Citizen','upperarm02.R',fr,val)
for fr,val in [(1,.48),(643,.48),(666,.12),(690,.26),(718,.48)]:rotkey('Journalist','upperarm02.R',fr,val)
for fr,val in [(1,0),(643,0),(680,-.05),(718,0)]:rotkey('Journalist','head',fr,val,1)
# Child looks toward mother and raises a small inquisitive hand at the final exchange.
for fr,val in [(1,.48),(1195,.48),(1235,.13),(1300,.21),(1363,.48),(1440,.48)]:rotkey('Child','upperarm02.L',fr,val)
for fr,val in [(1,0),(1195,0),(1235,-.28),(1363,-.28),(1440,-.28)]:rotkey('Child','head',fr,val,1)
for fr,val in [(1,0),(1195,0),(1235,.25),(1363,.25),(1440,.15)]:rotkey('Mother','head',fr,val,1)
for fr,val in [(1,.48),(1195,.48),(1235,.15),(1300,.20),(1363,.48),(1440,.48)]:rotkey('Mother','upperarm02.R',fr,val)
# Stage events: a leak grows from a broken pipe and the banner slumps after the mic is raised.
jet=bpy.data.objects.get('Leaking_Water_Jet');puddle=bpy.data.objects.get('Water_Puddle')
if jet:
    base=jet.scale.copy()
    for fr,val in [(1,.001),(548,.001),(549,1),(560,.9),(1440,.9)]:jet.scale=base*val;jet.keyframe_insert(data_path='scale',frame=fr)
if puddle:
    base=puddle.scale.copy()
    for fr,val in [(1,.001),(548,.001),(549,.12),(640,.65),(800,1),(1440,1)]:puddle.scale=base*val;puddle.keyframe_insert(data_path='scale',frame=fr)
# Camera stand-in for the leader turning up the microphone gain.
knobmat=bpy.data.materials.get('Mic_Gain_Brass') or bpy.data.materials.new('Mic_Gain_Brass');knobmat.diffuse_color=(.55,.34,.11,1);knobmat.use_nodes=True;knobmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.55,.34,.11,1)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.035,location=(-2.57,-.37,1.03));knob=bpy.context.object;knob.name='Microphone_Gain_Knob';knob.scale=(1,.65,.65);knob.data.materials.append(knobmat)
for fr,size in [(1,.001),(959,.001),(960,1),(1100,1),(1440,1)]:knob.scale=(size,.65*size,.65*size);knob.keyframe_insert(data_path='scale',frame=fr)
# Parent the Bengali printed banner to its fabric backplate, then animate the unsupported sag.
banner=bpy.data.objects.get('Banner_Backdrop');printtex=bpy.data.objects.get('Banner_Bengali_Raster')
if banner and printtex:
    mw=printtex.matrix_world.copy();printtex.parent=banner;printtex.matrix_parent_inverse=banner.matrix_world.inverted();printtex.matrix_world=mw
    for fr,dz,rx in [(1,0,0),(1082,0,0),(1085,-.08,.06),(1100,-.42,.22),(1120,-.55,.28),(1440,-.55,.28)]:
        banner.location.z=2.4+dz;banner.rotation_euler.x=rx;banner.keyframe_insert(data_path='location',frame=fr);banner.keyframe_insert(data_path='rotation_euler',frame=fr)
# Save a compact, resumable EEVEE render setup; this script never invokes render.
sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=1280;sc.render.resolution_y=720;sc.render.resolution_percentage=75;sc.render.fps=24;sc.render.fps_base=1
sc.eevee.taa_render_samples=16;sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA';sc.render.filepath='//renders/mithyar_mic_';sc.render.use_file_extension=True
sc.view_settings.view_transform='AgX'
try:sc.view_settings.look='AgX - Medium High Contrast'
except Exception:pass
sc.frame_set(1)
# Keep the GUI showing the cast and stage, never leave the Python console in front.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.region_3d.view_perspective='CAMERA';s.region_3d.view_camera_zoom=8;s.shading.color_type='MATERIAL'
# Native Blender 4.5 production pass: save a new project; never overwrite the source.
import shutil, json
DEST='/sdcard/Blender/bangla-short-films/mithyar-mic-native45-production-2026-10-28'
os.makedirs(os.path.join(DEST,'renders'),exist_ok=True)
os.makedirs(os.path.join(DEST,'scripts'),exist_ok=True)
sc.render.resolution_x=1280;sc.render.resolution_y=720;sc.render.resolution_percentage=100
sc.eevee.taa_render_samples=16
sc.render.filepath='//renders/mithyar_mic_'
sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA'
sc.render.fps=24;sc.render.fps_base=1;sc.frame_start=1;sc.frame_end=1440
sc['production_title']='Mithyar Mic — Native Blender 4.5 60-second visual animation'
sc['story_source']='Mithyar Mic STORY.md (Bangla political satire; 60s)'
sc['authoring_runtime']='Native Termux Blender 4.5.14 LTS, Termux:X11 :1'
sc['viewport_gpu_backend']='KGSL/Freedreno, Adreno 825'
sc['render_backend']='EEVEE Next; Native Adreno GPU required; no software fallback'
sc['duration_seconds']=60.0
sc['dialogue_audio_status']='Not included in this visual animation pass; exact dialogue remains in STORY.md'
bpy.ops.file.pack_all()
bpy.context.scene.frame_set(1)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.region_3d.view_perspective='CAMERA';s.region_3d.view_camera_zoom=8
            s.shading.type='SOLID';s.shading.color_type='MATERIAL';s.overlay.show_overlays=False
project_path=os.path.join(DEST,'mithyar_mic_native45_60s.blend')
bpy.ops.wm.save_as_mainfile(filepath=project_path,check_existing=False)
shutil.copy2('/sdcard/Blender/bangla-short-films/mithyar-mic-2026-10-14/STORY.md',os.path.join(DEST,'STORY.md'))
shutil.copy2('/data/data/com.termux/files/home/ternuxx/docs/evidence/2026-10-28-mithyar-mic-native45/production.py',os.path.join(DEST,'scripts','production.py'))
with open(os.path.join(DEST,'manifest.json'),'w',encoding='utf-8') as f:
    json.dump({'title':'Mithyar Mic — 60-second visual animation','source_project':'/sdcard/Blender/bangla-short-films/mithyar-mic-2026-10-14/mithyar_mic.blend','source_story':'STORY.md','blender':bpy.app.version_string,'duration_seconds':60,'fps':24,'frames':1440,'resolution':[1280,720],'engine':sc.render.engine,'samples':sc.eevee.taa_render_samples,'viewport_backend':'KGSL/Freedreno Adreno 825','render_backend':'Native accelerated EEVEE; software fallback not selected','dialogue_audio':'not included'},f,ensure_ascii=False,indent=2)
print('Built 60s timeline and saved NEW project; original source untouched:',project_path,'objects=',len(bpy.data.objects),'markers=',len(sc.timeline_markers))
