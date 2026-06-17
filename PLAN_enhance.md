# JobIt 增强计划 — CTO 架构评审

> 基于 CLAUDE.md / SPEC.md / Orchestrator.md / graphify-out / scripts/ 全量审计
> 评审日期：2026-06-16

---

## 0. 前言：整体判断

JobIt 是一个工程完成度相当高的多用户 AI 求职助手，核心流程（Phase 1-4）逻辑清晰，MCP 集成与原子写入等关键路径设计合理。主要问题集中在三类：

1. **历史积累负债** — 开发过程遗留的调试脚本、一次性迁移脚本、硬编码文件占据了 scripts/ 的约 40%，形成噪音。
2. **可扩展性盲点** — `server.py`（1821 行）单体化，全局状态在多用户并发下是 P0 风险（见上一轮分析），部分流程依赖手动操作。
3. **规格与实现漂移** — SPEC.md 与 Orchestrator.md 在若干细节上已不一致（双 PDF 输出、.docx、Page 3 待实现），说明规格文档未随实现同步更新。

---

## 1. 技术债（Technical Debt）

### 1.1 死代码 / 硬编码文件

| 文件 | 问题 | 风险 | 建议 |
|------|------|------|------|
| `scripts/parse_cv.py` | 15 行，路径硬编码，功能已由 cv-parser agent 替代 | 低 | 删除 |
| `scripts/parse_cv_em.py` | 172 行，硬编码候选人 "Boru Lai"，不可复用 | 低 | 删除 |
| `scripts/_patch_cv_parsed.py` | 硬编码 Leon 的工作经历公司名，一次性 patch | 低 | 删除（已应用） |
| `scripts/_find_unscored_pdm.py` | 硬编码 `raw_results_20260531_001.json` | 低 | 删除 |
| `scripts/_normalize_im_batch.py` | 特定数据导入，非通用 | 低 | 移至 `scripts/archive/` |

### 1.2 已完成使命的迁移脚本

这些脚本都有副作用检查（已存在则跳过），说明设计上是一次性的，现在保留只增加维护成本：

| 文件 | 目的 | 状态 | 建议 |
|------|------|------|------|
| `scripts/migrate_to_multiuser.py` (171 行) | 单用户 → 多用户目录迁移 | 完成 | 移至 `scripts/archive/` |
| `scripts/migrate_legacy_jd_fields.py` (430 行) | 补填旧 jd_analysis.json 缺失字段 | 完成 | 移至 `scripts/archive/` |
| `scripts/backfill_legitimacy.py` (134 行) | 估算 legitimacy_score | 完成 | 移至 `scripts/archive/` |
| `scripts/backfill_job_level.py` (68 行) | 正则回填 job_level 字段 | 完成 | 移至 `scripts/archive/` |
| `scripts/backfill_decision_score.py` (266 行) | 计算 decision_score（7 维度） | 完成 | 移至 `scripts/archive/` |
| `scripts/backfill_needs_refetch.py` (81 行) | 标记需要重新抓取的 job | 完成 | 移至 `scripts/archive/` |
| `scripts/backfill_default_answers.py` (198 行) | 回填面试 Q&A | 已被 agent 替代 | 移至 `scripts/archive/` |

### 1.3 遗留数据目录

| 路径 | 问题 | 建议 |
|------|------|------|
| `output/` | 多用户重构前的输出目录，现已由 `users/{uid}/output/` 替代，仍保留空壳 | 删除或确认内容为空后删除 |
| `ARCHIVE_pre_multiuser/` | 500+ MB 历史输出，占用上下文且污染 graphify | 移至项目目录外 |
| `users/nonexistent/output/` | users.json 中无对应条目的孤立用户目录 | 删除 |

### 1.4 Agent 目录重复（P1 风险）

```
D:\JobIt\1_generate_linkedin_cv\.claude\agents\         ← 外层（7 个文件）
D:\JobIt\1_generate_linkedin_cv\1_generate_linkedin_cv\.claude\agents\  ← 内层（11 个文件）
```

外层与内层重复的 7 个 agent：`cover-letter`, `cv-evaluator`, `cv-parser`, `cv-writer`, `jd-analyzer`, `Orchestrator`, `progress-writer`。

**风险**：Claude Code 按工作目录就近原则加载 agent，若用户在不同目录启动会使用不同版本（外层版本已做 model pin，但内层对应文件尚未同步）。  
**建议**：保留外层（`1_generate_linkedin_cv/.claude/agents/`）为唯一 source of truth，删除内层重复的 7 个文件；4 个新 agent（default-answers, exp-optimizer, form-assistant, interview-prep）迁移至外层。

> **即时操作**：内层 jd-analyzer / cv-writer / cover-letter / cv-evaluator / Orchestrator / cv-parser / progress-writer 尚未做 model pin，需要补做或直接删除这些内层副本。

---

## 2. 质量风险（Quality Risks）

### P0 — 多用户数据隔离（已识别，见上轮分析）

- `server.py:45` `_current_user` 全局变量
- `server.py:33` `_search_log` 全局列表
- **修复路径**：Week 2（per-request uid 参数）

