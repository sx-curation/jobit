# PLAN-multi-user.md

## 多用户架构补全计划

**目标**：消除多用户数据混用风险，使 amy / kelebogie 可独立运行完整流程，且不破坏 leon 的现有数据。

**核心原则**：所有改动向后兼容（`--uid` 默认值为 `"leon"`），每 Phase 独立可验证，Phase 之间可停顿。

---

## 风险评估矩阵

| ID | 问题 | 数据风险 | 触发条件 | 当前影响 |
|----|------|---------|---------|---------|
| R1 | Phase 2 脚本写到 `output/`（项目根目录） | **高** — 数据混用 | amy 触发搜索 | amy 暂时不用，潜在风险 |
| R2 | `check.py` 读 `config.json`（根目录遗留文件）| 中 — 误判通过 | 任何用户执行 check | leon 表面正常，实质错配 |
| R3 | `search_state.py` 模块级全局路径 | **高** — dedup 历史混用 | amy 搜索 | 同 R1 |
| R4 | 内层 `CLAUDE.md` 单用户路径 | 中 — Agent 读错指令 | 每次 session 启动 | Orchestrator 偶发行为异常 |
| R5 | `_current_user = 'leon'` hardcoded | 低 — UX 问题 | 新用户首次开 dashboard | 需手动 switch-user |
| R6 | `memory/` 目录未按用户隔离 | 低 — 未来风险 | 首次 session 结束后创建 | **目前 memory/ 不存在，暂无实际影响** |
| R7 | amy/kelebogie 无 scripts symlink | 低 — 工具缺失 | 未来在 user 目录下直接运行脚本 | 不影响 Claude Agent 流程 |

---

## 依赖图

```
Phase A (docs/config)
    └──► Phase B (check.py)
              └──► Phase C (Phase 2 scripts)
                        └──► Phase D (Orchestrator 指令)
                                   └──► Phase E (memory 隔离)  ← 可延后，目前无紧迫性
```

各 Phase 在前置完成前不可开始；Phase E 独立性最强，可单独排期。

---

## Phase A — 文档与配置修正（零风险，30 分钟）

**目标**：消除 R4、R5，无任何代码改动。

### A1. 修复内层 CLAUDE.md（R4）

**文件**：`1_generate_linkedin_cv/CLAUDE.md`

将以下 3 处**单用户路径**替换为多用户路径：

| 位置 | 当前 | 改为 |
|------|------|------|
| 启动步骤 3 | `读 \`config.json\`` | `读 \`users/<user id>/config.json\` 和 \`users.json\`` |
| 输出目录命名规则 | `output/<group_id>_<company>_<title>_<YYYYMMDD>/` | `users/<user id>/output/<group_id>_<company>_<title>_<YYYYMMDD>/` |
| 中间文件路径 | `output/temp/raw_results_<batch_id>.json` 等 | `users/<user id>/output/temp/raw_results_<batch_id>.json` 等 |

同步检查：`/check` 指令调用改为 `python3 scripts/check.py --uid {current_user}`

**验证**：diff 检查，无逻辑改动。

---

### A2. server.py 默认用户去硬编码（R5）

**文件**：`scripts/server.py` — 第 38 行

```python
# 当前
_current_user = 'leon'

# 改为（读 users.json 第一个用户，兜底仍为 leon）
def _load_default_user() -> str:
    try:
        data = json.loads(USERS_JSON.read_text(encoding='utf-8'))
        return data['users'][0]['id']
    except Exception:
        return 'leon'

_current_user = _load_default_user()
```

**风险**：极低。`users.json` 第一条是 leon，行为不变；其他用户加入后自动使用首个。

**验证**：重启 server.py，`GET /api/jobs` 返回 leon 数据（行为不变）。

---

## Phase B — check.py 多用户化（中复杂度，2 小时）

**目标**：消除 R2，使 `check.py` 对任意用户有效。

**依赖**：Phase A 完成后执行（CLAUDE.md 调用命令已更新）。

### B1. 添加 `--uid` 参数

**文件**：`scripts/check.py`

在 `main()` 的 argparse 块中添加：

```python
parser.add_argument("--uid", default="leon", help="用户 ID（对应 users/{uid}/ 目录）")
```

