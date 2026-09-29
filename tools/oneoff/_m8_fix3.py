"""修 `ops/selfcheck.ps1` 第④项：**别用 PowerShell 处理中文路径**。

## 病灶（2026-09-29 预演第 2 步当场炸出）

第④项用 `Get-FileHash (Join-Path $tplDir '模板_….xlsx') -Algorithm SHA256` ⇒ 当 selfcheck 被
**非 UTF-8 控制台**（例如由 Python 子进程）拉起时，**中文路径取不到** ⇒ `$h` 为空 ⇒ 判「SHA256 不符」✗✗
—— **两份模板其实完好**（实测哈希与期望逐字符一致 ✓、mtime 还是入库那天 ✓、git 零改动 ✓）。
⚠️ 这是**误报**，但落在目标机上就是"白折腾一轮"（用户会以为文件坏了）。

## 改法

第④项整个换成：**把校验交给后端 venv 的 Python**（`hashlib` ＋ `pathlib` ⇒ 中文路径天然没问题），
PowerShell 只读它最后那行 `RESULT OK/BAD` ⇒ ⛔ 不再让 PS 碰中文路径的哈希。
⚠️ 沿用两条既有教训：① 代码落**临时 `.py`** 再跑（⛔ 不内联引号）；② 本文件保持 **UTF-8 with BOM**。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_fix3.py --check` / `--write`
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = ROOT / "ops" / "selfcheck.ps1"

OLD = """# ---- ④ 运行时模板 ＋ SHA256 ----
Write-Host ''
Write-Host '④ 运行时模板'
$want = @{
    '模板_库存单据明细表.xlsx' = '6803d01b1b0793f02543b281e737f9de42c9b955b7f45da0d55547e15b5e6bd2'
    '模板_收发结存表.xlsx'     = 'eab1c626dce769ac979408564cbffa52a8ca3bc42d80c76c40e0335f8c46d323'
}
$tplDir = Join-Path $RepoRoot 'backend\\app\\resources\\templates'
foreach ($k in $want.Keys) {
    $p = Join-Path $tplDir $k
    if (-not (Test-Path $p)) { Bad ('缺模板 ' + $k + '（⛔ 报表导出会失败 —— 设计上就会显式报错）'); continue }
    $h = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
    if ($h -eq $want[$k]) { Ok ($k + ' SHA256 ✓') } else { Bad ($k + ' SHA256 不符（文件被改动/回退/损坏）') }
}"""

NEW = """# ---- ④ 运行时模板 ＋ SHA256（⭐ 交给 Python 算：⛔ 不让 PowerShell 碰中文路径）----
Write-Host ''
Write-Host '④ 运行时模板'
# ⚠️⚠️ 为什么不用 Get-FileHash：2026-09-29 实测 —— 本项在**非 UTF-8 控制台**（例如被 Python 子进程拉起）里
#   拿**中文路径**取不到哈希 ⇒ `$h` 为空 ⇒ 误报「SHA256 不符」✗✗（当时两份模板其实完好）。
#   ⇒ 改交后端 venv 的 Python（hashlib ＋ pathlib ⇒ 中文路径天然没问题），PS 只读最后一行 RESULT。
if (-not (Test-Path $py)) {
    Skip '没有 backend\\.venv\\Scripts\\python.exe ⇒ 本项跳过（⚠️ 目标机要跑自检就必须有 venv）'
} else {
    $tplDir = Join-Path $RepoRoot 'backend\\app\\resources\\templates'
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
}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    if not SELF.exists():
        print("⛔ 找不到 ops/selfcheck.ps1 ⇒ 停手"); return 2
    raw = SELF.read_bytes()
    enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    s = raw.decode(enc)
    n = s.count(OLD)
    print(f"  {'✓' if n == 1 else '⛔'} 第④项锚点：命中 {n} 处（要 1）· 编码 {enc}")
    if n != 1:
        print("     ⛔ 对不上 ⇒ 停手（别改错块）"); return 2
    if apply:
        SELF.write_bytes(s.replace(OLD, NEW, 1).encode(enc))
        print("     ✅ 已改（仍以 UTF-8 with BOM 写回）")
    else:
        print("     🧪 --check（干跑）")
    print("   复核：**从 Python 子进程拉起来跑**（同 `_m8_rehearse2.py`）⇒ 本机应 5/5 —— ⚠️ 直接从 UTF-8 控制台跑测不出这个 bug")
    return 0


if __name__ == "__main__":
    sys.exit(main())
