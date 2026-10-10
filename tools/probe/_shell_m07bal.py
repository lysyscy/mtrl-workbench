"""⑩b · m07 提取表「结余」列 == 后端 `balances`

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations



def check(page, errors) -> None:
    """⑩b —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- ⭐ 2026-09-18（用户裁定「甲」）提取表「结余」列：列 +1 ｜ 每行一个可编辑格 ｜ 值 == 后端
    #      ⚠️ **本段只读** —— 写路径的真机验证走 `tools/_e2e_m07bal.py`（冒烟脚本不写库、可反复跑）。
    m07b = page.evaluate("""async () => {
        const be = await (await fetch('/api/m07/extract')).json();
        const tbl = [...document.querySelectorAll('#view table')]
                      .find(t => t.dataset.sortKey === 'm07:kinds');
        if (!tbl) return {found: false};
        const ths = [...tbl.querySelectorAll('thead th')].map(x => x.innerText.trim());
        const ins = [...tbl.querySelectorAll('td input[data-act="extBal"]')];
        const bad = [];
        ins.forEach(i => {
          const b = ((be.balances || {})[i.dataset.k] || {})[i.dataset.p];
          const want = (b == null) ? '' : String(Number(b));
          if (String(i.value) !== want) {
            bad.push(i.dataset.k + '|' + i.dataset.p + ': ' + i.value + ' ≠ ' + want);
          }
        });
        const rows = [...tbl.querySelectorAll('tbody tr')].map(tr => {
          const tds = [...tr.querySelectorAll('td')];
          const span = tr.querySelector('td[colspan]');
          return {n: span ? Number(span.getAttribute('colspan')) : tds.length,
                  inputs: tds.filter(td => td.querySelector('input[data-act="extBal"]')).length};
        });
        return {found: true, ths: ths, n: ins.length, bad: bad, year: String(fExt.year),
                rows: rows, empty: !!tbl.querySelector('tbody td[colspan]')};
    }""")
    print("⑩b m07 结余列 =", m07b)
    # ⭐ 2026-10-10 用户裁定：「2025-11及之前」人工历史列**只在所选年份 ≤ 2025 时显示**
    #   ⇒ 表头 17 列（有该列）/ 16 列（没有）；数据行 · 合计行 · 空态行的跨列数都必须跟着走。
    want_cols = 17 if (m07b.get("year") or "").isdigit() and int(m07b["year"]) <= 2025 else 16
    off_cols = sorted({r["n"] for r in (m07b.get("rows") or []) if r["n"] != want_cols})
    editable = sum(r["inputs"] for r in (m07b.get("rows") or []))
    oks7 = [
        (bool(m07b.get("found")) and len(m07b.get("ths") or []) == want_cols
         and (("2025-11及之前" in "".join(m07b.get("ths") or [])) == (want_cols == 17)),
         f"⭐ 「结余」列与年份匹配（{m07b.get('year')} 年 ⇒ 表头 {want_cols} 列）：{m07b.get('ths')}"),
        (not off_cols,
         f"⭐ 数据行/合计行/空态行的列数都 == 表头 {want_cols} 列（歪列就是这里红）：{off_cols}"),
        ((editable >= 1 or m07b.get("empty")) if want_cols == 17 else editable == 0,
         f"⭐ 人工历史列的录入格随列一起显隐（本屏 {editable} 个 · 共 {m07b.get('n')}）：{want_cols} 列"),
        (m07b.get("bad") == [],
         f"⭐ 页面结余格逐格 == 后端 `balances`（未录入 ⇒ 空）：{m07b.get('bad')}"),
    ]
    for ok, what in oks7:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("m07 结余列自检未通过：" + what)


