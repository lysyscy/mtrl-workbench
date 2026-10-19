# ============================================================================
# ops/server_ctl.ps1 —— 调试期天天用的「后端服务遥控器」
#
# 为什么有它：后端**没有 --reload** ⇒ **改完 Python 代码必须重启进程**，
#   否则新端点/新逻辑一律不生效（症状：新 API 返回 404，而全绿的自检与 pytest 照绿
#   —— 因为测试直接 import 代码、不走那个进程）。本脚本把「重启」压成一条命令。
#
# 用法（普通窗口即可；只有 start/stop/restart 需要管理员）：
#     powershell -NoProfile -ExecutionPolicy Bypass -File ops\server_ctl.ps1 -Action status
#   -Action 可选：status | start | stop | restart | log | port | pg | all
#     status   服务状态 + 端口 + /app 探活（默认）
#     start/stop/restart  起停重启（restart = stop → start → 探活）
#     log      打印 var\log\server.err.log 与 server.out.log 的尾部
#     port     占用 8000 的进程与其命令行（诊断"是不是旧进程"）
#     pg       PostgreSQL 服务状态
#     all      上面全部
#   -Tail 200           log 显示的行数
#   -WaitSec 20         restart 后等探活的最长秒数
# ============================================================================
[CmdletBinding()]
param(
    [ValidateSet('status','start','stop','restart','log','port','pg','all')]
    [string] $Action = 'status',
    [string] $ServiceName = 'mtrl-workbench-server',
    [string] $RepoRoot    = '',      # ⚠️ 留空 ⇒ 本脚本所在目录的上一级（⛔ 别在 param 默认值里用 $PSScriptRoot：PS 5.1 下它有时为空）
    [int]    $Tail     = 200,
    [int]    $WaitSec  = 20
)

$ErrorActionPreference = 'Continue'
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
$LogsDir = Join-Path $RepoRoot 'var/log'

function Line([string] $m) { Write-Host $m }

function Show-Service {
    $s = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($s) { Line ("服务 {0}：{1} / {2}" -f $ServiceName, $s.Status, $s.StartType) }
    else {
        Line "服务 $ServiceName：**不存在**"
        $t = Get-ScheduledTask -TaskName $ServiceName -ErrorAction SilentlyContinue
        if ($t) { Line "  ⚠️ 但存在同名**计划任务**（$($t.State)）—— 说明还在 M7-A 之前的旧形态。" }
    }
}

function Show-Port {
    $c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if (-not $c) { Line '端口 8000：无人监听'; return }
    foreach ($p in ($c | Select-Object -ExpandProperty OwningProcess -Unique)) {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$p" -ErrorAction SilentlyContinue).CommandLine
        $start = (Get-Process -Id $p -ErrorAction SilentlyContinue).StartTime
        Line ("端口 8000：PID={0} 启动于 {1}" -f $p, $start)
        Line ("          命令行 = {0}" -f $cmd)
    }
}

function Show-Probe {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/app' -UseBasicParsing -TimeoutSec 5
        Line ("探活 GET /app = {0} {1}" -f $r.StatusCode, $r.StatusDescription)
    } catch {
        Line ("探活 GET /app = 失败（{0}）" -f $_.Exception.Message)
    }
}

function Do-Start {
    Assert-Admin
    $s = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $s) { Line "服务 $ServiceName 不存在 —— 先跑 ops\nssm_install.ps1"; return }
    if ($s.Status -eq 'Running') { Line '已经是 Running，跳过'; return }
    Start-Service -Name $ServiceName
    Line '已发出启动指令'
}

function Do-Stop {
    Assert-Admin
    $s = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $s) { Line "服务 $ServiceName 不存在（改用计划任务？Stop-ScheduledTask -TaskName $ServiceName）"; return }
    Stop-Service -Name $ServiceName -Force
    Line '已停'
}

function Assert-Admin {
    $ok = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
          ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $ok) { Line '⚠️ 起停服务需要管理员权限 —— 请用「以管理员身份运行」的 PowerShell。'; exit 1 }
}

function Do-Restart {
    Line '--- stop ---'
    Do-Stop
    Start-Sleep -Seconds 2
    Line '--- start ---'
    Do-Start
    for ($i = 0; $i -lt $WaitSec; $i++) {
        Start-Sleep -Seconds 1
        try {
            $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/app' -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { Line ("重启成功：/{0} 秒后 /app = 200" -f ($i + 1)); return }
        } catch { }
    }
    Line ('⚠️ {0} 秒内没探活成功 —— 看日志：' -f $WaitSec)
    Show-Log
}

function Show-Log {
    foreach ($f in @('server.err.log','server.out.log','app_{0}.log' -f (Get-Date -Format 'yyyy-MM-dd'))) {
        $p = Join-Path $LogsDir $f
        if (Test-Path -LiteralPath $p) {
            Line ("--- {0} （尾 {1} 行）---" -f $f, $Tail)
            Get-Content -LiteralPath $p -Tail $Tail
        }
    }
}

function Show-Pg {
    $pg = Get-Service -Name 'postgresql-x64-18' -ErrorAction SilentlyContinue
    if ($pg) { Line ("PG：{0} / {1}" -f $pg.Status, $pg.StartType) } else { Line 'PG：找不到 postgresql-x64-18' }
}

switch ($Action) {
    'status'  { Show-Service; Show-Port; Show-Probe }
    'start'   { Do-Start }
    'stop'    { Do-Stop }
    'restart' { Do-Restart }
    'log'     { Show-Log }
    'port'    { Show-Port }
    'pg'      { Show-Pg }
    'all'     { Show-Service; Show-Pg; Show-Port; Show-Probe; Show-Log }
}
