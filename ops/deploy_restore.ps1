<#
  ops/deploy_restore.ps1 —— **在目标机（办公室电脑）一把落**（M8 · `TAIL-188`）

  配合 `ops/pack.ps1`：本机产包 ⇒ 整个目录拷过来 ⇒ 在本脚本里跑一次。
  ⭐ **"落地成功"才算 `M8` ②「恢复演练成功一次」**（本机自己那遍⛔ 不算 —— 机器不同 ≠ 环境相同）。

  落地七步（每步都打印做了什么，⛔ 不静默）：
    0) 校 `SHA256SUMS.txt`（包在拷的过程中损坏 ⇒ 当场发现）
    1) 落仓：`git clone <包里的 bundle>` ⇒ **含全部历史**（`D18`）
    2) 把包内**非 git 件**放回：记忆档 / `nssm.exe` / 产物 / 壳基线
    3) `venv` ＋ 依赖（目标机已有环境 ⇒ 只会补缺）
    4) `.env`：**只检查、不写**（真口令不进包 —— 守 `TAIL-88`）⇒ 缺哪几个键就列出来
    5) 库：`-Mode empty`（建库＋迁移 ⇒ 干净可用）／ `-Mode asis`（灌包里那份现状 dump）
    6) 服务：调既有的 `ops\nssm_install.ps1`（幂等）
    7) 探活 ＋ 跑 `ops\selfcheck.ps1`

  用法（目标机 · **管理员**窗口）：
    powershell -ExecutionPolicy Bypass -File ops\deploy_restore.ps1 -Pack D:\deliver\mtrl-20260929
    powershell -ExecutionPolicy Bypass -File ops\deploy_restore.ps1 -Pack <目录> -Mode asis
    powershell -ExecutionPolicy Bypass -File ops\deploy_restore.ps1 -Pack <目录> -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $Pack,                    # 包目录（拷过来的那个）
    [string] $RepoRoot  = 'D:\dev\mtrl-workbench',                   # ⭐ 目标机仓落点（用户 2026-09-29：放 D:\dev）
    [ValidateSet('empty', 'asis')][string] $Mode = 'empty',
    [string] $PgBin     = 'C:\Program Files\PostgreSQL\16\bin',
    [string] $DbName    = 'mtrl_workbench',
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
function Say($m) { Write-Host $m }
function Step($m) { Write-Host ''; Write-Host ('── ' + $m) }
function Run($exe, [string[]] $argv, $cwd) {
    Say ('   > ' + $exe + ' ' + ($argv -join ' '))
    if ($DryRun) { return 0 }
    # ⚠️ 2026-09-29 修：**子进程一律带 UTF-8 的 IO 编码** —— `alembic` / `psql` 都会回显**中文**
    #    （表名 / 注释 / 角色名），而 Windows 控制台默认代码页是 GBK ⇒ 实测 `alembic upgrade head`
    #    的输出**整段乱码**（结论不受影响，但**看着像出错** ⇒ 目标机上最容易把人吓住的就是它）。
    #    `PGCLIENTENCODING` 管 psql 那一路；`PYTHONIOENCODING` 管 python/alembic。
    $prevPy = $env:PYTHONIOENCODING
    $prevPg = $env:PGCLIENTENCODING
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PGCLIENTENCODING = 'UTF8'
    Push-Location $cwd; & $exe @argv; $code = $LASTEXITCODE; Pop-Location
    if ($null -eq $prevPy) { Remove-Item Env:\PYTHONIOENCODING -ErrorAction SilentlyContinue } else { $env:PYTHONIOENCODING = $prevPy }
    if ($null -eq $prevPg) { Remove-Item Env:\PGCLIENTENCODING -ErrorAction SilentlyContinue } else { $env:PGCLIENTENCODING = $prevPg }
    return $code
}