在检查函数调用前计算用户目录：

```python
USER_DIR = Path("users") / args.uid
```

### B2. 修正全部路径引用

以下 5 个函数需将路径基准从项目根改为 `USER_DIR`：

| 函数 | 当前路径 | 改为 |
|------|---------|------|
| `check_config()` | `Path(args.config)`（默认 `config.json`） | `USER_DIR / "config.json"`（`--config` 保留覆盖能力） |
| `check_cv_files()` | `Path(cv)` — 相对 CWD | `USER_DIR / cv` — 相对用户目录 |
| `check_cv_parsed_cache()` | `Path(f"output/cv_parsed_{gid}.json")` | `USER_DIR / "output" / f"cv_parsed_{gid}.json"` |
| `check_search_history()` | `Path("output/search_history.json")` | `USER_DIR / "output" / "search_history.json"` |
| `check_output_dir()` | `Path("output")` | `USER_DIR / "output"` |

`check_progress_files()` 暂保持原路径（memory/ 未创建，Phase E 统一处理）。

### B3. 新增 users.json 验证（可选但建议）

在 `check_config()` 之前执行：

```python
def check_users_json(verbose: bool):
    name, path = "users.json", Path("users.json")
    data = _load_json(path, name, "文件不存在（多用户模式不可用）")
    if data is None: return
    if "users" not in data or not isinstance(data["users"], list):
        record("ERROR", name, "缺少 'users' 数组")
        return
    for u in data["users"]:
        if "id" not in u: record("ERROR", name, f"用户条目缺少 'id' 字段: {u}")
    if verbose:
        ids = [u.get("id","?") for u in data["users"]]
        record("PASS", name, f"{len(ids)} 个用户：{', '.join(ids)}")
```

### B4. 更新 CLAUDE.md 调用命令

`/check` 指令的内部实现改为：
```
python3 scripts/check.py --uid {current_user_id}
```

**验证**：
```bash
python3 scripts/check.py --uid leon    # 应通过（或与当前行为相同）
python3 scripts/check.py --uid amy     # 应显示 amy 的配置状态
python3 scripts/check.py --uid nonexistent  # 应 ERROR: users/nonexistent/config.json 不存在
```

---

## Phase C — Phase 2 搜索脚本多用户化（高复杂度，4–6 小时）

**目标**：消除 R1、R3，这是本计划中改动量最大、风险最高的部分。

**依赖**：Phase B 完成，且已对 leon 运行 check.py 验证通过。

**策略**：不改函数签名，仅将模块级全局路径改为运行时根据 `--uid` 计算。

---

### C1. search_state.py — 全局路径参数化

**文件**：`scripts/search_state.py`（603 行）

**问题**：第 50–51 行的模块级全局变量被后续所有函数直接引用：
```python
HISTORY_PATH = Path("output/search_history.json")
OUTPUT_DIR   = Path("output")
```

**改法**：将这两个全局变量改为由 `init_paths(uid)` 函数设置，在 `main()` 入口调用一次：

```python
# 替换模块级全局
HISTORY_PATH: Path = None  # type: ignore
OUTPUT_DIR:   Path = None  # type: ignore

def init_paths(uid: str):
    global HISTORY_PATH, OUTPUT_DIR
    base = Path(__file__).resolve().parent.parent / "users" / uid
    OUTPUT_DIR   = base / "output"
    HISTORY_PATH = base / "output" / "search_history.json"
```

在 `main()` 最开头（argparse 解析后）调用：
```python
args = parser.parse_args()
init_paths(args.uid)
```

同时在 `argparse` 中添加 `--uid` 参数（default `"leon"`）。

**影响范围**：函数体内对 `HISTORY_PATH` / `OUTPUT_DIR` 的所有引用不需要改（全局变量引用在运行时动态解析）。

**关键边界**：`load_cv_skills()` 函数读取 `cv_parsed_{group_id}.json`，需要同样改为用户路径：
```python
# 当前（假设）
cv_path = OUTPUT_DIR / f"cv_parsed_{group_id}.json"
# 改后自动正确，因为 OUTPUT_DIR 已被 init_paths() 设置
```

---

### C2. run_phase2_search.py — 添加 `--uid` 参数

