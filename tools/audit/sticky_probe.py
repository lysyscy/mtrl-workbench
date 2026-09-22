"""合计行「视口吸附置底」实测脚本（可复现）。

结论与解读见 `ops/M3-合计行置底实测结论.md`。

用法（本机）：
  $env:PLAYWRIGHT_BROWSERS_PATH = "C:\\Users\\Administrator\\AppData\\Local\\ms-playwright"
  & backend\\.venv\\Scripts\\python.exe tools\\sticky_probe.py
判据：容器高 200px、表内 30 行数据、`scrollTop = 0` 时**合计行是否已落在容器可视区内**。
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH", r"C:\Users\Administrator\AppData\Local\ms-playwright"
)

from playwright.sync_api import sync_playwright  # noqa: E402

CSS = """
*{box-sizing:border-box}
body{margin:0;font:12px/1.5 system-ui,'Microsoft YaHei';background:#f7f8fa}
.case{margin:12px;padding:9px;background:#fff;border:1px solid #d8dde6;border-radius:8px}
h4{margin:0 0 7px;font-size:12.5px}
.tw{overflow:auto;max-height:200px;min-height:200px;border:1px solid #c9d2de}
table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid #e3e8ef;padding:6px 8px;text-align:left;white-space:nowrap}
th{position:sticky;top:0;z-index:2;background:#eef2f7}
.n{text-align:right}
/* A · 原型现写法（作用于 td）—— 预期失败 */
.caseA tbody tr.sumrow>td{position:sticky;bottom:0;z-index:2;background:#eef2f7;box-shadow:inset 0 1px 0 #c9d2de}
/* D · tfoot 整块 */
.caseD tfoot{position:sticky;bottom:0;z-index:2;background:#eef2f7}
.caseD tfoot td{background:#eef2f7;box-shadow:inset 0 1px 0 #c9d2de}
/* E · 末行 tr 自身（推荐） */
.caseE tbody tr.sumrow{position:sticky;bottom:0;z-index:2}
.caseE tbody tr.sumrow>td{background:#eef2f7;box-shadow:inset 0 1px 0 #c9d2de}
/* C · 布局法：滚动区只包数据行 */
.caseC .tw{display:flex;flex-direction:column}
.caseC .scroller{overflow:auto;flex:1 1 auto;min-height:0}
.caseC .sumline{flex:0 0 auto;background:#eef2f7;border-top:1px solid #c9d2de}
"""

ROWS = "".join(
    f'<tr><td>D{i:02d}</td><td>项目{i:02d}</td><td class="n">{i * 1000}.00</td></tr>'
    for i in range(1, 31)
)
HEAD = "<tr><th>单据号</th><th>项目</th><th>金额</th></tr>"
SUM = '<td>合计</td><td>—</td><td class="n">465000.00</td>'


def page_html() -> str:
    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="case caseA"><h4>A · tbody tr.sumrow&gt;td{{position:sticky}}（原型现写法）</h4>
 <div class="tw" id="twA"><table class="dt"><thead>{HEAD}</thead><tbody>{ROWS}
 <tr class="sumrow" id="sumA">{SUM}</tr></tbody></table></div></div>

<div class="case caseD"><h4>D · tfoot 整块 sticky</h4>
 <div class="tw" id="twD"><table class="dt"><thead>{HEAD}</thead><tbody>{ROWS}</tbody>
 <tfoot><tr id="sumD">{SUM}</tr></tfoot></table></div></div>

<div class="case caseE"><h4>E · 末行 tr 自身 sticky（本工程采用）</h4>
 <div class="tw" id="twE"><table class="dt"><thead>{HEAD}</thead><tbody>{ROWS}
 <tr class="sumrow" id="sumE">{SUM}</tr></tbody></table></div></div>

<div class="case caseC"><h4>C · 布局法（滚动区只包数据行）</h4>
 <div class="tw" id="twC"><div class="scroller" id="scC"><table class="dt"><thead>{HEAD}</thead>
 <tbody>{ROWS}</tbody></table></div>
 <div class="sumline" id="sumC"><table class="dt"><tbody><tr>{SUM}</tr></tbody></table></div></div></div>
</body></html>"""


PROBE = """
() => {
  const out = {};
  for (const n of ['A','D','E','C']) {
    const tw = document.getElementById('tw'+n);
    const sc = n === 'C' ? document.getElementById('scC') : tw;
    const sum = document.getElementById('sum'+n);
    sc.scrollTop = 0;
    const c = tw.getBoundingClientRect(), s = sum.getBoundingClientRect();
    out[n] = {
      deltaBelow: +(s.bottom - c.bottom).toFixed(1),
      visibleAtTop: s.top < c.bottom - 0.5 && s.bottom > c.top + 0.5,
    };
  }
  return out;
}
"""


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.set_content(page_html(), wait_until="load")
        res = page.evaluate(PROBE)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print()
        for k in ("A", "D", "E", "C"):
            v = res[k]
            print(
                f"[{k}] 合计行底 − 容器底 = {v['deltaBelow']}px ⇒ "
                + ("✅ scrollTop=0 即可见（吸附生效）" if v["visibleAtTop"] else "❌ 不可见（吸附未生效）")
            )
        print("\n预期：A ❌（原型写法无效）· D ✅ · E ✅（本工程采用）· C ✅")
        sys.stdout.flush()
        os._exit(0)          # ⚠️ 收尾不调 close()/stop()（技术栈 §2.4 记其会挂死）


if __name__ == "__main__":
    raise SystemExit(main())
