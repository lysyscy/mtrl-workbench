<#
  ops/pack.ps1 —— **在本机产"交付包"**（M8 · `TAIL-188` · 2026-09-29 用户定）

  口径（用户 2026-09-29）：目标机（办公室电脑）**还要继续调试开发** ⇒
    包 = **「可继续开发的可运行系统」**（⛔ 不是客户交付件）⇒ **开发链全带**
    （tests / tools / demo / 验收面 / 计划台账 / 记忆）。
  设计件 = `.workbuddy/work/10-designs/设计-交付包与迁移-20260929.md`（§七/§七之補/§七之二）。
  ⭐⭐ **产包预案**（前置条件 / 一键步骤 / 产包后自检 / 已知坑）＝ **`ops/README.md` §一之四** ——
     ⛔ **出问题先看它，别临场想**（用户 2026-09-29 原话：「**你是否对产包有固定的预案？**」）。

  包内容（⭐ 三类分开，别混）：
    ① **仓**：`git bundle --all`（含全部历史 —— `D18`：git 历史是唯一回退保障）
    ② **非 git 但必需**（被 .gitignore 挡在外面、缺了就"不能继续开发"或"跑不起来"的）：
       · `.codebuddy/memory/**`（工作记忆 —— 本仓的跨会话方式）
       · `.workbuddy/memory/**`（注入档 ＋ journal）
       · `ops/nssm/nssm.exe`（服务注册要它，**已 gitignore**）
       · `artifacts/变异覆盖台账.md` ＋ `artifacts/acc_results.json`（变异台账 ＋ 四态快照）
       · `backups/` 里**最新一份** `*_壳单文件基线.html`（`shell_verify` 的默认基准）
    ③ **库**：`db/init_db.sql`（空库路线 · 建库＋角色）＋ 可选 `db/<db>-<日期>.dump`（`-WithDump` · 只作对照）
    ＋ 随包放一份 `docs/deployment.md`（一页）

  ⛔ **一律不带**：`backend/.venv`（绝对路径，拷过去必崩）· `logs/` · `.workbuddy/scratch` ·
    `backups/交付面-*`（交付面快照）· **`.env`**（真口令不进包 —— 守 `TAIL-88` 的"敏感件 0 命中"）。

  用法（本机 · 普通窗口即可）：
    powershell -ExecutionPolicy Bypass -File ops\pack.ps1
    powershell -ExecutionPolicy Bypass -File ops\pack.ps1 -Out D:\deliver\mtrl-20260929 -WithDump
    powershell -ExecutionPolicy Bypass -File ops\pack.ps1 -DryRun        # 只列会打什么，不落盘