### P1 — LinkedIn MCP 并发瓶颈（已识别）

- `run_phase2_search.py` `max_workers=1`，共享 cookie 目录
- **修复路径**：Week 3（per-user profile dir）

### P2 — 崩溃恢复逻辑不完整

`_phase2_temp_partial.json` 在 Orchestrator 中有文字描述（崩溃后使用 partial 文件并显示 WARN），但没有明确的写入时机和数据完整性校验。若 crash 发生在 50% 搜索进度，partial 结果可能包含该轮关键词的半数职缺，后续 dedup 不会重新抓取已有 job_id，导致静默丢失。

**建议**：在 `run_phase2_search.py` 中每个 keyword search 完成后立即 append 到 partial 文件（而非全量完成后一次写入），并在恢复时对 partial 文件做 schema 验证。

### P2 — CV-Group 强制绑定只在 dedup 时执行

SPEC 规定 CV 与 group 严格对应（`config.json` source of truth），但绑定检查在 Phase 2C（dedup prescore）时完成，Phase 3A cv-writer 直接信任传入的 `cv_file` 字段。若 `jd_analysis.json` 中 `cv_file` 字段被意外修改（手动编辑或 server 端 bug），Phase 3 会用错误的 CV 生成材料，且无感知。

**建议**：在 cv-writer agent 调用前，在 Orchestrator 中增加一次 `group_id === job_folder.split('_')[0]` 的断言校验。

### P2 — PDF 主题 session 级缓存无持久化

Phase 3C 主题选择 "session 内复用"，但 session 中断后下次须重新选择，且 Orchestrator 没有显式的主题 cache 文件。批量生成（10 个 job）时若中途 crash，重启后需重新选主题。

**建议**：在 `memory/progress.json` 中加入 `last_theme` 字段，Phase 3C 优先读取。

### P3 — LinkedIn Posting manual_review URL 不持久化

Orchestrator Phase 2（Posting 变体）收集无法提取 job_id 的帖子 URL，但仅 "展示，不分析"，不写入 search_history.json。下次搜索会重复展示相同 URL。

**建议**：在 search_history.json 的 batch 条目中增加 `manual_review_urls: []` 字段，dedup 时对比。

### P3 — default-answers 无法禁用

Phase 2F 对 score >= 70 的 job 自动触发 default-answers agent，无 config 开关。对 50+ 用户的商业产品，不同用户可能有不同偏好，且 story-bank 未初始化时降级到 cv_parsed 模式为静默降级（用户不知道没有用到 story bank）。

**建议**：
1. 在 `config.json` 中增加 `auto_default_answers: true/false` 开关（默认 true）
2. 降级时在 jd_analysis.json 中写入 `"default_answers_source": "cv_parsed_fallback"` 字段

---

## 3. 冗余 / 未使用代码（Redundant / Unused）

### 3.1 调试脚本（30+ 个，均以 `_` 开头）

这些脚本**从未被生产代码或 agent 调用**，是开发过程的临时工具：

```
_debug_search.py      _run_group_search.py    _find_unscored_pdm.py
_show_all_jobs.py     _show_new_jobs.py       _list_batch.py
_get_hidden_jobs.py   _extract_jd_data.py     _extract_extra_jobs.py
_create_jd_dirs.py    _get_jd_texts.py        _normalize_im_batch.py
_patch_cv_parsed.py   _fix_severity.py        _check_dedup.py
_check_dedup2.py      _check_after_dedup.py   _check_history_scores.py
_check_desc_full.py   _score_dist.py          _debug_score.py
_debug_build_meta.py  _reset_batch_seen.py    _prep_jd_analysis.py
_test_backfill.py
```

**建议**：整体移至 `scripts/archive/`，不删除（保留 debug 记录价值），但明确排除在 graphify 和 Claude Code 上下文之外。

### 3.2 功能重复的脚本

| 重复对 | 保留 | 删除/归档 |
|--------|------|-----------|
| `run_phase2_search.py` + `_run_group_search.py` | `run_phase2_search.py`（正式流程） | `_run_group_search.py`（手动 debug 版） |
| `_show_all_jobs.py` + `_show_new_jobs.py` | 均归档 | — |
| `_check_dedup.py` / `_check_dedup2.py` / `_check_after_dedup.py` | 均归档 | — |

### 3.3 `pre_generate.py` 功能已被 Agent 取代

`pre_generate.py`（363 行）直接调用 Anthropic SDK（`anthropic.Anthropic()`），实现预生成面试答案和 JD 增强描述，使用 thread pool（max_workers=2）批量处理。该功能已完全被以下 agent 覆盖：
- `default-answers` agent（Phase 2F 自动触发）
- `jd-analyzer` agent（JD 语义分析）

**建议**：归档 `pre_generate.py`。若 batch 预生成场景仍有需求，可通过 server 端触发 agent 替代。

### 3.4 `translate_skills.py` 功能可合并入 jd-analyzer

