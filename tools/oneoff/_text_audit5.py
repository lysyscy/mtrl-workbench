"""批 5 靶（只读）：把**弹窗里的**说明块（`class="tip"` 且块前 600 字里出现 `modal({`）**全文**打出来。

⚠️ 判定仍按 `D29`（读者 = 已清楚业务流程的人）：业务常识 / 机制辩解 / 内部编号 / 界面上看得见的 ⇒ 删；
   **系统特有行为与后果** ⇒ 留。本件只**列**，不判 —— 判断在人的那一步。
⚠️ 与 `_text_audit4.py` 是**互补**的一对：4 = 页内（排除 modal），5 = 弹窗内。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

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
        # ⚠️ 判定"在不在弹窗里"的口径（2026-10-01 深夜**订正**）：`audit3/4/5` 首版用
        #    「`modal({` 出现在块前、且它比最后一个 `}` 更靠右」—— ⛔ **那个判法是坏的**：
        #    弹窗标题常写成 ``title: `…${x}…`,``，`${…}` 里就有 `}` ⇒ 被误判成**页内**
        #    （实测漏掉 `core.js` 那几处弹窗 ⇒ 批 5 的"16 处"是**少算的**）。
        #    改成认 `body:`（弹窗正文的唯一写法）＋ `modal(` 同时在场 —— 与 `${…}` 无关。
        if not ("body:" in head and "modal(" in head):
            continue                                   # 页内的 ⇒ 批 4
        txt = strip(seg)
        n += 1
        print(f"\n── [{len(txt)} 字] {name}:{text[:m.start()].count(chr(10)) + 1}")
        print(f"   {txt}")

print(f"\n=== 共 {n} 处（弹窗内 · 全部）===")
