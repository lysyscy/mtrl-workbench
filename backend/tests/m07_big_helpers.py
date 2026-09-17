"""`MOD-07` **活动大表**验收断言的离线桩（**不连库**）。

⭐ `EXPECT` = **手写**的期望值（不从模型对象反推）—— 「派生列独立复算」就靠它当对照。
⭐ 数据刻意铺出**四种带入情形**（照原型 `BIGVAL` 的注释）：
   - 甲仓：本月录了 1 格 ⇒ 其余 5 格**带入自 2026-07**
   - 乙仓：本月未录、07 月也没有 ⇒ **跨月回退**取 2026-06
   - 丙仓：**本月**录了 `oil=0` ⇒ **0 是合法值**，必须**不再带入**（否则 001-09 会静默假绿）
   - 丁仓：全程无记录 ⇒ **留空待填**（不得硬凑）
"""

from __future__ import annotations

from decimal import Decimal

from app.mod01_projects.models import STATUS_ARCHIVED, TYPE_SHELL, Project
from app.mod06_proc.models import ProcMechManual
from app.mod07_setl.models import AnalysisBigManual, AnalysisBigProject, SetlDetail
from tests.m08_helpers import FakeSession  # noqa: F401  —— 会话桩共用（不另写一份）

YM_NOW, YM_PREV, YM_EARLIER = "2026-08", "2026-07", "2026-06"
WH_A, WH_B, WH_C, WH_D = "甲仓", "乙仓", "丙仓", "丁仓"
WH_ARCHIVED, WH_SHELL = "归档仓", "壳-未建仓"

#: 提取明细：`(核算月, 仓库, 资源名, 收金额)` —— 焊材走关键词、气体走白名单
EXTRACT_ROWS: tuple[tuple[str, str, str, str], ...] = (
    (YM_EARLIER, WH_A, "焊条 J422", "100.00"),
    (YM_PREV, WH_A, "焊丝 φ1.2", "200.00"),
    (YM_NOW, WH_A, "焊条 J422", "300.00"),
    (YM_PREV, WH_A, "氧气", "50.00"),
    (YM_NOW, WH_B, "焊锡丝", "40.00"),
)

#: 机械 6 列手录：`(核算月, 仓库, 内租设备, 外租零租含税, 外租包月含税)`
MECH_ROWS: tuple[tuple[str, str, str, str, str], ...] = (
    (YM_EARLIER, WH_A, "10.00", "100.00", "20.00"),
    (YM_NOW, WH_A, "5.00", "200.00", "30.00"),
    (YM_PREV, WH_B, "7.00", "0.00", "0.00"),
)

#: 手填值：`(核算月, 仓库, 键, 值)`
MANUAL_ROWS: tuple[tuple[str, str, str, object], ...] = (
    (YM_PREV, WH_A, "open_ym", "2024-03"),
    (YM_PREV, WH_A, "mech_est", "1000.00"),
    (YM_PREV, WH_A, "contract", "10000.00"),
    (YM_PREV, WH_A, "output_cum", "2000.00"),
    (YM_PREV, WH_A, "oil", "100.00"),
    (YM_PREV, WH_A, "note", "7月备注"),
    (YM_NOW, WH_A, "mech_est", "1600.00"),          # 本月只录这一格 ⇒ 其余 5 格应带入
    (YM_NOW, WH_C, "oil", Decimal("0.00")),         # ⭐ 0 是合法录入值（且录在**本月**）
    (YM_EARLIER, WH_B, "open_ym", "2025-01"),
    (YM_EARLIER, WH_B, "mech_est", "500.00"),
    (YM_EARLIER, WH_B, "contract", "1000.00"),
    (YM_EARLIER, WH_B, "output_cum", "250.00"),
    (YM_EARLIER, WH_B, "oil", "50.00"),
)

