#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从官方《认定要素细目表》抽取"章 / 节 / 细目点"三级结构，写入 tools/sources/outline_lN.json。

细目表是二进制 .doc，这里用 macOS 自带的 textutil 转成文本再解析。
转换结果已提交到 tools/sources/，重新构建题库时不需要再跑这个脚本。

用法：python3 tools/extract_outline.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOC = {
    3: "4-04-05-05_3_20250701/第2部分_人工智能训练师_3级_认定要素细目表.doc",
    4: "4-04-05-05_4_20250701/第2部分_人工智能训练师_4级_认定要素细目表.doc",
}

# 章代码 = 细目点代码第 1 位
CHAPTER = {
    3: {"0": "基本要求", "1": "业务分析", "2": "智能训练", "3": "智能系统设计", "4": "培训与指导"},
    4: {"0": "基本要求", "1": "数据采集和处理", "2": "数据标注", "3": "智能系统运维"},
}

# 节代码 = 细目点代码前 2 位。三级"培训"(41)/"指导"(42) 合并为一个节。
SECTION = {
    3: {
        "01": "职业道德", "02": "基础知识",
        "11": "业务流程设计", "12": "业务模块效果优化",
        "21": "数据处理规范制定", "22": "算法测试",
        "31": "智能系统监控和优化", "32": "人机交互流程设计",
        "41": "培训与指导", "42": "培训与指导",
    },
    4: {
        "01": "职业道德", "02": "基础知识",
        "11": "业务数据质量检验", "12": "数据处理方法优化",
        "21": "数据归类和定义", "22": "标注数据审核",
        "31": "智能系统维护", "32": "智能系统优化",
    },
}


def doc_to_text(path):
    out = os.path.join(tempfile.mkdtemp(), "outline.txt")
    subprocess.run(["textutil", "-convert", "txt", "-output", out, path], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(out, encoding="utf-8") as fh:
        return fh.read()


def rows_of(text):
    """按单元格分隔符切分，再把连续非空单元格还原成表格行。"""
    text = text.split("操作技能认定要素细目表")[0]
    rows, cur = [], []
    for cell in text.split("\x07"):
        if cell == "":
            if cur:
                rows.append(cur)
                cur = []
        else:
            cur.append(cell)
    if cur:
        rows.append(cur)
    return rows


def parse(text, level):
    rows = rows_of(text)
    chapter, section = "", ""
    points = []
    for i, row in enumerate(rows):
        if all(re.fullmatch(r"\d+", c) for c in row) and 1 <= len(row) <= 3:
            nxt = rows[i + 1] if i + 1 < len(rows) else None
            if not nxt or len(nxt) < 2 or not re.fullmatch(r"\d+(\.\d+)?", nxt[-1]):
                continue
            name = nxt[-2]
            if not re.search(r"[\u4e00-\u9fff]", name):
                continue
            code = "".join(row)
            if len(row) == 1:
                chapter = CHAPTER[level].get(code, name)
            elif len(row) == 2:
                section = SECTION[level].get(code, name)
            continue
        # 细目点行：序号 + 4 位代码 + 名称 + 分数
        if (len(row) >= 7 and all(re.fullmatch(r"\d+", c) for c in row[:5])
                and re.fullmatch(r"\d+(\.\d+)?", row[-1]) and re.search(r"[\u4e00-\u9fff]", row[-2])):
            code = "".join(row[1:5])
            points.append({
                "code": code,
                "name": row[-2],
                "ch": chapter,
                "sec": SECTION[level].get(code[:2], section),
            })
    return points


def main():
    if sys.platform != "darwin":
        print("这个脚本需要 macOS 的 textutil；tools/sources/outline_*.json 已提交，一般不用重跑。")
        return
    for level, rel in DOC.items():
        text = doc_to_text(os.path.join(ROOT, rel))
        points = parse(text, level)
        if not points:
            raise SystemExit("解析失败：%s" % rel)
        path = os.path.join(ROOT, "tools", "sources", "outline_l%d.json" % level)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(points, fh, ensure_ascii=False, separators=(",", ":"))
        secs = []
        for p in points:
            if not secs or secs[-1]["sec"] != p["sec"]:
                secs.append({"ch": p["ch"], "sec": p["sec"], "from": len(points) - len(points) + 0})
        print("L%d 细目点 %d 个，章 %d 个，节 %d 个 -> %s" % (
            level, len(points),
            len({p["ch"] for p in points}),
            len({p["sec"] for p in points}),
            os.path.relpath(path, ROOT)))


if __name__ == "__main__":
    main()
