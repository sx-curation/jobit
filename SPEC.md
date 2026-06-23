# Project Spec — LinkedIn CV Agent

> Agent 只读，不得修改。用户修改需求时在此文件追加，不覆盖原有内容。

---

## 核心目标

自动搜索 LinkedIn 最近 2 周的职缺，针对每个职缺用对应版本的 CV 生成定制材料，
经用户审核后输出最终 PDF。所有投递由用户手动完成。

---

## 功能需求

### 搜索

#### 标准搜索（Phase 2）
- 多 keyword group，每组绑定一份 CV（对应关系见 `config.json`）
- 每组关键词含 primary keywords + job family 扩展词
- 双语搜索：EN + DE
- 双源搜索：LinkedIn（uvx linkedin-scraper-mcp）+ Stepstone（本地 HTTP SSE server）
  - `搜索职缺`：同时搜索两源；`搜索LinkedIn职缺`：仅 LinkedIn；`搜索Stepstone职缺`：仅 Stepstone
  - Stepstone 职缀 ID 前缀 `st_`，与 LinkedIn 数字 ID 不冲突
  - Stepstone 需本地启动：`cd C:\tools\mcp-stepstone && python -m stepstone_http_server`
  - Stepstone 开关：`config.json["stepstone"]["enabled"]`（默认 `false`）
- 增量搜索：同天多批次自动续页，跨天重置 offset，保留去重历史
- 去重：job_id + 公司 + 职位三者完全相同才过滤；同公司不同职位保留
- 搜索结果按 match_score_preview 降序展示
- 搜索噪声过滤：自动过滤 company="Share/Save/Apply" 等 LinkedIn UI 残留，description < 150 字自动单次重试
- 崩溃恢复：每 keyword group 完成后立即写 `_phase2_temp_partial.json`；`_phase2_temp.json` 缺失时自动回退到 partial 文件

#### LinkedIn Posting 变体（`搜索Linkedin posting职缺`）

**分叉点**：跳过 Phase 2A-C（不运行 `run_phase2_search.py`），改为 WebSearch 抓取社交帖。

**流程**：
1. 对每个 group 取 `primary_keywords.en` 前 5 条关键词
2. 每条关键词生成 2 条 Google 查询：
   - `site:linkedin.com/posts ("we're hiring" OR "now hiring" OR "hiring") ("{keyword}") Germany`
   - `site:linkedin.com/posts ("welcome to our team" OR "excited to welcome") ("{keyword}") Germany`
3. WebSearch 执行，从结果 URL/snippet 用正则 `linkedin\.com/jobs/view/(\d+)` 提取 job_id
4. 新 job_id → `mcp__linkedin__get_job_details` → jd-analyzer（并行上限 3）
5. 无 job_id 的帖子 URL → `manual_review` 清单（仅展示，不分析）
6. jd_analysis.json 中 `_source` 写入 `"linkedin_posting"`

### CV 与 group 对应
- 对应关系在 `config.json` 的 `keyword_groups[].cv_file` 定义（source of truth）
- 任何情况不得混用不同 group 的 CV
- Scale Up：将新 CV 放入 `users/{uid}/my_cv/`，在 config.json 新增 group 对象即可

### Phase 2 自动流程（Phase 2F）
- JD 分析（match_score ≥ 70）完成后，自动为符合条件的职缺调用 `default-answers` agent
- 开关：`config.json["auto_default_answers"]`（默认 `true`）
- story-bank 不存在时静默降级到 cv_parsed 模式，并在 `jd_analysis.json` 写入 `"default_answers_source": "cv_parsed_fallback"`

### 材料生成（Phase 3）
- 每个职缺生成：定制 CV（Markdown + PDF×2）、Cover Letter（Markdown + PDF + DOCX）
- CV PDF 输出：`cv_ats.pdf`（ATS 机器可读）+ `cv_styled.pdf`（视觉版），通过 `generate_pdf.py --dual` 同时生成
- CV 改写规则：只调整措辞和技能排序，不添加虚构经历或技能
- Cover Letter：四段式结构，英文不超过 400 词
- PDF 主题：通过 theme-factory skill 选择，同 session 内复用

### 评估流程
- cv-evaluator 在 cv-writer + cover-letter 完成后，PDF 生成前运行
- 三个维度：捏造检测 / 字数检查 / JD 覆盖率
- FAIL → 强制修改；WARN → 用户主动确认；PASS → 正常批准

### 审核与人工确认
- Phase 2 搜索结束后暂停，等用户确认处理哪些职缺
- Phase 3 每个职缺完成后暂停，展示评估报告 + 材料预览

### 进度记录
- `memory/progress.json`：结构化状态快照，session 结束覆盖写入
- `memory/notes.md`：自由格式笔记，追加，最新在上

---

## 架构决策

