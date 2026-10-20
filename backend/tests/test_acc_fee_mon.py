"""`ACC-FEE-MON-001` · 特殊费用月报表（《说明书》§5.5 ＋ `DEV-R-04` ＋ §8.4 / §9.2 / §2.7.4 / §5.7.2）。

判据点归属：`MOD-09`（能力表 9 行，本用例认领其中 7 行；另两行归 `ACC-I8-TIME-001` / `ACC-X-EXP-001`）。

⚠️ 钉子纪律（`MEMORY` §十二）：
- 断言**绑到那一格 / 那一行**，不用整页 `in`（同页多个金额会互相喂饱）；
- 「该看不见的东西」用**行为**（没有那一行 / 没有那个 action），不绑措辞；
- 取数与合计都**独立复算**（手工筛样本），不复用被验的页面派生函数。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.core.period import MODE_MONTH, period_capabilities
from app.mod08_inv.domain import INV_TABLE_COLUMNS
from app.mod08_inv.models import InvDetail
from app.mod09_fee import domain as D
from app.mod09_fee import repository as R
from app.mod09_fee import service as S
from app.mod09_fee.models import FeeManualItem
from tests.m09_helpers import WH_A, WH_B, YM_NOW, YM_OTHER, session


def test_月度批量录入_按项名幂等且空格子不写():
    """⭐ `TAIL-156`（用户口径「一次录好几个月太麻烦」⇒ 月度批量录入）：新写入口 `S.act_batch` 的三条语义 ——

    ① **按 (核算月, 项目, 项名) 幂等**：同一格重提交 = **改那一条**（⛔ 不是又追加一条）；
    ② **空格子整格跳过**：⛔ 不写 0、也不建行（**"空 ≠ 0"**，与 `001-05` / `001-11` 同口径）；
    ③ **一格非法 ⇒ 整批不写**（写一半会让人分不清哪些进去了 ⇒ 宁可整批退回）。

    ⚠️ **能证伪**：把"空格跳过"改成"空 ⇒ 0"、或把 `R.upsert_item` 换回 `R.add_item` ⇒ 本件必红。
    """
    s = session()
    pid = R.project_by_key(s, WH_A).id
    before = {r["name"]: r["amount"] for r in R.items_of(s, ym=YM_NOW, project_id=pid)}
    n0 = len(before)
    assert "油卡使用" in before and "运费" in before, "样本变了：本件依赖 `m09_helpers` 那两条手填项"

    r1 = S.act_batch(s, project_key=WH_A, items=["油卡使用", "运费", "新项X"],
                     months=[{"ym": YM_NOW, "values": {"油卡使用": "120", "运费": "", "新项X": "9.5"}},
                             {"ym": YM_OTHER, "values": {"油卡使用": "77"}}])
    assert r1["kind"] == "ok", r1
    now = {r["name"]: r["amount"] for r in R.items_of(s, ym=YM_NOW, project_id=pid)}
    assert now["油卡使用"] == Decimal("120"), "① 没改到那一条（或者又追加了一条）"
    assert now["运费"] == before["运费"], "② 空格子被动过（空 ≠ 0 ⇒ 应原值不变）"
    assert now["新项X"] == Decimal("9.5"), "原来没有的项名没被新建"
    assert len(now) == n0 + 1, f"② 空格子建了行（实测 {len(now)} 条，应 {n0 + 1} 条）"
    other = {r["name"]: r["amount"] for r in R.items_of(s, ym=YM_OTHER, project_id=pid)}
    assert other.get("油卡使用") == Decimal("77"), "跨月那一格没落对（或落到了别的月份）"

    # ③ 一格非法 ⇒ 整批不写：这一格里「油卡使用」是**合法值**，但它也必须**没**被写进去
    r2 = S.act_batch(s, project_key=WH_A, items=["油卡使用", "坏格"],
                     months=[{"ym": YM_OTHER, "values": {"油卡使用": "55", "坏格": "abc"}}])
    assert r2["kind"] == "err", "非法金额没被拒"
    after = {r["name"]: r["amount"] for r in R.items_of(s, ym=YM_OTHER, project_id=pid)}
    assert after.get("油卡使用") == Decimal("77"), "被拒之后原值变了（半批落库）"
    assert "坏格" not in after, "被拒之后还是建了行（半批落库）"

# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 2**）：原先这里有一整组**页面观测辅助件**
#    （`_tbody` / `_heads` / `_sum_cells` / `_empty_row` / `_page`）。旧页整体删除（授权 `D18`）
#    后它们**零调用**（逐个数过 ✓）⇒ 一并移除；对应的**形态** claim 已搬到
#    `tests/test_wired_m09.py`（自动项与手填项同桌 / 合计行由共用出口出 / 重置回默认 /
#    空态跨列派生 / 项目面板单选 / 本页不设导出入口 / 表头是本表自己的列 ✓）。
#    ⛔ 判据没删：下面每条只剩**取数、判定、独立复算**的实质，且都改走 `S.build_page_data(...)`。


def _data(ym: str, wh: str = WH_A, sess=None) -> dict:
    """本表当页**数据**（= 旧页渲染前的那份 `build_page_data` 出口；⛔ 不碰任何页面形态）。"""
    s = sess if sess is not None else session()
    return S.build_page_data(s, {"ym": ym, "project": wh})


# ============================================================ 001-01 两类同桌 · 都只统计所选项目


def test_自动项与手填项同桌且都只算所选项目():
    """§5.5：本表 = **1 个自动项 ＋ N 个手填项**，两类内容**都只统计所选项目**。

    ⚠️ 样本里故意埋了四类"不该算"的库存单据行（入库 / 别的 CBS / 别的仓库 / 别的月），
       所以「只算所选项目」这一条**真的会被验到**（不是靠"恰好没有别的数据"）。
    """
    data = S.build_page_data(session(), {"ym": YM_NOW, "project": WH_A})
    # 自动项取数：只认 该月 · 该仓库 · CBS-安文费 · 出库
    assert data["auto"]["amount"] == Decimal("1000.00")
    assert [m["item"] for m in data["manuals"]] == ["油卡使用", "运费"]

    # 换项目 ⇒ 自动项与手填项**都换**（手填项那一份是空的，自动项换成乙仓库的 2000）
    other = S.build_page_data(session(), {"ym": YM_NOW, "project": WH_B})
    assert other["auto"]["amount"] == Decimal("2000.00")
    assert other["manuals"] == []

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


def test_合计等于自动项加手填项且独立复算():
    """§5.5：合计 = 该月 · 该项目的**自动项 ＋ Σ 手填项**。

    ⚠️ **独立复算**：手工按口径筛样本（不复用 `domain.total_amount`），
       并且**再钉一次页面上的那一格**（合计行的金额格）—— 结果对 ≠ 页面印对了。
    """
    s = session()
    data = S.build_page_data(s, {"ym": YM_NOW, "project": WH_A})
    inv = s.by_model[InvDetail]
    items = s.by_model[FeeManualItem]
    auto_want = sum(Decimal(str(r.amount)) for r in inv
                    if r.ym == YM_NOW and r.warehouse_name == WH_A
                    and r.cbs_name == D.CBS_AWF and r.direction == D.DIRECTION_OUT)
    manual_want = sum(Decimal(str(r.amount)) for r in items
                      if r.ym == YM_NOW and r.project_id == 11)
    assert data["total"] == auto_want + manual_want == Decimal("1300.00")
    # ⚠️ 2026-09-19（`§19` 批 2）：原先还钉「合计行的金额格 = `1,300.00`」（千分位形态，借旧页）；
    # 旧页删除（`D18`）后形态搬到壳 —— `test_wired_m09.py::test_壳里合计行由共用出口出` ✓。


# ============================================================ 001-03 按「核算年月 ＋ 项目」各存一份


def test_增改删只落在那一份上():
    """§5.5：手填项按「核算年月 ＋ 项目」**各存一份** —— 写路径不得波及其它月份或其它项目。"""
    s = session()
    jia_now = len(_data(YM_NOW, WH_A, s)["manuals"])
    jia_other = len(_data(YM_OTHER, WH_A, s)["manuals"])

    S.act_add(s, ym=YM_NOW, project_key=WH_B)
    S.act_rename(s, ym=YM_NOW, project_key=WH_B, index=0, value="__断言用项名__")
    S.act_set_amount(s, ym=YM_NOW, project_key=WH_B, index=0, raw="123.45")
    yi = _data(YM_NOW, WH_B, s)["manuals"]
    assert len(yi) == 1 and yi[0]["item"] == "__断言用项名__" and yi[0]["amount"] == Decimal("123.45")

    assert len(_data(YM_NOW, WH_A, s)["manuals"]) == jia_now          # 别的项目一行不动
    assert len(_data(YM_OTHER, WH_A, s)["manuals"]) == jia_other      # 别的月一行不动

    # 删除也只删那一份
    S.act_delete(s, ym=YM_NOW, project_key=WH_B, index=0)
    assert _data(YM_NOW, WH_B, s)["manuals"] == []
    assert len(_data(YM_NOW, WH_A, s)["manuals"]) == jia_now

    # 越界下标 ⇒ 显式报错，且不误删别份
    flash = S.act_delete(s, ym=YM_OTHER, project_key=WH_B, index=0)
    assert flash["kind"] == "err"
    assert len(_data(YM_NOW, WH_A, s)["manuals"]) == jia_now


# ============================================================ 001-04 默认年月 ＋ 重置


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

    # ⚠️ 2026-09-19（`§19` 批 2）：原先还看旧页的「重置」链接（`href="/m09"` 丢掉两个参数）；
    # 旧页删除（`D18`）后形态搬到壳 —— `test_wired_m09.py::test_壳里重置回默认月与默认项目`
    # （`awfReset`：回默认月 ＋ 默认项目 ✓）。上面「默认项目 = 候选第一个」是实质，留着。


# ============================================================ 001-05 未录 ⇒ 空 ＋ 提示行


def test_未录的月份项目为空并给提示行():
    """§5.5：未录的（月 · 项目）⇒ 手填区为空 ＋ 提示行（**跨列数 = 表头列数**）；合计 = 只有自动项。"""
    data = _data(YM_OTHER, WH_A)
    assert data["manuals"] == []
    assert data["total"] == Decimal("3000.00")                   # 只有该月该项目的自动项
    # ⚠️ 2026-09-19（`§19` 批 2）：原先还从旧页抠空态行的 `colspan`（= 表头列数，派生不写死）与合计行的
    # 金额格；旧页删除（`D18`）后形态搬到壳 ——
    # `test_wired_m09.py::test_壳里空态行跨列数由表头派生`（`EMPTYROW(thCount(AWF_THEAD), …)` ✓）＋
    # `…test_壳里合计行由共用出口出` ✓。


# ============================================================ 001-06 项目面板（单选 · 键 = 仓库名）


def test_项目筛选是单选且候选键为仓库名():
    """§2.7.4：候选**键 = 仓库名**、**显示 = 展示名**；面板**单选**（无全选 / 清空）；**壳不进候选**。"""
    data = _data(YM_NOW, WH_A)
    keys = [p.key for p in data["projects"]]
    assert keys == [WH_A, WH_B], f"候选键必须 = **仓库名**（壳不进候选）：{keys}"
    # ⚠️ 2026-09-19（`§19` 批 2）：原先还数旧页 html 里的 radio 组（**单选**恰好一个 checked、
    # 值 = 仓库名、显示 = 展示名、`[object Object]` 守卫、无「全选 / 清空」）；旧页删除（`D18`）后
    # 形态搬到壳 —— `test_wired_m09.py::test_壳里项目面板是单选且候选键来自后端` ✓
    # （`single:true` ⇒ 渲染 radio、⛔ 不给全选/清空；候选由后端 `projects` 的 `key` 落定 ⇒ 不会
    # `[object Object]`；显示名由壳的 `PROJ_META_KEY` 出）。


# ============================================================ 001-07 金额非法 ⇒ 拒绝且原值不变


def test_手填金额非法被拒绝且原值不变():
    """§8.4 第 ③ 档：手填项**只拦「非数字」，允许 0 与负数**；非法 ⇒ 拒绝 ＋ 原值不变。"""
    s = session()
    before = _data(YM_NOW, WH_A, s)["manuals"][0]["amount"]
    flash = S.act_set_amount(s, ym=YM_NOW, project_key=WH_A, index=0, raw="oops")
    assert flash["kind"] == "err" and D.MSG_BAD_AMOUNT in flash["message"]
    assert _data(YM_NOW, WH_A, s)["manuals"][0]["amount"] == before      # **绑那一格**，不看 kind

    for ok in ("0", "-500.25"):                                  # 0 与负数**合法**（此处有意最宽松）
        assert S.act_set_amount(s, ym=YM_NOW, project_key=WH_A, index=0, raw=ok)["kind"] == "ok"
        assert _data(YM_NOW, WH_A, s)["manuals"][0]["amount"] == Decimal(ok)


# ============================================================ 001-08 删除反馈带重算后的合计


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


# 001-09的实际断言在 test_wired_m09.py，本件不再保留空测试。


# ============================================================ 001-10 独立新报表（不是透视表形态）


def test_是独立新报表而非库存单据透视形态():
    """`DEV-R-04`：本表 = **独立新报表**，**不是**库存单据的第 3 张透视表。

    可观测形态：**表头 = 本表自己的列出口**（5 列），**含库存单据没有的列**
    （数据项 / 来源 / 占合计）且**不含任何库存单据的特征列**（单据编号 / 物料 / 数量 / 仓库 /
    `cbs 名称` / 价税合计 …）—— 透视表不可能长这样。
    """
    mine = [c["label"] for c in D.AWF_COLUMNS]
    # ⚠️ 2026-09-19（`§19` 批 2）：原先拿**旧页**渲染出的表头比对（`_heads(html) == mine`），
    # 还看页面上有没有「独立 / 透视」两词；旧页删除（`D18`）后形态搬到壳 ——
    # `test_wired_m09.py::test_壳里表头是本表自己的列而非库存单据透视形态` ✓（比 `AWF_THEAD`）。
    assert set(mine) - {c["label"] for c in INV_TABLE_COLUMNS} == {"数据项", "来源", "占合计"}
    assert not (set(mine) & {"单据编号", "序号", "方向", "物料", "规格", "单位", "数量",
                             "不含税单价", "含税单价", "调整后金额", "价税合计",
                             "业务类型", "供应商 / 班组", "单据日期", "审核日期", "仓库",
                             "wbs 名称", "cbs 名称"})
    assert len(mine) < len(INV_TABLE_COLUMNS)


# ============================================================ 001-11 不做「上次值带入」


def test_手填项不带入上月值():
    """§5.7.2：带入**只属活动大表** ⇒ 本表未录的月**就是空**（不预填、不标注来源月份）。"""
    s = session()
    data = _data(YM_OTHER, WH_A, s)
    assert data["manuals"] == []
    # ⚠️ 2026-09-19（`§19` 批 2）：原先还数旧页 tbody 里的手填行（`data-kind="manual"`）= 0；
    # 旧页删除（`D18`）后形态搬到壳 —— 壳的手填行**只由后端 `list` 渲染**、`list` 为空时只余空态行
    # （`test_wired_m09.py` 的 001-01 / 001-05 ✓）⇒ 未录的月**一个预填行都没有**
    # ——「别月的项名不得被带过来」这条**实质**就是上面那句 `data["manuals"] == []` ✓。
    assert data["auto"]["amount"] == Decimal("3000.00")         # 自动项照旧按"该月 · 该项目"取
