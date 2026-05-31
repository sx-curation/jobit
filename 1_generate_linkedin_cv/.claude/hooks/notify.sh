#!/usr/bin/env bash
# .claude/hooks/notify.sh
# Stop hook：任务完成时发送桌面通知
# 支持：macOS / Linux（notify-send）/ Windows WSL / Windows Git Bash

INPUT=$(cat)
GENERATED=$(find output -name "cv_draft.md" 2>/dev/null | wc -l | tr -d ' ')
TITLE="LinkedIn CV Agent"

if [[ "$GENERATED" -gt 0 ]]; then
    MSG="已生成 ${GENERATED} 份 CV 草稿，请在 VS Code 中审核"
else
    MSG="任务完成，请查看结果"
fi

# ── 检测系统并发送通知 ────────────────────────────────────────

# macOS
if [[ "$(uname -s)" == "Darwin" ]]; then
    osascript -e "display notification \"$MSG\" with title \"$TITLE\" sound name \"Glass\""

# Windows WSL
elif grep -qi microsoft /proc/version 2>/dev/null; then
    # 通过 PowerShell.exe 发送 Windows 原生通知
    powershell.exe -Command "
        Add-Type -AssemblyName System.Windows.Forms
        \$notify = New-Object System.Windows.Forms.NotifyIcon
        \$notify.Icon = [System.Drawing.SystemIcons]::Information
        \$notify.BalloonTipTitle = '$TITLE'
        \$notify.BalloonTipText = '$MSG'
        \$notify.Visible = \$true
        \$notify.ShowBalloonTip(5000)
        Start-Sleep -Seconds 6
        \$notify.Dispose()
    " 2>/dev/null || true

# Windows Git Bash（MSYS）
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # msg 命令（Windows 内置）
    if command -v msg &>/dev/null; then
        msg "%username%" "$TITLE: $MSG" 2>/dev/null || true
    else
        # 降级到 PowerShell toast
        powershell -Command "
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
            \$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
                [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            \$template.GetElementsByTagName('text')[0].AppendChild(
                \$template.CreateTextNode('$TITLE')) | Out-Null
            \$template.GetElementsByTagName('text')[1].AppendChild(
                \$template.CreateTextNode('$MSG')) | Out-Null
            \$toast = [Windows.UI.Notifications.ToastNotification]::new(\$template)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('LinkedIn CV Agent').Show(\$toast)
        " 2>/dev/null || true
    fi

# Linux（GNOME / KDE）
elif command -v notify-send &>/dev/null; then
    notify-send "$TITLE" "$MSG" --icon=dialog-information 2>/dev/null || true

# 终端回退（所有平台）
else
    echo ""
    echo "══════════════════════════════"
    echo "  $TITLE"
    echo "  $MSG"
    echo "══════════════════════════════"
fi