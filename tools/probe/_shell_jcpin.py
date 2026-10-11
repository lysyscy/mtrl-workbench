"""壳真机自检 · **㉝ `m11` 合同主表的「行身份区固定」**（`TAIL-180` · `B` 案 · 2026-09-29 用户裁定）。

**它验什么**（守则 §5.9「核心操作与核心数据一眼可见」· §4.2「别让人做错事」）：
  `m11` 合同主表 **20 列 · 330 行**，**4 个可编辑列**（付款方式 / 备注 / 存档号 / 寄回日期）**正好在最右**
  ⇒ 往右滚 855px 去填它们时，**行身份区**（勾选框 ＋ 序号 ＋ 合同日期 ＋ 材料名）必须留在视野里 ——
  否则用户**看不见自己在给哪条合同填**（会填错行；同族 = 月度会大表 `TAIL-175`）。本段量五件事：

  ① **连续前缀严丝合缝**：滚到最右后，前 4 格的左缘依次等于前一格的**右缘**（差 ≤1px）——
     露缝 = 露出被滚走的内容（假信息）· 叠住 = 盖住首列的字；
  ② **数据行与表头同款**（`TAIL-170`-③ 的口径：表头浮着、行里滚走 = 半成品）；
  ③ **钉住的那几格不透明**（`background-color` 不是 `transparent`）—— 否则被滚走的内容会**透出来**；
  ④ **合计行**：首格「合计」也钉（不钉 ⇒ 钉住的那几格左边**露个洞**），且它与后面几格接得上；
  ⑤ ⭐ **隐藏「贸易公司」三列之后要重量**（隐藏会**改剩下的列宽** ⇒ 旧偏移当场过期）——
     本页偏移是**量出来的**（⛔ 不是静态算式，实测列宽随视口变），这条专打"只量一次"的写法；
  ⑥ 顺带证明**这段不是空跑**：表必须**真的能横滚**、**真的有数据行**。

⚠️ 为什么必须在真机：离线判据只能证明"源码里有 `jcApplyPin` 且它量了宽"，**证明不了屏幕上真严丝合缝**
  （`sticky` 的错位 / 露底是它的经典失败模式，且**不报错**）。
⚠️ 本段**只读 ＋ 只滚一下 ＋ 点一次"隐藏列"再点回来**（纯屏幕偏好，不写任何业务数据）。
"""

from __future__ import annotations

#: 只认这张表（`data-sort-key` 是稳定锚）
TBL = 'table[data-sort-key="m11:jc"]'
PINNED = 4          # 勾选框 ＋ 序号 ＋ 合同日期 ＋ 材料名

JS = r"""(arg) => {
  const [sel, n] = arg;
  const tb = document.querySelector(sel);
  if (!tb) return {err: '没找到 `m11` 合同主表（`data-sort-key="m11:jc"` —— 选择器或页变了？）'};
  const tw = tb.closest('.tw');
  if (!tw) return {err: '合同主表不在滚动容器 `.tw` 里'};
  tw.scrollLeft = tw.scrollWidth;                     /* ⛔ 必须先滚到最右：`sticky` 只在"要被滚出去"时才生效 */
  const t = tw.getBoundingClientRect();
  const head = tb.querySelector('thead > tr');
  const heads = head ? [...head.children].slice(0, n) : [];
  const rows = [...tb.querySelectorAll('tbody > tr')];
  const sum = rows.find(tr => tr.className.indexOf('sumrow') >= 0) || null;
  const data = rows.filter(tr => tr !== sum);
  const box = e => { const b = e.getBoundingClientRect();
    return {l: Math.round(b.left - t.left), r: Math.round(b.right - t.left), w: Math.round(b.width)}; };
  const opq = e => { const c = getComputedStyle(e).backgroundColor;
    return !(!c || c === 'transparent' || c === 'rgba(0, 0, 0, 0)'); };
  const cells = tr => tr ? [...tr.children].slice(0, n) : [];
  /* ⚠️ 合计行的首格「合计」是 `colspan=1`（`sumRowOf` 默认），但**它自己也要钉**（见④） */
  return {
    cw: tw.clientWidth, sw: tw.scrollWidth,
    dataN: data.length, sumN: sum ? 1 : 0,
    head: heads.map(box), headFl: heads.map(e => e.classList.contains('fl')),
    row: cells(data[0]).map(box), rowFl: cells(data[0]).map(e => e.classList.contains('fl')),
    opaque: heads.map(opq),
    sumCells: cells(sum).map(box), sumFl: cells(sum).map(e => e.classList.contains('fl')),
    sumLead: sum && sum.children[0] ? (sum.children[0].innerText || '').trim().slice(0, 4) : '',
  };
}"""


