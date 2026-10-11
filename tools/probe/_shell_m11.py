"""壳真机自检 · **㉓ 集采台账的派生金额**（`TAIL-113` · 2026-09-26 用户报障后立）。

**它验什么**：页面那 5 个派生金额列（发票金额 · 贸易公司发票金额 · 结算金额（自动）· 付款金额 ·
欠款金额（自动））**显示的数 = 后端派生的数**（逐份合同 ＋ 合计行都比一遍）。

**为什么必须真机验**：这类 bug **离线完全看不见** —— 用户 2026-09-26 报的原话是
「宜化项目**发票子表导入成功**，但**发票金额没跟着动**」：
`M5-7`「判定搬家」把 5 列改成读后端时**漏了前两列**，它们仍按**本地子表数组**现算，
而 `/api/m11/list` **故意不给子表明细**（`adaptJc` 里那三个数组**恒为空**）⇒ **那两列恒 0.00**。
⚠️ 静态判据只能钉"函数体读的是哪个字段"（`test_wired_m11.py` 那条），**钉不出"页面真的画对了"**
   —— 只有把**页面上的字**与**后端的数**摆在一起比，才知道用户看见的是什么。

## ⭐ 判法：**按合同配对**，⛔ 不按下标（2026-10-10 修）

首版拿「页面第 i 行」对「`/api/m11/list` 第 i 行」。**那是错的** —— 两边**不是同一批合同**：
集采台账的默认筛选是 `fJc.tag='纳入台账'`（页面 253 行），而那个端点**不带筛选 = 全量**（258 行），
被筛掉的「不纳入」行不从中间删，而是**留在原地** ⇒ 从第一处筛除起，后面**每一行都错位一格**
（现场实测：`第 7 行页面 52378 / 后端 0`、`第 8 行页面 0 / 后端 52378` —— 一对**互换**，典型的错位而非算错）。

⇒ 现在按**稳定键**（合同日期 ＋ 材料 ＋ 合同金额，金额用 `num()` 归一避开千分位）做**多重集配对**：
同键的合同按出现顺序一一对上，剩下的只计数、不当成金额不一致。配对不上的**多了/少了**要报出来，
因为那说明页面画的不是后端这批合同（或页面把行序/内容搞乱了）—— 判据本身也得跟着查。
⚠️ **合计行**与已配对的当前筛选合同独立求和比较；不拿全量合计比较筛选结果。
⚠️ 反向灵敏度 = `tools/mut/_mut_probe_m11.py`（改坏页面那份数据 ⇒ 必须报红；零文件改动）。
"""

from __future__ import annotations

#: 配对率低于它就报红 —— 「页面画的合同大多在后端找不到对应」＝ 页面或判据坏了，⛔ 不能默默放过
MIN_PAIR_RATE = 0.9

