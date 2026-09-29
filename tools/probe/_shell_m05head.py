"""壳真机自检 · **㉚ 台账那排控件（控件贴着对象 / 点开有反馈）**（`TAIL-142` ＋ `TAIL-144` · 2026-09-28）。

**它验什么**（守则 §2.7「控件/结论贴在它管的对象上」· §5.5「看着能点的点了必须有明确反馈」·
§4.2「状态必须真实」· §4.4「相似元素不制造歧义」）：

  用户 2026-09-28 截图报障原话：「我要选辅材机械表的项目，要**在右上角选离那么远**；我要**统一导出，
  点按钮后又要跑到最左边选项目**，这操作起来很不便，不熟悉的人也会被误导」⇒ 本段就是那两句的机器眼：

  ⭐ 四件**只有真机能验**（静态只能证明"源码里写了那句"，证明不了"屏幕上真的这样"）：
    ① **控件贴着对象**：「看哪个项目」必须出现在**两栏台账上方**（在它管的那两张表之前）——
       原挂在卡头右上角（DOM 顺序与实际视距都是"离得远"）；
    ② **卡头只有一个导出入口**（用户 2026-09-13 裁定「卡头一个导出入口」；上一版挤了三个）；
    ③ **两个导出都在同一条面板里、各自的范围挨着动作** —— 点开「导出…」后，
       `① 逐月台账` 段与 `② 总欠款汇总` 段**都要真的画出来**（⛔ 别再走 DOM 注入那条路：注入件一旦没挂上，
       用户会看到一个"点开却少一半"的面板）；
    ④ **点开自己会变样**：两个 toggle 点开后按钮必须带 `on` 态、收起要复原（原来点开毫无变化）。

  另查三件顺手的：**卡头不许有同名按钮**（§4.4）· **卡头不许横向溢出**（§5.9）·
  **「已展开…」不许挂长机制说明**（§3.4：说明要贴在面板里）。

⚠️ 本段**只读 ＋ 点两下后复原**（点过 `ledExpCancel` 收起面板），⛔ 不动数据、⛔ 不下载文件。
"""

from __future__ import annotations

#: 卡头那个唯一入口 ＋ 面板里那两个"点开会展开东西"的按钮（`data-act` 是稳定锚，⛔ 别按文案找）
HEAD_ENTRY = "ledExpToggle"
TOGGLES: tuple[tuple[str, str], ...] = (
    ("ledPjToggle", "看哪个项目"),
    ("ledExpToggle", "导出…"),
)
#: 「看哪个项目」那条必须出现的锚（卡内、表格上方）
PICK_LABEL = "看哪个项目（两侧共用）"
#: 面板里两段的标题（都在同一条面板里 ⇒ 不用"跑到最左边"）
STRIP_SECTIONS: tuple[str, ...] = ("① 逐月台账", "② 总欠款汇总")

JS_HEAD = r"""
() => {
  const v = document.querySelector('#view');
  const card = [...v.querySelectorAll('.card')].find(c => {
    const h = c.querySelector('h4'); return h && h.textContent.indexOf('逐月欠款台账') >= 0; });
  if (!card) return {err: '没找到台账卡'};
  const head = card.querySelector('h4');
  const body = card.querySelector('.bd') || card;
  const txt = e => (e ? e.innerText.replace(/\s+/g, ' ').trim() : '');
  const sp = head.querySelector('.sp');
  /* ⭐ ① 「看哪个项目」是不是**在两栏台账之前**（DOM 顺序 = 视距顺序） */
  const label = [...body.querySelectorAll('span')].find(s => txt(s) === '看哪个项目（两侧共用）');
  const ledTable = body.querySelector('table[data-sort-key^="m05:ledger-"]');
  const before = !!(label && ledTable) &&
    (label.compareDocumentPosition(ledTable) & Node.DOCUMENT_POSITION_FOLLOWING) > 0;
  return {
    headButtons: [...head.querySelectorAll('button')].map(b => ({t: b.textContent.trim(), cls: b.className, act: b.dataset.act || ''})),
    /* ⚠️ 2026-09-28：`headButtons` 只覆盖卡头 —— 而「看哪个项目」`TAIL-144` 起**在卡体里**（表格上方）
       ⇒ 查"按钮有没有 `on` 态"必须看**整张卡**，否则那条永远是 ''（实测踩到：报了两条假红）。 */
    cardButtons: [...card.querySelectorAll('button')].map(b => ({t: b.textContent.trim(), cls: b.className, act: b.dataset.act || ''})),
    pickBeforeTables: before,
    pickLabelFound: !!label,
    strip: txt(body.querySelector('.fbar')),
    stripActs: [...body.querySelectorAll('.fbar [data-act]')].map(b => b.dataset.act),
    overflow: {sw: sp.scrollWidth, cw: sp.clientWidth},
    toast: txt(document.querySelector('.toast')),
  };
}
"""


