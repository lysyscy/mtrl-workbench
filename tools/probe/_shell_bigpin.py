"""壳真机自检 · **㉜ 月度会大表的「首列区固定」**（`TAIL-175` · 2026-09-29）。

**它验什么**（守则 §5.9「核心操作与核心数据一眼可见」· §4.2「别让人做错事」）：
  大表是 **20 列横表**（`min-width:1620px`）⇒ 往右填手填那 6 列（机械费测算 / 合同价 / 产值累计…，
  正好落在最右）时，**首列区（序号 ＋ 项目名称）必须留在视野里** —— 否则用户**看不见自己在给哪个
  项目填**（会填错行）。⇒ 本段把那三件事量到位：

  ① **表头**第 1 行的前两格钉在左缘，且**第 2 格紧接第 1 格右缘**（有缝 = 露底、叠住 = 盖字）；
  ② **数据行**前两格同款（`TAIL-170`-③ 的"表头与数据行同进同退"——大表也适用）；
  ③ **合计行**首格是 `colspan="2"` ⇒ 它**一格就该盖住这两列**（宽度 == 前两列之和）；
  ④ ⛔ **表头第 2 行不许被钉**（两行表头，第 2 行里没有「序号 / 项目名称」——
     挂错就把「焊材累计」钉住了，那正是"钉错列"的典型症状）；
  ⑤ 顺带证明**这段不是空跑**：表必须**真的能横滚**（`scrollWidth > clientWidth`），
     且大表**真的有数据行**（0 行时页面走的是空态 —— 那时本段无所谓对错，但**不该静默通过**）。

⚠️ 为什么必须在真机：离线判据只能证明"源码里给那两格挂了 `fl` / 写了 `left:calc(…)"，
   **证明不了屏幕上两个格子真的严丝合缝**（`sticky` 的错位是它的经典失败模式，且**不报错**）。
⚠️ 本段**只读 ＋ 只滚一下**（改 `scrollLeft`，不改数据、不点写动作、不下载）。
"""

from __future__ import annotations

#: 只认这张表（`data-sort-key` 是稳定锚；m07 页上还有收发结存 / 提取两张表）
BIG = 'table[data-sort-key="m07:bigtable"]'

JS = r"""(sel) => {
  const tb = document.querySelector(sel);
  if (!tb) return {err: '没找到大表（`data-sort-key="m07:bigtable"` —— 选择器或页变了？）'};
  const tw = tb.closest('.tw');
  if (!tw) return {err: '大表不在滚动容器 `.tw` 里'};
  const t = tw.getBoundingClientRect();
  const box = e => { const b = e.getBoundingClientRect();
    return {l: Math.round(b.left - t.left), w: Math.round(b.width), t: Math.round(b.top - t.top)}; };
  const hrows = [...tb.querySelectorAll('thead tr')];
  const brows = [...tb.querySelectorAll('tbody tr')];
  const sum = brows.find(tr => tr.className.indexOf('sumrow') >= 0);
  const data = brows.filter(tr => tr !== sum);
  const h0 = hrows[0] ? [...hrows[0].children] : [];
  const h1 = hrows[1] ? [...hrows[1].children] : [];
  const r0 = data[0] ? [...data[0].children] : [];
  return {
    cw: tw.clientWidth, sw: tw.scrollWidth, sl: Math.round(tw.scrollLeft),
    headN: hrows.length, dataN: data.length, sumN: sum ? 1 : 0,
    head: h0.slice(0, 2).map(box), headCls: h0.slice(0, 2).map(e => e.className),
    head2: h1.length ? box(h1[0]) : null, head2Txt: h1.length ? (h1[0].innerText || '').trim().slice(0, 8) : '',
    row: r0.slice(0, 2).map(box), rowCls: r0.slice(0, 2).map(e => e.className),
    sumCell: sum && sum.children[0] ? box(sum.children[0]) : null,
    sumCs: sum && sum.children[0] ? sum.children[0].colSpan : 0,
  };
}"""


