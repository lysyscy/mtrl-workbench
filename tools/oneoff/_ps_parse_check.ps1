#  ops 下 .ps1 的**语法闸**（2026-09-29 立 · `TAIL-191`）
#
#  为什么要有它：改完 `ops/*.ps1`（本次改的是 `pack.ps1` / `deploy_restore.ps1`）**没有东西替我验语法** ——
#  离线有 pytest、Python 有 `syntax_audit.py`，而 **PowerShell 一个尺子都没有** ⇒
#  只能等真跑那一刻才炸（而那一刻正是"要去办公室产包"的时候 ✗）。
#  ⚠️ 它**只管语法**（能不能被解析），⛔ 不管语义 / 参数 / 路径 —— 那两半靠 `-DryRun` 真跑。
#
#  用法（工程根）：
#    powershell -NoProfile -ExecutionPolicy Bypass -File tools\oneoff\_ps_parse_check.ps1 -Files ops\pack.ps1,ops\deploy_restore.ps1,ops\selfcheck.ps1,ops\server_ctl.ps1
#    不给 -Files ⇒ 默认查 `ops\*.ps1` 全量。
[CmdletBinding()]
param(
    [string[]] $Files = @()
)

$ErrorActionPreference = 'Stop'
if (-not $Files -or $Files.Count -eq 0) {
    # ⚠️ 2026-09-29：本件在 `tools/oneoff/` 下 ⇒ 仓根 = `$PSScriptRoot` 往上**两级**
    #    （`$PSScriptRoot` = tools\oneoff ⇒ 父 = tools ⇒ 父 = 仓根）。
    #    ⛔ 别抄"往上两级 = 仓根"这个写法去懂别的机器 —— 那对 `ops\*.ps1`（上一级）**正好相反** ✗；
    #    本仓踩过同一类：`tools/oneoff/_ps_bom.py` 从 `tools/` 搬下来后根算错一格 ⇒ 永远 "no .ps1 found"。
    $root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
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

if ($bad) { Write-Host ('=== 有 ' + $bad + ' 个文件语法不过 ==='); exit 1 }
Write-Host '=== 全部语法 ✓ ==='
exit 0
