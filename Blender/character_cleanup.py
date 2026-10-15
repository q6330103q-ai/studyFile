"""
캐릭터 정리 스크립트 (Blender 5.x)
Idle / Walk FBX 2개를 하나의 캐릭터로 합치고 게임용으로 정리
 1) Idle FBX를 기본으로 불러오고 Walk 애니메이션만 가져오기
 2) 동작 이름 Idle / Walk로 정리 + 루프 구간 잘라내기(첫·끝 포즈가 이어지는 구간)
 3) 키 1.6m로 스케일 (뼈 위치 키프레임도 같은 비율로 보정) → Apply Transform
 4) Decimate (Armature보다 먼저 적용) → 삼각형 약 3만
 5) Unity용 FBX 출력 (Idle, Walk 두 클립 포함)
사용법: blender -b -P character_cleanup.py -- <Assets 폴더> <출력 폴더>
"""
import bpy, sys, os, mathutils

TARGET_HEIGHT = 1.60
DECIMATE_RATIO = 0.06
# (파일, 동작 이름, 루프 시작, 루프 끝)  ← 루프 구간은 포즈 비교로 찾은 값
CLIPS = [
    ("Blue Chef Robot-idle.fbx", "Idle", 3, 97),   # 첫/끝 포즈 차이 1.2°
    ("Blue Chef Robot-walk.fbx", "Walk", 26, 60),  # 첫/끝 포즈 차이 9.6° (원본 3~85는 75° 튐)
]
NAME = "Char_ChefBot"

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv
os.makedirs(os.path.join(dst, "Textures"), exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

def import_fbx(path):
    before = set(bpy.data.objects); before_a = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    act = [a for a in bpy.data.actions if a not in before_a][0]
    return new, act

# 1) 기본 캐릭터 + 각 동작 가져오기
objs, first_act = import_fbx(os.path.join(src, CLIPS[0][0]))
arm = next(o for o in objs if o.type == 'ARMATURE')
mesh = next(o for o in objs if o.type == 'MESH')
actions = {CLIPS[0][1]: first_act}
for f, clip, s, e in CLIPS[1:]:
    tmp, act = import_fbx(os.path.join(src, f))
    actions[clip] = act
    for o in tmp:                      # 메시·뼈대는 지우고 애니메이션만 남김
        bpy.data.objects.remove(o, do_unlink=True)

# 2) 동작 이름 정리 + 루프 구간을 0프레임부터 시작하도록 이동, 구간 밖 키 삭제
def fcurves_of(act):
    try:
        return list(act.fcurves)
    except AttributeError:            # Blender 5 레이어드 액션
        return [fc for l in act.layers for st in l.strips for cb in st.channelbags for fc in cb.fcurves]

for f, clip, s, e in CLIPS:
    act = actions[clip]
    act.name = clip
    act.use_fake_user = True
    for fc in fcurves_of(act):
        for i in reversed(range(len(fc.keyframe_points))):
            x = fc.keyframe_points[i].co.x
            if x < s - 0.01 or x > e + 0.01:
                fc.keyframe_points.remove(fc.keyframe_points[i], fast=True)
        for k in fc.keyframe_points:
            k.co.x -= s; k.handle_left.x -= s; k.handle_right.x -= s
        fc.update()
    act.frame_range = (0, e - s)
    act.use_frame_range = True
    act.use_cyclic = True

# 3) 키 1.6m 스케일 (T-포즈 기준 높이)
arm.animation_data.action = None
bpy.context.view_layer.update()
pts = [mesh.matrix_world @ mathutils.Vector(c) for c in mesh.bound_box]
height = max(p.z for p in pts) - min(p.z for p in pts)
k = TARGET_HEIGHT / height
arm.scale *= k
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True); mesh.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for act in actions.values():          # 뼈 이동 키프레임도 같은 비율로
    for fc in fcurves_of(act):
        if fc.data_path.endswith("location"):
            for kp in fc.keyframe_points:
                kp.co.y *= k; kp.handle_left.y *= k; kp.handle_right.y *= k
            fc.update()

