# Job Tracker — Visual Design Spec

> 本文件只包含视觉设计规格：色彩、字体、间距、组件样式、交互状态。
> 产品功能逻辑、页面路由、字段映射见 `SPEC.md` → "Web UI — 功能规格"。

---

## Design Philosophy — "Kinetic Archive"

数据密集但容器轻盈。以**色调分层**取代传统边框线，以**留白**作为结构元素。
用户感受：高端编辑风格的数据管理，像 talent executive 而非数据录入员。

**核心原则：**
- No-Line Rule：禁止用 1px 边框分隔内容区，改用背景色差异区分层级
- Tonal Layering：`surface` → `surface-container-low` → `surface-container-lowest`（白色卡片）逐层"浮起"
- Breathable Density：信息紧凑，容器有呼吸感（section 间距 ≥ 24px）

---

## Typography

| 角色 | 字体 | 用途 |
|------|------|------|
| Display / Headlines | **Manrope** 700–800 | 页面标题、大数字统计 |
| Body / Utility | **Inter** 400–600 | 公司名、职位名、表格正文 |
| Labels / Tags | **Space Grotesk** 500–600 | 状态标签、日期、ID、表头 |

**字号层级：**

| 用途 | 字号 | 字重 | 字体 |
|------|------|------|------|
| 页面标题 | 24px | 800 | Manrope |
| 职位标题（Detail） | 22px | 800 | Manrope |
| 统计大数字 | 28px | 800 | Manrope |
| Score 仪表盘数字 | 44–48px | 800 | Manrope |
| 表格正文 | 13px | 400 | Inter |
| 表头 | 10px | 600 | Space Grotesk（uppercase） |
| 标签/徽章 | 11–12px | 600 | Space Grotesk |
| 辅助说明 | 11px | 400 | Inter |

---

## Color System

### 基础色板

| Token | Hex | 用途 |
|-------|-----|------|
| `surface` | `#F8F9FA` | 页面背景 |
| `surface-container-low` | `#F3F4F5` | 次要内容区 |
| `surface-container-lowest` (card) | `#FFFFFF` | 卡片、表格行 |
| `surface-container-high` | `#E7E8E9` | 表头背景 |
| `primary` | `#005D8F` | 主色（深蓝，按钮渐变起点） |
| `primary-bright` | `#0077B5` | LinkedIn 品牌蓝，渐变终点 |
| `on-surface` | `#191C1D` | 主文字色（非纯黑） |
| `on-surface-variant` | `#404850` | 次级文字 |
| `outline` | `#707881` | 辅助文字、表头文字 |
| `outline-variant` | `#D1D5DB` | Ghost border（仅无障碍需要时使用） |
| `row-hover` | `#EFF6FF` | 表格行 hover |

### Score 色彩阈值

| 区间 | 背景色 | 文字色 | 含义 |
|------|--------|--------|------|
| ≥ 70 | `#DCFCE7` | `#22C55E` | High Match |
| 45–69 | `#FEF9C3` | `#EAB308` | Good Match |
| 30–44 | `#FFEDD5` | `#F97316` | Moderate |
| < 30 | `#FEE2E2` | `#EF4444` | Low Match |

### 来源品牌色

| 来源 | 文字色 | 背景色（badge） |
|------|--------|----------------|
| LinkedIn | `#0077B5` | `#E0F0FB` |
| Stepstone | `#F97316` | `#FFEDD5` |

---

## Gradient & Glass

**主按钮渐变：**
```css
background: linear-gradient(135deg, #005D8F 0%, #0077B5 100%);
```

**导航栏玻璃效果：**
```css
backdrop-filter: blur(20px);
background: rgba(248, 249, 250, 0.92);
```

---

## Spacing & Layout

| Token | 值 | 用途 |
|-------|-----|------|
| Card Padding | `24px` | 卡片内边距 |
| Section Gap | `16px` | 卡片之间、section 之间 |
| Table Cell Padding | `9px 14px` | 表格单元格 |
| Page Top Padding | `84px` | 导航栏高度 68px + 余量 |
| Max Content Width | `1700px` (P1) / `1200px` (P2) | 居中容器 |

