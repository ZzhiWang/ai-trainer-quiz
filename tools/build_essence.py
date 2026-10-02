#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从「等级认定题库 + 大赛理论题库」里筛出 1000 道精华题，输出 data/essence.json。

筛选原则（全部可复现）：
  1. 只收答案可信度达标的题：官方答案 / 多源一致 / 已复核 / 第三方（需非 AI 补答）。
  2. 按《考试说明》的 9 个理论知识域统一归类，每个域都有配额，保证覆盖不偏科。
  3. 题型配额：单选 600 / 判断 250 / 多选 150。
  4. 近似重复的题只保留一条。
  5. 输出只存 id 列表 + 分组，不复制题目本体（题目永远只有一份数据）。
"""

import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STD = os.path.join(ROOT, "data", "questions.json")
N9 = os.path.join(ROOT, "data", "questions-n9.json")
OUT = os.path.join(ROOT, "data", "essence.json")

# 复用 build_n9 的知识域规则
import importlib.util
spec = importlib.util.spec_from_file_location("build_n9", os.path.join(ROOT, "tools", "build_n9.py"))
b9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b9)
DOMAINS = b9.DOMAINS
CH_ORDER = b9.CH_ORDER

QUOTA = {"single": 600, "judge": 250, "multi": 150}
TRUST = {"official": 5, "consensus": 4, "reviewed": 4, "override": 4, "gz": 2, "ww": 2, "bank": 2, "n9": 2, "ai": 0}
# 大赛题库（第九届公开题库）是本届对口题源，精华题里给它 40% 的份额，其余取自等级认定题库
N9_RATIO = 0.40


def norm(s):
    return re.sub(r"[\s，。、；：？！,.;:?!（）()【】\[\]\"'“”‘’]", "", s or "")


def classify(q):
    return b9.classify(q["stem"], " ".join((q.get("opts") or {}).values()))


def quality(q):
    """题目质量启发式评分，用于同域内的排序。"""
    score = 0
    n = len(q["stem"])
    if 12 <= n <= 60:
        score += 2
    elif n <= 120:
        score += 1
    if q["type"] == "judge":
        score += 1
    else:
        if len(q.get("opts") or {}) == 4:
            score += 2
        if all(len(v) >= 2 for v in (q.get("opts") or {}).values()):
            score += 1
    if q.get("exp"):
        score += 1
    return score


def main():
    std = json.load(open(STD, encoding="utf-8"))["questions"]
    n9 = json.load(open(N9, encoding="utf-8"))["questions"]

    pool = []
    for q in std:
        if q.get("src") == "ai":          # AI 补答的答案不进精华
            continue
        if not q.get("ans"):
            continue
        pool.append((q, "std"))
    for q in n9:
        if not q.get("ans"):
            continue
        pool.append((q, "n9"))

    # 去掉跨库/库内的近似重复
    seen = {}
    uniq = []
    for q, bank in pool:
        key = norm(q["stem"])[:24]
        if key in seen:
            continue
        seen[key] = q["id"]
        q = dict(q)
        q["_bank"] = bank
        q["_ch"], q["_sec"] = classify(q)
        uniq.append(q)

    buckets = defaultdict(list)
    for q in uniq:
        buckets[(q["_ch"], q["_sec"], q["type"])].append(q)

    for k, items in buckets.items():
        items.sort(key=lambda q: (-TRUST.get(q.get("src"), 1), -quality(q), q["id"]))

    # 按域分配题型配额：以各域题目数量开方为权重，保证小域也有份；
    # 每个（域，题型）内部再按 N9_RATIO 在「大赛题库 / 等级认定题库」之间分账。
    picked = []
    for qtype, total in QUOTA.items():
        domains = [ch for ch in CH_ORDER if any(k[0] == ch and k[2] == qtype for k in buckets)]
        weights = {}
        for ch in domains:
            available = sum(len(v) for k, v in buckets.items() if k[0] == ch and k[2] == qtype)
            weights[ch] = available ** 0.5
        wsum = sum(weights.values()) or 1
        quota = {}
        for ch in domains:
            quota[ch] = max(int(round(total * weights[ch] / wsum)), min(6, weights[ch] and 6 or 0))
        # 修正总量
        while sum(quota.values()) > total:
            ch = max(quota, key=lambda c: quota[c])
            if quota[ch] <= 1:
                break
            quota[ch] -= 1
        while sum(quota.values()) < total:
            ch = max(weights, key=lambda c: weights[c] - quota.get(c, 0))
            quota[ch] = quota.get(ch, 0) + 1

        for ch in domains:
            want = quota[ch]
            secs = [s for s in dict.fromkeys(k[1] for k in buckets if k[0] == ch and k[2] == qtype)]
            cand = {"n9": [], "std": []}
            for sec in secs:
                for q in buckets[(ch, sec, qtype)]:
                    cand[q["_bank"]].append(q)
            for b in cand:
                cand[b].sort(key=lambda q: (-TRUST.get(q.get("src"), 1), -quality(q), q["id"]))

            want_n9 = min(len(cand["n9"]), int(round(want * N9_RATIO)))
            want_std = min(len(cand["std"]), want - want_n9)
            # 一边不够就把缺口让给另一边
            if want_n9 + want_std < want:
                extra = want - want_n9 - want_std
                more_n9 = min(len(cand["n9"]) - want_n9, extra)
                want_n9 += more_n9
                extra -= more_n9
                want_std += min(len(cand["std"]) - want_std, extra)
            chosen = cand["n9"][:want_n9] + cand["std"][:want_std]
            chosen.sort(key=lambda q: (-TRUST.get(q.get("src"), 1), -quality(q), q["id"]))
            picked.extend(chosen)

    # 兜底：若某题型没凑够，从剩余题里补
    for qtype, total in QUOTA.items():
        have = [q for q in picked if q["type"] == qtype]
        if len(have) >= total:
            continue
        rest = [q for q in uniq if q["type"] == qtype and q not in picked]
        rest.sort(key=lambda q: (-TRUST.get(q.get("src"), 1), -quality(q), q["id"]))
        picked.extend(rest[: total - len(have)])

    order = {ch: i for i, ch in enumerate(CH_ORDER)}
    to = {"judge": 0, "single": 1, "multi": 2}
    picked.sort(key=lambda q: (order.get(q["_ch"], 99), to[q["type"]], q["id"]))

    ids = [q["id"] for q in picked]
    group_of = {q["id"]: [q["_ch"], q["_sec"]] for q in picked}
    groups = []
    for ch in CH_ORDER:
        sub = [q for q in picked if q["_ch"] == ch]
        if not sub:
            continue
        secs = []
        for sec in dict.fromkeys(q["_sec"] for q in sub):
            secs.append({
                "sec": sec,
                "count": len([q for q in sub if q["_sec"] == sec]),
                "single": len([q for q in sub if q["_sec"] == sec and q["type"] == "single"]),
                "judge": len([q for q in sub if q["_sec"] == sec and q["type"] == "judge"]),
                "multi": len([q for q in sub if q["_sec"] == sec and q["type"] == "multi"]),
            })
        groups.append({"ch": ch, "count": len(sub), "secs": secs})

    out = {
        "version": "2026-10-01",
        "title": "精华题 · 考纲精选",
        "total": len(ids),
        "counts": dict(Counter(q["type"] for q in picked)),
        "banks": dict(Counter(q["_bank"] for q in picked)),
        "sources": dict(Counter(q.get("src") for q in picked)),
        "ids": ids,
        "groupOf": group_of,
        "groups": groups,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    print("精华题:", len(ids), out["counts"], "| 来源分区:", out["banks"])
    print("答案来源:", out["sources"])
    print("知识域分布:")
    for g in groups:
        print("   %-28s %4d" % (g["ch"], g["count"]))
    print("输出:", OUT)


if __name__ == "__main__":
    main()
