# Project Spec — LinkedIn CV Agent

> Agent 只读，不得修改。用户修改需求时在此文件追加，不覆盖原有内容。

---

## 核心目标

自动搜索 LinkedIn 最近 2 周的职缺，针对每个职缺用对应版本的 CV 生成定制材料，
经用户审核后输出最终 PDF。所有投递由用户手动完成。

---

## 功能需求

### 搜索
- 多 keyword group，每组绑定一份 CV（对应关系见 `config.json`）
- 每组关键词含 primary keywords + job family 扩展词
- 双语搜索：EN + DE
- 双源搜索：LinkedIn（uvx linkedin-scraper-mcp）+ Stepstone（本地 HTTP SSE server）
  - `搜索职缺`：同时搜索两源；`搜索LinkedIn职缺`：仅 LinkedIn；`搜索Stepstone职缺`：仅 Stepstone
  - Stepstone 职缺 ID 前缀 `st_`，与 LinkedIn 数字 ID 不冲突
  - Stepstone 需本地启动：`cd C:\tools\mcp-stepstone && python -m stepstone_http_server`
- 增量搜索：同天多批次自动续页，跨天重置 offset，保留去重历史
- 去重：job_id + 公司 + 职位三者完全相同才过滤；同公司不同职位保留
- 搜索结果按 match_score_preview 降序展示
- 搜索噪声过滤：自动过滤 company="Share/Save/Apply" 等 LinkedIn UI 残留，description < 150 字自动单次重试

### CV 与 group 对应
- 对应关系在 `config.json` 的 `keyword_groups[].cv_file` 定义（source of truth）
- 任何情况不得混用不同 group 的 CV
- Scale Up：将新 CV 放入 `my_cv/`，在 config.json 新增 group 对象即可

### 材料生成
- 每个职缺生成：定制 CV（Markdown + PDF）、Cover Letter（Markdown + PDF）
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
| PDF 生成 | weasyprint + markdown + theme-factory | 纯 Python，支持主题 |
| 搜索状态 | output/search_history.json | 可读，无需数据库 |
| 中间文件 | output/temp/raw_results_<batch_id>.json | 不用 /tmp，可调试；temp/ 隔离中间文件 |
| 预评分 vs 精确分 | 两阶段 | 预评分快速排序，精确分在 Phase 3A |
| Sub-agent 并行 | 最多 3 个 | 避免界面卡顿 |
| CV 验证 | PostToolUse hook | 100% 拦截，优于 CLAUDE.md 指令 |
| 进度记录 | Stop hook + agent memory（两文件） | 结构化 + 自由格式分离 |
| 流程文档 | orchestrator.md + skills/ 模板 | CLAUDE.md 保持瘦身 |

---

## 文件结构

```
output/
  temp/                          ← 所有中间文件
    _phase2_temp.json            LinkedIn 原始搜索结果
    _phase2_temp_stepstone.json  Stepstone 原始搜索结果
    _phase2_temp_merged.json     合并后待保存
    raw_results_<batch_id>.json  保存的批次数据
  search_history.json            去重状态 + batch 索引（持久）
  cv_parsed_<group_id>.json      CV 解析缓存（持久）
  job_summary.md                 汇总表（持久）
  <group_id>_<company>_<title>_<YYYYMMDD>/   每职缺输出文件夹
    jd_analysis.json
    cv_draft.md / cv_final.pdf
    cover_letter_draft.md / cover_letter_final.pdf
    cv_changes.md / eval_report.json
```

---

## 已知限制

- LinkedIn ToS 禁止自动化投递，本专案只做搜索和材料生成
- linkedin-scraper-mcp session 可能过期，需定期重新登录
- Stepstone MCP server 需每次 Phase 2 前手动启动（无自动守护进程）
- PyMuPDF 对扫描版 PDF 效果较差，建议使用文字版 CV
- match_score_preview 是关键词重叠估算，不代表实际匹配度
- theme-factory 需要单独安装（setup.sh 自动处理）

---

## Web UI — 功能规格

> Web UI 由 `scripts/gen_job_tracker_html.py` 生成静态模板，配合 `scripts/server.py` 运行于 `http://localhost:8080`。
> 视觉设计规格见 `UI.md`。

### 架构总览

```
运行方式：python scripts/server.py → 自动打开 http://localhost:8080

服务端点（已实现）：
  GET  /                        → 返回 C:/Users/Leon/Desktop/job_tracker/index.html
  GET  /api/jobs                → 解析 job_summary.md + 合并所有 jd_analysis.json → JSON 数组
  GET  /api/status              → { "mtime": float }，供客户端轮询检测 job_summary.md 变更
  GET  /api/cvfiles             → 列出 my_cv/ 目录下的 PDF 文件名
  GET  /api/cvfile?name=<file>  → 返回 my_cv/<file> 的 PDF 字节（路径验证：禁止 ..）
  GET  /api/group-stats         → 计算每个 group 的统计数据（均分、缺失技能、最近搜索、搜索时间轴）
  POST /api/record              → { jd_path, record } → 写入 application_record 到 jd_analysis.json
  POST /api/note                → { jd_path, note } → 写入 user_note 字段到 jd_analysis.json
  POST /api/group-delete        → { group_id } → 从 config.json 删除该 group
  POST /api/group-dup           → { group_id } → 在 config.json 中复制该 group（加 -copy 后缀）
```

### 页面路由

