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
