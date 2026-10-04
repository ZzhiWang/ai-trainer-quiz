#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用人工/AI 裁定的题目修正（答案、题干、解析等）。

输入：tools/fix/*.jsonl，每行一个 JSON 对象：
    {"id": "L4-S-1217", "ans": "D", "stem": "……", "exp": "……",
     "src": "reviewed", "note": "……", "type": "single"}
可出现的字段：exp / ans / stem / opts / src / note / type（至少一个）。
opts 需给出完整的选项字典，如 {"A": "……", "B": "……"}。
只写出现的字段，其余保持题库原值；写 exp 时自动打 expSrc='ai'。

与 fill_exp.py / fill_exp_lv.py 的区别：那两个脚本只给“解析为空”的题目补解析，
本脚本用于**强制覆写**已有内容（修正答案、改写题干或替换解析）。

自动判断 id 属于哪个题库（data/questions.json 或 data/questions-n9.json）。

用法：
    python3 tools/apply_fix.py            # 应用并输出报告
    python3 tools/apply_fix.py --check    # 只统计，不写入
"""

import glob
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANKS = [os.path.join(ROOT, "data", "questions.json"),
         os.path.join(ROOT, "data", "questions-n9.json")]
FIX_DIR = os.path.join(ROOT, "tools", "fix")
FIELDS = ("exp", "ans", "stem", "opts", "src", "note", "type")


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
            qid = obj.get("id")
            if not qid:
                bad += 1
                continue
            patch = {}
            for k in FIELDS:
                if k in obj and obj[k] is not None:
                    v = obj[k]
                    if isinstance(v, str):
                        v = v.strip()
                    if k == "exp" and not v:
                        continue
                    patch[k] = v
            if patch:
                fixes.setdefault(qid, {}).update(patch)
            else:
                bad += 1
    return files, fixes, bad


def refresh_meta(data):
    """修正覆写后重算 meta，避免 counts 与实际题库不一致。

    build_bank.py 只按“覆写前”的题目算 meta；apply_fix 会改 type/src/exp，
    因此这里在写回前统一重算。
    """
    qs = data.get("questions", [])
    meta = data.setdefault("meta", {})
    meta["total"] = len(qs)
    # 键格式与顺序沿用原 meta.counts：等级认定题库用 "lv/type"，大赛题库用 "type"
    old_counts = meta.get("counts") or {}
    # 带 set 标记的大赛题库用 "type" 作键；等级认定题库用 "lv/type"
    prefixed = not meta.get("set")
    key = (lambda q: "%s/%s" % (q["lv"], q["type"])) if prefixed else (lambda q: q["type"])
    counts = Counter(key(q) for q in qs)
    ordered = {}
    for k in old_counts:
        if k in counts:
            ordered[k] = counts.pop(k)
    ordered.update(counts)
    meta["counts"] = ordered
    meta["answerSources"] = dict(Counter((q.get("src") or "?") for q in qs))
    explained = [q for q in qs if (q.get("exp") or "").strip()]
    meta["explained"] = len(explained)
    meta["explainSources"] = dict(Counter((q.get("expSrc") or "?") for q in explained))
    return meta


def main():
    check_only = "--check" in sys.argv
    files, fixes, bad = load_fixes()
    applied, unchanged = 0, 0
    unknown = []
    touched = []

    for bank in BANKS:
        data = json.load(open(bank, encoding="utf-8"))
        hit = False
        for q in data["questions"]:
            patch = fixes.get(q["id"])
            if not patch:
                continue
            hit = True
            same = all((q.get(k) or "") == v for k, v in patch.items())
            if same and ("exp" not in patch or q.get("expSrc") == "ai"):
                unchanged += 1
                continue
            for k, v in patch.items():
                q[k] = v
            if "exp" in patch:
                q["expSrc"] = "ai"
            applied += 1
            touched.append((q["id"], "+".join(sorted(patch))))
        if hit and not check_only:
            refresh_meta(data)
            json.dump(data, open(bank, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))

    ids = set()
    for bank in BANKS:
        ids |= {q["id"] for q in json.load(open(bank, encoding="utf-8"))["questions"]}
    unknown = [k for k in fixes if k not in ids]

    print("修正文件:", [os.path.basename(f) for f in files], "（无效行 %d）" % bad)
    print(("本次覆写: %d 条" % applied) + ("（--check 未写入）" if check_only else "") +
          "；已一致: %d 条" % unchanged)
    for qid, fields in touched:
        print("   -", qid, "->", fields)
    if unknown:
        print("题库中不存在的 id:", unknown)


if __name__ == "__main__":
    main()
