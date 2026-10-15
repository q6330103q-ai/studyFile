"""
게임 규격 정리 스크립트 (Blender 4.x / 5.x)
- 실제 크기로 스케일
- 원점을 바닥 중앙(발밑)으로
- 정면 방향 -Y (Blender 정면 = Unity +Z 정면)
- Apply Transform (위치/회전/스케일 0,0,0 / 1,1,1)
- Unity용 FBX 출력 (텍스처는 Textures 폴더로 분리)

사용법 (블렌더 Scripting 탭에서 실행하거나 명령줄):
  blender -b -P game_spec_cleanup.py -- <입력 폴더> <출력 폴더>
"""
import bpy, sys, os, math, mathutils

# 리소스별 규격: (원본 파일명 앞부분, 새 이름, 기준 축, 목표 길이 m, 정면 보정 회전(도))
SPECS = [
    ("Blue Chef Robot",           "Char_ChefBot",       "height", 1.60, 0),  # 캐릭터 키 1.6m
    ("Classic Cheeseburger",      "Prop_Burger",        "width",  0.12, 0),  # 실제 버거 지름 12cm
    ("Commercial Kitchen Island", "Env_KitchenIsland",  "width",  1.80, 0),  # 조리대 가로 1.8m
]

def world_bbox(objs):
    pts = [o.matrix_world @ mathutils.Vector(c) for o in objs for c in o.bound_box]
    mn = mathutils.Vector([min(p[i] for p in pts) for i in range(3)])
    mx = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
    return mn, mx

def process(src, dst_dir, new_name, axis, target, yaw_deg):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    log = {}

    mn, mx = world_bbox(meshes); size = mx - mn
    log["before_size"] = tuple(round(v, 3) for v in size)

    # 1) 방향 보정 (필요 시 Z축 회전)
    for o in meshes:
        o.rotation_euler.z += math.radians(yaw_deg)
    bpy.context.view_layer.update()

    # 2) 실제 크기로 스케일
    mn, mx = world_bbox(meshes); size = mx - mn
    cur = size.z if axis == "height" else size.x
    s = target / cur
    for o in meshes:
        o.scale *= s
    bpy.context.view_layer.update()

    # 3) Apply Transform (회전/스케일 적용)
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes: o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # 4) 원점 = 바닥 중앙 : 메시를 옮겨서 바닥 중앙이 (0,0,0)에 오게
    mn, mx = world_bbox(meshes)
    offset = mathutils.Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    for o in meshes:
        o.data.transform(mathutils.Matrix.Translation(-offset))
        o.location = (0, 0, 0)
        o.name = new_name
        o.data.name = new_name + "_Mesh"
    for m in bpy.data.materials:
        m.name = new_name + "_Mat"
    tex_dir = os.path.join(dst_dir, "Textures"); os.makedirs(tex_dir, exist_ok=True)
    for img in list(bpy.data.images):
        if not (img.packed_file or img.filepath): continue
        is_normal = "normal" in img.name.lower()
        img.name = f"{new_name}_{img.name}"
        ext, fmt = (".png", 'PNG') if is_normal else (".jpg", 'JPEG')   # 컬러맵은 JPG로 용량 절감
        path = os.path.join(tex_dir, img.name + ext)
        sc = bpy.context.scene.render.image_settings
        sc.file_format = fmt; sc.quality = 92
        img.save_render(path)
        if img.packed_file: img.unpack(method='REMOVE')
        img.filepath = path; img.source = 'FILE'; img.reload()
        img['rel'] = '//Textures/' + os.path.basename(path)
    bpy.context.view_layer.update()

    mn, mx = world_bbox(meshes)
    log["after_size"] = tuple(round(v, 3) for v in (mx - mn))
    log["after_min"] = tuple(round(v, 3) for v in mn)

    # 5) Unity용 FBX 출력
    out = os.path.join(dst_dir, new_name + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=out, use_selection=False, object_types={'MESH', 'ARMATURE'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
        axis_forward='-Z', axis_up='Y', bake_space_transform=True,
        path_mode='RELATIVE', embed_textures=False, add_leaf_bones=False,
    )
    for img in bpy.data.images:
        if 'rel' in img: img.filepath = img['rel']   # .blend에는 상대경로로 저장
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(dst_dir, new_name + ".blend"), relative_remap=True)
    return out, log

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[-2:]
    src_dir, dst_dir = argv
    os.makedirs(dst_dir, exist_ok=True)
    for prefix, name, axis, target, yaw in SPECS:
        src = next(os.path.join(src_dir, f) for f in os.listdir(src_dir)
                   if f.startswith(prefix) and f.endswith(".fbx"))
        out, log = process(src, dst_dir, name, axis, target, yaw)
        print(f"[DONE] {name}: size {log['before_size']} -> {log['after_size']} m, bbox min {log['after_min']} -> {out}")
