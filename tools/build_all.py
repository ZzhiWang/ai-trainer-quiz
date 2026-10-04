#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键重建题库（顺序固定、可重复运行）。

为什么需要它：
    data/questions.json 不是由 tools/build_bank.py 单独产出的，后面还有
    “补解析”和“修正覆写”两步。直接跑 build_bank.py 会把这些解析丢掉。

流程（data/questions.json）：
    1) tools/build_bank.py     —— 生成基础题库（题干/答案/来源，部分解析）
    2) tools/fill_exp_lv.py    —— 用 tools/gen_lv/*.jsonl 给空解析填空（expSrc=ai）
    3) tools/apply_fix.py      —— 用 tools/fix/*.jsonl 覆写答案/题干/解析（人工裁定）

可选（--with-n9）额外重建大赛题库 data/questions-n9.json：
    4) tools/build_n9.py → tools/fill_exp.py → tools/apply_fix.py

安全校验：运行前后对比题库，若出现“原本有解析、重建后变空”的题（且不在
tools/fix 覆盖范围内），会明确报警并以非零码退出，避免静默丢数据。

用法：
    python3 tools/build_all.py
    python3 tools/build_all.py --with-n9
    python3 tools/build_all.py --dry-run     # 只打印将要执行的步骤
"""

import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LV_BANK = os.path.join(ROOT, "data", "questions.json")
N9_BANK = os.path.join(ROOT, "data", "questions-n9.json")


def load_bank(path):
    if not os.path.exists(path):
        return {}
    data = json.load(open(path, encoding="utf-8"))
    return {q["id"]: q for q in data.get("questions", [])}


def fix_ids():
    ids = set()
    for path in glob.glob(os.path.join(ROOT, "tools", "fix", "*.jsonl")):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                ids.add(json.loads(line).get("id"))
            except Exception:
                pass
    return ids


def run(script, dry=False):
    print("  →", script)
    if dry:
        return
    subprocess.run([sys.executable, os.path.join(ROOT, script)], cwd=ROOT, check=True)


def report(before, after, path):
    lost = [i for i in after
            if (before.get(i, {}).get("exp") or "").strip()
            and not (after[i].get("exp") or "").strip()]
    changed = [i for i in after if json.dumps(before.get(i), ensure_ascii=False, sort_keys=True)
               != json.dumps(after[i], ensure_ascii=False, sort_keys=True)]
    print("  %s: 题数 %d -> %d，变化 %d 条" % (os.path.relpath(path, ROOT), len(before), len(after), len(changed)))
    if changed:
        print("     变化题:", ", ".join(sorted(changed)[:12]) + (" …" if len(changed) > 12 else ""))
    if lost:
        allowed = fix_ids()
        bad = [i for i in lost if i not in allowed]
        print("     ⚠ 解析被清空 %d 条%s" % (len(lost), ("，其中未在 tools/fix 声明的 %d 条: %s"
              % (len(bad), ", ".join(sorted(bad)[:10]))) if bad else "（均已在 tools/fix 声明）"))
        return len(bad)
    return 0


def main():
    dry = "--dry-run" in sys.argv
    with_n9 = "--with-n9" in sys.argv

    before_lv = load_bank(LV_BANK)
    print("[1/3] 重建等级认定题库 data/questions.json" + ("（dry-run）" if dry else ""))
    run("tools/build_bank.py", dry)
    run("tools/fill_exp_lv.py", dry)

    before_n9 = load_bank(N9_BANK)
    if with_n9:
        print("[2/3] 重建大赛理论题库 data/questions-n9.json")
        run("tools/build_n9.py", dry)
        run("tools/fill_exp.py", dry)
    else:
        print("[2/3] 跳过 n9（加 --with-n9 可一并重建）")

    print("[3/3] 应用 tools/fix 修正")
    run("tools/apply_fix.py", dry)

    if dry:
        print("\n(dry-run 结束，未写入)")
        return

    bad = report(before_lv, load_bank(LV_BANK), LV_BANK)
    if with_n9:
        bad += report(before_n9, load_bank(N9_BANK), N9_BANK)
    if bad:
        sys.exit(1)
    print("\n完成：题库已重建，未丢失任何解析。")


if __name__ == "__main__":
    main()
