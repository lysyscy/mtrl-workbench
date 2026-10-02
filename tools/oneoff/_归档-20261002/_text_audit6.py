"""只读盘点：四个导入域的**域自报文案**有多长（`TAIL-209` 余项 ③ · `imp` 那条 127 字）。

为什么单列一件：这些字**不在壳里**（在 backend 各域的 `imp_spec.py`）⇒ 壳那套扫描看不见它们；
而它们**照样上屏**（走 `lgMd`，见 `legacy.js`）⇒ 按 `D29` 同样该瘦。

⚠️ 用 `ast` **静态解析**（⛔ 不 import 那几个模块 —— 它们会连带拉进 models / DB）。
⚠️ 字数口径与真机 ㉖ 一致：剥掉 `**`（加粗标记，不上屏）与空白。
⚠️ 本件是**只读量测**：不进收工闸门、不判红。
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FILES = [
    ROOT / "backend/app/mod04_plan/imp_spec.py",
    ROOT / "backend/app/mod05_flow/imp_spec.py",
    ROOT / "backend/app/mod06_proc/imp_spec.py",
    ROOT / "backend/app/mod11_jc/imp_spec.py",
]
KEYS = ("note", "keep_note", "rule_note", "field_list_hint")


def plain(s: str) -> str:
    """上屏字数：剥 `**`（不上屏）与空白。"""
    return re.sub(r"\s+", "", s.replace("**", ""))


for path in FILES:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    print(f"\n══ {path.relative_to(ROOT)}")
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "DomainSpec"):
            continue
        for kw in node.keywords:
            if kw.arg not in KEYS:
                continue
            try:
                val = ast.literal_eval(kw.value)
            except Exception:                                  # noqa: BLE001
                print(f"   {kw.arg:16s} ⚠️ 不是字面量（{type(kw.value).__name__}）⇒ 手工看")
                continue
            txt = plain(str(val))
            flag = "⛔" if len(txt) > 120 else ("· " if len(txt) >= 80 else "  ")
            print(f" {flag} {kw.arg:16s} {len(txt):4d} 字  {txt[:60]}…")

print("\n（⛔ >120 字的按 `D29` 该瘦；80–119 视情）")
sys.exit(0)
