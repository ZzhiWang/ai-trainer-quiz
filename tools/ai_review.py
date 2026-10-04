#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 DeepSeek 批量复核题库答案/解析。

两种模式：
  fix109  : 针对“题库答案≠解析来源答案”的冲突题，重新判定答案并重写解析
  audit   : 对全库逐题检查 答案与解析是否一致、答案是否正确

输出 JSON 到 tools/review/ 下；支持断点续跑（已完成的 id 自动跳过）。
用法：
  python3 tools/ai_review.py --mode fix109
  python3 tools/ai_review.py --mode audit [--limit N]
"""
import argparse, json, os, re, sys, threading, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.deepseek.com/chat/completions"
KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL = os.environ.get("AI_REVIEW_MODEL", "deepseek-chat")
WORKERS = int(os.environ.get("AI_REVIEW_WORKERS", "8"))

SYSTEM = (
    "你是《人工智能训练师》国家职业技能等级认定题库的资深审题专家，"
    "熟悉三级/四级理论考试的考点与标准答案口径。"
    "你的任务是独立判定题目答案并给出解析，要求严谨、简洁、符合考试口径。"
)

FIX_TMPL = """请复核下面这道{lv}级{typ}题。

【题干】{stem}
【选项】{opts}
【题库现有答案】{ans}
【第三方解析对应的答案】{exp_ans}

要求：
1. 独立判断正确答案（{fmt}）。
2. 指出题库现有答案是否正确；若错误，给出正确字母。
3. 重写解析：先给结论，再逐项说明对/错原因，50~150字，中文，不要出现"题库""第三方"等字样。
只输出 JSON：{{"answer":"<正确答案>","answer_changed":<true|false>,"exp":"<解析>","reason":"<一句话说明判断依据>"}}"""


BLIND_TMPL = """请作答下面这道{lv}级{typ}题。

【题干】{stem}
【选项】{opts}

要求：
1. 给出正确答案（{fmt}）。
2. 写解析：先给结论，再逐项说明对/错原因，50~150字，中文。
只输出 JSON：{{"answer":"<正确答案>","exp":"<解析>","confidence":"high|medium|low"}}"""

AUDIT_TMPL = """请审核下面这道{lv}级{typ}题。

【题干】{stem}
【选项】{opts}
【题库答案】{ans}
【题库解析】{exp}

要求：
1. 判断【题库答案】是否正确（{fmt}）。
2. 判断【题库解析】的结论是否与【题库答案】一致。
3. 若答案错误，给出正确字母；若解析与答案不一致或解析有误，给出修正后的解析（否则 exp 留空）。
只输出 JSON：{{"correct":<true|false>,"consistent":<true|false>,"answer":"<正确字母>","exp":"<需要修正时的新解析，否则空字符串>","reason":"<一句话>"}}"""


def fmt_of(t):
    return {"judge": "√ 或 ×", "single": "单个字母 A-E", "multi": "字母组合，按字母升序，如 ABD"}[t]


def call(prompt, retries=4):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }).encode()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(API, data=body, headers={
                "Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
            return json.loads(data["choices"][0]["message"]["content"])
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("api failed: %r" % last)


def build_prompt(mode, q, extra=None):
    if q["type"] == "judge":
        opts = "（判断题，无选项）"
    else:
        opts = " / ".join(f"{k}. {v}" for k, v in q["opts"].items())
    if mode == "blind":
        return BLIND_TMPL.format(lv=q["lv"], typ={"judge": "判断", "single": "单选", "multi": "多选"}[q["type"]],
                                 stem=q["stem"], opts=opts, fmt=fmt_of(q["type"]))
    if mode == "fix109":
        return FIX_TMPL.format(lv=q["lv"], typ={"judge": "判断", "single": "单选", "multi": "多选"}[q["type"]],
                               stem=q["stem"], opts=opts, ans=q["ans"],
                               exp_ans=(extra or {}).get("exp_ans", ""), fmt=fmt_of(q["type"]))
    return AUDIT_TMPL.format(lv=q["lv"], typ={"judge": "判断", "single": "单选", "multi": "多选"}[q["type"]],
                             stem=q["stem"], opts=opts, ans=q["ans"], exp=q["exp"] or "（无）",
                             fmt=fmt_of(q["type"]))


def run(mode, items, out_path):
    done = {}
    if os.path.exists(out_path):
        for r in json.load(open(out_path)):
            done[r["id"]] = r
    lock = threading.Lock()
    todo = [it for it in items if it[0]["id"] not in done]
    print(f"{mode}: 共 {len(items)} 题，已完成 {len(done)}，待处理 {len(todo)}", flush=True)
    results = list(done.values())

    def worker(chunk):
        for q, extra in chunk:
            try:
                res = call(build_prompt(mode, q, extra))
            except Exception as e:
                res = {"_error": str(e)}
            rec = {"id": q["id"], "lv": q["lv"], "type": q["type"], "stem": q["stem"],
                   "opts": q["opts"], "old_ans": q["ans"], "old_exp": q["exp"],
                   "exp_src_ans": (extra or {}).get("exp_ans", ""), "ai": res}
            with lock:
                results.append(rec)
                json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=1)
                n = len(results)
            if n % 20 == 0:
                print(f"  {mode} 进度 {n}", flush=True)

    chunks = [todo[i::WORKERS] for i in range(WORKERS)]
    threads = [threading.Thread(target=worker, args=(c,)) for c in chunks if c]
    for t in threads: t.start()
    for t in threads: t.join()
    json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=1)
    errs = [r for r in results if "_error" in (r["ai"] or {})]
    print(f"{mode}: 完成 {len(results)}，失败 {len(errs)} -> {out_path}")
    for r in errs[:5]: print("  失败:", r["id"], r["ai"]["_error"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["fix109", "audit", "blind"], required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids-file", default="")
    args = ap.parse_args()
    if not KEY:
        sys.exit("缺少 DEEPSEEK_API_KEY")

    bank = json.load(open(os.path.join(ROOT, "data", "questions.json")))["questions"]
    bank = [q for q in bank if q["lv"] in (3, 4)]
    if args.mode == "blind":
        items = [(q, None) for q in bank]
        if args.ids_file:
            want=set(json.load(open(args.ids_file)))
            items=[(q,None) for q in bank if q["id"] in want]
        elif args.limit: items = items[:args.limit]
        out = os.path.join(ROOT, "tools", "review", "ai_blind_%s.json" % os.environ.get("AI_REVIEW_TAG","all"))
        run("blind", items, out)
        return
    if args.mode == "fix109":
        conf = json.load(open(os.path.join(ROOT, "tools", "review", "ans_exp_conflicts.json")))
        extra = {c["id"]: c for c in conf}
        items = [(q, extra[q["id"]]) for q in bank if q["id"] in extra]
        out = os.path.join(ROOT, "tools", "review", "ai_fixes_109.json")
    else:
        items = [(q, None) for q in bank]
        if args.ids_file:
            want = set(json.load(open(args.ids_file)))
            items = [(q, None) for q in bank if q["id"] in want]
        elif args.limit:
            items = items[:args.limit]
        out = os.path.join(ROOT, "tools", "review", "ai_audit_all.json")
    run(args.mode, items, out)


if __name__ == "__main__":
    main()
