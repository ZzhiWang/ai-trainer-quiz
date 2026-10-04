# 发给 ChatGPT 的完整材料与提示词

## 一、材料（二选一）
- 方案A（推荐，对方能上传文件/有代码工具）：上传 `tools/review/review_bank.jsonl`（全库 2246 题精简版，每行一题 JSON）。
- 方案B（纯对话粘贴）：用 `tools/review/gpt_batches/batch_01.jsonl` ~ `batch_15.jsonl`，每批 150 题，逐批粘贴。
- 可选：`tools/review/ai_disagreements.json`（已有的 294 条可疑清单，供交叉验证）。

## 二、提示词（第 1 条消息，固定发送）

你是《人工智能训练师》国家职业技能等级认定（三级/四级）理论题库的资深审题专家，熟悉该职业的国家职业技能标准和教材口径。

我会分批发给你题目数据，格式为 JSONL，每行一道题，字段含义：
- id：题目编号（务必原样返回）
- lv：等级（3=三级，4=四级）
- type：题型（judge=判断，single=单选，multi=多选）
- ch / sec：所属章/节
- stem：题干
- opts：选项（判断题为空 {}）
- ans：题库现有答案（判断题 √/×；多选为字母组合）
- exp：题库现有解析

请对每道题完成三项检查：
1. 答案正确性：ans 是否为该题唯一正确答案；
2. 解析一致性：exp 的结论是否与 ans 指向同一选项；
3. 解析正确性：exp 的推理与各项对错判断本身是否正确。

判定规则（严格遵守）：
1. 以《人工智能训练师》国家职业标准与官方教材/复习题口径为准，不要按个人偏好作答。
2. 注意否定式题干（"不正确的是/不属于/错误的是/不包括/无效的是"），答案应是"不符合要求"的那一项。
3. 单选给 1 个字母；多选给字母组合且按 A→E 升序（如 ABD）；判断只给 √ 或 ×。
4. 多选不要因"看起来该全选"就机械全选，也不要以"语义重复/多余"为由删掉本身成立的选项。
5. 不确定必须标 confidence=low，不要强行下结论。
6. 只改答案与解析，不得改动题干和选项。
7. 解析用中文，50~150 字，先给结论再说明其余选项为何不选；不得出现"题库""原答案""AI"等字样。

输出格式（严格 JSON，不要任何多余文字）：
{
  "batch": "<批次名>",
  "total": <本批题数>,
  "ok": <完全没问题的题数>,
  "issues": [
    {"id":"L3-S-0364","issue":"answer_wrong|exp_mismatch|exp_wrong|multiple",
     "correct_answer":"D 或 null","new_exp":"修正后的解析，无需修改则空字符串",
     "confidence":"high|medium|low","reason":"一句话依据"}
  ]
}

说明：
- 完全正常的题不要出现在 issues 中。
- issue：answer_wrong=答案错；exp_mismatch=解析结论与答案不一致；exp_wrong=解析本身有误；multiple=同时存在多个问题。
- 若答案错，correct_answer 必须给出；若只是解析问题，correct_answer 填 null。

示例
输入：{"id":"L3-S-0364","lv":3,"type":"single","ch":"业务分析","sec":"业务流程设计","stem":"为了确保抓取的数据质量，（　　）方法是无效的。","opts":{"A":"设置合理的抓取间隔","B":"使用更复杂的抓取规则","C":"避免抓取重复内容","D":"减少抓取深度"},"ans":"A","exp":"减少抓取深度会遗漏更多层级的数据，反而降低数据完整性……"}
输出：{"batch":"batch_01","total":150,"ok":149,"issues":[{"id":"L3-S-0364","issue":"exp_mismatch","correct_answer":null,"new_exp":"……","confidence":"high","reason":"解析结论指向 D，与题库答案 A 不一致"}]}

## 三、提示词（第 2 条及以后每条消息）

这是第 {X}/15 批，批次名 batch_{XX}，共 {N} 题，请开始审题：
{把 batch_XX.jsonl 的内容整段粘贴}

## 四、回传
把每批返回的 JSON 原样贴回（或存成 `batch_XX.result.json`），我负责合并、与题库交叉核对并落库。
