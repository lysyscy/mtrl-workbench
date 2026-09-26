"""壳真机自检 · **㉑ 通用浮层**（`TAIL-109` 立 · `TAIL-110` 收口 · 2026-09-26）。

**它验什么**（三件，都只在真机看得见）：
  ① **浮层真的被提升为 `fixed`** —— 也就是 `placePops()` 生效了（离线只能查"钩子在不在"）；
  ② **位置跟着触发按钮**（浮层顶 ≈ 按钮底 ＋ 5）—— 提升为 `fixed` 之后若不重算坐标，浮层会**粘在原地**；
  ③ ⭐ **点命中**：**按钮在窗口里**时，浮层最下面那个可点元素必须**也看得见、点得到**
     （`document.elementFromPoint` 落回浮层内）—— ⚠️ 这是**唯一**能证明"没被卡片 `overflow:hidden` 裁掉"
     的判法（几何算法对 `fixed` 会误判：它早就不受那个 `overflow` 约束了）。

⚠️ **按钮本身在折叠线以下**（如 `m05` 的两个图例时间选择器）⇒ 浮层也在屏外**属正常**（滚过去就能用）
   —— 那几处只判 ①（`fixed`），不判"点得到"（否则就是假红）。**判词不许用"看不见"当失败**。

⚠️ 本机坑（`_shell_smoke.py` 文件头那两条）同样适用；⚠️ **`click()` 会触发 `render()`** ⇒ 按钮与锚
   都要**每轮从新 DOM 重新查**（旧句柄的 `parentNode` 已断，`closest()` 返回 null —— 第一版就是这么全空的）。
"""

from __future__ import annotations

#: 有「时间选择器」的页（`tmBtn` 的调用点分布）
PAGES: tuple[str, ...] = ("m03", "m04", "m05", "m07", "m08", "m09")

MEASURE = """
() => {
  const v = document.querySelector('#view');
  const keys = [...v.querySelectorAll('[data-act="mpToggle"]')]
      .map(x => ({act: 'mpToggle', id: x.dataset.id || ''}));
  const find = (act, id) => v.querySelector('[data-act="' + act + '"]' + (id ? '[data-id="' + id + '"]' : ''));
  const out = [];
  for (const k of keys) {
    const b = find(k.act, k.id);
    if (!b) continue;
    /* ⚠️ 只认**整个按钮都在窗口里**（部分露出时，浮层合理地落在屏外 ⇒ 不该判"点不到"，那是假红） */
    const triggerInView = (() => { const r = b.getBoundingClientRect();
      return r.top >= 0 && r.bottom <= innerHeight; })();
    const triggerBottom = Math.round(b.getBoundingClientRect().bottom);
    b.click();
    const b2 = find(k.act, k.id);
    const wrap = b2 && b2.closest('.pjwrap');
    const panel = wrap ? wrap.querySelector(':scope > .pjpop') : null;
    if (!panel) { out.push({id: k.id, err: '浮层没开或没挂 pjpop'}); if (b2) b2.click(); continue; }
    const r = panel.getBoundingClientRect();
    const items = [...panel.querySelectorAll('button,input')].filter(x => x.offsetParent !== null);
    /* ⚠️⚠️ 判词只认「**面板可见区里**最下面那个可点元素」：
       ① 面板自己有 `overflow-y:auto` ⇒ 排在可见区**之外**的项是**滚一下就有**的（正常，⛔ 不算被裁）；
       ② 被卡片裁的病征是：**明明在面板自己的盒子（可见区）里，却点不到**（`elementFromPoint` 落空）。 */
    const visTop = Math.max(r.top, 0), visBottom = Math.min(r.bottom, innerHeight);
    const inside = items.filter(x => { const q = x.getBoundingClientRect();
      return q.top >= visTop - 1 && q.bottom <= visBottom + 1; });
    const probe = inside[inside.length - 1] || null;
    let hit = null, pr = null;
    if (probe) { pr = probe.getBoundingClientRect();
                 hit = document.elementFromPoint(pr.left + 3, pr.top + pr.height / 2); }
    const desc = el => el ? (el.tagName + '.' + String(el.className || '').slice(0, 18)
                              + (el.dataset && el.dataset.act ? '[' + el.dataset.act + ']' : '')) : 'null';
    out.push({id: k.id, pos: getComputedStyle(panel).position,
              top: Math.round(r.top), triggerBottom: triggerBottom, triggerInView: triggerInView,
              items: items.length, visible: inside.length, scrolls: panel.scrollHeight > panel.clientHeight + 1,
              probeHittable: probe ? !!(hit && panel.contains(hit)) : null,
              probeEl: desc(probe), hitEl: desc(hit),
              probeBottom: pr ? Math.round(pr.bottom) : null, panelBottom: Math.round(r.bottom)});
    if (b2) b2.click();                       /* 关掉（按钮是刚查的 ⇒ 还在 DOM 里） */
  }
  return out;
}
"""


def check(page, errors: list[str]) -> None:
    """逐页开「时间选择器」，量 `fixed` / 跟着按钮 / 末项点得到。"""
    from _shell_common import goto

    total = 0
    for key in PAGES:
        goto(page, key)
        rows = page.evaluate(MEASURE)
        for g in rows:
            total += 1
            if g.get("err"):
                errors.append(f"㉑ {key} 时间选择器 {g.get('id')}：{g['err']}"
                              " —— 浮层没挂 `pjpop`/没被 `placePops` 接管（`TAIL-110`）")
                continue
            if g["pos"] != "fixed":
                errors.append(f"㉑ {key} 时间选择器 {g['id']}：位置是 {g['pos']}，"
                              "**没有**被 `placePops` 提升为 `fixed` ⇒ 会被卡片 `overflow:hidden` 裁"
                              "（`TAIL-109`/`TAIL-110`）")
            if abs(g["top"] - (g["triggerBottom"] + 5)) > 8:
                errors.append(f"㉑ {key} 时间选择器 {g['id']}：浮层顶 {g['top']} 与按钮底 "
                              f"{g['triggerBottom']} ＋ 5 对不上 ⇒ 它在**粘在原地**、没跟着按钮")
            if g["triggerInView"] and g["visible"] and not g["probeHittable"]:
                errors.append(f"㉑ {key} 时间选择器 {g['id']}：按钮在窗口里、浮层可见区里有 "
                              f"{g['visible']} 项，**最下面那一项却点不到** —— 被裁了 / 被盖住了？"
                              f"（探测元素={g['probeEl']} 底={g['probeBottom']} · 浮层底={g['panelBottom']} · "
                              f"命中的却是 {g['hitEl']}）")
            print(f"  ㉑ {key} {g['id']}: pos={g['pos']} 顶={g['top']} 按钮底={g['triggerBottom']} "
                  f"项={g['items']} 可见={g['visible']} 会滚={g['scrolls']} 点得到={g['probeHittable']} "
                  f"· 探测={g['probeEl']}(底{g['probeBottom']}/浮层底{g['panelBottom']}) · 命中={g['hitEl']}")
    print(f"  ㉑ 通用浮层：逐页开了 {total} 个时间选择器（`PAGES`={len(PAGES)} 页）")
