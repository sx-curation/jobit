---
name: review-ui
description: 当 orchestrator 需要展示搜索结果列表、单个职缺审核界面、或完成汇总时自动加载。提供所有对外展示模板，确保格式一致。
---

# 展示模板集合

---

## 模板 1：搜索结果列表

```
本次搜索结果（新增 {N} 条 | 重复过滤 {M} 条 | 低分隐藏 {K} 条）
批次：{batch_id}  |  原始文件：output/raw_results_{batch_id}.json

排名  职缺                                       预评分   CV       命中关键词
────────────────────────────────────────────────────────────────────────────────
{rank}.  {title} @ {company}                     {bar} {score}  [{group}]  {keyword} ({lang})
     发布：{date}  |  {location}
     输出目录：output/{folder}/
     {url}

⚠  另有 {K} 条预评分低于 30，已隐藏。输入「显示全部」可查看。
```

图例：`[DA]` = my_cv_da.pdf，`[PMO]` = my_cv_pmo.pdf（以 config.json 为准）  
预评分进度条：每 17 分一个 █，共 6 格，例如 84 分 = `██████`，62 分 = `████░░`

---

## 模板 2：单个职缺审核界面

```
═══════════════════════════════════════════════════════════════
审核：{company} — {title}
CV：{cv_file}  |  预评分：{preview}/100  |  精确分：{exact}/100
关键词组：{group_label}  |  命中词：{keyword}  |  批次：{batch_id}
输出目录：output/{folder}/
═══════════════════════════════════════════════════════════════

【评估报告】  overall: {PASS | WARN | FAIL}
─────────────────────────────────────────────────────────────
捏造检测：{status}
{  如有 issue，每条格式：  ⚠/✗ [{severity}] {type} — {detail}  }

字数检查：{count} 词 / {limit} 上限  →  {PASS | OVER_LIMIT}
{  如超限：⚠ 超出 {N} 词，建议压缩第二或第三段  }

JD 覆盖率：必需技能 {X}%  |  核心职责 {Y}%
{  如有缺失：未命中必需技能：{skill1}, {skill2}  }

总结：{eval_report.summary}
─────────────────────────────────────────────────────────────

【CV 改动摘要】
{cv_changes.md 完整内容}

【Cover Letter 预览】
{cover_letter_draft.md 完整内容}

───────────────────────────────────────────────────────────────
{  overall=PASS  时显示：  }  [A] 批准，选择主题后生成 PDF
                              [B] 修改 CV
                              [C] 修改 Cover Letter
                              [D] 跳过此职缺
{  overall=WARN  时显示：  }  [E] 忽略警告，选择主题后生成
                              [B] 修改 CV
                              [C] 修改 Cover Letter
                              [D] 跳过此职缺
{  overall=FAIL  时显示：  }  [B] 修改 CV（必须）
                              [C] 修改 Cover Letter
                              [D] 跳过此职缺
═══════════════════════════════════════════════════════════════
```

---

## 模板 3：PDF 生成确认

```
PDF 已生成：
  CV：output/{folder}/cv_final.pdf
  Cover Letter：output/{folder}/cover_letter_final.pdf
  主题：{selected_theme}

继续下一个职缺...
```

---

## 模板 4：完成汇总

```
══════════════════════════════════════════════
完成汇总
══════════════════════════════════════════════

已生成 PDF（按精确分排序）：
  [{group}]  ✓ [{score}分] {title} @ {company}
                主题：{theme}  |  eval: {overall}
                output/{folder}/

已跳过：
  [{group}]  - [{score}分] {title} @ {company}  — {reason}

搜索统计：
  批次：{batch_id}
  {group_id}: {N} 条职缺  （每个 group 一行）
  重复过滤：{M} 条  |  低分隐藏：{K} 条

Session 结束后自动写入 memory/progress.json + memory/notes.md
══════════════════════════════════════════════
```

---

## 使用规则

- 模板中 `{...}` 为占位符，由 orchestrator 在运行时填入实际值
- 不展示 eval_report 的 `issues` 数组原始 JSON，转为人类可读格式
- 预评分进度条宽度固定 6 格，不足用 `░` 补齐
- 所有路径使用正斜线 `/`，跨平台兼容