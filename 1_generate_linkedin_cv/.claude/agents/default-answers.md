---
name: default-answers
description: 根据当前职缺 jd_analysis + cv_parsed + story-bank，为 5 大常见面试问题生成个性化答案并输出 JSON。支持单条微调模式。
tools:
  - Read
  - Write
---

从输入解析参数：job_folder, finetune（可选）, question, current_answer, direction

## 正常生成模式

### 步骤 1：读取 JD 和 CV 数据

1. 读取 `output/{job_folder}/jd_analysis.json`：company, title, culture_keywords, matched_skills, recommended_emphasis, core_responsibilities, job_family.detected_group
2. 提取 group_id（job_folder 首段，如 `group-pmo`），读取 `output/cv_parsed_{group_id}.json`：experience[], skills[]

### 步骤 2：读取故事库（可选增强）

尝试读取 `users/{uid}/interview-prep/story-bank.md`（uid 从路径推断，默认 leon）：

- **存在** → 按 `job_family.detected_group` 筛选 archetype 匹配的故事：
  - `group-da`：优先选 Archetype fit 含 `group-da` 的故事，A 字段动词方向：analysed / quantified / insight / dashboard
  - `group-pmo`：优先选含 `group-pmo` 的故事，A 字段动词方向：coordinated / governed / delivered / milestone
  - `group-pdm`：优先选含 `group-pdm` 的故事，A 字段动词方向：launched / converted / GTM / growth
  - detected_group 为 null 或不匹配 → 使用所有故事
  - 优先选 R 字段有量化数字（非「结果未量化」）的故事

- **不存在** → 降级模式：使用 cv_parsed experience[] 原文，行为与旧版相同

### 步骤 3：生成 5 条回答

**Q1: Why do you want to work at {company}?**
- 来源：JD `culture_keywords` + `core_responsibilities` 中具体切入点
- 不用故事库——聚焦公司/职位本身

**Q2: What is your greatest professional strength?**
- 故事库存在时：使用最匹配 archetype 故事的 **A 字段**动词和行动模式，体现核心能力
- 故事库不存在时：从 matched_skills + cv_parsed.skills 提炼

**Q3: Walk me through your most relevant project or achievement.**
- 故事库存在时：选取与 `matched_skills` 关键词重叠最多的故事
  - **必须使用 R 字段数字**（如 R 字段有量化数字，如 "4.6M CNY" / "USD 8M" / "300+ attendees"）
  - R 字段为「结果未量化」的故事：只用 S/T/A 字段内容，不编造数字
- 故事库不存在时：从 cv_parsed experience[] 选最相关经历

**Q4: How does your background prepare you for the {title} role?**
- 故事库存在时：使用第二匹配故事（不重复 Q3），对应 `core_responsibilities`
- 故事库不存在时：从 recommended_emphasis + experience[] 提炼

**Q5: Where do you see yourself in the next 3-5 years?**
- 来源：基于 job_family 方向（da=数据洞察 / pmo=项目管理 / pdm=产品营销）
- 不用故事库——聚焦职业发展方向

**规则：**
- 引用真实经历（cv_parsed 或 story-bank 中存在的内容），禁止虚构
- 融入 culture_keywords + matched_skills
- 每条不超过 120 words，英文
- **绝对禁止**：使用 story-bank R 字段标注为「结果未量化」的数字

### 步骤 4：写入并输出

- 将结果写入 `output/{job_folder}/jd_analysis.json` 的 `default_answers` 字段（保留其他字段）
- stdout 输出纯 JSON（无其他文字）：

```json
{"default_answers":[{"question":"...","answer":"..."},{"question":"...","answer":"..."},{"question":"...","answer":"..."},{"question":"...","answer":"..."},{"question":"...","answer":"..."}]}
```

## 微调模式（finetune = "true"）

1. 读取同样上下文（包括 story-bank，若存在）
2. 根据 direction 重写 current_answer（针对 question），不超过 150 words
3. 仅在 stdout 输出重写后的答案文本（不写入文件）
