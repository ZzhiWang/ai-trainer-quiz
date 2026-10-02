#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 AI 生成的解析合并进默认分区题库 data/questions.json（等级认定题库）。

与 tools/fill_exp.py 逻辑一致：解析以 JSONL 形式写入 tools/gen_lv/*.jsonl，
每行 {"id": "L4-S-1267", "exp": "答案 A。……"}。

  - 幂等：重复运行结果一致，已有解析的题目不会被覆盖为空。
  - 只给 exp 为空的题目写解析，并打上 expSrc='ai'（答案来源 src 保持不变）。
"""

import glob
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "data", "questions.json")
GEN_DIR = os.path.join(ROOT, "tools", "gen_lv")


def load_jsonl():
    items = {}
    bad = 0
    files = sorted(glob.glob(os.path.join(GEN_DIR, "*.jsonl")))
    for path in files:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    bad += 1
                    continue
                qid = obj.get("id")
                exp = (obj.get("exp") or "").strip()
                if qid and exp:
                    items[qid] = exp
    return files, items, bad


def main():
    check_only = "--check" in sys.argv
    data = json.load(open(BANK, encoding="utf-8"))
    questions = data["questions"]
    ids = set(q["id"] for q in questions)

    files, gen, bad = load_jsonl()
    unknown = [k for k in gen if k not in ids]

    filled = 0
    for q in questions:
        exp = gen.get(q["id"])
        if exp and not (q.get("exp") or "").strip():
            q["exp"] = exp
            q["expSrc"] = "ai"
            filled += 1

    total = len(questions)
    with_exp = sum(1 for q in questions if (q.get("exp") or "").strip())
    srcs = Counter(q.get("expSrc") or "?" for q in questions if (q.get("exp") or "").strip())
    data["meta"]["explained"] = with_exp
    data["meta"]["explainSources"] = dict(srcs)

    if not check_only:
        with open(BANK, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))

    print("jsonl 文件数:", len(files), "有效解析:", len(gen), "（解析失败 %d 行）" % bad)
    if unknown:
        print("题库中不存在的 id:", unknown[:10], "共", len(unknown))
    print("本次新增解析:", filled, "条")
    print("解析覆盖率: %d / %d = %.1f%%" % (with_exp, total, 100.0 * with_exp / total))


if __name__ == "__main__":
    main()
