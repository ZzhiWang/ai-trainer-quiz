#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""强制覆写指定题目的解析（用于修正“解析与答案不一致”等错误）。

与 fill_exp.py / fill_exp_lv.py 的区别：那两个脚本只给“解析为空”的题目补解析，
本脚本用于**强制覆写**已有解析，输入为 tools/fix/*.jsonl：
    {"id": "L4-S-1163", "exp": "A正确：……"}

会自动判断 id 属于哪个题库（data/questions.json 或 data/questions-n9.json），
只更新 exp（并保留 ans 与答案来源 src 不变）。

用法：
    python3 tools/apply_fix.py            # 应用并输出报告
    python3 tools/apply_fix.py --check    # 只统计，不写入
"""

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANKS = [os.path.join(ROOT, "data", "questions.json"),
         os.path.join(ROOT, "data", "questions-n9.json")]
FIX_DIR = os.path.join(ROOT, "tools", "fix")


def load_fixes():
    fixes, bad = {}, 0
    files = sorted(glob.glob(os.path.join(FIX_DIR, "*.jsonl")))
    for path in files:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except Exception:
                bad += 1
                continue
            qid, exp = obj.get("id"), (obj.get("exp") or "").strip()
            if qid and exp:
                fixes[qid] = exp
    return files, fixes, bad


def main():
    check_only = "--check" in sys.argv
    files, fixes, bad = load_fixes()
    applied, unknown, unchanged = 0, [], 0

    for bank in BANKS:
        data = json.load(open(bank, encoding="utf-8"))
        hit = False
        for q in data["questions"]:
            new = fixes.get(q["id"])
            if not new:
                continue
            hit = True
            if (q.get("exp") or "").strip() == new:
                unchanged += 1
            else:
                q["exp"] = new
                q.setdefault("expSrc", "ai")
                applied += 1
        if hit and not check_only:
            json.dump(data, open(bank, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))

    ids = set()
    for bank in BANKS:
        ids |= {q["id"] for q in json.load(open(bank, encoding="utf-8"))["questions"]}
    unknown = [k for k in fixes if k not in ids]

    print("修正文件:", [os.path.basename(f) for f in files], "（JSON 解析失败 %d 行）" % bad)
    print("本次覆写解析:", applied, "条；已一致:", unchanged, "条")
    if unknown:
        print("题库中不存在的 id:", unknown)


if __name__ == "__main__":
    main()
