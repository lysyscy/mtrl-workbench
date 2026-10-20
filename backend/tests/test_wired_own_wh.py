"""链路 C 弹窗 · **兜底前先跑 i8 仓库名单**的壳侧断言（`TAIL-39`）—— 离线静态。

**壳里只做三件事**：**问**（按钮）· **显示**（就地结果，四态分得开）· **拦**（没查过 / 没命中又没确认 ⇒ 不许提交）。
⛔ 判定全在后端（`domain.i8_warehouse_lookup` ＋ `/api/m03/notices/warehouse-check`）；
   壳里自己比对名单 = 第二份口径（本仓铁律）。

⚠️ 静态检查**不证明运行时能跑** ⇒ 那一半由壳真机自检 `tools/probe/_shell_ownwh.py` 覆盖
   （⚠️ 查名单**真会登录 i8 并顶号** ⇒ 真机**只看不点**）。
"""

from __future__ import annotations

from pathlib import Path


from tests.shell_src import api_entry, func_body

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带剪刀 `_fn`（"标记 A → 标记 B"）——
#    已**整把删掉**，取段改走壳的语义口径（函数 ⇒ `func_body` · `API` 条目 ⇒ `api_entry`）。⛔ 别写回来。


def test_新小微那块有查名单入口且先二次确认():
    """⭐ 用户原话「兜底前…应该有去仓库跑了一环」⇒ 弹窗的「新小微」那块必须有这一环，
    且因为**会登录 i8 并强踢**（`D9`）⇒ 先弹二次确认、确认之后才发请求。"""
    dlg = func_body("openOwnDialog")
    assert 'data-act="ownWhCheck"' in dlg, "没有「先查 i8 仓库名单」这个入口"
    assert "id=\"ownWhRes_" in dlg, "没有就地显示结果的位置"
    check = func_body("ownWhCheck")
    assert "会登录 i8，可能顶掉该账号在线会话" in check and 'data-act="ownWhOk"' in check, "要先二次确认、讲清会顶号"
    assert "只查询、不写入" in check, "必须说明查询不写入的范围"
    assert "API.whCheck(" not in check, "打开确认窗不得提前登录查询"
    ok = func_body("ownWhOk")
    assert "allow_kick: true" in ok and "API.whCheck(" in ok, "确认之后才发请求（⛔ 别在按钮点下就发）"


def test_没查过不许建_没命中要人确认():
    """⭐ 这一环的意义就在"**拦**"上：⛔ 不查就建 = 凭猜填仓库名（假档案行）。
    没查过 ⇒ 当场拦；查了**没命中**（或**没取到**）⇒ 必须**显式勾选确认**才放行。"""
    sub = func_body("ownAssignSubmit")
    assert "const seen = OWN_WH[i];" in sub and "if (!seen)" in sub, "没查过要拦下（⛔ 不静默建档）"
    assert "ownWhForce_" in sub, "没命中/没取到时要有「确认」这一道"
    assert "ck.checked" in sub, "确认必须是**真的勾了**（⛔ 别只看有没有那个框）"
    ok = func_body("ownWhOk")
    assert "ownWhForce_" in ok and "checkbox" in ok, "勾选框由检查结果就地生成"


def test_四态文案分开且没取到不等于没有():
    """⚠️ 三种结局要对用户说三种话：**命中** / **名单里没有** / **没取到名单** ——
    尤其「没取到」**不许**被说成「名单里没有」（那会让用户以为 i8 里真没这个仓库）。"""
    ok = func_body("ownWhOk")
    assert "r.degraded" in ok and "r.found" in ok, "四态要分别处理（degraded 先判）"
    assert "没取到名单" in ok and "不等于" in ok, "「没取到」要和「没有」分开说（⛔ 别让用户以为 i8 里真没有）"
    assert "名单里</b>没有" in ok or "没有</b>「" in ok, "没命中的话说得要直白"
    assert "与本条壳一致" in ok or "同一个壳" in ok, \
        "命中时还要核「它挂的壳与条目上的壳是不是同一个」（否则会建错行）"


def test_反向_强踢授权只有一处且壳里不自己判定():
    """⛔ 两条反向：
    ① `allow_kick: true` **只有一处**（确认之后的那个函数里）—— 别在别处悄悄打开；
    ② 壳里**不许**自己比对名单（那是 `i8_warehouse_lookup` 的活）。"""
    ok = func_body("ownWhOk")
    assert ok.count("allow_kick: true") == 1, "强踢授权只允许出现在确认出口那一处"
    api = api_entry("whCheck")
    assert "allow_kick" not in api, "适配层⛔ 不许自己写死 allow_kick（要向调用方拿）"
    for forbidden in ("owner_full_name", "warehouse_rows"):
        assert forbidden not in ok, f"壳里⛔ 不许自己解析 i8 名单（发现有 {forbidden}）"
