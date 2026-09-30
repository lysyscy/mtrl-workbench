"""壳真机自检 · ㉟ **表级虚拟滚动：本页内刷新不跳滚动**（`TAIL-64` P5-a · 2026-09-30）。

**它验什么**：`P5-a` 把虚拟滚动从"整页一张大表"下沉成"**每张表自己**"（`m08` 是试点页）。
换的是"**谁在滚 / 谁被重画**"，而这条路上有两个**只有真机才知道**的老毛病（都犯过、都被用户报过）：

  ① **本页内刷新跳回顶部**（`TAIL-66` 用户报障原话：「点一下勾选，列表就跳回最上面」）——
     `render()` 会用新 `innerHTML` **整体重建**那张表 ⇒ 承接滚动的 `.tw` 连同它的 `scrollTop` 一起没了
     ⇒ 必须"**先记后还**"。P5-a 换了容器（从"整页第一个 `.tw`"换成"**这张表自己的 `.tw`**"）
     ⇒ 还原的对象**必须跟着换**（⛔ 还错了对象不会报错，只会**悄悄跳回顶部**）。
  ② **重画把用户的手势打断**（每 tick 只剩 ~5px）—— 那条由 `⑧ m08` 的滚轮段守（真手势），本段不重复。

  ⇒ 本段只做一件真机上才成立的事：**滚到中段 ⇒ 触发一次本页内刷新 ⇒ 滚动位置与窗口内容必须还在原地**。

⚠️ **本页内刷新怎么触发**：直接调壳自己的 `render()` —— 那正是"勾选 / 改筛选 / 落库后重画"走的**同一条路**
   （⛔ 不是另造一条：另造一条就证明不了真正的刷新路径）。
⚠️ **只读 ＋ 只滚一下**：不点写动作、不改数据、不下载。
⚠️ **不是空跑**：先断言"真的滚下去了（`st > 0`）"且"DOM 只挂窗口行";否则本段**判红**（⛔ 不许静默通过）。
"""

from __future__ import annotations

#: 表级虚拟滚动认领过的表（`P5-a` 起：带 `data-vs` 的 `tbody`）—— 用它当锚，⛔ 不用 `:first-child`（换页就错）
VS_TB = 'tbody[data-vs]'

_SCROLL_HALF = r"""(sel) => {
  const tb = document.querySelector(sel);
  if (!tb) return {err: '页上找不到带 `data-vs` 的表体 —— 表级虚拟滚动没有认领任何表（标记丢了？）'};
  const tw = tb.closest('.tw');
  if (!tw) return {err: '那张表不在 `.tw` 里（滚动容器变了？）'};
  tw.scrollTop = Math.round((tw.scrollHeight - tw.clientHeight) * 0.5);
  return {st: Math.round(tw.scrollTop), domN: tb.children.length};
}"""

_MEASURE = r"""(sel) => {
  const tb = document.querySelector(sel);
  const tw = tb && tb.closest('.tw');
  if (!tb || !tw) return {err: '刷新后那张表 / 它的 `.tw` 不见了'};
  const trs = [...tb.children].filter(tr => !tr.classList.contains('vsp') && tr.className.indexOf('sumrow') < 0);
  const first = trs[0] ? (trs[0].innerText || '').replace(/\s+/g, ' ').trim().slice(0, 26) : '';
  return {st: Math.round(tw.scrollTop), domN: tb.children.length, first: first,
          claimed: (typeof VS_TS !== 'undefined') ? VS_TS.length : -1};
}"""

#: ① 点一次**可排表头**（走壳自己的 `headSort`）＋ 贴底 —— ⛔ **不在同一步里读**：
#:    重画走的是 `scroll` 事件 ＋ `rAF` ⇒ 同一个同步 `evaluate` 里读到的还是**重画前**的窗口
#:    （2026-09-30 第一版就是这么读到"最后一行不是合计行"的**假红**）。
_SORT_AND_BOTTOM = r"""(sel) => {
  const tb = document.querySelector(sel);
  const tbl = tb && tb.closest('table');
  if (!tbl) return {err: '找不到那张表'};
  const th = tbl.querySelector('thead th.srt');
  if (!th) return {err: '这张表没有可排表头（`th.srt`）—— 排序入口没了？'};
  th.click();
  /* ⚠️⚠️ **必须重新取元素**：`headSort` 会 `render()` ⇒ 那张表连同 `.tw` **整体换新** ⇒
     对着**旧**（已脱离文档的）元素设 `scrollTop` 是**空动作**（第一版就是这么假红的）。 */
  const tb2 = document.querySelector(sel);
  const tw2 = tb2 && tb2.closest('.tw');
  if (!tw2) return {err: '重画后找不到 `.tw`'};
  tw2.scrollTop = tw2.scrollHeight;
  return {key: th.getAttribute('data-tk') || '', st: Math.round(tw2.scrollTop)};
}"""