**文件**：`scripts/run_phase2_search.py`（647 行）

**改动**：

1. 删除第 40–42 行的模块级路径常量：
```python
# 删除
OUTPUT_DIR    = Path("output")
TEMP_DIR      = Path("output/temp")
CONFIG_PATH   = Path("config.json")
PROGRESS_LOG  = TEMP_DIR / "_search_progress.log"
PARTIAL_SAVE  = TEMP_DIR / "_phase2_temp_partial.json"
```

2. 在 `main()` 中（argparse 后）动态计算：
```python
args = parser.parse_args()
_BASE        = Path(__file__).resolve().parent.parent / "users" / args.uid
OUTPUT_DIR   = _BASE / "output"
TEMP_DIR     = _BASE / "output" / "temp"
CONFIG_PATH  = _BASE / "config.json"
PROGRESS_LOG = TEMP_DIR / "_search_progress.log"
PARTIAL_SAVE = TEMP_DIR / "_phase2_temp_partial.json"
```

3. 在 argparse 块添加：
```python
parser.add_argument("--uid", default="leon")
```

4. 修改 `search_state` 导入调用：`search_state.init_paths(args.uid)` 在路径计算后立即调用。

**注意**：`OUTPUT_DIR` 等变量在函数体内被直接引用（非通过参数传递），因此需要改为模块级但在 `main()` 入口赋值，或改为函数参数传递。推荐前者（改动量小，风险低）。

---

### C3. run_phase2_search_stepstone.py — 同 C2

**文件**：`scripts/run_phase2_search_stepstone.py`（490 行）

改法与 C2 相同：删除模块级路径常量，在 `main()` 入口动态计算，添加 `--uid`。

---

### C4. generate_summary.py — CLI 入口改造

**文件**：`scripts/generate_summary.py`（251 行）

函数 `load_all_analyses(output_dir)` 和 `load_last_seen(output_dir)` 已接受 `output_dir` 参数（✅ 不需改）。

只需修改 `main()` 的 argparse：

```python
# 当前：--output-dir（如果有）
# 新增：
parser.add_argument("--uid", default="leon")

# main() 中：
if args.uid:
    base = Path(__file__).resolve().parent.parent / "users" / args.uid
    output_dir = base / "output"
else:
    output_dir = Path(args.output_dir)  # 保留原有方式
```

---

### C5. 回归测试（Phase C 完成后必做）

```bash
# 1. leon 正常搜索路径验证（不实际搜索，只看路径计算）
python3 scripts/search_state.py --uid leon --mode summary
python3 scripts/generate_summary.py --uid leon

# 2. amy 路径隔离验证
python3 scripts/search_state.py --uid amy --mode summary
# 预期：输出 "users/amy/output/search_history.json 不存在"，不读 leon 的历史

# 3. check.py 验证
python3 scripts/check.py --uid leon --verbose
python3 scripts/check.py --uid amy
```

---

## Phase D — Orchestrator 指令同步（低复杂度，1 小时）

**目标**：确保 Agent 调用所有脚本时传入 `--uid {uid}`。

**依赖**：Phase C 完成（脚本已接受 `--uid`）。

**文件**：`.claude/agents/Orchestrator.md`

需检查并更新以下调用点（搜索 `python` / `scripts/`）：

| 调用 | 当前 | 改为 |
|------|------|------|
| Phase 2B 搜索 | `python scripts/run_phase2_search.py` | `python scripts/run_phase2_search.py --uid {uid}` |
| Phase 2B Stepstone | `python scripts/run_phase2_search_stepstone.py` | `...--uid {uid}` |
| Phase 2C 去重 | `python scripts/search_state.py --mode dedup ...` | `...--uid {uid}` |
| Phase 2E 汇总 | `python scripts/generate_summary.py` | `...--uid {uid}` |
| check 调用 | `python3 scripts/check.py` | `...--uid {uid}` |

**验证**：grep Orchestrator.md，确认无遗漏的 `python scripts/` 调用缺少 `--uid`。

---

## Phase E — Memory 目录用户隔离（低紧迫性，1.5 小时）

> **当前状态**：`memory/` 目录不存在，首次 session 结束后由 progress-writer agent 创建。此 Phase 应在 Phase D 完成后、第一次真正多用户 session 前执行。

