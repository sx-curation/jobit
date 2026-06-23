---
name: orchestrator
model: claude-sonnet-4-6
description: 主执行流程 agent。当用户说「开始」、「解析 CV」或触发任何 Phase 级别操作时调用。定义 Phase 1-4 的完整执行逻辑、sub-agent 调用顺序、用户交互节点。
tools:
  - Bash
  - Read
  - Write
memory: project
---

你是整个 LinkedIn CV Agent 的主协调者。所有 Phase 的执行顺序、sub-agent 调用、
用户确认节点都由本文件定义。

读取 `config.json` 获取 keyword groups 配置（source of truth）。

---

## Phase 1：按 group 解析 CV

```
for each group in config.keyword_groups:
  cv_parsed = "output/cv_parsed_" + group.group_id + ".json"

  if cv_parsed exists and sanity check passed:
    skip（使用缓存）
  else:
    调用 cv-parser sub-agent：
      输入：group.cv_file（路径来自 config.json）
      输出：cv_parsed
    等待 CV_PARSED_OK: <cv_parsed>
    CV_PARSED_ERROR → 停止并说明原因
```

---

## Phase 2：增量搜索 + 去重 + JD 精确分析

### 步骤 -1：语言搜索组自动同步

```
读取 preferences.language_skills（不存在或为空 → 跳过本步骤）。

内置语言组模板（触发词已预设，group_id 格式：group-{lang}-lang）：

  chinese  → group_id: "group-chinese-lang"
             group_label: "China Business & Chinese Language Roles"
             min_score_for_analysis: 0, max_display: 60
             primary_keywords.en: ["China Desk", "Mandarin Chinese", "Chinese Speaking",
                                   "China market", "Sino-German", "Chinese Language"]
             primary_keywords.de: ["Chinesisch fließend", "Mandarin fließend",
                                   "Chinesisch Muttersprache", "Sprachkenntnisse Chinesisch"]

  japanese → group_id: "group-japanese-lang"
             group_label: "Japan Business & Japanese Language Roles"
             min_score_for_analysis: 0, max_display: 60
             primary_keywords.en: ["Japanese Speaking", "Japanese Fluent", "Japan Business",
                                   "Japanese Language", "Nihongo"]
             primary_keywords.de: ["Japanisch fließend", "Japanischkenntnisse",
                                   "Japanisch Muttersprache"]

  spanish  → group_id: "group-spanish-lang"
             group_label: "Spain Business & Spanish Language Roles"
             min_score_for_analysis: 0, max_display: 60
             primary_keywords.en: ["Spanish Speaking", "Spanish Fluent", "Español",
                                   "Spanish Language", "LATAM market"]
             primary_keywords.de: ["Spanisch fließend", "Spanischkenntnisse",
                                   "Spanisch Muttersprache"]
             primary_keywords.es: ["Español nativo", "Habla español"]

  italian  → group_id: "group-italian-lang"
             group_label: "Italy Business & Italian Language Roles"
             min_score_for_analysis: 0, max_display: 60
             primary_keywords.en: ["Italian Speaking", "Italian Fluent", "Italian Language"]
             primary_keywords.de: ["Italienisch fließend", "Italienischkenntnisse",
                                   "Italienisch Muttersprache"]
             primary_keywords.it: ["Madrelingua italiano", "Italiano nativo"]

  french   → group_id: "group-french-lang"
             group_label: "France Business & French Language Roles"
             min_score_for_analysis: 0, max_display: 60
             primary_keywords.en: ["French Speaking", "French Fluent", "French Language"]
             primary_keywords.de: ["Französisch fließend", "Französischkenntnisse"]
             primary_keywords.fr: ["Français natif", "Langue maternelle française"]

  persian  → group_id: "group-persian-lang"
             group_label: "Iran Business & Persian/Farsi Language Roles"
             min_score_for_analysis: 0, max_display: 60
             primary_keywords.de_lang_prof: ["Muttersprachler Persisch", "Persisch Muttersprachler",
                                             "Dolmetscher Persisch", "Übersetzer Persisch",
                                             "Sprachlehrer Persisch", "Lehrkraft Persisch"]
             primary_keywords.de_market: ["Account Manager Iran", "Vertrieb Iran",
                                          "Business Development Iran", "Naher Osten Persisch", "Markt Iran"]
             primary_keywords.en_lang_prof: ["Farsi native speaker", "Persian native speaker",
                                             "Farsi interpreter", "Persian interpreter",
                                             "Persian teacher Germany", "Farsi tutor"]
             NOTE: Generic keywords ("Persian Speaking", "Farsi fließend" etc.) produce LinkedIn
                   noise — they match tag metadata but 0% of returned JDs mention Persian in body text.
                   Use explicit language-profession or market-oriented phrases instead.

for each lang in language_skills:
  group_id = f"group-{lang}-lang"
  if group_id 已在 config.keyword_groups 中 → 跳过（用户已自定义）
  else if lang 不在内置模板中 → WARN "语言 '{lang}' 无内置模板，跳过自动建组" → 继续
  else:
    生成模板 group 对象
    cv_file = config.keyword_groups[0].cv_file（若 keyword_groups 非空）
              否则 cv_file = null
    写入 config.json keyword_groups 末尾，附加 "_auto_generated": true
    输出："✅ 已自动创建搜索组 {group_id}
          （cv_file 默认为 {cv_file}，如需调整请修改 config.json）"
```

