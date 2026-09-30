#  ops 下 .ps1 的**语法闸**（2026-09-29 立 · `TAIL-191`）
#
#  为什么要有它：改完 `ops/*.ps1`（本次改的是 `pack.ps1` / `deploy_restore.ps1`）**没有东西替我验语法** ——
#  离线有 pytest、Python 有 `syntax_audit.py`，而 **PowerShell 一个尺子都没有** ⇒
#  只能等真跑那一刻才炸（而那一刻正是"要去办公室产包"的时候 ✗）。
#  ⚠️ 它管两半：**① 语法**（能不能被解析）＋ **② 仓内路径字面量存不存在**（⭐ 2026-09-29 加，见下面段②）。
#     ⛔ 仍不管**语义 / 参数** —— 那半靠 `-DryRun` 真跑（两者互补：段②查"写死的路径在不在"，`-DryRun` 查"流程对不对"）。
#
#  用法（工程根）：
#    powershell -NoProfile -ExecutionPolicy Bypass -File tools\oneoff\_ps_parse_check.ps1 -Files ops\pack.ps1,ops\deploy_restore.ps1,ops\selfcheck.ps1,ops\server_ctl.ps1
#    不给 -Files ⇒ 默认查 `ops\*.ps1` 全量。
[CmdletBinding()]
param(
    [string[]] $Files = @()
)

$ErrorActionPreference = 'Stop'
# ⚠️ 2026-09-29：本件在 `tools/oneoff/` 下 ⇒ 仓根 = `$PSScriptRoot` 往上**两级**
#    （`$PSScriptRoot` = tools\oneoff ⇒ 父 = tools ⇒ 父 = 仓根）。
#    ⛔ 别抄"往上两级 = 仓根"这个写法去懂别的机器 —— 那对 `ops\*.ps1`（上一级）**正好相反** ✗；
#    本仓踩过同一类：`tools/oneoff/_ps_bom.py` 从 `tools/` 搬下来后根算错一格 ⇒ 永远 "no .ps1 found"。
#    ⭐ 提到 `if` 外面：下面段② 也要用 `$root`（原先给了 `-Files` 时它根本没定义 ⇒ 段② 会瞎）。
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Files -or $Files.Count -eq 0) {
    $Files = @(Get-ChildItem (Join-Path $root 'ops') -File | Where-Object { $_.Extension -eq '.ps1' } |
        ForEach-Object { $_.FullName })
    if (-not $Files -or $Files.Count -eq 0) { Write-Host ('⛔ 在 ' + (Join-Path $root 'ops') + ' 下一份 .ps1 都没找到（⚠️ 先确认根算对了没）'); exit 1 }
}

$bad = 0
foreach ($f in $Files) {
    if (-not (Test-Path $f)) { Write-Host ('⛔ 找不到：' + $f); $bad++; continue }
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $f).Path, [ref]$null, [ref]$errs)
    if ($errs -and $errs.Count -gt 0) {
        $bad++
        Write-Host ('⛔ ' + $f)
        $errs | ForEach-Object { Write-Host ('     ' + $_.Message) }
    } else {
        Write-Host ('✅ ' + (Split-Path -Leaf $f) + ' 语法 ✓')
    }
}

