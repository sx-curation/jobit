#!/usr/bin/env python3
"""
scripts/check.py — 启动 baseline 验证

退出码：0 = 通过（含警告）  1 = 有 ERROR

用法：
  python3 scripts/check.py
  python3 scripts/check.py --verbose
  python3 scripts/check.py --config path/to/config.json
"""

import argparse, json, os, sys, time, subprocess, urllib.request, urllib.error
from pathlib import Path

from common import UVX, make_mcp_proc, send_recv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASS  = "\033[32m  PASS \033[0m"
WARN  = "\033[33m  WARN \033[0m"
ERROR = "\033[31m  ERROR\033[0m"
INFO  = "\033[36m  INFO \033[0m"

results: list[tuple[str, str, str]] = []

def record(level, name, msg): results.append((level, name, msg))

def _load_json(path: Path, name: str, absent_msg: str = "") -> "dict | list | None":
    if not path.exists():
        if absent_msg:
            record("INFO", name, absent_msg)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        record("ERROR", name, f"JSON 损坏：{e}")
        return None

def _check_schema(data: dict, schema: dict, name: str, level: str = "ERROR") -> bool:
    ok = True
    for k, t in schema.items():
        if k not in data: record(level, name, f"缺少字段「{k}」"); ok = False
        elif not isinstance(data[k], t): record(level, name, f"「{k}」类型错误"); ok = False
    return ok

# ── Schema 定义 ───────────────────────────────────────────────

CONFIG_REQUIRED      = {"job_search": dict}
JOB_SEARCH_REQUIRED  = {"keyword_groups": list, "location": str,
                         "date_range_days": int, "max_jobs_per_keyword": int,
                         "max_display": int, "score_threshold_warn": int}
GROUP_REQUIRED       = {"group_id": str, "group_label": str, "cv_file": str,
                         "primary_keywords": dict, "job_family": dict}
CV_PARSED_REQUIRED   = {"name": str, "email": str, "skills": list, "experience": list}
HISTORY_REQUIRED     = {"batches": list, "seen_jobs": dict}
PROGRESS_REQUIRED    = {"last_updated": str, "session_count": int,
                         "cv_parse_status": dict, "search_summary": dict,
                         "job_pipeline": dict}

# ── 检查函数 ──────────────────────────────────────────────────

def check_users_json(verbose: bool):
    name, path = "users.json", Path("users.json")
    data = _load_json(path, name, "文件不存在（多用户模式不可用）")
    if data is None:
        return
    if "users" not in data or not isinstance(data["users"], list):
        record("ERROR", name, "缺少 'users' 数组"); return
    for u in data["users"]:
        if "id" not in u:
            record("ERROR", name, f"用户条目缺少 'id' 字段: {u}")
    if verbose:
        ids = [u.get("id", "?") for u in data["users"]]
        record("PASS", name, f"{len(ids)} 个用户：{', '.join(ids)}")


def check_config(config_path: Path, verbose: bool) -> dict | None:
    name = "config.json"
    if not config_path.exists():
        record("ERROR", name, f"文件不存在：{config_path}"); return None
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        record("ERROR", name, f"JSON 解析失败：{e}"); return None

    for k, t in CONFIG_REQUIRED.items():
        if k not in cfg: record("ERROR", name, f"缺少字段：「{k}」"); return None
        if not isinstance(cfg[k], t): record("ERROR", name, f"「{k}」类型错误"); return None

    js = cfg["job_search"]
    for k, t in JOB_SEARCH_REQUIRED.items():
        if k not in js: record("ERROR", name, f"job_search 缺少：「{k}」")
        elif not isinstance(js[k], t): record("ERROR", name, f"job_search.{k} 类型错误")

    groups = js.get("keyword_groups", [])
    if not groups: record("ERROR", name, "keyword_groups 为空"); return None
    for i, g in enumerate(groups):
        pfx = f"keyword_groups[{i}]"
        for k, t in GROUP_REQUIRED.items():
            if k not in g: record("ERROR", name, f"{pfx} 缺少：「{k}」")
            elif not isinstance(g[k], t): record("ERROR", name, f"{pfx}.{k} 类型错误")
        for kf in ("primary_keywords", "job_family"):
            kw = g.get(kf, {})
            if not kw.get("en") and not kw.get("de"):
                record("WARN", name, f"{pfx}.{kf} 中 en/de 均为空")

    for key in ("cv_language", "your_name", "your_email"):
        if key not in cfg: record("WARN", name, f"建议填写字段「{key}」")
        elif cfg[key] in ("Your Name", "your@email.com", ""):
            record("WARN", name, f"「{key}」仍是占位符，请替换")

    if verbose: record("PASS", name, f"格式验证通过，{len(groups)} 个 group")
    return cfg