`translate_skills.py`（149 行）检测 recommended_emphasis / missing_skills 中的德语文本并通过 `claude -p` CLI 翻译为英文，是对 jd-analyzer 输出的一次后处理。该逻辑可直接写入 jd-analyzer 的 prompt："若 recommended_emphasis 中存在德语词汇，输出时翻译为英文。"

**建议**：将翻译逻辑内化到 jd-analyzer agent prompt，归档 `translate_skills.py`。

---

## 4. 特定场景代码（Scenario-Specific）

### 4.1 Backfill 脚本群（已归档建议，见第 1.2 节）

这 7 个 backfill 脚本对应不同版本的数据 schema 演进，是典型的"技术债还款"工具，保留在 scripts/ 中对新开发者造成误导（"这些是正常流程的一部分吗？"）。统一移至 `scripts/archive/backfill/`。

### 4.2 `refetch_stepstone_details.py` / `refetch_details.py`（恢复专用）

两个 refetch 脚本用于处理 Stepstone 反爬虫（空 description）和 LinkedIn 重新抓取场景，属于运维恢复脚本，不在主流程中自动触发。

**建议**：保留在 scripts/，但在 CLAUDE.md 中明确标注为"恢复工具（运维使用）"，避免误认为是常规流程的一部分。

### 4.3 LinkedIn Posting 搜索变体

该变体完整实现了一套不同于标准 Phase 2 的搜索路径（WebSearch + regex + MCP 代替 LinkedIn MCP 直接搜索），实用性高但与主流程在代码层面耦合度低，且 SPEC.md 对其描述与 Orchestrator.md 存在落差（SPEC 完全没有文档化这条路径）。

**建议**：在 SPEC.md 中为 LinkedIn Posting 变体补充独立章节，明确与标准 Phase 2 的分叉点。

---

## 5. 优化为 Agent / Hook / Skill / MCP 的机会

### 5.1 应改为 Hook 的脚本

| 脚本 | 当前触发方式 | 建议触发方式 | 理由 |
|------|-------------|-------------|------|
| `generate_summary.py` | Phase 2G 后由 Orchestrator 调用 | `PostToolUse(Write)` hook：检测 jd_analysis.json 写入后自动触发 | 每次 JD 分析完成后自动更新 summary，无需 Orchestrator 显式调用 |
| `gen_job_tracker_html.py` | server.py 启动时检查并生成 | `UserPromptSubmit` hook 或 server.py 启动逻辑内保留 | 35 行，保持在 server.py 内最简单 |
| `progress-writer` agent | Phase 4 / Stop hook | 已在 Stop hook 触发，机制正确 ✓ | — |

### 5.2 应改为 Skill 的功能

| 功能 | 现状 | 建议 |
|------|------|------|
| `check.py` | 每次 session 启动由 CLAUDE.md 指令调用 | 封装为 `/check` skill，支持 `--phase2 / --verbose`（已在 CLAUDE.md 定义，但无对应 .claude/skills/ 文件） |
| `theme-factory` | Orchestrator.md 中以"skill"名义被引用，但无对应的 `.claude/skills/` 文件 | 创建 `.claude/skills/theme-factory.md`，定义主题选择交互逻辑，并写入 `memory/progress.json` 的 `last_theme` |
| `review-ui` | 同上，Orchestrator 引用但无实际文件 | 创建 `.claude/skills/review-ui.md`，标准化 Phase 2G 和 Phase 3B 的用户选择交互格式 |

### 5.3 应改为 MCP 的功能

| 功能 | 现状 | 建议 |
|------|------|------|
| Stepstone 搜索 | 独立 HTTP SSE 进程，需手动启动，无自动重启 | 保持当前架构，但增加 server.py 启动时的健康检查 + pm2 管理（Week 4） |
| 公司稳定性 WebSearch 缓存 | jd-analyzer 每次查，无跨请求复用 | 在 `server.py` 中增加内存缓存层（key=company, TTL=1h），或封装为轻量 MCP 工具 |

### 5.4 `server.py` 中可提取为独立 Agent 调用的端点

下列 API 端点在 server.py 内直接 spawn `claude` subprocess，应改为通过正式 agent 调用（参数传递更结构化，可记录 token 成本）：

| 端点 | 当前实现 | 建议 |
|------|----------|------|
| `/api/default-answers` | SSE stream，spawn claude -p | 改调 default-answers agent（已有） |
| `/api/form-assist` | spawn claude -p form-assistant | 改调 form-assistant agent（已有） |
| `/api/optimize-exp` | spawn claude -p exp-optimizer | 改调 exp-optimizer agent（已有） |

---

## 6. 脚本合并机会（Script Consolidation）

### 6.1 Cover Letter 输出合并（高优先级）

```
gen_cover_letter_pdf.py  (221 行)
gen_cover_letter_docx.py (144 行)
```

两者均读取 `cover_letter_draft.md`，`gen_cover_letter_docx.py` 甚至直接 import `parse_cover_letter()` from `gen_cover_letter_pdf.py`。

**建议**：合并为 `gen_cover_letter.py --format pdf|docx|all`，`parse_cover_letter()` 保留为内部函数。节省约 120 行重复逻辑。

### 6.2 Phase 2 搜索脚本合并（中优先级）