# ---- ② 仓内路径字面量存在性（⭐ 2026-09-29 加 · 被 `pack.ps1 -DryRun` 抓到的那处真缺陷逼出来的）----
#  为什么：`pack.ps1` 的壳基线**源路径**原写成裸 `Join-Path $RepoRoot 'backups'`（真身 = `.workbuddy\backups`）
#  ⇒ 5 份基线**一份都进不了包**，**而报错说的是"没找到"** ⇒ ⛔ **把"路径写错"伪装成"真没有"**（人就不查了）。
#  ⇒ 把"`Join-Path $RepoRoot '<字面量>'` 里的字面量必须**真的存在**"做成**机器判据**（人眼一定会漏）。
#  口径（⛔ 别自己另定一套）：
#    · 只查 `ops/*.ps1`（产包 / 落地当天**照抄**的那批）；⛔ **不查** `tools/oneoff/`（历史脚本，路径过期是**正常的**）；
#    · 只认**单引号**形态（双引号里可能带 `$变量` 插值 ⇒ 判了会假红）；
#    · `$SkipPaths` = **脚本自己会创建**的路径（新机 / 目标机上"不存在"是**对的**）⇒ ⛔ 别往里加别的。
$SkipPaths = @('backend\.venv', 'logs')
Write-Host ''
Write-Host '② 仓内路径字面量（`Join-Path $RepoRoot ''…''` ⇒ 必须真的存在）'
$pathBad = 0
foreach ($f in $Files) {
    if (-not (Test-Path -LiteralPath $f)) { continue }
    # ⚠️⚠️ 先**剥注释**再扫（2026-09-29 现场踩到）：不剥 ⇒ **解释这个缺陷的那句注释本身**会被当成缺陷判红 ✗
    #    （本仓真发生过：注释里写着 `Join-Path $RepoRoot 'backups'` 这个**反例**作说明 ⇒ 判据指着它喊）。
    #    ⭐ 通则：**判据扫"源码"前先剥注释** —— 注释是写给人看的，规则只该管**会执行的那部分**。
    $txt = Get-Content -LiteralPath $f -Raw
    $txt = [regex]::Replace($txt, '(?s)<#.*?#>', '')
    $txt = [regex]::Replace($txt, '(?m)#.*$', '')
    foreach ($x in [regex]::Matches($txt, 'Join-Path\s+\$RepoRoot\s+''([^'']+)''')) {
        $rel = $x.Groups[1].Value
        $skip = $false
        foreach ($s in $SkipPaths) { if ($rel -eq $s -or $rel.StartsWith($s + '\')) { $skip = $true } }
        if ($skip) { continue }
        if (Test-Path -LiteralPath (Join-Path $root $rel)) {
            Write-Host ('   ✅ ' + (Split-Path -Leaf $f) + '  ' + $rel)
        } else {
            $pathBad++
            Write-Host ('   ⛔ ' + (Split-Path -Leaf $f) + '  ' + $rel + '  ⇒ **仓里没这个路径**（写错了？还是"将要新建"？）')
        }
    }
}

# ---- ③ 交付面快照那 2 件在不在（⭐ 2026-09-30 加 · 用户指示③「包内留一份快照」）----
#  为什么：`pack.ps1` 步骤 2b 要取 2 件（《材料科业务全流程说明书.md》＋ `PRD\验收\验收基线.json`）——
#    它们**在不在**只有真跑到那一步才知道，而"真跑"那一刻 = **去办公室前一天** ⇒
#    到期才发现"云没同步下来 / 被改名"就晚了（同族教训：2026-09-29 壳基线路径写错、到期才发现）。
#  口径：**交付面根只从 `.env` 的 `PRD_ACCEPTANCE_BASELINE` 上溯两级拿**（＝ `audit_common.delivery_root()`
#    **同一个主人** ⇒ ⛔ 本件不另写死一个绝对路径）；拿不到 ⇒ **显式报黄**（⛔ 不静默跳过 —— 本仓栽过两次的同一类错）。
$envFile = Join-Path $root '.env'
$faceRoot = ''
if (Test-Path -LiteralPath $envFile) {
    # ⚠️ 两处踩过、别改回去（2026-09-30 现场）：
    #   ① **必须 `-Encoding UTF8`** —— `.env` 是 UTF-8，而 PS 5.1 的 `Get-Content` 默认按**本地代码页(GBK)** 读
    #      ⇒ 中文路径整段**乱码** ⇒ `Test-Path` 全判假 ⇒ ⛔ 把"读错了"伪装成"交付面里真没有"（最贵那类假红）。
    #   ② **上溯三级**（⛔ 不是两级）—— `Split-Path -Parent` 对**文件**先取"所在目录"（＝一级）
    #      ⇒「文件 → 验收 → PRD → 交付面根」＝ 三次；⚠️ Python 那边 `Path.parents[2]` 是**两级**（语义相反），
    #      照 Python 抄会**少一级** ⇒ 拿到的"根"其实是 `…\PRD` ✗（本次就是这么错的）。
    foreach ($l in (Get-Content -LiteralPath $envFile -Encoding UTF8)) {
        if ($l.Trim().StartsWith('PRD_ACCEPTANCE_BASELINE=')) {
            $p = $l.Split('=', 2)[1].Trim()
            if ($p) { $faceRoot = [IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($p))) }
        }
    }
}
Write-Host ''
Write-Host '③ 交付面快照（`pack.ps1` 步骤 2b 要取的 2 件 · 用户 2026-09-30 指示）'
$faceBad = 0
if (-not $faceRoot) {
    Write-Host '   ⚠️ 拿不到交付面根（仓根 `.env` 里没有 `PRD_ACCEPTANCE_BASELINE`）⇒ **跳过**（⚠️ 跳过 ≠ 通过）'
} else {
    Write-Host ('   交付面根 = ' + $faceRoot)
    foreach ($rel in @('材料科业务全流程说明书.md', 'PRD\验收\验收基线.json')) {
        if (Test-Path -LiteralPath (Join-Path $faceRoot $rel)) {
            Write-Host ('   ✅ ' + $rel)
        } else {
            $faceBad++
            Write-Host ('   ⛔ ' + $rel + '  ⇒ 交付面里没这一件（云没同步下来？被改名？）⇒ 包里将缺它')
        }
    }
}

Write-Host ''
if ($bad -or $pathBad -or $faceBad) {
    Write-Host ('=== 语法不过 ' + $bad + ' 份 · 仓内路径不存在 ' + $pathBad + ' 处 · 交付面快照缺 ' + $faceBad + ' 件 ===')
    exit 1
}
Write-Host '=== 全部语法 ✓ · 仓内路径字面量全在 ✓ · 交付面快照在位 ✓ ==='
exit 0
