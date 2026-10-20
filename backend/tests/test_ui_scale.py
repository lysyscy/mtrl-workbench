"""「界面大小」（`TAIL-129` · 2026-09-27 用户裁定走**方案 B**）的工程自检（离线 · 不连库）。

⚠️ `@acc()` 显式**不绑定判据点** —— 本件守的是**实现面**这五件：
  ① 档位清单**只有一处真源**（`domain.UI_SCALES`）且默认档合法；
  ② 未设置 / 认不出 ⇒ 回落标准档；③ **非法档位显式拒绝**（⛔ 不静默）；
  ④ **按用户隔离**（只写自己那一行、端点不接 `id`）；⑤ 壳侧的两条形态：
     **档位清单来自后端**（⛔ 不写死）+ **样式块里没有裸 px 字号**（放大时它们不会变）。

⭐ 为什么第 ⑤ 条要在离线钉住：方案 B 的全部效果就是"字号/间距都乘 `--fscale`"——
   漏一处，那一处**放大时不动**（字大了、旁边的小字没大 = 半成品相），而**真机不一定看得出来**。
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from app.core.errors import MustReportError
from app.mod15_user import domain as D
from app.mod15_user import repository as R
from app.mod15_user.api import UiScaleIn
from tests.shell_src import SHELL


# ------------------------------------------------------------ ① 档位清单（唯一真源）


def test_档位清单是唯一真源且默认档合法():
    keys = [k for k, _, _ in D.UI_SCALES]
    assert keys, "档位清单不能是空的"
    assert keys == list(dict.fromkeys(keys)), "档位键不许重复（存库的就是它）"
    assert D.DEFAULT_UI_SCALE in keys, "默认档必须在清单里"
    for key, label, css in D.UI_SCALES:
        assert label, f"{key} 缺人看的名字"
        assert float(css) >= 1, f"{key} 的倍率必须 ≥ 1 —— 用户的原话是「看不清」，⛔ 不提供缩小"


# ------------------------------------------------------------ ② 回落 / ③ 拒绝


def test_未设置或认不出都回落标准档_未登录也是():
    assert D.effective_ui_scale(None) == D.DEFAULT_UI_SCALE, "没登录也要有档（⛔ 不能空）"
    assert D.effective_ui_scale(SimpleNamespace(ui_scale="")) == D.DEFAULT_UI_SCALE
    assert D.effective_ui_scale(SimpleNamespace(ui_scale="乱填的")) == D.DEFAULT_UI_SCALE
    u = SimpleNamespace(ui_scale="largest")
    assert D.effective_ui_scale(u) == "largest"
    assert D.ui_scale_css(u) == dict((k, c) for k, _, c in D.UI_SCALES)["largest"], \
        "倍率必须由 domain 一处给出（壳⛔ 不拿键去查表）"


def test_非法档位显式拒绝不静默():
    """⚠️ 与主题的「非法名**静默**回落默认套」**有意不同**：主题的乱名页面还看得见一套样式
    （用户能察觉），而界面大小的乱值**什么都不会发生**（`--fscale` 算不出来）⇒ 必须当场说清。"""
    with pytest.raises(MustReportError) as err:
        D.assert_ui_scale_usable("huge")
    assert "只能选这几档" in err.value.message
    assert "huge" in err.value.message, "要把**用户传的那个值**回显出来（否则他不知道哪儿错了）"
    assert D.assert_ui_scale_usable("large") == "large"


# ------------------------------------------------------------ ④ 按用户隔离


class _Sess:
    """最小会话替身：`get(模型, id)` + `flush()`（`set_ui_scale` 只用这两样）。"""

    def __init__(self, rows: dict):
        self.rows = rows

    def get(self, _model, uid):
        return self.rows.get(uid)

    def flush(self) -> None:
        pass


def test_按用户隔离_只写自己那一行():
    a, b = SimpleNamespace(ui_scale=""), SimpleNamespace(ui_scale="")
    s = _Sess({1: a, 2: b})
    R.set_ui_scale(s, 1, "larger")
    assert a.ui_scale == "larger"
    assert b.ui_scale == "", "⛔ 改 A 的档位不许碰到 B（这条就是「A 更大、B 标准」的另一半）"
    with pytest.raises(MustReportError):
        R.set_ui_scale(s, 99, "larger")          # 账号不存在 ⇒ 显式报错（⛔ 不静默）


def test_设置端点只收一个字段不接id():
    """⚠️ 多一个 `id` 就等于「管理员能改别人的界面大小」，而口径里没有这条 ——
    且那会让「按用户隔离」这条判据**测不出隔离**（同主题那条的注释）。"""
    assert set(UiScaleIn.model_fields) == {"ui_scale"}, \
        f"界面大小的入参只该有 `ui_scale`，实为 {sorted(UiScaleIn.model_fields)}"


# ------------------------------------------------------------ ⑤ 壳侧两条形态


def test_壳的档位清单来自后端_不写死映射():
    assert "applyUiScale" in SHELL, "壳里没有应用界面大小的地方"
    assert "--fscale" in SHELL, "壳没有把倍率写到 `--fscale` 上"
    assert "UI_SCALES.map" in SHELL, "档位按钮没有照着后端给的清单画（那样加一档就得改壳）"
    for bad in ("largest", "larger", "standard"):
        assert bad not in SHELL, \
            f"壳里出现了档位键字面量「{bad}」⇒ 档位映射被复制成了第二份真源"


def test_启动那一路就应用界面大小():
    """⚠️ 只把应用挂在「系统设置」页的取数上 = **只有进过那一页才生效** ——
    那正是主题当年报过的毛病（`reloadTheme` 的注释里记着）。启动那一路是 `/api/m15/users` 的 `me`。"""
    assert "me.ui_scale_css" in SHELL, "启动那一路（`applyWho`）没应用界面大小"


def test_样式块与内联样式里都没有裸px字号_且默认倍率在():
    """⭐ 方案 B 的全部效果 = "字号/间距都乘 `--fscale`" ⇒ 漏一处，那一处**放大时不动**。

    ⭐ 2026-09-28（`P0-c` · `TAIL-148`）：原先**只查样式块** —— 可壳里还有 577 处**内联**
    `style="…"`，其中一大批 `margin` / `padding` / `font-size` / `gap` 是**写死 px** 的
    ⇒ 用户把「界面大小」调大时，**这一批一处都不动**（正是"半成品相"最扎眼的地方）。
    ⇒ 判据扩到**内联**：这四类属性（**与样式块同一套口径**，⛔ 不新立一套）在内联里也不许有裸 px。

    ⚠️ 四类之外**刻意不管**（颜色 / 边框 / `border-radius` / 宽高 / `top`·`left`）——
        §5.11 要的是"**字号与间距**"跟着放大；1px 边框跟着放大会更难看的。
    """
    m = re.search(r"(?s)<style>(.*?)</style>", SHELL)
    assert m, "取不到样式块"
    css = m.group(1)
    bare = re.findall(r"font-size:\s*[\d.]+px", css)
    assert not bare, f"还有 {len(bare)} 处字号没走 `--fscale`（放大时它们不会变）：{bare[:4]}"
    assert "var(--fscale)" in css, "没有任何一处用到倍率 ⇒ 这条方案没接上"
    assert re.search(r"\{--fscale:\s*[\d.]+\}", css), \
        "少了 `--fscale` 的**默认值** —— `var()` 取不到值时整个 `calc(...)` 失效，界面会散架"

    # ---- ⭐ `P0-c`：内联 `style="…"` 里同样不许有裸 px（四类属性）----
    prop_re = re.compile(r"(?:margin|padding|font-size|gap|row-gap|column-gap)"
                         r"(?:-[a-z]+)?\s*:\s*([^;]*)", re.I)
    px_re = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)px")
    scaled = re.compile(r"calc\([^;]*var\(--fscale\)[^;]*\)")
    bad_inline: list[str] = []
    for one in re.findall(r'style="([^"]*)"', SHELL):
        for val in prop_re.findall(one):
            if px_re.search(scaled.sub("", val)):      # 先抹掉**已缩放**的 `calc(...)`，再看剩没剩裸 px
                bad_inline.append(f"{one.strip()}")
                break
    assert not bad_inline, (
        f"内联 `style=\"…\"` 里还有 {len(bad_inline)} 处该缩放的 px 没走 `--fscale`"
        f"（放大时它们不会变）：{bad_inline[:3]}")
