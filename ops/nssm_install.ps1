# ============================================================================
# ops/nssm_install.ps1 —— 把后端注册成 NSSM 服务（M7-A · 服务化「调试版」）
#
# 口径（用户 2026-09-21 裁定）：**服务形态 = NSSM**，取代此前的计划任务
#   `mtrl-workbench-server`（起停用 Stop-ScheduledTask / Start-ScheduledTask）。
#
# 它与 M7-B（交付版：备份 / 恢复演练 / IP 收紧 / 日志保留）**分开** ——
#   M7-A 只解决「调试期要能随时起停、崩了自拉、日志落文件」，⛔ 不动备份与访问控制。
#
# 用法（⚠️ 必须「以管理员身份」的 PowerShell；普通窗口会当场拒绝）：
#     powershell -NoProfile -ExecutionPolicy Bypass -File ops\nssm_install.ps1
#   ⛔ 别用 cmd.exe / sc.exe 装服务（它们在本机安全策略黑名单里，且会静默失败）。
#
# 前置：需要 `nssm.exe`（脚本自己会按下面顺序找；找不到会告诉你三条获取途径）。
#   NSSM 是**单个 exe、免安装**的 —— 推荐放到 `ops\nssm\nssm.exe`（本目录，随仓留痕）。
#
# 幂等：重复跑 = 先停掉旧服务 → 删掉 → 按同一套参数重建 → 启动。
# 回滚：`ops\nssm_uninstall.ps1`（会把服务删掉并可选恢复计划任务）。
# ============================================================================
[CmdletBinding()]
param(
    [string] $ServiceName = 'mtrl-workbench-server',
    [string] $RepoRoot    = '',      # ⚠️ 留空 ⇒ 本脚本所在目录的上一级（⛔ 别在 param 默认值里用 $PSScriptRoot：PS 5.1 下它有时为空）
    [string] $NssmPath    = '',
    # 迁移用：旧形态（计划任务）的同名任务；-KeepScheduledTask 可保留（默认删，避免两个同时抢 8000）
    [string] $ScheduledTaskName = 'mtrl-workbench-server',
    [switch] $KeepScheduledTask,
    # 装完顺手做一次「杀进程看自愈」的实测（会真的杀一次后端进程）
    [switch] $VerifySelfHeal,
    # 只打印将要执行的动作、不真的改机器
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = Split-Path -Parent $PSScriptRoot }

function Say([string] $m) { Write-Host "[nssm] $m" }
function Die([string] $m) { Write-Host "[nssm][错误] $m" -ForegroundColor Red; exit 1 }

# --- 0. 必须是管理员，否则 nssm 装服务会失败（服务控制管理器要管理员） -------
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Die '需要管理员权限 —— 请用「以管理员身份运行」的 PowerShell 重跑本脚本。' }

# --- 1. 解析三件必要路径（⛔ 一律绝对路径：服务以 LocalSystem 身份运行，没有 cwd 概念）
if (-not (Test-Path -LiteralPath $RepoRoot)) { Die "仓库根不存在：$RepoRoot" }
$BackendDir = Join-Path $RepoRoot 'backend'
$PythonExe  = Join-Path $BackendDir '.venv\Scripts\python.exe'
$LogsDir    = Join-Path $RepoRoot 'logs'
$StdOut     = Join-Path $LogsDir 'server.out.log'
$StdErr     = Join-Path $LogsDir 'server.err.log'

