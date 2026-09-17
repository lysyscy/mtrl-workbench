"""`ACC-I8-FETCH-001`（抓取：入参换算 / 命中回显 / 手动触发 / 降级 / 执行记录）8 个判据点的验收断言。"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.core.period import MODE_MONTH, period_capabilities
from app.mod02_i8.fetch_task import (
    CONFIRM_CLOSES_DIALOG,
    EXTERNAL_SOURCES,
    MANUAL_ONLY,
    build_dialog,
    build_fetch_params,
    degrade_to_excel,
    echo_params,
    fetch_record_payload,
    preview,
)
from app.mod02_i8.models import RunRecord
from tests.acc_plugin import acc

_REQS = Path(__file__).resolve().parents[1] / "requirements.txt"


@acc("ACC-I8-FETCH-001", "001-01")
def test_入参核算年月换算为单据日期起止并回显():
    params = build_fetch_params("2026-08")
    assert params == {"year_month": "2026-08", "start_date": "2026-08-01", "end_date": "2026-08-31"}
    echo = echo_params(params)
    assert "2026-08" in echo and "2026-08-01" in echo and "2026-08-31" in echo   # 回显换算结果


@acc("ACC-I8-FETCH-001", "001-02")
def test_抓取一律按月不提供自选模式():
    assert period_capabilities("fetch") == (MODE_MONTH,)
    # 不接受「全部 / 跨月 / 年」—— 传空值即拒绝
    from app.core.errors import MustReportError
    import pytest

    with pytest.raises(MustReportError):
        build_fetch_params("")
    with pytest.raises(MustReportError):
        build_fetch_params("2026-01~2026-06")


@acc("ACC-I8-FETCH-001", "001-03")
def test_弹窗回显命中条数有效剔除分列():
    rows = [{"BillNo": f"B{i}"} for i in range(5)]
    p = preview(rows, is_excluded=lambda r: r["BillNo"] in {"B1", "B3"})
    assert (p.total, p.valid, p.excluded) == (5, 3, 2)
    assert [r["BillNo"] for r in p.excluded_rows] == ["B1", "B3"]


@acc("ACC-I8-FETCH-001", "001-04")
def test_改月份弹窗自动重建():
    d1 = build_dialog("2026-08", [{"BillNo": "A"}])
    assert d1.params["start_date"] == "2026-08-01" and d1.preview.total == 1
    # 改月 ⇒ 区间与命中条数随之更新
    d2 = build_dialog("2026-07", [{"BillNo": "A"}, {"BillNo": "B"}])
    assert d2.params["start_date"] == "2026-07-01" and d2.params["end_date"] == "2026-07-31"
    assert d2.preview.total == 2
    assert d1.params != d2.params


@acc("ACC-I8-FETCH-001", "001-05")
def test_抓取手动触发确认后关闭弹窗():
    assert MANUAL_ONLY is True
    assert CONFIRM_CLOSES_DIALOG is True
    # 防回归：本工程**无任何定时任务** ⇒ 依赖里不得出现调度器
    assert "apscheduler" not in _REQS.read_text(encoding="utf-8").lower()


@acc("ACC-I8-FETCH-001", "001-06")
def test_接口不可用须降级为手动Excel并显式说明():
    result = degrade_to_excel(RuntimeError("i8 502 Bad Gateway"))
    assert result["degraded"] is True
    assert result["excel_import_available"] is True
    assert "降级" in result["message"] and "Excel" in result["message"]   # **显式说明**处于降级路径


@acc("ACC-I8-FETCH-001", "001-07")
def test_每次抓取留一条执行记录():
    payload = fetch_record_payload(object_desc="付款通知书 2026-08", success=12, fail=1, error_message="1 条失败")
    assert payload["run_type"] == "fetch"
    assert payload["target"] == "付款通知书 2026-08"
    assert payload["status"] == "partial"
    assert payload["error_message"] == "1 条失败"
    # 执行记录表含「时间」列（§3.1.3：时间 · 对象 · 结果 · 失败原因）
    cols = set(RunRecord.__table__.columns.keys())
    assert {"started_at", "target", "status", "error_message"} <= cols
    # 全成功 / 全失败
    assert fetch_record_payload(object_desc="x", success=3, fail=0)["status"] == "success"
    assert fetch_record_payload(object_desc="x", success=0, fail=3)["status"] == "failed"


@acc("ACC-I8-FETCH-001", "001-08")
def test_不接竞价平台i8是唯一外部数据源():
    assert EXTERNAL_SOURCES == ("i8",)
    # 配置里**不得**出现竞价平台相关字段（防回归）
    field_names = " ".join(Settings.model_fields.keys()).lower()
    assert "bid" not in field_names and "bidding" not in field_names and "竞价" not in field_names