#>
[CmdletBinding()]
param(
    [string] $Out       = '',                                        # 留空 ⇒ D:\deliver\mtrl-<yyyyMMdd-HHmm>
    [string] $RepoRoot  = '',                                        # 留空 ⇒ 本脚本所在目录的上一级
    [string] $PgBin     = 'C:\Program Files\PostgreSQL\16\bin',      # pg_dump.exe 所在
    [string] $DbName    = 'mtrl_workbench',
    [string] $DbUser    = 'mtrl',
    [switch] $WithDump,                                              # 另附一份"本机现状" dump（⛔ 不灌生产，只作对照）
    [switch] $SkipEvidence,                                          # 跳过 0b（刷新权威四态档）—— ⚠️ 只在"刚跑过全套 pytest"时用
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
$RepoRoot = (Resolve-Path $RepoRoot).Path
if (-not $Out) { $Out = Join-Path 'D:\deliver' ('mtrl-' + (Get-Date -Format 'yyyyMMdd-HHmm')) }

function Say($m) { Write-Host $m }
function Step($m) { Write-Host ''; Write-Host ('── ' + $m) }

Say '=== ops/pack.ps1 · 产交付包（可继续开发的可运行系统）==='
Say ('仓   = ' + $RepoRoot)
Say ('输出 = ' + $Out)
Say ('模式 = ' + $(if ($DryRun) { '干跑（不落盘）' } else { '落盘' }))

# ---- 0) 前置两件（⭐ 只打"绿的包"：闸门红 ⇒ 停手，别产出一个跑不起来/说不清的包）----
#   预案（`ops/README.md` §一之四）在这里落成**脚本**（⛔ 不靠"我记得"）：
#   0a 闸门全绿（16 把尺子）· 0b **证据新鲜**（权威四态档必须是刚跑出来的，⛔ 别把上一轮的当真）
Step '0a) 闸门（16 把尺子）'
$py = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'
if (Test-Path $py) {
    & $py -X utf8 (Join-Path $RepoRoot 'tools\oneoff\_run_rulers.py') | Select-Object -Last 3 | ForEach-Object { Say ('   ' + $_) }
    if ($LASTEXITCODE -ne 0) { Say '⛔ 闸门不是全绿 ⇒ 停手（先修尺子，再产包）'; exit 1 }
} else {
    Say ('   ⚠️ 没找到 ' + $py + ' ⇒ 跳过闸门（⚠️ 本机没装 venv：包会缺"能自检"的前提）')
}
if ((-not $SkipEvidence) -and (-not $DryRun) -and (Test-Path $py)) {
    Step '0b) 证据新鲜（全套 pytest ⇒ 写权威四态档）'
    # ⚠️ 机制（`tests/acc_plugin.py`）：**不显式给 `ACC_RESULTS_PATH` 时只写局部档**，
    #    权威档 `artifacts/acc_results.json` **不刷新** ⇒ 包里的四态快照会是**上一轮的**（＝旧证据被当真 ✗，
    #    本仓 `ops/README.md` 记过一次"拿旧证据当真、白追四步"）。
    # ⚠️ `artifacts/` 是 **gitignore** 的 ⇒ 刷新它**不会**弄脏工作区（下面的"未提交"闸不受影响 ✓）。
    $env:ACC_RESULTS_PATH = 'artifacts/acc_results.json'
    Push-Location (Join-Path $RepoRoot 'backend')
    & $py -X utf8 -m pytest -q 2>&1 | Select-Object -Last 3 | ForEach-Object { Say ('   ' + $_) }
    $rc = $LASTEXITCODE
    Pop-Location
    Remove-Item Env:\ACC_RESULTS_PATH -ErrorAction SilentlyContinue
    if ($rc -ne 0) { Say '⛔ 全套 pytest 不是 100% ⇒ 停手（包里的证据必须是真的）'; exit 1 }
    Say '   ✓ 权威四态档已刷新（artifacts\acc_results.json）'
}

# ---- 1) 目录 ----
$dirRepo = Join-Path $Out 'repo'
$dirDb   = Join-Path $Out 'db'
if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $dirRepo, $dirDb | Out-Null }

# ---- 2) 仓：git bundle --all ----
Step '1) 仓（git bundle --all —— 含全部历史）'
$bundle = Join-Path $dirRepo 'mtrl-workbench.bundle'
$head = (& git -C $RepoRoot rev-parse --short HEAD).Trim()
$dirty = (& git -C $RepoRoot status --porcelain | Measure-Object -Line).Lines
if ($dirty -gt 0) { Say ("   ⛔ 工作区有 " + $dirty + " 条未提交 —— 先提交再打包（否则包里缺这批改动）"); exit 1 }
Say ("   HEAD = " + $head + " · 工作区干净 ✓")
if ($DryRun) { Say ('   [干跑] git bundle create ' + $bundle + ' --all') }
else { & git -C $RepoRoot bundle create $bundle --all | Out-Null; Say ('   ✓ ' + (Split-Path -Leaf $bundle)) }

