"""`MOD-07` **活动大表**（`ACC-RPT-BIG-001`）的壳接线离线断言（自 `test_wired_m07.py` 拆出 · 2026-09-19）。

拆因同上（`T5` 行数）：大表这一族的判据点**独立成件**，与收发结存 / 提取那两族分开读。
共用件见 `tests/m07_shell_helpers.py`（⛔ 别在本文件重抄常量与取片工具）。
"""

from __future__ import annotations

import re

from tests.acc_plugin import acc

from tests.m07_shell_helpers import API, ROUTER, SHELL, _body, _slice  # noqa: F401
from tests.shell_src import with_kernel  # ⭐ `TAIL-67`：判据要连通用件一起看

# ---- `ACC-RPT-BIG-001`（活动大表）的形态半边


# ============== `ACC-RPT-BIG-001`（活动大表）的**形态**半边（`§19` 批 2 搬家）
#
# 原先钉在**旧服务端页**（`big_view.render_big_page` / `render_export_page` / `_cell_html` / `_thead`）
# 渲染出的 HTML 上；旧页删除（授权 `D18`）⇒ 形态改指新壳（⛔ 判据不删）。

# ⚠️ `BIG_THEAD` 在壳里是**多段反引号拼接**（`const BIG_THEAD=`…`` ` `` ＋ `` +`…` ``），
#    所以取到第一处 `` `; `` 为止（非贪婪）；取出来的是**两行表头的全部标记**。
_BIG_THEAD_RE = re.compile(r"const BIG_THEAD=(.*?)`;", re.S)


def _big_thead() -> str:
    m = _BIG_THEAD_RE.search(SHELL)
    assert m, "壳里找不到 `const BIG_THEAD=`"
    return m.group(1)


@acc("ACC-RPT-BIG-001", "001-02")
def test_壳里表头不含已裁掉的列():
    """拿**域内核那把尺子**（`boundary_violations`）扫壳的表头 ⇒ 不得含已裁掉的列（如「材料费」数据项）。"""
    from app.mod07_setl import big_domain as B

    assert B.boundary_violations(html=_big_thead()) == [], "壳表头里出现了不得有的列"


@acc("ACC-RPT-BIG-001", "001-03")
def test_壳里输入框只出现在手填列():
    """手填列**恰好 6 个**：表体只经一个 `cell()` 生成输入框（`cell(0)…cell(5)`），⛔ 没有第 7 个。"""
    s = _slice("m07")
    assert s.count('data-act="bigEdit"') == 1, "输入框渲染点不止一处（应只有一个 `cell()` 生成器）"
    for i in range(6):
        assert f"${{cell({i})}}" in s, f"手填列 `cell({i})` 没了"
    assert "${cell(6)}" not in s, "出现了第 7 个手填列（手填列应恰好 6 个）"


@acc("ACC-RPT-BIG-001", "001-04")
def test_壳里派生列是纯文本格():
    """派生列（合计 / 使用率 / 产值完成率）在壳里是**纯文本格**（走 `M(...)` / `pct(...)`），⛔ 无输入框。"""
    s = _slice("m07")
    for expr in ("M(r.totC)", "pct(r.use)", "pct(r.done)"):
        assert expr in s, f"派生列的渲染点变了：{expr}"


@acc("ACC-RPT-BIG-001", "001-05")
def test_壳里主材累计走金额出口且取数口已接入():
    """⭐ 2026-09-21（`TAIL-25`）集采台账取数口**已接入**（`MAIN_MATERIAL_PORT is not None`）⇒
    该列显示**真数**；它在本表仍是**派生文本格**（`M(r.matC)`，⛔ 不是手填输入框）。
    ⚠️ 旧的"未接入 ⇒ 显「—」"守卫保留在壳里（`MAT_OK ?`），端口被显式摘除时仍会兜住。"""
    from app.mod07_setl import big_service as BS

    assert BS.MAIN_MATERIAL_PORT is not None, "取数口被摘掉了 ⇒ 主材累计会退回「—」（接入态不许静默丢）"
    s = _slice("m07")
    assert "M(r.matC)" in s, "主材累计的渲染点变了（它必须是派生文本格，不能变成手填）"


@acc("ACC-RPT-BIG-001", "001-09")
def test_壳里零与未录入在输入框上分得开():
    """零是**合法录入值**（不得被误判成未录入）：输入框的值走 `bigDisp(c.v,i)`，而它的空值判定是
    **严格 `==null`** —— ⛔ 不用 `||`/`?` 之类的真值判断（那会把 `0` 吞掉、显示成未录入）。"""
    assert "const bigDisp=(v,i)=>v==null?'':String(v);" in SHELL, \
        "`bigDisp` 对空值的判定变了（用真值判断会把合法的 0 吞掉）"
    s = _slice("m07")
    assert "bigDisp(c.v,i)" in s, "输入框的值没走 `bigDisp` 出口"


