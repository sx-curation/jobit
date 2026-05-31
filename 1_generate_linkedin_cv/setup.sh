#!/usr/bin/env bash
# =============================================================================
# setup.sh — LinkedIn CV Agent 环境初始化（macOS / Linux）
#
# Windows 用户请使用：.\setup.ps1
#
# 用法：
#   bash setup.sh          # 完整安装
#   bash setup.sh --check  # 只检查依赖，不安装
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }
info() { echo -e "${BLUE}→${NC} $1"; }

CHECK_ONLY=false
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=true

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo ""
    echo "  检测到 Windows 环境，请改用 PowerShell 脚本："
    echo "  PowerShell> .\\setup.ps1"
    echo ""
    exit 1
fi

OS="$(uname -s)"

echo ""
echo "══════════════════════════════════════════"
echo "  LinkedIn CV Agent — 环境初始化（$OS）"
echo "══════════════════════════════════════════"
echo ""

# ─────────────────────────────────────────────
# 1. 系统依赖检查
# ─────────────────────────────────────────────
info "检查系统依赖..."

# Python 3.11+
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [[ "$(echo "$PY_VER" | cut -d. -f1)" -ge 3 && "$PY_MINOR" -ge 11 ]]; then
        ok "Python $PY_VER"
    else
        if [[ "$OS" == "Darwin" ]]; then
            err "需要 Python 3.11+，当前：$PY_VER。请运行：brew install python@3.12"
        else
            err "需要 Python 3.11+，当前：$PY_VER。请运行：sudo apt install python3.12"
        fi
    fi
else
    [[ "$OS" == "Darwin" ]] && err "找不到 python3。请运行：brew install python@3.12" \
                             || err "找不到 python3。请运行：sudo apt install python3.12"
fi

# Node.js 18+
if command -v node &>/dev/null; then
    NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
    if [[ "$NODE_MAJOR" -ge 18 ]]; then
        ok "Node.js $(node --version)"
    else
        err "需要 Node.js 18+，当前：$(node --version)"
    fi
else
    [[ "$OS" == "Darwin" ]] && err "找不到 node。请运行：brew install node" \
                             || err "找不到 node。请运行：sudo apt install nodejs npm"
fi

# uv
if command -v uv &>/dev/null; then
    ok "uv $(uv --version 2>/dev/null | head -1)"
else
    if [[ "$CHECK_ONLY" == true ]]; then warn "uv 未安装"
    else
        info "安装 uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        ok "uv 已安装"
    fi
fi

# Claude Code CLI
if command -v claude &>/dev/null; then
    ok "Claude Code $(claude --version 2>/dev/null | head -1)"
else
    if [[ "$CHECK_ONLY" == true ]]; then warn "Claude Code CLI 未安装"
    else
        info "安装 Claude Code CLI..."
        npm install -g @anthropic-ai/claude-code
        ok "Claude Code 已安装"
    fi
fi

# unzip（theme-factory 安装需要）
if command -v unzip &>/dev/null; then
    ok "unzip $(unzip -v 2>/dev/null | head -1 | awk '{print $2}')"
else
    if [[ "$CHECK_ONLY" == true ]]; then warn "unzip 未安装（theme-factory 安装需要）"
    else
        info "安装 unzip..."
        if [[ "$OS" == "Darwin" ]]; then
            brew install unzip
        else
            sudo apt-get install -y unzip
        fi
        ok "unzip 已安装"
    fi
fi

[[ "$CHECK_ONLY" == true ]] && { echo ""; info "检查完成（--check 模式）"; echo ""; exit 0; }

# ─────────────────────────────────────────────
# 2. Python 依赖
# ─────────────────────────────────────────────
echo ""
info "安装 Python 依赖..."
pip3 install --break-system-packages -q pymupdf weasyprint markdown jinja2
ok "pymupdf / weasyprint / markdown / jinja2"

# ─────────────────────────────────────────────
# 3. LinkedIn MCP 浏览器
# ─────────────────────────────────────────────
echo ""
info "初始化 LinkedIn MCP 浏览器..."
if uvx patchright install chromium --quiet 2>/dev/null; then
    ok "Patchright Chromium"
