## 2026-04-23 — Session #32 (group-pmo Stepstone search)

### 本次完成
- 搜索 Stepstone 职缺 group-pmo：100 raw → 6 candidates → 6 JD 分析完成
- 新增 #219-#224 到 job_summary.md，total = 224 jobs
- 最佳候选：ALDI (78)；König+Neurath 和 DIGOOH 均 72

### 新增职缺摘要
| # | Score | Company | Title | Key Gap |
|---|-------|---------|-------|---------|
| 219 | 78 | ALDI Einkauf SE | PMO – ERP Transformation | No consulting bg, no retail exp (bonus only) |
| 220 | 72 | König + Neurath AG | Senior PMO / Project Portfolio Manager | German B1 vs C1/C2, 5-8yr PMO req |
| 221 | 72 | DIGOOH Media GmbH | Projektmanager im Portfoliomanagement | No DOOH/advertising exp |
| 222 | 65 | LA Lernallianz GmbH | PMO / Transformation Manager | No consulting bg, no PE/EBITDA exp |
| 223 | 62 | ClimatePartner GmbH | Senior PMO Manager | 6+ yr req (CV says 4+) |
| 224 | 62 | MEAG Munich Ergo | Project Manager Transformation | German C1 req, asset mgmt knowledge gap |

### 决策建议
- #219 ALDI (78)：最强候选，两个 gap 均为 bonus（非硬要求），HSBC PMO 直接对应核心职责
- #220 König+Neurath (72)：值得申请，主要风险是德语（B1 vs verhandlungssicher）+ 5-8yr PMO gap
- #221 DIGOOH (72)：技术上匹配，但行业(DOOH/广告)是软要求；角色偏 account management
- #222-#224：分数偏低或关键缺口（PE背景/德语C1/asset mgmt），建议跳过

### 下次待办
- 决定是否为 #219 ALDI (78) 生成 CV/CL（使用 group-pmo CV）
- 可考虑 #220 König+Neurath (72)
- 可搜索 group-da Stepstone 新职缺（上次搜索 2026-04-23 批次 001）

---

## 2026-04-23 — Session #31 (continued, group-pdm Stepstone search)

### 本次完成
- 搜索 Stepstone 职缺 group-pdm：79 raw → 6 candidates → 6 JD 分析完成
- 新增 #213-#218 到 job_summary.md，total = 218 jobs
- 最佳候选：Hela Gewürzwerk (76)；其余偏低（德语要求 + SQL 缺口）

### 新增职缺摘要
| # | Score | Company | Title | Key Gap |
|---|-------|---------|-------|---------|
| 213 | 76 | Hela Gewürzwerk | Product & Marketing Manager | German C1+ required (CV B1+) |
| 214 | 52 | Lekkerland (REWE) | UX Research & Analytics Manager | UX tools (Hotjar, Contentsquare) absent |
| 215 | 48 | trivago | Data Analyst Marketing Strategy | SQL hard required |
| 216 | 44 | APPINIO | Customer Success Manager DACH | German native + no CSM track |
| 217 | 38 | Rebuy | Analyst Pricing & Revenue Opt | Pricing/SQL heavy |
| 218 | 32 | InnoNature | CRM Manager | Klaviyo required, German C1+ |

### 决策建议
- #213 Hela Gewürzwerk (76)：值得申请，但需在 Cover Letter 正视德语水平 (B1+ → 积极学习姿态)
- 其余 5 个分数过低或关键技能缺口过大，建议跳过

### 下次待办
- 决定是否为 #213 Hela Gewürzwerk 生成 CV/CL（使用 group-pdm CV）
- 可考虑搜索 group-pmo Stepstone 职缺

---

## 2026-04-19 23:30 — Session #30

### 本次完成
- 修复「搜索职缺」按钮，从临时剪贴板方案升级为直接 API 调用（UI/My_CVs/code.html）
  - 按钮点击→ POST /api/search {group_id} → 服务器启动 Claude Code 子进程
  - 实时 SSE 流接收日志，底部 Log Drawer 显示搜索进度
- 全面 /simplify 清理同文件：合并样式块、消除行内样式、修复 XSS、修复 409 状态逻辑、滚动优化

### 决策与判断
- 保留 API 直调方案（更自然），不再需要用户手动粘贴命令
- 移除临时降级方案（剪贴板复制），简化代码路径

### 发现的问题
- 无

### 下次待办
- 实现 Page 3（Add Search Group）表单 + POST /api/group-save 端点

---

## 2026-04-19 18:45 — Session #29

### 本次完成
- 搜索职缺按钮自动触发 Claude Code 功能：完整实现 4 个部分
  - `scripts/server.py`：新增 `_run_search()` 函数 + 3 个路由（`POST /api/search`、`GET /api/search-status`、`GET /api/search-log`）
  - `scripts/gen_job_tracker_html.py`：修改 `onLoadingClick()` 立即禁用按钮、新增日志面板 + SSE 流式接收
  - `subprocess.Popen` 启动 Claude Code 子进程、逐行读取 ANSI 剥离输出、`shutil.which('claude')` 查找可执行文件
  - 已重新生成 `C:\Users\Leon\Desktop\job_tracker\index.html`（84 KB）
