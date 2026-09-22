#!/usr/bin/env python
"""`TAIL-67` 收尾·第二批：**同一断言在同一文件里出现多次**（上一版只换了第一次）。

⭐ 教训：机械改写用 `str.replace(old, new, 1)` 时，**同一句断言出现 N 次就只改 1 处**
   ⇒ 剩下 N−1 处继续红。⇒ 这类"同形断言"必须 **`replace_all`** 或按**出现次数核对**。
"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
T = pathlib.Path(r"D:\dev\mtrl-workbench\backend\tests")
BAK = pathlib.Path(r"D:\dev\mtrl-workbench\.workbuddy\scratch")

ALL_EDITS: list[tuple[str, str, str]] = [
    # tail04：这两句在同文件里各出现 2~3 次 ⇒ 全部换掉
    ("test_tail04_export.py",
     '    assert "createObjectURL" in act and ".download" in act, "没真的触发下载（拿不到文件）"',
     '    _a = with_kernel(act)          # ⭐ `TAIL-67`：下载代码已抽到 `dlExport` 通用件\n'
     '    assert "dlExport" in act and "createObjectURL" in _a and ".download" in _a, "没真的触发下载（拿不到文件）"'),
    ("test_tail04_export.py",
     '    assert "x-export-filename" in act, "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"',
     '    assert "x-export-filename" in with_kernel(act), "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"'),
    ("test_tail04_export.py",
     '    assert "\'application/json\'" in act, "没按 `content-type` 分流失败原因"',
     '    assert "\'application/json\'" in with_kernel(act), "没按 `content-type` 分流失败原因"'),
    # m05 / m06 / m07_big：非 2xx 必须显式报错（这句现在在内核里）
    ("test_wired_m05.py",
     '    assert "if(!r.ok) return toast(`<b>导出没能完成</b>：HTTP ${r.status}`" in body, \\\n'
     '        "非 2xx 没显式报错（会静默产出空文件）"',
     '    assert "if(!r.ok)" in _b and "HTTP ${r.status}" in _b, \\\n'
     '        "非 2xx 没显式报错（会静默产出空文件）"'),
    ("test_wired_m06.py",
     '    assert "if(!r.ok) return toast(`<b>导出没能完成</b>：HTTP ${r.status}`" in body, \\\n'
     '        "非 2xx 没显式报错（会静默产出空文件）"',
     '    assert "if(!r.ok)" in _b and "HTTP ${r.status}" in _b, \\\n'
     '        "非 2xx 没显式报错（会静默产出空文件）"'),
    ("test_wired_m07_big.py",
     '    assert "if(!r.ok) return toast(`<b>导出没能完成</b>：HTTP ${r.status}`" in body, \\\n'
     '        "非 2xx 没显式报错（会静默产出空文件）"',
     '    assert "if(!r.ok)" in _b and "HTTP ${r.status}" in _b, \\\n'
     '        "非 2xx 没显式报错（会静默产出空文件）"'),
]

for fn, old, new in ALL_EDITS:
    p = T / fn
    t = p.read_text(encoding="utf-8")
    n = t.count(old)
    if not n:
        print(f"·  {fn}: 已无此形态 ⇒ {old.strip()[:56]}…")
        continue
    shutil.copy2(p, BAK / (fn + ".bak-dltest2"))
    p.write_text(t.replace(old, new), encoding="utf-8", newline="")
    print(f"✅ {fn}: 换 {n} 处 ⇒ {old.strip()[:52]}…")

# m07_big 缺 `_b`：补一行（它上面那条 `with_kernel` 变量叫什么要看情况）
p = T / "test_wired_m07_big.py"
t = p.read_text(encoding="utf-8")
if "_b = with_kernel(body)" not in t and "with_kernel(body)" in t:
    t = t.replace("    assert \"ct.includes('application/json')\" in _b",
                  "    _b = with_kernel(body)         # ⭐ `TAIL-67`：错误分类已抽到 `dlExport` 通用件\n"
                  "    assert \"ct.includes('application/json')\" in _b", 1)
    p.write_text(t, encoding="utf-8", newline="")
    print("➕ test_wired_m07_big.py: 补 `_b = with_kernel(body)`")
print("完成")
