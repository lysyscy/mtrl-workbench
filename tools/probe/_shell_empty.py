"""壳真机自检 · **㉛ 空态**（`TAIL-171`-① · 2026-09-29 · 用户裁定「按推荐做」）。

**它验什么**（守则 §2.1「四态各有一句话，不许一片空白」· §5.4「空态唯一出口 `EMPTYROW`」）：

  ⭐ 把 `m04` 的日期筛到一个**没有数据的月** ⇒ 屏幕上必须是**空态**（为什么空 ＋ 下一步），
  ⛔ **不许只剩表头**（那与"页面坏了"长得一样）；再把筛选**筛回「全部时间」** ⇒ 必须回到正常路
  （有数据行、**合计行还在表尾**）—— 半边只验"空态出来了"会漏掉"正常路被改坏"。
  ⚠️ 2026-10-01（`TAIL-208`）：原来是「筛回**当月**」⇒ 那是把"当月有数据"当恒定条件（跨月必红，实测）；已改成「全部时间」。

**为什么要它**（本仓实测）：`_shell_states.py`（㉗）只覆盖 **加载 / 错 / 重试**，
  **全站没有任何真机探针验过「空态」** ⇒ 空态此前只有**离线判据**（`EMPTYROW` 唯一出口）。
  而"0 行那一刻屏幕上到底画了什么"**只有真机能验**（离线只能证明源码里写了 `EMPTYROW(...)`）。
  ⇒ 2026-09-29 `A3` 逐页给 `m04` 补空态时，是**现写一次性脚本**才敢说它真画得出来 ⇒ 提升成正式判据。

**为什么拿 `m04` 做样本**：它三层筛选（年月 / 项目 / 审查结果）⇒ **造 0 行最干净**
  （挑一个没有数据的月即可，不用动库）；且它正是本条的起源页。
"""

from __future__ import annotations

#: 空态那两段原话（`V.m04` 的 `EMPTYROW(...)` —— 与源码里的**同一份口径**）
WHY = "当前筛选条件下没有付款计划"
NEXT = ""  # TAIL-263：默认空态仅保留没有付款计划，筛选操作仍在上方。
#: 筛到没有数据的月（`plf.ym` 是 m04 的年月筛选状态）
EMPTY_YM = "2000-01"


def _read(page) -> dict:
    """屏幕上现在是什么（正文 ＋ 表体行数）。"""
    return page.evaluate("""() => {
        const v = document.querySelector('#view') || {};
        const tb = v.querySelector('table tbody');
        return {
            txt: (v.innerText || '').replace(/\\s+/g, ' '),
            rows: tb ? tb.querySelectorAll('tr').length : -1,
        };
    }""")


def check(page, errors: list[str]) -> None:
    """㉛ 空态 ＋ 正常路（见文件头）。"""
    from _shell_common import goto

    goto(page, "m04")

    # ── ① 筛到**没有数据的月**：必须是空态，⛔ 不许只剩表头
    page.evaluate(
        "() => { plf.ym='" + EMPTY_YM + "'; plf.projs=[]; plf.review='全部'; render(); }")
    page.wait_for_timeout(700)
    a = _read(page)
    ok_empty = (WHY in a["txt"]) and a["rows"] == 1
    print(f"   {'✅' if ok_empty else '⛔'}㉛-① 筛到没数据的月 ⇒ 空态："
          f"{'在' if ok_empty else '**不在**'}（表体 {a['rows']} 行 · 期望 1 = 只有空态那一行）")
    if not ok_empty:
        errors.append(
            "㉛-① 筛不到行时**没有给出空态**（守则 §2.1：列表空着不说明下一步 ⇒ 用户以为页面坏了）"
            f" —— 屏幕上：{a['txt'][-160:]}")
    elif a["rows"] > 1:
        errors.append(f"㉛-① 空态没有取代空表（表体还有 {a['rows']} 行）")

    # ── ② 筛回「全部时间」：正常路没被改坏（有行 ＋ 合计行仍在）
    #    ⚠️⚠️ 2026-10-01（`TAIL-208`）：原先这里写的是 `plf.ym=bjMonth()`（**当月**）——
    #    那是把"立它时的实况（当月有数据）"当成了**恒定条件**：库里付款计划全在 2026-09，
    #    而今天 10-01（月初）当月本来就是空的 ⇒ 这条判据**跨月必红**（实测）。
    #    ⇒ 改成筛「**全部时间**」（`tmIn` 对 `'全部'` 恒真）：验的是同一条事（正常路没被改坏），
    #      但**不依赖"当月恰好有数据"**。⛔ **没放宽阈值**（仍是"表体 ≥2 行 ＋ 有合计行"）。
    # 空库也要验证正常分支：只在浏览器内加入一条隔离样本，结束后恢复，绝不写业务表。
    saved = page.evaluate("() => ({rows:PLs.slice(),filter:JSON.parse(JSON.stringify(plf))})")
    try:
        page.evaluate("""() => {
            if (!PLs.length) PLs.push({id:'probe-empty-normal',date:'2026-09-01',code:'probe',proj:'',
                year_month:'2026-09',monthAmt:10,flowAmt:10,review:'完全匹配',supplier:'',material:''});
            plf.ym='全部'; plf.projs=[]; plf.review='全部'; render();
        }""")
        page.wait_for_timeout(700)
        c = _read(page)
    finally:
        page.evaluate("(s) => {PLs.splice(0,PLs.length,...s.rows);Object.assign(plf,s.filter);render();}", saved)
    ok_norm = ("合计" in c["txt"]) and (c["rows"] >= 2)
    print(f"   {'✅' if ok_norm else '⛔'}㉛-② 筛回全部时间 ⇒ 正常路：表体 {c['rows']} 行（含合计行 ⇒ 期望 ≥2）")
    if not ok_norm:
        errors.append("㉛-② 筛回当月后行或合计行不见了 —— 空态那条分支把**正常路**改坏了")