```
run_phase2_search.py          (687 行) — LinkedIn
run_phase2_search_stepstone.py (596 行) — Stepstone
```

两者逻辑结构相似：抓取关键词 → 获取 job 详情 → 写 _phase2_temp.json。差异仅在 MCP 接口和字段映射。

**建议**：抽取共享的 Phase 2 search runner 框架，两个脚本作为 `--source linkedin|stepstone` 的具体实现保留，或将通用逻辑提取到 `common.py`。减少约 200 行重复的 offset 处理、日志输出、crash 恢复代码。

> 注：合并后需特别注意 Stepstone 的 async 特性（`asyncio`）vs LinkedIn 的同步 MCP 调用，两者的执行模型不同，合并需慎重处理并发模型。

### 6.3 generate_summary.py 可内化为 server.py 的后台任务

`generate_summary.py`（268 行）在 Phase 2G 后被 Orchestrator 调用，功能是扫描所有 jd_analysis.json 生成 job_summary.md。该逻辑可作为 `server.py` 的 `/api/refresh-summary` 端点实现，省去子进程调用开销。

**建议**（中优先级）：将 `generate_summary.py` 逻辑以函数形式集成到 `server.py`，同时保留作为命令行工具的入口（供 agent 调用）。

---

## 7. 过度设计（Over-Engineering）

### 7.1 双重评分（预评分 + 精确分）

**现状**：
- Phase 2C 执行 `quick_score()`（Python，关键词匹配，用于 display 排序）
- Phase 2E `jd-analyzer`（LLM，10 维度语义评分，生成 match_score）

两次评分都在 Phase 2 内完成，用户在 Phase 2G 看到汇总表之前两者都已完成。预评分的"加速展示"优势已不存在（用户看不到"先预排序再精确分"的中间状态），但引入了概念混乱：`match_score_preview`（int 0-100） vs `match_score`（float，jd_analysis.json）是两套不同体系。

**建议**：
- 保留 `quick_score()` 仅用于 Phase 2C 决定是否需要 JD 分析（`skip_analysis` 阈值），不用于展示排序
- Phase 2G 展示表以 jd-analyzer 的 `match_score` 为唯一排序依据
- `match_score_preview` 字段降级为内部字段，不在 UI 中暴露

### 7.2 `backfill_decision_score.py` 的 7 维度评分过复杂

该脚本实现了 `calc_location_fit()`, `calc_language_fit()`, `calc_level_fit()`, `calc_culture_fit()` 等 7 个独立函数来计算 `decision_score`。作为一次性 backfill 工具这过度工程化了；而如果该评分体系仍有业务价值，其逻辑应迁移进 jd-analyzer agent 的评分维度（而非作为独立脚本维护）。

**建议**：归档 `backfill_decision_score.py`；若 decision_score 维度仍需要，在 jd-analyzer.md prompt 中增加对应维度。

### 7.3 `server.py` 1821 行单体（P2）

单体 server.py 混合了：HTTP 路由分发 / 文件 I/O / 状态管理 / subprocess 管理 / SSE 流控 / 用户管理 / Job 数据逻辑。

**建议分拆**（Week 3-4）：

```
server.py          ~400 行  启动 + 路由分发 + 静态文件
server_jobs.py     ~400 行  Job 列表 / 缓存 / 字段更新 / 状态
server_search.py   ~300 行  搜索触发 / SSE log / subprocess 管理
server_ai.py       ~300 行  AI 端点（default-answers / form-assist / exp-optimizer）
server_users.py    ~200 行  多用户管理 / config / group CRUD
```

每个模块单独可测试，`server.py` 只做 import + `run()`。

### 7.4 Page 3（Add Group）已设计但未实现（P3 设计债）

SPEC.md 完整记录了 "Page 3: Add/Edit Keyword Group" 的交互设计（包含 `POST /api/group-save` 端点），但代码中标注 `🚧 待实现`。对于 50 用户以上的 B2C 产品，用户无法在 UI 中自助创建 keyword group，必须手动编辑 config.json，这是用户体验瓶颈。

**建议**：将 Page 3 列入 Roadmap，明确实现优先级（建议 Week 3-4 配合 server 拆分一起实现 `/api/group-save`）。

---

## 8. 模糊不清（Ambiguous / Unclear）

### 8.1 `theme-factory` 和 `review-ui` Skill 不存在

Orchestrator.md 中引用了 `theme-factory`（Phase 3C）和 `review-ui`（Phase 2G / 3B）作为 Claude Code skill，但 `.claude/skills/` 目录下不存在对应文件。这意味着 Orchestrator 在描述一个"应该存在"的接口，实际实现是 Orchestrator 自身的 inline 交互。

**影响**：如果将来有人添加 `.claude/skills/` 目录，可能会看到引用但找不到文件而困惑。

**建议**：在 Orchestrator.md 中注释说明这两个是"内联交互模式，非正式 skill 文件"，或创建实际的 skill 文件。

### 8.2 `_phase2_temp_partial.json` 的写入时机未定义