# ---- 3) 非 git 但必需 ----
Step '2) 非 git 但必需（记忆 / nssm.exe / 产物 / 壳基线）'
$extra = @(
    @{ Src = '.codebuddy\memory';                       Dst = '.codebuddy\memory';                    Kind = 'dir'  },
    @{ Src = '.workbuddy\memory';                       Dst = '.workbuddy\memory';                    Kind = 'dir'  },
    @{ Src = 'ops\nssm\nssm.exe';                       Dst = 'ops\nssm\nssm.exe';                     Kind = 'file' },
    @{ Src = 'artifacts\变异覆盖台账.md';                Dst = 'artifacts\变异覆盖台账.md';              Kind = 'file' },
    @{ Src = 'artifacts\acc_results.json';              Dst = 'artifacts\acc_results.json';           Kind = 'file' }
)
foreach ($e in $extra) {
    $s = Join-Path $RepoRoot $e.Src
    $d = Join-Path $Out $e.Dst
    if (-not (Test-Path $s)) { Say ('   ⚠️ 缺：' + $e.Src + '（跳过，⚠️ 记进 MANIFEST 说明）'); continue }
    if ($DryRun) { Say ('   [干跑] ' + $e.Src + ' -> ' + $e.Dst); continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $d) | Out-Null
    if ($e.Kind -eq 'dir') { Copy-Item -Recurse -Force $s $d } else { Copy-Item -Force $s $d }
    Say ('   ✓ ' + $e.Src)
}
$snap = Get-ChildItem (Join-Path $RepoRoot 'backups') -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like '*_壳单文件基线.html' } |
        Sort-Object Name | Select-Object -Last 1