| 决策 | 选择 | 原因 |
|------|------|------|
| LinkedIn 数据来源 | linkedin-scraper-mcp（uvx） | 无需官方 API |
| Stepstone 数据来源 | mcp-stepstone HTTP SSE server（本地） | 第二职缺源，覆盖 DE 主要城市 |
| CV 解析 | PyMuPDF | 轻量，无需 LibreOffice |
| PDF 生成 | fpdf2（pure Python） | Windows 无 GTK/Pango，WeasyPrint 不可用；fpdf2 零外部依赖 |
| Cover Letter 生成 | `gen_cover_letter.py`（fpdf2 + python-docx） | 单脚本同时输出 PDF + DOCX，共享 `parse_cover_letter()` 解析器 |
| 搜索状态 | `users/{uid}/output/search_history.json` | 可读，无需数据库 |
| 中间文件 | `users/{uid}/output/temp/raw_results_<batch_id>.json` | 不用 /tmp，可调试；temp/ 隔离中间文件 |
| 预评分 vs 精确分 | 两阶段 | 预评分快速排序，精确分在 Phase 3A |
| Sub-agent 并行 | 最多 3 个 | 避免界面卡顿 |
| CV 验证 | PostToolUse hook | 100% 拦截，优于 CLAUDE.md 指令 |
| 进度记录 | Stop hook + agent memory（两文件） | 结构化 + 自由格式分离 |
| 流程文档 | orchestrator.md + skills/ 模板 | CLAUDE.md 保持瘦身 |
| JD 分析执行方式 | `run_jd_analysis.py`（Anthropic SDK 直调） | 对 cv_parsed 启用 prompt caching，同 group 批次最高省 90% cv_parsed token |
| 模型配置 | `config/model_config.json` + `sync_models.py` | 单一 source of truth；改模型只需改 JSON 后运行 sync 脚本 |

---

## 多用户架构

server.py 以全局变量 `_current_user`（默认 `leon`）管理当前活跃用户（切换时更新）。  
所有数据读写均经由 `_user_dir(uid)` / `get_output_dir(uid)` 等路径函数隔离。

**per-request uid 覆盖**：`do_GET` / `do_POST` 优先读取请求的 `?uid=` 查询参数，  
不存在时回退到 `_current_user`。前端对所有核心 API 调用均附带 `?uid=` 参数，  
避免用户切换与正在进行的请求发生竞态。

**搜索日志隔离**：`_search_logs: dict[str, list]`（per-uid），  
`GET /api/search-log?uid=` 只消费对应用户的日志，不跨用户混淆。

**用户注册表**：`users.json`（项目根目录），格式：`[{"id": "leon", "name": "Leon"}, ...]`

**用户切换**：`POST /api/switch-user { uid }` → 更新 `_current_user`；若搜索进行中返回 409。

**并发锁**：`_user_lock`（用户切换）、`_write_lock`（config/JD 文件写入）、`_search_lock`（子进程管理）、`_jobs_cache_lock`（缓存读写）。

### config.json schema（顶层字段）

```json
{
  "job_search": {
    "keyword_groups":         [...],
    "max_display":            30,
    "min_score_for_analysis": 20,
    "score_threshold_warn":   30,
    "location":               "Germany",
    "date_range_days":        14,
    "max_jobs_per_keyword":   1
  },
  "stepstone": {
    "enabled":     false,
    "server_url":  "http://localhost:8765"
  },
  "auto_default_answers": true,
  "skill_taxonomy": {},
  "cv_language": "English",
  "preferences": {
    "preferred_level":                "entry, junior, associated, experienced",
    "preferred_locations":            ["Germany", "Remote"],
    "preferred_work_mode":            ["hybrid", "remote"],
    "salary_expectation_eur_monthly": 3000,
    "preferred_domains":              [],
    "language_skills":                ["chinese", "japanese"]
  }
}
```

> `stepstone.enabled`：是否在 Phase 2B 中触发 Stepstone 搜索（默认 `false`）。  
> `auto_default_answers`：是否在 Phase 2F 中自动为 score ≥ 70 的职缺生成面试答案（默认 `true`）。  
> `cv_language`：CV 与 Cover Letter 的输出语言（默认 `"English"`；当前仅作元数据，agents 默认产出英文）。  
> `preferences.language_skills`：用户会说的非 EN/DE 语言列表（小写），用于：① jd-analyzer 动态检测 `mentioned_<lang>` 字段；② decision_score 语言优势加成（每匹配一门 +8，上限 +15）；③ Phase 2 自动创建对应语言搜索组（如 `group-spanish-lang`）。

**keyword_groups 搜索语言支持**：`primary_keywords` 和 `job_family` 的子 key 可为任意语言代码（`en`、`de`、`es`、`it` 等），`run_phase2_search.py` 动态迭代所有 key，不限于 EN/DE。

