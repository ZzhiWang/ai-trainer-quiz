#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把题库原始文件合并成站点用的 data/questions.json。

输入（默认相对本仓库根目录）：
  题库/*.docx                                     官方复习题 / 模拟试卷（题目本体）
  tools/sources/ai_trainer_l3_answers_xxiao.xlsx  第三方三级答案（900 题）
  tools/sources/gz_l3_questions.json              第三方三级答案 + 解析（900 题）
  tools/sources/gz_l3_questions_new.json          第三方三级新增题（610 题）
  tools/sources/ww_l4_questions.json              第三方四级答案 + 解析（646 题）
  tools/overrides.json                            人工裁定（答案冲突 / AI 补答案）

答案可信度从高到低：official > reviewed > consensus > bank > gz/ww > ai

用法：python3 tools/build_bank.py
"""

import html
import json
import os
import re
import sys
import zipfile
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "sources")

DOCX = {
    3: "题库/第3部分-人工智能训练师_3级_理论知识复习题.docx",
    4: "题库/第3部分-人工智能训练师_4级_理论知识复习题.docx",
}
EXAM = {
    3: "题库/第5部分_人工智能训练师_3级_理论知识模拟试卷.docx",
    4: "题库/第5部分_人工智能训练师_4级_理论知识模拟试卷.docx",
}

TYPE_LABEL = {"judge": "判断题", "single": "单选题", "multi": "多选题"}
TYPE_ORDER = {"judge": 0, "single": 1, "multi": 2}

# 第三方题库里的英文知识点标签 -> 中文
TAG_MAP = {
    "training": "训练",
    "design": "设计",
    "basics": "基础",
    "analysis": "分析",
    "ethics": "伦理",
    "guide": "指导",
}


def clean_tag(tag):
    tag = (tag or "").strip()
    if not tag:
        return ""
    if tag in TAG_MAP:
        return TAG_MAP[tag]
    # "人工智能训练师4级考点" 这类和级别标签重复，丢掉
    if re.search(r"考点", tag):
        return ""
    return tag


def clean_stem(stem):
    """把题干里的空白括号统一成全角空格，避免被 HTML 折叠成“（）”。"""
    stem = re.sub(r"\s+", " ", stem).strip()
    return re.sub(r"[（(]\s*[)）]", "（　　）", stem)


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def norm(text):
    """归一化题干，用于跨来源匹配 / 去重。"""
    text = re.sub(r"[\s\u3000]", "", text)
    text = re.sub(r"[（）()【】\[\]。，,．.、；;：:？?！!“”\"'‘’·—\-_/\\|~`]", "", text)
    return text


def docx_paragraphs(path):
    """抽取 docx 正文段落文本（按 w:p 切分，避开 w:tcPr 之类的伪标签）。"""
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    out = []
    for chunk in xml.replace("</w:p>", "\x00").split("\x00"):
        texts = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", chunk, flags=re.S)
        line = html.unescape("".join(texts)).strip()
        if line:
            out.append(line)
    return out


RE_JUDGE = re.compile(r"^[（(]\s*[)）]\s*(\d+)\s*[.．、]\s*(.+)$")
RE_NUM = re.compile(r"^(\d+)\s*[.．、]\s*(.+)$")
RE_OPT = re.compile(r"^[（(]\s*([A-E])\s*[)）]\s*(.*)$")
RE_SECTION = re.compile(r"^(?:[一二三四五六七八九十]+\s*[、.．]\s*)?(判断题|单选题|多选题|简答题)")


def split_sections(lines):
    """把段落切成 [(标题, 段落列表), ...]。"""
    marks = [i for i, l in enumerate(lines) if RE_SECTION.match(l) and len(l) < 90]
    if not marks:
        return []
    secs = []
    for k, start in enumerate(marks):
        end = marks[k + 1] if k + 1 < len(marks) else len(lines)
        secs.append((lines[start], lines[start + 1:end]))
    return secs


def section_kind(title):
    if "判断" in title:
        return "judge"
    if "多选" in title:
        return "multi"
    return "single"


def parse_section(title, body):
    """把一个小节解析成题目列表。"""
    kind = section_kind(title)
    qs = []
    cur = None
    for line in body:
        if kind == "judge":
            m = RE_JUDGE.match(line) or RE_NUM.match(line)
            if m:
                cur = {"n": int(m.group(1)), "stem": m.group(2).strip(), "opts": OrderedDict()}
                qs.append(cur)
                continue
        else:
            m = RE_NUM.match(line)
            if m and not RE_OPT.match(line):
                cur = {"n": int(m.group(1)), "stem": m.group(2).strip(), "opts": OrderedDict()}
                qs.append(cur)
                continue
        mo = RE_OPT.match(line)
        if mo and cur is not None and kind != "judge":
            cur["opts"][mo.group(1)] = mo.group(2).strip()
            continue
        # 续行：接到题干或最后一个选项上
        if cur is not None and line:
            if kind != "judge" and cur["opts"]:
                last = list(cur["opts"])[-1]
                cur["opts"][last] += line
            else:
                cur["stem"] += line
    return kind, qs


def parse_bank_docx(path):
    """解析官方复习题 docx -> [(level 无关) 题目 dict]。"""
    lines = docx_paragraphs(path)
    out = []
    for title, body in split_sections(lines):
        kind, qs = parse_section(title, body)
        for q in qs:
            q["type"] = kind
            out.append(q)
    return out


# --------------------------------------------------------------------------
# 官方模拟卷答案（official）
# --------------------------------------------------------------------------
def parse_exam_answers(path):
    """从模拟试卷 docx 里抽出答案，按题干归一化键返回。"""
    lines = docx_paragraphs(path)
    secs = split_sections(lines)
    stems = []  # [(kind, n, stem)]
    for title, body in secs:
        kind, qs = parse_section(title, body)
        for q in qs:
            stems.append((kind, q["n"], q["stem"]))

    # 答案区
    try:
        ai = next(i for i, l in enumerate(lines) if "理论知识试卷答案" in l)
    except StopIteration:
        return {}
    tail = "\n".join(lines[ai:])
    judged = ["√" if v == "√" else "×" for v in re.findall(r"\((√|×|X|x)\)", tail)]

    single_blk = re.search(r"单选题参考答案[^：]*[:：](.*?)(?=多选题参考答案|$)", tail, flags=re.S)
    single = re.findall(r"[A-E]", re.sub(r"\d+\s*[-–]\s*\d+\s*[)）]", "", single_blk.group(1))) if single_blk else []

    multi_blk = re.search(r"多选题参考答案[^：]*[:：](.*)$", tail, flags=re.S)
    multi = re.findall(r"\d+\s*[)）]\s*([A-E]+)", multi_blk.group(1)) if multi_blk else []

    key = {}
    for kind, n, stem in stems:
        if kind == "judge" and 1 <= n <= len(judged):
            key[(kind, norm(stem))] = judged[n - 1]
        elif kind == "single" and 1 <= n <= len(single):
            key[(kind, norm(stem))] = single[n - 1]
        elif kind == "multi" and 1 <= n <= len(multi):
            key[(kind, norm(stem))] = "".join(sorted(multi[n - 1]))
    return key


# --------------------------------------------------------------------------
# 第三方答案源
# --------------------------------------------------------------------------
def parse_xxiao_xlsx(path):
    """第三方三级答案 xlsx：判断/单选/多选 各 300。判断题空白格按“×”处理。"""
    with zipfile.ZipFile(path) as zf:
        def sheet(name):
            xml = zf.read(name).decode("utf-8")
            data = {}
            for row in re.finditer(r"<row[^>]*>(.*?)</row>", xml, flags=re.S):
                cells = {}
                for cm in re.finditer(r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', row.group(1), flags=re.S):
                    col, _, _, inner = cm.groups()
                    inner = inner or ""
                    t = re.search(r"<t[^>]*>(.*?)</t>", inner, flags=re.S)
                    v = re.search(r"<v>(.*?)</v>", inner, flags=re.S)
                    val = html.unescape((t or v).group(1)) if (t or v) else None
                    cells[col] = val
                cols = sorted(cells, key=lambda c: (len(c), c))
                for i in range(0, len(cols) - 1, 2):
                    k, val = cells.get(cols[i]), cells.get(cols[i + 1])
                    if k and str(k).strip().isdigit():
                        data[int(k)] = val
            return data

        j = sheet("xl/worksheets/sheet1.xml")
        s = sheet("xl/worksheets/sheet2.xml")
        m = sheet("xl/worksheets/sheet3.xml")
    judge = {n: ("√" if v == "√" else "×") for n, v in j.items()}
    single = {n: (v or "").strip().upper() for n, v in s.items()}
    multi = {n: "".join(sorted((v or "").strip().upper())) for n, v in m.items()}
    return judge, single, multi


def norm_answer(kind, value):
    """把各种写法的答案统一。"""
    if value is None:
        return None
    v = str(value).strip()
    if kind == "judge":
        if v in ("√", "对", "正确", "T", "TRUE", "true", "Y", "是", "1"):
            return "√"
        if v in ("×", "x", "X", "错", "错误", "F", "FALSE", "false", "N", "否", "0"):
            return "×"
        return None
    v = re.sub(r"[^A-Ea-e]", "", v).upper()
    if not v:
        return None
    letters = sorted(set(v))
    if kind == "single":
        return letters[0] if len(letters) == 1 else None
    return "".join(letters)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def parse_gz(path, new=False):
    """第三方三级题库：返回 (按题干键的答案, 新增题列表)。"""
    data = load_json(path)
    questions = data["questions"] if isinstance(data, dict) else data
    answers, extras = {}, []
    for q in questions:
        kind = q["type"]
        ans = norm_answer(kind, q.get("answer"))
        opts = q.get("options") or {}
        item = {
            "type": kind,
            "stem": (q.get("stem") or "").strip(),
            "opts": OrderedDict((k, (v or "").strip()) for k, v in sorted(opts.items())),
            "answer": ans,
            "exp": (q.get("explanation") or "").strip(),
            "tag": (q.get("knowledge") or "").strip(),
            "src": "gz",
        }
        if new:
            extras.append(item)
        else:
            answers[(kind, norm(item["stem"]))] = ans
    return answers, extras


def parse_ww(path):
    """第三方四级题库：返回 (按题干键的答案, 新增题列表)。"""
    data = load_json(path)
    answers, extras = {}, []
    for q in data:
        kind = q["type"]
        raw = q.get("answer")
        ans = norm_answer(kind, raw)
        opts = OrderedDict()
        text = (q.get("options") or "").strip()
        if text:
            parts = re.split(r"(?=\b[A-E][.．、])", text)
            for p in parts:
                m = re.match(r"^\s*([A-E])[.．、]\s*(.*)$", p.strip())
                if m:
                    opts[m.group(1)] = m.group(2).strip()
        stem = re.sub(r"[。.]?\s*$", "", (q.get("stem") or "").strip())
        item = {
            "type": kind,
            "stem": stem,
            "opts": opts,
            "answer": ans,
            "exp": (q.get("analysis") or "").strip(),
            "tag": (q.get("knowledge") or "").strip(),
            "src": "ww",
        }
        answers[(kind, norm(item["stem"]))] = ans
        extras.append(item)
    return answers, extras


# --------------------------------------------------------------------------
# 合并
# --------------------------------------------------------------------------
def build():
    overrides = {}
    ov_path = os.path.join(ROOT, "tools", "overrides.json")
    if os.path.exists(ov_path):
        overrides = load_json(ov_path)

    official = {}
    for lv, rel in EXAM.items():
        for (kind, key), ans in parse_exam_answers(os.path.join(ROOT, rel)).items():
            official[(lv, kind, key)] = ans

    xj, xs, xm = parse_xxiao_xlsx(os.path.join(SRC, "ai_trainer_l3_answers_xxiao.xlsx"))
    gz_ans, _ = parse_gz(os.path.join(SRC, "gz_l3_questions.json"))
    _, gz_new = parse_gz(os.path.join(SRC, "gz_l3_questions_new.json"), new=True)
    ww_ans, ww_all = parse_ww(os.path.join(SRC, "ww_l4_questions.json"))

    questions = []
    seen = {}
    conflicts = []
    unexplained = []
    stats = Counter()

    def add(level, kind, stem, opts, sources, exp="", tag="", extra_id=None):
        key = (level, kind, norm(stem))
        if key in seen:
            return None
        seen[key] = True
        stem = clean_stem(stem)
        tag = clean_tag(tag)

        qid = extra_id or "L%d-%s-%04d" % (level, {"judge": "J", "single": "S", "multi": "M"}[kind], len(questions) + 1)

        # 官方答案最优先
        cand = OrderedDict()
        for name, value in sources:
            v = norm_answer(kind, value)
            if v is not None:
                cand[name] = v
        override = overrides.get(qid) or overrides.get(norm(stem))

        if override:
            answer = norm_answer(kind, override.get("answer"))
            src = override.get("src", "reviewed")
            note = override.get("note", "")
            stats["override"] += 1
        elif "official" in cand:
            answer = cand["official"]
            src = "official"
            note = ""
        else:
            votes = Counter(v for name, v in cand.items() if name in ("bank", "gz", "ww"))
            if not votes:
                answer, src, note = None, "missing", ""
                unexplained.append((level, kind, stem, qid))
            else:
                top = votes.most_common()
                multi_source = len(cand) >= 2
                if len(top) == 1 or top[0][1] > top[1][1]:
                    answer, note = top[0][0], ""
                    src = "consensus" if multi_source else top_src_name(cand, top[0][0])
                else:
                    answer, src = None, "conflict"
                    note = ""
                    conflicts.append((qid, level, kind, stem, dict(cand)))
        if answer is not None:
            stats[src] += 1

        questions.append({
            "id": qid,
            "lv": level,
            "type": kind,
            "stem": stem,
            "opts": opts,
            "ans": answer,
            "src": src,
            "note": note,
            "exp": exp,
            "tag": tag,
        })
        return qid

    def top_src_name(cand, value):
        for name, v in cand.items():
            if v == value:
                return {"official": "official", "bank": "bank", "gz": "gz", "ww": "ww"}.get(name, name)
        return "bank"

    # 1) 官方复习题
    for level, rel in DOCX.items():
        path = os.path.join(ROOT, rel)
        for q in parse_bank_docx(path):
            kind, stem, opts = q["type"], q["stem"], q["opts"]
            key = norm(stem)
            sources = []
            if (level, kind, key) in official:
                sources.append(("official", official[(level, kind, key)]))
            if level == 3:
                n = q["n"]
                if kind == "judge" and n in xj:
                    sources.append(("bank", xj[n]))
                if kind == "single" and n in xs:
                    sources.append(("bank", xs[n]))
                if kind == "multi" and n in xm:
                    sources.append(("bank", xm[n]))
                if (kind, key) in gz_ans:
                    sources.append(("gz", gz_ans[(kind, key)]))
            else:
                if (kind, key) in ww_ans:
                    sources.append(("ww", ww_ans[(kind, key)]))
            exp, tag = "", ""
            if level == 3:
                gz_map = {norm(s): (e, t) for s, e, t in []}
            add(level, kind, stem, opts, sources)

    # 2) 第三方新增题（三级模拟卷 610 题）
    for item in gz_new:
        add(3, item["type"], item["stem"], item["opts"], [(item["src"], item["answer"])],
            exp=item["exp"], tag=item["tag"])

    # 3) 第三方新增题（四级剩余）
    for item in ww_all:
        if (4, item["type"], norm(item["stem"])) in seen:
            continue
        add(4, item["type"], item["stem"], item["opts"], [(item["src"], item["answer"])],
            exp=item["exp"], tag=item["tag"])

    return questions, conflicts, unexplained, stats


def attach_explanations(questions):
    """把第三方解析挂到对应题目上（有官方答案的也保留解析）。"""
    gz = load_json(os.path.join(SRC, "gz_l3_questions.json"))["questions"]
    gzn = load_json(os.path.join(SRC, "gz_l3_questions_new.json"))["questions"]
    ww = load_json(os.path.join(SRC, "ww_l4_questions.json"))
    index = {}
    for q in gz + gzn:
        index[(3, q["type"], norm(q.get("stem") or ""))] = (q.get("explanation") or "").strip(), (q.get("knowledge") or "").strip()
    for q in ww:
        stem = re.sub(r"[。.]?\s*$", "", (q.get("stem") or "").strip())
        index[(4, q["type"], norm(stem))] = (q.get("analysis") or "").strip(), (q.get("knowledge") or "").strip()
    for q in questions:
        if q["exp"]:
            continue
        hit = index.get((q["lv"], q["type"], norm(q["stem"])))
        if hit:
            q["exp"], q["tag"] = hit[0], clean_tag(hit[1])
    return questions


def main():
    questions, conflicts, unexplained, stats = build()
    questions = attach_explanations(questions)
    questions.sort(key=lambda q: (q["lv"], TYPE_ORDER[q["type"]], q["id"]))

    out = {
        "meta": {
            "title": "人工智能训练师 理论刷题",
            "total": len(questions),
            "counts": dict(Counter("%s/%s" % (q["lv"], q["type"]) for q in questions)),
            "answerSources": dict(stats),
        },
        "questions": questions,
    }
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "questions.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(ROOT, "tools", "report_conflicts.json"), "w", encoding="utf-8") as fh:
        json.dump(conflicts, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "tools", "report_missing.json"), "w", encoding="utf-8") as fh:
        json.dump(unexplained, fh, ensure_ascii=False, indent=1)

    print("题目总数:", len(questions))
    print("按级别/题型:", out["meta"]["counts"])
    print("答案来源:", dict(stats))
    print("答案冲突:", len(conflicts))
    print("完全没答案:", len(unexplained))


if __name__ == "__main__":
    main()
