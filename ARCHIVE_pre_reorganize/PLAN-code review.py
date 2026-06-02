Jobit 代码审查报告（CTO 视角）      
                                     
 ▎ 审查范围：F:\Claude code project\jobit\ 全项目
 ▎ 审查日期：2026-05-31
 ▎ 审查人：Claude (Sonnet 4.6) — 以 10 年 B2B 招聘产品 CTO 视角

 ---
 总体评价

 架构意图清晰：工作区隔离 + 共享基础设施（junction/硬链接）设计合理，Phase 1–4 编排流程文档完善。
 主要风险：并发安全不足（竞态条件）、数据 schema 不一致（跨用户字段名分歧）、缺乏测试。
 当前适用场景：单用户单 session 运行稳定；多用户并发场景有中高风险问题。

 ---
 一、数据 Schema 不一致（立即影响现有功能）

 1.1 jd_analysis.json 字段名分歧（CRITICAL）

 ┌──────────┬──────────────┬───────────────────┬───────────────────────────────────────────────────────┐
 │   字段   │ Leon（旧版） │ Kelebogie（新版） │                         影响                          │
 ├──────────┼──────────────┼───────────────────┼───────────────────────────────────────────────────────┤
 │ 分数字段 │ match_score  │ score             │ /api/search-analysis 旧代码读 match_score，Kelebogie  │
 │          │              │                   │ 数据全为 0                                            │
 ├──────────┼──────────────┼───────────────────┼───────────────────────────────────────────────────────┤
 │ 来源字段 │ _source      │ source            │ parse_jobs 中来源过滤可能失效                         │
 ├──────────┼──────────────┼───────────────────┼───────────────────────────────────────────────────────┤
 │ group_id │ 缺失         │ 存在              │ 无法按 group 过滤 Leon 的部分旧数据                   │
 ├──────────┼──────────────┼───────────────────┼───────────────────────────────────────────────────────┤
 │ analyzed │ 缺失         │ 存在              │ 搜索分析时间轴不完整                                  │
 └──────────┴──────────────┴───────────────────┴───────────────────────────────────────────────────────┘

 根因：jd-analyzer agent 在不同时间有过 schema 变更，但旧数据未做迁移。

 修复方案（已在 server.py 中应用）：
 # server.py line 453 — 兼容两个字段名
 score = jd.get("score") or jd.get("match_score")
 # server.py line 498 — seen_jobs 为空时 fallback 到 fetched_per_keyword
 distinct = kw_distinct.get(kw, _fetch_count)

 长期建议：写一次 migration script，将 Leon 的旧 jd_analysis.json 统一成新 schema。

 ---
 二、并发安全问题

 2.1 Watchdog 线程读取 _search_proc 无锁（HIGH）

 位置：scripts/server.py lines 536–557
 问题：Watchdog 线程读取全局 _search_proc 时未持有 _search_lock，可能 kill 掉下一个用户的搜索进程。

 # 当前代码（有问题）
 def _watchdog():
     time.sleep(_SEARCH_MAX_S)
     proc = _search_proc  # ← 无锁读取全局变量
     if proc and proc.poll() is None:
         proc.kill()

 # 修复：传参而非读全局
 def _watchdog(proc):
     time.sleep(_SEARCH_MAX_S)
     if proc.poll() is None:
         proc.kill()
 threading.Thread(target=_watchdog, args=(_search_proc,), daemon=True).start()

 2.2 用户切换与搜索启动之间存在竞态窗口（HIGH）

 位置：/api/switch-user handler lines 817–834
 问题：检查 _search_lock 后释放，再调用 _set_current_uid()，中间窗口可能导致搜索以错误的用户上下文运行。

 修复思路：将 switch-user 逻辑整体包入一个复合锁，或使用状态机禁止搜索中切换用户。

 2.3 _jobs_cache 返回浅拷贝（MEDIUM）

 位置：line 111 return list(_jobs_cache[uid])
 问题：list 浅拷贝，但元素仍是可变 dict；某请求修改 job 对象会影响后续所有请求。
 修复：return [dict(j) for j in _jobs_cache[uid]] 或用 copy.deepcopy。

 2.4 更新 JD 字段后未失效缓存（MEDIUM）

 位置：_update_jd_field() lines 873–885（/api/record, /api/note）
 问题：写入 jd_analysis.json 后，_jobs_cache 未清除 → 下次 /api/jobs 返回旧数据。
 修复：在 _write_lock 块结束后加 _jobs_cache_mtime[uid] = 0.0。

 ---
 三、冗余逻辑与代码质量问题

 3.1 去重逻辑在两处实现（MEDIUM）

 ┌────────────────────────┬──────────────────────┬──────────────────────────────────────┐
 │          位置          │         函数         │               去重策略               │
 ├────────────────────────┼──────────────────────┼──────────────────────────────────────┤
 │ search_state.py:295    │ dedup_and_sort()     │ (company, title) 去重，LinkedIn 优先 │
 ├────────────────────────┼──────────────────────┼──────────────────────────────────────┤
 │ generate_summary.py:78 │ cross_source_dedup() │ 相同逻辑，不同实现，最高分优先       │
 └────────────────────────┴──────────────────────┴──────────────────────────────────────┘

 风险：两处策略不同步，同一 job 在不同路径下可能有不同去重结果。

 3.2 search_history.json 在一次请求中被多次读取（LOW）

 - compute_group_stats() 调用 _load_search_batches()
 - compute_search_analysis() 再次独立读取同一文件
 - 无缓存，每次请求重复 I/O

 建议：将 _load_search_batches() 的结果传参，或加轻量缓存。

 3.3 gen_job_tracker_html.py 体量过大（INFO）

 2,277 行 HTML 模板生成器，混合了 UI 逻辑和数据处理。
 建议：长期将 HTML 拆为真正的模板文件（Jinja2），降低维护成本。

 3.4 leon 用户硬编码特殊路径（LOW）

 # server.py lines 47-59
 if uid == 'leon' and not out_dir.exists():
     out_dir = OUTPUT_DIR  # legacy fallback

 风险：junction 失效时静默 fallback 到 PROJECT_DIR，不报错。
 建议：移除特判，确保 leon 的 junction 存在，或记录 WARN log。

 ---
 四、架构可扩展性问题

 4.1 单全局搜索进程（MEDIUM）

 _search_proc 是全局单例，用户 B 的搜索会被用户 A 的进程 block。
 短期：可接受（当前用户数 < 5）。
 中期：改为 per-user subprocess dict {uid: proc}。

 4.2 config.json 写入无分布式锁（MEDIUM）

 /api/group-save, /api/group-delete, /api/group-dup 都直接写文件，无锁。
 风险：多个 Claude session 同时修改 config 可能导致 JSON 损坏。
 建议：引入文件锁（fcntl/msvcrt）或 SQLite 事务。

 4.3 前端 localStorage 未按用户命名空间隔离（LOW）

 localStorage.setItem('jt_filter', ...) 全局共享。
 风险：切换用户后，上一用户的过滤器残留在 UI 中。
 修复：改为 jt_filter_<uid>。

 4.4 缺少测试（HIGH — 长期风险）

 当前无任何单元测试或集成测试文件。
 建议：至少对 compute_search_analysis()、parse_jobs()、_update_jd_field() 添加 pytest 测试。

 ---
 五、安全问题

 ┌────────┬──────────────────────────────────────────────────┬──────────────────┐
 │ 严重度 │                       问题                       │       位置       │
 ├────────┼──────────────────────────────────────────────────┼──────────────────┤
 │ MEDIUM │ 无身份验证，任意客户端可切换用户                 │ /api/switch-user │
 ├────────┼──────────────────────────────────────────────────┼──────────────────┤
 │ LOW    │ /api/cvfile 路径注入防护基本但可绕过（URL 编码） │ lines 640–650    │
 ├────────┼──────────────────────────────────────────────────┼──────────────────┤
 │ LOW    │ 新用户 user_id 未严格校验格式                    │ line 847         │
 └────────┴──────────────────────────────────────────────────┴──────────────────┘

 ---
 六、优先行动清单

 立即修复（影响已有功能）

 1. ✅ server.py:453 — score vs match_score 字段兼容读取（已应用）
 2. ✅ server.py:498 — seen_jobs 为空时 fallback 到 _fetch_count（已应用）
 3. server.py:885 — JD 字段更新后清除缓存 _jobs_cache_mtime[uid] = 0.0

 近期修复（稳定性）

 4. server.py:536–557 — Watchdog 传参而非读全局
 5. server.py:111 — 返回深拷贝防止跨请求数据污染
 6. search_state.py + generate_summary.py — 合并去重逻辑

 中期改进（可扩展性）

 7. 迁移 Leon 的旧 jd_analysis.json 到新 schema（match_score → score）
 8. localStorage 按 uid 命名空间隔离
 9. /api/switch-user 加复合锁防竞态
 10. config.json 写操作加文件锁

 长期（架构升级）

 11. 添加测试覆盖核心计算函数
 12. Per-user 搜索进程支持
 13. HTML 模板拆分（Jinja2）

 ---
 七、多用户迁移遗留文件清理方案

 背景与现状

 migrate_to_multiuser.py 执行时复制了数据而未删除源目录，导致根目录遗留了 Leon 的旧工作区快照。

 1_generate_linkedin_cv/          【当前实际状态】
 ├── config.json    ← Leon 旧 config（max_jobs=1，已过时，服务器不读）
 ├── output/        ← Leon 迁移时快照（608 文件，服务器不写这里）
 ├── memory/        ← Leon 旧 memory（服务器不读）
 ├── my_cv/         ← Leon 旧 CV 副本（服务器不读）
 ├── scripts/       ← 【权威】所有 users/*/scripts/ 的 symlink 目标
 ├── graphify-out/  ← 【权威】应作为所有用户的共享 junction 源
 ├── .claude/       ← 【权威】users/leon/.claude/ 已是 junction 指向这里
 ├── SPEC.md        ← 【权威】users/leon/SPEC.md 是 hard link
 └── users/
     ├── leon/
     │   ├── config.json    ← 【活跃】服务器读写这里
     │   ├── output/        ← 【活跃】608 文件，迁移后所有新数据写这里
     │   ├── .claude/       ← junction → ../../.claude/（已正确）
     │   ├── scripts/       ← symlink → ../../scripts/（已正确）
     │   └── graphify-out/  ← 独立副本（问题：未与根目录同步）
     └── kelebogie/
         ├── scripts/       ← symlink → ../../scripts/（已正确）
         └── graphify-out/  ← 独立副本（同上问题）

 ---
 依赖关系图

 根目录 scripts/
     ↑ symlink
 users/leon/scripts/       ← check.py、server.py、run_phase2 都在这里
 users/kelebogie/scripts/  ← 同上

 根目录 .claude/
     ↑ junction
 users/leon/.claude/       ← Orchestrator.md、agent 定义都在这里

 根目录 graphify-out/      ← graphify update 写这里（当前唯一更新点）
 users/leon/graphify-out/  ← 独立副本，graphify 不更新这里（过时）
 users/kelebogie/graphify-out/ ← 同上

 根目录 config.json        ← 旧版 Leon 配置，scripts 如从根目录执行会误读
 users/leon/config.json    ← 现行 Leon 配置（server.py 读这里）
 users/kelebogie/config.json ← Kelebogie 配置（server.py 读这里）

 关键风险点：check.py 若从 1_generate_linkedin_cv/ 目录执行，会读到根目录旧版
 config.json，导致校验通过但配置实际不符。

 ---
 分步执行方案

 Step 0：验证（执行前，只读，无破坏性）

 目的：确认数据一致性，建立清理安全基线。

 # 0-1. 确认 users/leon/output/ 是超集（包含根目录 output/ 的所有文件）
 diff <(ls "F:/Claude code project/jobit/1_generate_linkedin_cv/output/" | sort) \
      <(ls "F:/Claude code project/jobit/1_generate_linkedin_cv/users/leon/output/" | sort)

 # 0-2. 确认 check.py 读取路径
 grep -n "config" "F:/Claude code project/jobit/scripts/check.py" | head -20

 # 0-3. 确认根目录 config.json 是否被任何脚本直接 import
 grep -rn "1_generate_linkedin_cv/config.json\|PROJECT_DIR.*config" \
     "F:/Claude code project/jobit/scripts/"

 通过条件：
 - diff 无差异（或 users/leon/output/ 包含根目录所有文件）
 - check.py 使用相对路径或接受 --uid 参数，可指向 users/leon/
 - 无脚本硬编码读取根目录 config.json

 风险：若 diff 显示根目录 output/ 有 users/leon/ 没有的文件，停止，需手动合并。

 ---
 Step 1：归档根目录遗留文件（低风险，可完全回滚）

 目的：不立即删除，先移入 ARCHIVE 目录，确认系统正常后再清除。

 # 1-1. 创建归档目录
 mkdir -p "F:/Claude code project/jobit/1_generate_linkedin_cv/ARCHIVE_pre_multiuser"

 # 1-2. 移动遗留文件（保留目录结构）
 mv "F:/Claude code project/jobit/1_generate_linkedin_cv/config.json" \
    "F:/Claude code project/jobit/1_generate_linkedin_cv/ARCHIVE_pre_multiuser/"
 mv "F:/Claude code project/jobit/1_generate_linkedin_cv/output" \
    "F:/Claude code project/jobit/1_generate_linkedin_cv/ARCHIVE_pre_multiuser/"
 mv "F:/Claude code project/jobit/1_generate_linkedin_cv/memory" \
    "F:/Claude code project/jobit/1_generate_linkedin_cv/ARCHIVE_pre_multiuser/"
 mv "F:/Claude code project/jobit/1_generate_linkedin_cv/my_cv" \
    "F:/Claude code project/jobit/1_generate_linkedin_cv/ARCHIVE_pre_multiuser/"

 保留不动：scripts/、graphify-out/、.claude/、SPEC.md、CLAUDE.md、users.json、UI.md、setup.*

 回滚方式：将 ARCHIVE_pre_multiuser/ 下的文件移回原位。

 依赖：Step 0 通过后才可执行。

 ---
 Step 2：修复 server.py 中的 leon 硬编码特判（中风险）

 位置：scripts/server.py lines 47–59

 # 当前代码（需修改）
 def _user_paths(uid: str) -> dict:
     user_dir = USERS_DIR / uid
     out_dir  = user_dir / 'output'
     if uid == 'leon' and not out_dir.exists():   # ← 删除这段
         out_dir  = OUTPUT_DIR
         user_dir = PROJECT_DIR

 # 修改后（统一所有用户逻辑）
 def _user_paths(uid: str) -> dict:
     user_dir = USERS_DIR / uid
     out_dir  = user_dir / 'output'
     if not out_dir.exists():
         raise ValueError(f"Output dir not found for user '{uid}': {out_dir}")

 风险：Step 1 完成后 ARCHIVE_pre_multiuser/output/ 已不在原位，如果 fallback
 被触发就会报错。这正是我们想要的——强制所有流量走 users/leon/。

 依赖：Step 1 完成后执行（确保根目录 output/ 已移走，不再干扰）。

 验证：重启 server，切换到 Leon，访问 /api/jobs，数据正常则通过。

 ---
 Step 3：修复 graphify-out/ 为 junction（低风险）

 目的：让所有用户共享同一份知识图谱，graphify 更新一次即全部生效。

 REM Windows 命令（需管理员权限或开发者模式）

 REM 3-1. Leon
 rmdir "F:\Claude code project\jobit\1_generate_linkedin_cv\users\leon\graphify-out"
 mklink /J "F:\Claude code project\jobit\1_generate_linkedin_cv\users\leon\graphify-out" ^
           "F:\Claude code project\jobit\1_generate_linkedin_cv\graphify-out"

 REM 3-2. Kelebogie
 rmdir "F:\Claude code project\jobit\1_generate_linkedin_cv\users\kelebogie\graphify-out"
 mklink /J "F:\Claude code project\jobit\1_generate_linkedin_cv\users\kelebogie\graphify-out" ^
           "F:\Claude code project\jobit\1_generate_linkedin_cv\graphify-out"

 风险：若 graphify-out/ 内有用户特定数据（如用户个人 wiki），共享会造成数据混淆。
 - 当前评估：graphify 分析的是代码结构（scripts/、SPEC.md），与用户数据无关，共享安全。
 - 验证：执行后检查 graphify-out/GRAPH_REPORT.md 是否可从两个用户目录正常访问。

 依赖：Step 1、2 完成后执行（确保环境稳定再调整 junction）。

 ---
 Step 4：修复 check.py 的 config 读取路径（中风险）

 问题：check.py 可能从根目录运行，读取旧版 config.json。Step 1 后根目录已无 config.json，check.py
 将报错找不到文件。

 # check.py 需要支持 --uid 参数，或从环境变量获取用户目录
 # 修改前（假设从根目录读 config）：
 config = json.load(open('config.json'))

 # 修改后：
 import argparse
 parser = argparse.ArgumentParser()
 parser.add_argument('--uid', default='leon')
 args = parser.parse_args()
 config_path = USERS_DIR / args.uid / 'config.json'
 config = json.load(open(config_path))

 具体修改需先读 check.py 第 1–50 行确认当前路径逻辑再动手。

 依赖：Step 1 之前先检查（Step 0），确认影响范围。

 ---
 Step 5：清理 ARCHIVE（在观察期结束后）

 建议观察期：7 天。确认 Leon 和 Kelebogie 的所有功能正常后执行。

 rm -rf "F:/Claude code project/jobit/1_generate_linkedin_cv/ARCHIVE_pre_multiuser/"

 依赖：Steps 1–4 全部通过且稳定运行一段时间。

 ---
 执行顺序总结

 Step 0（验证）
     ↓ 通过
 Step 1（归档遗留文件）← 可回滚
     ↓
 Step 2（移除 server.py leon 特判）← 依赖 Step 1
     ↓                              否则 fallback 仍可能触发
 Step 3（修复 graphify junction）← 独立，可与 Step 2 并行
     ↓
 Step 4（修复 check.py 路径）← 需先读代码，确认影响范围
     ↓
 Step 5（清理 ARCHIVE，7 天后）

 ---
 风险矩阵

 ┌──────┬───────────────────┬──────────┬──────────────────┬──────────────┐
 │ Step │       操作        │ 风险等级 │     回滚方式     │   前置条件   │
 ├──────┼───────────────────┼──────────┼──────────────────┼──────────────┤
 │ 0    │ 验证 diff         │ 无       │ N/A              │ 无           │
 ├──────┼───────────────────┼──────────┼──────────────────┼──────────────┤
 │ 1    │ 归档遗留文件      │ 低       │ mv 回原位        │ Step 0 通过  │
 ├──────┼───────────────────┼──────────┼──────────────────┼──────────────┤
 │ 2    │ 移除 leon 特判    │ 中       │ git revert       │ Step 1 完成  │
 ├──────┼───────────────────┼──────────┼──────────────────┼──────────────┤
 │ 3    │ graphify junction │ 低       │ rmdir + 解压备份 │ Step 1 完成  │
 ├──────┼───────────────────┼──────────┼──────────────────┼──────────────┤
 │ 4    │ check.py 路径     │ 中       │ git revert       │ 读代码确认后 │
 ├──────┼───────────────────┼──────────┼──────────────────┼──────────────┤
 │ 5    │ 删除 ARCHIVE      │ 不可逆   │ 无（需提前备份） │ 7 天观察期   │
 └──────┴───────────────────┴──────────┴──────────────────┴──────────────┘

 ---
 关键文件路径参考

 ┌────────────────────────────────────────┬───────────────────────────────────┐
 │                  文件                  │             关键职责              │
 ├────────────────────────────────────────┼───────────────────────────────────┤
 │ scripts/server.py                      │ HTTP server、多用户状态、缓存管理 │
 ├────────────────────────────────────────┼───────────────────────────────────┤
 │ scripts/check.py                       │ 启动验证，需确认 config 读取路径  │
 ├────────────────────────────────────────┼───────────────────────────────────┤
 │ scripts/search_state.py                │ 去重、batch 管理、offset 追踪     │
 ├────────────────────────────────────────┼───────────────────────────────────┤
 │ scripts/generate_summary.py            │ job_summary.md 写入               │
 ├────────────────────────────────────────┼───────────────────────────────────┤
 │ scripts/migrate_to_multiuser.py        │ 迁移脚本（已执行，仅参考）        │
 ├────────────────────────────────────────┼───────────────────────────────────┤
 │ users/{uid}/output/search_history.json │ 搜索历史 + seen_jobs              │
 ├────────────────────────────────────────┼───────────────────────────────────┤
 │ users/{uid}/output/*/jd_analysis.json  │ JD 分析结果（schema 需统一）      │
 ├────────────────────────────────────────┼───────────────────────────────────┤
 │ 1_generate_linkedin_cv/graphify-out/   │ 权威知识图谱目录                  │