---

## Elevation & Shadow

| 层级 | 阴影值 | 用途 |
|------|--------|------|
| Card default | `0 1px 3px rgba(0,0,0,0.07)` | 卡片、面板 |
| Card hover | `0 4px 16px rgba(0,0,0,0.12)` | 鼠标悬停提升感 |
| Floating (popover) | `0 20px 40px rgba(25,28,29,0.06)` | 浮层、下拉 |
| Score badge hover | `0 4px 12px rgba(0,0,0,0.18)` + `translateY(-1px)` | 交互反馈 |

**不得使用 1px 实线边框分隔主要区块。** 需要边缘感时用 `outline-variant` 15% 透明度的"Ghost Border"。

---

## Border Radius

| 用途 | 值 |
|------|----|
| 卡片、面板 | `12px` (`rounded-xl`) |
| 按钮、Score badge、Segmented track | `9999px` (`rounded-full`) |
| 小标签 Tag | `4–6px` |
| Input 下划线样式 | `0` radius，仅底部 2px border |

---

## Component Specs

### Score Badge

```
display: inline-flex; align-items: center; justify-content: center;
min-width: 42px; padding: 3px 10px;
border-radius: 9999px;
font-family: Space Grotesk; font-size: 12px; font-weight: 700;
cursor: pointer;
hover: box-shadow(0 4px 12px rgba(0,0,0,0.18)) + translateY(-1px)
```
颜色按 Score 阈值表，背景 + 文字色成对使用。

### Segmented Control

```
track: background #E1E3E4; padding 4px; border-radius 9999px;
thumb (active): background #FFF; color #005D8F; box-shadow 0 1px 3px rgba(0,0,0,0.1);
font: Space Grotesk 12px 500; padding: 5px 14px;
```

### Primary Button

```
background: linear-gradient(135deg, #005D8F, #0077B5);
color: #FFF; border-radius: 9999px; font: Space Grotesk 12px 700;
padding: 7px 18px; border: none;
disabled: opacity 0.7;
```

### Ghost / Outline Button

```
background: transparent; border: 2px solid rgba(0,93,143,0.2);
color: #005D8F; border-radius: 9999px; font: Manrope bold;
```

### Application Record Select (4-state)

已替换为 `<select class="rec-select">` 下拉控件（见下方 CSS 规格），不再使用双按钮。

### Multiple Source Badge（原 Remark Badge）

```
background: #FEF9C3; color: #854D0E;
border-radius: 4px; padding: 2px 6px;
font: Space Grotesk 10px 600; white-space: nowrap;
内容："multiple source"（跨 LinkedIn + Stepstone 重复时显示）
列头已更名为"Multiple Source"（原"Remark"）
```

### Group Tag

```
background: #EDEEEF; color: #404850;
border-radius: 4px; padding: 2px 7px;
font: Space Grotesk monospace 11px;
```

### Culture Keyword Pill (Page 2)

```
background: #EFF6FF; color: #1D4ED8;
border: 1px solid #BFDBFE;
border-radius: 9999px; padding: 6px 12px; font-size: 12px 600;
```

### Bonus Skill Pill (Page 2)

```
border: 2px dashed #FCD34D; background: #FFFBEB; color: #92400E;
border-radius: 9999px; padding: 6px 12px; font-size: 12px 600;
```

### Recommended Emphasis Card (Page 2)

```
background: #FFF7ED; border: 1px solid #FED7AA;
border-radius: 12px; padding: 28px;
序号圆形：width/height 22px; background #FED7AA; color #C2410C;
font: Space Grotesk monospace 10px 700;
```

### Group Card (Page 4)

```
background: #FFFFFF; border-radius: 12px; padding: 24px;
border: 1px solid #E5E7EB; box-shadow: 0 1px 3px rgba(0,0,0,0.07);
transition: border-color .2s, box-shadow .2s;
hover: border-color #3B82F6; box-shadow: 0 4px 16px rgba(0,0,0,0.10);
position: relative;
```