if (-not (Test-Path -LiteralPath $PythonExe)) { Die "找不到 venv 的 python：$PythonExe" }
if (-not (Test-Path -LiteralPath (Join-Path $BackendDir 'app\main.py'))) { Die "找不到 backend\app\main.py —— RepoRoot 猜错了？" }
if (-not (Test-Path -LiteralPath $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }

# 启动参数：**一比一复刻现行计划任务**（见计划 §5.5 / §22.2）
#   ⚠️ 单 worker（不加 --workers）：无定时任务；单进程是为了共享连接池与**进程内抓取互斥锁**。
$AppParameters = '-m uvicorn app.main:app --host 0.0.0.0 --port 8000'

# --- 2. 找 nssm.exe ---------------------------------------------------------
function Resolve-Nssm([string] $explicit) {
    $cands = @()
    if ($explicit) { $cands += $explicit }
    $cands += (Join-Path $PSScriptRoot 'nssm\nssm.exe')
    $cands += (Join-Path $PSScriptRoot 'nssm.exe')
    $cands += 'C:\ProgramData\chocolatey\bin\nssm.exe'
    $cands += 'C:\Program Files\nssm\win64\nssm.exe'
    $cands += 'C:\tools\nssm\nssm.exe'
    $cands += 'D:\tools\nssm\nssm.exe'
    $cands += 'D:\tools\nssm\win64\nssm.exe'
    $cmd = Get-Command nssm -ErrorAction SilentlyContinue
    if ($cmd) { $cands += $cmd.Source }
    foreach ($c in $cands) { if ($c -and (Test-Path -LiteralPath $c)) { return (Resolve-Path -LiteralPath $c).Path } }
    return ''
}
$nssm = Resolve-Nssm $NssmPath
if (-not $nssm) {
    Die @'
找不到 nssm.exe。三条获取途径（任选其一，然后重跑本脚本）：
  ① 官网（推荐）：https://nssm.cc/release/nssm-2.24.zip 解压出 win64\nssm.exe
                 ⇒ 放到  ops\nssm\nssm.exe   （本目录，随仓留痕）
  ② winget：  winget install --id NSSM.NSSM  -e     （装完重开一个管理员窗口）
  ③ 若你本机已有 nssm.exe，直接传：  -NssmPath "D:\tools\nssm\win64\nssm.exe"
⚠️ 别用 sc.exe / cmd.exe 装服务（本机安全策略黑名单）。
'@
}
Say "nssm = $nssm"

Say "服务名        = $ServiceName"
Say "Application   = $PythonExe"
Say "AppParameters = $AppParameters"
Say "AppDirectory  = $BackendDir"
Say "AppStdout     = $StdOut"
Say "AppStderr     = $StdErr"

if ($DryRun) { Say '-DryRun：只打印、不改机器。到此结束。'; exit 0 }

# --- 3. 端口复核（技术栈要求"服务化前再查一次"） ------------------------------
$busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    $pids = ($busy | Select-Object -ExpandProperty OwningProcess -Unique) -join ','
    Say "⚠️ 8000 已被占用（PID=$pids）—— 先把它停掉（多半就是旧计划任务）；本脚本接着会处理计划任务。"
}

# --- 4. 迁移：停掉并（默认）删除同名计划任务，避免两个实例抢 8000 --------------
$task = Get-ScheduledTask -TaskName $ScheduledTaskName -ErrorAction SilentlyContinue
if ($task) {
    if ($KeepScheduledTask) {
        Say "保留计划任务（-KeepScheduledTask）：只停不删 —— ⚠️ 它若被触发仍会与 NSSM 服务抢端口"
        if ($task.State -eq 'Running') { Stop-ScheduledTask -TaskName $ScheduledTaskName; Say '已停计划任务' }
    } else {
        if ($task.State -eq 'Running') { Stop-ScheduledTask -TaskName $ScheduledTaskName; Say '已停计划任务' }
        Unregister-ScheduledTask -TaskName $ScheduledTaskName -Confirm:$false
        Say "已删除计划任务 $ScheduledTaskName（旧形态退场；回滚见 ops\nssm_uninstall.ps1）"
    }
} else {
    Say "（没有同名计划任务，跳过迁移那一步）"
}

# --- 5. 幂等：若服务已存在，先停后删 ----------------------------------------
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($svc) {
    Say "服务 $ServiceName 已存在（$($svc.Status)）⇒ 先停后删，按同一套参数重建"
    if ($svc.Status -ne 'Stopped') { Stop-Service -Name $ServiceName -Force; Start-Sleep -Seconds 2 }
    & $nssm remove $ServiceName confirm | Out-Null
    Start-Sleep -Seconds 1
}

# --- 6. 安装并配置 ----------------------------------------------------------
& $nssm install $ServiceName $PythonExe $AppParameters
if ($LASTEXITCODE -ne 0) { Die "nssm install 失败（exit=$LASTEXITCODE）" }

& $nssm set $ServiceName AppDirectory        $BackendDir
& $nssm set $ServiceName DisplayName          '材料报表自动化工作台（后端）'
& $nssm set $ServiceName Description          'FastAPI + uvicorn 单 worker；工作目录 backend/；日志 logs\server.out.log / server.err.log'