Orchestrator 提到若 `_phase2_temp.json` 缺失则尝试使用 `_phase2_temp_partial.json`，但：
- 谁写 `_phase2_temp_partial.json`？
- 何时写（每个 keyword 完成后，还是 crash 时的 signal handler）？
- 目前 `run_phase2_search.py` 中是否有实际的 partial 写入逻辑？

**建议**：在 `run_phase2_search.py` 中显式添加每个 keyword 完成后 append 的写入，并在 Orchestrator.md 中标注此为 `run_phase2_search.py` 的行为。

### 8.3 Stepstone `enabled` 配置字段无 schema 文档

SPEC.md 和 CLAUDE.md 多处引用 `stepstone.enabled=true/false` 作为 Stepstone 功能开关，但 config.json 的 schema 文档（SPEC 中）未明确列出该字段的位置和默认值。

**建议**：在 SPEC.md 的 config.json schema 章节中增加 `"stepstone": {"enabled": false}` 的文档。

### 8.4 SPEC.md 与 Orchestrator.md 的已知不一致

| 维度 | SPEC.md | Orchestrator.md | 应以哪个为准 |
|------|---------|-----------------|-------------|
| PDF 输出 | 提到 `cv_final.pdf` | `cv_ats.pdf` + `cv_styled.pdf`（--dual） | Orchestrator（实现更新） |
| Cover letter 输出 | `cover_letter_final.pdf` | `.pdf` + `.docx` | Orchestrator + CLAUDE.md |
| default-answers 触发 | 未提及 Phase 2 自动触发 | Phase 2F 自动触发（score>=70） | Orchestrator |
| LinkedIn Posting 变体 | 无 | 完整实现文档 | Orchestrator（SPEC 需补充） |

**建议**：以 Orchestrator.md 为实现真相，同步更新 SPEC.md 的对应章节。

---

## 9. 文件结构优化

### 9.1 目标结构（调整后）

```
scripts/
├── server.py                    ← 入口（400 行目标）
├── server_jobs.py               ← Job 逻辑（新）
├── server_search.py             ← 搜索端点（新）
├── server_ai.py                 ← AI 端点（新）
├── server_users.py              ← 用户管理（新）
├── check.py                     ← Sanity check（保留）
├── search_state.py              ← 状态管理（保留）
├── run_phase2_search.py         ← LinkedIn 搜索（保留）
├── run_phase2_search_stepstone.py ← Stepstone 搜索（保留）
├── common.py                    ← MCP 共享工具（保留）
├── generate_summary.py          ← 汇总生成（保留，考虑内化）
├── generate_pdf.py              ← PDF 生成（保留）
├── gen_cover_letter.py          ← CL PDF+DOCX 合并（新，替代两个旧文件）
├── refetch_details.py           ← LinkedIn 重新抓取（保留，标注：运维工具）
├── refetch_stepstone_details.py ← Stepstone 重新抓取（保留，标注：运维工具）
├── translate_skills.py          ← 翻译工具（归档，逻辑移入 jd-analyzer）
└── archive/
    ├── backfill/                ← 所有 backfill_*.py
    ├── migrate/                 ← 所有 migrate_*.py
    └── debug/                   ← 所有 _*.py

.claude/
└── agents/                      ← 唯一的 agent 目录（外层，11 个文件）
    ← 删除内层重复的 7 个文件

users/
└── nonexistent/                 ← 删除（孤立目录）

output/                          ← 删除（空旧目录）
ARCHIVE_pre_multiuser/           ← 移至项目外
```

### 9.2 新增文件

```
.claude/skills/theme-factory.md  ← Phase 3C 主题选择 skill
.claude/skills/review-ui.md      ← Phase 2G / 3B 用户选择 skill
```

---

## 10. 风险 / 复杂度 / 功能依赖矩阵