**目标**：消除 R6，使每个用户的 session 状态独立。

### E1. progress-writer agent 改路径

**文件**：`.claude/agents/progress-writer.md`

将写入路径从 `memory/progress.json` / `memory/notes.md` 改为：
- `users/{uid}/memory/progress.json`
- `users/{uid}/memory/notes.md`

Agent 接受 `uid` 参数（由 Orchestrator 在 session 结束时传入）。

### E2. check.py memory 路径同步

**文件**：`scripts/check.py`（接 Phase B 改动）

`check_progress_files()` 中：
```python
# 改为
pj = USER_DIR / "memory" / "progress.json"
nm = USER_DIR / "memory" / "notes.md"
```

### E3. CLAUDE.md session 启动同步

启动步骤 1–2 改为读 `users/{uid}/memory/progress.json` 和 `users/{uid}/memory/notes.md`。

### E4. 现有 leon 数据迁移（如 memory/ 已存在时执行）

```python
# 一次性迁移（如 memory/ 已存在）
import shutil, pathlib
for uid in ["leon"]:
    src = pathlib.Path("memory")
    dst = pathlib.Path(f"users/{uid}/memory")
    if src.exists() and not dst.exists():
        shutil.copytree(src, dst)
        print(f"Copied memory/ → users/{uid}/memory/  (原目录保留为备份)")
```

---

## 不纳入本计划的项（评估后搁置）

| 项目 | 原因 |
|------|------|
| Windows symlink 补全（amy/kelebogie） | Agent 流程不依赖 symlink；CLI 直接调用场景用户目前为零 |
| `--uid` vs `--user` backfill 命名统一 | backfill 是一次性脚本，命名不一致不影响自动化流程 |
| 并发用户文件锁 | 当前 server.py 已全局互斥；多设备并发场景尚无需求 |
| users.json → SQLite 迁移 | 用户数 < 10，文件系统方案足够 |
| generate_pdf.py `--uid` | 该脚本接受绝对路径作为 input/output 参数，调用方传正确路径即可 |

---

## 执行总览

| Phase | 文件数 | 估计行改动 | 风险 | 耗时 | 优先级 |
|-------|--------|-----------|------|------|--------|
| A — docs/config | 2 | ~15 行 | 极低 | 30 min | 立即 |
| B — check.py | 1 | ~40 行 | 低 | 2 hr | 本周 |
| C — Phase 2 脚本 | 4 | ~80 行 | 中（有回归风险） | 4–6 hr | 本周 |
| D — Orchestrator | 1 | ~10 行 | 低 | 1 hr | Phase C 后 |
| E — memory 隔离 | 3 | ~30 行 | 低（memory/ 尚不存在）| 1.5 hr | 首次多用户 session 前 |

**全部合计**：约 175 行净改动，涉及 11 个文件。

---

## 回滚策略

- **Phase A**：git revert 即可，无数据风险
- **Phase B**：`python3 scripts/check.py`（无 `--uid`）默认行为不变（default="leon"）
- **Phase C**：git revert + 验证 `python3 scripts/search_state.py --mode summary` 输出正确；leon 的 `output/` 数据在 `users/leon/output/` 中，不受脚本路径改动影响
- **Phase D**：Orchestrator.md git revert
- **Phase E**：如 `memory/` 已迁移，用备份恢复；如未迁移，直接 revert agent MD

---

## 验证 Checklist（全 Phase 完成后）

```
□ python3 scripts/check.py --uid leon   → 0 errors
□ python3 scripts/check.py --uid amy    → 读到 users/amy/config.json，0 errors
□ python3 scripts/search_state.py --uid amy --mode summary
                                        → 输出"无搜索历史"，不读 leon 数据
□ python3 scripts/generate_summary.py --uid amy
                                        → 输出"users/amy/output 不存在或为空"
□ server.py 重启后首个 GET /api/current-user → 返回 users.json 第一个用户
□ dashboard 切换到 amy → /api/jobs 返回空列表，不返回 leon 的职缺
□ leon 全流程搜索（小批量）→ 结果写入 users/leon/output/，行为与当前完全一致
```
