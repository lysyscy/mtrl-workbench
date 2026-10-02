"""⑤ · m01 渲染真数据（⛔ 不是「页面空着但不报错」）

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

from _shell_common import goto


def check(page, errors) -> None:
    """⑤ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- m01 项目档案：接线后应**渲染真数据**（⛔ 不是"页面空着但不报错"）
    goto(page, "m01")
    m01 = page.evaluate("""() => {
        const rows = [...document.querySelectorAll('#view tbody tr')];
        const cells = rows.map(tr => tr.innerText.replace(/\\s+/g,' ').trim()).slice(0, 3);
        return {
          pjs: PJs.length,
          rows: rows.length,
          empty: document.body.innerText.includes('当前筛选条件下没有项目档案'),
          wiredLabel: (document.querySelector('#ttl em')||{}).innerText||'',
          statusSel: [...document.querySelectorAll('#view tbody select[data-act="editStatus"]')]
                        .map(s => s.value).slice(0, 5),
          sample: cells,
        };
    }""")
    print("⑤ m01 =", m01)
    oks = [
        (m01["pjs"] > 0, "PJs 拉到真数据"),
        (m01["rows"] > 0 and not m01["empty"], "列表**真的渲染出行**（状态枚举没转对时会恒空）"),
        ("未接通" not in m01["wiredLabel"], "接通页的顶栏不挂状态牌（用户裁定 B）"),
        (all(v in ("在建", "归档") for v in m01["statusSel"]) and len(m01["statusSel"]) > 0,
         "状态列的 <select> **选中了值**（不是空选）"),
    ]
    for ok, what in oks:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("m01 自检未通过：" + what)