| 优化项 | 风险 | 复杂度 | 功能依赖 | 建议时序 |
|--------|------|--------|---------|---------|
| 清理 _*.py debug 脚本（移至 archive） | 极低 | 极低 | 无 | 立即 |
| 清理一次性 migrate/backfill 脚本 | 极低 | 极低 | 无 | 立即 |
| 删除 parse_cv.py / parse_cv_em.py | 极低 | 极低 | 无 | 立即 |
| 删除 users/nonexistent / output/ | 低 | 极低 | 无 | 立即 |
| 内层 agent 目录重复文件同步 / 删除 | 低 | 低 | agent 加载路径 | Week 1 |
| gen_cover_letter.py 合并 | 低 | 低 | CLAUDE.md 调用命令需更新 | Week 1 |
| translate_skills.py 逻辑内化到 jd-analyzer | 低 | 低 | jd-analyzer prompt 更新 | Week 1 |
| theme-factory / review-ui skill 文件 | 低 | 低 | Orchestrator.md 引用需同步 | Week 1 |
| memory/progress.json 增加 last_theme | 低 | 低 | progress-writer agent prompt | Week 1 |
| seen_jobs TTL（已完成） | ✓ | — | — | 完成 |
| Model pin 9 agents（已完成） | ✓ | — | — | 完成 |
| `_phase2_temp_partial.json` 写入逻辑明确化 | 中 | 中 | run_phase2_search.py | Week 2 |
| P0 数据隔离（_current_user / _search_log） | 高 | 高 | server.py 全部 handler | Week 2 |
| auto_default_answers 开关 + 降级标记 | 低 | 低 | config.json schema + Orchestrator | Week 2 |
| CV-group 断言在 Phase 3 前重新校验 | 低 | 低 | Orchestrator.md | Week 2 |
| SPEC.md 与 Orchestrator.md 同步更新 | 低 | 中 | 文档工作 | Week 2 |
| config.json stepstone.enabled schema 补充 | 极低 | 极低 | SPEC.md 文档 | Week 2 |
| quick_score 仅用于 skip_analysis，不用于展示 | 低 | 低 | Orchestrator + generate_summary.py | Week 2 |
| LinkedIn Posting manual_review URL 持久化 | 低 | 低 | search_history.json schema + Orchestrator | Week 2 |
| P1 LinkedIn MCP per-user profile dir | 中 | 中 | run_phase2_search.py + config | Week 3 |
| server.py 拆分为 5 个模块 | 中 | 高 | 所有 server 端测试 + 端点路由 | Week 3–4 |
| Page 3 Add Group UI 实现 | 中 | 高 | server_users.py（需先拆分） + 前端 | Week 4 |
| generate_summary.py 内化到 server.py | 低 | 中 | server_jobs.py（需先拆分） | Week 4 |
| Stepstone pm2 进程管理 | 低 | 低 | 运维脚本 | Week 4 |
| run_phase2_search.py 抽取公共框架 | 中 | 高 | LinkedIn + Stepstone 并发模型不同 | Week 4 |

---

## 11. 执行路线图

### 立即（无风险，今天）
1. `scripts/archive/` 目录创建，所有 `_*.py` + backfill + migrate 移入
2. 删除 `parse_cv.py`, `parse_cv_em.py`
3. 删除 `users/nonexistent/`, `output/`（确认为空）
4. 将 `ARCHIVE_pre_multiuser/` 移至项目目录外

### Week 1（低风险，不影响生产流程）
5. Agent 目录统一：比对内外层agent代码后，再决定要不要删除内层重复 7 个 agent，将 4 个新 agent 移至外层
6. 合并 `gen_cover_letter_pdf.py` + `gen_cover_letter_docx.py` → `gen_cover_letter.py`
7. 创建 `.claude/skills/theme-factory.md` + `review-ui.md`
8. jd-analyzer prompt 中增加德语翻译指令，归档 `translate_skills.py`
9. `memory/progress.json` 增加 `last_theme` 字段，更新 progress-writer agent

### Week 2（P0/P2 修复，需测试）
10. P0：`server.py` 数据隔离（_current_user / _search_log）
10a. **补写 `test_search_state.py`**（与第 10 条同步，优先写 TestDedup + TestQuickScore，为 P0 修复提供回归保护）
10b. **补写 `test_generate_summary.py`**（优先写 TestCrossSourceDedup + TestBuildMarkdown，拦截格式破坏传递到 parse_jobs 的传递性故障）
11. `run_phase2_search.py` 增加 partial 写入逻辑
12. Orchestrator 增加 Phase 3 前 cv-group 断言
13. `config.json` 增加 `auto_default_answers` 开关，jd_analysis 增加降级标记
14. SPEC.md 与 Orchestrator.md 内容对齐

### Week 3（可扩展性）
15. P1：LinkedIn per-user MCP profile dir
16. `server.py` → `server_jobs.py` + `server_search.py`（部分拆分）
16a. **扩展 `test_core.py`**（补写 TestParseRelativeDate + TestInferLocation + TestToStrList，并为 compute_group_stats() 建立基准测试，在 server.py 拆分前锁定行为）

### Week 4（架构优化）
17. `server.py` 完成拆分（+ `server_ai.py` + `server_users.py`）
18. Page 3 Add Group UI 实现（依赖 `server_users.py`）
19. Stepstone pm2 进程管理
20. `generate_summary.py` 内化为 server 后台任务

---

## 13. 单元测试覆盖审计（2026-06-17）

> 评审维度：现有覆盖 → 高风险缺口 → 补测方案 → 路线图插入点

---

### 13.1 现有覆盖状况

**文件：** `scripts/tests/test_core.py` + `conftest.py`（16 个测试，全部针对 `server.py`）

| 已测函数 | 测试数 | 覆盖质量 |
|---------|--------|---------|
| `_update_jd_field()` | 5 | 良好（400/404/覆盖/新增/Unicode） |
| `compute_search_analysis()` | 5 | 良好（无文件/损坏JSON/空批次/关键词聚合/分数分段） |
| `parse_jobs()` | 7 | 良好（空/基本行/短行/合并jd_analysis/materials_ready/缓存/跨源标记） |

**覆盖结论：** server.py 的数据读写层（3 个关键函数）已有稳固测试基础；但 `search_state.py`（643 行）和 `generate_summary.py`（268 行）**零覆盖**，而这两个模块是 Phase 2 核心数据流的主干。

---

### 13.2 高风险缺口（按优先级）

