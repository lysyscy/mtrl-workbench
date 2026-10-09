<#
  ops/deploy_restore.ps1 —— **在目标机（办公室电脑）一把落**（M8 · `TAIL-188`）

  配合 `ops/pack.ps1`：本机产包 ⇒ 整个目录拷过来 ⇒ 在本脚本里跑一次。
  安装与 selfcheck 只证明安装层；真实备份恢复须在隔离空库还原并核对数据，完成标准回 ops/deployment.md §三。

  落地七步（每步都打印做了什么，⛔ 不静默）：
    0) 校 `SHA256SUMS.txt`（包在拷的过程中损坏 ⇒ 当场发现）
    1) 落仓：`git clone <包里的 bundle>` ⇒ **含全部历史**（`D18`）
    2) 把包内**非 git 件**放回：记忆档 / `nssm.exe` / 产物 / 壳基线
    2b) ⭐ **交付面快照**（⭐ 2026-09-30 用户指示 · 包里**只带 2 件**：`face\材料科业务全流程说明书.md`
        ＋ `face\PRD\验收\验收基线.json`）—— 本步**只报"怎么用"**：⛔ 不动任何交付面文件、⛔ 不写 `.env`
        （守 `TAIL-88`）；要跑验收面那套尺子就把 `.env` 的 `PRD_ACCEPTANCE_BASELINE` 指过去
        （完整现行交付面需显式复制/配置，主人回 ops/deployment.md §四；包内两件仅作快照对照）
    3) `venv` ＋ 依赖（目标机已有环境 ⇒ 只会补缺）
    4) `.env`：只查文件存在、不检查键、不写；缺失仍继续，执行前须另核配置完整性
    5) 库：`-Mode empty`（建库＋迁移）／ `-Mode asis`（包内dump覆盖同名对象；不是服务故障的默认修复）
    6) 服务：调既有的 `ops\nssm_install.ps1`（幂等）
    7) 探活 ＋ 跑 `ops\selfcheck.ps1`

  前提与权限先读 ops/deployment.md §〇：缺.env仍继续、子进程退出码未统一拦截；末尾输出不是成功回执。
  DryRun跳过Run内子进程及部分写入，新仓分支仍可创建父目录，不能视为全程只读。
  用法（已确认目标机/包/数据权限 · **管理员**窗口）：
    powershell -ExecutionPolicy Bypass -File ops\deploy_restore.ps1 -Pack D:\deliver\mtrl-20260929
    powershell -ExecutionPolicy Bypass -File ops\deploy_restore.ps1 -Pack <目录> -Mode asis
    powershell -ExecutionPolicy Bypass -File ops\deploy_restore.ps1 -Pack <目录> -DryRun
    powershell -ExecutionPolicy Bypass -File ops\deploy_restore.ps1 -Pack <目录> -WriteBaseline   # ⭐ 顺手把**包内**那份验收基线写进仓根 `.env`（⚠️ 默认⛔ 不写；写前自动备份 `.env`）
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $Pack,                    # 包目录（拷过来的那个）
    [string] $RepoRoot  = 'D:\dev\mtrl-workbench',                   # ⭐ 目标机仓落点（用户 2026-09-29：放 D:\dev）
    [ValidateSet('empty', 'asis')][string] $Mode = 'empty',
    [string] $PgBin     = 'C:\Program Files\PostgreSQL\16\bin',
    [string] $DbName    = 'mtrl_workbench',
    [switch] $WriteBaseline,                                         # ⭐ 显式开关（默认 ⛔ 不写）：把**包内**那份验收基线写进仓根 `.env`
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
# ⚠️⚠️ 2026-09-29 修：本表原写成裸 `'backups'` —— 而仓里**没有**顶层 `backups/`（真身 = `.codebuddy\backups\`；
#    唯一主人 = `tools/audit/shell_verify.py` 的 `BACKUPS`）。⚠️ 本表每条 `$rel` 都是**包内相对路径 = 仓内相对路径**
#    （其余四项本来就是这样）⇒ 改成 `.codebuddy\backups` 才**左右对称**；否则即使包里带了壳基线，
#    也会被放到**目标机的顶层 `backups\`** ⇒ 而 `shell_verify` 只看 `.codebuddy\backups` ⇒ **照旧判红"没有基线"** ✗。
# ⭐ 2026-10-01（`TAIL-204` 第 2 步）：两个记忆家已并成一个 ⇒ ⛔ 原第二项 `.workbuddy\memory` 已删（它被机械改名后与首项重复）
foreach ($rel in @('.codebuddy\memory', 'ops\nssm', 'artifacts', '.codebuddy\backups')) {
    $s = Join-Path $Pack $rel
    if (-not (Test-Path $s)) { Say ('   ⚠️ 包里没有 ' + $rel + '（跳过）'); continue }
    if ($DryRun) { Say ('   [干跑] ' + $rel + ' -> ' + $RepoRoot); continue }
    $dstRel = Join-Path $RepoRoot $rel
    New-Item -ItemType Directory -Force -Path $dstRel | Out-Null
    # ⚠️⚠️ 2026-10-04 修（与 `ops\pack.ps1` 同源 —— 那道坑的**镜像**）：原先 `Copy-Item -Recurse -Force $s $dstRel`
    #    在 `$dstRel` **已存在**时会把源目录**塞进**它里面 ⇒ `.codebuddy\memory\memory\…`。
    #    ⚠️ 目标机上**必然**撞：仓是 clone 来的 ⇒ `.codebuddy\memory` **本来就在** ⇒ 每次落地都多造一份重复件。
    #    ⇒ 正解 = 拷**内容**（`$s\*`）⇒ 幂等合并、不再嵌套。
    Copy-Item -Path (Join-Path $s '*') -Destination $dstRel -Recurse -Force
    Say ('   ✓ ' + $rel)
}

