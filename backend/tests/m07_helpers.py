"""`MOD-07` 收发结存自检的公共桩（**离线：不连库**）。

⭐ `EXPECT` = **手写**的期望表（不从模型对象反推）—— 「行数 / 合计 = 独立复算」就用它当对照。
⭐ 库里存的是**明细行**（`SetlDetail`，与素材包 `stock_monthly` 同款）⇒ 桩也造明细：
   每个「月 × 仓」造 `rows` 条明细，金额按 **60% / 剩余** 拆给前两条、其余为 0
   ⇒ **求和仍等于 `EXPECT` 上的数**，所以上层的独立复算一条都不用改。

会话桩与 `MOD-08` / `MOD-06` 共用（`tests/m08_helpers.FakeSession`），此处只补结存数据。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.mod07_setl.models import SOURCE_AUTO, SetlDetail, WeldGasBalance
from app.mod08_inv.models import InvDetail
from tests.m08_helpers import FakeSession  # noqa: F401  —— 会话桩共用（不另写一份）

# 三个核算月；**行数合计互不相同**（17 / 18 / 4）⇒ 001-03 的"切月有区分力"成立
# ⚠️ 2026-07 「丙仓」差 **+0.50**、「戊仓」差 **-0.20** ⇒ 合计行差 **+0.30**
#    —— 三个数**互不相同**，用来证明「合计行的校验是**对合计值本身**再判一次，不是抄某一行」（001-09）
EXPECT: dict[str, dict[str, dict]] = {
    "2026-08": {
        "甲仓": {"rows": 12, "begin": "1000.00", "in": "500.50", "out": "200.25", "end": "1300.25"},
        "乙仓": {"rows": 5, "begin": "0.00", "in": "0.00", "out": "0.00", "end": "0.00"},
    },
    "2026-07": {
        "甲仓": {"rows": 9, "begin": "200.00", "in": "100.00", "out": "50.00", "end": "250.00"},
        "丙仓": {"rows": 3, "begin": "10.00", "in": "20.00", "out": "5.00", "end": "24.50"},
        "戊仓": {"rows": 6, "begin": "30.00", "in": "5.00", "out": "10.00", "end": "25.20"},
    },
    "2026-06": {
        "丁仓": {"rows": 4, "begin": "7.00", "in": "3.00", "out": "1.00", "end": "9.00"},
    },
}

EMPTY_MONTH = "2026-05"        # 桩里**没有**这个月 ⇒ 空态


def split_amount(value: str, parts: int) -> list[Decimal]:
    """把一个金额拆给 `parts` 条明细（60% / 剩余 / 其余 0）—— **求和恒等于原值**。"""
    total = Decimal(value)
    if parts <= 0:
        return []
    if parts == 1:
        return [total]
    head = (total * Decimal("0.6")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return [head, total - head] + [Decimal("0.00")] * (parts - 2)


def _details(ym: str, warehouse: str, cell: dict) -> list[SetlDetail]:
    n = int(cell["rows"])
    cols = {key: split_amount(cell[key], n) for key in ("begin", "in", "out", "end")}
    out: list[SetlDetail] = []
    for i in range(n):
        out.append(SetlDetail(
            ym=ym, warehouse_name=warehouse, resource_class="材料",
            resource_code=f"R{i + 1:02d}",          # ⚠️ 跨仓**故意同名** ⇒ 复合唯一键(月·仓·编码)才拦得住
            resource_name=f"物料{i + 1}", spec="—", unit="kg", material_property="主材",
            begin_qty=Decimal("0.00"), begin_amt=cols["begin"][i],
            in_qty=Decimal("0.00"), in_price=Decimal("0.00"), in_amt=cols["in"][i],
            out_qty=Decimal("0.00"), out_price=Decimal("0.00"), out_amt=cols["out"][i],
            end_qty=Decimal("0.00"), end_amt=cols["end"][i],
            source=SOURCE_AUTO,
        ))
    return out


def dataset(months: tuple[str, ...] = ("2026-08", "2026-07", "2026-06")) -> dict:
    """按 `EXPECT` 生成**明细**桩数据（只取指定月份，便于造"某月为空"的场景）。"""
    rows: list[SetlDetail] = []
    for ym in months:
        for warehouse, cell in EXPECT[ym].items():
            rows.extend(_details(ym, warehouse, cell))
    for i, d in enumerate(rows, start=1):
        d.id = i
    return {SetlDetail: rows}


def indep_row_total(ym: str) -> int:
    """**独立复算**行数合计（只用手写的 `EXPECT`，不问实现）。"""
    return sum(c["rows"] for c in EXPECT[ym].values())


def indep_warehouses(ym: str) -> list[str]:
    return sorted(EXPECT[ym])


def indep_amount_total(ym: str, key: str) -> Decimal:
    return sum((Decimal(c[key]) for c in EXPECT[ym].values()), Decimal("0.00"))


# ============================================================ 焊材 / 气体提取（§5.3.3 · ACC-SETL-EXT-001）

# 项目档案桩：**在建两仓 + 归档一仓**（`ord` 决定「在建」下的行序：乙仓 1 < 甲仓 2）
PROJECTS: dict[str, dict] = {
    "甲仓": {"status": "active", "ord": 2},
    "乙仓": {"status": "active", "ord": 1},
    "丙仓": {"status": "archived", "ord": 0},
}
# 归档仓（丙仓）**不放任何焊材 / 气体数据** —— 这样「切到归档」正好落在"两类都无行"的场景（001-04）
ARCHIVED_WAREHOUSE = "丙仓"

# 提取期望表（**手写**）：`{类别: {仓库: {月份: 收金额}}}`
# ⚠️ 刻意放三条"近名不命中"的行，证明**白名单精确匹配**（`氧气瓶` ≠ `氧气`）：
#    甲仓 2026-08 还有一条「氧气瓶」555.00 —— 若规则写成"包含"，气体甲仓 08 会变成 955.00
EXTRACT_EXPECT: dict[str, dict[str, dict[str, str]]] = {
    "焊材": {
        "甲仓": {"2026-06": "1000.00", "2026-08": "2000.00"},
        "乙仓": {"2026-07": "500.00"},
    },
    "气体": {
        "甲仓": {"2026-07": "300.00", "2026-08": "400.00"},
        "乙仓": {"2026-08": "100.00"},
    },
}
# 全部类别有数据的月份并集（导出矩阵的月份列）
EXTRACT_MONTHS: tuple[str, ...] = ("2026-06", "2026-07", "2026-08")

# 明细桩：(仓库, 月份, 资源名称, 收金额, 物料性质)
EXTRACT_DETAILS: tuple[tuple[str, str, str, str, str], ...] = (
    ("甲仓", "2026-06", "焊条J422", "1000.00", "主材"),
    ("甲仓", "2026-08", "焊丝Φ1.2", "2000.00", "主材"),
    ("乙仓", "2026-07", "焊锡丝", "500.00", "辅材"),
    ("甲仓", "2026-07", "氩气", "300.00", "辅材"),
    ("甲仓", "2026-08", "液氩", "400.00", "辅材"),
    ("乙仓", "2026-08", "氧气", "100.00", "辅材"),
    ("甲仓", "2026-08", "氧气瓶", "555.00", "辅材"),      # ⛔ 近名 ⇒ 精确匹配下**不命中**
    ("甲仓", "2026-08", "氩气表", "333.00", "辅材"),      # ⛔ 同上
    ("丙仓", "2026-08", "电缆YJV", "777.00", "主材"),     # 两类都不进（归档仓，也无提取数据）
)


def inventory_rows(details):
    """保留原收发结存桩，补相同已知金额的库存原单以验证共同源消费者。"""
    return [InvDetail(id=i, ym=d.ym, warehouse_name=d.warehouse_name, material_name=d.resource_name,
                      direction='入库', amount=d.in_amt, doc_no=f'TEST-{i}', seq='1')
            for i,d in enumerate(details,1)]


def extract_dataset(with_balances: bool = False) -> dict:
    """提取页用的桩：**明细 + 项目档案**（状态 / ord 决定筛选与行序）。

    `with_balances=True` 时**额外**带上 `BALANCE_EXPECT` 那几行「结余」录入值
    （默认**不带** —— 便于造"完全没有录入"的场景）。
    """
    from app.mod01_projects.models import Project

    details: list[SetlDetail] = []
    for i, (wh, ym, name, amount, prop) in enumerate(EXTRACT_DETAILS, start=1):
        details.append(SetlDetail(
            ym=ym, warehouse_name=wh, resource_class="材料", resource_code=f"{ym}-{i:02d}",
            resource_name=name, spec="—", unit="kg", material_property=prop,
            begin_qty=Decimal("0.00"), begin_amt=Decimal("0.00"),
            in_qty=Decimal("0.00"), in_price=Decimal("0.00"), in_amt=Decimal(amount),
            out_qty=Decimal("0.00"), out_price=Decimal("0.00"), out_amt=Decimal("0.00"),
            end_qty=Decimal("0.00"), end_amt=Decimal("0.00"), source=SOURCE_AUTO,
        ))
    for i, d in enumerate(details, start=1):
        d.id = i
    projects = [
        Project(id=i, warehouse_name=wh, name_full=f"{wh}项目", disp=wh, phid=f"P{i}",
                status=cfg["status"], ord=cfg["ord"])
        for i, (wh, cfg) in enumerate(PROJECTS.items(), start=1)
    ]
    data: dict = {SetlDetail: details, InvDetail: inventory_rows(details), Project: projects}
    if with_balances:
        data.update(balance_dataset())
    return data


# ------------------------------------------------------------ 「结余」手工录入（2026-09-18 裁定「甲」）

# 结余期望表（**手写**）：`{类别: {仓库: 金额}}` —— 粒度 = **类别 × 仓库 · 不按月**。
# ⭐ 两处刻意的样本：
#   · **焊材 · 乙仓 = 0** ⇒ `0` 是**合法录入值**（与"未录入"两件事；导出里写 0、不写空）；
#   · **气体只有甲仓** ⇒ 乙仓**没有键** = 未录入 ⇒ 导出里**如实留空**（⛔ 不写 0）。
BALANCE_EXPECT: dict[str, dict[str, str]] = {
    "焊材": {"甲仓": "1200.00", "乙仓": "0.00"},
    "气体": {"甲仓": "88.50"},
}


def balance_rows() -> list[WeldGasBalance]:
    """把 `BALANCE_EXPECT` 变成 ORM 行（**从手写期望表派生**，⛔ 不另写一份值）。"""
    out: list[WeldGasBalance] = []
    for kind, by_wh in BALANCE_EXPECT.items():
        for wh, amount in by_wh.items():
            out.append(WeldGasBalance(id=len(out) + 1, kind=kind,
                                      warehouse_name=wh, amount=Decimal(amount)))
    return out


def balance_dataset() -> dict:
    """结余的桩（单独一份 —— 便于"只有结余、没有明细"这类场景）。"""
    return {WeldGasBalance: balance_rows()}


def indep_balance(kind: str, warehouse: str):
    """**独立复算**该格的结余：未录入 ⇒ `None`（⛔ 不是 0）。"""
    raw = BALANCE_EXPECT.get(kind, {}).get(warehouse)
    return None if raw is None else Decimal(raw)


def indep_extract_total(kind: str, warehouse: str) -> Decimal:
    """**独立复算**「总金额」= 该类该仓全部月份之和。"""
    return sum((Decimal(v) for v in EXTRACT_EXPECT[kind].get(warehouse, {}).values()),
               Decimal("0.00"))


def indep_extract_sum(kind: str, warehouse: str, months) -> Decimal:
    """**独立复算**「金额」= 该类该仓落在给定月份里的金额。"""
    want = set(months)
    return sum((Decimal(v) for m, v in EXTRACT_EXPECT[kind].get(warehouse, {}).items()
                if m in want), Decimal("0.00"))


def indep_extract_kind_total(kind: str) -> Decimal:
    """**独立复算**某类的合计行（= 全部在建仓之和）。"""
    return sum((indep_extract_total(kind, w) for w in EXTRACT_EXPECT[kind]), Decimal("0.00"))


__all__ = ["FakeSession", "EXPECT", "EMPTY_MONTH", "SetlDetail", "SOURCE_AUTO",
           "WeldGasBalance", "BALANCE_EXPECT", "balance_rows", "balance_dataset", "indep_balance",
           "split_amount", "dataset",
           "indep_row_total", "indep_warehouses", "indep_amount_total",
           "PROJECTS", "ARCHIVED_WAREHOUSE", "EXTRACT_EXPECT", "EXTRACT_MONTHS",
           "EXTRACT_DETAILS", "extract_dataset",
           "indep_extract_total", "indep_extract_sum", "indep_extract_kind_total"]
