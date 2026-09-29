# ops/selfcheck.ps1 —— 目标机自检（M8 ④「交接口径与自检命令」的正文 · TAIL-188）
#
# 设计要点：⭐ 刻意写成「不依赖交付面」的 —— 交付面（WPS 那个文件夹）不进包、目标机不装，
#   所以四态报表（acc_report.py · 641 那个数）与 ui_parity / doc_audit --ui 在目标机跑不了（＝已知代价）。
#   这里做的是「这系统自己能不能转」的五项，⛔ 不是验收：
#     ① 服务在跑（mtrl-workbench-server = Running / Automatic）
#     ② http://127.0.0.1:8000/app 返回 200
#     ③ 库连得上、表建齐（走**后端自己的配置**去连 —— 口径只认一份）
#     ④ 两份运行时模板在，且 SHA256 对得上（防回退/拷贝损坏 —— 历史踩过）
#     ⑤ 三个历史导入域 ＋ 库存单据端点在（从 /openapi.json 里找；拿不到就照实说「跳过 + 原因」）
#
# 用法（目标机 · 普通窗口即可）：
#   powershell -ExecutionPolicy Bypass -File ops\selfcheck.ps1
#   powershell -ExecutionPolicy Bypass -File ops\selfcheck.ps1 -Base http://127.0.0.1:8000 -RepoRoot D:\dev\mtrl-workbench
# 退出码：0 = 五项全过（⚠️ 有「跳过」也照实打印）；1 = 有 ⛔。
#
# ⚠️⚠️ 本文件必须是 **UTF-8 with BOM**（PS 5.1 读无 BOM 的 UTF-8 会按 ANSI 解 ⇒ 中文全乱 ⇒ 解析崩 —— 2026-09-29 实测踩过）。
# ⚠️ 也⛔ 别用 <# #> 块注释（本机实测解析报 Unexpected attribute）；一律用 # 行注释。

[CmdletBinding()]
param(
    [string] $Base        = 'http://127.0.0.1:8000',
    [string] $RepoRoot    = '',
    [string] $ServiceName = 'mtrl-workbench-server'
)

$ErrorActionPreference = 'Continue'
if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
$script:fail = 0
function Ok($m)   { Write-Host ('   ✅ ' + $m) }
function Bad($m)  { Write-Host ('   ⛔ ' + $m); $script:fail++ }
function Skip($m) { Write-Host ('   ⚠️ ' + $m + '（跳过 —— ⛔ 但要知道这笔账）') }

Write-Host '=== ops/selfcheck.ps1 · 目标机自检（⛔ 不是验收；验收要交付面，那不在包内）==='
Write-Host ('仓 = ' + $RepoRoot + ' · 站 = ' + $Base)

# ---- ① 服务 ----
Write-Host ''
Write-Host '① 服务'
$s = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $s) { Bad ('服务 ' + $ServiceName + ' 不存在 —— 跑 ops\nssm_install.ps1') }
else {
    if ($s.Status -eq 'Running') { Ok '服务 Running' } else { Bad ('服务状态 = ' + $s.Status) }
    if ($s.StartType -eq 'Automatic') { Ok '开机自启 Automatic' } else { Bad ('StartType = ' + $s.StartType + '（重启机器后不会自己起来）') }
}

# ---- ② /app ----
Write-Host ''
Write-Host '② 页面'
try {
    $r = Invoke-WebRequest -Uri ($Base + '/app') -UseBasicParsing -TimeoutSec 15
    if ($r.StatusCode -eq 200) { Ok ('/app 200（' + $r.RawContentLength + ' 字节）') } else { Bad ('/app 返回 ' + $r.StatusCode) }
} catch { Bad ('/app 探活失败：' + $_.Exception.Message) }

