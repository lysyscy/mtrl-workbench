# ============================================================================
# ops/nssm_uninstall.ps1 —— 撤掉 NSSM 服务（安装脚本的回滚路径）
#
# 用法（⚠️ 管理员 PowerShell）：
#     powershell -NoProfile -ExecutionPolicy Bypass -File ops\nssm_uninstall.ps1
#     ... -RestoreScheduledTask        # 顺手把旧的计划任务形态装回去（回到迁移前）
#
# ⛔ 不动任何数据、不动 backend/、不动 .env —— 它只撤销「服务注册」这一件事。
# ============================================================================
[CmdletBinding()]
param(
    [string] $ServiceName = 'mtrl-workbench-server',
    [string] $RepoRoot    = '',      # ⚠️ 留空 ⇒ 本脚本所在目录的上一级（⛔ 别在 param 默认值里用 $PSScriptRoot：PS 5.1 下它有时为空）
    [string] $NssmPath    = '',
    [switch] $RestoreScheduledTask
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
function Say([string] $m) { Write-Host "[nssm] $m" }
function Die([string] $m) { Write-Host "[nssm][错误] $m" -ForegroundColor Red; exit 1 }

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Die '需要管理员权限 —— 请用「以管理员身份运行」的 PowerShell 重跑。' }

function Resolve-Nssm([string] $explicit) {
    $cands = @()
    if ($explicit) { $cands += $explicit }
    $cands += (Join-Path $PSScriptRoot 'nssm\nssm.exe')
    $cands += (Join-Path $PSScriptRoot 'nssm.exe')
    $cands += 'C:\ProgramData\chocolatey\bin\nssm.exe'
    $cands += 'C:\tools\nssm\nssm.exe'
    $cands += 'D:\tools\nssm\nssm.exe'
    $cands += 'D:\tools\nssm\win64\nssm.exe'
    $cmd = Get-Command nssm -ErrorAction SilentlyContinue
    if ($cmd) { $cands += $cmd.Source }
    foreach ($c in $cands) { if ($c -and (Test-Path -LiteralPath $c)) { return (Resolve-Path -LiteralPath $c).Path } }
    return ''
}

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    Say "服务 $ServiceName 不存在 —— 无需卸载。"
} else {
    if ($svc.Status -ne 'Stopped') { Stop-Service -Name $ServiceName -Force; Start-Sleep -Seconds 2; Say '已停服务' }
    $nssm = Resolve-Nssm $NssmPath
    if ($nssm) {
        & $nssm remove $ServiceName confirm | Out-Null
        Say "已删除服务 $ServiceName"
    } else {
        # 没有 nssm.exe 时的退路：用 PowerShell 的服务 cmdlet（⛔ 不用 sc.exe —— 本机黑名单）
        Say '⚠️ 找不到 nssm.exe ⇒ 改用 PowerShell cmdlet 删服务（nssm 的注册表项可能残留，不影响使用）'
        $null = & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "Remove-Service -Name '$ServiceName'"
    }
}

Start-Sleep -Seconds 1
$still = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($still) { Say "⚠️ 服务仍在（$($still.Status)）—— 请手工确认（可能被别的会话占用）" } else { Say '确认：服务已不存在。' }

if ($RestoreScheduledTask) {
    Say '按 -RestoreScheduledTask：把旧的计划任务形态装回去…'
    $python = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'
    $action  = New-ScheduledTaskAction -Execute $python `
                 -Argument '-m uvicorn app.main:app --host 0.0.0.0 --port 8000' `
                 -WorkingDirectory (Join-Path $RepoRoot 'backend')
    $t = Get-ScheduledTask -TaskName $ServiceName -ErrorAction SilentlyContinue
    if ($t) { Unregister-ScheduledTask -TaskName $ServiceName -Confirm:$false }
    Register-ScheduledTask -TaskName $ServiceName -Action $action -Force `
        -Trigger (New-ScheduledTaskTrigger -AtStartup) `
        -RunLevel Highest -User 'SYSTEM' | Out-Null
    Start-ScheduledTask -TaskName $ServiceName
    Say '计划任务已恢复并启动。'
}
