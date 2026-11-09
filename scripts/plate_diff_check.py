#!/usr/bin/env python3
"""plate_diff_check.py — 生成底板 vs 基准底板像素差断言。

用途
----
生成式补洞的底板必须保证「洞外零改动」：非编辑区与基准图逐像素一致。
本脚本对比底板与基准（可选用掩膜限定统计区域），输出全图最大像素差、
平均绝对差、差异像素占比。配合 --max-pixel-delta / --max-diff-ratio
阈值可作门禁：超限退出码非 0。

参数
----
plate            待检底板 PNG
baseline         基准 PNG（尺寸须与 plate 一致）
--mask           可选掩膜 PNG（白=纳入统计，黑=排除），尺寸须一致
--pixel-eps      像素差超过此值计为「差异像素」（默认 0，即任何改动都算）
--max-pixel-delta 允许的最大像素差，超过则退出码 1（默认不设=只报告）
--max-diff-ratio   允许的差异像素占比，超过则退出码 1（默认不设=只报告）

退出码：0 = 达标（或未设阈值仅报告）；1 = 超限；2 = 输入错误。
指标以 JSON 打印到 stdout。
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plate")
    ap.add_argument("baseline")
    ap.add_argument("--mask")
    ap.add_argument("--pixel-eps", type=float, default=0.0)
    ap.add_argument("--max-pixel-delta", type=float, default=None)
    ap.add_argument("--max-diff-ratio", type=float, default=None)
    args = ap.parse_args()

    try:
        a = Image.open(args.plate).convert("RGB")
        b = Image.open(args.baseline).convert("RGB")
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"cannot open image: {e}"}))
        return 2
    if a.size != b.size:
        print(json.dumps({"error": f"size mismatch: plate {a.size} vs baseline {b.size}"}))
        return 2

    diff = np.abs(
        np.asarray(a).astype(np.int32) - np.asarray(b).astype(np.int32)
    )
    pix_delta = diff.max(axis=2)  # per-pixel worst-channel delta

    if args.mask:
        try:
            m = Image.open(args.mask).convert("L")
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"error": f"cannot open mask: {e}"}))
            return 2
        if m.size != a.size:
            print(json.dumps({"error": f"mask size mismatch: {m.size} vs {a.size}"}))
            return 2
        sel = np.asarray(m) > 127
    else:
        sel = np.ones(pix_delta.shape, dtype=bool)

    vals = pix_delta[sel]
    n = int(vals.size)
    changed = int((vals > args.pixel_eps).sum())
    result = {
        "plate": args.plate,
        "baseline": args.baseline,
        "size": [a.width, a.height],
        "region_pixels": n,
        "max_pixel_delta": int(vals.max()) if n else 0,
        "mean_abs_delta": float(diff[sel].mean()) if n else 0.0,
        "changed_pixels": changed,
        "changed_ratio": changed / n if n else 0.0,
        "pixel_eps": args.pixel_eps,
    }
    ok = True
    if args.max_pixel_delta is not None:
        ok = ok and result["max_pixel_delta"] <= args.max_pixel_delta
    if args.max_diff_ratio is not None:
        ok = ok and result["changed_ratio"] <= args.max_diff_ratio
    result["pass"] = ok
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
