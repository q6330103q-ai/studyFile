"""
스타일 통일 스크립트 - 3종 베이스컬러 텍스처의 톤 맞추기
기준: 캐릭터(셰프 로봇)의 부드러운 '토이' 톤
 1) 사실적인 잔질감 줄이기 (버거·조리대만 Median 필터)
 2) 채도 평균을 목표값으로 (버거는 낮추고, 조리대는 올림)
 3) 밝기 평균 / 대비를 목표값으로
 4) 3종 공통 컬러 그레이드 (살짝 따뜻한 톤)
사용법: python unify_style.py <입력 텍스처 폴더> <출력 폴더>
"""
import sys, os
import numpy as np
from PIL import Image, ImageFilter

TARGET = dict(sat=0.55, lum=0.54, std=0.17)      # 3종 공통 목표 (sat = 채도 상위10% 값: 가장 진한 색의 세기)
S_RANGE = (0.4, 1.3)                              # 회색 금속·흰 앞치마가 과하게 물들지 않게 채도 배율 제한
COMMON_TINT = np.array([1.025, 1.0, 0.965])       # 공통 웜톤 그레이드
SMOOTH = {"Prop_Burger": 5, "Env_KitchenIsland": 3, "Char_ChefBot": 0}

def stats(a):
    m = a.max(2) > 0.03
    mx, mn = a.max(2), a.min(2)
    sat = np.percentile(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)[m], 90)
    L = (a @ np.array([0.299, 0.587, 0.114]))[m]
    return sat, L.mean(), L.std()

def grade(a, s, c, mu_src, mu_dst):
    L = (a @ np.array([0.299, 0.587, 0.114]))[..., None]
    a = L + (a - L) * s                              # 채도
    a = (a - mu_src) * c + mu_dst                    # 대비 + 밝기
    return np.clip(a * COMMON_TINT, 0, 1)

def fit(small):
    s, c = 1.0, 1.0
    for _ in range(12):                              # 작은 이미지로 목표값 맞추기
        sat, mu, sd = stats(grade(small, s, c, stats(small)[1], TARGET["lum"]))
        s = float(np.clip(s * (TARGET["sat"] / max(sat, 1e-3)) ** 0.8, *S_RANGE))
        c *= (TARGET["std"] / max(sd, 1e-3)) ** 0.8
    return s, c

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
for name in ["Char_ChefBot", "Prop_Burger", "Env_KitchenIsland"]:
    img = Image.open(os.path.join(src, f"{name}_base_color.jpg")).convert("RGB")
    if SMOOTH[name]:
        img = img.filter(ImageFilter.MedianFilter(SMOOTH[name]))
    small = np.asarray(img.resize((512, 512))) / 255.0
    before = stats(np.asarray(Image.open(os.path.join(src, f"{name}_base_color.jpg")).convert("RGB").resize((512, 512))) / 255.0)
    s, c = fit(small)
    a = np.asarray(img).astype(np.float32) / 255.0
    out = grade(a, s, c, stats(small)[1], TARGET["lum"])
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(os.path.join(dst, f"{name}_base_color.jpg"), quality=92)
    after = stats(np.asarray(Image.fromarray((out * 255).astype(np.uint8)).resize((512, 512))) / 255.0)
    print(f"[STYLE] {name}: sat {before[0]:.2f}->{after[0]:.2f}, lum {before[1]:.2f}->{after[1]:.2f}, "
          f"contrast {before[2]:.2f}->{after[2]:.2f} (saturation x{s:.2f}, contrast x{c:.2f}, median {SMOOTH[name]})")
