#!/usr/bin/env python3
"""
scripts/generate_pdf.py — Markdown → PDF（支持 theme-factory 主题）

用法：
  # 使用默认主题
  python3 scripts/generate_pdf.py input.md output.pdf

  # 使用指定主题（主题名来自 theme-factory SKILL.md 中定义的主题列表）
  python3 scripts/generate_pdf.py input.md output.pdf --theme "Corporate Blue"

  # 查看所有可用主题名称
  python3 scripts/generate_pdf.py --list-themes
"""

import argparse
import json
import re
import sys
from pathlib import Path

import markdown

# weasyprint 按需导入（部分环境可能未安装）
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_OK = True
except ImportError:
    WEASYPRINT_OK = False

# ── theme-factory 路径 ────────────────────────────────────────

THEME_DIR = Path(".claude/skills/theme-factory")

# ── 内建主题定义（theme-factory 未安装时的降级方案） ──────────

BUILTIN_THEMES: dict[str, dict] = {
    "default": {
        "font_family": "'Arial Unicode MS', 'Noto Sans CJK SC', Arial, Helvetica, sans-serif",
        "font_size":   "11pt",
        "color_primary":   "#2c3e50",
        "color_heading":   "#34495e",
        "color_accent":    "#2980b9",
        "color_text":      "#333333",
        "color_bg":        "#ffffff",
        "line_height":     "1.6",
    },
    "minimal": {
        "font_family": "'Arial Unicode MS', Georgia, 'Noto Serif CJK SC', serif",
        "font_size":   "11pt",
        "color_primary":   "#1a1a1a",
        "color_heading":   "#1a1a1a",
        "color_accent":    "#555555",
        "color_text":      "#1a1a1a",
        "color_bg":        "#ffffff",
        "line_height":     "1.7",
    },
    "modern": {
        "font_family": "'Arial Unicode MS', 'Trebuchet MS', 'Noto Sans CJK SC', sans-serif",
        "font_size":   "10.5pt",
        "color_primary":   "#0d3349",
        "color_heading":   "#0d3349",
        "color_accent":    "#e74c3c",
        "color_text":      "#2d2d2d",
        "color_bg":        "#ffffff",
        "line_height":     "1.6",
    },
}


# ── theme-factory 主题加载 ─────────────────────────────────────

