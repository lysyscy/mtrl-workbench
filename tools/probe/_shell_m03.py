"""④ · m03 结构件（对照 `ui_parity` 口径）

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

from _shell_common import goto


def check(page, errors) -> None:
    """④ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # 切到 m03 并断言结构件（对照 ui_parity 的口径）
    goto(page, "m03")
    dims = page.evaluate("""() => ({
        tables: document.querySelectorAll('#view table').length,
        fbar:   document.querySelectorAll('#view .fbar').length,
        tip:    document.querySelectorAll('#view details.tip').length,
        sum:    document.querySelectorAll('#view tr.sumrow').length,
        pjwrap: document.querySelectorAll('#view .pjwrap').length,
        sortcol:document.querySelectorAll('#view [data-sort-col]').length,
        rows:   document.querySelectorAll('#view tbody tr').length,
        head:   (document.querySelector('#view .card h4')||{}).innerText||'',
    })""")
    print("④ m03 结构件 =", dims)


