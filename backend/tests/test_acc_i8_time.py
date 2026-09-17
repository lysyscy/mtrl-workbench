"""`ACC-I8-TIME-001`（核算年月 / 时间口径）7 个判据点的验收断言。

⚠️ 时间口径是 **`MOD-01` · `MOD-02` 共用** 的（实现落在 `app/core/period.py`）。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.errors import MustReportError
from app.core.period import (
    ALL_MODES,
    GLOBAL_PERIOD,
    MODE_ALL,
    MODE_MONTH,
    MODE_SPAN,
    MODE_YEAR,
    PERIOD_COMPONENT,
    default_period,
    export_filename,
    in_period,
    parse_period,
    period_capabilities,
    period_range,
)
from tests.acc_plugin import acc


@acc("ACC-I8-TIME-001", "001-01")
def test_全站统一核算年月组件且无全局年月控件():
    # 全站唯一组件 + 四种模式；**不设「全局核算期」**（顶栏不再有全局年月控件）
    assert PERIOD_COMPONENT["id"] == "acc-period"
    assert PERIOD_COMPONENT["modes"] == ALL_MODES
    assert GLOBAL_PERIOD is None


@acc("ACC-I8-TIME-001", "001-02")
def test_能力由调用点声明():
    # 列表页给 4 种模式
    assert period_capabilities("notice") == ALL_MODES
    # 抓取弹窗 / 期初截止年月**只声明「月」** ⇒ 不渲染模式切换条
    assert period_capabilities("fetch") == (MODE_MONTH,)
    assert period_capabilities("opening") == (MODE_MONTH,)


@acc("ACC-I8-TIME-001", "001-03")
def test_跨月两击选区间且闭区间生效():
    mode, value = parse_period("2026-01~2026-06")
    assert mode == MODE_SPAN and value == "2026-01~2026-06"
    start, end = period_range("2026-01~2026-06")
    assert (start, end) == ("2026-01-01", "2026-06-30")
    # **闭区间**：两端各自命中
    assert in_period("2026-01-01", "2026-01~2026-06")
    assert in_period("2026-06-30", "2026-01~2026-06")
    assert not in_period("2026-07-01", "2026-01~2026-06")
    assert not in_period("2025-12-31", "2026-01~2026-06")


@acc("ACC-I8-TIME-001", "001-04")
def test_年模式命中全年各月():
    assert parse_period("2026") == (MODE_YEAR, "2026")
    assert period_range("2026") == ("2026-01-01", "2026-12-31")
    for m in range(1, 13):
        assert in_period(f"2026-{m:02d}-15", "2026")


@acc("ACC-I8-TIME-001", "001-05")
def test_全部模式下发到付款流水与付款计划():
    # 「全部」不再是某一页独有 —— 付款通知书声明的它，同样下发到付款流水与付款计划
    for ctx in ("notice", "flow", "plan"):
        assert MODE_ALL in period_capabilities(ctx)


@acc("ACC-I8-TIME-001", "001-06")
def test_各表默认年月各按口径():
    fixed = date(2026, 9, 15)
    # 付款侧（通知书 / 计划 / 流水）= 当月
    assert default_period("notice", fixed) == "2026-09"
    assert default_period("plan", fixed) == "2026-09"
    assert default_period("flow", fixed) == "2026-09"
    # 材料报表类 = 上月（月度报表做的是上一个月）
    assert default_period("process", fixed) == "2026-08"
    assert default_period("inventory", fixed) == "2026-08"
    # 跨年：1 月的上月 = 去年 12 月
    assert default_period("process", date(2026, 1, 5)) == "2025-12"


@acc("ACC-I8-TIME-001", "001-07")
def test_不设全局核算期且导出文件名用当前年月():
    assert GLOBAL_PERIOD is None
    # 单月 ⇒ 用该月
    assert export_filename("付款通知书", "2026-03") == "付款通知书-2026-03"
    # 非单月 ⇒ 用**当前年月**（不得硬编码固定月）
    from datetime import datetime

    assert export_filename("付款通知书", "", now=datetime(2026, 9, 15)) == "付款通知书-2026-09"
    assert export_filename("付款通知书", "2026", now=datetime(2026, 9, 15)) == "付款通知书-2026-09"
    with pytest.raises(MustReportError):
        parse_period("2026/03")   # 非法形态 ⇒ 显式报错
