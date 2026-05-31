---
name: eval-criteria
description: 当 cv-evaluator agent 开始执行评估时自动加载。定义捏造检测的边界规则、字数统计方法和 JD 命中的模糊匹配策略，避免误判。
---

# 评估标准细则

## 捏造检测边界规则

### 允许的改写，不算捏造
以下情况不应标记为问题：

| 情况 | 例子 | 判定 |
|------|------|------|
| 同义词替换 | 「开发」→「设计并实现」 | 允许 |
| 职责描述的关键词调整 | 「负责数据分析」→「主导数据驱动决策」 | 允许 |
| 技能排序调整 | Python 从第 5 位移到第 1 位 | 允许 |
| Summary 重写 | 整段重写，但内容来自已有经历 | 允许 |
| 公司名格式变化 | 「Deutsche Bahn AG」→「Deutsche Bahn」 | 允许 |

### 必须标记的捏造
| 情况 | 例子 | 标记类型 |
|------|------|---------|
| 新公司名 | cv_parsed 无此公司 | FABRICATED |
| 新职位名 | cv_parsed 无此职位 | FABRICATED |
| 新技能 | cv_parsed.skills 中没有 | ADDED_SKILL |
| 凭空数字 | 「提升 40%」但原文无此数据 | UNVERIFIABLE_METRIC |
| 新项目名 | 原文未提及的项目 | FABRICATED |

### 模糊情况的处理原则
- 缩写展开：`ML` 与 `Machine Learning` 视为同一技能，不标记
- 语言翻译：中文技能名与英文技能名对应，不标记
- 数字单位转换：「3 年」与「36 个月」，不标记
- 不确定时：标记为 `medium` severity，附说明，由用户判断

---

## 字数统计方法

### 英文
```
词数 = len(text.split())
```
去除 Markdown 符号（`#`、`**`、`-` 等）后再统计。
标点不算词。

### 中文
```
字数 = 中文字符数（Unicode CJK 区间 \u4e00-\u9fff）
```
英文单词在中文 Cover Letter 中按「1词=1字」计入。

### 混合语言
若中英文混合，分别统计后换算：英文词数 × 1.5 + 中文字数，对比中文上限 350。

---

## JD 命中的模糊匹配策略

直接字符串匹配经常漏判，使用以下策略：

### 技能命中规则
一个技能「被命中」，需满足以下任一条件：
1. 技能名（或缩写）直接出现在 cv_draft 或 cover_letter_draft 中
2. 技能的同义词出现（同义映射规则见 jd-scoring skill）
3. 技能所属的上位概念出现（如 JD 要求「Tableau」，cv 中有「数据可视化工具」）

### 职责命中规则
一条 `core_responsibility` 被视为「命中」，需满足：
- cv_draft 或 cover_letter_draft 中有语义相近的描述（不要求完全一致）
- 判断标准：该职责的核心动词 + 核心对象至少一个出现

例：`core_responsibility = "Lead cross-functional data projects"`
命中条件：出现「lead/主导/带领」+ 「data/数据」或「project/项目」中的任意组合

### 命中率分级
| 必需技能命中率 | 等级 |
|--------------|------|
| ≥ 80% | 良好 |
| 60–79% | 一般，建议补充 |
| < 60% | 不足，触发 WARN |

---

## Gotchas（常见误判防范）

1. **不要把 Summary 里的泛化描述算作捏造**
   Summary 可以包含「experienced data analyst with 5+ years」这类总结性语句，
   不需要在 experience 里逐条溯源。

2. **不要把 JD 关键词的出现算作技能添加**
   如果 cv_draft 只是在 summary 里提到了某个 JD 关键词，但 skills 列表没有新增，
   不算 ADDED_SKILL。只有 skills 列表新增了 cv_parsed 中没有的项目才算。

3. **年份和时间段不需要精确匹配**
   「2020–2023」和「3 年」描述同一段经历，不算矛盾，不标记。

4. **Cover Letter 字数超限是 WARN 不是 FAIL**
   超出 400 词是建议修改，不阻断流程。用户可以选择接受。