**skill_taxonomy 继承规则**：`config/global_taxonomy.json` 为全局基准（所有用户共享）；用户 `config.json` 中的 `skill_taxonomy` 在全局基础上追加（同类别 key 合并去重）。Amy 等新用户 `skill_taxonomy` 为空时自动继承全局分类词典，无需手动复制。

**语言搜索组自动同步**（Phase 2 步骤 -1）：Orchestrator 在搜索前检查 `language_skills`，自动为每种语言创建对应搜索组（如 `group-japanese-lang`）写入 config.json，附加 `"_auto_generated": true`；已存在的组不覆盖，用户可手动调整或删除。

**新用户创建**：`POST /api/create-user` → 在 `users/{uid}/` 下建立 `output/`、`my_cv/`，创建模板 `config.json`，并创建 `scripts/` symlink 和 `graphify-out/` symlink。

---

## 文件结构

> 项目根目录：`D:\JobIt\1_generate_linkedin_cv\`（2026-06 扁平化，消除原 GitHub 下载产生的双层嵌套）

```
/                                       ← 项目根目录
  .claude/                              ← Claude Code 配置（唯一）
    agents/                             ← 11 个 subagent（Orchestrator、cv-writer 等）
    skills/                             ← 7 个 skill（theme-factory、eval-criteria 等）
    hooks/                              ← validate-cv.py（CV 写入拦截）、notify.sh
    agent-memory/                       ← subagent 持久记忆（cv-parser、cv-writer、progress-writer）
    settings.json / settings.local.json ← 权限白名单
  config/
    ats_field_map.yml                   ← ATS 字段映射表
    global_taxonomy.json                ← 全局技能分类词典（所有用户共享基准）
    model_config.json                   ← 所有 Claude 模型 ID（agent + server endpoint），source of truth
  dashboard/
    index.html                          ← gen_job_tracker_html.py 生成的 live HTML（server 直接服务）
    logo.png
  graphify-out/                         ← 知识图谱输出（只读参考）
  memory/
    progress.json                       ← 结构化状态快照（session 结束覆盖写入）
    notes.md                            ← 自由格式 session 笔记（追加，最新在上）
  scripts/
    templates/
      index.html                        ← dashboard 的 Jinja2 模板源
    tests/
      test_core.py                      ← 核心逻辑单元测试
    archive/                            ← 已归档旧脚本（不参与主流程）
    server.py                           ← HTTP 服务器入口（port 8080）；路由分发到下列模块
    server_jobs.py                      ← 职缺数据、CV 文件、group-stats、JD 分析等
    server_search.py                    ← 搜索子进程管理、SSE 日志流
    server_ai.py                        ← LLM 相关端点（generate-job-family 等）
    server_users.py                     ← 用户注册表、group CRUD、偏好设置
    gen_job_tracker_html.py             ← 生成 dashboard/index.html
    gen_cover_letter.py                 ← cover_letter_draft.md → cover_letter.pdf + cover_letter.docx
    generate_summary.py                 ← 生成 job_summary.md
    linkedin_search.py                  ← LinkedIn MCP 搜索封装
    run_phase2_search.py                ← Phase 2 主搜索流程
    run_phase2_search_stepstone.py      ← Stepstone 搜索变体
    run_jd_analysis.py                  ← JD 精确分析（Anthropic SDK 直调，cv_parsed prompt caching）
    sync_models.py                      ← 将 model_config.json 同步到各 agent frontmatter
    search_state.py                     ← 去重状态管理、batch 索引
    refetch_details.py                  ← 补抓 LinkedIn JD 详情
    refetch_stepstone_details.py        ← 补抓 Stepstone JD 详情
    parse_cv.py                         ← CV PDF → JSON 解析
    common.py                           ← 共享工具函数
    check.py                            ← 启动 sanity check
  users/
    {uid}/                              ← 每用户独立工作区
      config.json                       ← keyword groups + skill_taxonomy + job_search 参数
      my_cv/                            ← CV PDF 文件（.gitignore 排除）
      memory/                           ← 用户级备用记忆（.gitignore 排除）
      interview-prep/
        story-bank.md                   ← 故事库（面试准备素材）
      output/                           ← 所有输出（.gitignore 排除）
        temp/                           ← 中间文件（session 内临时）
          _phase2_temp.json             LinkedIn 原始搜索结果
          _phase2_temp_stepstone.json   Stepstone 原始搜索结果
          _phase2_temp_merged.json      合并后待保存
          raw_results_<batch_id>.json   已保存批次数据
        search_history.json             ← 去重状态 + batch 索引（持久）
        cv_parsed_<group_id>.json       ← CV 解析缓存（持久）
        job_summary.md                  ← 职缺汇总表（持久）
        <group_id>_<company>_<title>_<YYYYMMDD>/
          jd_text.txt                ← Orchestrator 写入原始 JD（run_jd_analysis.py 读取）
          jd_analysis.json
          cv_draft.md / cv_ats.pdf / cv_styled.pdf   ← --dual 同时生成双版本
          cover_letter_draft.md / cover_letter.pdf / cover_letter.docx
          cv_changes.md / eval_report.json
  users.json                            ← 全用户注册表（id + name）
  CLAUDE.md                             ← 启动指引与执行流程（agent 主入口）
  SPEC.md                               ← 本文件（功能规格与架构决策）
  UI.md                                 ← Web UI 视觉设计规格
  PLAN_enhance.md                       ← 技术改进路线图（单元测试、重构计划）
  PLAN-upgrade.md                       ← 产品升级规划（P0–P3 功能迭代）
  setup.ps1                             ← Windows 环境初始化（从项目根运行）
  setup.sh                              ← macOS/Linux 环境初始化（从项目根运行）
  ARCHIVE_pre_reorganize/               ← 历史归档（重组前文件）
  ARCHIVE_pre_multiuser/                ← 历史归档（多用户改造前文件）
  1_generate_linux_cv/                  ← 独立 Linux CV 项目（不共享配置）
