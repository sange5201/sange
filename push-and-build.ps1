# push-and-build.ps1
# 用途：把本地仓库推送到你的 GitHub 空仓库，触发云 CI 自动跑 UI 烟雾 + 出 APK。
# 为什么需要它：当前 AI 会话没有你的 GitHub 凭据，无法替你 push；本机一键脚本由你本人在有网终端运行。
#
# 用法：
#   1. 用记事本打开本文件，把下面 $RepoUrl 改成你新建的「空」GitHub 仓库地址
#      （例如 https://github.com/你的用户名/你的仓库名.git）
#   2. 在本文件所在目录打开 PowerShell（地址栏输入 powershell 回车），执行：
#        .\push-and-build.ps1
#   3. 推送成功后脚本会自动打开 Actions 页；等 build-apk job 完成即可下载 APK。
#
# 注意：仓库请建为「空仓库」（不要勾 README / .gitignore / License），否则首次 push 会被拒绝。

param(
    [string]$RepoUrl = "https://github.com/<你的用户名>/<仓库名>.git"
)

if ($RepoUrl -like "*<*") {
    Write-Host "【错误】请先编辑本脚本顶部的 `$RepoUrl，改成你的 GitHub 空仓库地址。" -ForegroundColor Yellow
    exit 1
}

# 清理可能存在的旧 remote，避免冲突
git remote remove origin 2>$null
git remote add origin $RepoUrl
Write-Host "已添加 remote -> $RepoUrl" -ForegroundColor Cyan

# 推送 main 分支（CI 在 push 后自动触发；也可在 GitHub Actions 页手动 Run workflow）
git push -u origin main
if ($LASTEXITCODE -eq 0) {
    Write-Host "推送成功！GitHub 正在云端跑流水线：core 单测 -> UI 烟雾 -> CLI 冒烟 -> 出 APK。" -ForegroundColor Green
    # 从仓库地址推导 Actions 页并打开
    $clean = $RepoUrl -replace '\.git$', ''
    $m = [regex]::Match($clean, 'github\.com/([^/]+)/([^/]+)')
    if ($m.Success) {
        $actions = "https://github.com/$($m.Groups[1])/$($m.Groups[2])/actions"
        Write-Host "打开 Actions 查看进度并下载 APK 产物：$actions" -ForegroundColor Cyan
        Start-Process $actions
    } else {
        Write-Host "请自行打开 GitHub 仓库的 Actions 页查看进度。" -ForegroundColor Cyan
    }
} else {
    Write-Host "【失败】推送未成功。常见原因：仓库地址有误 / 未登录 GitHub / 仓库非空（含 README）。" -ForegroundColor Red
    Write-Host "  解决：确认地址；在 PowerShell 先运行 'git config --global credential.helper manager' 并登录；或新建空仓库。" -ForegroundColor Red
}
