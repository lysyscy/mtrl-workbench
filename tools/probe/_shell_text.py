"""壳真机自检 · **㉕ 上屏文案里不许有内部编号 / 开发话术**（`TAIL-117` 批次 2 · 2026-09-27）。

**它验什么**（守则 §2.5 用业务术语 · §3.1 内部编号不上屏 · §3.3 内部黑话 · §3.6 开发态标识）：
  ⭐ 把 **16 屏逐页走一遍**，读**页面正文（含默认折叠的 `<details>`）＋ 顶栏 ＋ 所有悬停 `title`**，
  命中断言：`API-0x` / `DEV-x` / `ENT-xx` / `OPEN-x` / `REQ-x` / `TAIL-nn` / 「模拟值 / 模拟今天 /
  原型态 / 原型演示 / 虚构」⇒ 报出「哪一页 · 哪一处 · 命中什么 · 上下文」。

⭐ **为什么这一半必须在真机**（离线那半是 `backend/tests/test_ux_text.py` 的精确墓碑）：
  离线要真想"全面扫"，就得先分清**字符串字面量 / `//` 注释 / 块注释 / HTML 注释 / 正则字面量** ——
  本批次实测：手写词法状态机被这四样接连带偏，报出 130 多条**假阳性**（把注释里的 `TAIL-94` 也算成上屏）。
  ⇒ 离线只钉"整串墓碑"，**"界面上到底有没有"交给真机读 DOM**（所见即所得，零假阳性）。

⚠️ 本件**不判** `§节号`：用户 2026-09-27 裁定 `B` —— 口径说明里保留《说明书》节号。
⚠️ 扫描用 `textContent`（**含折叠区**）而不是 `innerText`：折叠 ≠ 不存在，⛔ 别用"反正收起来了"当豁免。
⭐ **但悬停 `title` 另算**（守则 §5.8「换地方，不是删掉」）：悬停**允许放排障线索**（`API-01` 这类代号就是给它留的），
  只禁**开发话术**。⇒ ⛔ 别提"干脆把代号全删了"：那会让排障时束手无策（本段首版就是这么误报 21 条的）。
"""

from __future__ import annotations

#: 逐页走一遍（与侧栏 `NAV` 一一对应；⚠️ `m12` 已撤页、不在侧栏）
PAGES: tuple[str, ...] = ("home", "m01", "m02", "m03", "m04", "m05", "m06", "m07", "m08",
                          "m09", "m10", "m11", "m14", "m15", "set", "imp")