def check_cv_files(cfg: dict, user_dir: Path, verbose: bool):
    for g in cfg["job_search"].get("keyword_groups", []):
        gid, cv = g.get("group_id","?"), g.get("cv_file","")
        name = f"cv_file [{gid}]"
        if not cv: record("ERROR", name, "cv_file 字段为空"); continue
        p = user_dir / cv
        if not p.exists(): record("ERROR", name, f"文件不存在：{p}"); continue
        if not cv.startswith("my_cv"): record("WARN", name, f"CV 不在 my_cv/ 目录：{cv}")
        size = p.stat().st_size
        if size == 0: record("ERROR", name, f"文件为空：{cv}")
        elif size < 1024: record("WARN", name, f"文件过小（{size}B），可能不是有效 PDF")
        else:
            try:
                with open(p,"rb") as f:
                    if f.read(4) != b"%PDF": record("WARN", name, "文件头不是 PDF 格式")
                    elif verbose: record("PASS", name, f"{cv}（{size//1024}KB）")
            except OSError as e: record("ERROR", name, f"无法读取：{e}")


def check_cv_parsed_cache(cfg: dict, user_dir: Path, verbose: bool):
    for g in cfg["job_search"].get("keyword_groups", []):
        gid  = g.get("group_id","?")
        path = user_dir / "output" / f"cv_parsed_{gid}.json"
        name = f"cv_parsed [{gid}]"
        data = _load_json(path, name, absent_msg="缓存不存在（Phase 1 会生成）" if verbose else "")
        if data is None:
            continue
        if not _check_schema(data, CV_PARSED_REQUIRED, name):
            record("ERROR", name, f"schema 不合法 — 请删除 {path} 后重新运行 Phase 1"); continue
        if not data.get("skills"): record("WARN", name, "skills 为空，预评分默认 50 分")
        if data.get("experience") and "company" not in data["experience"][0]:
            record("WARN", name, "experience[0] 缺少 company 字段")
        if verbose:
            record("PASS", name,
                f"schema 通过（{len(data.get('skills',[]))} 技能，"
                f"{len(data.get('experience',[]))} 段经历）")


def check_search_history(user_dir: Path, verbose: bool):
    name = "search_history.json"
    path = user_dir / "output" / "search_history.json"
    data = _load_json(path, name, absent_msg="不存在（Phase 2 会创建）" if verbose else "")
    if data is None:
        return
    _check_schema(data, HISTORY_REQUIRED, name)
    incomplete = [b["batch_id"] for b in data.get("batches",[]) if not b.get("dedup_done", True)]
    if incomplete:
        record("WARN", name, f"{len(incomplete)} 个批次去重未完成：{', '.join(incomplete)}")
    for b in data.get("batches",[])[-3:]:
        rf = b.get("raw_results_file")
        if rf:
            rf_path = Path(rf)
            bid = b.get("batch_id", "")
            alt_path = user_dir / "output" / "temp" / f"raw_results_{bid}.json"
            if not rf_path.exists() and not alt_path.exists():
                record("WARN", name, f"批次 {bid} 的原始文件已删除：{rf}（不影响功能）")
    if verbose:
        record("PASS", name,
            f"可读（{len(data.get('batches',[]))} 批次，"
            f"{len(data.get('seen_jobs',{}))} 条记录）")


def check_progress_files(verbose: bool):
    # progress.json
    pj, name_pj = Path("memory/progress.json"), "memory/progress.json"
    data = _load_json(pj, name_pj, absent_msg="不存在（首次 session 结束后自动生成）" if verbose else "")
    if data is not None:
        for k, t in PROGRESS_REQUIRED.items():
            if k not in data: record("WARN", name_pj, f"缺少字段「{k}」（可能旧格式）")
            elif not isinstance(data[k], t): record("WARN", name_pj, f"「{k}」类型错误")
        pending = data.get("job_pipeline",{}).get("pending",[])
        if pending:
            record("WARN", name_pj, f"{len(pending)} 个职缺上次未完成，可用 /generate-cv 继续")
        elif verbose:
            total = len(data.get("job_pipeline",{}).get("generated_pdf",[]))
            record("PASS", name_pj, f"schema 通过（已生成 {total} 份 PDF）")

    # notes.md
    nm, name_nm = Path("memory/notes.md"), "memory/notes.md"
    if not nm.exists():
        if verbose: record("INFO", name_nm, "不存在（首次 session 结束后自动生成）")
    else:
        try:
            c = nm.read_text(encoding="utf-8")
            if not c: record("WARN", name_nm, "文件为空")
            elif verbose: record("PASS", name_nm, f"可读（{c.count(chr(10))} 行）")
        except OSError as e: record("ERROR", name_nm, f"无法读取：{e}")


