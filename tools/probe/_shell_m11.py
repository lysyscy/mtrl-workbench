"""壳真机自检 · **㉓ 集采台账的派生金额**（`TAIL-113` · 2026-09-26 用户报障后立）。

**它验什么**：页面那 5 个派生金额列（发票金额 · 贸易公司发票金额 · 结算金额（自动）· 付款金额 ·
欠款金额（自动））**显示的数 = 后端派生的数**（逐行 ＋ 合计行都比一遍）。

**为什么必须真机验**：这类 bug **离线完全看不见** —— 用户 2026-09-26 报的原话是
「宜化项目**发票子表导入成功**，但**发票金额没跟着动**」：
`M5-7`「判定搬家」把 5 列改成读后端时**漏了前两列**，它们仍按**本地子表数组**现算，
而 `/api/m11/list` **故意不给子表明细**（`adaptJc` 里那三个数组**恒为空**）⇒ **那两列恒 0.00**。
⚠️ 静态判据只能钉"函数体读的是哪个字段"（`test_wired_m11.py` 那条），**钉不出"页面真的画对了"**
   —— 只有把**页面上的字**与**后端的数**摆在一起比，才知道用户看见的是什么。

⚠️ 判法用**逐行比对**（⛔ 不写死金额）：后端是 0 时页面也必须显示 0，后端变了页面就得跟着变。
"""

from __future__ import annotations

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
    page.push(one);
  }
  /* 同一个端点的**后端真值**（同源 ⇒ 页面里直接拉） */
  const d = await (await fetch('/api/m11/list')).json();
  const api = (d.rows || []);
  const diff = [];
  const n = Math.min(page.length, api.length);
  for (let i = 0; i < n; i++) {
    for (const k of Object.keys(cols)) {
      if (!(k in page[i]) || cols[k] < 0) continue;
      const want = num(api[i][key[k]]), got = page[i][k];
      if (Math.abs(want - got) > 0.005) {
        diff.push({行: i + 1, 列: k, 页面: got, 后端: want});
      }
    }
  }
  const sumDiff = [];
  for (const k of Object.keys(cols)) {
    if (!(k in sum) || cols[k] < 0) continue;
    const want = num((d.totals || {})[key[k]]), got = sum[k];
    if (Math.abs(want - got) > 0.005) sumDiff.push({列: k, 页面: got, 后端: want});
  }
  return {nPage: page.length, nApi: api.length, diff: diff.slice(0, 6), sumDiff: sumDiff,
          有发票金额列: cols['发票金额'] >= 0, 样: page[0] || {}};
}
"""


def check(page, errors: list[str]) -> None:
    """集采台账：5 个派生金额列**逐行**与后端派生值比对（＋ 合计行）。"""
    from _shell_common import goto

    goto(page, "m11")
    got = page.evaluate(JS)
    print(f"  ㉓ 集采台账：页面 {got['nPage']} 行 / 后端 {got['nApi']} 行 · "
          f"首行派生={got['样']} · 逐行不一致 {len(got['diff'])} 处 · 合计不一致 {len(got['sumDiff'])} 处")
    if not got["有发票金额列"]:
        errors.append("㉓ 集采台账上找不到「发票金额」列 —— 列被改名/隐藏了？（本判词要跟着改）")
        return
    for d in got["diff"]:
        errors.append(f"㉓ 集采台账第 {d['行']} 行的「{d['列']}」：页面显示 {d['页面']}，"
                      f"后端派生 {d['后端']} —— 页面**没跟着后端走**（用户 2026-09-26 报的"
                      "「发票子表导入成功，但发票金额没跟着动」就是这一类）")
    for d in got["sumDiff"]:
        errors.append(f"㉓ 集采台账**合计行**的「{d['列']}」：页面显示 {d['页面']}，后端派生 {d['后端']} "
                      "—— 合计与后端不一致（用户第一眼就是看合计）")
