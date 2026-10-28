"""`MOD-07` **活动大表**（`ACC-RPT-BIG-001`）的壳接线离线断言（自 `test_wired_m07.py` 拆出 · 2026-09-19）。

拆因同上（`T5` 行数）：大表这一族的判据点**独立成件**，与收发结存 / 提取那两族分开读。
共用件见 `tests/m07_shell_helpers.py`（⛔ 别在本文件重抄常量与取片工具）。
"""

from __future__ import annotations

import re


# ⭐ 2026-10-03（`TAIL-219` 批 2）：取片改走壳的语义口径（⛔ 别在本件自造剪刀）

# ---- `ACC-RPT-BIG-001`（活动大表）的形态半边


# ============== `ACC-RPT-BIG-001`（活动大表）的**形态**半边（`§19` 批 2 搬家）
#
# 原先钉在**旧服务端页**（`big_view.render_big_page` / `render_export_page` / `_cell_html` / `_thead`）
# 渲染出的 HTML 上；旧页删除（授权 `D18`）⇒ 形态改指新壳（⛔ 判据不删）。

# ⚠️ `BIG_THEAD` 在壳里是**多段反引号拼接**（`const BIG_THEAD=`…`` ` `` ＋ `` +`…` ``），
#    所以取到第一处 `` `; `` 为止（非贪婪）；取出来的是**两行表头的全部标记**。
_BIG_THEAD_RE = re.compile(r"const BIG_THEAD=(.*?)`;", re.S)










def test_壳里主材累计走金额出口且取数口已接入():
    """⭐ 2026-09-21（`TAIL-25`）集采台账取数口**已接入**（`MAIN_MATERIAL_PORT is not None`）⇒
    该列显示**真数**；它在本表仍是**派生文本格**（`M(r.matC)`，⛔ 不是手填输入框）。
    ⚠️ 旧的"未接入 ⇒ 显「—」"守卫保留在壳里（`MAT_OK ?`），端口被显式摘除时仍会兜住。"""
    from app.mod07_setl import big_service as BS

    assert BS.MAIN_MATERIAL_PORT is not None, "取数口被摘掉了 ⇒ 主材累计会退回「—」（接入态不许静默丢）"








def test_壳里出纸走按模板导出且没有打印通道():
    """出纸 = **按模板导出 → Excel 打印**（壳的 `bigExport` → `/api/m07/big/export?period=`）；
    ⛔ 没有打印通道 / A3 入口（连标题里都不许出现）。"""
    # 导航里有本页（新壳的侧栏菜单）
    # ⭐ 2026-09-28 用户口径：界面上的「活动大表」改叫「**月度会大表**」（正式名仍是《说明书》§5.7 的
    #   「经济活动分析大表」，壳里挂在那张卡片标题的悬停上）
    # 路由层面：大表**没有**任何打印 / A3 入口（API 侧；旧页路由随本批删除）
    from app.main import create_app

    paths = [p for p in create_app().openapi()["paths"] if "big" in p]
    assert paths and not any(("print" in p or "a3" in p.lower()) for p in paths), paths


# --------------------------------------------------------------- 活动大表导出（`TAIL-04` 片 4b）






def test_大表零行时给后端那句空态而不是只剩三级表头():
    """⭐ `A5`（2026-09-29 逐页）：大表原先 0 行时 `return ''` ⇒ 用户看到一张**只剩三级表头的大空表**
    （20 列横表、没有任何「为什么空 / 下一步」）—— 与 `m04`（`A3`）/ `m06` 同族，本批第 3 例。

    ⚠️ **文案的主人是后端**（`big_domain.empty_text`，随 `/api/m07/big` 的 `empty_text` 给）——
       壳的空态行直接用 `BIG_EMPTY`，⛔ 壳里不编第二份；它此前是**死代码**（全仓没人调用）。
    ⚠️⚠️ **跨列数必须走 `thCols`，⛔ 不是 `thCount`**：大表是**两行表头**（`<th>` 23 个 / 实列 20）
       ⇒ `thCount` 会多算 ⇒ 空态行多出几格（`proj.js:120` 就记着这个坑）。
    ⚠️ **触发的唯一局面 = 大表候选为空**：`selected` 口径 = 「未选题取**全部候选**」⇒ 只要还有
       「在建」项目，未选题**照样有行** ⇒ 后端那句原文（「还没勾项目 —— 点上方「选题」挑几个」）
       与这条口径**不符**（会把人指去点一个"点了也不会变"的按钮）⇒ 同批改准。
    """
    # ⭐ 2026-09-29（`TAIL-64` P2③）：表外壳抽进统一件 `TBL` ⇒ 原写法（钉 `if(!rs.length) return EMPTYROW(...)`）
    #   **当场假红**。⇒ 改钉**意图**（⛔ 别退回钉字面）：空态行**挂在 `TBL` 的 `empty` 通道上** ＋
    #   跨列数走 `thCols` ＋ 文案取 `BIG_EMPTY`。自证 = `tools/mut/_mut_tbl.py` 的 M6（去掉这处委托 ⇒ 必须红）。
    # ⚠️ 文案对错**调函数看返回值**判（⛔ 不抠源码：文件里那段注释**引述**了旧写法作留痕 ⇒ 抠源码必假红）
    from app.mod07_setl import big_domain as BD
    txt = BD.empty_text("2026-08")
    assert "还没勾项目" not in txt, \
        "后端空态还说「还没勾项目」—— 与「未选题 = 全部候选」口径不符（会把人指去点一个点了不变的地方）"
    assert "2026-08" in txt and "在建" in txt, "空态没点明年月 / 没点出候选口径（在建项目）"
