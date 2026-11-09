#!/usr/bin/env python3
"""displacement_guard.py — 置换图保护区断言。

用途
----
动态卡用深度置换图做 2.5D 视差。v4 版本「拖动时裤裆在动」的真源是置换图
在骨盆区域数值偏离中性值 128，拖动时该区域被差分推移。本脚本断言：
指定保护区（矩形）内 |v - neutral| 的最大值与均值必须 ≈ 0，超限退出码非 0，
用作合成前门禁，防止保护区（脸、骨盆等）被置换带动。

参数
----
image            置换图 PNG（灰度或 RGB；RGB 时取指定通道，默认 R）
--rect           保护区矩形 "x0,y0,x1,y1"，像素坐标，可重复传入多个
--rect-norm      同上但为 0-1 归一化坐标，可重复传入多个
--channel        RGB 图取哪个通道：R/G/B/lum（默认 R）
--neutral        中性值（默认 128）
--max-abs        |v-neutral| 最大值容忍（默认 1.0）
--mean-abs       |v-neutral| 均值容忍（默认 0.5）

退出码：0 = 全部保护区达标；1 = 有保护区超限；2 = 输入错误。
指标以 JSON 打印到 stdout。
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image


def parse_rect(s: str):
    parts = [float(p) for p in s.split(",")]
    if len(parts) != 4:
        raise ValueError(f"bad rect: {s}")
    return parts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--rect", action="append", default=[])
    ap.add_argument("--rect-norm", action="append", default=[])
    ap.add_argument("--channel", choices=["R", "G", "B", "lum"], default="R")
    ap.add_argument("--neutral", type=float, default=128.0)
    ap.add_argument("--max-abs", type=float, default=1.0)
    ap.add_argument("--mean-abs", type=float, default=0.5)
    args = ap.parse_args()

    try:
        im = Image.open(args.image)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"cannot open image: {e}"}))
        return 2
    w, h = im.size
    if im.mode in ("L", "I;16", "I"):
        v = np.asarray(im.convert("L")).astype(np.float32)
        channel_used = "L"
    else:
        arr = np.asarray(im.convert("RGB")).astype(np.float32)
        idx = {"R": 0, "G": 1, "B": 2}[args.channel] if args.channel != "lum" else None
        if idx is None:
            v = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
        else:
            v = arr[..., idx]
        channel_used = args.channel

    rects = []
    for s in args.rect:
        try:
            rects.append([int(round(x)) for x in parse_rect(s)])
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            return 2
    for s in args.rect_norm:
        try:
            n = parse_rect(s)
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            return 2
        rects.append(
            [int(round(n[0] * w)), int(round(n[1] * h)),
             int(round(n[2] * w)), int(round(n[3] * h))]
        )
    if not rects:
        print(json.dumps({"error": "no --rect / --rect-norm given"}))
        return 2

    regions = []
    all_pass = True
    for r in rects:
        x0, y0, x1, y1 = r
        x0, x1 = max(0, min(x0, w)), max(0, min(x1, w))
        y0, y1 = max(0, min(y0, h)), max(0, min(y1, h))
        if x1 <= x0 or y1 <= y0:
            print(json.dumps({"error": f"empty rect after clamp: {r}"}))
            return 2
        dev = np.abs(v[y0:y1, x0:x1] - args.neutral)
        mx, mn = float(dev.max()), float(dev.mean())
        ok = mx <= args.max_abs and mn <= args.mean_abs
        all_pass = all_pass and ok
        regions.append(
            {
                "rect_px": [x0, y0, x1, y1],
                "max_abs_dev": mx,
                "mean_abs_dev": mn,
                "pass": ok,
            }
        )

    result = {
        "image": args.image,
        "size": [w, h],
        "channel_used": channel_used,
        "neutral": args.neutral,
        "tolerances": {"max_abs": args.max_abs, "mean_abs": args.mean_abs},
        "regions": regions,
        "pass": all_pass,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