```

---

## 已知限制

- LinkedIn ToS 禁止自动化投递，本专案只做搜索和材料生成
- linkedin-scraper-mcp session 可能过期，需定期重新登录
- Stepstone MCP server 需每次 Phase 2 前手动启动（无自动守护进程）
- PyMuPDF 对扫描版 PDF 效果较差，建议使用文字版 CV
- match_score_preview 是关键词重叠估算，不代表实际匹配度
- fpdf2 不支持 HTML/CSS 渲染，PDF 样式需通过 fpdf2 原生 API 实现；若需复杂主题需换库
- 多用户切换为全局单一进程（_current_user），搜索进行中不可切换用户

---

## Web UI — 功能规格

> Web UI 由 `scripts/gen_job_tracker_html.py` 生成静态模板，配合 `scripts/server.py` 运行于 `http://localhost:8080`。
> 视觉设计规格见 `UI.md`。

### 架构总览

```
运行方式：python scripts/server.py → 自动打开 http://localhost:8080

服务端点（已实现）：
  GET  /                        → 返回 index.html（由 gen_job_tracker_html.py 生成）
  GET  /api/jobs                → 解析 job_summary.md + 合并所有 jd_analysis.json → JSON 数组
  GET  /api/status              → { "mtime": float }，供客户端轮询检测 job_summary.md 变更
  GET  /api/cvfiles             → 列出 my_cv/ 目录下的 PDF 文件名
  GET  /api/cvfile?name=<file>  → 返回 my_cv/<file> 的 PDF 字节（路径验证：禁止 ..）
  GET  /api/group-stats         → 计算每个 group 的统计数据（均分、缺失技能、最近搜索、搜索时间轴）
  POST /api/record              → { jd_path, record } → 写入 application_record 到 jd_analysis.json
  POST /api/note                → { jd_path, note } → 写入 user_note 字段到 jd_analysis.json
  POST /api/group-delete        → { group_id } → 从 config.json 删除该 group
  POST /api/group-dup           → { group_id } → 在 config.json 中复制该 group（加 -copy 后缀）
  GET  /api/search-status       → { "running": bool }，轮询搜索子进程状态
  GET  /api/search-log          → SSE 实时流，输出搜索子进程的 stdout（ANSI stripped）
  GET  /api/search-analysis     → 全批次关键词分析（每 keyword 的 fetch/seen/new 数、source 分布）
  GET  /api/users               → { "users": [{id, name}], "current": uid }
  GET  /api/taxonomy            → 从 config.json 读取 skill_taxonomy
  POST /api/search              → { group_id? } → 启动搜索子进程（claude -p 搜索职缺）
  POST /api/switch-user         → { uid } → 切换当前用户（搜索中时返回 409）
  POST /api/create-user         → { uid, name } → 创建新用户工作区并注册到 users.json
  POST /api/group-save          → { group } → 新增 group 到 config.json（group_id 重复返回 409）
  POST /api/group-update        → { group } → 按 group_id 更新已有 group（group_id 不可改；不存在返回 404）
  POST /api/generate-job-family → { group_id } → 调用 Claude LLM 生成 EN+DE job titles
  POST /api/save-job-family     → { group_id, job_family } → 写入 job_family 到 config.json
  GET  /api/preferences         → 读取 config.json 中的偏好字段（跨多个顶层路径汇总）
  POST /api/preferences         → 写回偏好字段到 config.json 对应路径
  POST /api/refresh-summary     → 重新扫描 output/ 下所有 jd_analysis.json，原地重写 job_summary.md 并清除 jobs 缓存
                                   (双路径设计：Orchestrator 调 CLI generate_summary.py；UI 调本端点；server 未运行时 CLI 仍可独立执行)
```