# 4-0) UV 이음매로 갈라진 정점 병합 → Decimate 후 이음매가 벌어져 생기던 검은 점 방지
#      + 떨어진 작은 조각 제거 / 뒤집힌 면 수정
import bmesh
before_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
bm = bmesh.new(); bm.from_mesh(mesh.data)
cos = [v.co for v in bm.verts]
D = (mathutils.Vector([max(c[i] for c in cos) for i in range(3)]) - mathutils.Vector([min(c[i] for c in cos) for i in range(3)])).length
v0 = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=D * 1e-5)
merged = v0 - len(bm.verts)
bm.faces.ensure_lookup_table(); seen = set(); junk = []
for f0 in bm.faces:
    if f0.index in seen: continue
    stack = [f0]; seen.add(f0.index); fs = []
    while stack:
        f = stack.pop(); fs.append(f)
        for e in f.edges:
            for g in e.link_faces:
                if g.index not in seen: seen.add(g.index); stack.append(g)
    c = [v.co for f in fs for v in f.verts]
    if (mathutils.Vector([max(x[i] for x in c) for i in range(3)]) - mathutils.Vector([min(x[i] for x in c) for i in range(3)])).length < D * 0.05:
        junk += fs
bmesh.ops.delete(bm, geom=list({v for f in junk for v in f.verts}), context='VERTS')
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(mesh.data); bm.free()
print(f"[WELD] merged verts {merged:,}, removed loose faces {len(junk)}")

# 4) Decimate - Armature 모디파이어보다 위에서 적용
bpy.context.view_layer.objects.active = mesh
dec = mesh.modifiers.new("Decimate", 'DECIMATE')
dec.decimate_type = 'COLLAPSE'; dec.ratio = DECIMATE_RATIO
bpy.ops.object.modifier_move_to_index(modifier=dec.name, index=0)
bpy.ops.object.modifier_apply(modifier=dec.name)
after_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)

# 이름 정리
arm.name = NAME + "_Rig"; mesh.name = NAME; mesh.data.name = NAME + "_Mesh"
for m in mesh.data.materials: m.name = NAME + "_Mat"

# 텍스처 분리 저장 (Walk 파일에서 딸려온 중복 이미지는 먼저 삭제)
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
for img in list(bpy.data.images):
    if not (img.packed_file or img.filepath): continue
    is_n = "normal" in img.name.lower()
    img.name = f"{NAME}_{img.name.split('.')[0]}"
    ext, fmt = (".png", 'PNG') if is_n else (".jpg", 'JPEG')
    path = os.path.join(dst, "Textures", img.name + ext)
    st = bpy.context.scene.render.image_settings; st.file_format = fmt; st.quality = 92
    img.save_render(path)
    if img.packed_file: img.unpack(method='REMOVE')
    img.filepath = path; img.source = 'FILE'; img.reload()
for im in [i for i in bpy.data.images if i.users == 0]:
    bpy.data.images.remove(im)

# 5) NLA 트랙에 동작을 올려 클립 이름 = Idle / Walk 로 출력
ad = arm.animation_data or arm.animation_data_create()
ad.action = None
for clip, act in actions.items():
    tr = ad.nla_tracks.new(); tr.name = clip
    strip = tr.strips.new(clip, 0, act); strip.name = clip
bpy.context.scene.frame_start = 0
bpy.context.scene.frame_end = max(e - s for _, _, s, e in CLIPS)
bpy.context.scene.render.fps = 30

out = os.path.join(dst, NAME + ".fbx")
bpy.ops.export_scene.fbx(
    filepath=out, object_types={'ARMATURE', 'MESH'},
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z', axis_up='Y', add_leaf_bones=False,
    bake_anim=True, bake_anim_use_nla_strips=True, bake_anim_use_all_actions=False,
    bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
    path_mode='RELATIVE', embed_textures=False,
)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(dst, NAME + ".blend"))
print(f"[DONE] height {height:.3f} -> {TARGET_HEIGHT} m (x{k:.3f}), tris {before_tris:,} -> {after_tris:,}, clips {list(actions)} -> {out}")
