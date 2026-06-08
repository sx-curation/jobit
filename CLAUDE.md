# LinkedIn CV Agent

## 启动必读（每次 session，不得跳过）

1. 读 `memory/progress.json` — 先判断是否首次 session（文件不存在 = 首次）
   - **首次 session**（文件不存在）：读 `SPEC.md` 获取架构背景
   - **非首次 session**：跳过 SPEC.md（架构不变，notes.md 已有摘要）
2. 读 `memory/notes.md` — 上次决策脉络（不存在则跳过）
3. 读 `users/<user id>/config.json`和`users.json` — keyword groups 与 CV 对应关系（source of truth）
4. 运行 sanity check：`python3 scripts/check.py --uid {current_user}`
   - ERROR → 停止，等用户修复
   - WARN  → 展示警告，询问是否继续

完成后汇报：「已就绪，当前状态：<一句话总结>」

---

## 执行流程

完整流程见 `.claude/agents/Orchestrator.md`（Phase 1 解析 → 2 搜索+JD分析 → 3A CV+CL 生成 → 3A.5 评估 → 3B 审核 → 3C 主题 → 3D PDF → 4 汇总）。

---

## 重要规则

- CV 与 group 严格对应，见 `config.json`，禁止混用
- `my_cv/` 和 `SPEC.md` 只读
- 不自动投递
- 不编造经历（CV 只重新措辞，不添加虚构内容）
- 输出目录命名：`users/<user id>/output/<group_id>_<company>_<title>_<YYYYMMDD>/`（YYYYMMDD = batch_id 的前 8 位）
- 中间文件：`users/<user id>/output/temp/raw_results_<batch_id>.json`、`output/temp/_phase2_temp*.json`（不用 /tmp）
- jd-analyzer 并行上限：3 个

---

## 指令

| 指令 | 行为 |
|------|------|
| `开始` | 完整执行 Phase 1-4 |
| `解析 CV` / `解析 CV <group-id>` | 单独执行 Phase 1（解析 CV 并输出 cv_parsed JSON），可指定 group；已有缓存则跳过 |
| `搜索职缺 [group-id]` | LinkedIn + Stepstone 双源搜索（Phase 2 完整流程） |
| `搜索LinkedIn职缺 [group-id]` | 仅 LinkedIn 搜索（跳过 Stepstone） |
| `搜索Stepstone职缺 [group-id]` | 仅 Stepstone 搜索（需 stepstone.enabled=true） |
| `搜索Linkedin posting职缺 [group-id]` | 从 LinkedIn 社交帖子搜索招聘信号，提取职缺链接并执行 JD 分析；无 group-id 则搜索所有 group |
| `生成 CV <编号>` | 只为指定职缺执行 Phase 3 |
| `生成CL <job编号>` | 生成 cover_letter_draft.md + cover_letter.pdf + cover_letter.docx（如无 story-bank 先Bootstrap） |
| `面试准备 <job编号>` | 自动读取 story-bank 选故事、匹配 JD archetype、生成 cover_letter_draft.md + PDF |
| `显示全部` | 显示低分隐藏职缺 |
| `/check` | 单独运行 sanity check |
| `/check --verbose` | 显示所有通过项 |
| `/themes` | 列出可用 PDF 视觉主题（不含 ats——ats 版本每次 --dual 时自动生成，无需指定） |
| `/status` | progress.json + 搜索历史摘要 |
| `/progress` | memory/notes.md 最近 3 条笔记 |
| `/reset-history` | 清空 search_history.json（慎用）|

---

## 上下文管理（自动 compact）
默认英文输出/com
以下两种情况，**必须**在回复末尾追加 compact 提示块，不得省略：

### 触发条件 1：Phase 切换
Phase/Batch 完成切换时，先输出：完成（产出）/ 决策 / 下一步，再追加：
> 上下文已增长，请运行 `/compact` 后继续。

### 触发条件 2：长文本输出
单次回复 > 60 行时，末尾追加：
> 回复较长，建议运行 `/compact` 压缩上下文。

# Design Principle

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