else
    warn "Patchright 安装遇到问题，请手动运行：uvx patchright install chromium"
fi

# ─────────────────────────────────────────────
# 4. 创建目录结构
# ─────────────────────────────────────────────
echo ""
info "创建项目目录结构..."
mkdir -p my_cv output memory scripts \
    .claude/agents \
    .claude/skills/pdf-to-markdown \
    .claude/skills/jd-scoring \
    .claude/skills/cv-rewrite-rules \
    .claude/skills/cl-template \
    .claude/skills/eval-criteria \
    .claude/hooks
ok "目录结构已创建"

# ─────────────────────────────────────────────
# 5. theme-factory skill 安装
# ─────────────────────────────────────────────
echo ""
info "安装 theme-factory skill..."

THEME_DIR=".claude/skills/theme-factory"

if [[ -f "$THEME_DIR/SKILL.md" ]]; then
    ok "theme-factory 已安装（跳过）"
else
    if curl -fsSL --max-time 30 \
        -o /tmp/theme_skill.zip \
        "https://mcp.directory/api/skills/download/54" 2>/dev/null; then

        mkdir -p "$THEME_DIR"
        unzip -o -q /tmp/theme_skill.zip -d "$THEME_DIR"
        rm -f /tmp/theme_skill.zip

        if [[ -f "$THEME_DIR/SKILL.md" ]]; then
            ok "theme-factory 已安装"
            # 检查是否包含 theme-showcase.pdf
            if find "$THEME_DIR" -name "theme-showcase.pdf" | grep -q .; then
                ok "theme-showcase.pdf 已就绪"
            else
                warn "theme-showcase.pdf 未找到，主题预览功能可能不可用"
            fi
        else
            warn "theme-factory 安装后未找到 SKILL.md，请检查 $THEME_DIR 目录"
        fi
    else
        warn "无法连接 mcp.directory，theme-factory 安装失败"
        warn "请手动运行："
        warn "  mkdir -p $THEME_DIR && curl -L -o skill.zip 'https://mcp.directory/api/skills/download/54' && unzip -o skill.zip -d $THEME_DIR && rm skill.zip"
    fi
fi

# ─────────────────────────────────────────────
# 6. Hook 脚本权限
# ─────────────────────────────────────────────
echo ""
info "设置 hook 脚本权限..."
for f in ".claude/hooks/validate-cv.py" ".claude/hooks/notify.sh"; do
    if [[ -f "$f" ]]; then chmod +x "$f" && ok "$f"
    else warn "$f 不存在，跳过"; fi
done

# ─────────────────────────────────────────────
# 7. PATH 配置
# ─────────────────────────────────────────────
echo ""
info "检查 PATH..."
LOCAL_BIN="$HOME/.local/bin"
if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    RC="$HOME/.zshrc"; [[ "$SHELL" == */bash ]] && RC="$HOME/.bashrc"
    echo -e "\nexport PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$RC"
    warn "已将 ~/.local/bin 加入 $RC，请执行：source $RC"
else
    ok "PATH 已包含 ~/.local/bin"
fi

# ─────────────────────────────────────────────
# 后续步骤
# ─────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  后续步骤（需手动完成）"
echo "══════════════════════════════════════════"
echo ""
echo "  1. LinkedIn 登录（首次必须）："
echo "     uvx linkedin-scraper-mcp --login"
echo ""
echo "  2. 将 CV 放入 my_cv/ 目录："
echo "     my_cv/my_cv_da.pdf   ← Marketing Analytics CV"
echo "     my_cv/my_cv_pmo.pdf  ← PMO CV"
echo ""
echo "  3. 编辑 config.json：填写 your_name、your_email、location"
echo ""
echo "  4. VS Code 打开项目 → 点击 ⚡ Spark → 输入「开始」"
echo ""
echo "  完整文档：SPEC.md"
echo ""
ok "初始化完成"
echo ""