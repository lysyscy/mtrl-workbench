#!/usr/bin/env python
"""`TAIL-64` **P4-a** 顺手修一处**自己造的交付断点**（2026-09-30）。

**起因**：`demo/_links.js` 当场报 `FAIL · index.html ×1`（位置 = 原型 `1727` 行）——
那是我给 `FBAR` 写的**注释**里写了「声明见 `index.html` 的样式块」，而 `index.html` 是**工程仓**的壳本体、
**不在交付面扫描范围**内 ⇒ 交付面多了一条**断链**。

⚠️ 这是**本仓第二次**同款（`TAIL-64` `P2③` `m07`：原型注释里写了工程仓的文件名 ⇒ `_links` 当场 FAIL）——
**交付面里的注释只许提交付面自己的东西**。
⇒ 本件把那两行注释里的**工程仓文件名**去掉（**两侧同改同句** ⇒ `U5`/`U1` 的"逐字一致"不受影响：
   该注释在 `U5` 段**之外**，`top_segs` 会把 ` * ` 起头的续行整段削掉）。

用法：`python tools/oneoff/_p4a_links.py`
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")

OLD = """ * `cls` 的合法取值 = `.fbar` 的变体（`pane` / `strip` / `strip mb6` / `plate`），声明见 `index.html` 的样式块。
 * 自证：`tools/mut/_mut_fbar.py`（去掉委托 / 掏空内核 ⇒ 对应判据必须红）。 */"""
NEW = """ * `cls` 的合法取值 = `.fbar` 的变体（`pane` / `strip` / `strip mb6` / `plate`），声明在壳的样式块里。
 * 自证 = 变异脚本（去掉委托 / 掏空内核 ⇒ 对应判据必须红）。 */"""


def main() -> int:
    for p in (PROJ, PROTO):
        data = p.read_bytes()
        old = OLD.replace("\n", "\r\n").encode("utf-8")
        new = NEW.replace("\n", "\r\n").encode("utf-8")
        n = data.count(old)
        assert n == 1, f"⛔ 在 {p.name} 里命中 {n} 次（必须恰好 1 次）"
        p.write_bytes(data.replace(old, new, 1))
        print(f"  ✅ 已去掉工程仓文件名 —— {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