八、jobit 根目录 vs 1_generate_linkedin_cv/ 权威性分析

 背景

 jobit/ 是 git 仓库根目录，原始结构是单项目直接放在根目录。
 后来为组织多项目（1_generate_linkedin_cv/、1_generate_linux_cv/）将项目复制到子目录，但根目录文件未删除，
 导致两层目录同时存在类似的文件结构。

 ---
 权威性对照表

 ┌──────────────────────────┬──────────────────────────────┬──────────────────────┬──────────────────┐
 │        文件/目录         │           权威位置           │      根目录状态      │       风险       │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │                          │                              │ jobit/scripts/ (912  │ HIGH —           │
 │ scripts/server.py        │ 1_generate_linkedin_cv/scrip │ 行，缺少本次所有修复 │ 若从根目录启动   │
 │                          │ ts/ (1018行，含所有修复)     │ )                    │ server，所有修复 │
 │                          │                              │                      │ 失效             │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ scripts/gen_job_tracker_ │ 1_generate_linkedin_cv/scrip │ jobit/scripts/       │ MEDIUM           │
 │ html.py                  │ ts/                          │ (旧版，字节差异)     │                  │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ scripts/ 其他文件        │ 两处内容相同                 │ 同步                 │ LOW              │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ .claude/agents/          │ 两处内容相同                 │ 相同                 │ INFO             │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ .claude/settings.json    │ 两处内容相同                 │ 相同                 │ INFO             │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ .claude/settings.local.j │ 1_generate_linkedin_cv/.clau │ jobit/.claude/       │ MEDIUM           │
 │ son                      │ de/ (更新，4881B)            │ (旧版，2896B + .bak) │                  │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ .claude/agent-memory/    │ 1_generate_linkedin_cv/.clau │ jobit/.claude/ (缺   │ MEDIUM           │
 │                          │ de/ (含 kelebogie profile)   │ kelebogie profile)   │                  │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ graphify-out/            │ 1_generate_linkedin_cv/graph │ jobit/graphify-out/  │ LOW              │
 │                          │ ify-out/                     │ (旧版)               │                  │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ CLAUDE.md                │ 两处内容完全相同             │ 同步                 │ 无               │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ SPEC.md                  │ 两处内容完全相同             │ 同步                 │ 无               │
 ├──────────────────────────┼──────────────────────────────┼──────────────────────┼──────────────────┤
 │ setup.sh / setup.ps1     │ 两处内容完全相同             │ 同步                 │ 无               │
 └──────────────────────────┴──────────────────────────────┴──────────────────────┴──────────────────┘

 ---
 关键风险：server.py 两个版本并存（HIGH）

 jobit/scripts/server.py           ← 912 行，旧版，缺少所有近期修复
 jobit/1_generate_linkedin_cv/scripts/server.py  ← 1018 行，当前活跃版本
                                      ↑ users/*/scripts/ symlink 指向这里

 用户影响：若有人从 jobit/ 根目录运行 python scripts/server.py，会启动旧版 server，本次所有修复（Fix
 #1–Fix #10）全部失效，且没有任何错误提示。

 Claude Code 运行位置：从 users/{uid}/ 运行时，.claude/ 和 scripts/ 都通过 symlink/junction 指向
 1_generate_linkedin_cv/ 下的版本，是正确的。

 ---
 清理方案（按优先级）

 立即处理：防止意外启动旧 server（HIGH）

 方案 A（推荐）：在根目录 jobit/scripts/server.py 首行加重定向提示，防止误用：

 #!/usr/bin/env python3
 """
 ⚠ 此文件已过时。请从以下路径运行最新版本：
    cd 1_generate_linkedin_cv && python scripts/server.py
 """
 import sys
 print("ERROR: 此版本已过时，请从 1_generate_linkedin_cv/ 目录运行 server.py", file=sys.stderr)
 sys.exit(1)

 方案 B：直接删除根目录 jobit/scripts/server.py（不可逆，需 git 可回滚）

 方案 C：归档整个根目录 jobit/scripts/（同 1_generate_linkedin_cv 清理逻辑）

 近期处理：同步 .claude/ 状态（MEDIUM）

 根目录 jobit/.claude/settings.local.json 比子目录旧，agent-memory 也缺少 kelebogie profile。
 两者的 agents/ 和 settings.json 内容相同，无需处理。

 方案：复制 1_generate_linkedin_cv/.claude/settings.local.json → jobit/.claude/settings.local.json
 并同步 agent-memory/ 下的用户 profile 文件。

 长期：统一根目录结构

 根目录 jobit/ 保留：
 - .git/、.gitignore（必须）
 - CLAUDE.md、.claude/（Claude Code 顶层配置，层叠加载）
 - 1_generate_linkedin_cv/、1_generate_linux_cv/（子项目）

 归档/删除：
 - jobit/scripts/（旧版，被 1_generate_linkedin_cv/scripts/ 取代）
 - jobit/graphify-out/（旧版，被子目录取代）
 - jobit/config.json、jobit/output/、jobit/my_cv/、jobit/memory/（单用户时代遗留，已无人使用）
 - jobit/PLAN-code review.py（临时文件）

 ---
 执行顺序

 立即（防误用）
   └── 根目录 jobit/scripts/server.py 加 exit(1) 提示

 近期（同步状态）
   └── 同步 .claude/settings.local.json + agent-memory

 长期（7天观察期后）
   └── 归档 jobit/scripts/、jobit/graphify-out/、jobit 旧数据目录