def _click(page, act: str) -> None:
    page.evaluate("""(act) => {
        const v = document.querySelector('#view');
        const card = [...v.querySelectorAll('.card')].find(c => {
          const h = c.querySelector('h4'); return h && h.textContent.indexOf('逐月欠款台账') >= 0; });
        const b = card.querySelector('[data-act="' + act + '"]');
        if (b) b.click();
    }""", act)
    page.wait_for_timeout(350)


def _cls_of(head: dict, act: str) -> str:
    """该按钮现在的 `class`（⚠️ 查**整张卡**：`TAIL-144` 起「看哪个项目」在卡体里，不在卡头）。"""
    for b in head.get("cardButtons", []):
        if b["act"] == act:
            return b["cls"]
    return ""


def check(page, errors: list[str]) -> None:
    """㉚ 台账那排控件（见文件头）。

    ⚠️ **必须先切到 `m05`**：本段是编排件里**最后**一段，前一段（㉗ 四态）把页面留在了 `m09` ——
       而别处（`m09` 的说明行里就有「随「逐月欠款台账」导出」这种字）也含"逐月欠款台账"，
       不切页就会**认错卡**（实测：读到的是 `m09` 那张卡的卡头 ⇒ 三条假红）。
    """
    from _shell_common import goto

    goto(page, "m05")
    out: list[str] = []
    base = page.evaluate(JS_HEAD)
    if base.get("err"):
        errors.append(f"㉚ 找不到台账卡头（{base['err']}）—— 本段全部作废，请先查 `V.m05` 是否还在渲染")
        print(f"   ⛔ ㉚ {base['err']}")
        return

    # ① 控件贴对象：「看哪个项目」在两栏台账**之前**（§2.7）
    ok_pick = bool(base["pickLabelFound"]) and bool(base["pickBeforeTables"])
    out.append(("✅" if ok_pick else "⛔")
               + f"㉚-① 「看哪个项目」在两栏台账**上方**（找到={base['pickLabelFound']} · 在表前={base['pickBeforeTables']}）")
    if not ok_pick:
        errors.append("㉚-① 「看哪个项目」不在两栏台账上方（用户原话：要在右上角选、离那么远）——"
                      "守则 §2.7：控件要贴在它管的那两张表上")

    # ② 卡头只有一个导出入口（§4.4 ＋ 用户 2026-09-13 的裁定）
    hb = base["headButtons"]
    ok_head = len(hb) == 1 and hb[0]["act"] == HEAD_ENTRY
    out.append(("✅" if ok_head else "⛔")
               + f"㉚-② 卡头只有**一个**导出入口（实测 {len(hb)} 个：{' / '.join(b['t'] for b in hb) or '（没有）'}）")
    if not ok_head:
        errors.append(f"㉚-② 台账卡头上有 {len(hb)} 个入口（{', '.join(b['t'] for b in hb)}）——"
                      "用户 2026-09-13 裁定「卡头一个导出入口」，别再把导出件塞回卡头")
    if len({b["t"] for b in hb}) != len(hb):
        errors.append(f"㉚-② 卡头有**同名按钮**：{[b['t'] for b in hb]}（守则 §4.4）")

    # ③ 点开「导出…」⇒ 两个导出**都在同一条面板里**（段② 不再靠 DOM 注入）
    _click(page, HEAD_ENTRY)
    opened = page.evaluate(JS_HEAD)
    strip = opened.get("strip", "")
    acts = opened.get("stripActs", [])
    miss_sec = [x for x in STRIP_SECTIONS if x not in strip]
    need_acts = ("ledExpPjToggle", "ledExpOk", "ledExpCancel", "debtPick", "debtExpAll")
    miss_act = [a for a in need_acts if a not in acts]
    ok_strip = not miss_sec and not miss_act
    out.append(("✅" if ok_strip else "⛔")
               + f"㉚-③ 展开区一条面板里有两个导出、各自的控件都在（缺段={miss_sec or '无'} · 缺控件={miss_act or '无'}）")
    if not ok_strip:
        errors.append(f"㉚-③ 导出面板不全（缺段 {miss_sec} / 缺控件 {miss_act}）——"
                      "用户原话「点按钮后又要跑到最左边选项目」：各导出的**范围必须挨着它自己的动作**")

    # ④ 两个 toggle：点开带 on、再点复原（§5.5 / §4.2）
    #   ⚠️ **先归一化到"收起"**：③ 是把导出面板**开着**的 ⇒ 不先收起，循环里第一下点击就是"关掉"
    #      ⇒ 读到的 `on` 正好相反（实测：报出 2 条假红 ＋ 1 条"收起后仍带 on"）。
    for act, name in TOGGLES:
        if "on" in _cls_of(page.evaluate(JS_HEAD), act).split():
            _click(page, act)
        _click(page, act)
        c1 = _cls_of(page.evaluate(JS_HEAD), act)
        ok_on = "on" in c1.split()
        toast = page.evaluate(JS_HEAD).get("toast", "")
        ok_toast = len(toast) <= 60 and "特殊费用月报表" not in toast
        out.append(("✅" if (ok_on and ok_toast) else "⛔")
                   + f"㉚-④ 点开「{name}」⇒ 按钮带 `on`（实测 cls={c1!r}）· toast {toast[:34]!r}")
        if not ok_on:
            errors.append(f"㉚-④ 点开「{name}」后**按钮自己毫无变化**（cls={c1!r}）——"
                          "守则 §5.5：看着能点的点了必须有明确反馈；用户看不出点上了没有")
        if not ok_toast:
            errors.append(f"㉚-④ 点开「{name}」弹的还是**长机制说明**（{len(toast)} 字：{toast[:40]!r}）——"
                          "守则 §3.4：说明要贴在对象旁（面板里），别用长 toast 顶替")
        _click(page, act)                       # 复原
        c2 = _cls_of(page.evaluate(JS_HEAD), act)
        if "on" in c2.split():
            errors.append(f"㉚-④′ 收起「{name}」后按钮仍带 `on`（cls={c2!r}）—— 状态不真实（§4.2）")
    # 「导出」那个面板要顺手收干净（⛔ 别给后面的段留下展开态）
    page.evaluate("""() => { const b = document.querySelector('[data-act="ledExpCancel"]'); if (b) b.click(); }""")
    page.wait_for_timeout(300)

    # ⑤ 卡头不许横向溢出（§5.9）
    ov = base["overflow"]
    ok_ov = ov["sw"] <= ov["cw"] + 2
    out.append(("✅" if ok_ov else "⛔") + f"㉚-⑤ 卡头没有横向溢出（scrollWidth {ov['sw']} ≤ clientWidth {ov['cw']}）")
    if not ok_ov:
        errors.append(f"㉚-⑤ 卡头横向溢出（sw {ov['sw']} > cw {ov['cw']}）—— 挤出去的那个按钮用户点不到")

    print("㉚ 台账那排控件（贴对象 / 卡头一个入口 / 面板齐 / 点开有反馈）：")
    for line in out:
        print("   " + line)