### Group Icon (Page 4)

```
width/height: 42px; border-radius: 10px; flex-shrink: 0;
color: #FFFFFF; font: Space Grotesk 11px 700;
background: 由 group_id 哈希映射到 7 色调色板（蓝/紫/青/琥珀/粉/红/绿）
```

### Keyword Chips (Page 4)

```css
/* EN chip */
background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE;
border-radius: 9999px; padding: 2px 9px; font-size: 11px; font-weight: 600;

/* DE chip */
background: #EDE9FE; color: #5B21B6; border: 1px solid #DDD6FE;
border-radius: 9999px; padding: 2px 9px; font-size: 11px; font-weight: 600;

/* "+N more" chip */
background: #F3F4F6; color: #6B7280;
border-radius: 9999px; padding: 2px 9px; font-size: 11px; font-weight: 600;
```

### Missing Skill Tag (Page 1，Page 4 Section D)

```
background: #FEF9C3; color: #854D0E; border-radius: 4px;
padding: 1px 7px; font: Space Grotesk monospace 11px 600;
position: relative;（支持 Skill Gap 面板的右上角频次徽章）
```

### Matched Skill Tag (Page 4 Section E)

```
background: #DCFCE7; color: #166534; border-radius: 4px;
padding: 1px 7px; font: Space Grotesk monospace 11px 600;
position: relative;
CSS class: .match-tag
```

### Dropdown Menu (Page 4 ··· 操作)

```
position: absolute; right: 0; top: calc(100% + 4px); z-index: 40;
min-width: 140px; background: #FFFFFF;
border-radius: 10px; box-shadow: 0 8px 24px rgba(0,0,0,0.13);
overflow: hidden;

item: padding 10px 16px; font 13px Inter; hover background #F3F4F6;
danger item: color #EF4444; hover background #FEE2E2;
```

### Missing Skills / Matched Skills — 6-Category 渲染规则

```
classifySkill(s) → 6 种分类：
  tools    = sql/python/excel/powerbi/tableau/jira/salesforce/aws/azure/gcp/figma/
             mongodb/airflow/dbt/snowflake/github/docker/react/node.js 等
  academic = bachelor/master/phd/mba/bsc/msc/degree/economics/
             computer science/engineering/statistics 等
  cert     = pmp/prince2/scrum master/csm/cspo/certified/six sigma/
             aws certified/google certified 等
  langs    = german/deutsch/english/englisch/french/español/mandarin/
             c1/c2/b2/fließend/native speaker 等
  domain   = saas/b2b/b2c/ecommerce/product management/go-to-market/
             customer success/digital marketing/seo/agile/scrum/
             product-led/ux research/stakeholder management 等
  soft     = 其余

Page 1 Table — Missing Skills 列：
  容器：无高度限制（不截断）；hover title 显示完整列表
  渲染：6 分类各有 category label（Space Grotesk 9px uppercase slate-400）
        label 下方紧跟该分类的 miss-tag pills

Page 2 Matched Skills / Missing Skills：
  每分类前加 category label 行（同样式）
  Matched: Tools & Technical / Academic Background / Certificates /
           Languages / Domain Knowledge / Soft & Other
  Missing: 同标签，图标色 #EF4444

Page 4 Section D (Missing) / Section E (Matched)：
  同 6 分类，category label 样式相同
  Missing: .miss-tag（黄色）；Matched: .match-tag（绿色，见下方组件规格）
```

### Date Range Slider (过滤栏)

```
label: "Recent (days)"，Space Grotesk 10px 600 uppercase
input[type=range]: min=0, max=60, default=14, accent-[#005d8f]
value display: "#d" 格式；value=0 时显示 "All"
oninput: debounceFilters()（150ms，与 Score 共用）
过滤逻辑：保留 analyzed 日期在最近 N 天以内的职缺；N=0 时不过滤
持久化：写入 localStorage key 'jt_filter' 的 minDate 字段
```

### Card Section Label (Page 4)

```
font: Space Grotesk 10px 600 uppercase; letter-spacing: .07em;
color: #9CA3AF; margin-bottom: 6px;
```