@acc("ACC-RPT-BIG-001", "001-12")
def test_壳里带入格可辨且带来源月():
    """带入格**仍是可编辑输入框**（`class="inp…ed"`）＋ 带**来源月**标记（`↺MM月`）。"""
    s = _slice("m07")
    assert "c.from?' ed':''" in s, "带入格没有带入态样式（不再是可辨的输入框）"
    assert "↺${c.from.slice(5)}月" in s, "带入格没有来源月标记"


@acc("ACC-RPT-BIG-001", "001-13")
def test_壳里行只由一份装配出():
    """「页面行序 = 导出页行序」在壳里的等价形态：**行只从 `bigRows(...)` 这一处装配**（表体 ＋ 合计行），
    ⛔ 没有第二份行序；导出走 `/api/m07/big/export`（复用同一个 `big_service`，另有断言）。"""
    s = _slice("m07")
    assert s.count("bigRows(") == 2, f"`bigRows(` 出现了 {s.count('bigRows(')} 次（应只用于表体与合计行）"
    assert "bigRows(bjMonth(-1)).map((r,ri)=>" in s, "表体不是由 `bigRows` 装配的"
    assert "/api/m07/big/export?period=" in SHELL, "导出没走 API（那一份才是与页面同源的）"


@acc("ACC-RPT-BIG-001", "001-15")
def test_壳里出纸走按模板导出且没有打印通道():
    """出纸 = **按模板导出 → Excel 打印**（壳的 `bigExport` → `/api/m07/big/export?period=`）；
    ⛔ 没有打印通道 / A3 入口（连标题里都不许出现）。"""
    s = _slice("m07")
    assert 'data-act="bigExport"' in s, "壳里没有「按模板导出」入口"
    assert "Excel 打印" in s, "没写明出纸方式（按模板导出后在 Excel 打印）"
    assert "A3" not in s, "壳里还留着 A3 打印通道"
    # 导航里有本页（新壳的侧栏菜单）
    assert "'m07','收发结存与活动大表'" in SHELL, "新壳侧栏里没有本页入口"
    # 路由层面：大表**没有**任何打印 / A3 入口（API 侧；旧页路由随本批删除）
    from app.main import create_app

    paths = [p for p in create_app().openapi()["paths"] if "big" in p]
    assert paths and not any(("print" in p or "a3" in p.lower()) for p in paths), paths


# --------------------------------------------------------------- 活动大表导出（`TAIL-04` 片 4b）


@acc("ACC-RPT-BIG-001", "001-19")
def test_活动大表导出走真下载而不是假成功():
    """⭐ `TAIL-04` **片 4b**：大表成品由后端模板填充生成 ⇒ 壳侧必须是**真下载**。

    ⚠️ 原型那个按钮是 `data-act="exp"`（诚实占位：**没有文件产生**）—— 接线后必须换成大表自己的动作。
    """
    assert "bigExport:async ()=>{" in SHELL, "缺真下载动作 `bigExport`"
    assert "/api/m07/big/export?period=" in SHELL, "没走活动大表导出端点"
    assert "encodeURIComponent(bjMonth(-1))" in SHELL, \
        "月份没原样带给后端（§9.2 材料报表类默认 = 上月；⛔ 前端不另算）"
    assert "x-export-filename" in SHELL, "文件名没从 `X-Export-Filename` 带出（命名规则的主人在后端）"
    # ⛔ 旧的**假成功**按钮必须消失（大表卡头那一个）
    assert 'data-act="exp" data-t="经济活动分析大表（按模板）"' not in SHELL, "大表卡头还留着假成功的 `exp`"
    assert 'data-act="bigExport"' in SHELL, "大表卡头的按钮没接到 `bigExport`"


@acc("ACC-RPT-BIG-001", "001-19")
def test_活动大表导出失败必须给人原因不静默():
    """后端失败回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（一行都没有 / 模板坏 / **显示区对账不过**）
    ⇒ 壳必须**弹原因**，⛔ 不能静默、也不能当文件下载。"""
    i = SHELL.index("bigExport:async ()=>{")
    body = SHELL[i:SHELL.index("\n /* —— MOD-12 —— */", i)]     # 终点锚用**下一段注释头**（纯 ASCII）
    assert 100 < len(body) < 2200, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"
    _b = with_kernel(body)         # ⭐ `TAIL-67`：错误分类已抽到 `dlExport` 通用件
    assert "ct.includes('application/json')" in _b, "没按 content-type 分流"
    assert "后端没给原因" in _b, "失败时没把后端的中文原因给用户"
    assert "r.ok" in _b and "HTTP ${r.status}" in _b, \
        "非 2xx 没显式报错（会静默产出空文件）"