### 页面路由

| 路由 | 入口 | 实现状态 | 说明 |
|------|------|----------|------|
| Dashboard（默认） | 导航栏"Job Tracker" | ✅ 已实现 | Page 1：职缺汇总表 |
| Job Detail | 点击任意 Score badge 或职位行 | ✅ 已实现 | Page 2：单职缺详情 |
| My CVs | 导航栏"My CVs" | ✅ 已实现 | Page 4：CV-group 管理 + Settings Tab |
| Add / Edit Group | Page 4 右上角 Add Group / 卡片 Edit 按钮 | ✅ 已实现 | 右侧 Drawer（不新开页面） |


### 数据来源

| 页面 | 读取来源 | 写入来源 |
|------|----------|----------|
| Page 1 Dashboard | `users/{uid}/output/job_summary.md` + `users/{uid}/output/*/jd_analysis.json` | `users/{uid}/output/*/jd_analysis.json`（application_record, user_note） |
| Page 2 Job Detail | `users/{uid}/output/<dir>/jd_analysis.json`（via `/api/jobs`） | `users/{uid}/output/<dir>/jd_analysis.json`（user_note） |
| Page 3 Add Group | — | `users/{uid}/config.json` |
| Page 4 My CVs | `users/{uid}/config.json` | `users/{uid}/config.json` |

---

### Page 1 — Job Summary Dashboard

**功能：** 所有已分析职缺的汇总表，支持过滤、搜索、标记投递状态。

#### 数据字段（来自 `/api/jobs`）

| 列名 | 字段 | 来源 | 说明 |
|------|------|------|------|
| # | 行序号 | 前端生成 | |
| Score | `score` | `job_summary.md` | 可排序（↑↓）；可点击 → Page 2；色彩阈值见下 |
| Group | `group_label` | `config.json`（`parse_jobs()` 按 group_id 查找，随 `/api/jobs` 返回） | 取自 group_label，显示时去除 `group-` 前缀 |
| Source | `source` | `job_summary.md` | LinkedIn / Stepstone；含超链接 URL，点击直达职缺页面 |
| Company | `company` | `job_summary.md` | 可排序 |
| Title | `title` | `job_summary.md` | 可排序；有材料时显示 📄 Ready 徽章 |
| Size | `size` | `jd_analysis.json` | 优先 jd_analysis 中的值 |
| Location | `company_info.location` | `jd_analysis.json` | ✅ 已实现；server.py 读取 `company_info.location` |
| Recommended Emphasis | `recommended_emphasis_raw` | `job_summary.md` | 3 行截断，列点显示，hover 显示全文 |
| Missing Skills | `missing_skills_raw` | `job_summary.md` | 按 6 分类渲染（Tools / Academic / Certs / Languages / Domain / Other），每类前有 category label，无高度截断 |
| Analyzed | `analyzed` | `job_summary.md` | 日期，可排序 |
| Record | `application_record` | `jd_analysis.json` | 4-state select；详见 Application Record 逻辑 |
| Multiple Source | `remark` | 服务端推断 | 跨源重复时显示"multiple source"；`min-width:110px` |
| Notes | `user_note` | `jd_analysis.json` | 📝 图标：有备注时琥珀色，默认显示前20字，hover 显示前 80 字 |

**服务端新增字段（`/api/jobs` 返回）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `materials_ready` | bool | 对应目录下 `cv_ats.pdf` 是否存在（`--dual` 生成两版 CV：`cv_ats.pdf` + `cv_styled.pdf`） |
| `user_note` | string | 用户备注，来自 `jd_analysis.json['user_note']` |
| `group_label` | string | 来自 `config.json`，`parse_jobs()` 按 `group_id` 查找 |
| `location` | string | 来自 `jd_analysis.json['company_info']['location']`，无值时为空字符串 |

#### Score 阈值逻辑

| 分数区间 | 分类 | 用于 Stats 卡片 |
|----------|------|----------------|
| ≥ 70 | High Match | stat-green |
| 45 – 69 | Good Match | stat-yellow |
| 30 – 44 | Moderate | stat-orange |
| < 30 | Low Match | （不计入 stats） |

#### Stats 卡片计算逻辑（客户端）

```
// Stats 联动当前过滤结果，使用 filteredJobs（过滤后数组）
src = filteredJobs（若为空则 fallback 到 JOBS）
TRACKING = {'applied', 'interview', 'success'}  // success 为向后兼容保留

total = src.length
green.total    = src.filter(j => j.score >= 70).length
green.tracking = 上述中 application_record ∈ TRACKING 的数量
显示格式：total 数字，sub-label = "N applied"（= tracking 数量）
同理适用 yellow（45–69）、orange（30–44）
```

#### 过滤器逻辑

