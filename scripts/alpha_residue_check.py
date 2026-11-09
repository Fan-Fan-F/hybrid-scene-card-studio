#!/usr/bin/env python3
"""alpha_residue_check.py — 人物抠图「远距低 alpha 暗色残渣」检测。

用途
----
动态卡 v2 版本人物周围出现灰蒙蒙一圈，真源是抠图残留：大量低 alpha 的
暗色像素散落在离人物实体较远的位置。本脚本量化这类残渣：
  残渣像素 = alpha 在 (0, alpha_hi] 之间
             且亮度 < lum_hi（暗）
             且到「实体」(alpha >= solid) 的距离 > dist px
输出残渣像素数与占全图比，超过阈值时退出码非 0，用作合成前门禁。

参数
----
image            带 alpha 的人物 PNG 路径
--dist           距离阈值 px（默认 3.5）
--alpha-hi       低 alpha 上限（默认 128）
--solid          实体 alpha 下限（默认 200）
--lum-hi         暗像素亮度上限 0-255（默认 100）
--max-count      允许残渣像素上限，超过则退出码 1（默认 0，即零容忍）

退出码：0 = 残渣数 <= max-count；1 = 超标；2 = 输入错误。
指标以 JSON 打印到 stdout。
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--dist", type=float, default=3.5)
    ap.add_argument("--alpha-hi", type=int, default=128)
    ap.add_argument("--solid", type=int, default=200)
    ap.add_argument("--lum-hi", type=float, default=100.0)
    ap.add_argument("--max-count", type=int, default=0)
    args = ap.parse_args()

    try:
        im = Image.open(args.image).convert("RGBA")
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"cannot open image: {e}"}))
        return 2

    arr = np.asarray(im).astype(np.float32)
    rgb, alpha = arr[..., :3], arr[..., 3]
    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]

    solid = alpha >= args.solid
    if not solid.any():
        print(json.dumps({"error": "no solid pixels (alpha >= solid) found"}))
        return 2
    # distance from every pixel to nearest solid pixel
    dist = distance_transform_edt(~solid)

    low_alpha = (alpha > 0) & (alpha <= args.alpha_hi)
    dark = lum < args.lum_hi
    far = dist > args.dist
    residue = low_alpha & dark & far

    # head-region not special-cased: whole-image metric is the gate
    count = int(residue.sum())
    total = int(alpha.size)
    result = {
        "image": args.image,
        "size": [int(im.width), int(im.height)],
        "thresholds": {
            "dist_px": args.dist,
            "alpha_hi": args.alpha_hi,
            "solid": args.solid,
            "lum_hi": args.lum_hi,
        },
        "low_alpha_pixels": int(low_alpha.sum()),
        "low_alpha_dark_pixels": int((low_alpha & dark).sum()),
        "residue_pixels": count,
        "residue_ratio_of_image": count / total,
        "residue_ratio_of_low_alpha": (
            count / int(low_alpha.sum()) if low_alpha.any() else 0.0
        ),
        "max_dist_of_residue_px": float(dist[residue].max()) if count else 0.0,
        "pass": count <= args.max_count,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