# 日志：分流 ＋ 轮转（⛔ 不滚 = 日志无限长；这是调试期每天要看的东西）
& $nssm set $ServiceName AppStdout           $StdOut
& $nssm set $ServiceName AppStderr           $StdErr
& $nssm set $ServiceName AppRotateFiles       1
& $nssm set $ServiceName AppRotateOnline      1
& $nssm set $ServiceName AppRotateBytes       10485760     # 10 MB
# ⚠️ nssm 2.24 没有 AppTimestampLog 这个参数（2026-09-21 实测：写它会被拒并打印合法参数表）
#    ⇒ 要带时间戳只能另配（暂不需要）；留此注记免得以后又加回来。

# 生命周期：崩溃自重启 ＋ 开机自启 ＋ 与 PG 的依赖
& $nssm set $ServiceName AppExit Default Restart
& $nssm set $ServiceName AppRestartDelay     5000          # 崩溃后 5 秒拉起
& $nssm set $ServiceName AppThrottle         5000
& $nssm set $ServiceName AppStopMethodConsole 15000         # 给 uvicorn 15 秒优雅退出
& $nssm set $ServiceName Start                SERVICE_AUTO_START
& $nssm set $ServiceName ObjectName           LocalSystem
& $nssm set $ServiceName DependOnService      postgresql-x64-18

# ⭐⭐ Playwright 浏览器路径（2026-09-21 实测补的 —— ⛔ 别删）
#   服务以 **LocalSystem** 跑，而 Playwright 的浏览器默认装在**用户目录**
#   （`C:\Users\<人>\AppData\Local\ms-playwright`）⇒ 服务**一定找不到**，症状是
#   「只导出 PDF / 批量打印」全失败：`BrowserType.launch: Executable doesn't exist at
#   C:\WINDOWS\system32\config\systemprofile\AppData\Local\ms-playwright\…`
#   （⚠️ 抓取照常能用 —— 那是纯 HTTP，用不到浏览器 ⇒ 这个故障只打打印/导出那一路）。
#   ⇒ 浏览器统一放**机器级**目录，并把路径**显式交给服务**（⛔ 不依赖"用户环境变量"：
#     服务不读任何用户的用户级变量）。
#   ⚠️ 装浏览器：`$env:PLAYWRIGHT_BROWSERS_PATH='C:\ProgramData\ms-playwright'; <venv>\python.exe -m playwright install chromium`
$PlaywrightBrowsers = 'C:\ProgramData\ms-playwright'
& $nssm set $ServiceName AppEnvironmentExtra   "PLAYWRIGHT_BROWSERS_PATH=$PlaywrightBrowsers"

Say '配置完成，启动服务…'
Start-Service -Name $ServiceName
Start-Sleep -Seconds 5

# --- 7. 自检 ----------------------------------------------------------------
$s = Get-Service -Name $ServiceName
Say "服务状态 = $($s.Status)  启动类型 = $($s.StartType)"
if ($s.Status -ne 'Running') {
    Say '⚠️ 服务没起来 —— 看日志：'
    if (Test-Path -LiteralPath $StdErr) { Get-Content -LiteralPath $StdErr -Tail 40 }
    Die '安装完成但启动失败，请把上面日志发我。'
}

$ok = $false
foreach ($i in 1..10) {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/app' -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
Say "GET /app 探活 = $(if ($ok) { '200 ✓' } else { '失败 ✗（看 logs\server.err.log）' })"

if ($VerifySelfHeal) {
    Say '-VerifySelfHeal：杀掉后端进程，看 30 秒内是否自动拉起…'
    $pid0 = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
             Select-Object -First 1 -ExpandProperty OwningProcess)
    if ($pid0) {
        Stop-Process -Id $pid0 -Force
        Say "已杀 PID=$pid0（这是**故意**的，验证 AppExit=Restart）"
        $back = $false
        foreach ($i in 1..15) {
            Start-Sleep -Seconds 2
            $p = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
                  Select-Object -First 1 -ExpandProperty OwningProcess)
            if ($p -and $p -ne $pid0) { $back = $true; Say "已自动拉起：新 PID=$p（用时约 $($i*2) 秒）"; break }
        }
        if (-not $back) { Say '✗ 没有自动拉起 —— 检查 nssm 的 AppExit / AppRestartDelay 设置' }
    } else { Say '（没有监听到 8000，跳过自愈实测）' }
}

Say ''
Say '============================================================'
Say ' M7-A 安装完成。调试期天天用的是这条：'
Say '   powershell -NoProfile -ExecutionPolicy Bypass -File ops\server_ctl.ps1 -Action restart'
Say ' 看状态 / 看日志：'
Say '   ... -Action status'
Say '   ... -Action log'
Say '============================================================'
