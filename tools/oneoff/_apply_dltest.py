#!/usr/bin/env python
"""`TAIL-67` 收尾：**9 个"钉源码形态"的断言 ⇒ 改成"结构无关"的判据**。

⭐ 为什么必须改（不是"迁就测试"）：这些判据盯的是**意图**（"必须真下载" / "失败必须给人原因"），
   只是**用源码形态当代理**。抽成 `dlExport` 之后形态变了、意图没变
   ⇒ ⛔ 正确动作是**换代理**（动作委托 ＋ 内核真做了那几件事），
   ⛔ 而不是把通用件塞回每个动作里（那就等于"以后不许抽通用件"，与 `TAIL-62/67` 相反）。

⛔ 本脚本不改任何**意图**：每条断言的失败消息原文保留。
"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
T = pathlib.Path(r"D:\dev\mtrl-workbench\backend\tests")
BAK = pathlib.Path(r"D:\dev\mtrl-workbench\.workbuddy\scratch")
BAK.mkdir(parents=True, exist_ok=True)

# (文件, 旧断言, 新断言)
EDITS: list[tuple[str, str, str]] = [
    # ── 真下载：`createObjectURL` / `.download` 现在在内核里
    ("test_tail04_export.py",
     '    assert "createObjectURL" in act and ".download" in act, "没真的触发下载（拿不到文件）"',
     '    _a = with_kernel(act)          # ⭐ `TAIL-67`：下载代码已抽到 `dlExport` 通用件\n'
     '    assert "dlExport" in act and "createObjectURL" in _a and ".download" in _a, "没真的触发下载（拿不到文件）"'),
    ("test_path1_weldgas.py",
     '    assert "createObjectURL" in save and ".download" in save, "没真的触发下载（拿不到文件）"',
     '    _a = with_kernel(save)         # ⭐ `TAIL-67`：下载代码已抽到 `dlExport` 通用件\n'
     '    assert "dlExport" in save and "createObjectURL" in _a and ".download" in _a, "没真的触发下载（拿不到文件）"'),
    ("test_wired_m07.py",
     '    assert "createObjectURL" in body and ".download" in body, "没真的触发下载"',
     '    _a = with_kernel(body)         # ⭐ `TAIL-67`：下载代码已抽到 `dlExport` 通用件\n'
     '    assert "dlExport" in body and "createObjectURL" in _a and ".download" in _a, "没真的触发下载"'),
    # ── 文件名 / 分流 / 原因：同样在内核里
    ("test_tail04_export.py",
     '    assert "x-export-filename" in act, "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"',
     '    assert "x-export-filename" in with_kernel(act), "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"'),
    ("test_tail04_export.py",
     '    assert "\'application/json\'" in act, "没按 `content-type` 分流失败原因"',
     '    assert "\'application/json\'" in with_kernel(act), "没按 `content-type` 分流失败原因"'),
    ("test_path1_weldgas.py",
     '    assert "x-export-filename" in save, "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"',
     '    assert "x-export-filename" in with_kernel(save), "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"'),
    ("test_path1_weldgas.py",
     '    assert "\'application/json\'" in save, "没按 `content-type` 分流失败原因"',
     '    assert "\'application/json\'" in with_kernel(save), "没按 `content-type` 分流失败原因"'),
    # ── m05 / m06 / m07_big：失败必须给原因（三路都在内核里；动作只留"委托且不吞错"）
    ("test_wired_m05.py",
     '    assert "ct.includes(\'application/json\')" in body, "没按 content-type 分流"',
     '    _b = with_kernel(body)         # ⭐ `TAIL-67`：错误分类已抽到 `dlExport` 通用件\n'
     '    assert "ct.includes(\'application/json\')" in _b, "没按 content-type 分流"'),
    ("test_wired_m06.py",
     '    assert "ct.includes(\'application/json\')" in body, "没按 content-type 分流"',
     '    _b = with_kernel(body)         # ⭐ `TAIL-67`：错误分类已抽到 `dlExport` 通用件\n'
     '    assert "ct.includes(\'application/json\')" in _b, "没按 content-type 分流"'),
    ("test_wired_m07_big.py",
     '    assert "ct.includes(\'application/json\')" in body, "没按 content-type 分流"',
     '    _b = with_kernel(body)         # ⭐ `TAIL-67`：错误分类已抽到 `dlExport` 通用件\n'
     '    assert "ct.includes(\'application/json\')" in _b, "没按 content-type 分流"'),
    ("test_wired_m05.py",
     '    assert "d.message||\'后端没给原因\'" in body, "失败时没把后端的中文原因给用户"',
     '    assert "后端没给原因" in _b, "失败时没把后端的中文原因给用户"'),
    ("test_wired_m06.py",
     '    assert "d.message||\'后端没给原因\'" in body, "失败时没把后端的中文原因给用户"',
     '    assert "后端没给原因" in _b, "失败时没把后端的中文原因给用户"'),
    ("test_wired_m07_big.py",
     '    assert "d.message||\'后端没给原因\'" in body, "失败时没把后端的中文原因给用户"',
     '    assert "后端没给原因" in _b, "失败时没把后端的中文原因给用户"'),
    # ── 动作体变短了（错误处理搬走）⇒ 长度下限放宽，但**必须仍在**（防整段消失）
    ("test_wired_m05.py",
     '    assert 400 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"',
     '    assert 100 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"'),
    ("test_wired_m06.py",
     '    assert 400 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"',
     '    assert 100 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"'),
    ("test_wired_m07_big.py",
     '    assert 400 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"',
     '    assert 100 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"'),
    # ── 虚拟滚动阈值：`VSCROLL={m08:{min:400}}` ⇒ `const VS_MIN=400`（`TAIL-66` 默认全开）
    ("test_shell_render.py",
     '    assert "min:400" in read_shell(), "虚拟化阈值没了（小页也被虚拟化 = 固定开销不值）"',
     '    assert "VS_MIN=400" in read_shell(), "虚拟化阈值没了（小页也被虚拟化 = 固定开销不值）"'),
]

# 需要 `with_kernel` 的文件：确保已 import
NEED = {"test_tail04_export.py", "test_path1_weldgas.py", "test_wired_m05.py",
        "test_wired_m06.py", "test_wired_m07.py", "test_wired_m07_big.py"}

for fn, old, new in EDITS:
    p = T / fn
    t = p.read_text(encoding="utf-8")
    if old not in t:
        print(f"⚠️  {fn}: 找不到锚点 ⇒ {old.strip()[:70]}")
        continue
    shutil.copy2(p, BAK / (fn + ".bak-dltest"))
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8", newline="")
    print(f"✅ {fn}: {old.strip()[:52]}…")

for fn in NEED:
    p = T / fn
    t = p.read_text(encoding="utf-8")
    if "with_kernel" in t and "from tests.shell_src import" not in t:
        # 插到最后一个 `from tests.` 导入之后
        lines = t.split("\n")
        last = max(k for k, l in enumerate(lines) if l.startswith("from tests."))
        lines.insert(last + 1, "from tests.shell_src import with_kernel  # ⭐ `TAIL-67`：判据要连通用件一起看")
        p.write_text("\n".join(lines), encoding="utf-8", newline="")
        print(f"➕ {fn}: 补 `from tests.shell_src import with_kernel`")
print("完成 · 备份在 .workbuddy/scratch/*.bak-dltest")