- **Group 标签栏**：从 JOBS 数组动态提取所有唯一 group，前端显示group_label，显示时去除 `group-` 前缀，`All` 为默认
- **Source 标签栏**：固定 All / LinkedIn / Stepstone
- **Score 滑杆**：`min_score` 过滤，范围 0–100，默认 0；滑动时 150ms debounce
- **全文搜索框**：对 company + title + group + source 做 `includes()` 匹配
- **Recent date 滑杆**：`recent_date` 过滤，范围 0–60，默认 14
- **Application Record 下拉**：位于 Date 滑杆右侧；选项：All Status / — Track（未跟踪）/ Applied / Interview / Invalid；与其余 4 个过滤器 AND 组合
- 五个过滤器 AND 组合
- **Filter Persistence**：过滤状态写入 `localStorage` key `'jt_filter'`（activeGroup/activeSource/minScore/minDate/filterRecord/searchQuery），页面刷新后恢复
- **Empty State**：过滤无结果时显示 "No jobs match" + Reset Filters 按钮

#### 列排序（Column Sorting）

- 可排序列：Score（默认降序）、Company、Title、Analyzed
- 点击列头：升/降序切换；激活列显示 `↑`/`↓`，其余列显示淡色 `⇅`
- 排序在过滤后执行，不影响过滤逻辑
- 状态：`sortCol = 'score'`，`sortDir = 'desc'`（页面初始状态）

#### Skill Gap 面板

- 位置：过滤栏下方，表格上方，默认折叠
- 触发：点击过滤栏右侧"Skill Gap"按钮展开/收起
- 内容：统计当前 `filteredJobs` 中 `missing_skills` 词频，Top 20（频次 > 1 才显示），字体与词频成比例，范围 11–25px
- 按 6 分类分组显示（Tools & Technical / Academic Background / Domain Knowledge / Languages / Certificates / Soft & Other），每组有 section 标题
- 每个 pill 右上角显示频次数字徽章（灰色圆形 badge）
- 纯前端；`applyFilters()` 执行后调用 `updateSkillGap()`（仅在面板展开时更新）

#### Export CSV

- 触发：过滤栏右侧"CSV"按钮
- 导出当前 `filteredJobs` 为 UTF-8 BOM CSV（兼容 Excel）
- 字段：company, title, score, source, group, url, analyzed, application_record

#### Loading 按钮行为

1. 根据当前 Group label × Source 选择生成指令文字（见指令映射表）
2. 点击后：`navigator.clipboard.writeText(cmd)` 通过api将指令文字回传到程序，触发claude code运行指令，如果api回传失败，降级处理复制到剪贴板
3. 按钮变为 "⏳ Loading…"  
4. 开始每 5 秒轮询 `/api/status`，记录 baseline mtime
5. 检测到 mtime 变化 → 重新 `fetch('/api/jobs')` → 刷新全表 → 重置按钮

#### Loading 按钮指令映射

按钮显示文字用 group_label，剪贴板写入 group_id：
- display（按钮文字）：`搜索职缺 Marketing Analytics`
- clipboard（实际复制）：`搜索职缺 group-da`

| Group \ Source | All | LinkedIn | Stepstone |
|----------------|-----|----------|-----------|
| All | 搜索职缺 | 搜索LinkedIn职缺 | 搜索Stepstone职缺 |
| group-X | 搜索职缺 group-X | 搜索LinkedIn职缺 group-X | 搜索Stepstone职缺 group-X |

#### Application Record 写回逻辑

4 种状态（`null` = 未跟踪）：

| 值 | 标签 | 颜色 |
|----|------|------|
| `null` | — Track | 灰色默认 |
| `applied` | Applied | 蓝色 `#EFF6FF / #1D4ED8` |
| `interview` | Interview | 紫色 `#EDE9FE / #5B21B6` |
| `invalid` | Invalid | 浅灰 `#F3F4F6 / #6B7280` |

```
UI：<select class="rec-select"> 4 个 option（不含 Rejected），data-state 属性驱动 CSS 颜色
用户选择 → POST /api/record { jd_path, record: value|null }
成功后：更新本地 JOBS 数组 + 刷新 Stats 卡片 + 更新 select 的 data-state
向后兼容：legacy value "success" 在 select 中显示为 "Applied"
legacy value "rejected" 回退显示为 "— Track"（select 找不到匹配项时的浏览器默认行为）
```

#### 跨源重复检测逻辑（服务端）

```python
# 分组依据：(company.strip().lower(), title.strip().lower()[:60])
# 若同一组内同时存在 source 含"linkedin"和"stepstone"的记录
# → remark = "multiple source"
```

---

### Page 2 — Job Detail

**入口：** 点击 Page 1 中任意职缺行（Score badge 或行主体，排除链接和 Record 按钮区域）

