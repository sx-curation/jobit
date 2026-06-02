# PLAN-upgrade.md — JobiT 升级执行计划

> 版本：v2.2 | 日期：2026-06-01  
> 范围：P0-1（decision_score + job_family 联动）、P0-2（ATS PDF）、P1-1（Playwright 门户扫描）、P1-2（批处理容错）、P1-3（表单助手）、P3-1（合法性检测）、P3-2（missing_skills 严重度 + 优化潜力）、P3-3（薪资研究 + kununu 公司画像）  
> 参考：graphify-out/GRAPH_REPORT.md（348节点/22社区）、career-ops Block A/B/D/E/G 对标

---

## 0. 模块总览与依赖图

```
M0a: decision_score（非技能类综合评分）-code implemented
  └─ 产出：jd_analysis.json 新增 decision_score 字段 + Dashboard 双分显示
  └─ 依赖：无前置模块（扩展 jd-analyzer + server.py + UI）

M0b: ATS PDF 机器可读模式 -code implemented
  └─ 产出：cv_ats.pdf（默认优先输出）+ cv_styled.pdf（保留）
  └─ 依赖：无前置模块（扩展 theme-factory + generate_pdf()）

M1: Playwright 公司门户扫描 
  └─ 产出：新数据源（Portal jobs）→ 与 LinkedIn/Stepstone 合并进 Phase 2
  └─ 依赖：无前置模块（独立新增）


M2: 批处理容错升级 -code implemented
  └─ 产出：TSV 状态追踪 + 锁文件 + retry 机制
  └─ 依赖：无前置模块（扩展 search_state.py）

M3: 表单助手（前端 Panel）
  └─ 产出：Page 2 底部嵌入面板 + /api/form-assist 端点 + form-assistant agent
  └─ 依赖：M1/M2 无依赖；但依赖 jd_analysis.json 已存在（现有 Phase 2 输出）

M4: 合法性检测
  └─ 产出：jd_analysis.json 新增 legitimacy 字段 + UI 标记
  └─ 依赖：无前置模块（扩展 jd-analyzer agent）

M5: 技能缺口分级 + CV 优化潜力评估（career-ops Block B + E 对标）
  └─ 产出：missing_skills 结构化（severity/mitigation）+ customization_potential 评分
  └─ 依赖：M0a 完成后（共用 jd_analysis.json schema 扩展节奏）

M6: 薪资研究 + kununu 公司画像（career-ops Block D 对标 + 德国市场扩展）
  └─ 产出：jd_analysis.json 新增 company_profile 字段（kununu 评分 + 薪资区间 + JD 文化信号）
  └─ 依赖：M4（复用 WebSearch 工具 + session 级 company 缓存机制）
  └─ M6 完成后：M0a 的 industry_fit(0.05) → company_culture_fit(0.10)，权重重分配

M7: 面试准备 Agent + STAR+R 故事库（career-ops Block F 对标）
  └─ 产出：
       · users/{uid}/interview-prep/story-bank.md（持久，跨职位累积）
       · output/{job_folder}/interview_prep.md（per-job，JD 要求 → 故事映射）
  └─ 子模块：
       · M7a Story Bank Bootstrap（一次性，Phase 1 完成后首次触发）
       · M7b Per-job Interview Prep（Phase 3B 前，或用户手动触发）
  └─ 依赖：
       · 硬依赖：cv_parsed_{group_id}.json（M7a 原材料）+ jd_analysis.json（M7b 映射基础）
       · 软依赖：job_family（M0a，提供 Archetype 分帧规则）
       · 软依赖：customization_potential.top_changes（M5，提供强调提示）
       · 软依赖：cover_letter_draft.md（Phase 3A 输出，风格参考）
  └─ 无新 Python 基础设施（纯 agent 文件 I/O，无 server.py 改动）
```

**推荐执行顺序：M0a → M0b → M2 → M4 → M5 → M6 → M7 → M1 → M3**

理由：M0a/M0b 最高优先级；M2/M4 无依赖；M5 依赖 M0a schema；M6 依赖 M4 缓存；M7 依赖 M0a（job_family）和 M5（customization_potential）但无新基础设施，工作量最轻；M1 涉及新外部依赖；M3 改动最复杂放最后。

---

## 0.1 功能完整性检视报告（v2.2）

> 基于 2026-06-02 全模块检视，评分维度：目标清晰度 / 文件规格 / 实施步骤 / 验收标准 / 跨模块接口

### 完整性总览

| 模块 | 目标 | 文件 | 步骤 | 验收 | 跨模块接口 | 完整性 |
|------|------|------|------|------|----------|--------|
| M0a decision_score | ✅ | ✅ | ✅ | ✅ | ⚠️ job_family_fit 计算层未明确（LLM vs Python） | **85%** |
| M0b ATS PDF | ✅ | ✅ | ✅ | ✅ | 🔴 **阻断缺口 1+2**（已在 2.4 节修复） | **80%** |
| M1 Portal+Aggregator | ✅ | ✅ | ✅ | ✅ | ⚠️ Indeed 反检测方案未经实测验证 | **75%** |
| M2 批处理容错 | ✅ | ✅ | ✅ | ✅ | ✅ | **88%** |
| M3 表单助手 | ✅ | ✅ | ✅ | ✅ | ⚠️ `normalize_date()` 代码规范缺失 | **80%** |
| M4 合法性检测 | ✅ | ✅ | ✅ | ✅ | 🔴 **阻断缺口 3**（已在 6.4 节修复） | **80%** |
| M5 技能缺口 | ✅ | ✅ | ✅ | ✅ | ⚠️ `adjacent_in_cv` 查找算法缺失 | **80%** |
| M6 kununu 画像 | ✅ | ✅ | ✅ | ✅ | ⚠️ kununu XPath 路径未给出 | **75%** |
| M7 面试准备 | ✅ | ✅ | ✅ | ✅ | ⚠️ Bootstrap 经历选取优先级未定义 | **70%** |

### 阻断性缺口（实施前必须解决）

