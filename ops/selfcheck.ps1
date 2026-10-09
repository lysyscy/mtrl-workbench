# ops/selfcheck.ps1 —— 目标机自检（M8 ④「交接口径与自检命令」的正文 · TAIL-188）
#
# 设计要点：本自检不依赖交付面。完整现行交付面可另行复制/配置，见 ops/deployment.md §四；
#   相关验收按所需输入/工具判断。ui_parity只查壳自身，不因交付面缺失自动不可运行。
#   ⚠️ 这里**刻意不写条数**（原写「641 那个数」—— 判据点一涨它就过期，属"留痕被后续甩下"那族）。
#   这里做的是「这系统自己能不能转」的五项，⛔ 不是验收：
#     ① 服务在跑（mtrl-workbench-server = Running / Automatic）
#     ② http://127.0.0.1:8000/app 返回 200
#     ③ 库连得上、基础表数量检查（走**后端自己的配置**去连 —— 口径只认一份）
#     ④ 两份运行时模板在，且 SHA256 对得上（防回退/拷贝损坏 —— 历史踩过）
#     ⑤ 三个历史导入域 ＋ 库存单据端点在（从 /openapi.json 里找；拿不到就照实说「跳过 + 原因」）
#
# 用法（目标机 · 普通窗口即可）：
#   powershell -ExecutionPolicy Bypass -File ops\selfcheck.ps1
#   powershell -ExecutionPolicy Bypass -File ops\selfcheck.ps1 -Base http://127.0.0.1:8000 -RepoRoot D:\dev\mtrl-workbench
# 退出码：0 = 没有计入失败（可能有跳过，须逐项看）；1 = 有 ⛔。安装自检不证明真实备份恢复或完整业务数据。
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

Write-Host '=== ops/selfcheck.ps1 · 目标机自检（安装层检查；跳过须另核，真实恢复与相关验收分开）==='
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
    # ⚠️⚠️ `app` 包在 backend/ ⇒ 必须让它可导入。⛔ 光 `Push-Location backend` **不够** ——
    #    python 跑**脚本文件**时 `sys.path[0]` = **脚本所在目录**（这里是 %TEMP%）✗，不是 cwd ✗
    #    ⇒ 2026-09-29 实测 `ModuleNotFoundError: No module named 'app'` ⇒ 正解 = **显式给 PYTHONPATH**。
    $oldPp = $env:PYTHONPATH
    $env:PYTHONPATH = (Join-Path $RepoRoot 'backend')
    $out = (& $py $tmp 2>&1 | Select-Object -Last 1)
    $env:PYTHONPATH = $oldPp
    if ($LASTEXITCODE -eq 0 -and $out -match '^\d+$' -and [int]$out -ge 10) { Ok ('库连得上 · 当前 schema 表 ' + $out + ' 张') }
    else { Bad ('库自检失败（后端自己的配置连不上或缺表）：' + ($out -join ' ')) }
}

# ---- ④ 运行时模板 ＋ SHA256（⭐ 交给 Python 算：⛔ 不让 PowerShell 碰中文路径）----
Write-Host ''
Write-Host '④ 运行时模板'
# ⚠️⚠️ 为什么不用 Get-FileHash：2026-09-29 实测 —— 本项在**非 UTF-8 控制台**（例如被 Python 子进程拉起）里
#   拿**中文路径**取不到哈希 ⇒ `$h` 为空 ⇒ 误报「SHA256 不符」✗✗（当时两份模板其实完好）。
#   ⇒ 改交后端 venv 的 Python（hashlib ＋ pathlib ⇒ 中文路径天然没问题），PS 只读最后一行 RESULT。
if (-not (Test-Path $py)) {
    Skip '没有 backend\.venv\Scripts\python.exe ⇒ 本项跳过（⚠️ 目标机要跑自检就必须有 venv）'
} else {
    $tplDir = Join-Path $RepoRoot 'backend\app\resources\templates'
    $code = @"
import hashlib, pathlib
d = pathlib.Path(r'$tplDir')
want = {
    '模板_库存单据明细表.xlsx': '6803d01b1b0793f02543b281e737f9de42c9b955b7f45da0d55547e15b5e6bd2',
    '模板_收发结存表.xlsx': 'eab1c626dce769ac979408564cbffa52a8ca3bc42d80c76c40e0335f8c46d323',
}
bad = []
for k, v in want.items():
    p = d / k
    if not p.exists():
        print('MISS ' + k); bad.append(k); continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    print(('OK   ' if h == v else 'BAD  ') + k + '  ' + h)
    if h != v: bad.append(k)
print('RESULT ' + ('ALL-OK' if not bad else 'BAD:' + ','.join(bad)))
"@
    $tmp = Join-Path $env:TEMP 'mtrl_selfcheck_tpl.py'
    [IO.File]::WriteAllText($tmp, $code, (New-Object Text.UTF8Encoding($false)))
    $lines = @(& $py $tmp 2>&1)
    foreach ($l in $lines) { if ($l -notlike 'RESULT*') { Write-Host ('   ' + $l) } }
    $last = ($lines | Select-Object -Last 1)
    if ($last -eq 'RESULT ALL-OK') { Ok '两份运行时模板 SHA256 ✓（交 Python 算）' }
    else { Bad ('模板校验未过：' + $last) }
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
    Skip '「点进去真能导」只能人工走一小段真数据（openapi 只证明端点存在）⇒ 见 ops\deployment.md §三'
} catch { Skip ('拿不到 /openapi.json：' + $_.Exception.Message) }

Write-Host ''
if ($script:fail -eq 0) { Write-Host '=== 自检通过（⚠️ 有跳过的项按上面提示人工补）===' } else { Write-Host ('=== 自检失败：' + $script:fail + ' 项 ⛔ ===') }
exit $(if ($script:fail -eq 0) { 0 } else { 1 })
