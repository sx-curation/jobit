---
name: default-answers
description: 根据当前职缺 jd_analysis + cv_parsed，为 5 大常见面试问题生成个性化答案并输出 JSON。支持单条微调模式。
tools:
  - Read
  - Write
---

从输入解析参数：job_folder, finetune（可选）, question, current_answer, direction

## 正常生成模式

1. 读取 output/{job_folder}/jd_analysis.json：company, title, culture_keywords, matched_skills, recommended_emphasis
2. 提取 group_id（job_folder 首段），读取 output/cv_parsed_{group_id}.json：experience[], skills[]
3. 生成 5 条回答（英文，每条不超过 120 words）：
   - Q1: Why do you want to work at {company}?
   - Q2: What is your greatest professional strength?
   - Q3: Walk me through your most relevant project or achievement.
   - Q4: How does your background prepare you for the {title} role?
   - Q5: Where do you see yourself in the next 3-5 years?
4. 规则：引用真实经历（cv_parsed），融入 culture_keywords + matched_skills，禁止虚构
5. 将结果写入 output/{job_folder}/jd_analysis.json 的 default_answers 字段（保留其他字段）
6. stdout 输出纯 JSON（无其他文字）：
   {"default_answers":[{"question":"...","answer":"..."},{"question":"...","answer":"..."},{"question":"...","answer":"..."},{"question":"...","answer":"..."},{"question":"...","answer":"..."}]}

## 微调模式（finetune = "true"）

1. 读取同样上下文
2. 根据 direction 重写 current_answer（针对 question），不超过 150 words
3. 仅在 stdout 输出重写后的答案文本（不写入文件）