- 增加并发保护：POST /api/search 返回 409 若已有搜索进行中

### 决策与判断
- 采用客户端立即反馈策略：按钮禁用 + 「⏳ 连接中…」提示，提升 UX
- 日志面板采用 dark terminal 风格（符合开发者习惯）
- 降级方案：连接失败时自动切换为剪贴板复制 + 轮询（保证体验连贯性）

### 发现的问题
- 用户反映按钮无反应，已在 `onLoadingClick` 最开始添加立即禁用按钮逻辑和诊断日志
- 可能原因：服务器路由未加载（需重启 server.py）或网络连接问题

### 下次待办
- 用户重启 `python scripts/server.py` 以加载新路由
- 验证按钮点击后立即禁用、日志面板显示、执行流程完整

---

## 2026-04-19 14:30 — Session #28

### 本次完成
- 完成 Web UI v3 文档重组：SPEC.md（产品功能）vs UI.md（视觉设计）严格分离
- Page 1 修复：Remark 列加 min-width:110px，防止无数据时列宽坍缩
- Page 2 修复：3 列布局改为 grid-template-columns: 2fr 1.75fr 1.25fr（40/35/25%）
- Page 4（My CVs）全新实现：4 个 API 端点 + 完整 HTML + JS
  - GET /api/group-stats（group 统计）、GET /api/cvfiles（CV 文件列表）
  - POST /api/group-delete（删除 group）、POST /api/group-dup（复制 group）
  - 2 列卡片网格、Stats bar、Search Jobs 按钮、··· 菜单（Delete/Duplicate）
  - Edit 按钮禁用、+ Add Group 禁用、Toast 通知、Nav 高亮

### 决策与判断
- Page 3（Add Search Group）表单页设计已在 SPEC.md，待后续实现
- Edit 按钮暂时禁用，待 Page 3 实现后启用（关联编辑流程）
- group-da 24 jobs、group-pmo 27 jobs、group-pdm 46 jobs，合计 131 条（internal-marketing/event-management 暂无搜索数据）

### 发现的问题
- 无

### 下次待办
- 实现 Page 3（Add Search Group）：表单页面 + POST /api/group-save 端点
- 启用 Edit 按钮，连接到 Page 3 的编辑流程
- 考虑 internal-marketing / event-management 的搜索策略

---

## Session #27 — 2026-04-17

### 完成
- Stepstone MCP 环境从零搭建成功（克隆 kdkiss/mcp-stepstone，pip install，修复 SSE→StreamableHTTP 协议）
- 修复 run_phase2_search_stepstone.py 三处核心 bug：parse_search_response 新格式、get_job_details API 参数、parse_job_details_response emoji 格式
- group-da Stepstone 搜索：36 个有效职缺（5城，Munich 空结果已过滤）
- 12 个候选完成 JD 分析，job_summary.md 更新至 122 个职缺

### 分析结论
- 最佳候选：advalyze GmbH (62) + Coloplast GmbH (60)
- ING Deutschland (52) 有潜力但 SQL 是硬筛
- 其余 9 个因德语要求或技术栈差距过大，不建议申请

### 待决策
- 用户尚未决定是否为 advalyze / Coloplast 生成 CV
- 未来可继续搜索 group-pdm / group-pmo 的 Stepstone 职缺

---

## 2026-04-13 — Session #26

### 本次完成
- 新增指令 `解析 CV` / `解析 CV <group-id>` 支持单独执行 Phase 1（更新 CLAUDE.md + Orchestrator.md）
- 执行「解析 CV group-pmo」：cv-parser 成功解析 `my_cv/my_cv_pmo.pdf`
  - 输出：`output/cv_parsed_group-pmo.json`
  - 内容：7段工作经历（Hapag-Lloyd、HSBC、ECE Group 等）、3个学位、PL-300 证书
- 尝试「搜索职缺 group-pmo」：LinkedIn MCP 工具未在本 session 加载，Phase 2 未能执行
- 建立 global memory 系统（MEMORY.md + user_profile.md + project_groups.md + feedback_linkedin_mcp.md）

### 决策与判断
- group-pmo 为本项目第 3 个完成 Phase 1 的 group（da、pdm 已有缓存）
- LinkedIn MCP 未加载为已知问题（同 Session #20），重启 Claude Code 可解决

### 发现的问题
- LinkedIn MCP 在本 session 未加载，Phase 2 无法执行；需重启 Claude Code

### 下次待办
- 重启 Claude Code 后执行「搜索职缺 group-pmo」继续 Phase 2
- 旧 pending 职缺决策：#4 Bionorica(72)、#28 PUMA(67)、#29 Dahua(72) → PDF 或跳过
- #31 Intersnack(68)、#32 HelloFresh(82)、#33 Kraken(78) → 启动 cv-writer

---
