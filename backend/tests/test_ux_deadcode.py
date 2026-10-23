"""Protect actual legacy UI output, navigation and cancelled-page behavior."""

from __future__ import annotations

import pathlib

from tests.shell_src import SHELL

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_接口清单表不许回来():
    """⭐ `TASK` 那张表：**零引用** ＋ 内容是**开发视角**（`API-0x` 代号 / 触发方式 / 数据源），
    数据源本就是《说明书》附录 E.1 的文档 ⇒ 需要时查文档，⛔ 别在壳里再抄一份（抄了必静默过期）。

    ⚠️ **能证伪**：把那张表贴回 `index.html` ⇒ 本件必红。
    """
    for tomb in ("const TASK = [",
                 "['API-06','常用项目列表 GetCommonUseList'",
                 "接口清单表（`TASK`）刻意不接"):
        assert tomb not in SHELL, \
            f"已删的「接口清单表」残骸又回来了：{tomb!r} —— ⓵它零引用 ⓶内容是开发视角（守则 §3.1）"




def test_有意保留的留痕不许被顺手清掉():
    """Legacy cancelled-page rendering and navigation remain coherent."""
    assert "V.m12=" in SHELL, "`V.m12` 那片留痕不见了（它是原型切片的对位件，单边删 U1 立刻红）"
    for act in ("dfOk:", "dfAdd:", "dfCancel:"):
        assert act in SHELL, f"`ACT.{act[:-1]}` 不见了 —— 留痕要能**渲染**才算留痕（删了切片按钮会报错）"
    # ⭐ 2026-09-28（**用户裁定 `B`** · 审计清单 §六「裁定 5」）：侧栏最左列是**模块编号**（`MOD-xx`）——
    #    它是"**给人看的编号**"（文档 /《说明书》/ 判据件都按它对齐），**不是**黑话 ⇒ ⛔ 别当 §3.1 的场景清掉。
    assert '<span class="c">${c}</span>' in SHELL, \
        "侧栏的「模块编号列」被清掉了 —— 用户 2026-09-28 裁定保留（见审计清单 §六 裁定 5 / 守则 §3.1 例外栏）"
    assert "g.items.map(([k,n,c])" in SHELL, \
        "侧栏渲染不再取 `NAV` 第三列（模块编号）了 ⇒ 改这条要**先问用户**（裁定 5 选的是保留）"