#: ② 等 rAF 画完再读：贴底后**最后一行必须是合计行**
_READ_BOTTOM = r"""(sel) => {
  const tb = document.querySelector(sel);
  if (!tb) return {err: '那张表不见了'};
  const trs = [...tb.children].filter(tr => !tr.classList.contains('vsp'));
  const last = trs[trs.length - 1];
  return {first: (trs[0] ? (trs[0].innerText || '') : '').replace(/\s+/g, ' ').trim().slice(0, 20),
          lastTxt: last ? (last.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40) : '',
          lastIsSum: !!(last && last.className.indexOf('sumrow') >= 0)};
}"""


def check(page, errors: list[str]) -> None:
    """㉟ 表级虚拟滚动：本页内刷新不跳滚动（见文件头）。"""
    from _shell_common import goto

    goto(page, "m08")
    page.wait_for_timeout(250)
    d0 = page.evaluate(_SCROLL_HALF, VS_TB)
    print("㉟ 表级虚拟滚动（`m08` 试点）：本页内刷新不跳滚动")
    if d0.get("err"):
        errors.append(f"㉟ {d0['err']}")
        print(f"   ⛔ {d0['err']}")
        return
    page.wait_for_timeout(300)                      # 让 rAF 把窗口画到位
    a = page.evaluate(_MEASURE, VS_TB)
    ok_scrolled = a["st"] > 0
    print(("   ✅" if ok_scrolled else "   ⛔")
          + f"㉟-① 先证明本段不是空跑：真滚到中段（`scrollTop` = {a['st']}）· DOM 挂 {a['domN']} 行")
    if not ok_scrolled:
        errors.append(f"㉟-① 没滚下去（`scrollTop` = {a['st']}）⇒ 本段**验不了**"
                      "（「刷新不跳滚动」这件事只在「本来就在中段」时才有意义）—— ⛔ 别让它静默通过")
        return
    if not (10 < a["domN"] < 300):
        errors.append(f"㉟-① DOM 里挂了 {a['domN']} 行 —— 表级虚拟滚动**没生效**（应当只挂一个窗口）")
    if a["claimed"] < 1:
        errors.append(f"㉟-① 表级实例数 = {a['claimed']}（应 ≥ 1）—— `data-vs` 的表没被认领")

    # ⭐ 触发**本页内刷新**（勾选 / 改筛选 / 落库后重画走的就是这一条）
    page.evaluate("() => render()")
    page.wait_for_timeout(400)
    b = page.evaluate(_MEASURE, VS_TB)
    if b.get("err"):
        errors.append(f"㉟-② 刷新后：{b['err']}")
        print(f"   ⛔ {b['err']}")
        return

    ok_keep = b["st"] >= a["st"] * 0.8               # 允许被钳一点（贴底时应当不变），但⛔ 不许归零
    print(("   ✅" if ok_keep else "   ⛔")
          + f"㉟-② 本页内刷新后**滚动位置还在**（{a['st']} → {b['st']}）—— 归零 = 用户报过的「点一下跳回顶部」")
    if not ok_keep:
        errors.append(f"㉟-② 本页内刷新把滚动位置弄丢了（{a['st']} → {b['st']}）—— "
                      "还原的对象不是**这张表自己的** `.tw`（P5-a 换容器时最容易错的一处）")

    ok_same = a["first"] != "" and b["first"] == a["first"]
    print(("   ✅" if ok_same else "   ⛔")
          + f"㉟-③ 窗口内容还在原地（首行「{a['first']}」→「{b['first']}」）")
    if not ok_same:
        errors.append(f"㉟-③ 刷新后首行变了（「{a['first']}」→「{b['first']}」）—— "
                      "窗口没按 `keep` 的位置重算（画面会「跳」到别处，而**不报错**）")

    # ㉟-④ ⭐ 排序之后，**合计行必须仍在表尾**（`TAIL-94` 那条铁律：最后一行是合计行，⛔ 不能是垫高行）
    page.evaluate("() => render()")                 # 先回原序（把上一次状态清干净）
    page.wait_for_timeout(250)
    s = page.evaluate(_SORT_AND_BOTTOM, VS_TB)      # ① 点表头 ＋ 贴底（同一拍里**不读**）
    if s.get("err"):
        errors.append(f"㉟-④ {s['err']}")
        print(f"   ⛔ {s['err']}")
        return
    page.wait_for_timeout(400)                      # ② 等 `scroll` → rAF 那一次重画落下去
    r = page.evaluate(_READ_BOTTOM, VS_TB)
    if r.get("err"):
        errors.append(f"㉟-④ {r['err']}")
        print(f"   ⛔ {r['err']}")
        return
    print(("   ✅" if r["lastIsSum"] else "   ⛔")
          + f"㉟-④ 排序后贴底：最后一行仍是**合计行**（表尾「{r['lastTxt'][:24]}」）"
          f"· 排序键 = {s['key'] or '（无）'} · 现首行「{r['first']}」")
    if not r["lastIsSum"]:
        errors.append(f"㉟-④ 排序后贴底，最后一行不是合计行（「{r['lastTxt']}」）—— "
                      "虚拟化的**贴底钳制**必须让合计行如约出现（⛔ 不能留一个空垫高行在表尾）")