#### P0 — `search_state.py` — 去重与评分逻辑（零测试）

| 函数 | 风险 | 说明 |
|------|------|------|
| `dedup_and_sort()` | 🔴 极高 | 规则 A（job_id）+ 规则 B（company+title）+ `needs_refetch` 豁免三者并存，边界条件多，已有已知 bug（seen_jobs 仅更新 display_jobs）修复后无回归保护 |
| `quick_score()` | 🔴 高 | 5/2 分权重+token 化拆分逻辑，无测试导致评分回归无法感知（snippet<100字 fallback 路径尤其脆弱） |
| `_expand_skill_tokens()` | 🟡 中 | 正则拆分（`& , / ( )`）影响所有关键词命中判断，边界字符集变化静默失效 |
| `compute_offsets()` | 🟡 中 | 同天多批次续页 vs 跨天归零，逻辑分支清晰但无测试，offset 计算错误导致职缺漏抓 |
| `save_raw_results()` | 🟡 中 | 原子写入 + batch_id 创建 + fallback_fetched 统计，失败时静默丢数据 |
| `_prune_seen_jobs()` | 🟡 中 | 30 天 TTL 裁剪，date 比较依赖字符串 lexicographic 排序，闰年/月末边界未验证 |
| `new_batch_id()` | 🟢 低 | 逻辑简单，但 YYYYMMDD_NNN 格式是后续所有路径的 key，回归价值高 |

#### P1 — `generate_summary.py` — 汇总表生成（零测试）

| 函数 | 风险 | 说明 |
|------|------|------|
| `cross_source_dedup()` | 🔴 高 | LinkedIn 优先于 Stepstone + 最早日期保留 + URL 回填三合一，逻辑复杂，是 job_summary.md 正确性的最后一道防线 |
| `build_markdown()` | 🔴 高 | 生成 `parse_jobs()` 的上游输入，任何格式变化都会导致 server.py 解析出错，形成传递性故障 |
| `fmt_list()` | 🟡 中 | max_items 截断 + `+N` 追加 + dict/str 混合处理，已在生产遇到过 dict 格式兼容问题 |
| `extract_group_id()` | 🟡 中 | 文件夹名解析，新 group_id 命名不规范时返回 "—" 静默失效 |
| `score_bar()` | 🟢 低 | 纯阈值函数，4 个分支，测试价值明确 |
| `load_last_seen()` | 🟡 中 | join 逻辑（by_id + by_ct），`last_seen` 缺失时 fallback 到 `first_seen` |

#### P2 — `server.py` 未覆盖函数（补充测试）

| 函数 | 风险 | 说明 |
|------|------|------|
| `compute_group_stats()` (L515) | 🟡 中 | 500+ 行，集成 timeline/is_active/skill aggregation，是 Page 4 My CVs 的数据源 |
| `infer_location()` (L68) | 🟢 低 | 字段回退链，边界容易漏 |
| `_parse_relative_date()` (L127) | 🟡 中 | 解析 "3 days ago" 类文本，失效时 last_seen 全为空 |
| `_to_str_list()` (L110) | 🟢 低 | None/string/dict/list 多态处理 |

---

### 13.3 补测方案

#### 新文件：`scripts/tests/test_search_state.py`

```
TestQuickScore
  test_returns_50_when_no_skills          — cv_skills=[] 返回 50
  test_title_hit_scores_5_per_skill       — 1 个技能命中 title → 5 分
  test_text_hit_scores_2_per_skill        — 1 个技能命中 text → 2 分
  test_snippet_fallback_when_short        — snippet<100字时使用 description_full
  test_capped_at_100                      — 多技能命中不超过 100
  test_token_expansion_ampersand          — "A/B Testing" 命中 "a/b" 子词

TestExpandSkillTokens
  test_splits_on_slash
  test_splits_on_ampersand
  test_includes_full_phrase_as_first
  test_minimum_token_length_2

TestDedup
  test_rule_a_job_id_dedup               — 同 job_id+company+title → 跳过
  test_rule_b_company_title_dedup        — 不同 job_id 但同 company+title → 跳过
  test_needs_refetch_bypass              — needs_refetch=True → 放行
  test_intra_batch_dedup                 — 同批次内同 company+title → 仅保留首条
  test_all_new_jobs_added_to_seen        — 低分隐藏 job 也应进入 seen_jobs（bug fix 回归）
  test_skip_analysis_flag                — match_score_preview < min_score → skip_analysis=True

TestComputeOffsets
  test_same_day_accumulates             — 当天两批次 offset 累加
  test_cross_day_resets                 — 昨天的批次不计入 offset

TestSaveRawResults
  test_creates_batch_entry              — 新 batch_id 写入 history
  test_atomic_write                     — .tmp 文件在 replace 后不存在
  test_updates_existing_batch           — 重复 batch_id 更新而不新增

TestNewBatchId
  test_first_batch_today                — 返回 YYYYMMDD_001
  test_second_batch_today               — 返回 YYYYMMDD_002

TestPruneSeenJobs
  test_removes_entries_older_than_30_days
  test_keeps_recent_entries
  test_missing_date_field_kept          — 无 last_seen/first_seen 字段不崩溃
```

