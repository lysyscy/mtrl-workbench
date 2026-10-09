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
        return {found: true, ths: ths, n: ins.length, bad: bad,
                empty: !!tbl.querySelector('tbody td[colspan]')};
    }""")
    print("⑩b m07 结余列 =", m07b)
    oks7 = [
        (bool(m07b.get("found")) and len(m07b.get("ths") or []) == 17
         and "2025-11及之前" in "".join(m07b.get("ths") or []),
         f"⭐ 「结余」列就位（表头 17 列）：{m07b.get('ths')}"),
        (m07b.get("n", 0) >= 1 or m07b.get("empty"),
         "⭐ 每个数据行都有可编辑的「结余」格（该筛选下没有数据时如实给空态行）"),
        (m07b.get("bad") == [],
         f"⭐ 页面结余格逐格 == 后端 `balances`（未录入 ⇒ 空）：{m07b.get('bad')}"),
    ]
    for ok, what in oks7:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("m07 结余列自检未通过：" + what)


