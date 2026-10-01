"""批 4 靶：把**页内**说明块（`class="tip"` 且不在 `modal` 里）≥80 字的**全文**打出来（只读）。

⚠️ 判定仍按 `D29`：读者 = 已清楚业务流程的人 ⇒ 业务常识 / 机制辩解 / 内部编号 / 界面上看得见的 ⇒ 删；
   **系统特有行为与后果** ⇒ 留。本件只**列**，不判 —— 判断在人的那一步。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from tools.audit.shell_source import parts_text  # noqa: E402

TAG = re.compile(r"<[^>]+>")
JSX = re.compile(r"\$\{[\s\S]{0,600}?\}")
DET = re.compile(r"<details[\s\S]*?</details>")


def strip(s: str) -> str:
    return re.sub(r"\s+", "", TAG.sub("", DET.sub("", JSX.sub("…", s))))


n = 0
for name, text in parts_text():
    for m in re.finditer(r'<div class="tip', text):
        seg, depth, i = text[m.start():m.start() + 4000], 0, 0
        while i < len(seg):
            op, cl = seg.find("<div", i), seg.find("</div>", i)
            if cl < 0:
                break
            if 0 <= op < cl:
                depth += 1
                i = op + 4
            else:
                depth -= 1
                i = cl + 6
                if depth == 0:
                    seg = seg[:i]
                    break
        head = text[max(0, m.start() - 600):m.start()]
        if "modal({" in head and head.rfind("modal({") > head.rfind("}"):
            continue                                   # 弹窗里的 ⇒ 批 5
        txt = strip(seg)
        if len(txt) < 80:
            continue
        n += 1
        print(f"\n── [{len(txt)} 字] {name}:{text[:m.start()].count(chr(10)) + 1}")
        print(f"   {txt}")

print(f"\n=== 共 {n} 处（页内 · ≥80 字）===")