Say '=== ops/deploy_restore.ps1 · 目标机落地 ==='
Say ('包   = ' + $Pack)
Say ('仓   = ' + $RepoRoot)
Say ('库   = ' + $Mode + '（empty＝空库＋迁移 / asis＝灌包里的现状 dump）')
if (-not (Test-Path $Pack)) { Say '⛔ 包目录不存在'; exit 2 }

# ---- 0) 校验和 ----
Step '0) 校 SHA256SUMS.txt'
$sum = Join-Path $Pack 'SHA256SUMS.txt'
if (Test-Path $sum) {
    $bad = @()
    foreach ($l in Get-Content $sum -Encoding UTF8) {
        if (-not $l.Trim()) { continue }
        $h, $rel = $l -split '\s+', 2
        $p = Join-Path $Pack $rel.Trim()
        if (-not (Test-Path $p)) { $bad += ('缺 ' + $rel); continue }
        if ((Get-FileHash $p -Algorithm SHA256).Hash -ne $h) { $bad += ('损坏 ' + $rel) }
    }
    if ($bad.Count) { Say ('   ⛔ 校验不过：' + ($bad -join ' / ') + ' ⇒ 停手，重拷一次'); exit 1 }
    Say '   ✓ 全部对上'
} else { Say '   ⚠️ 包里没有 SHA256SUMS.txt ⇒ 跳过（⛔ 不推荐：无法发现拷贝损坏）' }

# ---- 1) 落仓 ----
Step '1) 落仓（git clone <bundle> · 含全部历史）'
$bundle = Join-Path $Pack 'repo\mtrl-workbench.bundle'
if (-not (Test-Path $bundle)) { Say '   ⛔ 包里没有 repo\mtrl-workbench.bundle ⇒ 停手'; exit 1 }
if (Test-Path (Join-Path $RepoRoot '.git')) {
    Say ('   ⚠️ ' + $RepoRoot + ' 已经是 git 仓 ⇒ 改为从 bundle 拉取（⛔ 不覆盖工作区）')
    $null = Run 'git' @('-C', $RepoRoot, 'fetch', $bundle, 'master:refs/remotes/bundle/master') $RepoRoot
    Say '   ⚠️ 合并/切换请人工确认（本脚本⛔ 不替你 merge / reset）'
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $RepoRoot) | Out-Null
    $null = Run 'git' @('clone', $bundle, $RepoRoot) (Split-Path -Parent $RepoRoot)
}
if ($DryRun) { Say '   [干跑]' } else { Say ('   ✓ 仓在 ' + $RepoRoot) }

# ---- 2) 非 git 件放回 ----
Step '2) 非 git 件放回（记忆 / nssm.exe / 产物 / 壳基线）'
foreach ($rel in @('.codebuddy\memory', '.workbuddy\memory', 'ops\nssm', 'artifacts', 'backups')) {
    $s = Join-Path $Pack $rel
    if (-not (Test-Path $s)) { Say ('   ⚠️ 包里没有 ' + $rel + '（跳过）'); continue }
    if ($DryRun) { Say ('   [干跑] ' + $rel + ' -> ' + $RepoRoot); continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent (Join-Path $RepoRoot $rel)) | Out-Null
    Copy-Item -Recurse -Force $s (Join-Path $RepoRoot $rel)
    Say ('   ✓ ' + $rel)
}

# ---- 3) venv ＋ 依赖 ----
Step '3) venv ＋ 依赖'
$venv = Join-Path $RepoRoot 'backend\.venv'
if (Test-Path (Join-Path $venv 'Scripts\python.exe')) { Say '   ✓ venv 已在（目标机原有环境沿用）' }
else {
    Say '   ⚠️ 没有 venv ⇒ 建一个（⚠️ 目标机若已有 Python，注意版本要与本机一致，见 docs\deployment.md）'
    $null = Run 'python' @('-m', 'venv', $venv) $RepoRoot
}
$req = Join-Path $RepoRoot 'backend\requirements.txt'
if (Test-Path $req) { $null = Run (Join-Path $venv 'Scripts\python.exe') @('-m', 'pip', 'install', '-r', $req) (Join-Path $RepoRoot 'backend') }
else { Say '   ⚠️ 没有 backend\requirements.txt ⇒ 跳过（⚠️ 目标机缺包时按 docs\deployment.md 装）' }