### Application Record Select (Page 1 — 4-state)

```css
.rec-select {
  border-radius: 9999px; border: 1.5px solid #D1D5DB; background: #FFF;
  font: Space Grotesk 11px 600; padding: 2px 8px 2px 10px;
  max-width: 96px; color: #9CA3AF; outline: none; cursor: pointer;
  transition: .15s;
}
/* State variants (via data-state attribute) — 4 states only */
[data-state="applied"]   { background: #EFF6FF; color: #1D4ED8; border-color: #1D4ED8; }
[data-state="interview"] { background: #EDE9FE; color: #5B21B6; border-color: #5B21B6; }
[data-state="invalid"]   { background: #F3F4F6; color: #6B7280; border-color: #9CA3AF; }
/* rejected 已移除；旧数据回退为空选项"— Track" */
```

### Materials Ready Badge (Page 1 — Title 列)

```
display: inline-flex; align-items: center; gap: 2px;
background: #DCFCE7; color: #16A34A;
border-radius: 3px; padding: 1px 5px;
font: Space Grotesk monospace 10px 600; white-space: nowrap;
margin-bottom: 2px;
内容：📄 Ready
```

### Notes Icon (Page 1 — Notes 列)

```
Material Symbol: edit_note; font-size: 16px;
default (无备注): color #D1D5DB，仅图标
has-note (有备注): color #F59E0B（琥珀色）+ 图标下方显示前 20 字文本
  文本样式：font-size 10px, font-mono, amber-600, max-width 72px, truncate
hover (title 属性): 显示前 80 字预览
```

### Sortable Column Header

```css
.th-sort { cursor: pointer; user-select: none; }
.th-sort:hover { background: #DDE0E2; }
/* Sort icon (⇅ / ↑ / ↓) */
.sort-icon { font-size: 9px; opacity: .45; margin-left: 3px; }
.th-sort.sort-active .sort-icon { opacity: 1; color: #005D8F; }
```

### Skill Gap Panel

```
container: bg-white, rounded-xl, shadow-sm, mb-5
header: px-5 pt-4; flex justify-between; Manrope 14px bold + slate-400 subtitle
        subtitle 格式："— N jobs · M unique gaps"
body: 按 6 分类分组，每组有 section 标题 + flex flex-wrap gap-2

词云渲染规则：
  - 仅展示频次 > 1 的技能（count > 1）
  - 使用 .miss-tag 黄色 pill 样式（同 Page 4 Section D）
  - font-size: 11px + (count/maxCount) × 14px，范围 11–25px（最大 25px）
  - padding 随字体大小等比扩大
  - 频次徽章：右上角绝对定位 <sup>，灰色圆形 background:#6B7280，白色数字，font-size:9px

Section 标题：Space Grotesk 9px 700 uppercase，letter-spacing .06em，color #9CA3AF
  分组顺序：Tools & Technical → Academic Background → Domain Knowledge →
            Languages → Certificates → Soft & Other
```

### Notes Textarea (Page 2 — bottom of detail)

```css
.note-textarea {
  width: 100%; min-height: 80px; resize: vertical;
  border: 1.5px solid #E5E7EB; border-radius: 8px;
  padding: 10px 14px; font: Inter 13px; color: #191C1D;
  outline: none; transition: border-color .15s;
}
.note-textarea:focus { border-color: #005D8F; }
```

### Ghost Action Buttons (Skill Gap + Export，过滤栏右侧)

```
background: #FFFFFF; border: 2px solid rgba(0,93,143,0.2);
color: #005D8F; border-radius: 9999px;
font: Space Grotesk 12px 700; padding: 6px 16px;
icon: Material Symbol 14px + text label
与 Loading 按钮并排，flex items-end gap-3 布局
```

### Empty State (过滤无结果)

```
colspan 14, text-center, py-12
icon: Material Symbol "search_off" text-4xl text-slate-400
title: "No jobs match your filters"  Inter 13px font-semibold
subtitle: 12px text-slate-400
button: "Reset Filters"  kinetic-gradient text-white rounded-full
        Space Grotesk 12px 700; padding: 8px 16px
```