| 路由 | 入口 | 实现状态 | 说明 |
|------|------|----------|------|
| Dashboard（默认） | 导航栏"Job Tracker" | ✅ 已实现 | Page 1：职缺汇总表 |
| Job Detail | 点击任意 Score badge 或职位行 | ✅ 已实现 | Page 2：单职缺详情 |
| My CVs | 导航栏"My CVs" | ✅ 已实现 | Page 4：CV-group 管理 |
| Add Search Group | 导航栏"+ Add Group"（已禁用） | 🚧 待实现 | Page 3：新增搜索组表单 |


### 数据来源

| 页面 | 读取来源 | 写入来源 |
|------|----------|----------|
| Page 1 Dashboard | `output/job_summary.md` + `output/*/jd_analysis.json` | `output/*/jd_analysis.json`（application_record, user_note） |
| Page 2 Job Detail | `output/<dir>/jd_analysis.json`（via `/api/jobs`） | `output/<dir>/jd_analysis.json`（user_note） |
| Page 3 Add Group | — | `config.json` |
| Page 4 My CVs | `config.json` | `config.json` |

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
| `materials_ready` | bool | 对应目录下 `cv_final.pdf` 是否存在 |
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

### Page 3 — Add Job Search Group

**功能：** 新建 keyword group，写入 `config.json`。
> **状态：🚧 待实现。** 导航栏"+ Add Group"按钮当前禁用（tooltip "Coming soon"）。
> Page 4 的"Edit"按钮同样禁用，待本页实现后启用。
#### 表单字段 → config.json 映射

| 表单字段 | config.json 路径 | 默认值 |
|----------|-----------------|--------|
| Group ID | `keyword_groups[].group_id` | — |
| Group Label | `keyword_groups[].group_label` | — |
| CV File | `keyword_groups[].cv_file`（从 `my_cv/` 下拉选择） | — |
| Primary Keywords EN | `keyword_groups[].primary_keywords.en[]` | — |
| Primary Keywords DE | `keyword_groups[].primary_keywords.de[]` | — |
| Job Family EN | `keyword_groups[].job_family.en[]` | — |
| Job Family DE | `keyword_groups[].job_family.de[]` | — |
| Location | `job_search.location` | Germany |
| Date Range Days | `job_search.date_range_days` | 14 |
| Max Jobs Per Keyword | `job_search.max_jobs_per_keyword` | 1 |
| Score Threshold Warning | `job_search.score_threshold_warn` | 30 |

#### 规划操作行为

| 按钮 | 行为 |
|------|------|
| Save & Search Now | 写入 config.json → 复制搜索指令到剪贴板 → 跳转 Dashboard 并开始轮询 |
| Save Draft | 仅写入 config.json，不触发搜索 |
| Cancel | 返回上一页，丢弃未保存内容 |

#### 需要新增的服务端点（待实现）

```
POST /api/group-save   → { group } → 新增或更新 config.json 中的 group 对象
```
---

### Page 4 — My CVs (Group Mapping List)
> **状态：✅ 已实现。** 数据由 `/api/group-stats` 提供，页面动态渲染卡片网格。
**功能：** 管理所有 CV-group 映射，展示每组的 CV 文件、关键词、覆盖度及缺失技能摘要。

#### 页面顶部 Stats Bar（客户端计算）

| 卡片 | 计算逻辑 |
|------|----------|
| Total Groups | `groups.length` |
| Assigned CVs | `new Set(groups.map(g => g.cv_file)).size`（统计已分配给 group 的不重复 CV 数） |
| Active Searches | `groups.filter(g => g.is_active).length`（is_active = 最近 7 天内有搜索记录） |
| Last Updated | 所有 group 中最新的 `last_search` 日期 |

#### `/api/group-stats` 服务端计算逻辑（per group）

```python
# 扫描 OUTPUT_DIR，找出以 group_id + "_" 开头的所有文件夹
# 读取每个文件夹内的 jd_analysis.json：
#   - 收集 match_score → 计算均值
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
| Edit | 打开 Page 3 表单，预填该 group 数据 | 🚧 禁用（Page 3 待实现） |
| ··· → Duplicate | `POST /api/group-dup` → 复制 group，新 group_id = 原 id + `-copy`；重复时加 `-2`/`-3` | ✅ 已实现 |
| ··· → Delete | `POST /api/group-delete` → 从 config.json 删除；显示 confirm 对话框 | ✅ 已实现 
#### 当前 Groups（来自 config.json，可随时扩充）

| Group ID | Label | CV File | 状态 |
|----------|-------|---------|------|
| `group-da` | Marketing Analytics | `my_cv_da.pdf` | Active（24 jobs） |
| `group-pmo` | Project Management Office | `my_cv_pmo.pdf` | Active（27 jobs） |
| `group-pdm` | Product Marketing Management | `my_cv_pdm.pdf` | Active（46 jobs） |
| `group-internal-marketing` | Internal Marketing & Communications | `my_cv_img.pdf` | Draft（无搜索结果） |
| `group-event-management` | Event Management | `my_cv_em.pdf` | Draft（无搜索结果） |

#### 搜索历史时间轴（Search Timeline）✅ 已实现
 - Page 4 My CVs 卡片 Footer：展示该 group 最近 3 次搜索记录
 - 每条格式：`<date> · <new_net> new · <fetched_total> fetched (<sources>)`
   - `new_net = new_total - hidden_low_score - skipped_duplicate`
 - 服务端：读 `output/search_history.json`，按 `batch.group_id` 过滤，按 date 降序取最近 3 条
 - 注：旧格式 batch（无 `group_id` 字段）不显示，新搜索后自动累积