**技术实现：** 事件委托（`tbody` 监听 click，通过 `data-row-idx` + `tbody._slice[idx]` 取 job 对象），不依赖 onclick 属性。

#### 数据字段（来自 jd_analysis.json，已由服务端合并入 job 对象）

| 区块 | 字段 |
|------|------|
| 头部 | `company`, `title`, `size`, `source`, `url` |
| 分数仪表盘 | `score` |
| 核心职责 | `core_responsibilities[]` |
| 文化关键词 | `culture_keywords[]` |
| 已匹配技能 | `matched_skills[]` | 按 6 分类渲染（Matched Tools & Technical / Academic Background / Certificates / Languages / Domain Knowledge / Soft & Other），每类前有 category label |
| 缺失技能 | `missing_skills[]` | 同上 6 分类，category label 样式相同，图标色 `#EF4444` |
| 加分技能 | `bonus_skills[]` |
| 硬性要求 | `required_skills[]` |
| 推荐侧重点 | `recommended_emphasis[]`（fallback：`recommended_emphasis_raw` 以分号分割） |
| 备注 | `user_note`（textarea，onblur 自动保存 → `POST /api/note`） |

#### 页面底部固定操作栏

| 按钮 | 行为 |
|------|------|
| Apply Now → | `<a href="{url}" target="_blank">` |
| Back to List | `showPage('dashboard')`，隐藏 footer |

---

### Page 3 — Add / Edit Group Drawer

**功能：** 新建或编辑 keyword group，写入 `config.json`。
> **状态：✅ 已实现。** 以右侧 Drawer 形式实现（不新开页面）。
> 入口：Page 4 右上角 "Add Group" 按钮 / 每个 group 卡片的 "Edit" 按钮。

#### Drawer 字段 → config.json 映射

| 字段 | config.json 路径 | Add 模式 | Edit 模式 |
|------|-----------------|----------|-----------|
| Group ID | `keyword_groups[].group_id` | 从 Label 自动派生，只读 | 显示原值，锁定不可改 |
| Group Label | `keyword_groups[].group_label` | 必填 | 可编辑 |
| CV File | `keyword_groups[].cv_file` | 从 `my_cv/` 下拉选择 | 可更换 |
| Min Score for Analysis | `keyword_groups[].min_score_for_analysis` | 默认 20（slider） | 可编辑 |
| Primary Keywords EN | `keyword_groups[].primary_keywords.en[]` | 每行一条 | 可编辑 |
| Primary Keywords DE | `keyword_groups[].primary_keywords.de[]` | 可选 | 可编辑 |
| Job Family Titles | `keyword_groups[].job_family[]` | 可选，支持 AI Generate | 可编辑 |

**AI Generate**：仅在 Edit 模式下显示（Add 模式隐藏）；调用 `POST /api/generate-job-family`，需 group 已存在于 config.json。

**保存端点：**
- Add 模式 → `POST /api/group-save`（group_id 重复返回 409）
- Edit 模式 → `POST /api/group-update`（group_id 不存在返回 404；原有字段如 `_auto_generated` 以 merge 方式保留）

---

### Page 4 — My CVs (Group Mapping List)
> **状态：✅ 已实现。** 数据由 `/api/group-stats` 提供，页面动态渲染卡片网格。
**功能：** 管理所有 CV-group 映射，展示每组的 CV 文件、关键词、覆盖度及缺失技能摘要；含 Settings Tab 管理用户偏好。

#### Tab 结构

| Tab | 内容 |
|-----|------|
| Groups（默认） | Stats Bar + Skill Gap 面板 + Group 卡片网格 |
| Settings | 用户偏好表单（见下方） |

#### 页面顶部 Stats Bar（客户端计算）

| 卡片 | 计算逻辑 |
|------|----------|
| Total Groups | `groups.length` |
| Assigned CVs | `new Set(groups.map(g => g.cv_file)).size`（统计已分配给 group 的不重复 CV 数） |
| Active Searches | `groups.filter(g => g.is_active).length`（is_active = 最近 7 天内有搜索记录） |
| Last Updated | 所有 group 中最新的 `last_search` 日期 |

#### `/api/group-stats` 服务端计算逻辑（per group）

```python
# 扫描 users/{uid}/output/，找出以 group_id + "_" 开头的所有文件夹
# 读取每个文件夹内的 jd_analysis.json：
#   - 收集 score（新 schema）或 match_score（旧 schema 兼容）→ 计算均值
#   - 收集所有 missing_skills → Counter 取 top 6 高频词
#   - 收集所有 matched_skills → Counter 取 top 6 高频词
#   - 取最新 jd_analysis.json 的 mtime → 格式化为 "Apr 17"
#   - is_active = (now - latest_mtime) < 7 * 86400

返回字段：group_id, group_label, cv_file, primary_keywords,
          job_family, job_count, avg_score,
          top_missing_skills, top_matched_skills,
          last_search, is_active, search_timeline[]
search_timeline 每条：{date, new_net, fetched_total, sources}
  new_net = new_total - hidden_low_score - skipped_duplicate
```