def check(page, errors: list[str]) -> None:
    """㉜ 大表首列区固定（见文件头）。"""
    from _shell_common import goto

    goto(page, "m07")
    # ⛔ 必须**先滚到最右**：`sticky` 只在"该格本来要被滚出去"时才生效 ⇒ 不滚 = 量的是"没吸附"的位置。
    page.evaluate("(sel) => { const tw = document.querySelector(sel).closest('.tw');"
                  " tw.scrollLeft = tw.scrollWidth; }", BIG)
    page.wait_for_timeout(350)
    d = page.evaluate(JS, BIG)
    print("㉜ 大表首列区固定（序号 ＋ 项目名称）：")
    if d.get("err"):
        errors.append(f"㉜ {d['err']} —— 本段全部作废，请先查 `V.m07` 是否还在渲染那张表")
        print(f"   ⛔ {d['err']}")
        return

    # ⑤ 先证"这段不是空跑"
    ok_over = d["sw"] > d["cw"] + 2
    print(("   ✅" if ok_over else "   ⛔") + f"㉜-⑤ 大表真的能横滚（内容 {d['sw']} > 容器 {d['cw']}）"
          f"· 数据行 {d['dataN']} · 表头 {d['headN']} 行")
    if not ok_over:
        errors.append(f"㉜-⑤ 大表没有横向溢出（{d['sw']} vs {d['cw']}）⇒ 本段**验不了**"
                      "（「钉住首列」这件事只在有横滚时才有意义）—— 别让它静默通过")
    if d["dataN"] < 1:
        errors.append("㉜-⑤ 大表没有数据行 ⇒ 首列区吸附验不了（空态时页面走的是另一条路）")

    if len(d["head"]) < 2 or len(d["row"]) < 2:
        errors.append(f"㉜ 大表结构不像预期（表头前两格 {len(d['head'])} / 数据行前两格 {len(d['row'])}）")
        return

    h0, h1 = d["head"][0], d["head"][1]
    r0, r1 = d["row"][0], d["row"][1]

    # ① 表头：首格贴左缘；第 2 格紧接它右缘
    ok_h0 = abs(h0["l"]) <= 1
    print(("   ✅" if ok_h0 else "   ⛔") + f"㉜-① 表头「序号」钉在左缘（左 = {h0['l']}，宽 {h0['w']}）"
          f"· class = {d['headCls'][0]!r}")
    if not ok_h0:
        errors.append(f"㉜-① 表头「序号」没钉住（左 = {h0['l']}，应为 0）—— 横滚时首列跟着跑了")
    gap_h = h1["l"] - (h0["l"] + h0["w"])
    ok_h1 = abs(gap_h) <= 1
    print(("   ✅" if ok_h1 else "   ⛔") + f"㉜-①′ 表头「项目名称」紧接首列右缘（左 = {h1['l']}，"
          f"首列右缘 = {h0['l'] + h0['w']}，差 {gap_h:+d}px）· class = {d['headCls'][1]!r}")
    if not ok_h1:
        errors.append(f"㉜-①′ 表头第 2 格与首列差 {gap_h:+d}px"
                      f"（正 = 露缝露出被滚走的内容；负 = 叠住首列的字）—— 偏移算式与列宽对不上了")

    # ② 数据行：与表头同进同退
    ok_r = abs(r0["l"]) <= 1 and abs(r1["l"] - (r0["l"] + r0["w"])) <= 1
    print(("   ✅" if ok_r else "   ⛔") + f"㉜-② 数据行前两格同款（序号 左 = {r0['l']}；"
          f"项目名称 左 = {r1['l']}，首列右缘 = {r0['l'] + r0['w']}）")
    if not ok_r:
        errors.append(f"㉜-② 数据行只钉了表头没钉行（序号 左 = {r0['l']} / 项目名称 左 = {r1['l']}）"
                      "—— 横滚时表头浮着、行里那两格滚走了（`TAIL-170`-③ 那条口径）")

    # ③ 合计行首格（colspan=2）一格就该盖住这两列
    sc = d["sumCell"]
    if sc is None:
        errors.append("㉜-③ 大表没有合计行（`sumRowOf` 那一路）—— 合计行首格本来就是`colspan=2`，"
                      "少钉它 ⇒ 横滚时「合计」两个字会被滚走")
    else:
        want = h0["w"] + h1["w"]
        ok_s = d["sumCs"] == 2 and abs(sc["l"]) <= 1 and abs(sc["w"] - want) <= 2
        print(("   ✅" if ok_s else "   ⛔") + f"㉜-③ 合计行首格钉住且**盖住前两列**（colspan = {d['sumCs']}，"
              f"左 = {sc['l']}，宽 {sc['w']} vs 前两列之和 {want}）")
        if not ok_s:
            errors.append(f"㉜-③ 合计行首格没盖住前两列（colspan {d['sumCs']} · 左 {sc['l']} · "
                          f"宽 {sc['w']} vs {want}）—— 要么漏钉、要么多给后面那格挂了 `fl`")

    # ④ 表头第 2 行⛔ 不许被钉（它里面没有「序号 / 项目名称」）
    h2 = d["head2"]
    if h2 is None:
        errors.append("㉜-④ 找不到表头第 2 行 —— 大表应当是**两行表头**，结构变了要重新核这一段")
    else:
        ok_2 = abs(h2["l"]) > 1
        print(("   ✅" if ok_2 else "   ⛔") + f"㉜-④ 表头第 2 行**没有被钉**（首格「{d['head2Txt']}」"
              f"左 = {h2['l']}，应 ≠ 0 —— 它里面没有「序号 / 项目名称」）")
        if not ok_2:
            errors.append(f"㉜-④ 表头第 2 行也被钉在左缘了（首格「{d['head2Txt']}」左 = {h2['l']}）"
                          "—— 那是**钉错列**：第 2 行里根本没有「序号 / 项目名称」")