def check_theme_factory(verbose: bool):
    """检查 theme-factory skill 是否已安装。"""
    name = "theme-factory"
    skill_dir  = Path(".claude/skills/theme-factory")
    skill_file = skill_dir / "SKILL.md"

    if not skill_dir.exists():
        record("WARN", name,
            "未安装 theme-factory skill（PDF 主题选择功能不可用）\n"
            "         安装命令：\n"
            "         mkdir -p .claude/skills/theme-factory && "
            "curl -L -o skill.zip 'https://mcp.directory/api/skills/download/54' && "
            "unzip -o skill.zip -d .claude/skills/theme-factory && rm skill.zip")
        return

    if not skill_file.exists():
        record("WARN", name,
            f"目录存在但缺少 SKILL.md，安装可能不完整：{skill_dir}")
        return

    # 检查 theme-showcase.pdf
    showcases = list(skill_dir.rglob("theme-showcase.pdf"))
    if not showcases:
        record("WARN", name,
            "SKILL.md 存在但未找到 theme-showcase.pdf，"
            "用户将无法预览主题外观（不影响生成功能）")
    else:
        if verbose:
            record("PASS", name,
                f"已安装（SKILL.md + theme-showcase.pdf 均存在）")


def _mcp_handshake_ok(timeout: float = 25) -> bool:
    """
    Launch uvx linkedin-scraper-mcp and verify it responds to MCP initialize.

    Uses make_mcp_proc() (queue-based stdout reader, stderr=DEVNULL) and
    send_recv() (deadline-bounded) from common.py.  No blocking readline(),
    no stderr pipe that can fill up and deadlock the MCP process.
    """
    init_msg = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "check", "version": "1.0"},
        },
    }
    try:
        proc = make_mcp_proc()
    except (FileNotFoundError, OSError):
        return False

    try:
        resp = send_recv(proc, init_msg, timeout=timeout)
        return bool(resp and "result" in resp)
    except Exception:
        return False
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