---

## Data Table

**No vertical lines, no horizontal lines between rows.**

| 属性 | 值 |
|------|----|
| 奇数行背景 | `#FFFFFF` |
| 偶数行背景 | `#F8F9FA` |
| Hover 行背景 | `#EFF6FF` |
| 行下边框 | `1px solid #F3F4F5`（极细分隔，不作为视觉边界） |
| 表头背景 | `#E7E8E9` |
| 表头：sticky | `position: sticky; top: 0; z-index: 20` |
| 表头底部线 | `box-shadow: 0 1px 0 #D1D5DB` |
| 日期/数字字体 | Space Grotesk monospace（保证纵向对齐） |
| 滚动容器 | `overflow: auto; max-height: calc(100vh - 310px)` |

**Sticky 实现要点：** 滚动容器用 `overflow: auto`，不得用 `overflow: hidden`（会阻断 sticky 定位）。

---

## Page Layouts

### Page 1 — Dashboard

```
[Navbar 68px fixed]
[Page padding-top: 84px]
[Stats Row: 4 cards, grid-cols-4, gap-4]
  Total Jobs | High Match ≥70 | Good Match 45–69 | Moderate 30–44
[Filter Bar: flex, items-end, bg-white, rounded-xl, p-4, shadow-sm]
  left:   Group segmented control
  center: Source segmented control + Score slider (debounced 150ms) + Date Slider
          + Application Record 下拉（Status: All / — Track / Applied / Interview / Invalid）
  right:  flex items-end gap-3 → [Skill Gap button] [CSV button] [Loading button]
[Skill Gap Panel: bg-white rounded-xl shadow-sm mb-5, 默认折叠]
  header: analytics icon + "Top Missing Skills" + subtitle (N jobs · M unique gaps)
  body:   按 6 分类分组，词云，font-size 11–25px，右上角频次徽章，仅显示频次 > 1 的技能
[Table Card: bg-white, rounded-xl, shadow-sm]
  Columns（14 列）: # | Score↕ | Group | Source(+URL) | Company↕ | Title↕ | Size | Location |
           Recommended Emphasis | Missing Skills | Analyzed↕ | Record | Multiple Source | Notes
  [.table-scroll-wrapper: overflow:auto, max-height: calc(100vh - 310px)]
  [Empty State: search_off icon + Reset Filters button（过滤无结果时）]
  [Pagination footer: bg-gray-50, rounded-b-xl, flex, justify-between]
```

### Page 2 — Job Detail

```
[padding-top: 84px; padding-bottom: 100px]
[max-width: 1200px, mx-auto]
[Back button row]
[Title card: company + size badge + source badge + score badge]
[Score gauge: centered, max-w-xs card, SVG ring 160×160px]
[3-col grid: grid-template-columns: 2fr 1.75fr 1.25fr  → 约 40% / 35% / 25%]
  left (2fr):    Core Responsibilities card + Culture Keywords card
  center (1.75fr): Skills Analysis card (matched + missing) + Bonus Skills card
  right (1.25fr):  Recommended Emphasis card (orange bg) + Required Skills card
[Notes card: detail-card mt-5; textarea auto-save onblur → POST /api/note]
[Sticky footer bar: position:fixed bottom:0, bg-white, rounded-t-2xl]
  Apply Now (primary gradient, links to job URL) + Back to List (ghost outline)
```

### Page 3 — Add Search Group *(🚧 待实现)*

```
[Breadcrumb gray] [Title 24px Manrope] [Subtitle gray]
[2-col grid card: white bg, 32px padding]
  left: Group Identity fields (Group ID / Group Label / CV File 下拉选 my_cv/)
  right: Search Keywords (EN chips / DE chips / Job Family EN list / DE list)
[Collapsible "Search Settings" section: chevron toggle, default collapsed]
  Location / Date Range / Max Jobs / Score Threshold
[Sticky bottom action bar]
  Cancel (ghost) | Save Draft (outlined) | Save & Search Now (primary)
```

