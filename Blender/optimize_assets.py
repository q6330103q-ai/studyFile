"""
최적화 스크립트 (Blender 5.x) - 규격 정리된 소품/배경 FBX 대상
 1) UV 이음매로 갈라진 정점 병합(Merge by Distance) → 진짜 '떨어진 조각'만 남게 함
 2) 불필요한 조각 제거 : 본체에서 떨어져 떠 있는 작은 조각(오브젝트 대각선의 5% 미만)
 3) 뒤집힌 면 검사 / 수정 (Recalculate Outside)
 4) Decimate (Collapse) 로 목표 삼각형 수까지 감소
 5) Unity용 FBX 재출력 (규격 정리 때와 동일 설정)
사용법: blender -b -P optimize_assets.py -- <입력 폴더(규격정리 FBX)> <출력 폴더>
"""
import bpy, bmesh, sys, os, mathutils

TARGETS = {                     # 이름: 목표 삼각형 수
    "Prop_Burger": 6000,        # 12cm 소품 → 6천이면 충분
    "Env_KitchenIsland": 30000, # 소품이 많이 올라간 배경 → 3만
}
LOOSE_RATIO = 0.05              # 대각선 5% 미만의 떨어진 조각 = 불필요 조각

def tris(me): return sum(len(p.vertices) - 2 for p in me.polygons)

def loose_islands(bm):
    bm.faces.ensure_lookup_table(); seen = set(); out = []
    for f0 in bm.faces:
        if f0.index in seen: continue
        stack = [f0]; seen.add(f0.index); fs = []
        while stack:
            f = stack.pop(); fs.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen: seen.add(g.index); stack.append(g)
        out.append(fs)
    return out

def diag(cos):
    mn = mathutils.Vector([min(c[i] for c in cos) for i in range(3)])
    mx = mathutils.Vector([max(c[i] for c in cos) for i in range(3)])
    return (mx - mn).length

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv
os.makedirs(dst, exist_ok=True)
for name, target in TARGETS.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(src, name + ".fbx"))
    obj = next(o for o in bpy.data.objects if o.type == 'MESH')
    log = {"tris_before": tris(obj.data)}

    bm = bmesh.new(); bm.from_mesh(obj.data)
    D = diag([v.co for v in bm.verts])
    log["islands_raw"] = len(loose_islands(bm))
    v0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=D * 1e-5)          # 1) 병합
    log["merged_verts"] = v0 - len(bm.verts)

    isl = loose_islands(bm)                                              # 2) 조각 제거
    log["islands_welded"] = len(isl)
    junk = [fs for fs in isl if diag([v.co for f in fs for v in f.verts]) < D * LOOSE_RATIO]
    junk_faces = {f for fs in junk for f in fs}
    junk_verts = {v for f in junk_faces for v in f.verts}
    bmesh.ops.delete(bm, geom=list(junk_verts), context='VERTS')
    log["removed_pieces"] = len(junk); log["removed_faces"] = len(junk_faces)

    before_n = {f.index: f.normal.copy() for f in bm.faces}              # 3) 뒤집힌 면
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    log["flipped_fixed"] = sum(1 for f in bm.faces if f.normal.dot(before_n[f.index]) < 0)
    bm.to_mesh(obj.data); bm.free()

    dec = obj.modifiers.new("Decimate", 'DECIMATE')                      # 4) Decimate
    dec.decimate_type = 'COLLAPSE'; dec.ratio = min(1.0, target / tris(obj.data))
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=dec.name)
    log["tris_after"] = tris(obj.data)

    out = os.path.join(dst, name + ".fbx")                                # 5) 출력
    bpy.ops.export_scene.fbx(
        filepath=out, object_types={'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
        axis_forward='-Z', axis_up='Y', bake_space_transform=True,
        path_mode='RELATIVE', embed_textures=False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(dst, name + ".blend"))
    print(f"[DONE] {name}: {log}")
