"""壳的**外链件**必须**两处登记**：`index.html` 的 `<script src>` ＋ `main.py` 的路由。

⭐ 2026-09-29（`TAIL-192`-③/-④）**并守两条同族**（都属"壳的接线层写了必然会漂的话"）：
① **不许写死壳件数 / 件清单**（活文档 ＋ `main.py` 注释）—— 件数 2026-09-19 / 09-24 / 09-28 各涨过一次；
② **`API`（唯一数据出口）只许在 `api.js` 里定义** —— 别处再来个同名局部变量会**静默遮蔽**它（真例见下）。

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


# ── `TAIL-192`-③：活文档与注释**只许写指针**、不许写死壳件数 ─────────────────────
#: ⚠️ 下面三条**刻意不绑契约面**（`@acc()` 空参 = 显式不绑定）：它们守的是**工程侧的可操作性**
#:    （件数别写死 / 数据出口别被遮蔽 / 头注别指错路），不对应任何"用户看得见的行为" ⇒ 不硬绑涨绿数
#:    （口径见 `TAIL-167` 的裁定：只登记"用户看得见"的）。
#: 扫描面 = **活的**文档与代码（⛔ 不含计划 / `归档-*` / `.codebuddy/memory/*` —— 那些是留痕，记的当时那个数是对的）
_CANNOT_PIN_SHELL_COUNT = (ROOT / "ops" / "architecture.md", MAIN)   # ⚠️ 2026-10-01 起文档落 `ops/`（`docs/` 已并入）


@acc()
def test_活文档与注释不许写死壳件数():
    """⭐ 件数会随拆件涨（09-19 `P4`② · 09-24 `api.js` · 09-28 `P2-a` 六件）⇒ 只许写指针，写了必漂。

    两条墓碑形态：① `shell/{a,b}.js` 这种**件清单**；② 「壳…N 件」里的阿拉伯数字。
    指针 = `index.html` 的 `<script src>`（唯一出口，`tools/audit/shell_source.py` 照它现读）。
    """
    for p in _CANNOT_PIN_SHELL_COUNT:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT).as_posix()
        hit = re.search(r"shell/\{[^}]*\}", text)
        assert not hit, (
            f"`{rel}` 里写死了壳件清单：「{hit.group(0) if hit else ''}」 ⇒ 拆件后必漂；"
            "改写成指针（`shell/*.js` ＋ `tools/audit/shell_source.py`）"
        )
        hit = re.search(r"壳[^\n]{0,20}?\d+\s*件", text)
        assert not hit, (
            f"`{rel}` 里写死了壳件数：「{hit.group(0) if hit else ''}」 ⇒ 拆件后必漂；"
            "改写成指针（清单唯一出口 = `index.html` 的 `<script src>`）"
        )


# ── `TAIL-192`-④：`API`（唯一数据出口）只许在 `api.js` 里定义 ─────────────────────
@acc()
def test_数据出口_API_只许在_api_js_里定义():
    """⭐ 防**同名遮蔽**：局部映射表也叫 `API` ⇒ 那个函数里再用 `API.xxx` 取数就**静默失效**。

    真例（2026-09-29）：`actions.js` 的抓取弹窗里两处写成 `const API={nt:'API-01',…}`（本意是"接口代号"），
    它把 `api.js` 的全壳数据出口 `API` **遮蔽**了 —— 当时没炸，纯属那个函数里恰好不用数据出口。
    判法：除 `api.js` 外，壳里不许再出现 `const/let/var API =`（局部名请用 `apiCode` 之类）。
    """
    offenders: list[str] = []
    for p in sorted((ROOT / "backend" / "app" / "web").rglob("*.js")):
        if p.name == "api.js":
            continue
        if re.search(r"\b(?:const|let|var)\s+API\s*=", p.read_text(encoding="utf-8")):
            offenders.append(p.relative_to(ROOT).as_posix())
    assert not offenders, (
        f"这些件里又出现了局部 `API`（会遮蔽全局数据出口 ⇒ 静默失效）：{offenders}"
        " —— 换个不撞的名字（如 `apiCode`）"
    )


# ── `TAIL-192`-③：`core.js` 头注要说清 `API` 去哪了 ─────────────────────────────
@acc()
def test_core_js_头注要说清_API_去哪了():
    """⭐ `API` 2026-09-24（`TAIL-48`）已切到 `api.js`，而 `core.js` 头注还把它算在本件里 ⇒ 按错的图找代码。"""
    text = (ROOT / "backend" / "app" / "web" / "shell" / "core.js").read_text(encoding="utf-8")
    head = text[: text.find("*/") + 2]          # 只取模块头注（第一个块注释）
    assert "api.js" in head, (
        "`core.js` 头注必须写明 `API`（唯一数据出口）已切到 `api.js`"
        " —— 否则读的人会在这件里找一个不在的东西"
    )
