#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate tools/overrides.json -- the answer adjudication table.
build_bank.py prefers answers from this file over any third-party source.

Three groups:
1. HAND_MISSING  four-level questions with no answer from any source (80) -> src=ai
2. HAND_CONFLICT three-level judge/single conflicts (23) -> hand adjudicated, src=reviewed
3. three-level multi conflicts (66) -> follow the official-style answer key
   (that key matches the official mock-paper multi answers 7/10 vs 2/10 for the AI source)

Usage: python3 tools/make_overrides.py && python3 tools/build_bank.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- 1) four-level questions that no source could answer --------------------
HAND_MISSING = {
    "L4-J-1013": "\u00d7",
    "L4-J-1014": "\u221a",
    "L4-J-1077": "\u221a",
    "L4-J-1078": "\u221a",
    "L4-S-1252": "D",
    "L4-S-1253": "C",
    "L4-S-1254": "C",
    "L4-S-1256": "A",
    "L4-S-1258": "B",
    "L4-S-1260": "D",
    "L4-S-1261": "C",
    "L4-S-1262": "B",
    "L4-S-1264": "B",
    "L4-S-1265": "C",
    "L4-S-1266": "B",
    "L4-S-1268": "C",
    "L4-S-1269": "D",
    "L4-S-1270": "A",
    "L4-S-1272": "C",
    "L4-S-1273": "B",
    "L4-S-1274": "D",
    "L4-S-1276": "B",
    "L4-S-1277": "C",
    "L4-S-1278": "B",
    "L4-S-1280": "B",
    "L4-S-1281": "B",
    "L4-S-1282": "B",
    "L4-S-1284": "B",
    "L4-S-1286": "C",
    "L4-S-1287": "B",
    "L4-S-1288": "D",
    "L4-S-1290": "A",
    "L4-S-1291": "D",
    "L4-S-1292": "D",
    "L4-S-1294": "A",
    "L4-S-1295": "A",
    "L4-S-1296": "B",
    "L4-S-1298": "A",
    "L4-S-1300": "A",
    "L4-S-1302": "D",
    "L4-S-1303": "A",
    "L4-S-1304": "A",
    "L4-S-1306": "C",
    "L4-S-1307": "C",
    "L4-S-1308": "C",
    "L4-S-1310": "B",
    "L4-S-1311": "C",
    "L4-S-1312": "B",
    "L4-S-1314": "D",
    "L4-S-1315": "C",
    "L4-S-1316": "C",
    "L4-S-1318": "C",
    "L4-S-1319": "A",
    "L4-S-1320": "A",
    "L4-S-1322": "B",
    "L4-S-1324": "D",
    "L4-S-1326": "A",
    "L4-S-1328": "B",
    "L4-S-1330": "B",
    "L4-S-1331": "D",
    "L4-S-1332": "C",
    "L4-S-1334": "D",
    "L4-S-1335": "B",
    "L4-S-1336": "B",
    "L4-S-1338": "D",
    "L4-S-1339": "A",
    "L4-S-1340": "C",
    "L4-S-1342": "B",
    "L4-S-1344": "B",
    "L4-S-1345": "A",
    "L4-S-1346": "C",
    "L4-S-1348": "B",
    "L4-S-1349": "B",
    "L4-S-1350": "C",
    "L4-S-1412": "D",
    "L4-S-1474": "D",
    "L4-S-1475": "A",
    "L4-S-1595": "C",
    "L4-S-1596": "B",
    "L4-S-1601": "B",
}

# --- 2) three-level judge/single conflicts, hand adjudicated -----------------
# Only entries that differ from the answer-key value are listed here.
HAND_CONFLICT = {
    "L3-J-0008": ("\u221a", "self-regulatory code, no legal force"),
    "L3-J-0068": ("\u221a", "encryption protects confidentiality, not leakage events"),
    "L3-J-0117": ("\u00d7", "numpy ndarray is homogeneous"),
    "L3-J-0135": ("\u221a", "hash table is the common dedup technique"),
    "L3-J-0140": ("\u221a", "traditional annotation is manual and costly"),
    "L3-S-0362": ("D", "interpretability is a model property, not a data-source metric"),
    "L3-S-0388": ("C", "computational intelligence core: neural, fuzzy, evolutionary"),
    "L3-S-0410": ("C", "filter methods use variance/correlation thresholds"),
    "L3-S-0416": ("D", "Keras high-level API suits fast prototyping"),
}


def main():
    conflicts_path = os.path.join(ROOT, "tools", "report_conflicts.json")
    with open(conflicts_path, encoding="utf-8") as fh:
        conflicts = json.load(fh)

    path = os.path.join(ROOT, "tools", "overrides.json")
    # 与已有裁定合并：build_bank 跑第二遍时冲突已被 overrides 消解，
    # report_conflicts.json 会变空，此时必须保留上一轮已经裁定过的答案。
    overrides = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            overrides = json.load(fh)
    before = len(overrides)

    for qid, answer in HAND_MISSING.items():
        overrides[qid] = {"answer": answer, "src": "ai", "note": "AI filled"}

    for cid, lv, kind, stem, cand in conflicts:
        bank = cand.get("bank")
        if kind == "multi":
            overrides[cid] = {
                "answer": bank,
                "src": "reviewed",
                "note": "multi conflict: follow the answer key",
            }
        else:
            if cid in HAND_CONFLICT:
                answer, note = HAND_CONFLICT[cid]
            else:
                answer, note = bank, "judge/single conflict: keep the answer key"
            overrides[cid] = {"answer": answer, "src": "reviewed", "note": note}

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(overrides, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("overrides.json entries: %d (原有 %d，本次冲突 %d)" % (len(overrides), before, len(conflicts)))


if __name__ == "__main__":
    main()