# ---- 2b) 交付面快照（⭐ 2026-09-30 用户指示 · 包里只带那 2 件 · 本步⛔ 不写任何文件）----
#  完整现行交付面须显式复制/配置，位置回 ops/deployment.md §四，不假设WPS同步；
#    ② `.env` 里真口令/真路径**一律不替用户写**（本脚本第 4 步的口径）⇒ 这里只把"该填什么"打出来。
Step '2b) 交付面快照（《说明书》＋ 验收基线 · 包里只带这 2 件）'
$faceSnap = Join-Path $Pack 'face'
if (-not (Test-Path -LiteralPath $faceSnap)) {
    Say '   ⚠️ 包里没有 face\（产包时用了 -SkipFace，或交付面缺件）⇒ 核对并配置完整现行交付面（见 ops\deployment.md §四）'
    Say '      ⚠️ 后果：完整交付面未配齐 ⇒ 相关验收无法据完整输入执行'
} else {
    $snapList = @(Get-ChildItem -LiteralPath $faceSnap -Recurse -File | ForEach-Object { $_.FullName.Substring($faceSnap.Length + 1) })
    Say ('   ✓ 包内快照：' + ($snapList -join ' · '))
    Say '   ⭐ 两种用法（挑一种写进**仓根 `.env`**）：'
    Say '      ① **完整现行交付面已配置** ⇒ PRD_ACCEPTANCE_BASELINE=<交付面根>\PRD\验收\验收基线.json'
    Say ('      ② **包内快照仅作历史对照**（不替代完整交付面）⇒ PRD_ACCEPTANCE_BASELINE=' + (Join-Path $faceSnap 'PRD\验收\验收基线.json'))
    Say '      ⚠️ 改完 `.env` 要**重启后端**（它没有 --reload）；该键的读取方 = `doc_audit` / `_audit_face.py` / `acc_report`'
    # ⭐ `-WriteBaseline`（2026-09-30 补 · 用户指示③「.env 的 PRD_ACCEPTANCE_BASELINE 默认指包内」）：
    #    默认**只报不写**（守 `A6`：真 `.env` 不进包 / 脚本不替你写）；给了开关才动 ⇒ **只改那一行**，
    #    且**写前先备份** `.env`（现有配置可恢复；包内快照不自动成为完整现行真源）。
    if ($WriteBaseline) {
        $blFile = Join-Path $RepoRoot '.env'
        $blVal  = Join-Path $faceSnap 'PRD\验收\验收基线.json'
        if (-not (Test-Path -LiteralPath $blFile)) {
            Say ('   ⛔ -WriteBaseline 要写 ' + $blFile + '，但**它不存在** ⇒ 跳过（先照上表把 `.env` 建起来）')
        } elseif ($DryRun) {
            Say ('   [干跑] 把 ' + $blFile + ' 的 PRD_ACCEPTANCE_BASELINE 改为：' + $blVal)
        } else {
            $blBak = $blFile + '.bak-' + (Get-Date -Format 'yyyyMMdd-HHmm')
            Copy-Item -LiteralPath $blFile -Destination $blBak -Force
            $hit = $false
            $out = foreach ($l in (Get-Content -LiteralPath $blFile -Encoding UTF8)) {
                if ($l.TrimStart().StartsWith('PRD_ACCEPTANCE_BASELINE=')) { $hit = $true; 'PRD_ACCEPTANCE_BASELINE=' + $blVal } else { $l }
            }
            if (-not $hit) { $out = @($out) + ('PRD_ACCEPTANCE_BASELINE=' + $blVal) }
            [IO.File]::WriteAllLines($blFile, [string[]]$out, (New-Object Text.UTF8Encoding($false)))
            Say ('   ✓ 已写 PRD_ACCEPTANCE_BASELINE=' + $blVal)
            Say ('      （`.env` 备份 = ' + (Split-Path -Leaf $blBak) + '；⚠️ **重启后端**才生效）')
        }
    } else {
        Say '   ⏭ 未给 `-WriteBaseline` ⇒ **只报告、不写** `.env`（默认口径：真 `.env` 不进包 · 脚本不替你写）'
    }
    if ($DryRun) { Say '   [干跑]' }
}

