#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 AI 生成的解析合并进 data/questions-n9.json。

解析以 JSONL 形式逐批写入 tools/gen/*.jsonl，每行：
    {"id": "N9-S-0001", "exp": "答案 C。……"}

特性：
  - 幂等：同一 id 重复出现时以后写的为准，已有解析的题目不会被覆盖为空。
  - 可续跑：随时中断，重新运行会把所有 jsonl 重新合并一遍。
  - 只给 exp 为空的题目写解析，并打上 expSrc='ai'（答案来源 src 保持 'n9' 不变）。

用法：
    python3 tools/fill_exp.py            # 合并并输出覆盖率
    python3 tools/fill_exp.py --check    # 只统计，不写入
"""

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "data", "questions-n9.json")
GEN_DIR = os.path.join(ROOT, "tools", "gen")


def load_jsonl():
    items = {}
    files = sorted(glob.glob(os.path.join(GEN_DIR, "*.jsonl")))
    bad = 0
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
                    # from 字段标明解析来自哪个题源（搜索结果），没有则是 AI 生成
                    items[qid] = {"exp": exp, "from": (obj.get("from") or "").strip(),
                                  "score": obj.get("score")}
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
        rec = gen.get(q["id"])
        if rec and not (q.get("exp") or "").strip():
            q["exp"] = rec["exp"]
            q["expSrc"] = rec["from"] or "ai"
            filled += 1
        elif rec and q.get("exp"):
            pass  # 已经有解析，保留原样

    total = len(questions)
    with_exp = sum(1 for q in questions if (q.get("exp") or "").strip())
    from collections import Counter
    srcs = Counter(q.get("expSrc") or "?" for q in questions if (q.get("exp") or "").strip())
    data["meta"]["explained"] = with_exp
    data["meta"]["explainSources"] = dict(srcs)

    if not check_only:
        with open(BANK, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))

    print("生成文件:", [os.path.basename(f) for f in files])
    print("jsonl 有效解析: %d 条（解析失败 %d 行）" % (len(gen), bad))
    if unknown:
        print("警告：%d 条解析的 id 不在题库里，例如 %s" % (len(unknown), unknown[:3]))
    print("本次新增解析: %d 条" % filled)
    print("解析覆盖率: %d / %d = %.1f%%" % (with_exp, total, 100.0 * with_exp / total))
    if check_only:
        print("（--check 模式，未写入文件）")


if __name__ == "__main__":
    main()
