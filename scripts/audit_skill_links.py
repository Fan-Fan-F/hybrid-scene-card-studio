#!/usr/bin/env python3
"""audit_skill_links.py — SKILL.md 相对链接完整性审计。

用途
----
技能包 P0 故障：SKILL.md 正文引用了 references/、scripts/、assets/ 下的
文件，但发布包里这些文件根本不存在，照文档执行必然断链。本脚本扫描
SKILL.md 中所有 Markdown 相对链接（形如 (references/xxx.md)），逐个验证
目标文件在磁盘上存在，输出缺失清单；有缺失则退出码非 0，用作打包门禁。

参数
----
skill_md         SKILL.md 路径；链接相对该文件所在目录解析
--prefixes       只审计这些前缀的链接，逗号分隔
                 （默认 references/,scripts/,assets/）
--include-all    审计全部相对链接（忽略 http(s)、锚点、mailto 等）

退出码：0 = 无缺失；1 = 有缺失；2 = 输入错误。
指标以 JSON 打印到 stdout。
"""
import argparse
import json
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
DEFAULT_PREFIXES = ("references/", "scripts/", "assets/")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("skill_md")
    ap.add_argument("--prefixes", default=",".join(DEFAULT_PREFIXES))
    ap.add_argument("--include-all", action="store_true")
    args = ap.parse_args()

    md_path = Path(args.skill_md)
    if not md_path.is_file():
        print(json.dumps({"error": f"not a file: {md_path}"}))
        return 2
    text = md_path.read_text(encoding="utf-8", errors="replace")
    base = md_path.parent
    prefixes = tuple(p.strip() for p in args.prefixes.split(",") if p.strip())

    targets = []
    for m in LINK_RE.finditer(text):
        raw = m.group(1).strip("<>")
        if raw.startswith(("http://", "https://", "mailto:", "#", "sandbox:")):
            continue
        path_part = raw.split("#")[0]
        if not path_part:
            continue
        if not args.include_all and not path_part.startswith(prefixes):
            continue
        targets.append(path_part)

    unique = sorted(set(targets))
    missing, present = [], []
    for t in unique:
        (present if (base / t).exists() else missing).append(t)

    result = {
        "skill_md": str(md_path),
        "base_dir": str(base),
        "links_found_total": len(targets),
        "links_unique": len(unique),
        "present_count": len(present),
        "missing_count": len(missing),
        "missing": missing,
        "pass": not missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