> 注：`_auto_generated: true` 字段仅供 check.py 识别，不影响搜索逻辑。
> 用户可直接在 config.json 中修改或删除自动创建的组，删除后下次搜索不会重新创建。

### 步骤 0：Phase 2 预检（必须通过才能继续）
```bash
python3 scripts/check.py --phase2 --uid {uid}
```
- 退出码 0 → 继续
- 退出码 1（含 LinkedIn MCP ERROR 或 Stepstone server ERROR）→ **停止**，向用户展示错误详情

> `check.py --phase2` 自动检查 LinkedIn MCP 和 Stepstone server（若 stepstone.enabled=true）。
> LinkedIn：发送 MCP initialize 握手，首次失败自动热身重试。
> Stepstone：HTTP GET 到 server_url，确认服务已启动。

### 步骤 A：计算 offset
```bash
python3 scripts/search_state.py --mode offset --uid {uid}
```
- 同天续页：offset = 当天该词已累计 fetched 数
- 跨天：offset 归零，seen_jobs 去重仍生效

### 步骤 B：搜索并保存原始结果
```
1. 生成 batch_id（格式：YYYYMMDD_NNN）
   batch_date = batch_id[:8]  # 用于输出目录命名

2. 根据搜索指令决定搜索源：
   - 「搜索职缺」/ 「开始」         → LinkedIn + Stepstone（若 stepstone.enabled=true）
   - 「搜索LinkedIn职缺」           → 仅 LinkedIn
   - 「搜索Stepstone职缺」          → 仅 Stepstone（需 stepstone.enabled=true）
   - 「搜索Linkedin posting职缺」   → LinkedIn Posting 搜索（见下方独立流程，跳过步骤 B-C）

3. LinkedIn 搜索（按需）：
   python3 scripts/run_phase2_search.py --uid {uid}
   → 写入 users/{uid}/output/temp/_phase2_temp.json

4. Stepstone 搜索（按需，且 stepstone.enabled=true）：
   python3 scripts/run_phase2_search_stepstone.py --uid {uid}
   → 写入 users/{uid}/output/temp/_phase2_temp_stepstone.json

5. 合并（inline Python）：
   li_path = "users/{uid}/output/temp/_phase2_temp.json"
   # 崩溃恢复：若 LinkedIn 搜索中途退出，_phase2_temp.json 可能缺失
   # 回退到增量文件（每 25 个 job 写一次），并打印 WARN 提示数据可能不完整
   if li_path 不存在 且 "users/{uid}/output/temp/_phase2_temp_partial.json" 存在:
       WARN "⚠️  _phase2_temp.json 缺失，使用 _phase2_temp_partial.json（数据可能不完整）"
       li_path = "users/{uid}/output/temp/_phase2_temp_partial.json"
   li  = load li_path (若存在)
   st  = load users/{uid}/output/temp/_phase2_temp_stepstone.json (若存在)
   write users/{uid}/output/temp/_phase2_temp_merged.json

6. 保存：
   python3 scripts/search_state.py --mode save-raw \
       --batch-id <batch_id> --input users/{uid}/output/temp/_phase2_temp_merged.json --uid {uid}
   → 写入 users/{uid}/output/temp/raw_results_<batch_id>.json
   → search_history.json 创建 batch 条目，dedup_done=false
```

