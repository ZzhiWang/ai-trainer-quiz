#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析补全第一步：先在已有题库/第三方来源里"搜索"这道题，能搜到就直接复用解析。

搜索顺序（命中即停）：
  1. data/questions.json（等级认定题库，2134 条带解析）
  2. tools/sources/gz_l3_questions.json（900 条）
  3. tools/sources/gz_l3_questions_new.json（610 条）
  4. tools/sources/ww_l4_questions.json（646 条）

匹配策略：题干归一化后先精确匹配，再做模糊匹配（difflib 相似度 ≥ 0.88 且长度接近）。
命中结果写入 tools/gen/n9_exp_from_source.jsonl，带 from 字段标明来源，
交给 fill_exp.py 合并（expSrc 会记成对应来源，而不是 ai）。
"""

import difflib
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N9 = os.path.join(ROOT, "data", "questions-n9.json")
OUT = os.path.join(ROOT, "tools", "gen", "n9_exp_from_source.jsonl")
THRESHOLD = 0.88


def norm(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"[\s，。、；：？！,.;:?!（）()【】\[\]\"'“”‘’_`~\-—]", "", s)


def load_candidates():
    cands = []

    std = json.load(open(os.path.join(ROOT, "data", "questions.json"), encoding="utf-8"))["questions"]
    for q in std:
        if q.get("exp"):
            cands.append({"from": "std", "stem": q["stem"], "exp": q["exp"], "ans": q.get("ans")})

    for name, key_stem, key_exp in [
        ("gz", "stem", "explanation"),
        ("gznew", "stem", "explanation"),
    ]:
        path = os.path.join(ROOT, "tools", "sources", "%s_l3_questions%s.json" % (
            "gz" if name == "gz" else "gz", "" if name == "gz" else "_new"))
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        items = data["questions"] if isinstance(data, dict) else data
        for q in items:
            exp = (q.get(key_exp) or "").strip()
            if exp:
                cands.append({"from": name, "stem": q.get(key_stem, ""), "exp": exp, "ans": q.get("answer")})

    ww_path = os.path.join(ROOT, "tools", "sources", "ww_l4_questions.json")
    if os.path.exists(ww_path):
        for q in json.load(open(ww_path, encoding="utf-8")):
            exp = (q.get("analysis") or "").strip()
            if exp:
                cands.append({"from": "ww", "stem": q.get("stem", ""), "exp": exp, "ans": q.get("answer")})

    for c in cands:
        c["key"] = norm(c["stem"])
    return [c for c in cands if len(c["key"]) >= 8]


def main():
    data = json.load(open(N9, encoding="utf-8"))
    todo = [q for q in data["questions"] if not (q.get("exp") or "").strip()]
    cands = load_candidates()
    print("候选解析来源: %d 条" % len(cands))

    exact = {}
    # 4-gram 倒排索引：只和共享若干字符片段的候选做精细比对，避免全量两两比较
    index = {}
    for i, c in enumerate(cands):
        exact.setdefault(c["key"], c)
        grams = set(c["key"][j:j + 4] for j in range(0, max(1, len(c["key"]) - 3)))
        c["_grams"] = grams
        for g in grams:
            index.setdefault(g, []).append(i)
    print("4-gram 索引: %d 个片段" % len(index))

    hits = []
    stats = Counter()
    for q in todo:
        key = norm(q["stem"])
        if len(key) < 8:
            stats["题干过短跳过"] += 1
            continue
        c = exact.get(key)
        score = 1.0
        if not c:
            grams = set(key[j:j + 4] for j in range(0, max(1, len(key) - 3)))
            share = Counter()
            for g in grams:
                for idx in index.get(g, ()):
                    share[idx] += 1
            need = max(3, int(len(grams) * 0.35))
            best = None
            best_score = 0.0
            for idx, cnt in share.items():
                if cnt < need:
                    continue
                cand = cands[idx]
                r = difflib.SequenceMatcher(None, key, cand["key"]).quick_ratio()
                if r < THRESHOLD:
                    continue
                r = difflib.SequenceMatcher(None, key, cand["key"]).ratio()
                if r > best_score:
                    best_score, best = r, cand
            if best and best_score >= THRESHOLD:
                c, score = best, best_score
        if c:
            hits.append({"id": q["id"], "exp": c["exp"], "from": c["from"], "score": round(score, 3)})
            stats["命中-" + c["from"]] += 1
        else:
            stats["未命中"] += 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        for h in hits:
            fh.write(json.dumps(h, ensure_ascii=False) + "\n")

    print("待补解析题目: %d" % len(todo))
    for k, v in stats.most_common():
        print("   %-12s %d" % (k, v))
    print("命中率: %d/%d = %.1f%%" % (len(hits), len(todo), 100.0 * len(hits) / max(1, len(todo))))
    print("输出:", OUT)


if __name__ == "__main__":
    main()