| # | 缺口 | 影响模块 | 解决方案位置 |
|---|------|---------|-------------|
| 🔴 1 | `generate_pdf()` 现有签名未知 → 步骤 0b-D 可能需整体重设计 | M0b | → 见 [步骤 0b-A 扩展](#步骤-0b-a实施前检查generate_pdf签名) |
| 🔴 2 | HTML 模板可能用 `<div class="section-title">` 而非 `<h2>` → ATS 标题替换全部无效 | M0b | → 见 [步骤 0b-C 扩展](#步骤-0b-c修改-html-内容用于-ats-渲染) |
| 🔴 3 | `_company_signal_cache` 归属未定义 → M4 和 M6 同时引用但无人实现 | M4, M6 | → 见 [步骤 4-D 扩展](#步骤-4-d公司招聘信号-websearch新增career-ops-block-g-信号-3) |

### 重要缺口（实施中决策）

| 缺口 | 模块 | 建议 |
|------|------|------|
| `job_family_fit` 计算层：LLM agent 无法调用 Python `difflib` | M0a | 计算逻辑放在 `server.py:parse_jobs()` 的后处理层，而非 jd-analyzer agent 内部 |
| M4 WebSearch 缺少德语查询 | M4 | 在现有两条 query 后增加第三条：`"{company_name}" Stellenabbau 2025` |
| `normalize_date()` 规范缺失 | M3 | 实施 M3 时在 `scripts/server.py` 新增该函数，入参 `(raw: str, ats_type: str) -> str` |
| M7 Bootstrap 经历选取优先级 | M7 | 规则：最近 3 年 > 早期；有量化数字 > 无数字；经历描述 > 50 词 > 短描述；至少 1 条含失败/挑战 |
| M5 `adjacent_in_cv` 查找 | M5 | LLM 语义匹配（不是精确词匹配）；prompt 规则：优先在 cv_parsed.skills[] 找同类工具，再在 experience[].responsibilities 找概念重叠 |
| `psutil` 降级方向（M2）| M2 | 无法读取 PID 时改为返回 `True`（假设进程存活），避免误覆盖锁文件 |

### jd_analysis.json 完整字段清单（所有模块 Single Source of Truth）

```json
{
  // ── 现有字段（Phase 2 已输出，不修改）──────────────────────────
  "job_id": "",  "company": "",  "title": "",  "url": "",  "posted_date": "",
  "match_score": 0,
  "required_skills": [],  "bonus_skills": [],
  "matched_skills": [],
  "missing_skills": [],          // M5 改格式：字符串列表 → 对象数组（向后兼容）
  "core_responsibilities": [],   "culture_keywords": [],
  "recommended_emphasis": [],    "company_info": {},

  // ── M0a 新增 ─────────────────────────────────────────────────
  "decision_score": -1,
  "decision_signals": {
    "level_fit": 50, "location_fit": 50, "work_mode_fit": 50,
    "posting_freshness": 50, "compensation_fit": 50,
    "job_family_fit": 50, "industry_fit": 50
  },
  "decision_notes": [],
  "job_family": {
    "detected_group": null, "confidence": 0.0,
    "matched_title": null, "cv_group_match": false, "group_mismatch_warning": null
  },

  // ── M4 新增 ─────────────────────────────────────────────────
  "legitimacy": {
    "verdict": "UNKNOWN", "score": -1,
    "signals": {}, "red_flags": [],
    "repost_info": { "detected": false, "count": 0, "first_seen_batch": null,
                     "days_since_first": 0, "similar_titles": [] },
    "hiring_signal": { "verdict": "unknown", "evidence": null,
                       "search_executed": false, "search_skipped_reason": null }
  },

  // ── M5 新增 ─────────────────────────────────────────────────
  "gap_summary": { "hard_blockers": 0, "nice_to_have": 0, "learnable": 0, "blocker_flag": false },
  "customization_potential": {
    "current_match_score": -1, "estimated_max_score": -1,
    "score_gap": 0, "top_changes": []
  },

  // ── M6 新增 ─────────────────────────────────────────────────
  "company_profile": {
    "kununu": null,
    "salary_research": null,
    "jd_culture_signals": { "growth": [], "wlb": [], "team": [], "culture": [] },
    "search_executed": false, "search_skipped_reason": null
  }
}
```

所有新增字段默认值均已设计为「安全的空值」，旧 jd_analysis.json 文件通过 `.get(field, default)` 读取不会报错。

---

## 1. M0a：decision_score 非技能类综合评分（P0-1）

### 1.1 目标

career-ops 用 10 维度 A-F 框架评估职位，其中包含技能匹配之外的"决策维度"：level alignment、compensation、work mode 等。JobiT 当前只有 `match_score`（技能匹配），缺乏对岗位适配性的整体判断。

新增 `decision_score`（0-100），与 `match_score` 并列显示在 Dashboard，辅助用户快速决策"是否值得投"。

### 1.2 评分维度（career-ops 启发，共 6 维）

| 维度 | 字段名 | 权重 | 数据来源 |
|------|--------|------|---------|
| 岗位级别匹配 | `level_fit` | 0.25 | JD 文本推断 vs `config.preferences.preferred_level` |
| 工作地点匹配 | `location_fit` | 0.20 | JD location vs `config.preferences.preferred_locations` |
| 工作模式匹配 | `work_mode_fit` | 0.15 | JD remote/hybrid/onsite vs `config.preferences.preferred_work_mode` |
| 职位新鲜度 | `posting_freshness` | 0.10 | `date_posted` 距今天数 |
| 薪资范围匹配 | `compensation_fit` | 0.10 | JD 薪资（若有）vs `config.preferences.salary_expectation_eur` |
| **职能家族匹配** | **`job_family_fit`** | **0.15** | JD title fuzzy-match → `config.keyword_groups[].job_family`（career-ops Block A 对标） |
| 行业领域匹配 | `industry_fit` | 0.05 | 公司行业 vs `config.preferences.preferred_domains`（原 domain_fit，降权）**→ M6 完成后升级为 `company_culture_fit`（权重 0.10），数据源换为 kununu** |

**decision_score = Σ(维度分 × 权重)**，0-100 整数。权重合计 = 1.00。

> **`job_family_fit` 是本版本最大升级点**：career-ops 用固定的 6-archetype（FDE/SA/PM/LLMOps/Agentic/Transformation）分类职位，JobiT 的 `config.json` 的 `keyword_groups[].job_family` 列表（每组 15-19 个职位标题、中英双语）**本身就是用户定制的 Archetype 定义**，无需另建映射。

### 1.3 config.json 联动说明

**`preferences` 字段**（已在 leon config.json 中存在，路径正确）：

```json
"preferences": {
  "preferred_level": "entry, experienced",
  "preferred_locations": ["Hamburg", "Berlin", "Munich", "Frankfurt", "Remote"],
  "preferred_work_mode": ["hybrid", "remote"],
  "salary_expectation_eur_monthly": 3500,
  "preferred_domains": ["supply-chain", "logistics", "commercial", "finance", "it"]
}
```

**`job_family` 字段（已存在，零改动）**：

`config.json` 中每个 `keyword_groups[]` 已有 `job_family.en[]` 和 `job_family.de[]` 列表，直接用于 archetype 检测：

```
group-da     → job_family: ["Marketing Data Analyst", "CRM Analyst", ...]（18 en + 18 de）
group-pmo    → job_family: ["PMO Analyst", "Chief of Staff", ...]
group-pdm    → job_family: ["Product Marketing Manager", "GTM Lead", ...]
group-img    → job_family: ["Internal Communications Manager", ...]
group-em     → job_family: ["Event Manager", "Field Marketing Manager", ...]
```

**jd-analyzer 需读取的路径**：`config["job_search"]["keyword_groups"]`（顶层，无需改动结构）

**踩坑**：`config.json` 是多用户结构，`preferences` 已在顶层（不在 `users.{uid}` 下）。jd-analyzer 读取时直接 `config.get("preferences", {})`，不需要 uid 路由。

### 1.4 jd_analysis.json 新增字段

```json
{
  "decision_score": 73,
  "decision_signals": {
    "level_fit": 80,
    "location_fit": 90,
    "work_mode_fit": 100,
    "posting_freshness": 75,
    "compensation_fit": 50,
    "job_family_fit": 88,
    "industry_fit": 60
  },
  "decision_notes": [
    "Remote work confirmed in JD",
    "Salary not disclosed — estimated mid-range",
    "Posted 12 days ago",
    "job_family matched: 'Marketing Data Analyst' (group-da, confidence=0.88)"
  ],
  "job_family": {
    "detected_group": "group-da",
    "confidence": 0.88,
    "matched_title": "Marketing Data Analyst",
    "cv_group_match": true,
    "group_mismatch_warning": null
  }
}
```

向后兼容：旧 `jd_analysis.json` 无此字段时，`parse_jobs()` 用 `.get("decision_score", -1)` 读取，Dashboard 显示「—」而非报错。

`job_family.group_mismatch_warning` 示例（当检测到 CV group 与实际 JD 不匹配时）：
```json
"group_mismatch_warning": "This JD matches group-pmo (confidence=0.91) better than current group-da (0.45). Consider re-running with group-pmo CV."
```

### 1.5 修改文件

| 文件 | 改动 | Graph 社区 |
|------|------|-----------|
| `.claude/agents/jd-analyzer.md` | 新增 decision_score 计算段落 | Community 0 |
| `scripts/server.py:parse_jobs()` | 读取 decision_score + decision_signals | Community 4: HTTP Server |
| `UI/job_tracker_dashboard_desktop/code.html` | 新增 D-Score 列 / 双分 Badge | Community 2: UI Design |
| `config.json` schema | 新增 preferences 对象（文档 + 注释） | — |

### 1.6 分步骤实施

#### 步骤 0a-A：扩展 jd-analyzer agent

在 `.claude/agents/jd-analyzer.md` 的输出 JSON 规范末尾追加：

```markdown
### Decision Score（非技能类评分，新增）

在 match_score 完成后，额外计算 decision_score。读取候选人偏好（从 config.preferences 传入）：

level_fit 计算规则：
- JD 包含 "senior/lead/principal" + 候选人 preferred_level=mid → 60分
- JD 包含 "junior/associate" + 候选人 preferred_level=mid → 50分
- JD 级别与候选人偏好匹配 → 90分
- JD 未明确级别 → 70分（中性）

location_fit 计算规则：
- JD location 与 preferred_locations 精确匹配 → 100分
- JD 包含 "Germany" + preferred_locations 含德国城市 → 70分
- 完全不匹配 → 20分
- JD location 未注明 → 50分（中性）

work_mode_fit 计算规则：
- JD 含 "remote" + preferred_work_mode 含 "remote" → 100分
- JD 含 "hybrid" + preferred_work_mode 含 "hybrid" → 100分
- JD 含 "on-site/in-office" + preferred_work_mode 仅含 "remote" → 10分
- 未注明 → 50分（中性）

posting_freshness 计算规则（date_posted 距今天数）：
- 0-7天 → 100分
- 8-30天 → 80分
- 31-90天 → 50分
- >90天 → 20分
- 无 date_posted → 50分（中性）

compensation_fit 计算规则：
- JD 含薪资范围且 ≥ salary_expectation_eur × 0.9 → 90分
- JD 含薪资范围但低于期望 20% 以上 → 30分
- JD 未披露薪资 → 50分（中性）

job_family_fit 计算规则（career-ops Block A 对标，权重 0.15）：

用 difflib.SequenceMatcher 对 JD title 与所有 keyword_groups[].job_family.en + .de 做模糊匹配：
- confidence ≥ 0.85 → 95分（强匹配）
- confidence 0.70-0.84 → 80分
- confidence 0.50-0.69 → 60分
- confidence < 0.50 → 35分
- job_family 列表读取失败 → 50分（中性）

若 detected_group ≠ 当前分析所用 group_id：
- decision_notes 追加 group_mismatch_warning（建议换用更匹配的 CV group）
- job_family_fit 分数本身不惩罚（是 orchestrator 路由问题，非 JD 问题）

industry_fit 计算规则（原 domain_fit，降权至 0.05）：
- 公司行业 / JD 文本中行业关键词与 preferred_domains 任一匹配 → 90分
- 相邻领域（如 logistics ↔ supply-chain）→ 70分
- 不匹配 → 40分

decision_score = round(level_fit×0.25 + location_fit×0.20 + work_mode_fit×0.15
                       + posting_freshness×0.10 + compensation_fit×0.10
                       + job_family_fit×0.15 + industry_fit×0.05)
```

#### 步骤 0a-B：server.py parse_jobs() 扩展

在现有 `jd.get("match_score")` 读取行之后追加：
```python
job["decision_score"]    = jd.get("decision_score", -1)
job["decision_signals"]  = jd.get("decision_signals", {})
job["decision_notes"]    = jd.get("decision_notes", [])
job["job_family"]        = jd.get("job_family", {})
```

#### 步骤 0a-C：Dashboard UI 新增 D-Score 列

在 `UI/job_tracker_dashboard_desktop/code.html` 的 Match Score 列旁新增 Decision Score 列：

```
┌────────┬───────────┬───────────┬──────────┐
│ Title  │ M-Score ▼ │ D-Score ▼ │ Source   │
├────────┼───────────┼───────────┼──────────┤
│ SAP PA │    82     │    73     │ portal   │  ← 双分 Badge
│ Siemen │    65     │    91     │ linkedin │
│ Capge  │    71     │    —      │ stepstone│  ← 旧数据无 D-Score
└────────┴───────────┴───────────┴──────────┘
```

- D-Score 颜色映射：≥80 绿色、60-79 橙色、<60 灰色、-1（无数据）破折号
- 点击 D-Score Badge → tooltip 展开 7 维明细（含 job_family_fit 的 matched_title）
- 若 `job_family.group_mismatch_warning` 非空 → Dashboard 该行显示 ⚠️ 图标 + tooltip 建议换用的 CV group
- 排序：支持按 D-Score 排序（独立于 M-Score）

**踩坑**：Dashboard 现有排序逻辑绑定在 `match_score` 字段，新增 D-Score 排序需在 `parse_jobs()` 返回的 job 对象中明确包含 `decision_score` 字段，且前端 sort key 需区分。

### 1.7 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| config.json 无 preferences 字段（首次部署） | 高 | jd-analyzer 无偏好数据，所有维度默认 50 | agent prompt 中：preferences 缺失时各维度取中性值 50，输出 decision_notes 提示「未配置偏好」 |
| level_fit 误判（JD 用 "manager" 指 IC 而非管理层） | 中 | 分数偏低 10-20 分 | level 推断使用多信号：职责数量 + 是否有直属汇报 + JD 关键词权重；结果不影响 match_score |
| 旧 jd_analysis.json 无 decision_score 导致前端报错 | 低 | Dashboard 崩溃 | `parse_jobs()` 使用 `.get("decision_score", -1)`；前端对 -1 显示「—」而非数字 |
| 薪资未公开时 compensation_fit 拉低总分 | 高（德国市场薪资不透明） | decision_score 普遍偏低 | 薪资未公开固定给 50 分（中性），权重仅 0.10，最大影响 5 分 |

### 1.8 验收标准

- [ ] 对已有 `date_posted`、location、work_mode 的 JD → `decision_score` 非 -1
- [ ] `config.json` 无 preferences 字段时，所有维度为 50，decision_notes 含提示
- [ ] Dashboard 双列显示 M-Score 和 D-Score
- [ ] 旧 `jd_analysis.json`（无此字段）→ Dashboard 显示「—」不报错
- [ ] 点击 D-Score tooltip → 显示 6 维明细

---

## 2. M0b：ATS PDF 机器可读模式（P0-2）

### 2.1 目标

career-ops 用 Playwright/Puppeteer + `cv-template.html` 生成 ATS 兼容 PDF（去除所有装饰性 CSS，关键词注入，标准 section 标题）。JobiT 当前 WeasyPrint 输出 Kinetic Archive 风格 PDF，渐变/玻璃效果对 ATS 解析不友好。

目标：每次 Phase 3D 自动生成两份 PDF：
- `cv_ats.pdf` — 机器可读版（默认，优先推荐附附件）
- `cv_styled.pdf` — 视觉设计版（保留，供人工审核）

### 2.2 ATS CSS 规则（career-ops 启发）

| 规则 | ATS 模式 | 当前 Kinetic 主题 |
|------|---------|----------------|
| 字体 | Arial/Helvetica（系统字体） | Space Grotesk（Web 字体） |
| 布局 | 单列，无 CSS Grid/Flexbox | 双栏 Flexbox |
| 颜色 | #000000 文字 / #ffffff 背景 | 渐变 #005D8F→#0077B5 |
| 装饰 | 无 box-shadow/backdrop-filter/gradient | 玻璃效果 |
| Section 标题 | 标准英文：Work Experience / Education / Skills / Contact | Kinetic 风格标题 |
| 图形 | 无 SVG / 无背景图 | 技能图表 SVG |
| 字号 | 11pt 正文 / 16pt 姓名 | 自定义 |
| 边距 | 25mm 标准 | 自定义 |

**为什么 ATS 解析会失败**：WeasyPrint 渲染的 PDF 文字是可选中的（非图片），这点没问题。问题在于 ATS 按 CSS reading order 解析：Flexbox 列会导致左列末尾接右列开头，打乱职位/时间阅读顺序；自定义字体可能导致字符编码异常。

### 2.3 修改文件

| 文件 | 改动 | Graph 社区 |
|------|------|-----------|
| `scripts/generate_pdf.py` 或 `pdf_generator.py` | 新增 `get_ats_css()` 函数，调整 `generate_pdf()` 支持 theme='ats' | Community 12: PDF Generator |
| `scripts/generate_pdf.py` | Phase 3D 入口：generate 两次（styled + ats） | Community 12 |
| `.claude/agents/Orchestrator.md` | Phase 3D 注释更新：两份 PDF | Community 0 |
| `CLAUDE.md` 指令表 | 更新 `/themes` 说明 | — |

### 2.4 分步骤实施

#### 步骤 0b-A：实施前检查——`generate_pdf` 签名（阻断缺口 1 解决方案）

**必须在动任何代码前完成此检查**，结果决定步骤 0b-D 的实现路径。

```bash
grep -n "def generate_pdf\|css_string\|html_content\|theme" scripts/generate_pdf.py scripts/pdf_generator.py 2>/dev/null
```

根据结果选择对应路径：

**路径 A：函数已有 `css_string` 参数（或 `html_content` 参数）**
```python
# 已支持，直接在步骤 0b-D 中调用：
generate_pdf(html_content=ats_html, css_string=get_ats_css(), output_path=...)
```

**路径 B：函数只接受 `theme` 名称字符串（无 `css_string` 参数）**
```python
# 在函数末尾追加可选参数（保持向后兼容）：
def generate_pdf(cv_path, output_path, theme="kinetic", css_string=None):
    css = css_string if css_string is not None else build_css_from_theme(theme)
    # ... 其余逻辑不变
```

**路径 C：函数通过 theme 文件名加载 CSS（不接受 CSS 字符串）**
```python
# 将 ATS CSS 写为临时主题文件：
import tempfile, pathlib
with tempfile.NamedTemporaryFile(suffix=".css", delete=False, mode="w") as f:
    f.write(get_ats_css())
    ats_theme_path = f.name
generate_pdf(cv_path, output_path, theme=ats_theme_path)
pathlib.Path(ats_theme_path).unlink()
```

**踩坑**：若函数不在 `scripts/` 下（如 `.claude/skills/pdf-generator/`），用 `grep -r "def generate_pdf" .` 全局搜索。确认路径后将实际文件名填入步骤 0b-D。

#### 步骤 0b-B：新增 ATS CSS 主题

在 PDF 生成模块中新增函数（不修改现有函数签名）：

```python
def get_ats_css() -> str:
    """返回 ATS 兼容的最小化 CSS。无外部字体、无装饰。"""
    return """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: Arial, Helvetica, sans-serif;
        font-size: 11pt;
        line-height: 1.4;
        color: #000000;
        background: #ffffff;
        margin: 25mm;
        max-width: none;
    }
    h1 { font-size: 16pt; font-weight: bold; margin-bottom: 4pt; }
    h2 { font-size: 13pt; font-weight: bold; border-bottom: 1pt solid #000;
         padding-bottom: 2pt; margin-top: 12pt; margin-bottom: 6pt; text-transform: uppercase; }
    h3 { font-size: 11pt; font-weight: bold; margin-top: 8pt; margin-bottom: 2pt; }
    p, li { font-size: 11pt; margin-bottom: 3pt; }
    ul { padding-left: 15pt; }
    .date { float: right; font-size: 10pt; color: #333; }
    /* 禁止所有装饰 */
    .glass, .gradient, .chart, svg, canvas { display: none !important; }
    """
```

#### 步骤 0b-C：修改 HTML 内容用于 ATS 渲染

ATS 版本在渲染前需对 CV HTML 做以下替换（Python 字符串操作，不依赖 BeautifulSoup）：

```python
def prepare_ats_html(cv_html: str) -> str:
    """将 Kinetic 风格 HTML 转换为 ATS 兼容格式。"""
    import re
    # 替换 section 标题为标准英文
    header_map = {
        r'(?i)(berufserfahrung|work history|experience|erfahrung)': 'Work Experience',
        r'(?i)(ausbildung|bildung|education)': 'Education',
        r'(?i)(kenntnisse|fähigkeiten|skills|kompetenzen)': 'Skills',
        r'(?i)(kontakt|contact)': 'Contact',
        r'(?i)(zusammenfassung|profil|summary|profile)': 'Summary',
    }
    for pattern, replacement in header_map.items():
        cv_html = re.sub(
            rf'(<h[12][^>]*>)[^<]*{pattern}[^<]*(</h[12]>)',
            rf'\g<1>{replacement}\g<2>', cv_html, flags=re.IGNORECASE
        )
    # 移除 <script> 标签（WeasyPrint 会忽略但保持干净）
    cv_html = re.sub(r'<script[^>]*>.*?</script>', '', cv_html, flags=re.DOTALL)
    return cv_html
```

**阻断缺口 2 解决方案：实施前必须确认模板标签类型**

在执行 `prepare_ats_html()` 前，先检查实际渲染模板使用的标签：

```bash
# 在 CV 渲染模板文件中搜索 section 标题的实际 HTML 结构
grep -n "Work Experience\|Education\|Skills\|section-title\|section-header\|<h[12]" \
  scripts/generate_pdf.py scripts/pdf_generator.py .claude/skills/pdf-generator/*.md 2>/dev/null | head -30
```

根据结果，`prepare_ats_html()` 需覆盖以下三种模式（已全部写入正则）：

```python
def prepare_ats_html(cv_html: str) -> str:
    import re

    header_map = {
        r'(?i)(berufserfahrung|work history|experience|erfahrung)': 'Work Experience',
        r'(?i)(ausbildung|bildung|education)':                       'Education',
        r'(?i)(kenntnisse|fähigkeiten|skills|kompetenzen)':          'Skills',
        r'(?i)(kontakt|contact)':                                     'Contact',
        r'(?i)(zusammenfassung|profil|summary|profile)':             'Summary',
    }

    # 模式 1：<h1>/<h2> 标签（最常见）
    for pattern, replacement in header_map.items():
        cv_html = re.sub(
            rf'(<h[12][^>]*>)[^<]*{pattern}[^<]*(</h[12]>)',
            rf'\g<1>{replacement}\g<2>', cv_html, flags=re.IGNORECASE
        )

    # 模式 2：<div class="section-title"> 或 <div class="section-header">
    # ATS 解析器需要语义标签，将此类 div 转换为 <h2>
    for pattern, replacement in header_map.items():
        cv_html = re.sub(
            rf'<div[^>]*class="[^"]*(?:section-title|section-header)[^"]*"[^>]*>'
            rf'[^<]*{pattern}[^<]*</div>',
            f'<h2>{replacement}</h2>', cv_html, flags=re.IGNORECASE
        )

    # 模式 3：<span> 或 <p> 内仅含标题文字（边界情况）
    for pattern, replacement in header_map.items():
        cv_html = re.sub(
            rf'(<(?:span|p)[^>]*class="[^"]*(?:heading|title|label)[^"]*"[^>]*>)'
            rf'[^<]*{pattern}[^<]*(</(?:span|p)>)',
            rf'<h2>{replacement}</h2>', cv_html, flags=re.IGNORECASE
        )

    # 移除 <script> 标签
    cv_html = re.sub(r'<script[^>]*>.*?</script>', '', cv_html, flags=re.DOTALL)
    return cv_html
```

**验证方法**：运行后用 `pdftotext cv_ats.pdf -` 检查输出，确认 "WORK EXPERIENCE" / "EDUCATION" / "SKILLS" 等标题出现在正确位置（单栏线性顺序）。若仍乱序，说明 Flexbox 列布局影响了 DOM 读取顺序，需要考虑专用 ATS HTML 模板方案（见 Section 0.1 备注）。

#### 步骤 0b-D：Phase 3D 双 PDF 输出

在 `generate_pdf.py` 的 Phase 3D 入口（调用 `generate_pdf()` 的地方）改为：

```python
# Phase 3D: 生成两份 PDF（优先输出 ATS 版本）
output_dir = get_output_dir(uid) / job_folder

# 1. ATS 版（默认，优先）
ats_html = prepare_ats_html(cv_html)
generate_pdf(
    html_content=ats_html,
    css_string=get_ats_css(),
    output_path=output_dir / "cv_ats.pdf"
)

# 2. 视觉版（保留）
generate_pdf(
    html_content=cv_html,
    theme=selected_theme,           # 现有主题逻辑不变
    output_path=output_dir / "cv_styled.pdf"
)

log(f"[PDF] cv_ats.pdf (机器可读) + cv_styled.pdf (视觉) 生成完成")
```

**注意**：不修改 `generate_pdf()` 函数签名，新增 `css_string` 参数走现有 `build_css_from_theme()` 的旁路（直接传 CSS 字符串）。若 `generate_pdf()` 当前不支持 `css_string` 参数，先追加该参数（默认 `None`，`None` 时走现有主题逻辑）。

#### 步骤 0b-E：CLAUDE.md 指令更新

更新 `/themes` 条目说明：
```
| `/themes`  | 列出可用 PDF 视觉主题（不含 ats——ats 版本每次自动生成无需指定） |
```

### 2.5 文件命名规范更新

| 文件 | 旧名 | 新名 | 用途 |
|------|------|------|------|
| ATS PDF | `cv_draft.pdf` | `cv_ats.pdf` | 投递附件（默认） |
| 视觉 PDF | `cv_draft.pdf` | `cv_styled.pdf` | 人工审核、分享 |

**关键**：`output/` 目录命名规范不变（`<group_id>_<company>_<title>_<YYYYMMDD>/`）；只是 PDF 文件名拆分。需更新 `Orchestrator.md` 中 Phase 4 汇总逻辑，区分这两个文件。

### 2.6 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| `prepare_ats_html()` 正则误替换 CV 正文内容 | 中 | CV 内容损坏 | 正则仅匹配 `<h1>/<h2>` 标签内文字，不处理 `<p>/<li>` 文字；验收时肉眼对比两版 PDF |
| ATS CSS 过于简化导致 cv_ats.pdf 排版混乱 | 低 | ATS 版不可读 | 准备 PDF 样本进行 ATS 解析器测试（用 pdftotext 提取文本，检查顺序） |
| generate_pdf() 不支持 css_string 参数 | 中 | 需修改函数 | 检查当前函数签名，若不支持则追加 `css_string=None` 参数作为旁路 |
| cv_draft.pdf 被其他脚本硬编码引用 | 中 | 引用失效 | 用 grep 全局搜索 `cv_draft.pdf` 字符串，确认引用点后统一修改 |
| WeasyPrint 对系统 Arial 字体不可用（某些 Linux 环境） | 低 | 字体降级 | 在 ATS CSS 中加 `font-family: Arial, Helvetica, Liberation Sans, sans-serif`，WeasyPrint 会选可用字体 |

### 2.7 验收标准

- [ ] `pdftotext cv_ats.pdf -` 输出文本顺序正确（Work Experience 在前，Skills 在后）
- [ ] `cv_ats.pdf` 不含渐变/玻璃 CSS（用 pdftotext 验证无乱码）
- [ ] `cv_styled.pdf` 外观与当前 Kinetic 主题一致
- [ ] Phase 3D 完成后，output 目录同时存在两个文件
- [ ] 旧 generate_pdf() 调用路径不受影响（现有 `/themes` 功能正常）

---

## 3. M1：Playwright 公司门户扫描（P1-1）

### 3.1 目标

M1 覆盖两类 Playwright 数据源，合并进入同一 Phase 2 管道：

| 类别 | 来源 | 工作方式 | source_type |
|------|------|---------|-------------|
| **公司职业页** | SAP、Siemens、Capgemini、Hapag-Lloyd、Aldi | 导航到企业 careers 页 → 按 ATS 类型解析职位列表 | `portal` |
| **求职聚合平台** | **Indeed、Xing、Monster**（新增） | 按 config.json 关键词搜索 → 翻页提取职位 | `aggregator` |

`aggregator` 源的输入是 `config.keyword_groups[].primary_keywords`（与 LinkedIn/Stepstone 共用关键词列表），输出 job_id 格式为 `ind_` / `xing_` / `mon_` 前缀。

**career-ops 架构参考**：按 `ats_type` / `source_type` 分发，便于未来扩展更多公司或平台。

### 3.2 新增文件

| 文件 | 说明 |
|------|------|
| `scripts/scan_portal.py` | 主扫描入口，按 ats_type 分发到解析器 |
| `scripts/portal_parsers/__init__.py` | 解析器包 + ATS 类型注册表 |
| `scripts/portal_parsers/ats_sap_custom.py` | SAP 自有 ATS 解析器（SAP + Hapag-Lloyd 共用） |
| `scripts/portal_parsers/ats_workday.py` | Workday ATS 解析器（Siemens） |
| `scripts/portal_parsers/ats_generic.py` | 通用分页解析器（Capgemini / Aldi） |
| `scripts/portal_parsers/agg_indeed.py` | Indeed Germany 关键词搜索解析器 |
| `scripts/portal_parsers/agg_xing.py` | XING Jobs 关键词搜索解析器 |
| `scripts/portal_parsers/agg_monster.py` | Monster.de 关键词搜索解析器 |
| `config/portals.yml` | 公司 URL 配置 + ats_type + aggregator 平台配置 |

### 3.3 修改文件

| 文件 | 改动 | Graph 社区 |
|------|------|-----------|
| `scripts/search_state.py` | `save_raw_results()` 接受新 source=`portal_<company>` | Community 5: Search State Engine |
| `scripts/run_phase2_search.py` | 末尾调用 `scan_portal.py` 并合并结果 | Community 8: LinkedIn Phase 2 Search |
| `scripts/check.py` | 新增 `check_playwright()` 健康检测 | Community 7: Sanity Check Module |
| `CLAUDE.md` 指令表 | 新增 `搜索Portal职缺 [company]` 指令 | — |

### 3.4 分步骤实施

#### 步骤 1-A：环境准备
```bash
pip install playwright
playwright install chromium
# 验证：python -c "from playwright.sync_api import sync_playwright; print('OK')"
```
**踩坑**：Windows 下 playwright install 需要管理员权限或手动设置 `PLAYWRIGHT_BROWSERS_PATH`。  
`setup.ps1` 需新增这两行，否则其他用户（kelebogie/amy）环境跑不起来。

#### 步骤 1-B：portals.yml 配置结构（career-ops ats_type 分发模式）
```yaml
portals:
  - id: sap
    name: SAP SE
    careers_url: https://jobs.sap.com/search/?createNewAlert=false&q=&locationsearch=Germany
    ats_type: sap_custom
    keywords_filter: true
    location_filter: Germany
    headless: true

  - id: siemens
    name: Siemens AG
    careers_url: https://jobs.siemens.com/careers?location=Germany
    ats_type: workday
    headless: true

  - id: capgemini
    name: Capgemini
    careers_url: https://www.capgemini.com/jobs/?country=de
    ats_type: generic
    pagination: query_param   # ?page=N 分页
    headless: true

  - id: hapag_lloyd
    name: Hapag-Lloyd AG
    careers_url: https://www.hapag-lloyd.com/en/about-us/careers/job-search.html
    ats_type: sap_custom      # SAP SuccessFactors，与 SAP 自有共用同一解析器
    headless: true

  - id: aldi_nord
    name: Aldi Nord
    careers_url: https://karriere.aldi-nord.de/stellenangebote
    ats_type: generic
    headless: true

  - id: aldi_sued
    name: Aldi Süd
    careers_url: https://www.aldi-sued.de/de/karriere/stellenangebote.html
    ats_type: generic
    headless: true

# ── 求职聚合平台（source_type: aggregator，按关键词搜索） ──────────────
aggregators:
  - id: indeed
    name: Indeed Germany
    search_url: https://de.indeed.com/jobs?q={keyword}&l=Deutschland&sort=date
    source_type: aggregator
    ats_type: indeed
    pagination: query_param      # &start=10 每页10条
    max_pages: 3                 # 每关键词最多 3 页 = 30 条
    headless: true
    anti_bot: cloudflare         # 需特殊启动参数

  - id: xing
    name: XING Jobs
    search_url: https://www.xing.com/jobs/search?q={keyword}&sc_o=jobs_search_button&sort=2
    source_type: aggregator
    ats_type: xing
    pagination: query_param      # &page=2
    max_pages: 3
    headless: true
    anti_bot: moderate

  - id: monster
    name: Monster.de
    search_url: https://www.monster.de/jobs/suche/?q={keyword}&where=Deutschland&sort=newest
    source_type: aggregator
    ats_type: monster
    pagination: query_param      # &pg=2
    max_pages: 3
    headless: true
    anti_bot: low
```

#### 步骤 1-C：portal_parsers/__init__.py 注册表

```python
# scripts/portal_parsers/__init__.py
from .ats_sap_custom import SapCustomParser
from .ats_workday    import WorkdayParser
from .ats_generic    import GenericParser
from .agg_indeed     import IndeedParser
from .agg_xing       import XingParser
from .agg_monster    import MonsterParser

# source_type: portal → company career pages (fixed URL browse)
ATS_TYPE_MAP = {
    "sap_custom": SapCustomParser,
    "workday":    WorkdayParser,
    "generic":    GenericParser,
}

# source_type: aggregator → keyword-search job boards
AGG_TYPE_MAP = {
    "indeed":  IndeedParser,
    "xing":    XingParser,
    "monster": MonsterParser,
}

def get_parser(source_type: str, ats_type: str):
    if source_type == "aggregator":
        cls = AGG_TYPE_MAP.get(ats_type)
    else:
        cls = ATS_TYPE_MAP.get(ats_type)
    if cls is None:
        raise ValueError(f"Unknown {source_type}/{ats_type}. Add to map.")
    return cls()
```

#### 步骤 1-D：scan_portal.py 核心结构（含 aggregator 分发）

```python
# scripts/scan_portal.py

# 统一输出格式（portal 和 aggregator 相同）：
# {
#   "job_id":      "portal_sap_XXXXXXXXXXXX" | "ind_XXXXXXXXXXXX" | "xing_XXXXXXXXXXXX" | "mon_XXXXXXXXXXXX",
#   "title":       "...",
#   "company":     "SAP SE",
#   "description": "...",
#   "url":         "https://...",
#   "_source":     "portal_sap" | "indeed" | "xing" | "monster",
#   "_keyword":    "<matched_keyword>",
#   "_group_id":   "group-da",
#   "location":    "Germany",
#   "date_posted": "2026-06-01"
# }

def run_all_portals(config, group_filter=None):
    """运行所有 portal（公司职业页）解析器。"""
    ...

def run_all_aggregators(config, group_filter=None):
    """运行所有 aggregator（求职平台）解析器，按关键词搜索。"""
    keywords = get_keywords_for_group(config, group_filter)
    results = []
    for agg in load_aggregators():
        parser = get_parser("aggregator", agg["ats_type"])
        for kw in keywords:
            jobs = parser.search(kw, max_pages=agg["max_pages"])
            results.extend(jobs)
    return results
```

**job_id 格式对照：**

| 来源 | job_id 前缀 | 示例 |
|------|------------|------|
| LinkedIn（现有） | `li_` | `li_3789254812` |
| Stepstone（现有） | `st_` | `st_a3f2c1d8e9b0` |
| SAP/公司门户 | `portal_sap_` | `portal_sap_8f3a2b1c4d5e` |
| Indeed | `ind_` | `ind_4a8f3c2b1d9e` |
| XING | `xing_` | `xing_9b2e3f4a5c6d` |
| Monster | `mon_` | `mon_1c4d5e6f7a8b` |

Indeed job_id 可直接用 indeed 平台的 `data-jk`（16位 hex）：`ind_{data-jk}`，无需额外 sha256。

#### 步骤 1-E：各公司解析器实现要点

| 公司 | ats_type | 解析器 | 关键坑 | 解决方案 |
|------|---------|--------|--------|---------|
| **SAP** | sap_custom | ats_sap_custom.py | 无限滚动加载，需 scroll-to-bottom | `page.evaluate("window.scrollTo(0, document.body.scrollHeight)")` 循环3次 |
| **Siemens** | workday | ats_workday.py | 有 bot 检测，headless 可能被阻 | `--disable-blink-features=AutomationControlled` 启动参数；加随机 sleep(1-3s) |
| **Capgemini** | generic | ats_generic.py | 分页参数 `?page=N`，需翻页 | 循环 GET 直到 `nextPage` 为空 |
| **Hapag-Lloyd** | sap_custom | ats_sap_custom.py | 候选人曾在此工作（Work History 节点），同公司不同职位需保留 | `dedup_and_sort()` 现有逻辑已支持（company+title 精确匹配），无需改动 |
| **Aldi Nord** | generic | ats_generic.py | Nord 和 Süd 是独立法人，分开处理；产品类职位少，噪音多 | 关键词过滤相似度阈值调至 0.3 |
| **Aldi Süd** | generic | ats_generic.py | 同上 | 同上 |

#### 步骤 1-F：集成到 Phase 2

在 `run_phase2_search.py` 末尾（LinkedIn + Stepstone 结果合并后），追加：
```python
# 步骤 B.3: Portal 扫描（公司职业页，可选）
if not args.skip_portal:
    from scan_portal import run_all_portals, run_all_aggregators
    portal_jobs = run_all_portals(config, group_filter=args.group)
    all_jobs.extend(portal_jobs)
    log(f"[Portal] 扫描到 {len(portal_jobs)} 条职位")

# 步骤 B.4: Aggregator 扫描（Indeed/Xing/Monster，可选）
if not args.skip_aggregator:
    agg_jobs = run_all_aggregators(config, group_filter=args.group)
    all_jobs.extend(agg_jobs)
    log(f"[Aggregator] 扫描到 {len(agg_jobs)} 条职位")
```

**关键**：`_source` 字段已被 `fetched_per_source` 统计，`indeed` / `xing` / `monster` 作为新 source key 自动累计，无需修改 `save_raw_results()` 签名。

#### 步骤 1-G：三个聚合平台实现要点

| 平台 | anti_bot 级别 | 关键实现 | 主要踩坑 |
|------|-------------|---------|---------|
| **Indeed** | 强（Cloudflare） | job_id = `data-jk` 属性（16位hex，Indeed 原生 ID）；搜索 URL `?q={kw}&l=Deutschland&sort=date` | Cloudflare 拦截 headless → 需 `--disable-blink-features=AutomationControlled` + 真实 UA + 随机 sleep(2-4s) + 不使用 `page.goto` 直接等待，改用 `wait_for_load_state("networkidle")` |
| **XING** | 中 | 搜索结果页 job card 有 `data-testid="job-card"` 属性；sort=2 = 最新发布；XING 与 kununu 同属 New Work SE → company_name 可直接复用 M6 缓存 | 部分职位需登录才能看完整描述 → 先提取卡片摘要，标记 `description_truncated=true`；detail URL 抓取作可选步骤 |
| **Monster** | 低 | 标准 HTML，分页 `?pg=2`；德国市场覆盖率下降，预计单关键词 ≤ 5 条结果 | 职位去重命中率高（Monster 聚合其他平台职位）→ dedup 阶段会过滤，设 max_pages=2 避免浪费 |

**Indeed 反检测启动参数：**
```python
browser = playwright.chromium.launch(
    headless=True,
    args=[
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]
)
context = browser.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    locale="de-DE",
    timezone_id="Europe/Berlin",
)
```

**XING 与 M6 缓存共享：**
```python
# agg_xing.py 抓到职位时，公司名写入 _company_profile_cache
# M6 的 kununu 搜索优先读取此缓存，XING 和 kununu 均属 New Work SE 数据生态
from scan_portal import _company_profile_cache
_company_profile_cache[company_name] = {"source": "xing", "verified": True}
```

#### 步骤 1-H：CLAUDE.md 新指令
```
| `搜索Portal职缺 [company]`      | 仅执行公司职业页扫描；company 可选：sap/siemens/capgemini/hapag/aldi |
| `搜索聚合平台职缺 [platform]`    | 仅执行聚合平台搜索；platform 可选：indeed/xing/monster/all           |
```

### 3.5 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Workday/SAP SF 动态结构变更 | 高（每季度可能更新） | 解析器失效 | 解析器失败 → 输出 `{"error": "parse_failed"}` 并继续，不阻断主流程 |
| Siemens bot 检测封 IP | 中 | 当次扫描失败 | 随机 user-agent + sleep；首次运行用 headed 模式验证 |
| Aldi 职位与 keyword 不匹配 | 高 | 0 结果 | 关键词匹配 fallback：先精确，再词干匹配 |
| **Indeed Cloudflare 拦截** | **高** | **搜索全失败** | **反检测启动参数 + 真实 UA + locale=de-DE；失败时降级跳过 Indeed，不阻断其他源** |
| **XING 职位描述截断（需登录）** | **中** | **description_truncated=true** | **先抓卡片摘要；detail 抓取作可选步骤，截断标记写入 job 对象** |
| **Monster 聚合重复职位** | **高** | **dedup 后剩余少** | **预期行为：dedup 过滤后净增量低，max_pages=2 避免浪费；保留 `_source=monster` 用于来源统计** |
| playwright install 在 CI/offline 环境失败 | 低 | setup 失败 | `check.py` 检测是否已安装；未安装时 Portal/Aggregator 功能降级而非崩溃 |
| Hapag-Lloyd 去重误判（同公司多职位） | 低 | 职位被错误过滤 | 现有 dedup 逻辑是 company+title 精确匹配，不会误杀 |

### 3.6 验收标准

- [ ] `python scripts/scan_portal.py --company sap` 输出 ≥1 条，job_id 格式 `portal_sap_XXXXXXXXXXXX`
- [ ] `python scripts/scan_portal.py --aggregator indeed --keyword "Marketing Analyst"` 输出 ≥1 条，job_id 格式 `ind_XXXXXXXXXXXXXXXX`
- [ ] `python scripts/scan_portal.py --aggregator xing --keyword "Data Analyst"` 输出 ≥1 条，job_id 格式 `xing_XXXXXXXXXXXX`
- [ ] `python scripts/scan_portal.py --aggregator monster --keyword "PMO"` 输出 ≥0 条（Monster 可能 0 结果，不报错）
- [ ] 运行完整 Phase 2 后，`fetched_per_source` 包含 `indeed` / `xing` / `monster` / `portal_sap` 等键
- [ ] Dashboard Source 列正确显示各来源标签
- [ ] Indeed 被 Cloudflare 拦截时：程序打印 `[WARN] Indeed blocked, skipping` 并继续，不崩溃
- [ ] `python scripts/check.py` playwright 健康检测通过

---

## 4. M2：批处理容错升级（P1-2）

### 4.1 目标

升级 `search_state.py` 的批处理状态追踪：
- 增加 TSV 格式状态文件（便于人工核查，不替换现有 JSON）
- 增加锁文件防止并发重复执行
- 增加单任务失败隔离（`failed_jobs` 字段）
- 增加 `--retry-failed` 选择性重试

### 4.2 修改文件

| 文件 | 改动量 | Graph 社区 |
|------|--------|-----------|
| `scripts/search_state.py` | 新增 ~80 行（新函数，不修改现有函数） | Community 5: Search State Engine |
| `scripts/run_phase2_search.py` | 新增锁文件 acquire/release，~20 行 | Community 8 |
| `scripts/server.py` | `_load_search_batches()` 读取 TSV（可选展示），~15 行 | Community 4 |

### 4.3 分步骤实施

#### 步骤 2-A：新增 TSV 状态文件

路径：`output/temp/batch_state.tsv`  
格式（Tab 分隔）：
```
batch_id	job_id	source	status	score	error	completed_at
20260601_001	li_123456	linkedin	done	72	-	2026-06-01T10:23:11
20260601_001	st_789abc	stepstone	failed	-	parse_error	2026-06-01T10:23:45
20260601_001	portal_sap_xxxx	portal_sap	skipped_dup	-	-	2026-06-01T10:24:01
```

**Status 枚举**：`done` / `failed` / `skipped_dup` / `skipped_score` / `pending`

在 `search_state.py` 新增（不修改现有函数）：
```python
BATCH_STATE_TSV = TEMP_DIR / "batch_state.tsv"

def append_batch_state(batch_id: str, job_id: str, source: str,
                       status: str, score: int = -1,
                       error: str = "-") -> None:
    """追加一行到 batch_state.tsv（append-only，不读取）。"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if not BATCH_STATE_TSV.exists():
        BATCH_STATE_TSV.write_text(
            "batch_id\tjob_id\tsource\tstatus\tscore\terror\tcompleted_at\n",
            encoding="utf-8"
        )
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"{batch_id}\t{job_id}\t{source}\t{status}\t{score}\t{error}\t{ts}\n"
    with open(BATCH_STATE_TSV, "a", encoding="utf-8") as f:
        f.write(line)
```

**踩坑**：append-only 设计避免了读写竞争。多线程下只需 `threading.Lock()` 保护 `open(..., "a")`。

#### 步骤 2-B：锁文件

```python
LOCK_FILE = TEMP_DIR / ".search.lock"

def acquire_lock() -> bool:
    """返回 True=获锁成功，False=已有进程在跑。"""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            import psutil
            if psutil.pid_exists(pid):
                return False
        except Exception:
            pass  # psutil 未安装或读取失败，保守返回 False
    LOCK_FILE.write_text(str(os.getpid()))
    return True

def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)
```

**踩坑**：`psutil` 非必需依赖，`except` 分支降级为"不检查存活性"。`setup.ps1` 中加入 `pip install psutil`（soft）。

在 `run_phase2_search.py` 的 `main()` 函数入口和 `finally` 块：
```python
if not acquire_lock():
    print("[ERROR] 另一个搜索进程正在运行，退出。", file=sys.stderr)
    sys.exit(1)
try:
    # ... 现有搜索逻辑 ...
finally:
    release_lock()
```

#### 步骤 2-C：failed_jobs 追踪 + retry

在 `search_history.json` 的 batch 结构新增字段（向后兼容，旧 batch 无此字段时视为 `[]`）：
```json
{
  "batch_id": "20260601_001",
  "failed_jobs": ["li_123456", "portal_sap_xxxx"],
  "retry_count": 0
}
```

新增函数：
```python
def mark_job_failed(batch_id: str, job_id: str) -> None:
    h = load_history()
    b = get_batch(h, batch_id)
    if b is None: return
    b.setdefault("failed_jobs", [])
    if job_id not in b["failed_jobs"]:
        b["failed_jobs"].append(job_id)
    save_history(h)

def get_failed_jobs(batch_id: str) -> list[str]:
    h = load_history()
    b = get_batch(h, batch_id)
    return b.get("failed_jobs", []) if b else []
```

CLI 新增：
```bash
python3 scripts/search_state.py --mode retry-failed --batch-id 20260601_001
```

#### 步骤 2-D：断点续传

`dedup_and_sort()` 已有 `dedup_done` 字段。扩展逻辑：  
如果 `dedup_done=true` 且 `--force` 未指定 → 跳过本 batch，打印提示。

**不修改 `dedup_and_sort()` 函数签名**，只在 CLI `main()` 入口判断：
```python
if get_batch(h, batch_id).get("dedup_done") and not args.force:
    print(f"[skip] {batch_id} 已完成去重，使用 --force 强制重跑")
    sys.exit(0)
```

### 4.4 向后兼容要求

- `load_history()` / `save_history()` 签名不变
- `new_batch_id()` / `get_batch()` / `dedup_and_sort()` 不修改
- 旧批次数据无 `failed_jobs` 字段 → `get_failed_jobs()` 返回 `[]`，不报错
- TSV 文件不存在 → 功能正常，只是无 TSV 记录

### 4.5 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 锁文件在崩溃后遗留 | 中 | 下次运行被错误阻断 | PID 存活检测；`/check` 命令新增锁文件状态检查 |
| TSV 并发写冲突 | 低（主流程单线程写 TSV） | 数据损坏 | `threading.Lock()` 保护；append-only 设计天然安全 |
| `psutil` 未安装 | 中（首次环境） | 锁文件永远报"有进程在跑" | `except` 降级为警告+继续（不阻断） |
| 新增 `failed_jobs` 字段破坏旧 JSON | 无 | — | `.setdefault()` 写法，旧文件兼容 |

### 4.6 验收标准

- [ ] 同时运行两个 `run_phase2_search.py` → 第二个立即退出并打印锁提示
- [ ] 手动向 batch 注入 failed_jobs → `--retry-failed` 仅重跑失败任务
- [ ] `batch_state.tsv` 每次搜索后包含正确状态行
- [ ] 现有测试 `tests/test_core.py` 全部通过（无 breaking change）

---

## 5. M3：申请表单助手（P1-3）

### 5.1 目标

在 Page 2（Job Detail 页）底部增加**折叠式表单助手 Panel**，覆盖两类填表痛点：

1. **开放性问题**（Why do you want to work here?）：Claude agent 读取 `jd_analysis.json` + `cv_parsed` 生成草稿
2. **结构化经历字段**（工作经历/教育经历的雇主名、日期、职位等）：从 `cv_parsed` 提取并渲染为带独立复制按钮的字段卡片，用户点击复制 → 粘贴到 ATS 表单，无需重新打字

**不自动提交，不自动填写**，用户复制粘贴使用。

### 5.2 涉及组件

#### 新增文件

| 文件 | 说明 |
|------|------|
| `config/ats_field_map.yml` | ATS 字段名映射表，键为 ats_type，值为字段标签别名组 |

#### 后端（server.py）
| 端点 | 方法 | 说明 |
|------|------|------|
| `POST /api/form-assist` | 新增 | 接收 job_folder + form_fields → 启动 agent → 返回 SSE 流（开放性问题） |
| `GET /api/form-fields` | 新增 | 返回该职位的结构化字段卡片 JSON（同步，无 SSE） |

`/api/form-assist` 参数结构：
```json
{
  "uid": "leon",
  "job_folder": "group-da_SAP-SE_Product-Analyst-20260601",
  "form_fields": [
    {"label": "Why do you want to work at SAP?", "type": "textarea"},
    {"label": "Describe a data analysis project", "type": "textarea"},
    {"label": "Expected salary", "type": "text"}
  ]
}
```

`/api/form-fields` 返回结构（server.py 读取 cv_parsed + ats_field_map.yml 后静态生成）：
```json
{
  "ats_type": "workday",
  "work_experience": [
    {
      "employer":    {"label": "Employer",    "value": "ECE Group Hamburg"},
      "title":       {"label": "Job Title",   "value": "Working Student Business Development"},
      "start_month": {"label": "Start (MM)",  "value": "09"},
      "start_year":  {"label": "Start (YYYY)","value": "2024"},
      "end_month":   {"label": "End (MM)",    "value": ""},
      "end_year":    {"label": "End (YYYY)",  "value": "Present"},
      "country":     {"label": "Country",     "value": "Germany"},
      "city":        {"label": "City",        "value": "Hamburg"},
      "description_short": {"label": "Description (1-line)", "value": "Supported cross-functional BI reporting..."},
      "description_long":  {"label": "Description (full)",   "value": "Led data pipeline..."}
    }
  ],
  "education": [
    {
      "institution": {"label": "School",      "value": "Hamburg University of Applied Sciences"},
      "degree":      {"label": "Degree",      "value": "Bachelor of Science"},
      "field":       {"label": "Field",       "value": "Business Informatics"},
      "start_year":  {"label": "Start Year",  "value": "2020"},
      "end_year":    {"label": "End Year",    "value": "2024"},
      "gpa":         {"label": "GPA",         "value": "2.1"}
    }
  ]
}
```

#### Agent（.claude/agents/form-assistant.md）
新增 agent，加载数据：
1. `output/{job_folder}/jd_analysis.json` → 职位需求、公司文化、必须技能
2. `output/cv_parsed_{group_id}.json` → 候选人经历、成就、技能
3. `output/{job_folder}/cover_letter_draft.md`（若已存在）→ 引用成段落

输出格式：
```markdown
## 表单填写草稿

### Why do you want to work at SAP?
[200字以内，引用：SAP数字化转型战略 + 候选人在 ECE Group 的 BI 项目经验]

> 参考经历：ECE Group Hamburg — Working Student Business Development (2024)
```

#### 前端（UI/job_detail_page/code.html）
在现有 Job Detail 页最底部（`<apply-button>` 之后）新增，含两个 Tab：

```
┌─────────────────────────────────────────────────────────┐
│ 申请表单助手  [折叠 ▲]                                    │
├──────────────────────┬──────────────────────────────────┤
│  [📋 结构化字段]       │  [✍️ 开放性问题]                   │  ← Tab 切换
├──────────────────────┴──────────────────────────────────┤
│                                                         │
│  ── TAB 1: 结构化字段（工作/教育经历）──────────────────── │
│                                                         │
│  ATS 类型: [Workday ▾]   ← 下拉，读取 ats_field_map.yml  │
│                                                         │
│  工作经历 1 — ECE Group Hamburg                          │
│  ┌────────────────────┬────────────────────┬─────────┐  │
│  │ Employer           │ ECE Group Hamburg  │ [复制]  │  │
│  │ Job Title          │ Working Student... │ [复制]  │  │
│  │ Start (MM/YYYY)    │ 09/2024            │ [复制]  │  │
│  │ End (MM/YYYY)      │ Present            │ [复制]  │  │
│  │ Country            │ Germany            │ [复制]  │  │
│  │ Description (short)│ Supported cross... │ [复制]  │  │
│  │ Description (full) │ Led data pipeli... │ [复制]  │  │
│  └────────────────────┴────────────────────┴─────────┘  │
│                           [复制全部工作经历]               │
│                                                         │
│  教育经历 1 — Hamburg University                         │
│  ┌────────────────────┬────────────────────┬─────────┐  │
│  │ School             │ Hamburg Univ...    │ [复制]  │  │
│  │ Degree             │ Bachelor of Sci... │ [复制]  │  │
│  │ Field              │ Business Inform... │ [复制]  │  │
│  │ Start/End Year     │ 2020 / 2024        │ [复制]  │  │
│  └────────────────────┴────────────────────┴─────────┘  │
│                                                         │
│  ── TAB 2: 开放性问题 ────────────────────────────────── │
│                                                         │
│  粘贴问题（每行一个）：                                   │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Why do you want to work here?                   │    │
│  │ Describe a data analysis project                │    │
│  └─────────────────────────────────────────────────┘    │
│                                           [生成草稿]     │
│  生成结果（流式）：                                       │
│  ┌─────────────────────────────────────────────────┐    │
│  │ ### Why do you want to work here?               │    │
│  │ [AI 生成内容...]                                 │    │
│  └─────────────────────────────────────────────────┘    │
│                                [复制全部]  [清除]        │
└─────────────────────────────────────────────────────────┘
```

### 5.3 分步骤实施

#### 步骤 3-A：form-assistant agent

新建 `.claude/agents/form-assistant.md`：
```markdown
# form-assistant agent

## 触发条件
当 orchestrator 调用 `表单助手 <job_folder>` 或 server.py 通过 /api/form-assist 触发时加载。

## 输入
- job_folder: 职位输出目录路径（相对于 users/{uid}/output/）
- form_fields: 字符串列表，每项为申请表单的一个字段标签

## 执行步骤
1. 读 jd_analysis.json → 提取 company_name, required_skills, culture_keywords, responsibilities
2. 读 cv_parsed_{group_id}.json → 提取 experience[], skills[], education[]
3. 若 cover_letter_draft.md 存在 → 读取前两段作为风格参考
4. 为每个 form_field 生成回答：
   - 引用候选人真实经历中最相关的一条
   - 结合 JD 的核心关键词
   - 英文 ≤150词，中文 ≤120字
   - 标注「引用来源：{公司} - {职位}（{年份}）」
5. 输出 Markdown 格式，每个字段一节

## 禁止
- 不捏造候选人未有过的经历
- 不写超出 cv_parsed 信息范围的技能
```

#### 步骤 3-B：server.py 新增端点

在 `server.py` 的 `Handler.do_POST()` 中新增路由（参考现有 `/api/record` 实现模式）：

```python
elif path == '/api/form-assist':
    self._handle_form_assist(body)
```

`_handle_form_assist()` 实现要点：
- 验证 `job_folder` 路径：必须在 `users/{uid}/output/` 下（`Path.resolve()` + `is_relative_to()` 检查）
- 读取 `jd_analysis.json` 中的 `group_id` 字段，确定对应 `cv_parsed_{group_id}.json`
- 通过 subprocess 调用 claude agent（与现有 `_handle_search()` 的 SSE 模式相同）
- Content-Type: `text/event-stream`

**踩坑**：`server.py:28` 中 `HTML_PATH = Path("C:/Users/Leon/Desktop/...")` 是硬编码路径，M3 实施前需确认此处不影响新端点。新端点路径验证必须用 `Path.resolve().is_relative_to(get_output_dir(uid))` 防注入。

#### 步骤 3-C：前端 Panel 实现

修改 `UI/job_detail_page/code.html`：

1. 在 Apply 按钮后新增折叠 Panel（使用现有 Kinetic Archive 设计系统风格）：
   - `<details><summary>` 原生折叠，无需 JS 框架
   - `<textarea>` 接受表单字段（每行一个）
   - `[生成草稿]` 按钮触发 `fetch('/api/form-assist', {method:'POST', ...})`
   - 结果区域用 SSE `EventSource` 流式渲染

2. 端点调用参数组装：
   ```javascript
   const jobFolder = document.querySelector('[data-job-folder]').dataset.jobFolder;
   const uid = window.__UID__ || 'leon';
   ```

3. 复制按钮：`navigator.clipboard.writeText(resultArea.innerText)`

**踩坑**：现有 `UI/job_detail_page/code.html` 是静态模板，实际运行时由 `server.py` 的 `GET /` 路由动态注入 job 数据。需确认 `server.py` 的 HTML 渲染逻辑中包含 `data-job-folder` 的注入点（Community 4）。

#### 步骤 3-D：CLAUDE.md 新指令
```
| `表单助手 <job编号>` | 为指定职位启动 form-assistant agent，交互式填写申请表单 |
```

#### 步骤 3-E：ATS 字段映射表 + /api/form-fields 端点

**新建 `config/ats_field_map.yml`**（驱动 Tab 1 字段名显示）：

```yaml
# 每种 ATS 类型的字段标签别名
# label: 显示在卡片左列的字段名（匹配该 ATS 表单用词）
# key:   cv_parsed 中对应的 JSON 路径

workday:
  work_experience:
    - key: employer      label: "Employer"
    - key: title         label: "Job Title"
    - key: start_month   label: "Start Month (MM)"
    - key: start_year    label: "Start Year (YYYY)"
    - key: end_month     label: "End Month (MM)"     optional: true
    - key: end_year      label: "End Year (YYYY)"
    - key: country       label: "Country"
    - key: city          label: "City"
    - key: desc_short    label: "Description (1 line)"
    - key: desc_full     label: "Description (full)"
  education:
    - key: institution   label: "School / Institution"
    - key: degree        label: "Degree"
    - key: field         label: "Field of Study"
    - key: start_year    label: "Start Year"
    - key: end_year      label: "End Year"
    - key: gpa           label: "GPA"                optional: true

sap_custom:
  work_experience:
    - key: employer      label: "Unternehmen / Company"
    - key: title         label: "Stelle / Job Title"
    - key: start_month   label: "Von (MM)"
    - key: start_year    label: "Von (JJJJ)"
    - key: end_month     label: "Bis (MM)"           optional: true
    - key: end_year      label: "Bis (JJJJ)"
    - key: country       label: "Land / Country"
    - key: desc_full     label: "Aufgaben / Responsibilities"
  education:
    - key: institution   label: "Bildungseinrichtung"
    - key: degree        label: "Abschluss"
    - key: field         label: "Fachrichtung"
    - key: start_year    label: "Von (JJJJ)"
    - key: end_year      label: "Bis (JJJJ)"

greenhouse:
  work_experience:
    - key: employer      label: "Company"
    - key: title         label: "Title"
    - key: start_month   label: "Start Month"
    - key: start_year    label: "Start Year"
    - key: end_month     label: "End Month"          optional: true
    - key: end_year      label: "End Year"
    - key: desc_full     label: "Job Description"
  education:
    - key: institution   label: "School"
    - key: degree        label: "Degree"
    - key: field         label: "Discipline"
    - key: start_year    label: "Start Year"
    - key: end_year      label: "End Year"
```

**server.py 新增 `GET /api/form-fields` 路由**（在 `Handler.do_GET()` 中）：

```python
elif path.startswith('/api/form-fields'):
    uid        = params.get("uid", _current_user)
    job_folder = params.get("job_folder", "")
    ats_type   = params.get("ats_type", "workday")
    self._handle_form_fields(uid, job_folder, ats_type)
```

`_handle_form_fields()` 实现要点：
1. 路径验证（同 `/api/form-assist`，`is_relative_to()` 检查）
2. 读取 `cv_parsed_{group_id}.json` → 提取 experience[]、education[]
3. 加载 `config/ats_field_map.yml` 中对应 ats_type 的字段配置
4. 拼装 JSON 响应（见 5.2 返回结构）
5. 同步返回，无 SSE，响应约 5ms

**前端 Tab 1 初始化逻辑**（页面加载时自动请求）：

```javascript
// 页面打开时自动加载结构化字段卡片
async function loadFormFields() {
  const atsType = document.getElementById('ats-type-select').value;
  const res = await fetch(`/api/form-fields?uid=${uid}&job_folder=${jobFolder}&ats_type=${atsType}`);
  const data = await res.json();
  renderFieldCards(data);  // 渲染字段卡片 + [复制] 按钮
}

// 每个 [复制] 按钮
function copyField(value) {
  navigator.clipboard.writeText(value);
  // 短暂显示 "✓ 已复制" 反馈（300ms 后恢复）
}
```

**踩坑**：`cv_parsed` 中日期格式可能是 `"2024-09"` 或 `"September 2024"` 等多种形式。  
`_handle_form_fields()` 需在组装时做日期格式转换（按 ats_type 的 date_format 字段）：
- Workday: `MM/YYYY`（`"2024-09"` → `"09/2024"`）
- SAP: `MM.YYYY`（`"2024-09"` → `"09.2024"`）
- Greenhouse: 分开的 month select + year input

**踩坑**：`end_year: "Present"` 需对应 ATS 的"至今"写法——Workday 是留空 end_month/year + 勾选 "Current"，SAP 是 `"aktuell"`。字段卡片的 `end_year` 行要在旁边加注：`(Workday: 留空 + 勾 "I currently work here")`。

### 5.4 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| `jd_analysis.json` 不存在（Phase 2 未运行） | 中 | Panel 无法生成内容 | 前端检测：`data-jd-analyzed` 属性缺失时显示「请先运行 Phase 2 分析」 |
| 路径遍历攻击（`../../etc/passwd`） | 低但高危 | 泄露系统文件 | 强制 `Path.resolve().is_relative_to()` 检查，`/api/form-fields` 同样需要 |
| SSE 连接在长生成过程中断开 | 中 | 用户看到不完整草稿 | 生成完成后输出完整 Markdown 作为 `event: complete` 消息 |
| `cv_parsed_{group_id}.json` group_id 提取错误 | 低 | 使用错误 CV | 从 `jd_analysis.json` 的 `group_id` 字段读取，不从路径名推断 |
| cv_parsed 日期格式不统一（多种来源格式） | 高 | 字段卡片显示原始字符串，ATS 不接受 | `_handle_form_fields()` 内置日期解析器，支持 `YYYY-MM`、`Month YYYY`、`MM.YYYY` 三种输入格式 |
| "Present"/"aktuell" end_date 在 ATS 字段卡片误导用户 | 中 | 用户直接粘贴被 ATS 拒绝 | 卡片 end_date 行显示值 + 灰色注释：`(Workday: 留空 + 勾选 "I currently work here")` |
| ats_field_map.yml 未配置用户遇到的 ATS 类型 | 中 | Tab 1 显示为空 | 下拉新增 "Other/Unknown"：显示通用字段（employer/title/dates），无字段名别名 |

### 5.5 验收标准

- [ ] Page 2 底部显示「申请表单助手」折叠面板，含两个 Tab
- [ ] Tab 1（结构化字段）：切换 ATS 类型为 Workday → 字段标签变为英文；切换为 SAP → 标签变为德文
- [ ] Tab 1 每个 [复制] 按钮点击后显示「✓ 已复制」300ms 反馈
- [ ] Tab 1 日期字段：cv_parsed 中 `"2024-09"` → Workday 卡片显示 `"09/2024"`，SAP 显示 `"09.2024"`
- [ ] Tab 2（开放性问题）：粘贴 3 个表单字段 → 点击「生成草稿」→ 流式输出 3 段回答
- [ ] 每段回答包含「引用来源」标注，来源必须在 cv_parsed 中存在
- [ ] 「复制全部」正确复制完整 Markdown 文本
- [ ] 路径验证：`/api/form-fields` 传入 `../../../config.json` 返回 400 错误

---

## 6. M4：职位合法性检测（P3-1）

### 6.1 目标

在 `jd-analyzer` agent 的输出中新增 `legitimacy` 评估字段，检测幽灵职位、长期挂机职位、JD 质量过低等风险信号。Dashboard 和 Job Detail 页显示合法性标记。

**v2.1 新增两个数据源（career-ops Block G 对标）：**
1. **重复发帖检测**：跨 batch 扫描 `search_history.json`，发现同公司相似职位重复出现 → 幽灵职位信号。零额外成本，数据已有。
2. **公司裁员/招聘冻结 WebSearch**：仅对 match_score ≥ 50 且不在白名单的公司触发，避免浪费配额。

### 6.2 修改文件

| 文件 | 改动 | Graph 社区 |
|------|------|-----------|
| `.claude/agents/jd-analyzer.md` | 新增 legitimacy 评估 + 重复检测步骤 + WebSearch 触发条件 | Community 0 |
| `.claude/agents/jd-analyzer.md` frontmatter | 新增 `WebSearch` 工具（条件触发） | Community 0 |
| `.claude/skills/jd-scoring/` | 新增合法性评分维度（含 repost + hiring_signal） | Skills Layer |
| `scripts/server.py:parse_jobs()` | 读取 legitimacy 字段（含 repost_info + hiring_signal） | Community 4 |
| `UI/job_tracker_dashboard_desktop/code.html` | 新增合法性列/标记 + 🔁 重复发帖图标 | Community 2 |
| `UI/job_detail_page/code.html` | 新增合法性详情展示 | Community 2 |

### 6.3 jd_analysis.json 新增字段

向后兼容：旧文件无此字段时 UI 显示「未评估」。

```json
{
  "legitimacy": {
    "verdict": "CAUTION",
    "score": 58,
    "signals": {
      "jd_quality": 90,
      "posting_freshness": 80,
      "company_verifiable": 95,
      "requirements_realistic": 70,
      "contact_info_present": 60,
      "repost_freshness": 30,
      "company_stability": 60
    },
    "red_flags": [
      "同一职位在 batch 20260501_001 已出现（重复发帖，已 31 天）"
    ],
    "repost_info": {
      "detected": true,
      "count": 2,
      "first_seen_batch": "20260501_001",
      "days_since_first": 31,
      "similar_titles": ["Marketing Analyst", "Marketing Data Analyst"]
    },
    "hiring_signal": {
      "verdict": "neutral",
      "evidence": "No layoff or hiring freeze news found for this company in 2025",
      "search_executed": true,
      "search_skipped_reason": null
    }
  }
}
```

### 6.4 分步骤实施

#### 步骤 4-A：jd-analyzer frontmatter 新增 WebSearch 工具

```yaml
---
name: jd-analyzer
tools:
  - Read
  - Write
  - WebSearch   # 新增：仅在 match_score >= 50 且公司不在白名单时触发
---
```

#### 步骤 4-B：5 维基础评分（原有逻辑不变）

```markdown
评分维度（各 0-100）：
1. jd_quality:            <200字=20；200-500字=60；>500字有结构=90
2. posting_freshness:     0-7天=100；8-30天=80；31-90天=50；>90天=20；无日期=50
3. company_verifiable:    知名企业=100；仅缩写/无法识别=30
4. requirements_realistic:要求技能数≤10且合理=90；>15且含矛盾=30
5. contact_info_present:  有申请按钮/邮箱=100；无=20
```

#### 步骤 4-C：重复发帖检测（新增，career-ops Block G 信号 4）

数据来源：**本地 `output/search_history.json`，零额外成本。**

```markdown
### 重复发帖检测步骤

1. 读取 output/search_history.json → 获取所有 batch 的 raw_results_file 路径
2. 排除当前 batch_id
3. 对每个历史 batch 读取 raw_results_<batch_id>.json → 提取 (company, title) 列表
4. 标题归一化：小写 + 去除 [junior/senior/lead/manager/head/director] + 去除城市名
5. 用 SequenceMatcher 比较当前 JD 的 (company, normalized_title)，ratio ≥ 0.80 = 重复

repost_freshness 评分：
- 未重复 → 100
- 重复 1 次，距今 ≤ 30 天 → 60（可能正常刷新发布）
- 重复 1 次，距今 > 30 天 → 30（幽灵职位风险）
- 重复 ≥ 2 次，任意时间 → 10（高度可疑）

容错：raw_results 文件不存在（已清理）→ 跳过该 batch，repost_info.detected=false
```

**踩坑**：`search_history.json` 存的是文件路径引用，实际 job 列表在 `output/temp/raw_results_<batch_id>.json`。jd-analyzer 通过 `search_history.batches[].raw_results_file` 找到路径，再 Read 该文件。若文件已删除则跳过，不阻断分析。

#### 步骤 4-D：公司招聘信号 WebSearch（新增，career-ops Block G 信号 3）

```markdown
### 公司招聘信号检测（触发条件：match_score ≥ 50 且公司不在白名单）

白名单（stability assumed）：
  SAP, Siemens, Capgemini, Hapag-Lloyd, Aldi, BMW, Mercedes-Benz, Bosch,
  Deutsche Bank, Allianz, BASF, Bayer, Volkswagen, DHL, Lufthansa, Zalando,
  Otto, Beiersdorf, Airbus, Daimler, Continental

触发时执行（公司名预处理：去除 GmbH/AG/SE/Ltd/GmbH & Co. KG）：
  WebSearch: "{company_name}" layoffs 2025
  WebSearch: "{company_name}" hiring freeze 2025

company_stability 评分：
- 结果含 layoffs/hiring freeze/Stellenabbau/restructuring → 20
- 结果含 expanding/new office/growth/we are hiring → 90
- 无相关结果 → 60（neutral）
- 白名单公司（跳过搜索）→ 80

缓存：同一 company 在当次 session 内只搜一次（_company_signal_cache[company] = result）
     避免同公司多个职位重复消耗 WebSearch 配额
```

**阻断缺口 3 解决方案：`_company_signal_cache` 归属与实现（M4 + M6 共用）**

jd-analyzer 是 LLM agent，每次调用是独立进程，无法在内存中共享 Python dict。缓存必须通过**临时文件**实现，由 `run_phase2_search.py` 的同一次运行共享：

```python
# 缓存文件路径（与 batch_state.tsv 同目录）
COMPANY_CACHE_PATH = TEMP_DIR / ".company_signal_cache.json"

# jd-analyzer agent 在执行 WebSearch 前读取此文件（Read 工具）
# 执行 WebSearch 后将结果追加写入（Write 工具，原子更新）
```

jd-analyzer.md 中需明确以下流程：

```markdown
### 公司信号缓存读写流程（WebSearch 前必执行）

1. 尝试 Read output/temp/.company_signal_cache.json
   - 文件不存在 → 视为空缓存 {}，继续
   - 文件存在 → 解析为 JSON dict

2. 检查 cache[company_name] 是否存在：
   - 存在 → 直接使用缓存值，跳过 WebSearch
   - 不存在 → 执行 WebSearch（M4 的 hiring signal + M6 的 kununu 均写入此缓存）

3. WebSearch 完成后：
   - 读取最新 .company_signal_cache.json（防止并发写入覆盖）
   - 追加本次结果：cache[company_name] = { hiring: {...}, kununu: {...} }
   - Write 回 output/temp/.company_signal_cache.json

4. 缓存生命周期：Phase 2 搜索开始时由 run_phase2_search.py 清空（删除旧文件）
   Phase 2 结束后文件保留，可供调试查看
```

**并发安全**：jd-analyzer 并行上限已设 3，且每次写入前先读取最新内容再合并，最坏情况是同一公司被搜索 2-3 次（并发窗口内），可接受。

**M6 集成**：M6 步骤 6-B 的 kununu WebSearch 结果写入 `cache[company]["kununu"]`，M4 的 hiring signal 写入 `cache[company]["hiring"]`，两者共用同一缓存文件，互不干扰。

#### 步骤 4-E：7 维合并评分公式

```
score = round(
  jd_quality×0.25 + posting_freshness×0.15 + company_verifiable×0.15
  + requirements_realistic×0.10 + contact_info_present×0.10
  + repost_freshness×0.15 + company_stability×0.10
)
verdict：≥75→HIGH_CONFIDENCE；50-74→CAUTION；<50→SUSPICIOUS
```

#### 步骤 4-F：server.py 读取扩展字段

```python
legitimacy = jd.get("legitimacy", {})
job["legitimacy_verdict"] = legitimacy.get("verdict", "UNKNOWN")
job["legitimacy_score"]   = legitimacy.get("score", -1)
job["legitimacy_flags"]   = legitimacy.get("red_flags", [])
job["legitimacy_repost"]  = legitimacy.get("repost_info", {}).get("detected", False)
job["legitimacy_hiring"]  = legitimacy.get("hiring_signal", {}).get("verdict", "unknown")
```

#### 步骤 4-G：Dashboard UI 标记

- `HIGH_CONFIDENCE` → 无标记（静默通过）
- `CAUTION` → 🟡 + tooltip 显示 red_flags
- `SUSPICIOUS` → 🔴 + 默认折叠
- `UNKNOWN`（旧数据）→ ⚪
- `repost_info.detected = true` → 额外 🔁 图标 + tooltip 显示首次出现 batch 和天数
- `hiring_signal.verdict = "negative"` → 额外 ⚠️ 图标

筛选器新增「隐藏可疑职位」checkbox（默认开启）。

### 6.5 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| raw_results 文件不存在（已清理）导致检测崩溃 | 中 | jd-analyzer 报错 | 文件读取失败 → 跳过该 batch，不阻断，repost_info.detected=false |
| 标题归一化后误判不同职位为重复（如 "Analyst" 过于通用） | 中 | 误报重复 | ratio 阈值设 0.80，同时要求 company 名完全匹配才触发 |
| WebSearch 配额耗尽（高并发分析） | 低 | company_stability 无法获取 | 并行上限已设 3；配额耗尽时降级 verdict="neutral"，不报错 |
| 公司名含特殊字符（& / 括号）导致 WebSearch 无结果 | 中 | company_stability 误报 neutral | 搜索前去除 GmbH/AG/SE 等法律后缀；& → and |
| freshness 误判（无 date_posted） | 高 | score 偏低 | date_posted 缺失时 posting_freshness=50（中性）|
| 新字段导致旧测试失败 | 中 | test_core.py 报错 | `parse_jobs()` 全程 `.get("legitimacy", {})` 防御读取 |

### 6.6 验收标准

- [ ] JD < 200字 的职位：`legitimacy.score` 低，`red_flags` 含「JD 过短」
- [ ] SAP/Siemens 职位：`legitimacy.verdict = "HIGH_CONFIDENCE"`，`hiring_signal.search_skipped_reason = "Whitelisted employer — stability assumed"`
- [ ] 同一职位在上一 batch 出现过：`repost_info.detected = true`，Dashboard 显示 🔁
- [ ] match_score < 50 的职位：`hiring_signal.search_skipped_reason` 非空，无 WebSearch 调用
- [ ] Dashboard「隐藏可疑职位」勾选时，SUSPICIOUS 职位消失
- [ ] 旧 `jd_analysis.json`（无 legitimacy 字段）在 Dashboard 显示为⚪，不报错

---

## 7. M5：技能缺口分级 + CV 优化潜力（career-ops Block B + E 对标）

### 7.1 目标

**Block B 对标**：`missing_skills` 从平铺字符串列表升级为结构化对象，每项标注严重度（hard_blocker / nice_to_have / learnable）和应对方案。Dashboard 显示放弃信号，cv-writer 利用相邻技能做针对性措辞。

**Block E 对标**：新增 `customization_potential` 字段，评估"这份 CV 针对这岗位还能优化多少分"，并列出 Top 3-5 具体改动建议。cv-writer 执行改动后在 `cv_changes.md` 记录改前/改后对比和预期提升分。

### 7.2 修改文件

| 文件 | 改动 | Graph 社区 |
|------|------|-----------|
| `.claude/agents/jd-analyzer.md` | 步骤 2 扩展：missing_skills 结构化 + 步骤新增 customization_potential 计算 | Community 0 |
| `.claude/agents/cv-writer.md` | 读取 `top_changes` 逐条执行，cv_changes.md 记录 score_boost | Community 0 |
| `scripts/server.py:parse_jobs()` | 读取 gap_summary + customization_potential.estimated_max_score | Community 4 |
| `UI/job_tracker_dashboard_desktop/code.html` | hard_blockers > 0 显示 🔴 旗帜；显示优化后预测分 | Community 2 |

### 7.3 jd_analysis.json 新增字段

```json
{
  "missing_skills": [
    {
      "skill": "Airflow",
      "severity": "learnable",
      "weeks_to_acquire": 4,
      "adjacent_in_cv": "Luigi pipeline orchestration at ECE Group",
      "mitigation": "Cover letter: 'proven pipeline orchestration with Luigi; Airflow ramp-up in 2 weeks'"
    },
    {
      "skill": "Security clearance",
      "severity": "hard_blocker",
      "weeks_to_acquire": null,
      "adjacent_in_cv": null,
      "mitigation": null
    },
    {
      "skill": "Power BI",
      "severity": "nice_to_have",
      "weeks_to_acquire": 2,
      "adjacent_in_cv": "Tableau and Looker Studio in current CV",
      "mitigation": "Reframe: 'BI tool agnostic — Tableau/Looker, Power BI ramp-up in days'"
    }
  ],
  "gap_summary": {
    "hard_blockers": 1,
    "nice_to_have": 1,
    "learnable": 1,
    "blocker_flag": true
  },
  "customization_potential": {
    "current_match_score": 65,
    "estimated_max_score": 82,
    "score_gap": 17,
    "top_changes": [
      {
        "rank": 1,
        "target": "Experience → ECE Group, bullet 2",
        "issue": "JD uses 'stakeholder reporting' 4x; CV says 'internal reporting'",
        "reframe": "Change 'internal reporting' → 'cross-functional stakeholder reporting'",
        "score_boost": 5
      },
      {
        "rank": 2,
        "target": "Skills section",
        "issue": "Tableau appears 3x in JD, not in top 3 skills",
        "reframe": "Move Tableau to position 2 in Skills list",
        "score_boost": 4
      },
      {
        "rank": 3,
        "target": "Summary paragraph",
        "issue": "JD emphasizes 'data-driven decision making' 5x; Summary does not use this phrase",
        "reframe": "Add 'data-driven decision making' to Summary opening",
        "score_boost": 3
      }
    ]
  }
}
```

向后兼容：旧 `missing_skills` 为字符串列表时，`parse_jobs()` 检测 `isinstance(item, str)` 降级处理，不崩溃。

### 7.4 分步骤实施

#### 步骤 5-A：jd-analyzer 步骤 2 扩展（missing_skills 结构化）

在现有步骤 2 完成 match_score 后，对每个 `missing_skills` 条目追加严重度分析：

```markdown
### missing_skills 严重度分类（新增，career-ops Block B 对标）

对每个 missing skill 按以下规则分类：

hard_blocker（放弃信号）：
- JD 含「zwingend」「must have」「required」且该技能无任何相邻可替代经验
- 证照/许可类（Sicherheitsüberprüfung、PMP、CISSP 等）且 JD 标注 required
- 领域排他性（「Pharma industry experience required」且候选人完全无相关背景）

nice_to_have（相邻覆盖）：
- JD 含「nice to have」「preferred」「von Vorteil」
- 同概念不同工具：Airflow ↔ Luigi/Prefect；Tableau ↔ Looker；React ↔ Vue
- 框架变体：GA4 ↔ Google Analytics；AWS ↔ GCP（同类云平台）

learnable（4-8 周可补）：
- API 语法、新 BI 工具变体、次要 domain 扩展
- 候选人有明确学习路径（现有 CV 有强基础）

adjacent_in_cv：从 cv_parsed.experience[] 和 cv_parsed.skills[] 中找最相关的一条
mitigation：生成一句话（英文），适合在 Cover Letter 或面试中使用
```

#### 步骤 5-B：jd-analyzer 新增步骤：customization_potential 计算

在输出 `jd_analysis.json` 之前，额外计算：

```markdown
### Customization Potential（新增，career-ops Block E 对标）

对比 JD 高频词（出现 ≥3 次）与 cv_parsed 中的用词：
1. 如果 JD 高频词在 CV 中用了近义词或更宽泛词 → Reframe 建议（score_boost: 3-5）
2. 如果 JD 高频词在 Skills 列表中存在但排在第 5 位以后 → Reorder 建议（score_boost: 2-4）
3. 如果 JD 强调量化指标词（revenue, conversion, reduction, %）而对应 CV bullet 无数字 → Quantify 建议（score_boost: 2-3）
4. 如果 nice_to_have 技能在候选人 CV 有相邻经验 → Reframe as strength 建议（score_boost: 3-5）
5. Summary 段缺少 JD 出现 ≥4 次的关键动词 → Keyword insertion 建议（score_boost: 2-3）

estimated_max_score = current_match_score + Σ(top 5 changes 的 score_boost)
最多输出 5 条 top_changes，按 score_boost 降序排列。
```

#### 步骤 5-C：cv-writer 改写逻辑升级

修改 `cv-writer.md` 步骤 2：

```markdown
## 改写顺序（升级后）

1. 读取 customization_potential.top_changes（若存在）
2. 按 rank 顺序逐条执行：
   - rank 1-5 的每条改动：
     a. 找到 target 指定的 CV 段落/条目
     b. 执行 reframe（措辞替换，不改含义）
     c. 在 cv_changes.md 记录：「[改动N] {target}："{改前}" → "{改后}" (预计 +{score_boost}分)」
3. 若 customization_potential 不存在（旧版数据）→ 使用原有 recommended_emphasis 逻辑（向后兼容）
4. 完成后在 cv_changes.md 末尾追加：
   「预计优化后匹配分：{estimated_max_score}（原始：{current_match_score}）」
```

#### 步骤 5-D：Dashboard 新增放弃信号和优化潜力显示

1. **hard_blockers > 0** → 该行显示 🔴 旗帜（比 legitimacy 更直接的放弃信号），hover 显示 blocker skill 名称
2. **customization_potential 存在** → M-Score 旁显示 `65 → 82↑` 小箭头（点击展开 top_changes 列表）
3. 筛选器新增「隐藏硬缺口职位」checkbox（默认关闭，用户可选）

### 7.5 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 旧 `missing_skills` 为字符串列表导致解析失败 | 高（所有旧文件） | server.py 报错 | `parse_jobs()` 检测 `isinstance(item, str)` 降级为 `{"skill": item, "severity": "unknown"}` |
| hard_blocker 误判（LLM 过于保守） | 中 | 优质职位被标放弃 | blocker 规则仅对含「zwingend/must have + 无相邻经验」才触发；「required」单独不触发 |
| customization_potential.score_boost 过于乐观 | 中 | 用户期望落差 | score_boost 上限单条 8 分，总上限 estimated_max_score ≤ current + 25 |
| cv-writer 读到 customization_potential 但找不到 target 段落 | 低 | 改动静默跳过 | 若 target 段落不存在，记录 `[跳过] {target} 未找到对应段落`，不报错 |

### 7.6 验收标准

- [ ] 对含「must have」且无相邻经验的技能：`severity = "hard_blocker"`，`mitigation = null`
- [ ] 对 Tableau/Power BI 此类同类工具：`severity = "nice_to_have"`，`adjacent_in_cv` 非空
- [ ] Dashboard 对 hard_blockers > 0 的职位显示 🔴 旗帜
- [ ] cv_changes.md 末尾包含「预计优化后匹配分」一行
- [ ] 旧 `missing_skills` 字符串列表 → Dashboard 正常显示，不报错
- [ ] `estimated_max_score` 不超过 `current_match_score + 25`

---

## 8. M6：薪资研究 + kununu 公司画像（P3-3）

### 8.1 目标

career-ops Block D 用 WebSearch（Glassdoor/Levels.fyi/Blind）做薪资研究，但针对德国市场覆盖不足。JobiT M6 以 **kununu**（德国最大职场评分平台，隶属 XING）为核心数据源，补充：
1. **薪资区间**：kununu 薪资 + StepStone Gehaltsreport（校验）
2. **公司文化画像**：kununu 5 维评分（总体 / WLB / 薪资公平 / 文化 / 晋升）+ 员工评论摘要
3. **JD 文本文化信号**：零 WebSearch 成本，从 JD 提取成长/WLB/团队/文化关键词

M6 完成后，`decision_score` 中 `industry_fit`（0.05，信号弱）→ `company_culture_fit`（0.10，kununu 驱动），提升决策精度。

### 8.2 修改文件

| 文件 | 改动 | Graph 社区 |
|------|------|-----------|
| `.claude/agents/jd-analyzer.md` | 新增 company_profile 步骤（JD 文化信号提取 + WebSearch 触发） | Community 0 |
| `scripts/server.py:parse_jobs()` | 读取 company_profile 字段 | Community 4 |
| `UI/job_detail_page/code.html` | 新增「公司画像」区块（kununu 评分 + 薪资区间 + 文化标签） | Community 2 |
| `UI/job_tracker_dashboard_desktop/code.html` | kununu 总分 badge（可选，轻量展示） | Community 2 |

### 8.3 jd_analysis.json 新增字段

```json
{
  "company_profile": {
    "kununu": {
      "overall": 3.8,
      "wlb": 3.5,
      "salary_fairness": 3.2,
      "culture": 4.0,
      "career_growth": 3.6,
      "sample_size": 412,
      "top_pro": "Flexible Arbeitszeiten, gutes Teamklima",
      "top_con": "Wenig Gehaltstransparenz, langsame Entscheidungsprozesse"
    },
    "salary_research": {
      "estimated_range_eur": [55000, 72000],
      "market_median_eur": 63000,
      "vs_expectation": "within_range",
      "data_quality": "medium",
      "sources": ["kununu (28 Gehaltsmeldungen)", "Glassdoor (12 samples)"]
    },
    "jd_culture_signals": {
      "growth":  ["learning budget mentioned", "internal promotion path described"],
      "wlb":     ["30 days Urlaub", "flexible hours", "home office 2x/week"],
      "team":    ["team of 8", "reports to Head of Marketing", "cross-functional"],
      "culture": ["flat hierarchy", "agile", "international team"]
    },
    "search_executed": true,
    "search_skipped_reason": null
  }
}
```

`vs_expectation` 枚举：`above_expectation` / `within_range` / `below_expectation` / `unknown`

### 8.4 分步骤实施

#### 步骤 6-A：JD 文化信号提取（零 WebSearch 成本）

在 jd-analyzer 步骤 1（提取 JD 关键信息）末尾追加：

```markdown
### JD 文化信号提取（company_profile.jd_culture_signals）

提取触发词（中英文均支持）：

growth 信号词：
  "learning budget", "Weiterbildungsbudget", "conference", "certification support",
  "promotion path", "career development", "grow into", "leadership track",
  "Aufstiegsmöglichkeiten", "interne Beförderung"

wlb 信号词：
  "Urlaub", "vacation days", "Jahresurlaub", "flexible hours", "Gleitzeit",
  "home office", "remote", "Teilzeit möglich", "part-time", "work-life balance"

team 信号词：
  "team of X", "team of [数字]", "report to", "berichten an", "cross-functional",
  "work with X engineers/designers", "squad", "chapter"

culture 信号词：
  "flat hierarchy", "flache Hierarchien", "agile", "startup culture",
  "international team", "diverse", "autonomous", "Eigenverantwortung", "open-door policy"

每类最多输出 3 条，格式为原文句子片段（≤ 20 词）
```

#### 步骤 6-B：kununu + 薪资 WebSearch（条件触发）

触发条件（同时满足）：
- `match_score ≥ 60` AND `decision_score ≥ 60`（双高分才值得深度调研）
- 同一公司在 Phase 2 运行内只搜一次，通过 **`output/temp/.company_signal_cache.json`** 共享（与 M4 缓存文件相同，缓存 key 为 `company_name`，M6 写入 `cache[company]["kununu"]`，M4 写入 `cache[company]["hiring"]`）

```markdown
### kununu + 薪资研究执行步骤

公司名预处理：去除 GmbH / AG / SE / GmbH & Co. KG / Ltd，& → and

WebSearch 1（kununu 评分）：
  query: "kununu {company_name} Bewertung Mitarbeiter"
  提取：总体评分（x.x/5）、WLB 评分、薪资公平、Kultur、Karriere 评分
  提取：sample_size（"X Bewertungen"）
  提取：top_pro（最高赞 Pro 评论，≤ 25 词）
  提取：top_con（最高赞 Contra 评论，≤ 25 词）
  若无 kununu 结果 → kununu 对象所有字段设 null，不报错

WebSearch 2（薪资区间）：
  query: "{company_name} {job_title} Gehalt Germany"
  优先匹配：kununu Gehaltsreport > Glassdoor > Stepstone 薪资页
  提取：年薪区间（€）、样本量
  样本量 < 5 条 → data_quality="low"，estimated_range 不输出（避免误导）
  数据年份 > 2 年 → data_quality="stale"

WebSearch 3（可选，仅 match_score ≥ 75 的高意向职位）：
  query: "{company_name} {job_title} salary site:levels.fyi"
  用于补充 tech 公司 total compensation 数据
```

**踩坑**：kununu 搜索结果有时返回 XING 聚合页而非 kununu 直接评分页。提取逻辑需同时处理 `kununu.com` 和 `xing.com/companies/` 两种 URL 格式，评分格式均为 `x.x/5`。

#### 步骤 6-C：company_culture_fit 替换 industry_fit（M0a 升级）

M6 完成后，在 jd-analyzer 的 decision_score 计算段更新：

```markdown
### company_culture_fit（替换 industry_fit，M6 完成后生效）

权重：0.10（原 industry_fit 0.05 → 升权并改数据源）

若 company_profile.kununu 数据存在：
  company_culture_fit = round(
    (kununu.overall/5×100)×0.40
    + (kununu.wlb/5×100)×0.30
    + (kununu.career_growth/5×100)×0.30
  )

若 kununu 无数据：
  - jd_culture_signals 有 wlb ≥ 2 条 → 65（JD 文本正面信号）
  - jd_culture_signals 有 wlb 0 条 → 50（中性）
  - preferred_domains 行业匹配（原 industry_fit 逻辑）→ 最低兜底

decision_score 权重重分配（M6 后）：
  level_fit×0.25 + location_fit×0.20 + work_mode_fit×0.15
  + posting_freshness×0.10 + compensation_fit×0.10
  + job_family_fit×0.15 + company_culture_fit×0.10 - industry_fit 移除（0.05→0.00）
  ＝ 总计 1.05 → 调整：posting_freshness 0.10→0.05，总计 = 1.00
```

**踩坑**：权重重分配需同步更新 jd-analyzer.md 的公式和 Dashboard tooltip 的维度说明。

#### 步骤 6-D：「公司画像」区块

在 `UI/job_detail_page/code.html` 的 Job Info 区域（标题 / 公司 / 地点下方）新增折叠区块：

```
┌──────────────────────────────────────────────────────────┐
│ 公司画像  [折叠 ▼]                                         │
├──────────────────────────────────────────────────────────┤
│  kununu: ★3.8  WLB ★3.5  文化 ★4.0  晋升 ★3.6           │
│  "412 Bewertungen · Flexible Arbeitszeiten 👍"            │
│  "Wenig Gehaltstransparenz 👎"                            │
├──────────────────────────────────────────────────────────┤
│  薪资区间: €55K–72K/年  (市场中位 €63K)                    │
│  vs 期望薪资: ✅ 在预期范围内  [来源: kununu 28条]          │
├──────────────────────────────────────────────────────────┤
│  JD 文化信号:                                              │
│  🌱 成长: learning budget, internal promotion path        │
│  ⚖️  WLB: 30 days Urlaub, home office 2x/week            │
│  👥 团队: team of 8, cross-functional, reports to HoM    │
│  🏢 文化: flat hierarchy, agile, international           │
└──────────────────────────────────────────────────────────┘
```

- kununu 无数据时该区块显示「暂无评分数据」，JD 文化信号仍正常显示
- 薪资区间：绿色（within/above）/ 橙色（below）/ 灰色（unknown）
- 折叠状态与表单助手 Panel 独立控制

#### 步骤 6-E：server.py parse_jobs() 扩展

```python
profile = jd.get("company_profile", {})
job["kununu_overall"]     = (profile.get("kununu") or {}).get("overall", -1)
job["kununu_wlb"]         = (profile.get("kununu") or {}).get("wlb", -1)
job["salary_range"]       = (profile.get("salary_research") or {}).get("estimated_range_eur", [])
job["salary_vs_expect"]   = (profile.get("salary_research") or {}).get("vs_expectation", "unknown")
job["culture_signals"]    = profile.get("jd_culture_signals", {})
```

### 8.5 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| kununu 搜索返回 XING 聚合页，评分格式不同 | 中 | 提取失败 | 同时匹配 `kununu.com` 和 `xing.com/companies/` 两种格式的评分 xpath |
| kununu 小公司（<50 员工）无评分数据 | 高 | kununu 对象全 null | null 时降级使用 JD 文化信号计算 company_culture_fit，不输出「无数据」错误 |
| 薪资区间样本量 < 5 → 数据不可信 | 中 | 误导用户 | data_quality="low" 时前端不显示具体数字，仅显示「样本不足」 |
| company_culture_fit 权重升至 0.10 导致 decision_score 偏高 | 低 | 评分膨胀 | M6 实施后对 20 个历史职位回测，确认分布合理 |
| WebSearch 配额与 M4 共享导致双模块竞争 | 中 | 某模块搜索被跳过 | M4 和 M6 共用 `_company_signal_cache`：M4 搜到的 hiring_signal 结果同时写入 M6 缓存，避免重复调用 |

### 8.6 验收标准

- [ ] SAP 职位：`company_profile.kununu.overall` 非 null，`sample_size ≥ 100`
- [ ] 小型初创公司（无 kununu 数据）：`kununu = null`，`jd_culture_signals` 仍正常提取
- [ ] Job Detail 页「公司画像」折叠区块正常显示 kununu 评分 + 薪资区间
- [ ] 薪资 data_quality="low" 时前端不显示具体数字
- [ ] match_score < 60 的职位：`search_skipped_reason` 非空，无 WebSearch 调用
- [ ] M6 完成后：decision_score 计算从 `industry_fit×0.05` 切换到 `company_culture_fit×0.10`

---

---

## 9. M7：面试准备 Agent + STAR+R 故事库（career-ops Block F 对标）

### 9.1 目标与风险评估

**目标**：实现 career-ops Block F 的 JobiT 版本——维护用户的持久化 STAR+R 故事库，并为每个职位生成定制面试准备文档。

**风险评估**：

| 维度 | 评级 | 说明 |
|------|------|------|
| 技术复杂度 | 低 | 纯 agent 文件 I/O，无新 Python 基础设施，无 server.py 改动 |
| 依赖耦合度 | 低-中 | 硬依赖已有（cv_parsed / jd_analysis），软依赖（M0a/M5）优雅降级 |
| 数据安全风险 | 低 | 故事内容来自 cv_parsed，「不捏造」规则与 cv-writer 一致 |
| 维护成本 | 低 | story-bank.md 是人类可读 Markdown，用户可直接编辑修正 |
| 关键坑 | 中 | 故事库增长后 LLM 可能生成重复故事；dedup 检查是唯一防线 |

### 9.2 子模块拆分

**M7a：Story Bank Bootstrap（一次性初始化）**
- 触发：用户第一次调用 interview-prep，且 `story-bank.md` 不存在
- 输入：`cv_parsed_{group_id}.json`（所有 group 的 cv_parsed）
- 输出：`users/{uid}/interview-prep/story-bank.md`（5-8 个初始故事）
- 工作量：~1 天

**M7b：Per-job Interview Prep（每次职位面试准备）**
- 触发：`面试准备 <job编号>` 命令，或 Orchestrator Phase 3B 前自动运行
- 输入：`story-bank.md` + `jd_analysis.json` + 可选 `cover_letter_draft.md`
- 输出：`output/{job_folder}/interview_prep.md`
- 副作用：若 JD 要求有覆盖缺口，追加 ≤2 条新故事到 story-bank.md
- 工作量：~1 天

### 9.3 新增文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `.claude/agents/interview-prep.md` | Agent | 核心逻辑（M7a + M7b 合并，入参决定运行路径） |
| `users/{uid}/interview-prep/story-bank.md` | 生成+持久 | 全局故事库，初始 5-8 条，跨职位累积增长 |
| `output/{job_folder}/interview_prep.md` | Per-job 生成 | JD 要求 → 故事映射表 + 开场稿 + 红旗预案 |

### 9.4 修改文件

| 文件 | 改动 | Graph 社区 |
|------|------|-----------|
| `.claude/agents/Orchestrator.md` | Phase 3B 前新增可选步骤：`如果 interview_prep.md 不存在，调用 interview-prep agent` | Community 0 |
| `CLAUDE.md` 指令表 | 新增 `面试准备 <job编号>` 和 `初始化故事库` 两条指令 | — |

### 9.5 输出格式规范

#### story-bank.md 格式

```markdown
# STAR+R 故事库

> 最后更新：2026-06-01 | 故事数：7 | 覆盖 group：da / pmo

---

## Story #001 — 数据管道重建

- **Theme**: Technical problem-solving under constraint
- **Archetype fit**: group-da（量化数字 + 工具深度）/ group-pmo（交付里程碑）
- **Source**: cv_parsed — ECE Group Hamburg, Working Student BD (2024)
- **S**: ECE Group BI 报告系统每周崩溃，影响 5 个业务团队，依赖手动 Excel...
- **T**: 无额外预算，3 周内完成迁移，不影响周报发布节奏
- **A**: 用 Luigi 替换手动流程，建立 Airflow 风格 DAG，加入监控告警...
- **R**: 崩溃率 100% → 0%，报告延迟 48h → 2h，节省 8 人/周工时
- **Reflection**: 下次先建沙盒验证，避免两次回滚带来的团队信任损耗
- **Best for**: "数据技术难题" / "有限资源下的交付" / "量化影响"
- **Avoid when**: 职位聚焦纯营销无技术组件
```

#### interview_prep.md 格式

```markdown
# 面试准备 — {company} {title}

> 生成时间：2026-06-01 | job_family: group-da | match_score: 78 | decision_score: 82

## 开场自我介绍（90秒）
[混合 Story #001 的数据成果 + Story #003 的跨部门协调，以 group-da 分帧强调数据洞察]

---

## JD 要求 → 故事映射

| # | JD 核心要求 | 推荐故事 | 强调维度 | 备注 |
|---|------------|---------|---------|------|
| 1 | Stakeholder reporting | Story #003 | 业务影响数字 | 提 ECE 的 5 个部门受益 |
| 2 | SQL / data pipeline | Story #001 | 工具深度 + 交付速度 | 提 Luigi → 48h→2h |
| 3 | Cross-functional collaboration | Story #001（复用）| 协作维度 | 换角度：聚焦与 PM 的沟通 |
| 4 | KPI tracking & dashboards | Story #005 | 量化成果 | 提转化率提升 % |

---

## 红旗问题预案

**"为什么离开 ECE Group？"**
→ "想在更大规模的数据环境中深化技术，ECE 的 Working Student 阶段给了我很好的基础，
   现在希望在 [公司] 的完整数据栈上进一步成长。"（正面导向，不批评前雇主）

**"你最大的弱点是什么？"**
→ 用 Story #006 的 Reflection 部分：真实的改进点 + 已采取的行动

---

## 推荐案例研究

Story #001 的数据管道项目——量化结果清晰，可延伸讲系统设计决策，适合 45 分钟 case。

---

## 新增故事（本次分析追加到 story-bank）

> Story #008 已追加：[Hapag-Lloyd project coordination — 覆盖 "Supply chain + logistics" JD 要求]
```

### 9.6 分步骤实施

#### 步骤 7-A：interview-prep agent 核心逻辑

新建 `.claude/agents/interview-prep.md`：

```markdown
# interview-prep agent

## 触发方式
- M7a（Bootstrap）：story-bank.md 不存在时，传入 mode=bootstrap
- M7b（Per-job）：传入 mode=interview，job_folder=<路径>

## M7a 执行步骤（Bootstrap）

1. 读取所有 cv_parsed_{group_id}.json（遍历用户所有 group）
2. 从 experience[] 中提取 5-8 个最具代表性的经历：
   - 优先：有量化数字的成果（revenue/time/% improvement）
   - 优先：跨部门或复杂背景的经历
   - 至少 1 个包含失败/挑战→恢复的经历（Reflection 层最丰富）
3. 为每个经历生成 STAR+R 故事（格式见 9.5）
4. 标注 Archetype fit（job_family 对应关系见下文）
5. 写入 users/{uid}/interview-prep/story-bank.md

## M7b 执行步骤（Per-job）

1. 读取 story-bank.md → 解析现有故事列表
2. 读取 jd_analysis.json → 提取 required_skills + core_responsibilities + job_family
3. 将 JD 核心要求（取 top 5）逐一匹配故事库中最相关的故事
4. 判断覆盖缺口：若某 JD 要求无合适故事 →
   - 检查 cv_parsed 是否有对应经历
   - 有：生成 1 条新故事 → 追加到 story-bank.md（标注 Source）
   - 无：在映射表中标注「无相关经历，建议诚实承认 + 强调快速学习」
5. 生成开场自我介绍（90秒，混合 2-3 故事精华）
6. 生成红旗问题预案（从 jd_analysis.culture_keywords 推断敏感话题）
7. 选择推荐案例研究（score_boost 最高的 customization_potential 项目，若 M5 不存在则跳过）
8. 写入 output/{job_folder}/interview_prep.md

## Archetype 分帧规则（job_family → 故事强调方向）

| job_family  | 强调维度                                      |
|-------------|----------------------------------------------|
| group-da    | 量化数字、数据工具深度、业务洞察（insight）       |
| group-pmo   | 交付里程碑、跨部门协调、风险化解（delivery）      |
| group-pdm   | 转化率、增长指标、GTM 执行（GTM impact）         |
| group-em    | 活动规模、预算控制、现场应急处理（execution）     |
| group-img   | 利益相关方影响、沟通清晰度、变革推动（influence） |

## 禁止
- 不捏造候选人未有过的经历（与 cv-writer 相同规则）
- 不写超出 cv_parsed 信息范围的成果数字
- 不批评前雇主（红旗问题预案需正面导向）
```

#### 步骤 7-B：故事 dedup 检查

story-bank.md 每次追加前检查重复：

```markdown
### Dedup 规则（M7b 追加前必执行）

若新故事的 (Source company, Source role, Theme) 与已有故事相同 → 跳过追加，
在 interview_prep.md 注明「使用已有 Story #XXX」

若新故事 Source 相同但 Theme 不同 → 允许追加（同一经历不同维度）
故事库上限：20 条；超过时提示用户手动归档旧故事
```

#### 步骤 7-C：Orchestrator 集成（可选）

在 `.claude/agents/Orchestrator.md` Phase 3B（Human Review）前追加：

```markdown
### Phase 3A.7：面试准备（可选）

如果 output/{job_folder}/interview_prep.md 不存在：
  调用 interview-prep agent（mode=interview, job_folder=当前职位目录）

如果 users/{uid}/interview-prep/story-bank.md 不存在：
  先执行 M7a Bootstrap，再执行 M7b

输出：interview_prep.md（随 cv_draft.md 一起进入 Phase 3B 人工审核）
```

#### 步骤 7-D：CLAUDE.md 新指令

```
| `面试准备 <job编号>`  | 为指定职位生成 interview_prep.md，自动更新故事库 |
| `初始化故事库`        | 强制从 cv_parsed 重新生成 story-bank.md（谨慎：会覆盖手动编辑内容）|
```

### 9.7 风险分析

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 故事库增长后 LLM 生成重复故事 | 高（故事库 >10 条后） | 库膨胀，用户困惑 | dedup 规则（Source+Theme 双检查）+ 20 条上限提示 |
| M7a Bootstrap 提取故事质量差（cv_parsed 经历描述简略） | 中 | 故事缺少量化细节 | Bootstrap 后在 story-bank.md 末尾生成「待补充提示」列表，请用户补充数字 |
| Reflection 层 LLM 编造「教训」而非真实反思 | 中 | 面试中露馅 | Reflection 只能来自 cv_parsed 中已有的经历描述；无明确线索时写「仍在持续改进中」而非编造 |
| Per-job 故事映射错位（用错故事） | 低 | 面试准备不准 | M7b 步骤 3 明确：匹配 required_skills 关键词 + Archetype fit 双重检查 |
| `初始化故事库` 命令误操作覆盖手动编辑 | 低但不可逆 | 用户手动优化的故事丢失 | 覆盖前先备份到 `story-bank.md.bak`；CLAUDE.md 指令加「谨慎」标注 |

### 9.8 验收标准

- [ ] 首次运行 `初始化故事库`：生成 ≥5 条 Story，每条含 S/T/A/R/Reflection/Best for 全字段
- [ ] 每条 Story 的 R 字段含至少一个可验证数字（来自 cv_parsed）
- [ ] 运行 `面试准备 <job编号>`：生成 interview_prep.md，含 JD 映射表（≥3行）+ 开场稿 + 红旗预案
- [ ] 若 JD 要求有覆盖缺口且 cv_parsed 有相关经历：story-bank.md 自动追加 ≤2 条新故事
- [ ] 追加故事前 dedup：相同 Source+Theme 不重复追加
- [ ] `初始化故事库` 执行前：自动生成 story-bank.md.bak

---

## 10. 风险汇总矩阵

| 风险 | 模块 | 概率 | 严重度 | 关联 Graph 社区 | 应对状态 |
|------|------|------|--------|----------------|---------|
| config.json 无 preferences 字段 | M0a | 低（已存在） | 低 | Community 5 | 应对：中性默认值 + decision_notes 提示 |
| job_family fuzzy match 误匹配（不同职能标题相似度高） | M0a | 中 | 中 | Community 5 | 应对：confidence < 0.70 时视为未匹配，job_family_fit 给 50 分而非 35 分 |
| group_mismatch_warning 频繁出现误报 | M0a | 中 | 低 | Community 2 | 应对：confidence 阈值 ≥ 0.80 才触发 warning，避免低置信度误报 |
| cv_ats.pdf 正则误替换正文 | M0b | 中 | 中 | Community 12 | 应对：仅处理 h1/h2 标签内文字 |
| cv_draft.pdf 被其他脚本硬编码引用 | M0b | 中 | 中 | Community 12 | 应对：实施前 grep 全局确认引用点 |
| Workday bot 检测阻断 Siemens | M1 | 高 | 中 | Community 8 | 应对：随机 UA + sleep |
| Indeed Cloudflare 拦截整个 session | M1 | 高 | 中 | Community 8 | 应对：反检测启动参数；失败时跳过该平台不崩溃 |
| XING 职位描述截断（登录墙） | M1 | 中 | 低 | Community 8 | 应对：标记 description_truncated=true，Phase 3 时再 refetch |
| Monster 聚合重复导致 dedup 后净增量极低 | M1 | 高 | 低 | Community 5 | 应对：预期行为，max_pages=2 限制无效搜索 |
| 锁文件崩溃遗留 | M2 | 中 | 中 | Community 5 | 应对：PID 检测 |
| 路径遍历注入（form-assist） | M3 | 低 | 高 | Community 4 | 应对：`is_relative_to()` 强制检查 |
| legitimacy 误判知名公司 | M4 | 低 | 中 | Community 0 | 应对：白名单直给 80（company_stability）|
| raw_results 文件已清理导致重复检测失败 | M4 | 中 | 低 | Community 5 | 应对：文件缺失时跳过 batch，不阻断 |
| WebSearch 配额耗尽（批量高分职位） | M4 | 低 | 低 | Community 0 | 应对：session 级 company 缓存 + 并行上限 3 |
| playwright install 在其他用户环境失败 | M1 | 中 | 中 | Community 7 | 应对：check.py 降级而非崩溃 |
| 多用户路径硬编码（server.py:28） | M3 | 中 | 低 | Community 4 | **已知 tech debt**，M3 实施前确认 HTML_PATH 不影响新端点 |
| 旧 missing_skills 字符串列表导致解析失败 | M5 | 高（所有旧文件） | 中 | Community 4 | 应对：`isinstance(item, str)` 降级处理 |
| hard_blocker 误判优质职位 | M5 | 中 | 中 | Community 0 | 应对：blocker 需同时满足「required/zwingend + 无相邻经验」双条件 |
| kununu 小公司无数据导致 company_culture_fit 失效 | M6 | 高 | 低 | Community 0 | 应对：null 时降级用 JD 文化信号，不惩罚分数 |
| M4/M6 WebSearch 配额竞争 | M6 | 中 | 低 | Community 0 | 应对：共用 `_company_signal_cache`，M4 结果同步写入 M6 缓存 |
| kununu/Glassdoor 数据陈旧（>2年） | M6 | 中 | 中 | Community 0 | 应对：data_quality="stale" 时前端加「数据可能过期」提示 |
| 故事库重复（LLM 生成同类故事） | M7 | 高 | 低 | Community 0 | 应对：Source+Theme 双 dedup + 20 条上限提示 |
| Bootstrap 故事缺量化细节（cv_parsed 描述简略） | M7 | 中 | 中 | Community 0 | 应对：生成后追加「待补充」提示列表，引导用户补数字 |
| `初始化故事库` 误覆盖手动编辑 | M7 | 低 | 高 | Community 0 | 应对：执行前自动备份 story-bank.md.bak |

---

## 11. 执行时间线

| 周次 | 模块 | 里程碑 |
|------|------|--------|
| Week 1 | M0a | `jd-analyzer.md` decision_score + job_family_fit 联动扩展 + Dashboard 双列显示 + group_mismatch_warning |
| Week 1 | M0b | ATS CSS 主题 + 双 PDF 输出（cv_ats.pdf + cv_styled.pdf） |
| Week 1 | M2 | `search_state.py` TSV + 锁文件完成，`tests/test_core.py` 全通过 |
| Week 1 | M4 | `jd-analyzer.md` legitimacy 扩展（5维）+ 重复发帖检测 + WebSearch 触发条件 + Dashboard 标记 |
| Week 2 | M5 | jd-analyzer missing_skills 结构化 + customization_potential 计算 |
| Week 2 | M5 | cv-writer 读取 top_changes 逐条执行 + cv_changes.md score_boost 记录 |
| Week 2 | M6 | jd-analyzer JD 文化信号提取（零成本）+ kununu/薪资 WebSearch + company_profile 字段 |
| Week 2 | M6 | Job Detail 页「公司画像」区块 + decision_score company_culture_fit 升级 |
| Week 2 | M7 | interview-prep agent（M7a Bootstrap + M7b Per-job）+ story-bank.md 格式 + Orchestrator 集成 |
| Week 2-3 | M1 | portals.yml + scan_portal.py + ats_type/aggregator 双分发架构；SAP/Capgemini/Indeed 先上 |
| Week 3 | M1 | Siemens/Hapag-Lloyd/Aldi（portal）+ Xing/Monster（aggregator）完成 |
| Week 4 | M1 | Phase 2 集成测试：end-to-end 6 源（portal×5 + aggregator×3）→ jd_analysis.json |
| Week 5 | M3 | form-assistant agent + `/api/form-assist` 端点 |
| Week 6 | M3 | Page 2 Panel UI + SSE 流式渲染 + 安全测试 |

---

## 12. 关键接口契约（不可破坏）

以下接口被多个模块依赖（来源：graphify God Nodes + Hyperedges），**修改前必须确认下游兼容性**：

| 接口 | 被依赖方 | 约束 |
|------|---------|------|
| `jd_analysis.json` schema | server.py:`parse_jobs()`, UI Dashboard, cv-writer agent, interview-prep agent | 新增顶层字段：`decision_score`、`job_family`、`gap_summary`、`customization_potential`、`legitimacy`、`company_profile` |
| `users/{uid}/interview-prep/story-bank.md` | interview-prep agent（M7a 写入，M7b 读写） | append-only 增长；覆盖前必须备份 .bak；20 条上限 |
| `output/temp/.company_signal_cache.json` | jd-analyzer agent（M4 + M6 读写）| Phase 2 开始时由 run_phase2_search.py 清空；key=company_name，value={hiring:{...}, kununu:{...}}；jd-analyzer 每次写入前先读再合并（防并发覆盖） |
| `missing_skills` 元素结构 | server.py, cv-writer, Dashboard | 旧格式（字符串）须通过 `isinstance` 检测降级；新格式为对象（含 skill/severity/mitigation） |
| `config.json` keyword_groups[].job_family | jd-analyzer（job_family_fit 计算） | 只读，不修改；jd-analyzer 通过 `config["job_search"]["keyword_groups"]` 读取 |
| `search_history.json` schema | server.py:`_load_search_batches()`, check.py | 新增字段必须有默认值；新增 `failed_jobs: []`、`retry_count: 0` |
| `output/{group_id}_{company}_{title}_{YYYYMMDD}/` | server.py, generate_summary.py, form-assistant | 目录名格式不变；M0b 的 pdf 文件名拆为 cv_ats.pdf + cv_styled.pdf |
| `_source` 字段枚举 | server.py, UI Source 列过滤 | 新增 `portal_*` 前缀，UI 过滤逻辑需支持前缀匹配 |
| `quick_score()` 函数 | run_phase2_search.py | M1 的 portal jobs 在合并前调用同一函数预评分 |
| `config.json` 结构 | 所有 agent + server.py | 新增 `users.{uid}.preferences` 层级；不修改现有字段 |
| `generate_pdf()` 签名 | Phase 3D, Orchestrator | 若新增 `css_string` 参数，必须默认值为 `None` 保持向后兼容 |
| `config/ats_field_map.yml` | server.py:`_handle_form_fields()`, 前端 Tab 1 | 新增文件；key 名称一旦发布不可随意改动（前端 JS 依赖 key 索引字段卡片） |
| `/api/form-fields` 端点响应 schema | 前端 Tab 1 `renderFieldCards()` | `work_experience[]` 和 `education[]` 数组结构不可破坏；新增字段 ok，删除/重命名需同步更新前端 |

---

## 13. graphify 更新提醒

每个模块完成后，运行：
```bash
graphify update .
```

预期新增社区：
- `Decision Score Engine + Job Family Detector`（M0a）— 连接 Community 0、Community 2（UI）、Community 5（Search State）
- `Skill Gap Classifier + CV Optimizer`（M5）— 扩展 Community 0（jd-analyzer）连接 Community 12（PDF/cv-writer）
- `ATS PDF Generator`（M0b）— 扩展 Community 12（PDF Generator）
- `Portal Scanner`（M1）— 新增独立社区
- `Form Assistant`（M3）— 连接 Community 4（HTTP Server）和 Community 2（UI）
- `legitimacy` 节点（M4）— 连接 Community 0 和 Community 2
- `Company Profile + kununu Researcher`（M6）— 扩展 Community 0（jd-analyzer）连接 Community 2（UI Job Detail）
- `Interview Prep + Story Bank`（M7）— 新社区，连接 Community 0（Orchestrator）和 Community 3（Application Outputs）
