#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把第九届大赛公开题库（4424 题）转成站点格式 data/questions-n9.json。

输入：tools/sources/n9_raw_questions.json
      （由公开仓库 ZongXR/The-9th-National-Final-of-Workers-Vocational-Skills-Competition
        的「理论题库.xlsx」解析而来，字段：type/q/answer/explain/row）
输出：data/questions-n9.json    站点题库（与 questions.json 同结构，新增 set/expSrc 字段）
      tools/review/n9_report.json  校验报告

设计要点：
  - 新题 id 使用 N9- 命名空间，绝不复用 L3-/L4- 的 id，保证老用户 localStorage 进度不受影响。
  - 答案来源统一标 src='n9'（大赛公开题库，未经官方确认）。
  - 解析来源独立字段 expSrc：'' 表示暂无，'ai' 表示 AI 生成。
  - 按《考试说明》列出的 9 个理论知识域自动归类到 ch/sec，供章节刷题使用。
"""

import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "sources", "n9_raw_questions.json")
OUT_BANK = os.path.join(ROOT, "data", "questions-n9.json")
OUT_REPORT = os.path.join(ROOT, "tools", "review", "n9_report.json")

TYPE_MAP = {"单选题": "single", "多选题": "multi", "判断题": "judge"}
TYPE_PREFIX = {"single": "S", "multi": "M", "judge": "J"}

# ---------------------------------------------------------------- 知识域归类
# 顺序即优先级：越"有辨识度"的域越靠前，最后落到「人工智能基础知识」兜底。
DOMAINS = [
    ("人工智能伦理与合规", [
        ("法律法规", ["网络安全法", "数据安全法", "个人信息保护法", "生成式人工智能服务管理",
                  "深度合成", "条例", "法规", "法律", "条款", "违法", "合规审查", "备案",
                  "著作权", "知识产权", "专利", "开源许可", "许可证", "GDPR"]),
        ("行业标准与规范", ["GB/T", "国家标准", "行业标准", "团体标准", "标准文件", "规范要求",
                      "术语标准", "认证", "职业技能标准", "认定要素"]),
        ("伦理与公平", ["伦理", "公平性", "非歧视", "偏见", "歧视", "可解释", "透明",
                    "问责", "人机协作伦理", "算法公平"]),
    ]),
    ("人工智能安全与责任意识", [
        ("对抗攻击与提示注入", ["提示词注入", "提示注入", "对抗样本", "对抗攻击", "越狱",
                        "后门", "投毒", "数据投毒", "模型窃取", "成员推断"]),
        ("内容安全与幻觉", ["幻觉", "毒性", "有害内容", "内容安全", "生成内容标识", "水印",
                      "敏感内容", "违规内容", "虚假信息"]),
        ("数据安全与隐私", ["隐私", "脱敏", "匿名化", "去标识", "个人信息", "敏感数据",
                      "数据分级", "数据分类分级", "加密", "访问控制", "沙盒", "隔离环境",
                      "泄露", "安全防护"]),
    ]),
    ("数据标注与对齐", [
        ("指令与偏好数据", ["指令数据", "指令微调", "指令标注", "偏好数据", "RLHF", "DPO",
                      "SFT", "human feedback", "对齐"]),
        ("自动标注与校验", ["自动标注", "预标注", "标注一致性", "标注质量", "复核", "审核",
                      "交叉验证标注", "多人标注", "标注结果校验"]),
        ("标注规范与流程", ["标注规范", "标注规则", "标签体系", "标注任务", "标注流程",
                      "标注人员", "标注平台", "标注工具", "标注指南", "标签定义"]),
        ("数据增强与合成", ["数据增强", "合成数据", "数据合成", "样本扩充", "回译",
                      "SMOTE", "过采样", "欠采样", "图像生成", "语音合成"]),
    ]),
    ("数据治理与数据质量", [
        ("数据清洗与预处理", ["清洗", "去重", "缺失值", "异常值", "噪声", "标准化",
                       "归一化", "格式化", "脏数据", "重复数据", "停用词", "分词"]),
        ("数据质量评估", ["数据质量", "覆盖率", "代表性", "完整性", "准确性", "一致性检查",
                     "质量评估", "质量指标"]),
        ("数据采集", ["数据采集", "爬虫", "抓取", "采集工具", "采样", "标注数据采集",
                  "数据获取", "数据来源"]),
        ("数据治理与版本管理", ["数据治理", "数据标准", "数据偏差", "数据版本", "可追溯",
                        "数据集管理", "数据集划分", "黄金数据集", "数据分布", "数据配比"]),
    ]),
    ("人工智能训练师环境配置", [
        ("容器与镜像", ["docker", "镜像", "容器", "kubernetes", "k8s", "compose"]),
        ("GPU 与算力", ["cuda", "cudnn", "显存", "gpu", "算力", "显卡", "nvidia", "驱动版本"]),
        ("环境搭建与依赖", ["虚拟环境", "conda", "pip", "依赖", "环境配置", "环境搭建",
                      "jupyter", "notebook", "ide", "vscode", "pycharm", "版本管理",
                      "requirements"]),
    ]),
    ("模型智能运维", [
        ("推理加速与优化", ["vllm", "tensorrt", "量化", "剪枝", "蒸馏", "推理加速",
                      "显存优化", "吞吐", "延迟", "批处理", "onnx", "onnxruntime"]),
        ("监控与运维", ["监控", "日志", "告警", "漂移", "模型漂移", "数据漂移", "灰度",
                    "回滚", "线上问题", "aiops", "运维"]),
        ("模型部署与服务化", ["部署", "上线", "服务化", "api", "接口", "fastapi", "flask",
                       "模型服务", "边缘部署", "容器化部署", "并发"]),
        ("MLOps 与流水线", ["mlops", "流水线", "pipeline", "ci/cd", "持续集成", "自动化训练",
                       "模型版本管理", "mlflow", "实验跟踪"]),
    ]),
    ("智能训练与模型评估", [
        ("大模型微调", ["lora", "qlora", "微调", "fine-tune", "finetune", "peft", "adapter",
                    "prefix tuning", "p-tuning", "全量微调"]),
        ("模型评估指标", ["准确率", "精确率", "召回率", "f1", "map", "auc", "roc", "混淆矩阵",
                     "评估指标", "bleu", "rouge", "perplexity", "c-eval", "mmlu", "交叉验证",
                     "均方误差", "r2", "rmse"]),
        ("模型训练与调参", ["训练", "超参数", "学习率", "批量大小", "epoch", "优化器",
                      "梯度下降", "adam", "sgd", "正则化", "dropout", "早停", "过拟合",
                      "欠拟合", "损失函数", "反向传播"]),
        ("特征工程", ["特征工程", "特征选择", "特征提取", "降维", "pca", "编码", "one-hot",
                  "独热", "标签编码", "特征缩放"]),
        ("任务建模与算法选型", ["算法选择", "模型选择", "任务建模", "业务需求", "分类任务",
                        "回归任务", "聚类", "监督学习", "无监督", "强化学习", "决策树",
                        "随机森林", "svm", "knn", "xgboost", "lightgbm", "朴素贝叶斯"]),
    ]),
    ("人工智能通用基础能力", [
        ("Python 与数据处理库", ["python", "pandas", "numpy", "dataframe", "series",
                          "matplotlib", "seaborn", "列表", "字典", "函数", "类", "异常处理",
                          "正则表达式", "scikit-learn", "sklearn", "read_csv", "loc", "iloc"]),
        ("SQL 与数据库", ["sql", "数据库", "mysql", "索引", "事务", "查询", "join",
                       "表结构", "主键", "外键"]),
        ("Linux 与命令行", ["linux", "命令行", "shell", "bash", "chmod", "权限", "进程",
                       "目录", "grep", "awk", "sed", "crontab", "top 命令"]),
        ("开发工具与协作", ["git", "github", "版本控制", "分支", "commit", "merge",
                      "代码规范", "重构", "单元测试", "调试", "ide 插件"]),
        ("信息检索与文档", ["检索", "搜索引擎", "技术文档", "论文", "持续学习", "新框架"]),
    ]),
    ("人工智能基础知识", [
        ("大模型机制", ["transformer", "注意力", "attention", "自注意力", "预训练",
                    "大语言模型", "llm", "token", "tokenizer", "上下文窗口", "位置编码",
                    "解码策略", "温度", "top-p", "提示词", "prompt", "思维链", "cot",
                    "agent", "智能体", "工具调用", "mcp", "rag", "检索增强", "向量数据库",
                    "embedding", "多智能体", "工作流编排"]),
        ("深度学习原理", ["神经网络", "卷积", "cnn", "循环神经", "rnn", "lstm", "gru",
                    "激活函数", "relu", "sigmoid", "batchnorm", "池化", "yolo",
                    "目标检测", "图像分类", "语义分割", "多模态", "vit", "生成式",
                    "diffusion", "gan", "bert", "gpt"]),
        ("数学与统计基础", ["线性代数", "矩阵", "向量", "概率", "条件概率", "贝叶斯",
                      "期望", "方差", "协方差", "分布", "微积分", "梯度", "导数",
                      "范数", "距离度量", "余弦相似度", "统计学", "假设检验", "p值"]),
        ("机器学习基础概念", ["机器学习", "训练集", "测试集", "验证集", "模型泛化",
                        "有监督", "无监督", "样本", "标签", "特征", "模型评估基本",
                        "人工智能基本概念", "算法原理"]),
    ]),
]

CH_ORDER = [d[0] for d in DOMAINS]


def classify(stem, opts_text):
    text = (stem + " " + opts_text).lower()
    for ch, secs in DOMAINS:
        for sec, keys in secs:
            for k in keys:
                if k.lower() in text:
                    return ch, sec
    return "人工智能基础知识", "机器学习基础概念"


# ---------------------------------------------------------------- 清洗工具
TAG_RE = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
WS_RE = re.compile(r"[ \t\u00a0\u3000]+")


def clean_text(s):
    if not s:
        return ""
    s = TAG_RE.sub(" ", s)
    s = s.replace("\r", " ").replace("\n", " ").replace("\u2028", " ")
    s = WS_RE.sub(" ", s)
    return s.strip()


def strip_leading_number(s):
    """去掉题干开头的题号，如 '1．' '12、' '3.'"""
    return re.sub(r"^\s*\d{1,4}\s*[．.、,，)）]\s*", "", s).strip()


def main():
    raw = json.load(open(SRC, encoding="utf-8"))
    questions = []
    report = {"dropped": [], "fixed": [], "duplicates": [], "cleaned_html": 0}
    counters = Counter()
    seen = {}

    for item in raw:
        qtype = TYPE_MAP.get((item.get("type") or "").strip())
        if not qtype:
            report["dropped"].append({"reason": "未知题型", "type": item.get("type"),
                                      "stem": (item.get("q") or "")[:60]})
            continue

        row = item.get("row") or []
        stem = strip_leading_number(clean_text(item.get("q") or ""))
        if not stem:
            report["dropped"].append({"reason": "题干为空", "stem": ""})
            continue

        opts = {}
        if qtype != "judge":
            for i, key in enumerate("ABCDEF"):
                idx = 2 + i
                if idx < len(row):
                    text = clean_text(row[idx])
                    if text:
                        opts[key] = text

        raw_ans = (item.get("answer") or "").strip()
        if qtype == "judge":
            if raw_ans in ("正确", "对", "√", "T", "true", "A"):
                ans = "√"
            elif raw_ans in ("错误", "错", "×", "F", "false", "B"):
                ans = "×"
            else:
                report["dropped"].append({"reason": "判断题答案无法识别", "ans": raw_ans,
                                          "stem": stem[:60]})
                continue
        else:
            letters = sorted(set(re.findall(r"[A-F]", raw_ans.upper())))
            if not letters:
                report["dropped"].append({"reason": "选择题答案为空", "stem": stem[:60]})
                continue
            missing = [l for l in letters if l not in opts]
            if missing:
                report["dropped"].append({"reason": "答案指向不存在的选项 %s" % "".join(missing),
                                          "ans": raw_ans, "stem": stem[:60]})
                continue
            if len(opts) < 2:
                report["dropped"].append({"reason": "选项不足 2 个", "stem": stem[:60]})
                continue
            ans = "".join(letters)
            if len(letters) > 1 and qtype == "single":
                qtype = "multi"
                report["fixed"].append({"reason": "单选但答案多字母，已改为多选", "stem": stem[:60]})

        ch, sec = classify(stem, " ".join(opts.values()))
        counters[qtype] += 1
        tid = "N9-%s-%04d" % (TYPE_PREFIX[qtype], counters[qtype])

        q = {
            "id": tid,
            "lv": 3,
            "type": qtype,
            "ch": ch,
            "sec": sec,
            "stem": stem,
            "opts": opts,
            "ans": ans,
            "src": "n9",
            "note": "",
            "exp": "",
            "expSrc": "",
            "tag": "",
            "set": "n9",
        }

        # 题内精确去重（同一题干只保留一条）
        key = re.sub(r"[\s，。、；：？！,.;:?!（）()【】\[\]\"'“”‘’]", "", stem)
        if key in seen:
            report["duplicates"].append({"kept": seen[key], "dropped": tid, "stem": stem[:60]})
            counters[qtype] -= 1
            continue
        seen[key] = tid
        questions.append(q)

    order = {"judge": 0, "single": 1, "multi": 2}
    questions.sort(key=lambda x: (order[x["type"]], x["id"]))

    out = {
        "meta": {
            "title": "第九届全国职工职业技能大赛人工智能训练师赛项 理论题库",
            "set": "n9",
            "total": len(questions),
            "counts": dict(Counter(q["type"] for q in questions)),
            "chapters": dict(Counter(q["ch"] for q in questions)),
            "answerSources": {"n9": len(questions)},
            "version": "2026-10-01",
        },
        "questions": questions,
    }
    os.makedirs(os.path.dirname(OUT_BANK), exist_ok=True)
    with open(OUT_BANK, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    report["summary"] = {
        "total": len(questions),
        "counts": out["meta"]["counts"],
        "chapters": out["meta"]["chapters"],
        "dropped": len(report["dropped"]),
        "fixed": len(report["fixed"]),
        "duplicates": len(report["duplicates"]),
    }
    os.makedirs(os.path.dirname(OUT_REPORT), exist_ok=True)
    with open(OUT_REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    print("题库输出:", OUT_BANK)
    print("题目总数:", len(questions), out["meta"]["counts"])
    print("知识域分布:")
    for ch in CH_ORDER:
        print("   %-28s %d" % (ch, out["meta"]["chapters"].get(ch, 0)))
    print("丢弃:", len(report["dropped"]), "修正:", len(report["fixed"]),
          "题内重复:", len(report["duplicates"]))


if __name__ == "__main__":
    main()
