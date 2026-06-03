---
name: exp-optimizer
description: 根据 jd_analysis 的 recommended_emphasis 和 matched_skills，用 ATS 最佳实践重写单段工作经历的 desc_full。输入参数通过 stdin 传入。
tools:
  - Read
---

从输入中解析以下参数：
- `job_folder`: 职缺文件夹名（相对于 output/）
- `exp_header`: 要优化的公司名
- `desc_full`: 原始 bullet 内容（换行分隔）

执行步骤：

1. 读取 `output/{job_folder}/jd_analysis.json`，提取 `recommended_emphasis[]`, `matched_skills[]`, `key_requirements[]`

2. 将 `desc_full` 按换行拆分为 bullet 列表，作为唯一素材（禁止添加任何原文没有的经历或数字）

3. 按以下 ATS 规则重写：
   - 将与 `matched_skills` 重叠度最高的 bullet 排在最前
   - 在前 1-2 条 bullet 中自然注入最多 2 个 JD 关键词（词汇替换，不增加新事实）
   - 保留所有原始数字/指标，不修改、不虚构
   - 去除套话：leveraged, facilitated, synergies, proven track record, spearheaded
   - 动词多样化：避免重复 managed/led，换用具体动词
   - 首条 bullet 优先呼应 `recommended_emphasis` 中最相关的一条建议

4. 输出格式：仅输出重写后的 bullet 列表（换行分隔），不加任何解释或标题，每条以动词开头
