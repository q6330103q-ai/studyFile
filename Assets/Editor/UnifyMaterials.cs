// 3종 리소스 스타일 통일 + 정리 전/후 비교 씬 도구
// 위치: Assets/Editor/UnifyMaterials.cs
// 메뉴: Tools > Chef Kitchen > ...
using System.IO;
using UnityEditor;
using UnityEngine;

public static class UnifyMaterials
{
    const string Root = "Assets/Models/Cleaned";
    static readonly string[] Names = { "Char_ChefBot", "Prop_Burger", "Env_KitchenIsland" };

    // 3종 공통 재질 값 (톤 통일)
    const float Metallic = 0f;      // 크롬 반사 제거 → 토이 스타일
    const float Smoothness = 0.3f;  // 살짝 부드러운 하이라이트
    const float NormalScale = 0.8f; // 실사 요철을 약간 눌러줌

    [MenuItem("Tools/Chef Kitchen/1. Apply Unified Materials")]
    public static void Apply()
    {
        string matDir = Root + "/Materials";
        if (!AssetDatabase.IsValidFolder(matDir)) AssetDatabase.CreateFolder(Root, "Materials");
        var shader = Shader.Find("Universal Render Pipeline/Lit");
        if (shader == null) { Debug.LogError("URP Lit 셰이더를 찾을 수 없습니다."); return; }

        foreach (var n in Names)
        {
            // 노멀맵 텍스처 타입 지정
            string nPath = $"{Root}/Textures/{n}_normal.png";
            if (AssetImporter.GetAtPath(nPath) is TextureImporter ti && ti.textureType != TextureImporterType.NormalMap)
            {
                ti.textureType = TextureImporterType.NormalMap; ti.SaveAndReimport();
            }
            var baseTex = AssetDatabase.LoadAssetAtPath<Texture2D>($"{Root}/Textures/{n}_base_color.jpg");
            var normTex = AssetDatabase.LoadAssetAtPath<Texture2D>(nPath);

            // 공통 값으로 머티리얼 생성/갱신
            string mPath = $"{matDir}/{n}_Mat.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(mPath);
            if (mat == null) { mat = new Material(shader); AssetDatabase.CreateAsset(mat, mPath); }
            mat.shader = shader;
            mat.SetTexture("_BaseMap", baseTex);
            mat.SetColor("_BaseColor", Color.white);
            mat.SetTexture("_BumpMap", normTex);
            mat.SetFloat("_BumpScale", NormalScale);
            mat.EnableKeyword("_NORMALMAP");
            mat.SetFloat("_Metallic", Metallic);
            mat.SetFloat("_Smoothness", Smoothness);
            EditorUtility.SetDirty(mat);

            // FBX 안의 머티리얼을 새 머티리얼로 연결(Remap)
            string fbx = $"{Root}/{n}.fbx";
            if (AssetImporter.GetAtPath(fbx) is ModelImporter mi)
            {
                foreach (var m in AssetDatabase.LoadAllAssetsAtPath(fbx))
                    if (m is Material src)
                        mi.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), src.name), mat);
                mi.SaveAndReimport();
            }
            Debug.Log($"[Unify] {n}: Metallic {Metallic}, Smoothness {Smoothness}, Normal {NormalScale}");
        }
        AssetDatabase.SaveAssets();
    }

    // 정리 전(뒤 줄) / 정리 후(앞 줄) 나란히 배치
    [MenuItem("Tools/Chef Kitchen/2. Build Before-After Layout")]
    public static void BuildCompare()
    {
        var root = new GameObject("Compare_BeforeAfter");
        string[] raw = { "Blue Chef Robot-691b344a3281ad36c6973f417345d4ee", "Commercial Kitchen Island-2403f72255cbc67226c9af943ea32de5", "Classic Cheeseburger-22f1053ea6a2fe7f56184f323971049b" };
        string[] clean = { "Char_ChefBot", "Env_KitchenIsland", "Prop_Burger" };
        float[] xs = { -2.5f, 0f, 2.5f };
        for (int i = 0; i < 3; i++)
        {
            Place($"Assets/{raw[i]}.fbx", "Before_" + clean[i], new Vector3(xs[i], 0, 2f), root.transform);
            Place($"{Root}/{clean[i]}.fbx", "After_" + clean[i], new Vector3(xs[i], 0, -1f), root.transform);
        }
        var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cube.name = "Ref_1m_Cube"; cube.transform.SetParent(root.transform);
        cube.transform.position = new Vector3(4.5f, 0.5f, -1f);
        Selection.activeGameObject = root;
        Debug.Log("[Compare] 뒤 줄 = 정리 전, 앞 줄 = 정리 후, 오른쪽 큐브 = 1m 기준");
    }

    static void Place(string path, string name, Vector3 pos, Transform parent)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
        if (prefab == null) { Debug.LogWarning("없음: " + path); return; }
        var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        go.name = name; go.transform.SetParent(parent); go.transform.position = pos;
    }
}