#### 卡片区块结构 → config.json 映射

| 区块 | 内容 | 来源 |
|------|------|------|
| Header | 彩色 icon（initials）+ Group Label + Group ID tag + Status badge + Avg Score badge | `/api/group-stats` |
| Section A | CV 文件名 + 预览图标 + 下载图标 | `cv_file` |                                                                                                                             
| Section B | 位于左侧，与 Section C 并列展示；Primary Keywords EN（蓝色 chip）+ Job Family EN（蓝色 chip）；前 6 个显示，超出折叠为 "+N more" | `primary_keywords.en`，`job_family.en` |
| Section C | 位于右侧，与 Section B 并列展示；Primary Keywords DE（紫色 chip）+ Job Family DE（紫色 chip）；前 6 个显示，超出折叠为 "+N more" | `primary_keywords.de`，`job_family.de` |
| Section D | 高频缺失技能（黄色 miss-tag）；按 6 分类排序并加 category label（Tools / Academic / Certs / Languages / Domain / Other） | `top_missing_skills` |
| Section E | 高频已匹配技能（绿色 match-tag）；同 Section D 分类逻辑 | `top_matched_skills` |
| Footer | 最近搜索日期 + 职缺数 / 操作按钮 | 计算值 |

**卡片排序：** 按 `avg_score` 从高到低排列（前端排序，`sort((a,b) => (b.avg_score??-1)-(a.avg_score??-1))`）

#### 卡片操作（实现状态）

| 操作 | 行为 | 状态 |
|------|------|------|
| Search Jobs | 复制 `搜索职缺 group-X` 到剪贴板 → 跳转 Dashboard，预选该 group → 进入 Loading 轮询状态 | ✅ 已实现 |
| Edit | 打开右侧 Drawer，预填该 group 数据；group_id 锁定只读 | ✅ 已实现 |
| ··· → Duplicate | `POST /api/group-dup` → 复制 group，新 group_id = 原 id + `-copy`；重复时加 `-2`/`-3` | ✅ 已实现 |
| ··· → Delete | `POST /api/group-delete` → 从 config.json 删除；显示 confirm 对话框 | ✅ 已实现 |
#### Groups 数据来源

Groups 由各用户的 `config.json` 动态加载，通过 `/api/group-stats` 返回。  
切换用户后，Page 4 自动重新渲染该用户的 group 卡片。  
初始 groups 可在 `users/{uid}/config.json` 的 `keyword_groups` 数组中配置。

#### 搜索历史时间轴（Search Timeline）✅ 已实现
 - Page 4 My CVs 卡片 Footer：展示该 group 最近 3 次搜索记录
 - 每条格式：`<date> · <new_net> new · <fetched_total> fetched (<sources>)`
   - `new_net = new_total - hidden_low_score - skipped_duplicate`
 - 服务端：读 `users/{uid}/output/search_history.json`，按 `batch.group_id` 过滤，按 date 降序取最近 3 条
 - 注：旧格式 batch（无 `group_id` 字段）不显示，新搜索后自动累积

#### Settings Tab ✅ 已实现

由 `GET /api/preferences` 加载，`POST /api/preferences` 保存。跨 config.json 多个顶层路径读写。

| 区块 | 字段 | config.json 路径 |
|------|------|-----------------|
| Search Settings | Location（逗号分隔） | `preferences.preferred_locations[]` |
| | Date Range（slider, 1–30 days） | `job_search.date_range_days` |
| | Max Jobs Displayed（number） | `job_search.max_display` |
| Work Preferences | Work Mode（hybrid / remote / onsite，多选） | `preferences.preferred_work_mode[]` |
| | Preferred Level（pill 多选：entry/junior/associated/experienced/senior/lead/manager） | `preferences.preferred_level`（逗号分隔字符串） |
| | Salary Expectation（€/mo） | `preferences.salary_expectation_eur_monthly` |
| | Preferred Domains（逗号分隔） | `preferences.preferred_domains[]` |
| Language Skills | 9 种语言 checkbox（Chinese/Japanese/Spanish/Italian/French/Korean/Arabic/Portuguese/Persian） | `preferences.language_skills[]` |
| Job Sources & Automation | Stepstone toggle | `stepstone.enabled` |
| | Auto-generate Interview Answers toggle | `auto_default_answers` |

**设计决策：**
- 取消勾选 language_skills 不自动删除已有的语言搜索组（如 `group-chinese-lang`），用户在 Groups tab 手动管理
- `preferred_level` 在 config.json 存储为逗号分隔字符串（兼容 jd-analyzer prompt 注入），UI 以 pill 多选方式呈现