def load_theme_factory_themes() -> dict[str, dict]:
    """
    尝试从 theme-factory skill 加载主题定义。
    theme-factory 在 SKILL.md 中描述主题名称和样式参数。
    如果存在 themes.json，直接读取；否则只返回空 dict。
    """
    if not THEME_DIR.exists():
        return {}

    # 优先读取 themes.json（如果 skill 提供了机器可读的主题列表）
    themes_json = THEME_DIR / "themes.json"
    if themes_json.exists():
        try:
            return json.loads(themes_json.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 降级：扫描 theme-factory 目录下的 CSS 文件，每个 CSS 对应一个主题
    themes = {}
    for css_file in THEME_DIR.rglob("*.css"):
        theme_name = css_file.stem.replace("-", " ").replace("_", " ").title()
        themes[theme_name] = {"css_file": str(css_file)}

    return themes


def get_all_themes() -> dict[str, dict]:
    """合并 theme-factory 主题和内建主题（theme-factory 优先）。"""
    all_themes = {**BUILTIN_THEMES}
    tf_themes  = load_theme_factory_themes()
    all_themes.update(tf_themes)
    return all_themes


def resolve_theme(theme_name: str) -> tuple[str | None, dict | None]:
    """
    解析主题名称，返回 (css_string, theme_dict)。
    优先级：theme-factory CSS 文件 > theme-factory themes.json > 内建主题。
    """
    all_themes = get_all_themes()

    # 大小写不敏感匹配
    matched_key = None
    for k in all_themes:
        if k.lower() == theme_name.lower():
            matched_key = k
            break

    if matched_key is None:
        return None, None

    theme = all_themes[matched_key]

    # 如果主题有 css_file 字段，直接读取 CSS 文件
    if "css_file" in theme:
        css_path = Path(theme["css_file"])
        if css_path.exists():
            return css_path.read_text(encoding="utf-8"), theme
        return None, theme

    # 否则用内建主题参数生成 CSS
    css = build_css_from_theme(theme)
    return css, theme


def build_css_from_theme(t: dict) -> str:
    """从主题参数字典生成 CSS 字符串。"""
    return f"""
    @page {{
        margin: 25mm 20mm 25mm 20mm;
        @bottom-center {{
            content: counter(page) " / " counter(pages);
            font-size: 9pt;
            color: {t.get('color_accent', '#888')};
        }}
    }}
    body {{
        font-family: {t.get('font_family', 'Arial, sans-serif')};
        font-size: {t.get('font_size', '11pt')};
        color: {t.get('color_text', '#333')};
        background: {t.get('color_bg', '#fff')};
        line-height: {t.get('line_height', '1.6')};
    }}
    h1 {{
        font-size: 18pt;
        color: {t.get('color_primary', '#2c3e50')};
        border-bottom: 2px solid {t.get('color_accent', '#2980b9')};
        padding-bottom: 4pt;
        margin-bottom: 12pt;
    }}
    h2 {{
        font-size: 13pt;
        color: {t.get('color_heading', '#34495e')};
        border-bottom: 1px solid #e0e0e0;
        padding-bottom: 2pt;
        margin-top: 14pt;
        margin-bottom: 6pt;
    }}
    h3 {{
        font-size: 11pt;
        color: {t.get('color_heading', '#34495e')};
        margin-top: 10pt;
        margin-bottom: 4pt;
    }}
    ul, ol {{
        margin: 4pt 0 8pt 0;
        padding-left: 18pt;
    }}
    li {{
        margin-bottom: 2pt;
    }}
    strong {{
        color: {t.get('color_primary', '#2c3e50')};
    }}
    a {{
        color: {t.get('color_accent', '#2980b9')};
        text-decoration: none;
    }}
    p {{
        margin: 4pt 0 8pt 0;
    }}
    hr {{
        border: none;
        border-top: 1px solid #e0e0e0;
        margin: 10pt 0;
    }}
    """


# ── ATS 兼容模式 ──────────────────────────────────────────────

def get_ats_css() -> str:
    """返回 ATS 兼容的最小化 CSS。无外部字体、无装饰。"""
    return """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: Arial, Helvetica, 'Liberation Sans', sans-serif;
        font-size: 11pt;
        line-height: 1.4;
        color: #000000;
        background: #ffffff;
        margin: 25mm;
        max-width: none;
    }
    h1 { font-size: 16pt; font-weight: bold; margin-bottom: 6pt; }
    h2 { font-size: 13pt; font-weight: bold;
         border-bottom: 1pt solid #000000;
         padding-bottom: 2pt; margin-top: 14pt; margin-bottom: 6pt;
         text-transform: uppercase; }
    h3 { font-size: 11pt; font-weight: bold; margin-top: 8pt; margin-bottom: 2pt; }
    p, li { font-size: 11pt; margin-bottom: 3pt; }
    ul { padding-left: 15pt; }
    strong { font-weight: bold; }
    a { color: #000000; text-decoration: none; }
    hr { border: none; border-top: 1pt solid #000000; margin: 8pt 0; }
    """


def prepare_ats_html(cv_html: str) -> str:
    """将 CV HTML 转换为 ATS 兼容格式：标准化 section 标题，移除 script 标签。"""
    import re as _re
    header_map = {
        r'berufserfahrung|work history|experience|erfahrung': 'Work Experience',
        r'ausbildung|bildung|education': 'Education',
        r'kenntnisse|fähigkeiten|skills|kompetenzen': 'Skills',
        r'kontakt|contact': 'Contact',
        r'zusammenfassung|profil|summary|profile': 'Summary',
        r'sprachen|languages': 'Languages',
    }
    for pattern, replacement in header_map.items():
        cv_html = _re.sub(
            rf'(<h[12][^>]*>)([^<]*(?:{pattern})[^<]*)(</h[12]>)',
            rf'\g<1>{replacement}\g<3>',
            cv_html, flags=_re.IGNORECASE
        )
    # Remove script tags (WeasyPrint ignores them but keep output clean)
    cv_html = _re.sub(r'<script[^>]*>.*?</script>', '', cv_html, flags=_re.DOTALL)
    return cv_html


# ── HTML 净化 ─────────────────────────────────────────────────

def _sanitize_html(html: str) -> str:
    """Strip <script>/<style> tags and on* event attributes to prevent injection."""
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'(\s)on\w+\s*=\s*"[^"]*"',  r'\1', html, flags=re.IGNORECASE)
    html = re.sub(r"(\s)on\w+\s*=\s*'[^']*'",  r'\1', html, flags=re.IGNORECASE)
    return html