SCAN = r"""
() => {
  /* ⚠️⚠️ 两条口径**故意不同**（守则 §5.8：「内部信息要**换地方**——折进技术明细 / 悬停，
     而不是删掉」）：
       ① **可见文案**（能一眼看到的正文 / 顶栏）：**内部编号与开发话术都不许有**；
       ② **悬停 `title`**（要主动悬停才看见）：**允许放排障线索**（`API-01` 这类代号就是给它留的），
          但 ⛔ **不许放开发话术**（"模拟值 / 原型态"那种没有任何排障价值的词）。
     ⛔ 别把 ② 也写成"一律禁" —— 那等于把排障线索**删掉**（与 §5.8 相反），
        实测这么写会让 21 条**合规的悬停**被报成违规（本段首版）。
  */
  /* ⚠️ `容差`（批次 4 · 2026-09-27）：**验收/开发术语** —— 界面上任何地方都不该有
     （`m07` 原来写着"金额按 2 位小数对平、容差 0"，已改成"差 1 分也算不平"）。
     ⚠️ 它**只在正文里禁**、悬停里也禁（悬停同样可能写着它）；但**注释不在扫描范围**（只看 DOM）。 */
  /* ⚠️ **源码注释标记不该出现在页面上**（2026-09-27 加，这条是"真踩过"才加的）：
     壳里有一大段 HTML 是**模板字符串**，往那里面写注释标记不是注释，它会**原样渲染成文字**
     （`node --check` 照样过 ⇒ 离线那道哨**看不见**它）⇒ 由本段在真机上盯。
     ⚠️ 正文里出现注释标记只可能是这个错 ⇒ 零假阳性。⛔ 本行注释里**不能写注释结束符本身**
     （会把本注释提前闭合 —— 加这条规则时当场踩到：`Page.evaluate: SyntaxError`）。 */
  const VISIBLE = /API-\d\d|DEV-[A-Z]|ENT-\d\d|OPEN-[A-Z0-9]|REQ-[A-Z]|TAIL-\d+|模拟值|模拟今天|原型态|原型演示|虚构|容差|\/\*|\*\/|跨域能力/g;
  const TITLE = /模拟值|模拟今天|原型态|原型演示|虚构|容差/g;
  const out = [];
  const add = (where, re, s) => {
    if (!s) return;
    let m; re.lastIndex = 0;
    while ((m = re.exec(s)) !== null) {
      out.push({where: where, hit: m[0],
                ctx: s.slice(Math.max(0, m.index - 26), m.index + 26).replace(/\s+/g, ' ').trim()});
    }
  };
  const v = document.querySelector('#view');
  add('正文', VISIBLE, v ? v.textContent : '');
  const ttl = document.querySelector('#ttl');
  add('顶栏', VISIBLE, ttl ? ttl.textContent : '');
  /* ⭐ 2026-09-28（`TAIL-131`）：**侧栏正文也要扫** —— 此前只扫「正文 ＋ 顶栏」（侧栏只扫了悬停），
     而侧栏是**每页都在**的用户可见区（页名 / 分组 / 状态标）⇒ 从那以后它就是"没人看的那一层"。
     ⚠️ 只挂**同一份**禁用集（⛔ 不另立一套），所以不会引入新口径。 */
  const sb = document.querySelector('.sb');
  add('侧栏', VISIBLE, sb ? (sb.textContent || '') : '');
  document.querySelectorAll('#view [title]').forEach(x => add('悬停', TITLE, x.title));
  document.querySelectorAll('.sb [title]').forEach(x => add('侧栏悬停', TITLE, x.title));
  /* ⭐ 第三件（批次 3 · 守则 §4.4「相似元素不制造歧义」）：**同一个卡头里按钮文案不许重复** ——
     同名的两个按钮并排，用户必然认错。⚠️ 只查 `h4 .sp`（卡头右侧操作区）：
     行内每行都有的「删除」那种**不算**（它不在卡头里，重复是正常的）。 */
  document.querySelectorAll('#view h4 .sp').forEach((sp, i) => {
    const seen = {};
    sp.querySelectorAll('button').forEach(b => {
      const t = (b.innerText || '').replace(/\s+/g, ' ').trim();
      if (!t) return;
      if (seen[t]) out.push({where: '卡头#' + (i + 1), hit: '同名按钮',
                             ctx: '同一个卡头里有两个「' + t + '」'});
      seen[t] = 1;
    });
  });
  return out;
}
"""


#: ㉖ 的阈值：**默认展开**的说明块正文**上限**（字符数 · 空白不计）。
#: 定这个数的依据（守则 §3.4「与当前任务无关的冗余信息不塞同一屏」/ §5.9「次要信息可折叠」）：
#:  一屏里默认铺开的说明**超过 ~三四行**就变成"墙"，用户会直接跳过 ⇒ 该压短或折起来。
#:  ⚠️ 它管的是**默认展开**的那些；`<details>` 里的（用户主动点开才看）**不设上限** ——
#:     那是"要查才看"的技术/口径档，是 §5.8「换地方，不是删掉」的落点。
LONG_LIMIT = 200

#: ㉖ 的诊断阈值：低于上限、但已偏长的，也**打出来**（免得"刚好卡在 199"这种看不出来）。
LONG_REPORT = 120

#: ㉙ 页级规则保留扩展接口；TAIL-263 已删除原说明页 m13。
PAGE_TEXT_RULES: tuple[tuple[str, str, str], ...] = ()

#: ⭐⭐ **㉙ 全站通用**（扫**每一屏**的正文）：`**` 是"加粗"标记，壳**必须渲染成 `<b>`**（唯一出口 = `lgMd`）——
#:   它出现在可见文本里 = 某处**漏了渲染**（守则 §3.1「标记不上屏」）。
#:   ⚠️ 这条一开始只写在 `imp` 一页上（因为源起是域自报文案）；**当场就抓到 4 处**在 `imp` 的
#:   「截止核算月」人话提示里（壳自己写的模板，含 `**被拒**` / `**那个项目**`）⇒ 说明"漏渲染"
#:   不挑页面，凡是**默认展开**的说明文字都可能中招 ⇒ 扩成全站扫（零假阳性：可见文本里出现
#:   成对的 `**` 没有第二种解释）。
GLOBAL_TEXT_RULES: tuple[tuple[str, str], ...] = (
    (r"\*\*", "加粗标记原样上屏（守则 §3.1：要渲染成 `<b>` —— `lgMd` 是唯一出口）"),
)

