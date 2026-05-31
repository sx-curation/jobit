# =============================================================================
# setup.ps1 — LinkedIn CV Agent 环境初始化（Windows）
#
# 用法：
#   .\setup.ps1          # 完整安装
#   .\setup.ps1 -Check   # 只检查依赖，不安装
#
# 如遇执行策略限制：
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# =============================================================================

param([switch]$Check)

function Write-Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [!!] $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "  [XX] $msg" -ForegroundColor Red; exit 1 }
function Write-Info { param($msg) Write-Host "   ->  $msg" -ForegroundColor Cyan }

function Test-Version {
    param([string]$VersionStr, [int]$MajorMin, [int]$MinorMin)
    try {
        $parts = $VersionStr -replace '[^0-9.]','' -split '\.'
        $major = [int]$parts[0]; $minor = [int]$parts[1]
        return ($major -gt $MajorMin) -or ($major -eq $MajorMin -and $minor -ge $MinorMin)
    } catch { return $false }
}

Write-Host ""
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  LinkedIn CV Agent — 环境初始化（Windows）" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ─────────────────────────────────────────────
# 1. 系统依赖检查
# ─────────────────────────────────────────────
Write-Info "检查系统依赖..."

# Python 3.11+
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command python3 -ErrorAction SilentlyContinue }
if ($pyCmd) {
    $pyVer = & $pyCmd.Name -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if (Test-Version $pyVer 3 11) { Write-Ok "Python $pyVer" }
    else {
        if ($Check) { Write-Warn "Python 3.11+ 未满足（当前：$pyVer）" }
        else { Write-Err "需要 Python 3.11+，请从 https://python.org 下载安装" }
    }
} else {
    if ($Check) { Write-Warn "未找到 Python" }
    elseif (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "用 winget 安装 Python 3.12..."
        winget install -e --id Python.Python.3.12 --silent
        Write-Ok "Python 已安装（请重启 PowerShell）"
    } else { Write-Err "未找到 Python 且 winget 不可用，请从 https://python.org 手动安装" }
}

# Node.js 18+
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    $nodeVer = & node --version 2>$null
    $nodeMajor = [int]($nodeVer -replace 'v','').Split('.')[0]
    if ($nodeMajor -ge 18) { Write-Ok "Node.js $nodeVer" }
    else {
        if ($Check) { Write-Warn "Node.js 18+ 未满足" }
        else { Write-Err "需要 Node.js 18+，请从 https://nodejs.org 下载 LTS" }
    }
} else {
    if ($Check) { Write-Warn "未找到 Node.js" }
    elseif (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "用 winget 安装 Node.js LTS..."
        winget install -e --id OpenJS.NodeJS.LTS --silent
        Write-Ok "Node.js 已安装（请重启 PowerShell）"
    } else { Write-Err "未找到 Node.js，请从 https://nodejs.org 手动安装" }
}

# uv
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Ok "uv $(& uv --version 2>$null)"
} else {
    if ($Check) { Write-Warn "uv 未安装" }
    else {
        Write-Info "安装 uv..."
        powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","User") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","Machine")
        if (Get-Command uv -ErrorAction SilentlyContinue) { Write-Ok "uv 已安装" }
        else { Write-Warn "uv 安装完成，请重启 PowerShell 后继续" }
    }
}

# Claude Code CLI
if (Get-Command claude -ErrorAction SilentlyContinue) {
    Write-Ok "Claude Code $(& claude --version 2>$null | Select-Object -First 1)"
} else {
    if ($Check) { Write-Warn "Claude Code CLI 未安装" }
    else {
        Write-Info "安装 Claude Code CLI..."
        npm install -g @anthropic-ai/claude-code
        Write-Ok "Claude Code 已安装"
    }
}

if ($Check) {
    Write-Host ""; Write-Info "检查完成（-Check 模式）"; Write-Host ""; exit 0
}

# ─────────────────────────────────────────────
# 2. Python 依赖
# ─────────────────────────────────────────────
Write-Host ""
Write-Info "安装 Python 依赖..."
$pipCmd = if (Get-Command pip -ErrorAction SilentlyContinue) { "pip" } else { "pip3" }
& $pipCmd install -q pymupdf weasyprint markdown jinja2
Write-Ok "pymupdf / weasyprint / markdown / jinja2"

