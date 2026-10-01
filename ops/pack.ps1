<#
  ops/pack.ps1 —— **在本机产"交付包"**（M8 · `TAIL-188` · 2026-09-29 用户定）

  口径（用户 2026-09-29）：目标机（办公室电脑）**还要继续调试开发** ⇒
    包 = **「可继续开发的可运行系统」**（⛔ 不是客户交付件）⇒ **开发链全带**
    （tests / tools / demo / 验收面 / 计划台账 / 记忆）。
  设计件 = `.codebuddy/work/10-designs/设计-交付包与迁移-20260929.md`（§七/§七之補/§七之二）。
  ⭐⭐ **产包预案**（前置条件 / 一键步骤 / 产包后自检 / 已知坑）＝ **`ops/README.md` §一之四** ——
     ⛔ **出问题先看它，别临场想**（用户 2026-09-29 原话：「**你是否对产包有固定的预案？**」）。

  包内容（⭐ 三类分开，别混）：
    ① **仓**：`git bundle --all`（含全部历史 —— `D18`：git 历史是唯一回退保障）
    ② **非 git 但必需**（被 .gitignore 挡在外面、缺了就"不能继续开发"或"跑不起来"的）：
       · `.codebuddy/memory/**`（工作记忆 —— 本仓的跨会话方式：注入档 ＋ 分册 ＋ **逐日日志** `journal/`）
         ⭐ 2026-10-01（`TAIL-204` 第 2 步）起**只剩这一个记忆家**（原 `.workbuddy/memory/**` 已并入）
       · `ops/nssm/nssm.exe`（服务注册要它，**已 gitignore**）
       · `artifacts/变异覆盖台账.md` ＋ `artifacts/acc_results.json`（变异台账 ＋ 四态快照）
       · **`.codebuddy/backups/`** 里**最新一份** `*_壳单文件基线.html`（`shell_verify` 的默认基准）
         ⚠️ **2026-09-29 干跑实测抓出**：这里原写成**顶层** `backups/` —— 仓里**没有**那个目录
         （真身 = `.codebuddy\backups\`）⇒ **5 份基线一份都进不了包**，而脚本还会说"没找到"
         ⇒ ⛔ 把**路径写错**伪装成**真没有**（详见下面第 2 步的注释）
       ③ **库**：`db/init_db.sql`（空库路线 · 建库＋角色）＋ 可选 `db/<db>-<日期>.dump`（`-WithDump` · 只作对照）
       ＋ 随包放一份 `ops/deployment.md`（一页）
       ④ ⭐ **交付面快照 · 只 2 件**（⭐ 用户 2026-09-30 指示 · 见 §20 指示③）：
          `face\材料科业务全流程说明书.md` ＋ `face\PRD\验收\验收基线.json`
          ⇒ 目标机 `.env` 的 `PRD_ACCEPTANCE_BASELINE` 可**指包内**这份（⚠️ 口径：**云那份仍是真源**，
          连得上云就改回 —— 免得「两处副本必漂」）。
          ⛔ **交付面其余件一律不进包**（`demo\` · `PRD\` 余件 · `PRD素材包-*` · 交付面根 4 个 md）——
          交付面是 **WPS 云同步树**（2026-09-30 订正）：目标机只要 WPS 同步了它**本来就在**，
          要跑那套尺子只需**核路径 ＋ 在 `.env` 配 `PRD_ACCEPTANCE_BASELINE`**（≈零成本）；
          ⇒ ⛔ 别整份拷（实测 **1404 件 / 42.27 MB**）。已做：参数 `$FaceRoot` 与 `-SkipFace`。


       ⛔ **一律不带**：`backend/.venv`（绝对路径，拷过去必崩）· `logs/` · `.workbuddy/scratch` ·
       `.codebuddy/backups/交付面-*`（交付面快照）· **`.env`**（真口令不进包 —— 守 `TAIL-88` 的"敏感件 0 命中"）。

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
    [string] $FaceRoot  = '',                                        # 交付面根（⭐ 只用来取 ④ 那 2 件快照；留空 ⇒ 用本机默认路径）
    [switch] $SkipFace,                                              # 跳过 ④ 交付面快照（⇒ 包里将没有那 2 件）
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
#: ⭐ 2026-09-29：**"该带的件"缺了几项** —— **干跑时它非零 ⇒ `exit 1`**（见末尾）。
#:   为什么要有它：原先"缺件"只打印一行 ⛔、**rc 仍是 0** ⇒ 照抄"干跑"的人（或自动化）会当它**通过** ⇒
#:   今天那次缺陷（壳基线路径写错）就是靠**人读输出**才发现的，机器判不出来 ✗。
$packProblems = 0

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
    # ⭐ 2026-10-01（`TAIL-204` 第 2 步）：两个记忆家已并成一个 ⇒ ⛔ 原第二条 `.workbuddy\memory` 已删
    #    （它当时被机械改名成 `.codebuddy\memory` ⇒ 与上面这条**重复**）
    @{ Src = '.codebuddy\memory';                       Dst = '.codebuddy\memory';                    Kind = 'dir'  },
    @{ Src = 'ops\nssm\nssm.exe';                       Dst = 'ops\nssm\nssm.exe';                     Kind = 'file' },
    @{ Src = 'artifacts\变异覆盖台账.md';                Dst = 'artifacts\变异覆盖台账.md';              Kind = 'file' },
    @{ Src = 'artifacts\acc_results.json';              Dst = 'artifacts\acc_results.json';           Kind = 'file' }
)
foreach ($e in $extra) {
    $s = Join-Path $RepoRoot $e.Src
    $d = Join-Path $Out $e.Dst
    if (-not (Test-Path $s)) { Say ('   ⛔ 缺：' + $e.Src + '（跳过 ⇒ 已记进"该带的件缺 N 项"；见末尾）'); $packProblems++; continue }
    if ($DryRun) { Say ('   [干跑] ' + $e.Src + ' -> ' + $e.Dst); continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $d) | Out-Null
    if ($e.Kind -eq 'dir') { Copy-Item -Recurse -Force $s $d } else { Copy-Item -Force $s $d }
    Say ('   ✓ ' + $e.Src)
}
# ⚠️⚠️ 2026-09-29 修（**干跑 `-DryRun` 当场抓出**）：源路径原写成 `Join-Path $RepoRoot 'backups'` ——
#    而仓里**根本没有顶层 `backups/`**（真身 = `.codebuddy\backups\`；**唯一主人** = `tools/audit/shell_verify.py`
#    的 `BACKUPS = REPO / ".codebuddy" / "backups"`）⇒ **5 份基线一份都匹配不到**，
#    而 else 分支还会把它说成"包里没有壳基线" ⇒ ⛔ **把"路径写错"伪装成"真没有"**（最贵的一类：人就不查了）。
# ⭐ 同批把**包内布局**改成与**仓内相对路径一致**（`.codebuddy\backups\`）—— 这样 `deploy_restore.ps1`
#    那张"放回列表"才**左右对称**（原先五项里**只有这一项**不对称 ⇒ 那正是错的来源）。
# ⚠️ 另一条同源坑（别删）：中文通配交给 `-Filter` 会**命中 0** ⇒ 已改 `Where-Object -like`（见 `ops/README.md` §一之四 ⑤）。
$snapDir = Join-Path $RepoRoot '.codebuddy\backups'
$snap = Get-ChildItem $snapDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like '*_壳单文件基线.html' } |
        Sort-Object Name | Select-Object -Last 1
$snapName = ''
if ($snap) {
    $snapName = $snap.Name
    $d = Join-Path $Out ('.codebuddy\backups\' + $snap.Name)
    if ($DryRun) { Say ('   [干跑] .codebuddy\backups\' + $snap.Name) }
    else { New-Item -ItemType Directory -Force -Path (Join-Path $Out '.codebuddy\backups') | Out-Null; Copy-Item -Force $snap.FullName $d; Say ('   ✓ .codebuddy\backups\' + $snap.Name + '（shell_verify 的默认基准）') }
} else {
    # ⭐ 两类**必须分开报**（2026-09-29）：原先混成一句"一个都没匹配到" ⇒ 分不清是**真没有**还是**路径写错**。
    #    ⚠️ 同族教训 = `TAIL-190`（同步回执把两类待人工混成一个数 ⇒ 用户看到空卡，只能靠猜）。
    Say '   ⛔ **包里没有壳基线**'
    if (-not (Test-Path $snapDir)) {
        Say ('      真因① = **目录都不存在**：' + $snapDir)
        Say '        ⚠️ 这多半是**路径写错**（真身必须是仓内 `.codebuddy\backups\`）⇒ 先查这个，⛔ 别急着去 --snapshot'
    } else {
        $loose = @(Get-ChildItem $snapDir -File -ErrorAction SilentlyContinue).Count
        Say ('      真因② = 目录在（' + $loose + ' 个散件）但**没有** `*_壳单文件基线.html` 匹配')
        Say '        ⇒ 先复核壳，再 `python tools/audit/shell_verify.py --snapshot` 建一份'
    }
    Say '      ⚠️ 后果：目标机第一次跑 `shell_verify` 会判红「没有基线、要你建基线」⇒ 届时 `--snapshot` 一次即可'
    $packProblems++
}

# ---- 3b) 交付面快照（⭐ 用户 2026-09-30 指示 · ⛔ 只 2 件，别整份拷）----
#  为什么要它：交付面是 **WPS 云同步树** ⇒ 目标机**多半本来就有**（2026-09-30 订正）；
#    但**云可能没同步 / 云那份会漂** ⇒ 用户点名留**一份包内快照**（`.env` 可指包内）。
#  ⚠️ 两条教训照抄本文件既有写法（别重踩）：
#    · **中文一律走 `.NET` / `-like` / Python**（`-Filter` 会命中 0）；
#    · 缺件报**两类真因**（目录不存在 = 多半路径写错 / 文件不存在 = 真缺），⛔ 别混成一句"没找到"
#      （那正是 2026-09-29「5 份壳基线一份都进不了包」的成因）。
Step '2b) 交付面快照（《说明书》＋ 验收基线 · 用户 2026-09-30 指示）'
$faceDone = 0
if ($SkipFace) {
    Say '   ⏭ -SkipFace ⇒ 跳过（⚠️ 包里将没有那 2 件 ⇒ 目标机只能靠云那份）'
} else {
    # ⚠️ 本机默认路径写在这里（⛔ 不写进 param 默认值 —— 目标机/换机时 `-FaceRoot` 可覆盖）
    if (-not $FaceRoot) { $FaceRoot = 'D:\工作\AI\PRD编写夹 - Workbuddy专用' }
    Say ('   源 = ' + $FaceRoot)
    foreach ($rel in @('材料科业务全流程说明书.md', 'PRD\验收\验收基线.json')) {
        $s = Join-Path $FaceRoot $rel
        if (-not (Test-Path -LiteralPath $s)) {
            $packProblems++
            Say ('   ⛔ 缺：' + $rel)
            if (-not (Test-Path -LiteralPath $FaceRoot)) {
                Say ('      真因① = **交付面根都不存在**：' + $FaceRoot + '（WPS 云没同步下来？还是路径写错？）')
            } else {
                Say ('      真因② = 交付面根在，但**没有这一件**（云同步缺件 / 被改名？）')
            }
            Say '      ⚠️ 后果：目标机 `.env` 的 PRD_ACCEPTANCE_BASELINE 只能指云那份 ⇒ 云没同步到就断'
            continue
        }
        $d = Join-Path $Out ('face\' + $rel)
        if ($DryRun) { Say ('   [干跑] face\' + $rel); continue }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $d) | Out-Null
        Copy-Item -Force -LiteralPath $s -Destination $d
        $faceDone++
        Say ('   ✓ face\' + $rel)
    }
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
    Copy-Item -Force (Join-Path $RepoRoot 'ops\deployment.md') (Join-Path $Out '部署-落地说明.md') -ErrorAction SilentlyContinue
    # ⭐ **MANIFEST.txt**（2026-09-29 补：上面标题里一直写着 MANIFEST，其实**没有任何一行代码写它** ✗）——
    #    它是"**这个包是什么 / 有什么 / 缺什么**"的**落纸**：产包预案里"件清单 ＋ 壳基线在不在"必须有据可查，
    #    ⛔ 不靠人回忆（用户 2026-09-29 问的就是这个：产包有没有固定预案）。
    $mf = @()
    $mf += 'M8 交付包 · MANIFEST（可继续开发的可运行系统 · 详见 ops/README.md §一之四 的产包预案）'
    $mf += ('产出时间 : ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
    $mf += ('HEAD     : ' + $head + '（工作区干净 —— 产包闸已挡过未提交）')
    $mf += '仓       : repo\mtrl-workbench.bundle（git bundle --all ⇒ 含全部历史，D18 的回退保障）'
    $mf += '非 git 件: .codebuddy\memory\**（注入档＋分册＋逐日日志）· ops\nssm\nssm.exe · artifacts\*'
    # ⭐ 2026-09-30（用户指示③）：交付面**只带 2 件快照** —— MANIFEST 必须写明，⛔ 别让人以为整份都在包里
    $mf += ('交付面快照: ' + $(if ($faceDone -ge 2) { 'face\材料科业务全流程说明书.md ＋ face\PRD\验收\验收基线.json（⭐ .env 的 PRD_ACCEPTANCE_BASELINE 可指包内这份；⚠️ 云那份仍是真源）' } elseif ($faceDone -eq 1) { '⚠️ 只带了 1 件（另 1 件缺 · 见产包日志）' } else { '⛔ 一件都没带（-SkipFace 或交付面缺件；见产包日志）⇒ 交付面只能靠 WPS 云同步' }))
    $mf += '⛔ 交付面其余件不进包: demo\ · PRD\ 余件 · PRD素材包-* · 交付面根 4 个 md（= WPS 云同步树 ⇒ 目标机同步即有）'
    $mf += ('壳基线   : ' + $(if ($snapName) { '.codebuddy\backups\' + $snapName } else { '⛔ 缺！见产包日志里"真因①/②"那两行（目标机 --snapshot 一次即可）' }))
    $mf += ('库       : db\init_db.sql（空库路线；⚠️ 里面 <PASSWORD> 到目标机要换）' + $(if ($WithDump) { ' ＋ db\*.dump（⚠️ 只作对照，⛔ 不灌生产）' } else { '' }))
    $mf += '⛔ 一律不带: backend\.venv · logs\ · .workbuddy\scratch · .codebuddy\backups\交付面-* · .env（真口令不进包，守 TAIL-88）'
    $mf += '落地说明 : 部署-落地说明.md（= ops\deployment.md）'
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
if ($packProblems -gt 0) {
    Say ('⛔ 该带的件缺 ' + $packProblems + ' 项（上面逐项写明了是哪一项、以及后果）')
    if ($DryRun) {
        Say '⭐ **干跑通过的含义 = "该带的都带得上"** ⇒ 现在 rc=1'
        Say '   （⛔ 别把干跑当"放宽版"：它是产包那天**唯一能机器判**的一步 ⇒ 它绿了，那天照抄才有底）'
        exit 1
    }
    Say '⚠️ 正式产包**放行**（MANIFEST 里已如实写明缺哪项）—— 但先想清楚：目标机会不会因此少东西'
}
Say ('=== 完成 · 包在 ' + $Out + ' ===')
Say '下一步：把整个目录拷到目标机 ⇒ 在目标机跑 ops\deploy_restore.ps1 -Pack <该目录> -Mode empty ⇒ 再跑 ops\selfcheck.ps1'
