"""⑥b · m04 手动行：点得出草稿行（**不落库**，验完收起）

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations



def check(page, errors) -> None:
    """⑥b —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- m04 手动行（`TAIL-35`）：⭐ 真机验「入口真的能开出草稿行」（**不落库**，验完收起）
    page.click('[data-act="plRowAdd"]')
    # 条件 = **下一步就要读的那个元素**（草稿行的「保存」按钮）—— ⛔ 不是"睡 400 ms 再说"
    page.wait_for_selector('[data-act="plRowSave"]', timeout=8000)
    m04d = page.evaluate("""() => ({
        draft: !!document.querySelector('[data-act="plRowSave"]'),
        setCells: document.querySelectorAll('#view [data-act="plRowSet"]').length,
    })""")
    print("⑥b m04 手动行草稿 =", m04d)
    for ok, what in [
        (m04d["draft"], "⭐ 点「＋ 手动新增计划行」**真的开出草稿行**（接线前只是一句 toast 提示）"),
        (m04d["setCells"] >= 5, f"⭐ 草稿行的可填格已就位（{m04d['setCells']} 格）"),
    ]:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("m04 手动行自检未通过：" + what)
    if m04d["draft"]:
        page.click('[data-act="plRowCancel"]')      # ⚠️ 收起草稿 —— **不落库**（写库验证走 curl 那边）
        page.wait_for_selector('[data-act="plRowSave"]', state="detached", timeout=8000)
        print("  ℹ️ 草稿已收起（未落库）")