# ---- 4) .env：只检查 ----
Step '4) .env（⛔ 不写：真口令不进包）'
$envFile = Join-Path $RepoRoot '.env'   # ⚠️ 在**仓根**（不是 backend/）
if (Test-Path $envFile) {
    Say ('   ✓ 已有 ' + $envFile + '（⚠️ 逐项核：i8 账号 / 库口令 / ALLOWED_IP_CIDRS 是本机的还是目标机的）')
} else {
    Say '   ⛔ 缺**仓根** `.env` ⇒ **停在这里之前请先补**（键名与取值见 docs\deployment.md §二）'
    Say '      （若目标机旧的那半开发留过 .env，直接用它的；没有就按 ops\init_db.sql 里的账号口令写）'
}

# ---- 5) 库 ----
Step ('5) 库 · ' + $Mode)
$psql = Join-Path $PgBin 'psql.exe'
if ($Mode -eq 'empty') {
    Say '   · 建库＋角色：ops\init_db.sql（⚠️ 先把里面的 <PASSWORD> 换成目标机口令，并同步写进 backend\.env）'
    $null = Run $psql @('-U', 'postgres', '-f', (Join-Path $RepoRoot 'ops\init_db.sql')) $RepoRoot
    Say '   · 建表：alembic upgrade head'
    $null = Run (Join-Path $venv 'Scripts\python.exe') @('-m', 'alembic', 'upgrade', 'head') (Join-Path $RepoRoot 'backend')
    Say '   ⭐ 空库是**对的**：真实历史随后用「数据导入」页的四个入口录（付款存量 / 过程资料 / 集采 / 库存补抓）'
} else {
    $dump = Get-ChildItem (Join-Path $Pack 'db') -Filter '*.dump' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $dump) { Say '   ⛔ 包里没有 db\*.dump ⇒ -Mode asis 用不了（改用 -Mode empty）'; exit 1 }
    Say ('   · 灌 ' + $dump.Name + '（--clean --if-exists ⇒ 会覆盖现有同名对象）')
    $null = Run (Join-Path $PgBin 'pg_restore.exe') @('-U', 'mtrl', '-d', $DbName, '--clean', '--if-exists', $dump.FullName) $RepoRoot
}

# ---- 6) 服务 ----
Step '6) 注册服务（NSSM · 幂等）'
$install = Join-Path $RepoRoot 'ops\nssm_install.ps1'
if (Test-Path $install) { $null = Run 'powershell' @('-ExecutionPolicy', 'Bypass', '-File', $install) $RepoRoot }
else { Say '   ⚠️ 没有 ops\nssm_install.ps1 ⇒ 跳过（⚠️ 那就没有开机自启）' }

# ---- 7) 探活 ＋ 自检 ----
Step '7) 探活 ＋ 自检'
Start-Sleep -Seconds 5
$check = Join-Path $RepoRoot 'ops\selfcheck.ps1'
if (Test-Path $check) { $null = Run 'powershell' @('-ExecutionPolicy', 'Bypass', '-File', $check, '-RepoRoot', $RepoRoot) $RepoRoot }
else { Say '   ⚠️ 没有 ops\selfcheck.ps1 ⇒ 请手工打开 http://127.0.0.1:8000/app 看一眼' }

Say ''
Say '=== 落地流程走完 ==='
Say '⭐ 通关判据（`M8` ②）＝ selfcheck 全 ✅ ⇒ 然后进 `M8` ①：在「数据导入」页走四个初始化入口各一小段。'
Say '⚠️ 出问题先看：ops\server_ctl.ps1 log（服务日志）· ops\server_ctl.ps1 port（8000 被谁占）· ops\server_ctl.ps1 pg（PG 服务）'