#: ㉙ 的扫描器：在**当前页**的 `#view` 正文里找 `re` 的所有命中（带上下文）。
PAGE_SCAN = r"""
(re) => {
  const v = document.querySelector('#view');
  const s = v ? (v.textContent || '') : '';
  const out = [];
  let m;
  const rx = new RegExp(re, 'g');
  while ((m = rx.exec(s)) !== null) {
    out.push({hit: m[0],
              ctx: s.slice(Math.max(0, m.index - 26), m.index + 26).replace(/\s+/g, ' ').trim()});
  }
  return out;
}
"""

LONG_SCAN = r"""
() => {
  const out = [];
  document.querySelectorAll('#view .tip, #view .tip.ok, #view .tip.wn').forEach(t => {
    if (t.closest('details')) return;                 /* ⭐ 已折叠 ⇒ 合规（用户主动点开才看） */
    const txt = (t.innerText || '').replace(/\s+/g, ' ').trim();
    if (!txt) return;
    const n = txt.replace(/\s/g, '').length;
    if (n >= 120) out.push({n: n, head: txt.slice(0, 40)});
  });
  return out;
}
"""


def _scan_long(page, key: str) -> list[dict]:
    return page.evaluate(LONG_SCAN)


def check(page, errors: list[str]) -> None:
    """逐页扫 DOM 文本与悬停属性。"""
    from _shell_common import goto

    seen: list[str] = []
    total = 0
    over: list[str] = []
    for key in PAGES:
        goto(page, key)
        hits = page.evaluate(SCAN)
        for h in hits:
            total += 1
            line = f"{key} · {h['where']} · 「{h['hit']}」… {h['ctx']}"
            if line not in seen:
                seen.append(line)
    print(f"㉕ 逐页扫上屏文案（含卡头同名按钮）：{len(PAGES)} 屏 · 命中 {total} 处 · 去重 {len(seen)} 处")
    for line in seen:                      # ⚠️ 全量打印（去重后通常几十条）—— 修的时候要看得全
        print("   ·", line)
    if seen:
        errors.append(
            "㉕ 有内部编号 / 开发话术**漏到了界面上**（守则 §2.5/§3.1/§3.3/§3.6）——\n"
            + "\n".join("      " + s for s in seen[:20])
            + (f"\n      … 另有 {len(seen) - 20} 处" if len(seen) > 20 else ""))

    # ---- ㉖ 默认展开的说明块有多长（守则 §3.4 / §5.9）----
    print(f"㉖ 默认展开的说明块长度（上限 {LONG_LIMIT} 字 · ⚠️ 折叠区不设上限）：")
    for key in PAGES:
        goto(page, key)
        for it in _scan_long(page, key):
            mark = "⛔" if it["n"] > LONG_LIMIT else "·"
            if it["n"] > LONG_LIMIT or it["n"] >= LONG_REPORT:
                print(f"   {mark} {key} · {it['n']} 字 · {it['head']}…")
            if it["n"] > LONG_LIMIT:
                over.append(f"{key} · {it['n']} 字 · {it['head']}…")
    if over:
        errors.append(
            f"㉖ 有说明块**默认就铺满一屏**（> {LONG_LIMIT} 字 · 守则 §3.4 / §5.9）"
            "—— 压成 1~2 句（本系统已不再有折叠的口径说明抽屉，见 `TAIL-213`）：\n"
            + "\n".join("      " + s for s in over))

    # ---- ⭐ ㉙ 页级 / 全站禁用（`TAIL-124` / `TAIL-105` · 2026-09-28）----
    page_bad: list[str] = []
    print("㉙ 页级 / 全站禁用文案（工程台账话术 / 原样上屏的标记）：")
    for key, pat, why in PAGE_TEXT_RULES:
        goto(page, key)
        for h in page.evaluate(PAGE_SCAN, pat):
            line = f"{key} · 「{h['hit']}」… {h['ctx']} —— {why}"
            if line not in page_bad:
                page_bad.append(line)
    for pat, why in GLOBAL_TEXT_RULES:
        for key in PAGES:
            goto(page, key)
            for h in page.evaluate(PAGE_SCAN, pat):
                line = f"{key} · 「{h['hit']}」… {h['ctx']} —— {why}"
                if line not in page_bad:
                    page_bad.append(line)
    print("   " + ("✅ 无" if not page_bad else f"⛔ {len(page_bad)} 处"))
    for line in page_bad:
        print("   ·", line)
    if page_bad:
        errors.append(
            "㉙ 页级禁用命中（守则 §1.1「用户需要感知吗」/ §3.1「标记不上屏」/ §4.1「文案与行为一致」）：\n"
            + "\n".join("      " + s for s in page_bad))