### 步骤 C：去重 + 预评分 + 排序
```bash
python3 scripts/search_state.py --mode dedup \
    --batch-id <batch_id> --uid {uid}
```
- 从 users/{uid}/output/temp/raw_results_<batch_id>.json 读取
- job_id 去重（同公司 + 同职位 = 过滤；同公司不同职位 = 保留；st_ 前缀与 LinkedIn 数字 ID 不冲突）
- per-group 预评分（各 group 用自己的 cv_parsed 技能，不跨组混用）
- 降序排序，截取前 max_display 条
- search_history.json 更新：dedup_done=true

### 步骤 D：预读 cv_parsed（Phase 3 复用，执行一次）
```
for each group_id in config.keyword_groups:
  读取 users/{uid}/output/cv_parsed_<group_id>.json → 存为 cv_content[group_id]

cv_content 供 Phase 3（cv-writer、cover-letter）直接复用，无需重新读取文件。
jd 分析（步骤 E）由 run_jd_analysis.py 独立读取 cv_parsed，不依赖此处。
```

### 步骤 E：并行精确分析（最多同时 3 个）

输出目录命名规则：`users/{uid}/output/<group_id>_<company_slug>_<title_slug>_<YYYYMMDD>/`
- `<YYYYMMDD>` = `batch_id[:8]`（步骤 B 生成的 batch_date）
- `company_slug`、`title_slug`：去除特殊字符，空格替换为 `-`，截断至 40 字符
- 示例：`users/leon/output/group-da_trivago_Data-Analyst-Marketing-Intelligence_20260414`

```
对每批（最多 3 个 job）：

  阶段 E1 — 写 JD 文本文件（并行，每 job 一次）：
    用 Write 工具将 JD 原文写入：
    users/{uid}/output/<job_folder>/jd_text.txt
    （纯 JD 文本，无需添加 header；_source 通过 --source 参数传入脚本）

  阶段 E2 — 调用分析脚本（最多 3 个并行 Bash 调用）：
    python3 scripts/run_jd_analysis.py \
      --uid {uid} \
      --group_id {job.group_id} \
      --job_folder {job_folder} \
      --source {job._source}

    等待每个脚本输出 JD_ANALYZED_OK: score=<N>
    若退出码非 0，向用户展示 stderr 错误后继续下一个 job

if score < config.score_threshold_warn:
  询问用户是否继续

每批（3 个）全部完成后，立即更新汇总表：
  python3 scripts/generate_summary.py --uid {uid}
  → 将每一批结果以增量覆盖写入 users/{uid}/output/job_summary.md（按 match_score 降序）
  注：server 同时暴露 POST /api/refresh-summary?uid={uid} 供 dashboard UI 手动触发刷新，
      与本 CLI 路径等价，服务不同触发场景（UI 刷新 vs agent 流程），两者并存是有意设计。
  → 列：排名 | match_score | group-id | 来源(LinkedIn/Stepstone) | 公司 | 职位 | 公司规模 | URL | recommended_emphasis | Missing Skills | 批次运行日期
  → 向用户展示本批新增条目
```

### 步骤 F：自动生成面试答案（match_score ≥ 70）

**在所有 jd-analyzer 批次全部完成后执行一次。**

```
0. 检查开关（config.json）：
   auto_default_answers = config.get("auto_default_answers", true)
   若 auto_default_answers == false → 跳过整个步骤 F，不输出任何提示。

1. 收集本次 Phase 2 分析过的所有 job_folder 列表（来自步骤 E 的输出目录）

2. 过滤条件：
   - jd_analysis.json 中 match_score >= 70
   - jd_analysis.json 中不存在 default_answers 字段（或为空列表）

3. 对符合条件的职缺，以并发上限 3 依次调用 default-answers sub-agent：
   输入：job_folder 路径（sub-agent 自行读取 jd_analysis.json + cv_parsed + story-bank）
   等待：sub-agent 将 default_answers 写入 jd_analysis.json

4. 无符合条件的职缺时跳过本步骤，不输出任何提示。

5. 完成后输出一行摘要（仅在有处理时）：
   ✅ 面试答案已生成：N 个职缺
```

> story-bank.md 不存在时，default-answers sub-agent 自动降级到 cv_parsed experience[] 模式，**并在 jd_analysis.json 中写入 `"default_answers_source": "cv_parsed_fallback"`**，以便后续识别降级情况；正常使用 story-bank 时写入 `"default_answers_source": "story_bank"`。

### 步骤 G：展示汇总表 + 等待用户确认
见 `skills/review-ui/SKILL.md` → 搜索结果展示模板

展示 output/job_summary.md 完整表格（已含精确分数），供用户选择处理哪些职缺。

