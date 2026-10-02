"""⑩ · m07 收发结存与活动大表

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

from _shell_common import goto


def check(page, errors) -> None:
    """⑩ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- m07 收发结存与活动大表：读全量 ＋ 提取 ＋ 大表
    #      ⭐ 可观测证据 = **表内渲染行数 == 后端给出的行数 ＋ 合计行**（同 m08 的口径）
    goto(page, "m07")
    m07 = page.evaluate("""() => {
        const rows = whRows(fWhYm);
        const tbls = [...document.querySelectorAll('#view table')];
        const first = tbls[0] ? tbls[0].querySelectorAll('tbody tr').length : 0;
        return {
          ym: fWhYm, wh: rows.length, whRows: first,
          big: BIGSET.length, bigRows: bigRows(bjMonth(-1)).length,
          extKinds: Object.keys(EXTM).length,
          manMons: Object.keys(BIGVAL).length,
          matOk: MAT_OK,
          tables: tbls.length,
          wiredLabel: (document.querySelector('#ttl em')||{}).innerText||'',
        };
    }""")
    print("⑩ m07 =", m07)
    oks6 = [
        (m07["tables"] >= 3, "三张表在线（收发结存 ＋ 焊材/气体提取 ＋ 活动大表）"),
        ("未接通" not in m07["wiredLabel"], "接通页的顶栏不挂状态牌（用户裁定 B）"),
        (m07["whRows"] == m07["wh"] + 1,
         f"⭐ 收发结存表内渲染 == 后端行数 ＋ 合计行（{m07['whRows']} = {m07['wh']} ＋ 1）"),
        (m07["big"] > 0 and m07["bigRows"] == m07["big"],
         f"⭐ 大表行数 == 后端选题数（{m07['bigRows']} vs {m07['big']}）"
         " —— 若 `BIGSET` 没接后端，这里会是演示的 8 行"),
        (m07["matOk"] is True,
         "⭐ 「主材累计」取数口**已接入**（`TAIL-25` · 后端 `mat_available=True`）⇒ 该列显**真数**而非「—」"),
    ]
    for ok, what in oks6:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("m07 自检未通过：" + what)


