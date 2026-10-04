#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对分歧题做多轮不同问法的复核（自洽投票）。"""
import json, os, sys, threading, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.deepseek.com/chat/completions"
KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL = os.environ.get("AI_REVIEW_MODEL", "deepseek-chat")
WORKERS = int(os.environ.get("AI_REVIEW_WORKERS", "8"))
SYS = "你是《人工智能训练师》国家职业技能等级认定题库的审题专家，按教材标准口径作答。"

V = {
 "B": """逐项分析下面这道{lv}级{typ}题的每个选项，再给出结论。只依据教材通识，不要猜测出题人意图。

【题干】{stem}
【选项】{opts}

先对每个选项判断对错，再给出正确答案（{fmt}），最后写解析。
只输出 JSON：{{"answer":"<正确答案>","exp":"<解析>","confidence":"high|medium|low"}}""",
 "C": """这是一道{lv}级{typ}职业资格考试题。请严谨作答。

题目：{stem}
选项：{opts}

请先分别说明每个选项成立或不成立的理由，再给出最终答案（{fmt}）。
只输出 JSON：{{"answer":"<正确答案>","exp":"<解析>","confidence":"high|medium|low"}}""",
}

def call(prompt, temp, retries=4):
    body = json.dumps({"model": MODEL,
        "messages": [{"role":"system","content":SYS},{"role":"user","content":prompt}],
        "temperature": temp, "max_tokens": 1200,
        "response_format": {"type":"json_object"}}).encode()
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(API,data=body,headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=150) as r:
                return json.loads(json.loads(r.read().decode())["choices"][0]["message"]["content"])
        except Exception as e:
            last=e; time.sleep(2*(i+1))
    raise RuntimeError(repr(last))

def build(variant,q):
    opts="（判断题，无选项）" if q["type"]=="judge" else " / ".join(f"{k}. {v}" for k,v in q["opts"].items())
    fmt={"judge":"√ 或 ×","single":"单个字母 A-E","multi":"字母组合按字母升序"}[q["type"]]
    return V[variant].format(lv=q["lv"],typ={"judge":"判断","single":"单选","multi":"多选"}[q["type"]],stem=q["stem"],opts=opts,fmt=fmt)

def main():
    variant=sys.argv[1]; temp=float(sys.argv[2])
    rows=json.load(open(os.path.join(ROOT,"tools","review","ai_disagreements.json")))
    out_path=os.path.join(ROOT,"tools","review","ai_recheck_%s.json"%variant)
    done={r["id"]:r for r in json.load(open(out_path))} if os.path.exists(out_path) else {}
    todo=[r for r in rows if r["id"] not in done]
    print(f"variant {variant} temp {temp}: 共 {len(rows)}，待办 {len(todo)}",flush=True)
    res=list(done.values()); lock=threading.Lock()
    def work(chunk):
        for r in chunk:
            try: a=call(build(variant,r),temp)
            except Exception as e: a={"_error":str(e)}
            rec={"id":r["id"],"type":r["type"],"ai":a}
            with lock:
                res.append(rec); json.dump(res,open(out_path,"w"),ensure_ascii=False,indent=1)
    ch=[todo[i::WORKERS] for i in range(WORKERS)]
    ts=[threading.Thread(target=work,args=(c,)) for c in ch if c]
    [t.start() for t in ts]; [t.join() for t in ts]
    json.dump(res,open(out_path,"w"),ensure_ascii=False,indent=1)
    errs=sum(1 for r in res if "_error" in (r["ai"] or {}))
    print(f"variant {variant}: 完成 {len(res)}，失败 {errs}")

main()