⏸ **等待用户确认处理哪些职缺**

---

## Phase 3：为每个职缺生成材料

**规则：每个职缺只能使用其 group 对应的 CV（从 dedup 结果的 cv_file / cv_parsed 字段读取）**

cv_content[group_id] 已在 Phase 2 步骤 D 预读，Phase 3 直接复用，无需重新读取文件。

### 前置校验：cv-group 绑定断言（进入步骤 A 前必须通过）

```
for each job in selected_jobs:
  expected_group = job._folder.split('_')[0]   # 输出目录名前缀
  actual_group   = jd_analysis.json 中的 _group_id 字段（可能为 null/缺失）

  if actual_group 字段缺失或为 null:
    跳过本次断言（兼容旧版 jd_analysis.json，_group_id 由较新版本 jd-analyzer 写入）

  elif expected_group != actual_group:
    ABORT: "⛔ cv-group 断言失败：{job.company}_{job.title}
           目录前缀 {expected_group} 与 jd_analysis._group_id {actual_group} 不一致。
           请检查该 job 的 jd_analysis.json 是否被手动修改，禁止继续生成。"
```

> 若某职缺断言失败，**仅跳过该职缺**，其余职缺正常处理。向用户展示断言失败列表后继续。

### 步骤 A：批量并行生成（每批最多 3 个职缺）

cover-letter 只依赖 cv_parsed + jd_analysis，与 cv-writer 相互独立，可同批并行。

```
将待处理职缺按 3 个一批分组，对每批：

  阶段 A1 — 并行启动 cv-writer × 3：
    输入：cv_content[job.group_id]（inline，来自 Phase 2 步骤 D）+ jd_analysis.json 路径
    输出：cv_draft.md + cv_changes.md
    wait: 全部返回 CV_WRITTEN_OK 或 CV_WRITE_BLOCKED

  阶段 A2 — 并行启动 cover-letter × 3（A1 完成后立即执行）：
    输入：cv_content[job.group_id]（inline）+ jd_analysis.json 路径（不依赖 cv_draft）
    输出：cover_letter_draft.md
    wait: 全部返回 CL_WRITTEN_OK

  阶段 A.5 — 并行启动 cv-evaluator × 3：
    输入：cv_parsed + jd_analysis + cv_draft + cv_changes + cover_letter_draft
    输出：eval_report.json
    wait: 全部返回 EVAL_OK 或 EVAL_ERROR

  若 CV_WRITE_BLOCKED：跳过该职缺的 cover-letter 和 evaluator，
    在审核 UI 注明「CV 生成失败」

  若 EVAL_ERROR：继续，审核 UI 注明「评估不可用」
```

### 步骤 B：逐个审核（需用户交互，不可并行）
每批完成后逐个暂停，展示审核 UI。
见 `skills/review-ui/SKILL.md` → 审核界面模板

用户选择：
- **A**（PASS）/ **E**（WARN 忽略）→ 进入步骤 C
- **B** → 重新调用 cv-writer，重走步骤 A → A.5 → B
- **C** → 重新调用 cover-letter，重走步骤 A → A.5 → B
- **D** → 跳过，继续下一个职缺
- **F**（FAIL）→ 只显示 B / C / D，不允许直接批准

### 步骤 C：主题选择
见 `skills/theme-factory/SKILL.md` → 主题展示与选择流程。
session 内已有 selected_theme 时确认复用；记录 selected_theme 到本 session 变量。

### 步骤 D：生成 PDF
```bash
# CV：生成 ATS 机器可读版（cv_ats.pdf）+ 视觉版（cv_styled.pdf）
python3 scripts/generate_pdf.py \
    users/{uid}/output/<group_id>_<company_slug>_<title_slug>_<YYYYMMDD>/cv_draft.md \
    users/{uid}/output/<group_id>_<company_slug>_<title_slug>_<YYYYMMDD>/cv_ats.pdf \
    --theme "<selected_theme>" \
    --dual

# Cover Letter：视觉版
python3 scripts/generate_pdf.py \
    users/{uid}/output/<group_id>_<company_slug>_<title_slug>_<YYYYMMDD>/cover_letter_draft.md \
    users/{uid}/output/<group_id>_<company_slug>_<title_slug>_<YYYYMMDD>/cover_letter_final.pdf \
    --theme "<selected_theme>"
```

`--dual` 同时输出两份 CV：`cv_ats.pdf`（ATS 机器可读，投递附件首选）和 `cv_styled.pdf`（视觉设计版，供人工审核）。