#: ⭐ **手写期望**（独立复算的对照物）
EXPECT: dict[str, dict] = {
    WH_A: {
        "hw_cum": "600.00", "hw_mon": "300.00", "qt_cum": "50.00", "qt_mon": "0.00",
        "rent_cum": "350.00", "rent_mon": "230.00",
        "lease_cum": "15.00", "lease_mon": "5.00",
        "total_cum": "365.00",
        "mech_est": "1600.00",                       # 本月录入（不带入）
        "carry": {                                   # 带入自 YM_PREV 的 5 格
            "open_ym": "2024-03", "contract": "10000.00",
            "output_cum": "2000.00", "oil": "100.00", "note": "7月备注",
        },
    },
    WH_B: {
        "hw_cum": "40.00", "hw_mon": "40.00", "qt_cum": "0.00", "qt_mon": "0.00",
        "rent_cum": "0.00", "rent_mon": "0.00",
        "lease_cum": "7.00", "lease_mon": "0.00",
        "total_cum": "7.00",
        "mech_est": "500.00",
        "carry": {"open_ym": "2025-01", "mech_est": "500.00", "contract": "1000.00",
                  "output_cum": "250.00", "oil": "50.00"},   # 全部带入自 **2026-06**（跨月）
    },
    WH_C: {"oil": "0.00"},                            # 0 ⇒ **本月已录**，不带入
    WH_D: {},                                         # 全程无记录 ⇒ 留空待填
}

#: 默认行序（= 全部候选，按档案顺序）
DEFAULT_ORDER: tuple[str, ...] = (WH_A, WH_B, WH_C, WH_D)


def make_projects() -> list[Project]:
    """项目档案：4 个在建（有仓库）＋ 1 个归档 ＋ 1 个壳（无仓库）。"""
    rows = [
        Project(id=11, project_type="normal", name_full="甲公司项目全名", warehouse_name=WH_A, disp="甲公司项目"),
        Project(id=12, project_type="normal", name_full="乙公司项目全名", warehouse_name=WH_B, disp="乙公司项目"),
        Project(id=13, project_type="normal", name_full="丙公司项目全名", warehouse_name=WH_C, disp="丙公司项目"),
        Project(id=14, project_type="normal", name_full="丁公司项目全名", warehouse_name=WH_D, disp="丁公司项目"),
        Project(id=15, project_type="normal", name_full="已归档项目全名", warehouse_name=WH_ARCHIVED,
                disp="已归档项目", status=STATUS_ARCHIVED),
        Project(id=16, project_type=TYPE_SHELL, name_full="某小微壳", warehouse_name=None, disp=""),
    ]
    for p in rows:
        p.ord = 0
    return rows


def make_setl() -> list[SetlDetail]:
    out = []
    for i, (ym, wh, name, amt) in enumerate(EXTRACT_ROWS, 1):
        out.append(SetlDetail(id=i, ym=ym, warehouse_name=wh, resource_class="材料",
                              resource_code=f"R{i:02d}", resource_name=name, spec="—", unit="kg",
                              material_property="主材", in_amt=Decimal(amt)))
    return out


def make_mech() -> list[ProcMechManual]:
    out = []
    for i, (ym, wh, lease, rent_a, rent_b) in enumerate(MECH_ROWS, 1):
        out.append(ProcMechManual(id=i, ym=ym, warehouse_name=wh, project_id=None,
                                  mech_1=Decimal(lease), mech_2=Decimal(rent_a), mech_3=Decimal(rent_b)))
    return out


def make_manual() -> list[AnalysisBigManual]:
    from app.mod07_setl import big_domain as B

    key_row: dict[tuple[str, str], AnalysisBigManual] = {}
    for i, (ym, wh, key, value) in enumerate(MANUAL_ROWS, 1):
        row = key_row.get((ym, wh))
        if row is None:
            row = AnalysisBigManual(id=i, ym=ym, warehouse_name=wh, project_id=None)
            key_row[(ym, wh)] = row
        if B.MANUAL_FMT[key] == B.FMT_MONEY and value is not None:
            value = Decimal(str(value))
        setattr(row, B.MANUAL_COLUMN[key], value)
    return list(key_row.values())


def make_order(warehouses=DEFAULT_ORDER) -> list[AnalysisBigProject]:
    """大表自己的顺序（**空列表 = 库里没有选题记录** ⇒ 默认 = 全部候选）。"""
    return [AnalysisBigProject(id=i + 1, warehouse_name=w, seq=i) for i, w in enumerate(warehouses)]


def dataset(*, order=None) -> dict:
    """一份完整样本（项目 / 提取明细 / 机械手录 / 手填值 / 大表顺序）。"""
    return {
        Project: make_projects(),
        SetlDetail: make_setl(),
        ProcMechManual: make_mech(),
        AnalysisBigManual: make_manual(),
        AnalysisBigProject: list(order or []),
    }


__all__ = ["YM_NOW", "YM_PREV", "YM_EARLIER", "WH_A", "WH_B", "WH_C", "WH_D",
           "WH_ARCHIVED", "WH_SHELL", "EXPECT", "DEFAULT_ORDER", "dataset", "make_order"]