### Page 4 — My CVs *(✅ 已实现)*

```
[padding-top: 84px; padding-bottom: 48px]
[max-width: 1400px, mx-auto]
[Title row: "My CVs" (Manrope 24px 800) + "+ Add Group" (禁用，灰色)]
[Summary bar: 4 stat-cards, grid-cols-4, gap-4]
  Total Groups | Assigned CVs | Active Searches (sub: "last 7 days") | Last Updated
[Card grid: grid-cols-1 xl:grid-cols-2, gap-4]
  Each .group-card:
    Header row: .group-icon (42px, 彩色, initials) + Label+ID + Status badge + Avg Score badge
    Section A "CV File": file icon + filename
                         + 👁 <a href="/api/cvfile?name=…" target="_blank"> 预览
                         + ⬇ 下载（待实现，tooltip 提示路径）
    Section B（左列）: Primary Keywords EN（蓝色 kw-chip-en）+ Job Family EN（蓝色 kw-chip-en）
                       各显示前 6 个，超出折叠为 "+N more" 按钮（kw-chip-more），点击展开
    Section C（右列）: Primary Keywords DE（紫色 kw-chip-de）+ Job Family DE（紫色 kw-chip-de）
                       同上，前 6 + "+N more"
    Section D "Top Missing Skills": miss-tag badges（黄色），按 6 分类 + category label
    Section E "Top Matched Skills": match-tag badges（绿色），按 6 分类 + category label
    Footer (border-top):
      Search Timeline rows（最多 3 行，Space Grotesk 10px monospace，slate-400）
        格式：<date> · <new_net> new · <fetched_total> fetched (<sources>)
      Actions row: last search date + job count | Search Jobs (gradient) + Edit (disabled) + ···
  卡片排序：按 avg_score 从高到低
[Bottom callout banner: background #EFF6FF, text #1D4ED8]
```

---

## Interactive States

| 元素 | Default | Hover | Active/Selected |
|------|---------|-------|-----------------|
| 表格行 | 白/灰交替 | `#EFF6FF` | — |
| Score badge | 按分段色 | shadow lift + translateY(-1px) | — |
| Segmented btn | 透明 | — | 白色 thumb + shadow |
| Sortable th | `#E7E8E9` | `#DDE0E2` | sort-active: icon opacity 1 + `#005D8F` |
| Group card (P4) | `border: 1px solid #E5E7EB` | `border-color: #3B82F6` + lift shadow | — |
| Primary button | gradient | opacity 0.9 | — |
| App Record select | 灰色边框，`#9CA3AF` text | — | data-state 驱动颜色（见组件规格） |
| Notes icon | `#D1D5DB` | — | has-note: `#F59E0B` |
| Ghost action btn | `border rgba(0,93,143,.2)` | border opacity 0.6 | — |
| ··· Dropdown | 关闭 | — | 弹出菜单，点击外部关闭 |
| Nav link | text-slate-500 | bg-gray-100 | `border-b-2 border-[#0077B5]` text-[#0077B5] |

---

## Design Tokens (Quick Reference)

| Token | Value |
|-------|-------|
| `--bg` | `#F8F9FA` |
| `--card` | `#FFFFFF` |
| `--primary` | `#005D8F` |
| `--primary-bright` | `#0077B5` |
| `--on-surface` | `#191C1D` |
| `--text-secondary` | `#6B7280` |
| `--score-green` | `#22C55E` |
| `--score-yellow` | `#EAB308` |
| `--score-orange` | `#F97316` |
| `--score-red` | `#EF4444` |
| `--row-hover` | `#EFF6FF` |
| `--radius-card` | `12px` |
| `--radius-pill` | `9999px` |
| `--shadow-card` | `0 1px 3px rgba(0,0,0,0.07)` |
| `--font-display` | `Manrope` |
| `--font-body` | `Inter` |
| `--font-label` | `Space Grotesk` |
| `--body-size` | `13px` |
| `--card-padding` | `24px` |
| `--section-gap` | `16px` |