# ---- ③ 库（走后端自己的配置 —— 口径只认一份）----
Write-Host ''
Write-Host '③ 库'
$py = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { Skip '没有 backend\.venv\Scripts\python.exe' }
else {
    # ⚠️⚠️ **别用 `python -c <串>` 传含引号的代码**：PowerShell 5.1 把它交给原生 exe 时会把**双引号弄坏**
    #    ⇒ Python 收到残串、报 `'(' was never closed`（2026-09-29 实测踩过两轮）⇒ 改成**落一个临时 .py 再跑**，
    #    用 .NET 写文件 ⇒ 完全绕开命令行的引号规则。
    $code = @'
from app.core.db import session_scope
from sqlalchemy import text
ctx = session_scope()
s = ctx.__enter__()
print(s.execute(text("select count(*) from information_schema.tables where table_schema = current_schema()")).scalar())
'@
    $tmp = Join-Path $env:TEMP 'mtrl_selfcheck_db.py'
    [IO.File]::WriteAllText($tmp, $code, (New-Object Text.UTF8Encoding($false)))
    # ⚠️ 必须**在 backend 里**跑：`app` 包在那儿（⛔ 从仓根跑 ⇒ ModuleNotFoundError: No module named 'app'）
    Push-Location (Join-Path $RepoRoot 'backend')
    $out = (& $py $tmp 2>&1 | Select-Object -Last 1)
    Pop-Location
    if ($LASTEXITCODE -eq 0 -and $out -match '^\d+$' -and [int]$out -ge 10) { Ok ('库连得上 · 当前 schema 表 ' + $out + ' 张') }
    else { Bad ('库自检失败（后端自己的配置连不上或缺表）：' + ($out -join ' ')) }
}

# ---- ④ 运行时模板 ＋ SHA256 ----
Write-Host ''
Write-Host '④ 运行时模板'
$want = @{
    '模板_库存单据明细表.xlsx' = '6803d01b1b0793f02543b281e737f9de42c9b955b7f45da0d55547e15b5e6bd2'
    '模板_收发结存表.xlsx'     = 'eab1c626dce769ac979408564cbffa52a8ca3bc42d80c76c40e0335f8c46d323'
}
$tplDir = Join-Path $RepoRoot 'backend\app\resources\templates'
foreach ($k in $want.Keys) {
    $p = Join-Path $tplDir $k
    if (-not (Test-Path $p)) { Bad ('缺模板 ' + $k + '（⛔ 报表导出会失败 —— 设计上就会显式报错）'); continue }
    $h = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
    if ($h -eq $want[$k]) { Ok ($k + ' SHA256 ✓') } else { Bad ($k + ' SHA256 不符（文件被改动/回退/损坏）') }
}

# ---- ⑤ 初始化入口的端点 ----
Write-Host ''
Write-Host '⑤ 初始化入口（付款存量 / 过程资料 / 集采 / 库存补抓）'
try {
    $spec = (Invoke-WebRequest -Uri ($Base + '/openapi.json') -UseBasicParsing -TimeoutSec 15).Content | ConvertFrom-Json
    $paths = @($spec.paths.PSObject.Properties.Name)
    # 前三个历史导入域都走**通用导入面** /imp/<域>/*（D26：导入只留通用面）⇒ 逐个域核，别只看「面在」
    foreach ($d in @('m05_flow', 'm06_proc', 'm11_jc')) {
        $hit = @($paths | Where-Object { $_ -like ('/api/imp/' + $d + '/*') })
        if ($hit.Count -gt 0) { Ok ('导入域 ' + $d + ' 在（' + $hit.Count + ' 个端点）') } else { Bad ('导入域 ' + $d + ' 不在 openapi 里') }
    }
    if (@($paths | Where-Object { $_ -like '/api/m08*' }).Count -gt 0) { Ok '库存单据 /api/m08* 在（补抓入口）' } else { Bad '库存单据 /api/m08* 不在' }
    Skip '「点进去真能导」只能人工走一小段真数据（openapi 只证明端点存在）⇒ 见 docs\deployment.md §三'
} catch { Skip ('拿不到 /openapi.json：' + $_.Exception.Message) }

Write-Host ''
if ($script:fail -eq 0) { Write-Host '=== 自检通过（⚠️ 有跳过的项按上面提示人工补）===' } else { Write-Host ('=== 自检失败：' + $script:fail + ' 项 ⛔ ===') }
exit $(if ($script:fail -eq 0) { 0 } else { 1 })
