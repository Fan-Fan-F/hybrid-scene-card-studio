#!/usr/bin/env python3
"""contour_divergence.py — 火焰轮廓 vs 人物轮廓独立性度量。

用途
----
动态卡 v4 版本火焰被批「轮廓跟人物一模一样，像剪影描边」。本脚本量化
火焰与人物的轮廓重合程度：
  - 火焰轮廓点 = 火焰 alpha >= thr 的区域边界像素
  - 人物轮廓    = 人物 alpha >= thr 的区域边界像素
  - 重合 = 火焰轮廓点到最近人物轮廓点的距离 <= band px
重合率越低，火焰越独立于人物剪影。配合 --max-overlap 可作门禁。

参数
----
flame            火焰 alpha 帧 PNG（RGBA，尺寸须与人物一致）
subject          人物 PNG（RGBA）
--alpha-thr      实体 alpha 阈值（默认 32）
--band           轮廓膨胀带宽 px（默认 4）
--max-overlap    允许的最大重合率 0-1，超过则退出码 1（默认不设=只报告）

退出码：0 = 达标（或未设阈值仅报告）；1 = 超限；2 = 输入错误。
指标以 JSON 打印到 stdout。
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion, distance_transform_edt


def contour_points(alpha: np.ndarray, thr: int) -> np.ndarray:
    """Boolean mask of boundary pixels of the solid region."""
    solid = alpha >= thr
    if not solid.any():
        return np.zeros_like(solid)
    eroded = binary_erosion(solid)
    return solid & ~eroded


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("flame")
    ap.add_argument("subject")
    ap.add_argument("--alpha-thr", type=int, default=32)
    ap.add_argument("--band", type=float, default=4.0)
    ap.add_argument("--max-overlap", type=float, default=None)
    args = ap.parse_args()

    try:
        f = Image.open(args.flame).convert("RGBA")
        s = Image.open(args.subject).convert("RGBA")
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"cannot open image: {e}"}))
        return 2
    if f.size != s.size:
        print(json.dumps({"error": f"size mismatch: flame {f.size} vs subject {s.size}"}))
        return 2

    f_alpha = np.asarray(f)[..., 3]
    s_alpha = np.asarray(s)[..., 3]

    f_contour = contour_points(f_alpha, args.alpha_thr)
    s_contour = contour_points(s_alpha, args.alpha_thr)
    n_f = int(f_contour.sum())
    if n_f == 0:
        print(json.dumps({"error": "flame has no contour points"}))
        return 2
    if not s_contour.any():
        print(json.dumps({"error": "subject has no contour points"}))
        return 2

    # distance from every pixel to nearest subject-contour pixel
    dist_to_subject_contour = distance_transform_edt(~s_contour)
    d = dist_to_subject_contour[f_contour]
    overlap = float((d <= args.band).mean())

    result = {
        "flame": args.flame,
        "subject": args.subject,
        "size": [f.width, f.height],
        "alpha_thr": args.alpha_thr,
        "band_px": args.band,
        "flame_contour_points": n_f,
        "subject_contour_points": int(s_contour.sum()),
        "overlap_ratio": overlap,
        "mean_dist_to_subject_contour_px": float(d.mean()),
        "median_dist_to_subject_contour_px": float(np.median(d)),
    }
    ok = True
    if args.max_overlap is not None:
        ok = overlap <= args.max_overlap
    result["pass"] = ok
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
