"""壳的**外链件**必须**两处登记**：`index.html` 的 `<script src>` ＋ `main.py` 的路由。

⚠️ 为什么单独立一条（2026-09-24 **实测踩到**，代价是"整支壳崩")：
把 `API` 切进 `shell/api.js` 之后，`<script src>` 加了、但 `main.py` **没有对应路由**
⇒ 浏览器拿到 **404** ⇒ `ReferenceError: API is not defined`（壳一启动就崩，页面一片空白）。

⚠️ **离线判据全都看不见这一条**：
 · `shell_source` 读的是**磁盘上的件** ⇒ `in SHELL` 之类的断言照绿；
 · `Q3` 只看"目录里有没有**散件**" ⇒ 它管的是**反向**（有件没引用）；
 ⇒ 只有**真机**（`_shell_smoke`）与**本件**能发现。⇒ 本件 = 把真机才发现的事提前到离线。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audit"))          # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import INDEX_HTML  # type: ignore  # noqa: E402  ← `P4`① 读取点收敛

MAIN = ROOT / "backend" / "app" / "main.py"


def _srcs() -> list[str]:
    """`index.html` 里被 `<script src>` 引到的壳件（顺序 = 浏览器执行顺序）。"""
    return re.findall(r"/static/shell/([\w.\-]+)", INDEX_HTML.read_text(encoding="utf-8"))


@acc()
def test_壳的每一件外链件都有路由():
    """⭐ **有 `<script src>` ⇒ 必须有路由**（缺 ⇒ 404 ⇒ 整支壳崩，且离线看不见）。"""
    srcs = _srcs()
    assert srcs, "`index.html` 里没有外链壳件（拆件被回退了？）"
    main_txt = MAIN.read_text(encoding="utf-8")
    missing = [n for n in srcs if f'"/static/shell/{n}"' not in main_txt]
    assert not missing, (f"缺路由 ⇒ 浏览器 404 ⇒ `ReferenceError` 整支崩：{missing} "
                         f"（在 `main.py` 里照既有那几条加一条 `_shell_js` 路由）")


@acc()
def test_路由与外链件一一对应_没有孤儿():
    """⛔ 反向也要堵：别留"挂了路由但 `index.html` 不引"的孤儿（`Q3` 看不见它）。"""
    main_txt = MAIN.read_text(encoding="utf-8")
    routed = set(re.findall(r'@app\.get\("/static/shell/([\w.\-]+)"', main_txt))
    srcs = set(_srcs())
    assert routed == srcs, (f"两边不一致 —— 只挂路由={sorted(routed - srcs)} · "
                            f"只被引用={sorted(srcs - routed)}")