# ── PDF 生成 ──────────────────────────────────────────────────

def generate_pdf(md_path: str, pdf_path: str, theme_name: str = "default",
                 css_string: str | None = None, ats_mode: bool = False):
    """Generate PDF from Markdown.

    Args:
        md_path:    Input Markdown file path.
        pdf_path:   Output PDF file path.
        theme_name: Theme name (ignored when css_string is provided).
        css_string: Raw CSS string bypass. When provided, skips theme resolution.
        ats_mode:   When True, apply prepare_ats_html() to normalize section headings.
    """
    if not WEASYPRINT_OK:
        print("ERROR: weasyprint 未安装。请运行：pip3 install weasyprint --break-system-packages",
              file=sys.stderr)
        sys.exit(1)

    md_content = Path(md_path).read_text(encoding="utf-8")

    # Markdown → HTML (sanitized to remove any injected script/style tags)
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "nl2br"]
    )
    html_body = _sanitize_html(html_body)
    if ats_mode:
        html_body = prepare_ats_html(html_body)

    # 解析 CSS
    theme_dict = None
    if css_string is None:
        css_string, theme_dict = resolve_theme(theme_name)
        if css_string is None:
            print(f"WARNING: 主题「{theme_name}」不存在，使用默认主题", file=sys.stderr)
            css_string, _ = resolve_theme("default")

    # 组装完整 HTML
    full_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>CV</title>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

    # 生成 PDF
    Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)
    HTML(string=full_html).write_pdf(
        pdf_path,
        stylesheets=[CSS(string=css_string)]
    )

    theme_label = theme_dict.get("label", theme_name) if theme_dict else theme_name
    print(f"PDF 已生成：{pdf_path}（主题：{theme_label}）")


def list_themes():
    """列出所有可用主题。"""
    all_themes = get_all_themes()
    tf_themes  = load_theme_factory_themes()

    print("\n可用主题：\n")

    if tf_themes:
        print("  [theme-factory]")
        for name in tf_themes:
            src = "CSS" if "css_file" in tf_themes[name] else "JSON"
            print(f"    {name}  ({src})")
        print()

    print("  [内建主题]")
    for name in BUILTIN_THEMES:
        print(f"    {name}")

    if not tf_themes:
        print()
        print("  提示：安装 theme-factory skill 可获得更多专业主题")
        print("  安装命令：")
        print("    mkdir -p .claude/skills/theme-factory && \\")
        print("    curl -L -o skill.zip 'https://mcp.directory/api/skills/download/54' && \\")
        print("    unzip -o skill.zip -d .claude/skills/theme-factory && rm skill.zip")
    print()


# ── 入口 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Markdown → PDF with theme support"
    )
    parser.add_argument("input",    nargs="?", help="输入 Markdown 文件路径")
    parser.add_argument("output",   nargs="?", help="输出 PDF 文件路径")
    parser.add_argument("--theme",  default="default",
                        help="主题名称（默认：default）")
    parser.add_argument("--list-themes", action="store_true",
                        help="列出所有可用主题并退出")
    parser.add_argument("--dual", action="store_true",
                        help="同时生成 ATS 版（输出路径）和视觉版（cv_styled.pdf）两份 PDF")
    args = parser.parse_args()

    if args.list_themes:
        list_themes()
        sys.exit(0)

    if not args.input or not args.output:
        parser.print_help()
        sys.exit(1)

    if args.dual:
        # ATS version → the specified output path (ATS CSS + section header normalization)
        generate_pdf(args.input, args.output, css_string=get_ats_css(), ats_mode=True)
        print("  ↑ ATS 机器可读版")
        # Styled version → cv_styled.pdf in same directory
        styled_path = str(Path(args.output).parent / "cv_styled.pdf")
        generate_pdf(args.input, styled_path, args.theme)
        print("  ↑ 视觉版")
    else:
        generate_pdf(args.input, args.output, args.theme)