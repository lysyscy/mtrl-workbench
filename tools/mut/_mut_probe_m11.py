"""守真机自检 ㉓ 段（`tools/probe/_shell_m11.py`）：页面集采台账那 5 个派生金额列 == 后端派生值。

**为什么必需**：首版判法拿「页面第 i 行」对「「/api/m11/list 第 i 行」」，而两边**不是同一批合同**
（页面默认筛「纳入台账」253 行 · 端点无筛选＝全量 258 行）⇒ 从第一处筛除起**每行错位一格**，
该段长期假红（2026-10-10 现场定位：第 7/8 行那对 52378 是**互换**，不是算错）。
⇒ 改成**按合同稳定键多重集配对**。**假红修掉 ≠ 判据变松**：下面三条证明它照样会红。

**三条变异（隔离输入：只在**浏览器内存里**改那份页面数据，⛔ 零文件改动）**：

| 靶 | 页面数据怎么坏 | 该红的是 |
|---|---|---|
| `M1` | 某份合同的 `inv_sum` 改成别的数（`M5-7` 老 bug 的形态：页面那份数没跟着后端走） | 逐行不一致 |
| `M2` | 某份合同的**合同日期**改掉（配对键变 ⇒ 它在后端找不到对应） | 配对率下限（<90%） |
| `M3` | 某份合同的**合同金额**改掉（配对键的另一半） | 同上 |

⚠️ 前提：**壳在跑**（`http://127.0.0.1:8000/app` ＋ 真库）—— 本段本来就是真机段。
⚠️ 数据只在页面内存里改，**不发任何写请求** ⇒ 库与工作文件都不受影响（⛔ 别把自证改成写库）。
⚠️ 每次自证前先跑一遍**正常态**（必须 `errors` 为空）—— 否则"红"分不清是判据有牙还是现场本来就坏。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_probe_m11.py`
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools" / "probe")]

#: 页面内存里的改坏脚本（⛔ 全部只改 `JCs`（前端缓存）＋ 重画，**不发写请求**）
#: ⚠️ 键那两条改**一批行**（1/4）而不是一行 —— 配对率是**按比例**判的（单行对不上可能只是
#:    现场数据刚变动，不该红）；要证明"跌破下限会红"，得让跌破真的发生。
MUTS = {
    "M1 页面那份发票金额没跟着后端走（改 JCs 的 inv_sum）":
        "JCs[0].inv_sum = String((Number(JCs[0].inv_sum) || 0) + 12345.67); render();",
    "M2 配对键之一被改坏（改 1/4 那批 JCs 的 date ⇒ 后端找不到这些合同）":
        "for (let i=0;i<Math.ceil(JCs.length/4);i++) JCs[i].date='1999-01-01'; render();",
    "M3 配对键之二被改坏（改 1/4 那批 JCs 的 contractAmt）":
        "for (let i=0;i<Math.ceil(JCs.length/4);i++) JCs[i].contractAmt=(Number(JCs[i].contractAmt)||0)+999; render();",
}

#: 等真数据到位 —— ⚠️ **必须走 `goto('m11')`**（那是壳自己的导航入口，会触发加载）；
#: 只 `VIEW='m11'` 不会拉数据 ⇒ `JCs` 永远是空的。
WAIT = 'typeof ACT !== "undefined" && JCs.length > 0'


def _boot(page) -> None:
    """进 `m11` 并等它的合同到位（⛔ 只等 `PJs` 不够：`JCs` 空时变异会崩在 `JCs[0]` 上）。"""
    from _shell_common import goto

    page.wait_for_function('typeof ACT !== "undefined" && PJs.length > 0')
    goto(page, "m11")
    page.wait_for_function(WAIT)


def _open(pw):
    """开一页真机壳（⚠️ 本段要真后端：`/api/m11/list` 的派生值就是被比的那一方）。"""
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "C:/ProgramData/ms-playwright")
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto("http://127.0.0.1:8000/app")
    _boot(page)
    return page


def _run(page) -> list[str]:
    import _shell_m11

    errors: list[str] = []
    _shell_m11.check(page, errors)
    return errors


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        page = _open(pw)
        base = _run(page)
        if base:
            print("✗ 正常态就报红 ⇒ 先修现场/判据，别拿它当基线：")
            for e in base[:5]:
                print("   -", e[:160])
            page.context.browser.close()
            return 1
        print("PASS 正常基线（0 条红）", flush=True)
        bad = 0
        for label, script in MUTS.items():
            try:
                page.evaluate(script)
                errors = _run(page)
            finally:
                page.reload()                       # 页面内存的改动一律丢掉
                _boot(page)
            if errors:
                print(f"PASS 反向：{label}")
                print("      " + errors[0][:150])
            else:
                print(f"✗ 改坏后仍全绿（判据假绿）：{label}")
                bad += 1
        page.context.browser.close()
    print(f"\n结果：{len(MUTS) - bad}/{len(MUTS)} 通过")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())