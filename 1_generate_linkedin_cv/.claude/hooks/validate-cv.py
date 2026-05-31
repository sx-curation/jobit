#!/usr/bin/env python3
"""
.claude/hooks/validate-cv.py

PostToolUse hook：每次 Write 工具调用后触发。
仅对 cv_draft.md 执行捏造检测，跳过所有其他文件写入。

退出码：
  0 — 通过或不适用（不阻断）
  2 — 检测到高危问题（阻断，错误信息回传给 Claude）
"""
import json
import re
import sys
from pathlib import Path


# 不需要验证的文件名（cv-evaluator、cover-letter 等的输出）
SKIP_SUFFIXES = (
    "eval_report.json",
    "cover_letter_draft.md",
    "jd_analysis.json",
    "cv_changes.md",
    "progress.md",
    "search_history.json",
    "cv_parsed_group",   # cv_parsed_group-*.json
)


def load_json(path: str) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def should_skip(file_path: str) -> bool:
    """判断是否跳过此文件的验证。"""
    name = Path(file_path).name
    return any(name.endswith(s) or name.startswith(s) for s in SKIP_SUFFIXES)


def main():
    hook_input = json.loads(sys.stdin.read())
    written_file = hook_input.get("tool_input", {}).get("path", "")

    # 只处理 cv_draft.md 和 cv_tailored.md
    CV_FILES_TO_VALIDATE = ("cv_draft.md", "cv_tailored.md")
    if not any(written_file.endswith(f) for f in CV_FILES_TO_VALIDATE):
        sys.exit(0)

    if should_skip(written_file):
        sys.exit(0)

    # 加载原始 CV（寻找对应 group 的 cv_parsed）
    # 路径格式：output/<group_id>_<company>_<title>/cv_draft.md
    # 对应的 cv_parsed：output/cv_parsed_<group_id>.json
    cv_original = None
    try:
        folder = Path(written_file).parent.name          # e.g. group-da_Siemens_MarketingDA
        group_id = folder.split("_")[0]                  # e.g. group-da
        # Whitelist validation to prevent path traversal
        if not re.match(r'^group-[a-z0-9\-]+$', group_id):
            sys.exit(0)
        cv_parsed_path = f"output/cv_parsed_{group_id}.json"
        cv_original = load_json(cv_parsed_path)
    except Exception:
        pass

    # cv_parsed 不存在时降级：只做基本检查
    if not cv_original:
        # 尝试旧路径作为降级
        cv_original = load_json("output/cv_parsed.json")

    if not cv_original:
        # 无法加载原始 CV，跳过（不阻断）
        print("validate-cv: cv_parsed 不可用，跳过验证", file=sys.stderr)
        sys.exit(0)

    draft_text = Path(written_file).read_text(encoding="utf-8")

    original_companies = {
        e.get("company", "").lower()
        for e in cv_original.get("experience", [])
        if e.get("company")
    }
    original_skills = {s.lower() for s in cv_original.get("skills", [])}

    # ── 检查 1：疑似新增公司名 ────────────────────────────────
    # 匹配大写开头的连续词组（排除常见非公司词汇）
    SKIP_WORDS = {
        # English section headers & common words
        "summary", "experience", "education", "skills", "languages",
        "certifications", "references", "january", "february", "march",
        "april", "may", "june", "july", "august", "september",
        "october", "november", "december", "monday", "tuesday",
        "wednesday", "thursday", "friday", "saturday", "sunday",
        "bachelor", "master", "doctor", "university", "college",
        "present", "current", "remote", "germany", "berlin", "munich",
        "hamburg", "frankfurt", "english", "german", "french",
        # German section headers (Lebenslauf targeting German market)
        "berufserfahrung", "kenntnisse", "ausbildung", "sprachen",
        "zertifizierungen", "lebenslauf", "profil", "kompetenzen",
        "weiterbildung", "projektmanagement", "qualifikationen",
    }

    draft_entities = set(re.findall(r'\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*\b', draft_text))
    violations = []

    for entity in draft_entities:
        if len(entity) <= 3:
            continue
        if entity.lower() in SKIP_WORDS:
            continue
        if entity.lower() in original_companies:
            continue
        # 检查是否是原始公司名的子字符串（如「Deutsche」是「Deutsche Bahn」的一部分）
        is_substring = any(entity.lower() in co for co in original_companies)
        if is_substring:
            continue
        # 超过 2 个词的实体且不在原始数据中，才标记
        if len(entity.split()) >= 2:
            violations.append(f"疑似新增公司/组织名：「{entity}」（原始 CV 中未找到）")

    # ── 检查 2：技能列表新增项 ────────────────────────────────
    # 提取 cv_draft 中 Skills 区块的内容（简单启发式）
    skills_section = ""
    in_skills = False
    for line in draft_text.splitlines():
        if re.match(r"^#{1,3}\s*(skills|技能)", line, re.IGNORECASE):
            in_skills = True
            continue
        if in_skills and re.match(r"^#{1,3}\s+", line):
            in_skills = False
        if in_skills:
            skills_section += line + " "

    if skills_section and original_skills:
        # 从 skills 区块提取词汇
        draft_skill_words = {
            w.lower().strip("·,;-")
            for w in re.split(r"[\s,|·•]+", skills_section)
            if len(w) > 2
        }
        for word in draft_skill_words:
            # 如果这个词不在原始技能中，且不是通用词，标记
            generic = {"and", "or", "the", "with", "for", "years", "experience",
                       "strong", "good", "excellent", "proficient", "knowledge"}
            if word not in original_skills and word not in generic and len(word) > 4:
                # 检查是否是原始技能的子字符串
                is_sub = any(word in s for s in original_skills)
                if not is_sub:
                    violations.append(
                        f"Skills 区块疑似新增词汇：「{word}」（原始 CV 技能列表中未找到）"
                    )

    # ── 结果处理 ──────────────────────────────────────────────
    if violations:
        # 超过 3 条才阻断，避免误判过多导致工作流卡死
        if len(violations) >= 3:
            print("CV 验证发现多处疑似问题，已阻断：", file=sys.stderr)
            for v in violations:
                print(f"  - {v}", file=sys.stderr)
            print("请检查 cv_draft.md 是否只包含原始 CV 中已有的内容。", file=sys.stderr)
            sys.exit(2)
        else:
            # 少量疑似问题：警告但不阻断（cv-evaluator 会做更精确的语义检查）
            print(f"validate-cv: {len(violations)} 处疑似问题（已记录，不阻断）：")
            for v in violations:
                print(f"  ⚠ {v}")
            sys.exit(0)
    else:
        print(f"validate-cv: 通过 — {Path(written_file).name}")
        sys.exit(0)


if __name__ == "__main__":
    main()