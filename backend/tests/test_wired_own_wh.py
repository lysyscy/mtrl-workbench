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
from tests.ui_helpers import ui_page  # noqa: F401

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带剪刀 `_fn`（"标记 A → 标记 B"）——
#    已**整把删掉**，取段改走壳的语义口径（函数 ⇒ `func_body` · `API` 条目 ⇒ `api_entry`）。⛔ 别写回来。


def test_新小微直接查名单并允许强踢():
    """界面主动查询允许强踢，保留建档前核对，不再另问强踢授权。"""
    dlg = func_body("openOwnDialog")
    assert 'data-act="ownWhCheck"' in dlg, "没有「先查 i8 仓库名单」这个入口"
    assert "id=\"ownWhRes_" in dlg, "没有就地显示结果的位置"
    check = func_body("ownWhCheck")
    assert 'ownWhOk(i)' in check and 'modal(' not in check
    ok = func_body("ownWhOk")
    assert "allow_kick: true" in ok and "API.whCheck(" in ok


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
    ① `allow_kick: true` 由主动查询的调用方传入；
    ② 壳里**不许**自己比对名单（那是 `i8_warehouse_lookup` 的活）。"""
    ok = func_body("ownWhOk")
    assert ok.count("allow_kick: true") == 1
    api = api_entry("whCheck")
    assert "allow_kick" not in api, "适配层⛔ 不许自己写死 allow_kick（要向调用方拿）"
    for forbidden in ("owner_full_name", "warehouse_rows"):
        assert forbidden not in ok, f"壳里⛔ 不许自己解析 i8 名单（发现有 {forbidden}）"


def test_query_runs_on_click_and_keeps_separate_archive_confirmation(ui_page):
    p = ui_page
    p.evaluate('''async () => {
      window.warehouseQueries=[]; window.archiveWrites=[];
      API.unresolved=async()=>({items:[{project_name:'壳全名',doc_name:'测试材料',kind:'needs_keyword',shell_id:2,candidates:[]}]});
      API.whCheck=async body=>{warehouseQueries.push(body);return {found:false,degraded:false,owners:[],total:0,message:'名单里没有'};};
      API.assignOwnership=async body=>{archiveWrites.push(body);return {ok:false,message:'隔离写出口'};};
      await openOwnDialog();
    }''')
    p.locator('#ownNewName_0').fill('测试新仓库')
    p.locator('#ownNewKw_0').fill('测试')
    p.get_by_role('button', name='① 先查 i8 仓库名单', exact=True).click()
    p.wait_for_function('warehouseQueries.length===1 && !!document.querySelector("#ownWhForce_0")')
    assert p.evaluate('warehouseQueries[0]') == {'warehouse_name': '测试新仓库', 'allow_kick': True}
    assert p.locator('#ownNewName_0').is_visible()
    p.get_by_role('button', name='建档并归集', exact=True).click()
    assert p.evaluate('archiveWrites.length') == 0
    p.locator('#ownWhForce_0').check()
    p.get_by_role('button', name='建档并归集', exact=True).click()
    p.wait_for_function('archiveWrites.length===1')