$snapName = ''
if ($snap) {
    $snapName = $snap.Name
    $d = Join-Path $Out ('backups\' + $snap.Name)
    if ($DryRun) { Say ('   [干跑] backups\' + $snap.Name) }
    else { New-Item -ItemType Directory -Force -Path (Join-Path $Out 'backups') | Out-Null; Copy-Item -Force $snap.FullName $d; Say ('   ✓ backups\' + $snap.Name + '（shell_verify 的默认基准）') }
} else {
    # ⚠️ 2026-09-29 修：原先是 `-Filter '*_壳单文件基线.html'` —— **中文通配在 `-Filter` 上不可靠**
    #    （实测**命中 0**，而 `backups/` 里明明有基线）⇒ 改成 `Where-Object -like`（与 `ops/README.md` §一之四 同口径：
    #    ⛔ **中文路径 / 中文通配一律别交给 PowerShell 原语**）。⇒ 顺带**把它报响**（原先只是一句 ⚠️、容易被当噪声跳过）。
    Say '   ⛔ **包里没有壳基线**（`backups\*_壳单文件基线.html` 一个都没匹配到）'
    Say '      ⚠️ 后果：目标机第一次跑 `shell_verify` 会判红「没有基线、要你建基线」⇒ 届时 `--snapshot` 一次即可'
    Say '      ⚠️ 但"没找到"也可能是**匹配/路径写错了**（本仓真踩过：中文通配 `-Filter` 命中 0 ✗）'
}

# ---- 4) 库 ----
Step '3) 库（空库 SQL ＋ 可选现状 dump）'
if ($DryRun) { Say '   [干跑] db\init_db.sql' }
else { Copy-Item -Force (Join-Path $RepoRoot 'ops\init_db.sql') (Join-Path $dirDb 'init_db.sql'); Say '   ✓ db\init_db.sql（空库路线：建库＋角色；⚠️ 里面 <PASSWORD> 要换）' }
if ($WithDump) {
    $pgdump = Join-Path $PgBin 'pg_dump.exe'
    if (-not (Test-Path $pgdump)) { Say ('   ⛔ 找不到 ' + $pgdump + ' ⇒ 跳过着一条（用 -PgBin 指路）') }
    else {
        $dump = Join-Path $dirDb ($DbName + '-' + (Get-Date -Format 'yyyyMMdd') + '.dump')
        if ($DryRun) { Say ('   [干跑] pg_dump -Fc ' + $dump) }
        else {
            $env:PGPASSWORD = Read-Host ('   输入 PG 口令（用户 ' + $DbUser + '；⚠️ 只为本次 dump，不落盘）') -AsSecureString |
                              ConvertFrom-SecureString -AsPlainText
            & $pgdump -U $DbUser -d $DbName -Fc -f $dump
            Remove-Item Env:\PGPASSWORD
            Say ('   ✓ ' + (Split-Path -Leaf $dump) + '（⚠️ 只作对照/回滚，⛔ 不灌生产）')
        }
    }
}

# ---- 5) 一页说明 ＋ 清单 ＋ 校验和 ----
Step '4) 一页说明 ＋ MANIFEST ＋ SHA256SUMS'
if (-not $DryRun) {
    Copy-Item -Force (Join-Path $RepoRoot 'docs\deployment.md') (Join-Path $Out '部署-落地说明.md') -ErrorAction SilentlyContinue
    # ⭐ **MANIFEST.txt**（2026-09-29 补：上面标题里一直写着 MANIFEST，其实**没有任何一行代码写它** ✗）——
    #    它是"**这个包是什么 / 有什么 / 缺什么**"的**落纸**：产包预案里"件清单 ＋ 壳基线在不在"必须有据可查，
    #    ⛔ 不靠人回忆（用户 2026-09-29 问的就是这个：产包有没有固定预案）。
    $mf = @()
    $mf += 'M8 交付包 · MANIFEST（可继续开发的可运行系统 · 详见 ops/README.md §一之四 的产包预案）'
    $mf += ('产出时间 : ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
    $mf += ('HEAD     : ' + $head + '（工作区干净 —— 产包闸已挡过未提交）')
    $mf += '仓       : repo\mtrl-workbench.bundle（git bundle --all ⇒ 含全部历史，D18 的回退保障）'
    $mf += '非 git 件: .codebuddy\memory\** · .workbuddy\memory\** · ops\nssm\nssm.exe · artifacts\*'
    $mf += ('壳基线   : ' + $(if ($snapName) { 'backups\' + $snapName } else { '⛔ 缺！见产包日志的解释（目标机 --snapshot 一次即可）' }))
    $mf += ('库       : db\init_db.sql（空库路线；⚠️ 里面 <PASSWORD> 到目标机要换）' + $(if ($WithDump) { ' ＋ db\*.dump（⚠️ 只作对照，⛔ 不灌生产）' } else { '' }))
    $mf += '⛔ 一律不带: backend\.venv · logs\ · .workbuddy\scratch · backups\交付面-* · .env（真口令不进包，守 TAIL-88）'
    $mf += '落地说明 : 部署-落地说明.md（= docs\deployment.md）'
    $mf += '校验     : SHA256SUMS.txt 覆盖本目录**全部文件**（本件也在内）—— 目标机脚本先校它'
    [IO.File]::WriteAllText((Join-Path $Out 'MANIFEST.txt'), ($mf -join "`r`n") + "`r`n", (New-Object Text.UTF8Encoding($false)))
    Say '   ✓ MANIFEST.txt（HEAD / 时间 / 件清单 / 壳基线状态 / ⛔ 排除项）'
    $files = Get-ChildItem $Out -Recurse -File | Where-Object { $_.Name -ne 'SHA256SUMS.txt' }
    $lines = $files | ForEach-Object { (Get-FileHash $_.FullName -Algorithm SHA256).Hash + '  ' + $_.FullName.Substring($Out.Length + 1) }
    [IO.File]::WriteAllText((Join-Path $Out 'SHA256SUMS.txt'), ($lines -join "`r`n") + "`r`n", (New-Object Text.UTF8Encoding($false)))
    Say ('   ✓ SHA256SUMS.txt（' + $files.Count + ' 件）')
    # ⛔ 敏感件自检：包里出现这些名字就报出来（守 TAIL-88 的口径）
    $bad = $files | Where-Object { $_.Name -match '^\.env$|cookie|password|secret' }
    if ($bad) { Say ('   ⛔ 包里有疑似敏感件，请人工确认：' + (($bad | ForEach-Object { $_.Name }) -join ', ')) }
    else { Say '   ✓ 敏感件自检：0 命中' }
}
Say ''
Say ('=== 完成 · 包在 ' + $Out + ' ===')
Say '下一步：把整个目录拷到目标机 ⇒ 在目标机跑 ops\deploy_restore.ps1 -Pack <该目录> -Mode empty ⇒ 再跑 ops\selfcheck.ps1'