def _warmup_uvx():
    """
    Spawn uvx linkedin-scraper-mcp briefly to trigger package download/cache,
    then kill it. Blocking for up to 30 s — acceptable for a one-time warm-up.
    """
    try:
        proc = subprocess.Popen(
            [UVX, "linkedin-scraper-mcp"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait up to 30 s; the goal is just to let uvx pull/cache the package.
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass


def check_linkedin_mcp(verbose: bool) -> bool:
    """
    Verify that uvx linkedin-scraper-mcp is reachable via MCP initialize.
    On first failure, triggers a uvx warm-up and retries once.
    Records PASS / ERROR into the shared `results` list.
    Returns True if the tool is ready, False otherwise.
    """
    name = "linkedin-mcp"

    # ── First attempt ─────────────────────────────────────────
    if _mcp_handshake_ok(timeout=25):
        if verbose:
            record("PASS", name, "linkedin-scraper-mcp 响应正常，可以开始 Phase 2")
        return True

    # ── Auto-reload ───────────────────────────────────────────
    print(f"{INFO}  [linkedin-mcp]  工具未响应，正在自动加载（首次使用可能需要下载，请稍候…）")
    sys.stdout.flush()
    _warmup_uvx()

    # ── Retry ─────────────────────────────────────────────────
    if _mcp_handshake_ok(timeout=30):
        record("PASS", name, "自动加载成功，linkedin-scraper-mcp 响应正常")
        return True

    record("ERROR", name,
           "linkedin-scraper-mcp 无法启动，Phase 2 搜索无法执行。\n"
           "         可能原因：① uvx 未安装（pip install uv）"
           "  ② 网络问题  ③ 包名变更\n"
           "         请手动运行以下命令确认：\n"
           f"           {UVX} linkedin-scraper-mcp")
    return False


def check_stepstone_server(cfg: dict, verbose: bool, strict: bool = False) -> bool:
    """
    HTTP GET to Stepstone MCP server to verify it is running.
    Uses stepstone.server_url from config; short-circuits if stepstone.enabled=false.

    strict=True  → unreachable server records ERROR (used in --phase2)
    strict=False → unreachable server records WARN only (used in baseline check)
    """
    name = "stepstone-mcp"
    stepstone_cfg = cfg.get("stepstone", {})

    if not stepstone_cfg.get("enabled", False):
        if verbose:
            record("INFO", name, "Stepstone disabled in config (stepstone.enabled=false), skipping")
        return True

    server_url = stepstone_cfg.get("server_url", "http://127.0.0.1:8000/mcp")
    # Probe the base URL (strip /mcp suffix for root health check)
    base_url = server_url.rsplit("/mcp", 1)[0] + "/"
    fail_level = "ERROR" if strict else "WARN"

    prereq = (
        "前置操作（每次 Phase 2 搜索前，保持终端开启）：\n"
        "           cd C:\\tools\\mcp-stepstone && python -m stepstone_http_server\n"
        "           # 监听 http://127.0.0.1:8000/mcp"
    )

    try:
        req = urllib.request.Request(base_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status < 500:
                if verbose:
                    record("PASS", name, f"Stepstone MCP server reachable at {base_url}")
                return True
            record(fail_level, name,
                   f"Stepstone server returned HTTP {resp.status}.\n         {prereq}")
            return False
    except urllib.error.URLError as e:
        record(fail_level, name,
               f"Stepstone MCP server not reachable at {base_url}: {e}\n"
               f"         {prereq}")
        return False
    except Exception as e:
        record(fail_level, name,
               f"Unexpected error checking Stepstone server: {e}\n         {prereq}")
        return False


def check_output_dir(user_dir: Path, verbose: bool):
    p = user_dir / "output"
    name = "output/"
    if not p.exists():
        try: p.mkdir(parents=True); record("WARN", name, "目录不存在，已自动创建")
        except OSError as e: record("ERROR", name, f"无法创建：{e}"); return
    if not p.is_dir(): record("ERROR", name, "output 路径不是目录"); return
    if not os.access(p, os.W_OK):
        record("ERROR", name, "不可写：权限拒绝")
    elif verbose:
        record("PASS", name, "存在且可写")


# ── 主函数 ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LinkedIn CV Agent — baseline sanity check")
    parser.add_argument("--uid",     default="leon", help="用户 ID（对应 users/{uid}/ 目录）")
    parser.add_argument("--config",  default=None,   help="覆盖 config.json 路径（默认 users/{uid}/config.json）")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--phase2",  action="store_true",
                        help="额外检查 LinkedIn MCP 可用性（Phase 2 搜索前必须通过）")
    args = parser.parse_args()

    user_dir    = Path("users") / args.uid
    config_path = Path(args.config) if args.config else user_dir / "config.json"

    t0 = time.monotonic()
    label = "Phase 2 Pre-flight Check" if args.phase2 else "Baseline Sanity Check"
    print(f"\n┌─────────────────────────────────────────┐")
    print(f"│   {label:<38}│")
    print(f"└─────────────────────────────────────────┘\n")

    check_users_json(args.verbose)
    cfg = check_config(config_path, args.verbose)
    if cfg:
        check_cv_files(cfg, user_dir, args.verbose)
        check_cv_parsed_cache(cfg, user_dir, args.verbose)
    check_search_history(user_dir, args.verbose)
    check_progress_files(args.verbose)
    check_theme_factory(args.verbose)
    check_output_dir(user_dir, args.verbose)

    # Phase 2 pre-flight: verify LinkedIn MCP + Stepstone server (strict → ERROR on failure)
    # Baseline (no --phase2): Stepstone check is WARN-only
    if args.phase2:
        check_linkedin_mcp(args.verbose)
        if cfg:
            check_stepstone_server(cfg, args.verbose, strict=True)
    else:
        if cfg:
            check_stepstone_server(cfg, args.verbose, strict=False)

    elapsed = time.monotonic() - t0
    errors   = [r for r in results if r[0] == "ERROR"]
    warnings = [r for r in results if r[0] == "WARN"]
    passes   = [r for r in results if r[0] == "PASS"]
    infos    = [r for r in results if r[0] == "INFO"]

    if args.verbose or errors or warnings:
        for level, name, msg in results:
            icon = {"PASS": PASS, "WARN": WARN, "ERROR": ERROR, "INFO": INFO}[level]
            print(f"{icon}  [{name}]  {msg}")
        print()

    parts = []
    if passes:   parts.append(f"\033[32m{len(passes)} passed\033[0m")
    if warnings: parts.append(f"\033[33m{len(warnings)} warnings\033[0m")
    if errors:   parts.append(f"\033[31m{len(errors)} errors\033[0m")
    if infos and args.verbose: parts.append(f"{len(infos)} info")
    print(f"  结果：{' · '.join(parts)}  ({elapsed*1000:.0f} ms)\n")

    if errors:
        print("  需要修复：")
        for _, name, msg in errors: print(f"    ✗  [{name}]  {msg}")
        print("\n  修复以上问题后重新运行。\n"); sys.exit(1)
    if warnings and not errors:
        print("  存在警告，不影响运行。建议在方便时修复。\n")
    if not errors and not warnings:
        print("  \033[32m所有检查通过，可以开始。\033[0m\n")
    sys.exit(0)


if __name__ == "__main__":
    main()