# ─────────────────────────────────────────────
# 3. LinkedIn MCP 浏览器
# ─────────────────────────────────────────────
Write-Host ""
Write-Info "初始化 LinkedIn MCP 浏览器..."
try {
    & uvx patchright install chromium 2>$null
    Write-Ok "Patchright Chromium"
} catch {
    Write-Warn "Patchright 安装遇到问题，请手动运行：uvx patchright install chromium"
}

# ─────────────────────────────────────────────
# 4. 创建目录结构
# ─────────────────────────────────────────────
Write-Host ""
Write-Info "创建项目目录结构..."
$dirs = @(
    "my_cv", "output", "memory", "scripts",
    ".claude\agents",
    ".claude\skills\pdf-to-markdown",
    ".claude\skills\jd-scoring",
    ".claude\skills\cv-rewrite-rules",
    ".claude\skills\cl-template",
    ".claude\skills\eval-criteria",
    ".claude\hooks"
)
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}
Write-Ok "目录结构已创建"

# ─────────────────────────────────────────────
# 5. theme-factory skill 安装
# ─────────────────────────────────────────────
Write-Host ""
Write-Info "安装 theme-factory skill..."

$ThemeDir = ".claude\skills\theme-factory"
$ThemeSkill = "$ThemeDir\SKILL.md"

if (Test-Path $ThemeSkill) {
    Write-Ok "theme-factory 已安装（跳过）"
} else {
    try {
        New-Item -ItemType Directory -Path $ThemeDir -Force | Out-Null
        $TmpZip = "$env:TEMP\theme_skill.zip"

        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile("https://mcp.directory/api/skills/download/54", $TmpZip)

        Expand-Archive -Path $TmpZip -DestinationPath $ThemeDir -Force
        Remove-Item $TmpZip -Force

        if (Test-Path $ThemeSkill) {
            Write-Ok "theme-factory 已安装"
            $showcase = Get-ChildItem -Path $ThemeDir -Filter "theme-showcase.pdf" -Recurse
            if ($showcase) { Write-Ok "theme-showcase.pdf 已就绪" }
            else { Write-Warn "theme-showcase.pdf 未找到，主题预览功能可能不可用" }
        } else {
            Write-Warn "theme-factory 安装后未找到 SKILL.md，请检查 $ThemeDir"
        }
    } catch {
        Write-Warn "无法连接 mcp.directory，theme-factory 安装失败"
        Write-Warn "请手动运行："
        Write-Warn "  mkdir -p $ThemeDir"
        Write-Warn "  curl -L -o skill.zip 'https://mcp.directory/api/skills/download/54'"
        Write-Warn "  Expand-Archive skill.zip -DestinationPath $ThemeDir"
    }
}

# ─────────────────────────────────────────────
# 6. Hook 文件检查
# ─────────────────────────────────────────────
Write-Host ""
Write-Info "检查 hook 文件..."
foreach ($f in @(".claude\hooks\validate-cv.py", ".claude\hooks\notify.sh")) {
    if (Test-Path $f) { Write-Ok "$f" }
    else { Write-Warn "$f 不存在，请确认已创建此文件" }
}
Write-Warn "notify.sh 在 Windows 上需要 Git Bash 或 WSL（不影响核心功能）"

# ─────────────────────────────────────────────
# 7. PATH 配置
# ─────────────────────────────────────────────
Write-Host ""
Write-Info "检查 PATH..."
$userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
$localBin = "$env:APPDATA\Python\Scripts"
if ($userPath -notlike "*$localBin*") {
    [System.Environment]::SetEnvironmentVariable("PATH", "$userPath;$localBin", "User")
    Write-Warn "已将 $localBin 加入用户 PATH，请重启 PowerShell"
} else {
    Write-Ok "PATH 已包含 Python Scripts"
}

# ─────────────────────────────────────────────
# 后续步骤
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  后续步骤（需手动完成）"
Write-Host "══════════════════════════════════════════"
Write-Host ""
Write-Host "  1. LinkedIn 登录（首次必须）："
Write-Host "     uvx linkedin-scraper-mcp --login"
Write-Host ""
Write-Host "  2. 将 CV 放入 my_cv\ 目录"
Write-Host "  3. 编辑 config.json：填写 your_name、your_email、location"
Write-Host "  4. VS Code 打开项目 -> 点击 Spark -> 输入「开始」"
Write-Host ""
Write-Host "  完整文档：SPEC.md" -ForegroundColor Cyan
Write-Host ""
Write-Ok "初始化完成"
Write-Host ""