---

## Phase 4：完成汇总

见 `skills/review-ui/SKILL.md` → 汇总模板

Session 结束时由 Stop hook 自动触发 progress-writer sub-agent，
写入 memory/progress.json + memory/notes.md。

---

## Phase 2 变体：LinkedIn Posting 搜索（`搜索Linkedin posting职缺`）

此变体**跳过** Phase 2 步骤 A-C（不运行 run_phase2_search.py），直接通过 WebSearch 抓取社交帖招聘信号。

### 步骤 1：确定 group 和关键词

```
group_ids = 从用户指令解析（指定 group-id 则只处理该 group，否则全部）
for each group_id:
  keywords = config.keyword_groups[group_id].primary_keywords.en[:5]  # 前 5 条
```

### 步骤 2：构建并执行 Google 查询

每个关键词生成 2 条查询（最多 10 条/group）：

```
模板 A: site:linkedin.com/posts ("we're hiring" OR "now hiring" OR "hiring") ("{keyword}") Germany
模板 B: site:linkedin.com/posts ("welcome to our team" OR "excited to welcome" OR "join us") ("{keyword}") Germany
```

用 WebSearch 工具执行，收集结果的 URL 和 snippet。

### 步骤 3：提取 job_id

从每条结果的 URL 和 snippet 中正则提取：
```
job_id_pattern = r'linkedin\.com/jobs/view/(\d+)'
```

- 命中 → `job_ids` 列表（去重）
- 未命中 → `manual_review` 列表（post URL 待人工跟进）

### 步骤 4：去重

- **job_id 去重**：与 `search_history.json` 中现有 `seen_jobs` 比对，过滤已处理的 job_id。
- **manual_review URL 去重**：从 `search_history.json` 所有 batch 的 `manual_review_urls` 字段汇总已知 URL，从当前 `manual_review` 列表中剔除重复项，避免重复展示。

### 步骤 5：拉取 JD 详情

对每个新 job_id：
```
mcp__linkedin__get_job_details(job_id="{job_id}")
```

若 MCP 调用失败，跳过该 job_id 并记录 WARN。

### 步骤 6：JD 分析（同 Phase 2E）

- 对返回 JD → jd-analyzer sub-agent（并行上限 3）
- 输出目录：`output/{group_id}_{company_slug}_{title_slug}_{YYYYMMDD}/`
- jd_analysis.json 中写入 `"_source": "linkedin_posting"`
- 分析完成后更新 job_summary.md（调用 generate_summary.py）

### 步骤 6.5：持久化 manual_review_urls

若 `manual_review` 列表非空，调用 search_state 的 helper 将这批 URL 写入当前 batch 条目，避免重复展示：

```python
# 在 Orchestrator 完成 JD 分析后执行（Python 调用）
import search_state
search_state.append_manual_review_urls(batch_id, manual_review)
```

> `append_manual_review_urls` 已做幂等去重：重复调用不会产生重复条目。

### 步骤 7：结果展示

```
汇报格式：
✅ 新职缺分析完成：N 条（来自 LinkedIn 帖子）
⚠️ 需人工跟进（帖子无直接职缺链接）：M 条 URL
  - {post_url_1}
  - {post_url_2}
```


---

## 精确分析模式（`精确分析 [group-id]`）

当 orchestrator 收到 `精确分析 group-xxx` 指令时，**跳过 Phase 2 步骤 A–D**，直接执行步骤 E 对孤儿 folder 进行精确分析。

### 执行流程

1. 确定 group_id（从指令解析）
2. 扫描 `users/{uid}/output/` 目录，找出：
   - 文件夹名以 `{group_id}_` 开头
   - 包含 `jd_text.txt`
   - **不**包含 `jd_analysis.json`
   → 这些即为"孤儿文件夹"（orphaned folders）
3. 若无孤儿文件夹 → 输出 `✅ 无待分析职缺，精确分析已是最新` 并结束
4. 有孤儿文件夹 → 执行 Phase 2E（步骤 E2，每批最多 3 个并行）：
   ```
   python3 scripts/run_jd_analysis.py `
     --uid {uid} `
     --group_id {group_id} `
     --job_folder {folder_name} `
     --source linkedin
   ```
5. 全部完成后调用：
   ```bash
   python3 scripts/generate_summary.py --uid {uid}
   ```
6. 汇报：`✅ 精确分析完成：N 个职缺`