def _chain(what: str, boxes: list[dict], errors: list[str], need_fl: list[bool] | None = None) -> None:
    """逐格核「后一格的左缘 == 前一格的右缘」（连续前缀严丝合缝）＋ `fl` 挂没挂。"""
    bad = [(i, boxes[i]["l"] - boxes[i - 1]["r"]) for i in range(1, len(boxes))]
    bad = [(i, g) for i, g in bad if abs(g) > 1]
    print(("   ⛔" if bad else "   ✅")
          + f"㉝-{what} 前 {len(boxes)} 格「左缘(右缘)」链："
          + " → ".join(f"{b['l']}({b['r']})" for b in boxes))
    for i, gap in bad:
        errors.append(f"㉝-{what} 第 {i + 1} 格与前一格差 {gap:+d}px"
                      "（正 = 露缝，露出被滚走的内容；负 = 叠住前一列的字）—— 偏移与列宽对不上了")
    if need_fl is not None and not all(need_fl):
        errors.append(f"㉝-{what} 有格子没挂 `fl`（{need_fl}）—— 那就没钉住")


def check(page, errors: list[str]) -> None:
    """㉝ `m11` 行身份区固定（见文件头）。"""
    from _shell_common import goto

    goto(page, "m11")
    page.wait_for_timeout(200)
    d = page.evaluate(JS, [TBL, PINNED])
    print("㉝ m11 合同主表的行身份区固定（勾选框 ＋ 序号 ＋ 合同日期 ＋ 材料名）：")
    if d.get("err"):
        errors.append(f"㉝ {d['err']} —— 本段全部作废，请先查 `V.m11` 是否还在渲染那张表")
        print(f"   ⛔ {d['err']}")
        return

    # ⑥ 先证"这段不是空跑"
    if not (d["sw"] > d["cw"] + 2):
        errors.append(f"㉝-⑥ 合同主表没有横向溢出（{d['sw']} vs {d['cw']}）⇒ 本段**验不了**"
                      "（「钉住行身份区」只在有横滚时才有意义）—— 别让它静默通过")
        print(f"   ⛔ ㉝-⑥ 表没有横滚（{d['sw']} vs {d['cw']}）⇒ 本段验不了")
        return
    if d["dataN"] < 1:
        errors.append("㉝-⑥ 合同主表没有数据行 ⇒ 行身份区吸附验不了（空态时页面走的是另一条路）")
    print(f"   ✅㉝-⑥ 表真的能横滚（内容 {d['sw']} > 容器 {d['cw']}）· 数据行 {d['dataN']} · "
          f"合计行 {d['sumN']}")

    if len(d["head"]) < PINNED:
        errors.append(f"㉝ 合同主表结构不像预期（表头只有 {len(d['head'])} 格）")
        return

    # ① 表头连续前缀
    _chain("①", d["head"], errors, d["headFl"])
    h0 = d["head"][0]
    if abs(h0["l"]) > 1:
        errors.append(f"㉝-① 首格没贴左缘（左 = {h0['l']}）")
    print(f"   ✅㉝-① 表头 `fl` 挂法：{d['headFl']}（第 1 格是原型自带的 `TAIL-170`-③）")

    # ② 数据行与表头同款
    if len(d["row"]) >= PINNED:
        _chain("②", d["row"], errors, d["rowFl"])
        off = max(abs(d["row"][i]["l"] - d["head"][i]["l"]) for i in range(PINNED))
        print(("   ✅" if off <= 1 else "   ⛔")
              + f"㉝-② 数据行与表头逐格同款（最大偏差 {off}px）· 行 `fl` = {d['rowFl']}")
        if off > 1:
            errors.append(f"㉝-② 数据行与表头的钉位差 {off}px —— 表头浮着、行里那几格滚走了")
    else:
        errors.append(f"㉝-② 数据行格子太少（{len(d['row'])}）—— 结构变了")

    # ③ 不透明（否则被滚走的内容透出来）
    if not all(d["opaque"]):
        errors.append(f"㉝-③ 有钉住的格是**透明**的（{d['opaque']}）—— 被滚走的内容会从底下透出来")
    print(("   ✅" if all(d["opaque"]) else "   ⛔") + f"㉝-③ 钉住的格都不透明：{d['opaque']}")

    # ④ 合计行首格也钉（否则左边露个洞）
    if d["sumN"] and len(d["sumCells"]) >= PINNED:
        lead, s1 = d["sumCells"][0], d["sumCells"][1]
        ok = abs(lead["l"]) <= 1 and s1["l"] - lead["r"] <= 1 and d["sumFl"][0]
        print(("   ✅" if ok else "   ⛔")
              + f"㉝-④ 合计行首格「{d['sumLead']}」也钉住（左 = {lead['l']} · `fl` = {d['sumFl'][0]} · "
                f"宽 {lead['w']}）")
        if not ok:
            errors.append(f"㉝-④ 合计行首格没钉（左 = {lead['l']} · `fl` = {d['sumFl'][0]}）"
                          "—— 横滚时「合计」被滚走，钉住那几格左边露个洞")
    else:
        errors.append("㉝-④ 找不到可判的合计行（`sumRowOf` 那一路）—— 结构变了要重新核这一段")

    # ⑤ 隐藏「贸易公司」三列之后必须**重量**（隐藏会改剩下的列宽 ⇒ 旧偏移当场过期）
    # ⚠️ 先收掉**上一段留下的浮层**（2026-09-29 实测：跑在前面的某段留了个「删除确认」没关
    #    ⇒ `#jcTradeBtn` 被它挡住，Playwright 报 `intercepts pointer events` 连重试 57 次）。
    #    ⛔ 不静默：收掉了就打印出来（那是**探针卫生**问题，不是本页的问题 —— 但也别让它糊过去）。
    left = page.evaluate("""() => {
      const n = document.querySelectorAll('.mf [data-act="closeModal"]').length;
      document.querySelectorAll('.mf [data-act="closeModal"]').forEach(b => b.click());
      /* ⚠️ `bootErrorBanner()` 那条横幅是 `position:fixed;top:0` ⇒ 它**盖住页首那一带、还吃掉点击**
         （守则 §5.5 的反例同族：「提示条盖住可点区」）。它只该在"启动取数失败"时出现 ——
         跑到这里多半是**前面某段（㉗ 故意拦断一路）留下的残留** ⇒ 本段按它自己写的下一步做（**刷新一次**）。 */
      const banner = [...document.querySelectorAll('.tip.dg')]
        .some(e => getComputedStyle(e).position === 'fixed');
      return {n, banner};
    }""")
    if left["n"]:
        print(f"   ⚠️㉝-⑤ 先收掉上一段留下的浮层（{left['n']} 个「取消」）—— 否则下面那枚按钮点不着")
        page.wait_for_timeout(250)
    if left["banner"]:
        print("   ⚠️㉝-⑤ 场上残留着**启动失败横幅**（`position:fixed;top:0`，前面那段拦断过一路留下的）"
              "⇒ 本段**就地摘掉它**再点（⛔ 不刷新：那条路在冒烟时序里不稳；本段验的是「钉列」）"
              "（⚠️ 横幅本身盖住页首、连卡头按钮都点不到 —— 那是**全局件**的账，已登记 `TAIL-182`）")
        page.evaluate("""() => { [...document.querySelectorAll('.tip.dg')]
          .filter(e => getComputedStyle(e).position === 'fixed').forEach(e => e.remove()); }""")
        page.wait_for_timeout(200)
    if not page.query_selector("#jcTradeBtn"):
        errors.append("㉝-⑤ 找不到「隐藏贸易公司列」按钮（`#jcTradeBtn`）—— 本段验不了")
        return
    # ⚠️ 两次都**按选择器**点（⛔ 不缓存 `ElementHandle`）：`jcToggleTrade` 会 `render()` 重建整张表
    #    ⇒ 缓存下来的那个句柄当场 detach（实测：第二次点击报 `Element is not attached to the DOM`）。
    page.click("#jcTradeBtn")
    page.wait_for_timeout(450)
    d2 = page.evaluate(JS, [TBL, PINNED])
    page.click("#jcTradeBtn")                     # ⭐ 点回来：纯屏幕偏好，⛔ 别给后面段留个「藏着列」的页
    page.wait_for_timeout(450)
    if not d2 or d2.get("err") or len(d2.get("head") or []) < PINNED:
        errors.append("㉝-⑤ 隐藏三列后量不出结构 —— 本段验不了")
        return
    _chain("⑤", d2["head"], errors, d2["headFl"])
    hid = abs(d2["head"][3]["w"] - d["head"][3]["w"]) > 1 or abs(d2["sw"] - d["sw"]) > 1
    print(("   ✅" if hid else "   ⚠️")
          + f"㉝-⑤ 切换贸易公司三列后**重量**：表内容 {d['sw']} ⇒ {d2['sw']}（列宽确实改变 ⇒ "
            f"偏移必须重量；链 = {[c['l'] for c in d2['head']]}）")
    if not hid:
        errors.append("㉝-⑤ 切换三列后表的宽度没变 ⇒ 本段没能真的验到「重量」这条（换一种隐藏机制了？）")
