"""`ACC-RPT-BIG-001` —— **经济活动分析大表**的验收断言（§5.7.1 / §5.7.2 / §5.7.3）。

覆盖点 = `PRD/验收/验收基线.json` 里该用例的 15 个判据点（`001-01` … `001-15`）。

⚠️ **判据点 ↔ 实现出口的对应**（每条都钉在**那一条逻辑本身**上，不钉"恰好也对的结果"）：
- 列结构 / 手填列集合 → `big_domain.BIG_COLUMNS` / `BIG_MANUAL`（**表头与列同源**）
- 带入 → `big_domain.manual_cell`（**`is not None` 判据**，不是真值判断）
- 派生 → `total_of` / `use_rate` / `output_rate`（**独立复算**：期望值手写在 `m07_big_helpers.EXPECT`）
- 页面 / 导出 → `big_view.render_big_page` / `render_export_page`（**同一份行装配** ⇒ 两处同序）
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from app.mod07_setl import big_domain as B
from app.mod07_setl import big_repository as R
from app.mod07_setl import big_service as S
from tests.acc_plugin import acc
from tests.m07_big_helpers import (
    DEFAULT_ORDER, EXPECT, WH_A, WH_ARCHIVED, WH_B, WH_C, WH_D, WH_SHELL,
    YM_EARLIER, YM_NOW, YM_PREV, dataset, make_order,
)
from tests.m08_helpers import FakeSession

CASE = "ACC-RPT-BIG-001"


# ============================================================ 桩


def _session(order=None) -> FakeSession:
    return FakeSession(dataset(order=order))


def _data(s=None, month: str = YM_NOW, order=None) -> dict:
    return S.build_big_data(s or _session(order), {"month": month})


# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 2**）：原先这里有一组**页面观测辅助件** ——
#    `_html()`（取旧页 HTML）· `_cell()`（从页面里抠那一格）· `_table()`（抠表体那一段）。
#    旧页（`big_view`）整体删除（授权 `D18`）后三者**零调用**（逐个数过 ✓）⇒ 一并移除。
#    ⛔ 判据一条没删：形态 claim 全在 `tests/test_wired_m07.py`（`ACC-RPT-BIG-001` 那 8 条 ✓）。


def _rows(data: dict) -> dict[str, dict]:
    return {r["warehouse"]: r for r in data["rows"]}


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


# ============================================================ 列结构（001-01 / 001-02 / 001-03）


@acc(CASE, "001-01")
def test_手填列集合以主人节为准_主材累计不在手填里():
    """§5.7.1：手填列 = **开工时间 / 机械费测算 / 合同（预估）价 / 产值累计（含税）/ 工程用油 / 备注**。

    ⭐ 「主材累计（含税）」**已由手填改为派生**（2026-09-13 用户裁定）⇒ 它**不在**手填列里。
    """
    assert tuple(m["key"] for m in B.BIG_MANUAL) == (
        "open_ym", "mech_est", "contract", "output_cum", "oil", "note")
    assert "mat_cum" not in B.BIG_MANUAL_KEYS, "主材累计已改派生 ⇒ 不得再当手填列"
    # 手填列在整表里**确实是手填性质**（两个清单必须自洽）
    for m in B.BIG_MANUAL:
        col = next(c for c in B.BIG_COLUMNS if c["key"] == m["key"])
        assert col["kind"] == B.KIND_HAND, f"{m['key']} 在手填清单里，却不是 hand 列"
    assert len(B.BIG_MANUAL) == 6


@acc(CASE, "001-02")
def test_列结构为用户最终模板_且不含已裁掉的列():
    """§5.7.1：列结构 = 用户给的**最终模板** ⇒ 表头齐备、且**不含已裁掉的明细列**。"""
    assert B.BIG_LABELS == (
        "序号", "项目名称", "开工时间",
        "焊材累计", "焊材当月", "三气累计", "三气当月",
        "外租机械开工累计", "外租机械当月", "设备租赁开工累计", "设备租赁当月",
        "合计", "机械费测算", "使用率",
        "产值完成率", "合同（预估）价", "产值累计（含税）",
        "主材累计（含税）", "工程用油", "备注",
    )
    assert len(B.BIG_COLUMNS) == 20
    # 两行表头的**叶数**必须等于列数（两行表头最容易"看着对、其实错位"）
    leaves = sum(len(subs) if subs else 1 for _g, subs in B.BIG_HEADER)
    assert leaves == len(B.BIG_COLUMNS) == 20
    # ⚠️ 已裁掉的列不得出现；而「辅材使用（不含税）」是**保留**的组标签（别把两者搞混）
    # ⚠️ 2026-09-19（`§19` 批 2）：原先拿**旧页表头**（`V._thead()`）去扫；旧页删除（授权 `D18`）后
    # 改扫**壳的表头** —— `test_wired_m07.py::test_壳里表头不含已裁掉的列`（同一个 `boundary_violations` ✓）。


@acc(CASE, "001-03")
def test_输入框只出现在手填列_自动与派生列一律只读():
    """§5.7.1：**手填输入框只出现在手填列上**；材料 / 机械的取数列与派生列一律只读。"""
    rows = len(_rows(_data()))
    assert sum(c["kind"] == B.KIND_HAND for c in B.BIG_COLUMNS) == 6, "手填列不是 6 个"
    # ⚠️ 2026-09-19（`§19` 批 2）：原先在**旧页** HTML 里数 `class="inp "` 与逐列找输入框；
    # 旧页删除（授权 `D18`）后形态搬到壳 —— `test_wired_m07.py::test_壳里输入框只出现在手填列`
    # （壳只经一个 `cell()` 生成器渲染输入框、且只调 `cell(0)…cell(5)` ⇒ ⛔ 没有第 7 个 ✓），
    # 上面那句「手填列恰好 6 个」是数据侧的实质。
    assert rows > 0


# ============================================================ 派生列（001-04 / 001-05）


@acc(CASE, "001-04")
def test_派生列独立复算():
    """§5.7.1：合计 = 外租累计 ＋ 设备租赁累计；使用率 = 合计 ÷ 机械费测算；产值完成率 = 产值累计 ÷ 合同价。

    ⭐ 期望值**手写**在 `m07_big_helpers.EXPECT`（不从被测量的对象反推）；比率再**独立算一遍**。
    """
    rows = _rows(_data())
    a = rows[WH_A]
    assert _money(a["derived"]["total_cum"]) == _money(EXPECT[WH_A]["total_cum"]), "合计 ≠ 两个累计之和"
    # 独立复算（用自己的两个加数，而不是"合计字段"）
    rent, lease = Decimal(EXPECT[WH_A]["rent_cum"]), Decimal(EXPECT[WH_A]["lease_cum"])
    want_total = rent + lease
    assert _money(a["derived"]["total_cum"]) == _money(want_total)
    want_use = (want_total / Decimal(EXPECT[WH_A]["mech_est"])).quantize(Decimal("0.0001"))
    assert a["derived"]["use_rate"] == want_use, "使用率 ≠ 合计 ÷ 机械费测算"
    want_done = (Decimal(EXPECT[WH_A]["carry"]["output_cum"]) / Decimal("10000.00")).quantize(Decimal("0.0001"))
    assert a["derived"]["output_rate"] == want_done, "产值完成率 ≠ 产值累计 ÷ 合同价"
    # 分母为空 / 为 0 ⇒ `None`（**不臆造 0**：0 会冒充"使用率为 0"）
    assert B.use_rate(Decimal("100.00"), None) is None
    assert B.use_rate(Decimal("100.00"), Decimal("0.00")) is None
    assert B.output_rate(Decimal("100.00"), None) is None
    assert B.output_rate(Decimal("100.00"), Decimal("0.00")) is None
    # 派生列**只读**：⚠️ 2026-09-19（`§19` 批 2）原先在**旧页** HTML 里查那几格有没有输入框；
    # 旧页删除（授权 `D18`）后形态搬到壳 —— `test_wired_m07.py::test_壳里派生列是纯文本格`
    # （壳里合计/使用率/产值完成率走 `M(...)`/`pct(...)`，⛔ 不经手填 `cell()` ✓）。


@acc(CASE, "001-05")
def test_主材累计取集采结算额_只计纳入台账():
    """§5.7.1 末条：主材累计（含税）= **按项目取集采台账结算额**，且**只计「纳入台账」的合同**。

    `contracts` 每行 = 集采合同落库行的最小投影：`{"project": 仓库名, "in_ledger": 是否纳入台账, "settle": 结算金额}`。
    """
    contracts = [
        {"project": WH_A, "in_ledger": True, "settle": "100.00"},
        {"project": WH_A, "in_ledger": True, "settle": "20.50"},
        {"project": WH_A, "in_ledger": False, "settle": "999.00"},      # 未纳入台账 ⇒ 不计
        {"project": WH_B, "in_ledger": True, "settle": "7.00"},         # 别的项目 ⇒ 不计
    ]
    assert B.main_material_total(contracts, project_key=WH_A) == Decimal("120.50")
    assert B.main_material_total(contracts, project_key=WH_B) == Decimal("7.00")
    # 该项目确实没有纳入台账的合同 ⇒ **0**（与"取数口未接入"是两回事）
    assert B.main_material_total(contracts, project_key=WH_D) == Decimal("0.00")
    # ⭐ 2026-09-21（`TAIL-25`）取数口**已接入**（M5 集采台账落地）⇒ 该列显示**真数**；
    #    "不可得 ⇒ `None`"的那条路保留给**显式摘除**（`set_main_material_port(None)`）——
    #    ⚠️ 两件事不许混：**没合同 = 0**（上面那行），**取不到数 = None**（现在只有显式摘除才发生）。
    assert S.MAIN_MATERIAL_PORT is not None
    # ⚠️ 2026-09-19（`§19` 批 2）：原先拿**旧页**的 `_cell_html` 渲染那一格、断言里面是「—」不是 `0.00`；
    # 旧页删除（授权 `D18`）后形态搬到壳 —— `test_wired_m07.py::test_壳里主材累计走金额出口且取数口未接入`
    # （壳里它是**派生文本格**（`M(r.matC)`），⛔ 不是手填输入框；「0.00 与取数口没接」两件事不许混 ✓）。
    mat = next(c for c in B.BIG_COLUMNS if c["key"] == "mat_cum")
    assert mat["kind"] == B.KIND_DERIVED, "主材累计不是派生列了"


# ============================================================ 手填与写入语义（001-06 / 001-07 / 001-08）


@acc(CASE, "001-06")
def test_手填值落在本月_编辑一格不连带确认同行其他格():
    """§5.7.2：手填值录入后落在**本月**；**编辑一格不连带确认同行其他格**（其余仍保持带入态）。"""
    s = _session()
    res = S.save_manual_cell(s, month=YM_NOW, warehouse=WH_B, key="open_ym", raw="2023-05",
                             cands=_data(s)["candidates"])
    assert res["ok"], res["message"]
    row = _rows(_data(s))[WH_B]
    assert row["manual"]["open_ym"] == {"value": "2023-05", "from": ""}, "本月没录上"
    # 其余格**仍是带入态**（没有被"连带确认"）
    for key in ("mech_est", "contract", "output_cum", "oil"):
        assert row["manual"][key]["from"] == YM_EARLIER, f"{key} 被连带确认了（应仍带入）"
    # 只写了这一格 ⇒ 库里那一行只有这一个键有值
    stored = R.load_manual(s)[YM_NOW][WH_B]
    assert stored["open_ym"] == "2023-05"
    assert all(stored[k] is None for k in ("mech_est", "contract", "output_cum", "oil", "note"))


@acc(CASE, "001-07")
def test_开工时间只认年月格式_非法拒绝且原值不变():
    """§5.7.1：开工时间列格式 = **`年-月`** ⇒ 非法格式被拒、合法格式可写入。"""
    assert B.parse_manual("2026-03", B.FMT_YM)["ok"]
    assert B.parse_manual("2026-03", B.FMT_YM)["value"] == "2026-03"
    for bad in ("2026-3", "2026/03", "26-03", "2026-13", "2026-00", "2026-03-01", "abc"):
        got = B.parse_manual(bad, B.FMT_YM)
        assert not got["ok"], f"{bad} 竟然被当成合法年月"
        assert got["value"] is None
    # 走写动作：非法 ⇒ **不写库**，库里原值不变
    s = _session()
    cands = _data(s)["candidates"]
    before = R.load_manual(s)[YM_PREV][WH_A]["open_ym"]
    res = S.save_manual_cell(s, month=YM_NOW, warehouse=WH_A, key="open_ym", raw="2026-3", cands=cands)
    assert not res["ok"] and res["message"] == B.MSG_BAD_YM
    assert R.load_manual(s)[YM_PREV][WH_A]["open_ym"] == before, "非法输入改动了原值"
    assert (R.load_manual(s).get(YM_NOW, {}).get(WH_A, {}) or {}).get("open_ym") is None, "非法输入竟然落库"


@acc(CASE, "001-08")
def test_非法金额与负数都被拒绝且原值不变():
    """§5.7.1：**非法金额与负数都必须被拒绝**，且原值不变。"""
    for bad in ("abc", "1e3x", "-1", "-0.01"):
        got = B.parse_manual(bad, B.FMT_MONEY)
        assert not got["ok"], f"{bad} 竟然被当成合法金额"
    assert B.parse_manual("0", B.FMT_MONEY) == {"ok": True, "value": Decimal("0.00"), "message": ""}
    s = _session()
    cands = _data(s)["candidates"]
    before = R.load_manual(s)[YM_PREV][WH_A]["mech_est"]
    for bad in ("abc", "-100"):
        res = S.save_manual_cell(s, month=YM_NOW, warehouse=WH_A, key="mech_est", raw=bad, cands=cands)
        assert not res["ok"] and res["message"] == B.MSG_BAD_MONEY
    assert R.load_manual(s)[YM_PREV][WH_A]["mech_est"] == before, "非法 / 负数输入改动了原值"


# ============================================================ 带入（001-09 / 001-10 / 001-11 / 001-12）


@acc(CASE, "001-09")
def test_零是合法录入值_不得被误判成未录入():
    """§5.7.2：**0 是合法录入值**，不得被当成「未录入」而重新触发带入。"""
    own = {YM_NOW: {WH_C: {"oil": Decimal("0.00")}}}
    got = B.manual_cell(own, YM_NOW, WH_C, "oil")
    assert got == {"value": Decimal("0.00"), "from": ""}, "0 被当成「未录入」了（会重新带入）"
    # ⚠️ 这条是**判据本身**：判「未录入」必须用 `is None`，不能用真值判断（`if not v` 会把 0 吃掉）
    # ⚠️ 2026-09-19（`§19` 批 2）：原先在**旧页** HTML 里查那一格有没有带入标记、值有没有写进输入框；
    # 旧页删除（授权 `D18`）后形态搬到壳 —— `test_wired_m07.py::test_壳里零与未录入在输入框上分得开`
    # （壳的 `bigDisp` 用**严格 `==null`** 判空 ⇒ 合法的 `0` **不会被吞掉**；带入标记只看 `c.from` ✓）。


@acc(CASE, "001-10")
def test_上次值带入_最近一次_清空回带入态_无记录留空():
    """§5.7.2：本月未录 ⇒ 向前取**最近一次录入值**预填并标来源月；清空 ⇒ 回带入态；无记录 ⇒ 留空。"""
    rows = _rows(_data())
    a = rows[WH_A]["manual"]
    for key, want in EXPECT[WH_A]["carry"].items():
        got = a[key]["value"]
        assert (_money(got) == _money(want)) if key not in ("note", "open_ym") else (got == want), \
            f"甲仓 {key} 带入值不对：{got!r} ≠ {want!r}"
        assert a[key]["from"] == YM_PREV, f"甲仓 {key} 的来源月不对（应最近一次 = {YM_PREV}）"
    assert a["mech_est"] == {"value": Decimal("1600.00"), "from": ""}, "本月已录的格不该带入"
    # **跨月回退**：乙仓 07 月没有记录 ⇒ 取 06 月
    b = rows[WH_B]["manual"]
    assert _money(b["contract"]["value"]) == Decimal("1000.00") and b["contract"]["from"] == YM_EARLIER
    assert b["oil"]["from"] == YM_EARLIER
    # **全程无记录** ⇒ 留空待填（不得硬凑）
    d = rows[WH_D]["manual"]
    assert all(c["value"] is None and c["from"] == "" for c in d.values()), "丁仓被硬凑了值"
    # **清空 ⇒ 回到带入态**
    s = _session()
    R.save_cell(s, ym=YM_NOW, warehouse=WH_A, key="oil", value=None)
    row = _rows(_data(s))[WH_A]
    assert _money(row["manual"]["oil"]["value"]) == Decimal("100.00"), "清空后没回到带入态"
    assert row["manual"]["oil"]["from"] == YM_PREV


@acc(CASE, "001-11")
def test_带入是只读派生_历史月份录入值不被改写():
    """§5.7.2：带入**只读派生** ⇒ 历史月份的录入值本身**不被改写**。"""
    s = _session()
    before = {ym: dict(whs) for ym, whs in R.load_manual(s).items()}
    _data(s)                                            # 渲染 + 装配（包含带入）
    res = S.save_manual_cell(s, month=YM_NOW, warehouse=WH_A, key="contract", raw="12345.00",
                             cands=_data(s)["candidates"])
    assert res["ok"]
    after = R.load_manual(s)
    for ym in (YM_PREV, YM_EARLIER):
        assert after[ym] == before[ym], f"{ym} 的历史录入值被改写了（带入必须是只读派生）"
    assert after[YM_NOW][WH_A]["contract"] == Decimal("12345.00")


@acc(CASE, "001-12")
def test_带入格在页面上可辨_仍是可编辑输入框且带来源月():
    """§5.7.2：带入格在页面上**可辨** —— 金额带入格**仍是可编辑输入框**，并带**来源月标记**。"""
    # 数据侧：带入态与值
    a_row = _rows(_data())[WH_A]
    assert a_row["manual"]["oil"]["from"] == YM_PREV, "样本里油卡那格不是带入态"        # 预期
    assert _rows(_data())[WH_C]["manual"]["oil"]["from"] == "", "本月已录的格子被标成了带入"
    # ⚠️ 2026-09-19（`§19` 批 2）：原先在**旧页** HTML 里看那一格是不是可编辑输入框、有没有「↺MM月」标记、
    # 值有没有预填；旧页删除（授权 `D18`）后形态搬到壳 ——
    # `test_wired_m07.py::test_壳里带入格可辨且带来源月`（壳的 `c.from?' ed':''` ＋ `↺${c.from.slice(5)}月` ✓）。


@acc()
def test_路由里引用的域出口都真实存在():
    """⚠️ 这条**不绑定判据点**，它守的是一类「离线断言天生看不见」的错：

    路由里写 `别名.出口` 时，若出口其实住在**另一个模块**（本轮实测：`parse_state` 住在
    `big_service`，我却写成 `big_domain.parse_state`），**直接调函数的断言全部照绿** ——
    只有**真机请求**才会 500。

    ℹ️ 扫法是公共件（`tests/router_refs.py`），**全站统一守卫**在 `tests/test_router_refs.py`；
       这里保留本模块这一条，是为了让"活动大表"这一轮的教训在**本文件里也看得见**。
    """
    from app.mod07_setl import router as R
    from tests.router_refs import broken_refs

    bad = broken_refs(R)
    assert not bad, "路由引用了不存在的出口：" + "；".join(bad)


# ============================================================ 项目集合与顺序（001-13）


@acc(CASE, "001-13")
def test_项目集合与顺序_候选在建非壳_顺序由大表自己定():
    """§5.7.3：候选 = **在建 · 非壳**；多选后可**逐项调序** ⇒ 集合与行序即所设顺序。"""
    data = _data()
    keys = [c["warehouse"] for c in data["candidates"]]
    assert keys == list(DEFAULT_ORDER), "候选不对（应只含在建 · 非壳，且按档案顺序）"
    assert WH_ARCHIVED not in keys and WH_SHELL not in keys, "归档 / 壳进了候选"
    # 库中无选题记录 ⇒ **默认 = 全部候选**
    assert [r["warehouse"] for r in data["rows"]] == list(DEFAULT_ORDER)
    # 勾选 2 个 ⇒ 集合与行序即所设顺序
    s = _session()
    S.save_selection(s, [WH_C, WH_A], cands=_data(s)["candidates"])
    rows = _rows(_data(s))
    assert list(rows) == [WH_C, WH_A], "行序 ≠ 所设顺序"
    # ⭐ **「清空」≠「从未选题」**：清空后表里是 **0 个项目**（不得悄悄回到全部候选）
    S.save_selection(s, [], cands=_data(s)["candidates"])
    assert _rows(_data(s)) == {}, "清空后竟然回到了全部候选（两种状态没分开）"
    # 再选回来（后面的调序测试要用）
    S.save_selection(s, [WH_C, WH_A], cands=_data(s)["candidates"])
    # 逐项调序：丙仓下移
    S.move_project(s, warehouse=WH_C, direction="down", cands=_data(s)["candidates"])
    assert list(_rows(_data(s))) == [WH_A, WH_C], "下移没生效"
    S.move_project(s, warehouse=WH_C, direction="up", cands=_data(s)["candidates"])
    assert list(_rows(_data(s))) == [WH_C, WH_A], "上移没生效"
    # 越界不动（不抛异常、不绕圈）
    assert B.move_in_list([WH_A, WH_C], WH_A, "up") == [WH_A, WH_C]
    assert B.move_in_list([WH_A, WH_C], WH_C, "down") == [WH_A, WH_C]
    # 行序 = **装配行序**（⚠️ 2026-09-19 `§19` 批 2：原先这里比**旧页**与**旧导出页**两串 HTML 谁先谁后；
    # 旧页删除（授权 `D18`）后，「两处同序」改成守**同一份装配**）：
    # · **数据侧**（这里）：行序就是 `big_service` 的装配顺序 ✓；
    # · **壳侧**：表体与合计行都只从 `bigRows(...)` 一处装配、导出走 `/api/m07/big/export`（同一个装配），
    #   见 `test_wired_m07.py::test_壳里行只由一份装配出` ✓。
    s2 = _session(order=make_order([WH_B, WH_A]))
    rows_s2 = _rows(_data(s2))
    assert list(rows_s2) == [WH_B, WH_A], "装配没按大表自己的顺序排"
    assert len(rows_s2) == 2


# ============================================================ 边界（001-14 / 001-15）


@acc(CASE, "001-14")
def test_手填值不参与欠款计算():
    """§5.7.2：大表机械费等手填列**不触发欠款重算**（欠款只认付款域口径，§4.5）。

    ⭐ 用 **spy 数调用次数** 钉住"根本没调用"（⚠️ 不能断"值没变" —— 那会被下层另一道闸掩盖）。
    """
    calls: list[tuple] = []

    def _spy(*args, **kwargs):
        calls.append((args, kwargs))
        return None

    s = _session()
    cands = _data(s)["candidates"]
    with patch("app.mod05_flow.repository.sync_stat_paid", _spy):
        for key, raw in (("mech_est", "888.00"), ("oil", "0"), ("note", "手改")):
            assert S.save_manual_cell(s, month=YM_NOW, warehouse=WH_A, key=key, raw=raw,
                                      cands=cands)["ok"]
    assert calls == [], "手填值触发了欠款重算（付款域的重算出口被调用了）"


@acc(CASE, "001-15")
def test_出纸走按模板导出_且没有打印通道入口():
    """§5.7.2 · §1.4.1：出纸走「**按模板导出 → Excel 打印**」，且**不再有 A3 打印通道入口**。"""
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这里看**旧页**与**旧导出页**有没有写出纸方式、有没有 A3、
    # 导出入口在不在，以及 `NAV` 里有没有 `/m07/big`；旧页删除（授权 `D18`）后形态搬到壳 ——
    # `test_wired_m07.py::test_壳里出纸走按模板导出且没有打印通道`（壳的 `bigExport` ＋「Excel 打印」
    # ＋ ⛔ 无 A3 ＋ 新壳侧栏里有本页 ✓）。下面这条**路由层面**的守卫是实质（API 侧不许有 print/a3）：
    assert B.PRINT_CHANNEL and "Excel 打印" in B.PRINT_CHANNEL, "域内核里的出纸口径丢了"
    from app.main import create_app

    paths = [p for p in create_app().openapi()["paths"] if "big" in p]
    assert paths and not any(("print" in p or "a3" in p.lower()) for p in paths), paths
    # ⚠️ 证明这条判据**咬得住**：真塞一个 A3 入口 ⇒ 自检必须报出来
    assert B.boundary_violations(html="<h4>活动大表（A3 打印）</h4>", actions=("print",))