#### 新文件：`scripts/tests/test_generate_summary.py`

```
TestFmtList
  test_empty_returns_dash
  test_single_item
  test_truncates_at_max_items_with_plus_n
  test_dict_items_use_skill_key         — {'skill': 'Python'} → 'Python'
  test_pipe_in_item_replaced_with_slash

TestExtractGroupId
  test_group_prefix_extracted
  test_non_group_folder_returns_dash

TestScoreBar
  test_green_at_75_and_above
  test_yellow_60_to_74
  test_orange_45_to_59
  test_red_below_45

TestCrossSourceDedup
  test_linkedin_preferred_over_stepstone
  test_url_filled_from_stepstone_when_linkedin_missing
  test_remark_set_to_source_duplicate
  test_same_source_keeps_highest_score
  test_earliest_date_preserved_across_duplicates
  test_single_record_group_unchanged

TestBuildMarkdown
  test_output_starts_with_header
  test_row_count_matches_records
  test_missing_skills_formatted_as_fmt_list
  test_folder_link_in_score_cell
  test_empty_records_no_data_rows

TestLoadLastSeen
  test_no_history_file_returns_empty_dicts
  test_by_id_lookup
  test_by_company_title_lookup
  test_fallback_to_first_seen_when_last_seen_missing
```

#### 扩展：`scripts/tests/test_core.py`（补充到现有文件）

```
TestParseRelativeDate（新增）
  test_days_ago
  test_weeks_ago
  test_returns_none_on_unrecognized

TestInferLocation（新增）
  test_location_from_jd_analysis
  test_fallback_to_company_info_location
  test_returns_empty_on_missing

TestToStrList（新增）
  test_none_input
  test_string_list
  test_dict_list_with_skill_key
  test_mixed_types
```

---

### 13.4 测试基础设施说明

现有 `conftest.py` 的 `patch_paths` fixture 已处理 `server.USERS_DIR` 重定向，可直接复用。

`test_search_state.py` 需要新建类似 fixture：
```python
@pytest.fixture
def state_paths(tmp_path):
    import search_state
    search_state.init_paths.__wrapped__ = None  # 重置 lru_cache
    search_state.OUTPUT_DIR      = tmp_path / "output"
    search_state.TEMP_DIR        = tmp_path / "output" / "temp"
    search_state.HISTORY_PATH    = tmp_path / "output" / "search_history.json"
    search_state.BATCH_STATE_TSV = tmp_path / "output" / "temp" / "batch_state.tsv"
    search_state.LOCK_FILE       = tmp_path / "output" / "temp" / ".search.lock"
    (tmp_path / "output" / "temp").mkdir(parents=True)
    search_state._expand_skill_tokens.cache_clear()
    return tmp_path
```

`test_generate_summary.py` 只需要 `tmp_path`（所有函数是纯函数或接受 `Path` 参数，无全局状态）。

---

### 13.5 估算工作量

| 文件 | 测试数 | 估计工时 |
|------|--------|---------|
| `test_search_state.py`（新） | ~28 | 3h |
| `test_generate_summary.py`（新） | ~22 | 2.5h |
| `test_core.py` 扩展 | ~10 | 1h |
| **合计** | **~60** | **~6.5h** |

覆盖后，三个核心数据流模块（server.py / search_state.py / generate_summary.py）的主要分支覆盖率预计从当前 **~18%** 提升至 **~65%**，可拦截 dedup 逻辑回归、markdown 格式破坏、score 计算漂移等最高频故障类型。

---

### 13.6 路线图插入点

在现有第 11 节路线图的 **Week 2** 中增加：

- **10a（新）**：补写 `test_search_state.py`（TestDedup + TestQuickScore 优先，拦截 P0 数据隔离修复引入的回归）
- **10b（新）**：补写 `test_generate_summary.py`（TestCrossSourceDedup + TestBuildMarkdown 优先）
- 修改说明：Week 2 P0 数据隔离修复（原第 10 条）与测试补写同步进行，避免"修了 P0 但破坏了 dedup 逻辑"的无感知场景

在 **Week 3** 中增加：

- **16a（新）**：`test_core.py` 扩展 + `compute_group_stats()` 测试（在 server.py 拆分前建立基准）

---

## 12. 不建议做的事

| 项目 | 原因 |
|------|------|
| 将 `run_phase2_search.py` 和 Stepstone 脚本强行合并 | 并发模型不同（sync vs async），强行合并引入比解决的问题更多 |
| 删除 `refetch_details.py` / `refetch_stepstone_details.py` | 这是重要的运维恢复工具，Stepstone 反爬虫场景下必需 |
| 将 `check.py` 改为 agent | check.py 需要 shell 访问（ps / netstat），作为 Python script 比 agent 更直接 |
| 重写 `search_state.py` | 该模块设计良好（原子写入、TSV 状态、锁文件），已是最小化设计 |
| 用 FastAPI / Flask 替换 server.py 的 stdlib HTTP | 增加外部依赖，对于本地 dashboard 不值得 |
