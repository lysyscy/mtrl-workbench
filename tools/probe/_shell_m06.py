"""⑨ · m06 过程资料：`procPj` 必须有值

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

from _shell_common import goto


def check(page, errors) -> None:
    """⑨ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- m06 过程资料：机械源已接后端 ⇒ ⭐ **`procPj` 必须有值**（证明「加载时求值」的坑已修）
    goto(page, "m06")
    m06 = page.evaluate("""() => ({
        mach6Wh: Object.keys(MACH6).length,
        ivs: IVs.length,
        procPj: (typeof procPj === 'string') ? procPj : String(procPj),
        pjCands: (typeof PROC_PJS === 'object' && PROC_PJS) ? PROC_PJS.length : -1,
        tabs: document.querySelectorAll('#view .tb2').length,
        tables: document.querySelectorAll('#view table').length,
        mechCells: document.querySelectorAll('[data-act="procMechSave"]').length,
        wiredLabel: (document.querySelector('#ttl em')||{}).innerText||'',
    })""")
    print("⑨ m06 =", m06)
    oks5 = [
        (m06["tables"] >= 1 and m06["tabs"] == 3, "三张表签（表① / 表② / 差异表）＋ 表在线"),
        ("未接通" not in m06["wiredLabel"], "接通页的顶栏不挂状态牌（用户裁定 B）"),
        (m06["ivs"] > 0, f"材料侧取数已通（库存单据 {m06['ivs']} 行）"),
        (bool(m06["procPj"]) and m06["pjCands"] > 0,
         f"⭐ 项目候选已落定（procPj={m06['procPj'][:18]!r} · 候选 {m06['pjCands']} 个）"
         " —— 若仍是「加载时求值」，这里会是空的"),
        (m06["mechCells"] > 0, "机械费数据格可编辑"),
    ]
    for ok, what in oks5:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("m06 自检未通过：" + what)


