"""`ACC-FEE-MON-001` · 特殊费用月报表（《说明书》§5.5 ＋ `DEV-R-04` ＋ §8.4 / §9.2 / §2.7.4 / §5.7.2）。

判据点归属：`MOD-09`（能力表 9 行，本用例认领其中 7 行；另两行归 `ACC-I8-TIME-001` / `ACC-X-EXP-001`）。

⚠️ 钉子纪律（`MEMORY` §十二）：
- 断言**绑到那一格 / 那一行**，不用整页 `in`（同页多个金额会互相喂饱）；
- 「该看不见的东西」用**行为**（没有那一行 / 没有那个 action），不绑措辞；
- 取数与合计都**独立复算**（手工筛样本），不复用被验的页面派生函数。
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from app.core.period import MODE_MONTH, period_capabilities
from app.mod08_inv.domain import INV_TABLE_COLUMNS
from app.mod08_inv.models import InvDetail
from app.mod09_fee import domain as D
from app.mod09_fee import service as S
from app.mod09_fee import view as V
from app.mod09_fee.models import FeeManualItem
from tests.acc_plugin import acc
from tests.m09_helpers import WH_A, WH_B, YM_NOW, YM_OTHER, session

# ============================================================ HTML 取格子（**按格取，不整页撞**）

_TABLE_RE = re.compile(r'<table class="dt" data-sort-key="m09:awf">')
_TBODY_RE = re.compile(r"<tbody>([\s\S]*?)</tbody>")


def _tbody(html: str) -> str:
    start = _TABLE_RE.search(html)
    assert start is not None, "页面上找不到本表（data-sort-key=m09:awf）"
    body = _TBODY_RE.search(html[start.start():])
    assert body is not None, "本表没有 tbody"
    return body.group(1)


def _heads(html: str) -> list[str]:
    start = _TABLE_RE.search(html)
    assert start is not None
    return [re.sub(r"<[^>]*>", "", h).strip()
            for h in re.findall(r"<th[^>]*>([\s\S]*?)</th>", html[start.start():])]


def _sum_cells(html: str) -> list[str]:
    m = re.search(r'<tr class="sumrow">([\s\S]*?)</tr>', _tbody(html))
    assert m is not None, "本表没有合计行（sumrow）"
    return [re.sub(r"<[^>]*>", "", c).strip() for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", m.group(1))]


def _empty_row(html: str) -> tuple[int, str]:
    m = re.search(r'<tr class="empty"[^>]*>\s*<td colspan="(\d+)"[^>]*>([\s\S]*?)</td>', _tbody(html))
    assert m is not None, "未录的那一份没有提示行"
    return int(m.group(1)), re.sub(r"<[^>]*>", "", m.group(2)).strip()


def _page(ym: str, wh: str = WH_A, sess=None) -> tuple[dict, str]:
    s = sess if sess is not None else session()
    data = S.build_page_data(s, {"ym": ym, "project": wh})
    return data, V.render_fee_page(data)


# ============================================================ 001-01 两类同桌 · 都只统计所选项目


@acc("ACC-FEE-MON-001", "001-01")
def test_自动项与手填项同桌且都只算所选项目():
    """§5.5：本表 = **1 个自动项 ＋ N 个手填项**，两类内容**都只统计所选项目**。

    ⚠️ 样本里故意埋了四类"不该算"的库存单据行（入库 / 别的 CBS / 别的仓库 / 别的月），
       所以「只算所选项目」这一条**真的会被验到**（不是靠"恰好没有别的数据"）。
    """
    data, html = _page(YM_NOW, WH_A)
    # 自动项取数：只认 该月 · 该仓库 · CBS-安文费 · 出库
    assert data["auto"]["amount"] == Decimal("1000.00")
    assert [m["item"] for m in data["manuals"]] == ["油卡使用", "运费"]

    body = _tbody(html)
    assert body.count('data-kind="auto"') == 1 and body.count('data-kind="manual"') == 2

    # 换项目 ⇒ 自动项与手填项**都换**（手填项那一份是空的，自动项换成乙仓库的 2000）
    other, other_html = _page(YM_NOW, WH_B)
    assert other["auto"]["amount"] == Decimal("2000.00")
    assert other["manuals"] == []
    assert "油卡使用" not in other_html

    # ⭐ **直接钉域内核本身**（不借道 `repository` 那条 SQL 过滤）：
    #    否则「只算该月 · 该仓库 · 该 CBS · 出库」四条**一条都没真被验到** ——
    #    实测（反向灵敏度）：把 `auto_amount` 里的**月份 / 出库**判据改坏，上面那些页面级断言**照绿**，
    #    因为仓储层已经把该月筛过了（判据骑在别人的闸上 ⇒ 假绿）。下面这组数据每一条**只错一项**。
    rows = [
        {"ym": YM_NOW, "warehouse": WH_A, "cbs": D.CBS_AWF, "direction": D.DIRECTION_OUT, "amount": "10.00"},
        {"ym": YM_OTHER, "warehouse": WH_A, "cbs": D.CBS_AWF, "direction": D.DIRECTION_OUT, "amount": "100.00"},
        {"ym": YM_NOW, "warehouse": WH_B, "cbs": D.CBS_AWF, "direction": D.DIRECTION_OUT, "amount": "1000.00"},
        {"ym": YM_NOW, "warehouse": WH_A, "cbs": "CBS-其他", "direction": D.DIRECTION_OUT, "amount": "10000.00"},
        {"ym": YM_NOW, "warehouse": WH_A, "cbs": D.CBS_AWF, "direction": "入库", "amount": "100000.00"},
    ]
    assert D.auto_amount(rows, ym=YM_NOW, project_key=WH_A) == Decimal("10.00")


# ============================================================ 001-02 合计 = 独立复算


@acc("ACC-FEE-MON-001", "001-02")
def test_合计等于自动项加手填项且独立复算():
    """§5.5：合计 = 该月 · 该项目的**自动项 ＋ Σ 手填项**。

    ⚠️ **独立复算**：手工按口径筛样本（不复用 `domain.total_amount`），
       并且**再钉一次页面上的那一格**（合计行的金额格）—— 结果对 ≠ 页面印对了。
    """
    s = session()
    data, html = _page(YM_NOW, WH_A, s)
    inv = s.by_model[InvDetail]
    items = s.by_model[FeeManualItem]
    auto_want = sum(Decimal(str(r.amount)) for r in inv
                    if r.ym == YM_NOW and r.warehouse_name == WH_A
                    and r.cbs_name == D.CBS_AWF and r.direction == D.DIRECTION_OUT)
    manual_want = sum(Decimal(str(r.amount)) for r in items
                      if r.ym == YM_NOW and r.project_id == 11)
    assert data["total"] == auto_want + manual_want == Decimal("1300.00")
    assert _sum_cells(html)[2] == "1,300.00"        # 合计行的**金额格**（千分位形态）


# ============================================================ 001-03 按「核算年月 ＋ 项目」各存一份


@acc("ACC-FEE-MON-001", "001-03")
def test_增改删只落在那一份上():
    """§5.5：手填项按「核算年月 ＋ 项目」**各存一份** —— 写路径不得波及其它月份或其它项目。"""
    s = session()
    jia_now = len(_page(YM_NOW, WH_A, s)[0]["manuals"])
    jia_other = len(_page(YM_OTHER, WH_A, s)[0]["manuals"])

    S.act_add(s, ym=YM_NOW, project_key=WH_B)
    S.act_rename(s, ym=YM_NOW, project_key=WH_B, index=0, value="__断言用项名__")
    S.act_set_amount(s, ym=YM_NOW, project_key=WH_B, index=0, raw="123.45")
    yi = _page(YM_NOW, WH_B, s)[0]["manuals"]
    assert len(yi) == 1 and yi[0]["item"] == "__断言用项名__" and yi[0]["amount"] == Decimal("123.45")

    assert len(_page(YM_NOW, WH_A, s)[0]["manuals"]) == jia_now          # 别的项目一行不动
    assert len(_page(YM_OTHER, WH_A, s)[0]["manuals"]) == jia_other      # 别的月一行不动

    # 删除也只删那一份
    S.act_delete(s, ym=YM_NOW, project_key=WH_B, index=0)
    assert _page(YM_NOW, WH_B, s)[0]["manuals"] == []
    assert len(_page(YM_NOW, WH_A, s)[0]["manuals"]) == jia_now

    # 越界下标 ⇒ 显式报错，且不误删别份
    flash = S.act_delete(s, ym=YM_OTHER, project_key=WH_B, index=0)
    assert flash["kind"] == "err"
    assert len(_page(YM_NOW, WH_A, s)[0]["manuals"]) == jia_now


# ============================================================ 001-04 默认年月 ＋ 重置


@acc("ACC-FEE-MON-001", "001-04")
def test_默认核算年月为上月且重置回默认():
    """§9.2：材料报表类默认年月 = **北京时间上月**；本页**只开放按月**；「重置」回到默认。"""
    assert D.default_ym(date(2026, 9, 15)) == "2026-08"
    assert D.default_ym(date(2026, 1, 5)) == "2025-12"           # 跨年
    assert period_capabilities("fee") == (MODE_MONTH,)           # 只开放「月」
    assert S.parse_state({})["ym"] == D.default_ym()             # 不给参数 ⇒ 落默认
    assert S.parse_state({"ym": "2026-13"})["ym"] == D.default_ym()   # 非法月份 ⇒ 落默认（不猜）

    s = session()
    default = S.build_page_data(s, S.parse_state({}))
    assert default["ym"] == D.default_ym()
    assert default["project"] == default["projects"][0].key       # 默认项目 = 候选第一个

    # 页面的「重置」= 回本站根（丢掉 ym / pj 两个参数 ⇒ 回到默认月份 ＋ 默认项目）
    html = V.render_fee_page(S.build_page_data(s, {"ym": YM_OTHER, "project": WH_B}))
    assert 'href="/m09"' in html


# ============================================================ 001-05 未录 ⇒ 空 ＋ 提示行


@acc("ACC-FEE-MON-001", "001-05")
def test_未录的月份项目为空并给提示行():
    """§5.5：未录的（月 · 项目）⇒ 手填区为空 ＋ 提示行（**跨列数 = 表头列数**）；合计 = 只有自动项。"""
    data, html = _page(YM_OTHER, WH_A)
    assert data["manuals"] == []
    span, text = _empty_row(html)
    assert span == len(D.AWF_COLUMNS) == len(_heads(html))       # 派生自表头列数，不写死
    assert text                                                  # 只验"不是空白"，**不绑措辞**
    assert data["total"] == Decimal("3000.00")                   # 只有该月该项目的自动项
    assert _sum_cells(html)[2] == "3,000.00"


# ============================================================ 001-06 项目面板（单选 · 键 = 仓库名）


@acc("ACC-FEE-MON-001", "001-06")
def test_项目筛选是单选且候选键为仓库名():
    """§2.7.4：候选**键 = 仓库名**、**显示 = 展示名**；面板**单选**（无全选 / 清空）；**壳不进候选**。"""
    _, html = _page(YM_NOW, WH_A)
    radios = re.findall(r'<input type="radio"[^>]*name="pj"[^>]*>', html)
    assert len(radios) == 2                                      # 甲 / 乙；壳（无仓库）不进候选
    assert sum('checked' in r for r in radios) == 1              # **单选**：恰好一个被选中
    assert 'value="甲仓库"' in html and 'value="乙仓库"' in html   # 值 = 仓库名（键）
    assert "甲公司项目" in html and "某壳" not in html            # 显示 = 展示名；壳不出现
    assert "[object Object]" not in html                         # 不得渲染成对象字面量
    assert "全选" not in html and "清空" not in html


# ============================================================ 001-07 金额非法 ⇒ 拒绝且原值不变


@acc("ACC-FEE-MON-001", "001-07")
def test_手填金额非法被拒绝且原值不变():
    """§8.4 第 ③ 档：手填项**只拦「非数字」，允许 0 与负数**；非法 ⇒ 拒绝 ＋ 原值不变。"""
    s = session()
    before = _page(YM_NOW, WH_A, s)[0]["manuals"][0]["amount"]
    flash = S.act_set_amount(s, ym=YM_NOW, project_key=WH_A, index=0, raw="oops")
    assert flash["kind"] == "err" and D.MSG_BAD_AMOUNT in flash["message"]
    assert _page(YM_NOW, WH_A, s)[0]["manuals"][0]["amount"] == before      # **绑那一格**，不看 kind

    for ok in ("0", "-500.25"):                                  # 0 与负数**合法**（此处有意最宽松）
        assert S.act_set_amount(s, ym=YM_NOW, project_key=WH_A, index=0, raw=ok)["kind"] == "ok"
        assert _page(YM_NOW, WH_A, s)[0]["manuals"][0]["amount"] == Decimal(ok)


# ============================================================ 001-08 删除反馈带重算后的合计


@acc("ACC-FEE-MON-001", "001-08")
def test_删除给反馈且带重算后的合计():
    """§5.5 ＋ 设计规则 `R9`：删除**必须给反馈**，且反馈里带**重算后的合计**。"""
    s = session()
    assert S.build_page_data(s, {"ym": YM_NOW, "project": WH_A})["total"] == Decimal("1300.00")
    flash = S.act_delete(s, ym=YM_NOW, project_key=WH_A, index=0)          # 删掉 100.00 的那条
    assert flash["kind"] == "ok"
    assert "油卡使用" in flash["message"]                                   # 说清删了哪一条
    after = S.build_page_data(s, {"ym": YM_NOW, "project": WH_A})["total"]
    assert after == Decimal("1200.00")                                      # 真的重算了
    assert D.money_text(after) in flash["message"]                          # 反馈里带的就是它


# ============================================================ 001-09 随台账导出 · 不设单独导出


@acc("ACC-FEE-MON-001", "001-09")
def test_随逐月欠款台账导出且本页不设导出按钮():
    """§7.1 / §5.5：本表**随「逐月欠款台账」导出**，页面须说明；**本页不设单独导出按钮**。"""
    _, html = _page(YM_NOW, WH_A)
    assert "逐月欠款台账" in html and "特殊费用月报表" in html          # 说明里点了台账与三个工作表
    actions = re.findall(r'<form[^>]*action="([^"]*)"', html)
    assert actions, "页面应有表单（筛选 / 增删改）"
    assert all("export" not in a for a in actions)                      # **没有**导出入口
    assert not re.search(r'(?:action|href)="[^"]*export', html)


# ============================================================ 001-10 独立新报表（不是透视表形态）


@acc("ACC-FEE-MON-001", "001-10")
def test_是独立新报表而非库存单据透视形态():
    """`DEV-R-04`：本表 = **独立新报表**，**不是**库存单据的第 3 张透视表。

    可观测形态：**表头 = 本表自己的列出口**（5 列），**含库存单据没有的列**
    （数据项 / 来源 / 占合计）且**不含任何库存单据的特征列**（单据编号 / 物料 / 数量 / 仓库 /
    `cbs 名称` / 价税合计 …）—— 透视表不可能长这样。
    """
    _, html = _page(YM_NOW, WH_A)
    mine = [c["label"] for c in D.AWF_COLUMNS]
    assert _heads(html) == mine
    assert set(mine) - {c["label"] for c in INV_TABLE_COLUMNS} == {"数据项", "来源", "占合计"}
    assert not (set(mine) & {"单据编号", "序号", "方向", "物料", "规格", "单位", "数量",
                             "不含税单价", "含税单价", "调整后金额", "价税合计",
                             "业务类型", "供应商 / 班组", "单据日期", "审核日期", "仓库",
                             "wbs 名称", "cbs 名称"})
    assert len(mine) < len(INV_TABLE_COLUMNS)
    assert "独立" in html and "透视" in html


# ============================================================ 001-11 不做「上次值带入」


@acc("ACC-FEE-MON-001", "001-11")
def test_手填项不带入上月值():
    """§5.7.2：带入**只属活动大表** ⇒ 本表未录的月**就是空**（不预填、不标注来源月份）。"""
    s = session()
    data, html = _page(YM_OTHER, WH_A, s)
    assert data["manuals"] == []
    assert _tbody(html).count('data-kind="manual"') == 0        # 一个预填行都没有
    assert "油卡使用" not in html and "运费" not in html          # 别月的项名不得被带过来
    assert data["auto"]["amount"] == Decimal("3000.00")         # 自动项照旧按"该月 · 该项目"取