# ---- 3) venv ＋ 依赖 ----
Step '3) venv ＋ 依赖'
$venv = Join-Path $RepoRoot 'backend\.venv'
if (Test-Path (Join-Path $venv 'Scripts\python.exe')) { Say '   ✓ venv 已在（目标机原有环境沿用）' }
else {
    Say '   ⚠️ 没有 venv ⇒ 建一个（⚠️ 目标机若已有 Python，注意版本要与本机一致，见 ops\deployment.md）'
    $null = Run 'python' @('-m', 'venv', $venv) $RepoRoot
}
# ---- 3b) ⭐ 依赖镜像加固（2026-10-02 补 · `TAIL-188` 只读清点当场挖出的缺口）----
#  为什么要有这一段：镜像 URL 原先**只**活在 `backend\.venv\pip.ini` 里，而 **`.venv` 是 gitignore 的**
#    ⇒ **不进 bundle** ⇒ 目标机**重建 venv** 之后那份加固**当场失效**（悄悄走默认 PyPI 官方源 —— 国内
#    可能极慢/超时），而 ⛔ **本脚本原先一个字都不报**（静默失效 = 本仓最贵那一类）。
#  ⭐ 修法（用户 2026-10-02 选「乙」）：**真源搬进仓** = `ops\pip.ini`（随 bundle 走）⇒ 这里**复制成 venv 级**。
#  ⚠️ **一处定义**：`ops\pip.ini` 是唯一主人，`backend\tests\test_pipini_single_source.py` 守"两份逐字节相同"。
#  ⚠️ 已在**且不同**时**不静默覆盖**：报出来让人判（目标机可能故意用别的镜像）。
$pipSrc = Join-Path $RepoRoot 'ops\pip.ini'
$pipDst = Join-Path $venv 'pip.ini'
if (-not (Test-Path -LiteralPath $pipSrc)) {
    Say '   ⛔ 仓里没有 ops\pip.ini ⇒ 依赖会走默认 PyPI 源（国内可能极慢）—— 先把它补回来再继续'
} elseif (-not (Test-Path -LiteralPath $pipDst)) {
    if ($DryRun) { Say ('   [干跑] ' + $pipSrc + ' -> ' + $pipDst) }
    else {
        New-Item -ItemType Directory -Force -Path $venv | Out-Null
        Copy-Item -Force -LiteralPath $pipSrc -Destination $pipDst
        Say ('   ✓ 依赖镜像已落 venv 级：' + $pipDst + '（来自 ops\pip.ini）')
    }
} elseif ((Get-FileHash $pipSrc -Algorithm SHA256).Hash -ne (Get-FileHash $pipDst -Algorithm SHA256).Hash) {
    Say '   ⚠️ venv 里那份 pip.ini 与仓内真源**不一致**（目标机可能故意用别的镜像）⇒ **只报不覆盖**：'
    Say ('       仓内 ops\pip.ini = ' + ((Get-Content -LiteralPath $pipSrc -Encoding UTF8) -join ' | '))
    Say ('       现有 venv\pip.ini = ' + ((Get-Content -LiteralPath $pipDst -Encoding UTF8) -join ' | '))
} else {
    Say '   ✓ 依赖镜像已在，且与仓内真源一致（venv 级 pip.ini）'
}
$req = Join-Path $RepoRoot 'backend\requirements.txt'
if (Test-Path $req) { $null = Run (Join-Path $venv 'Scripts\python.exe') @('-m', 'pip', 'install', '-r', $req) (Join-Path $RepoRoot 'backend') }
else { Say '   ⚠️ 没有 backend\requirements.txt ⇒ 跳过（⚠️ 目标机缺包时按 ops\deployment.md 装）' }

# ---- 4) .env：只检查 ----
Step '4) .env（⛔ 不写：真口令不进包）'
$envFile = Join-Path $RepoRoot '.env'   # ⚠️ 在**仓根**（不是 backend/）
if (Test-Path $envFile) {
    Say ('   ✓ 已有 ' + $envFile + '（⚠️ 逐项核：i8 账号 / 库口令 / ALLOWED_IP_CIDRS 是本机的还是目标机的）')
} else {
    Say '   ⛔ 缺**仓根** `.env` ⇒ **实际脚本仍继续，执行前须先补齐**（键名与取值见 ops\deployment.md §二）'
    Say '      （按已确认目标机与角色配置；勿照抄旧机实值，见 ops\deployment.md §二）'
}

# ---- 5) 库 ----
Step ('5) 库 · ' + $Mode)
$psql = Join-Path $PgBin 'psql.exe'
if ($Mode -eq 'empty') {
    Say '   · 建库＋角色：ops\init_db.sql（⚠️ 先把里面的 <PASSWORD> 换成目标机口令，并同步写进仓根 .env）'
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
Say '=== 已到流程末尾（不作成功证明） ==='
Say '⚠️ 流程末尾不等于成功：本脚本未统一拦截子进程失败；须核对各步退出码和selfcheck实际结果。'
Say '⭐ 安装层自检与真实备份恢复分别核验；恢复到隔离空库并核对数据才证明可恢复，见 ops\deployment.md §三。'
Say '⚠️ 出问题先看：ops\server_ctl.ps1 log（服务日志）· ops\server_ctl.ps1 port（8000 被谁占）· ops\server_ctl.ps1 pg（PG 服务）'