JS = """
async () => {
  const v = document.querySelector('#view');
  const ths = [...v.querySelectorAll('table thead th')].map(x => x.innerText.replace(/[↕\\s]/g, ''));
  const at = t => ths.indexOf(t);
  /* ⚠️ 键**一律加引号**：列名里有**全角括号**（「结算金额（自动）」）⇒ 不带引号当属性名是**非法 JS**
     （实测报 `SyntaxError: Invalid or unexpected token`，整段 evaluate 直接挂）。 */
  const cols = {'发票金额': at('发票金额'), '贸易公司发票金额': at('贸易公司发票金额'),
                '结算金额（自动）': at('结算金额（自动）'), '付款金额': at('付款金额'),
                '欠款金额（自动）': at('欠款金额（自动）')};
  const key = {'发票金额': 'inv_sum', '贸易公司发票金额': 'trade_inv_sum',
               '结算金额（自动）': 'settle', '付款金额': 'pay_sum', '欠款金额（自动）': 'debt'};
  const num = s => { const t = String(s == null ? '' : s).replace(/[^\\d.-]/g, ''); return t ? Number(t) : 0; };
  const txt = td => (td ? td.innerText.trim() : '');
  /* 配对键用哪三列（⛔ 标签取自 `JC_COLUMNS`，材料那列叫「材料名」不叫「材料」）。
     ⚠️ 三列**缺一即报红**（`表头变了，本判词要跟着改`）—— ⛔ 不许让 `at()` 返回 -1 静默变成空串，
        那会让"配对率 0%"顶替掉"列改名了"这条真正的原因。 */
  const kc = {'合同日期': at('合同日期'), '材料名': at('材料名'), '合同金额': at('合同金额')};
  const 缺列 = Object.keys(kc).filter(k => kc[k] < 0);
  /* 稳定键：日期 ＋ 材料名 ＋ 合同金额。⛔ 不含供应商（那格可能带徽标/换行 ⇒ 文字对不齐就把好数据判红） */
  const kOf = (d, m, a) => [d, m, num(a)].join('\\u0001');
  const rows = [...v.querySelectorAll('table tbody tr')];
  const page = [], sum = {};
  for (const tr of rows) {
    const tds = [...tr.querySelectorAll('td')];
    const cls = tr.className || '';
    if (cls.indexOf('sumrow') >= 0) {
      for (const k of Object.keys(cols)) if (cols[k] >= 0 && tds[cols[k]]) sum[k] = num(tds[cols[k]].innerText);
      continue;
    }
    const one = {};
    for (const k of Object.keys(cols)) if (cols[k] >= 0 && tds[cols[k]]) one[k] = num(tds[cols[k]].innerText);
    page.push({键: kOf(txt(tds[kc['合同日期']]), txt(tds[kc['材料名']]), txt(tds[kc['合同金额']])),
               日期: txt(tds[kc['合同日期']]), 值: one});
  }
  /* 同一个端点的**后端真值**（同源 ⇒ 页面里直接拉）。⛔ 不带筛选：本端点无筛选＝全量。 */
  const d = await (await fetch('/api/m11/list')).json();
  const bucket = new Map();
  for (const r of (d.rows || [])) {
    const k = kOf(r.date, r.material, r.contract_amt);
    if (!bucket.has(k)) bucket.set(k, []);
    const one = {};
    for (const c of Object.keys(cols)) one[c] = num(r[key[c]]);
    bucket.get(k).push({值: one});
  }
  /* 多重集配对：同键按出现顺序一一对上（⛔ 不是按下标 —— 页面有筛选，两边行数本就不等） */
  const diff = [];
  const 未配上 = [];
  let paired = 0;
  const sumWant = Object.fromEntries(Object.keys(cols).map(k=>[k,0]));
  for (const p of page) {
    const q = bucket.get(p.键);
    if (!q || !q.length) { 未配上.push(p.日期 || '?日期'); continue; }
    const a = q.shift();
    paired += 1;
    for (const k of Object.keys(cols)) sumWant[k] += a.值[k];
    for (const k of Object.keys(cols)) {
      if (!(k in p.值) || cols[k] < 0) continue;
      if (Math.abs(a.值[k] - p.值[k]) > 0.005) {
        diff.push({合同: p.日期, 列: k, 页面: p.值[k], 后端: a.值[k]});
      }
    }
  }
  const sumDiff = [];
  for (const k of Object.keys(cols)) {
    if (!(k in sum) || cols[k] < 0) continue;
    const want = num(sumWant[k]), got = sum[k];
    if (Math.abs(want - got) > 0.005) sumDiff.push({列: k, 页面: got, 后端: want});
  }
  return {nPage: page.length, nApi: (d.rows || []).length, paired: paired, miss: 未配上.length,
          missEg: 未配上.slice(0, 3), diff: diff.slice(0, 6), sumDiff: sumDiff, 缺列: 缺列,
          有发票金额列: cols['发票金额'] >= 0, 样: page[0] ? page[0].值 : {}};
}
"""


def check(page, errors: list[str]) -> None:
    """集采台账：5 个派生金额列**按合同配对**与后端派生值比对（＋ 合计行）。"""
    from _shell_common import goto

    goto(page, "m11")
    got = page.evaluate(JS)
    if got["缺列"]:
        errors.append(f"㉓ 集采台账表头里找不到配对要用的列 {got['缺列']} —— 列改名了？"
                      "（⛔ 别让它退化成「配对率 0%」，先改本判词里那三列标签）")
        return
    rate = (got["paired"] / got["nPage"]) if got["nPage"] else 1.0
    print(f"  ㉓ 集采台账：页面 {got['nPage']} 行 / 后端 {got['nApi']} 行 · 配对 {got['paired']} 行"
          f"（配对率 {rate:.0%}）· 配不上的 {got['miss']} 行 · 逐行不一致 {len(got['diff'])} 处"
          f" · 合计不一致 {len(got['sumDiff'])} 处")
    if not got["有发票金额列"]:
        errors.append("㉓ 集采台账上找不到「发票金额」列 —— 列被改名/隐藏了？（本判词要跟着改）")
        return
    if rate < MIN_PAIR_RATE:
        errors.append(
            f"㉓ 集采台账只有 {got['paired']}/{got['nPage']} 行（{rate:.0%}）能在后端找到对应合同"
            f"（配不上的例：{got['missEg']}）—— 页面画的**不是后端这批合同**（筛选口径对不上？行被改乱了？），"
            "⛔ 这种情况下下面那些金额比对**没有意义**，先查这个")
    for d in got["diff"]:
        errors.append(f"㉓ 集采台账 {d['合同']} 那份合同的「{d['列']}」：页面显示 {d['页面']}，"
                      f"后端派生 {d['后端']} —— 页面**没跟着后端走**（用户 2026-09-26 报的"
                      "「发票子表导入成功，但发票金额没跟着动」就是这一类）")
    for d in got["sumDiff"]:
        errors.append(f"㉓ 集采台账**合计行**的「{d['列']}」：页面显示 {d['页面']}，后端派生 {d['后端']} "
                      "—— 合计与后端不一致（用户第一眼就是看合计）")