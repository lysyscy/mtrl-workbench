"""i8 接口契约对齐的工程自检（离线 · 不连库 · **不绑定 `ACC-*` 判据点**）。

守的是**实现层**这一层：`API-01` / `API-05` / `API-06` 的**字段真名**（来源见
`docs/reference/i8-contract.md`）能正确映射，且**旧别名仍然兼容**（回归保护）。

⚠️ 另含一条**防漂移**断言：`mod02`（基础设施）里独立声明的「已批」字面量
**必须与** `mod03`（业务）的 `APPROVE_STATUS_DONE` 相等 —— 两侧**不得各说各话**。
"""

from __future__ import annotations

import pytest

from app.core import app_settings
from app.core.config import Settings, get_settings
from app.mod02_i8.notice_source import (
    APPROVE_STATUS_DONE,
    APPROVE_STATUS_OTHER,
    BILL_TYPE_MATERIAL,
    BILL_TYPE_MECHANICAL,
    _map_record,
    approve_status_of,
    bill_type_of,
)
from app.mod02_i8.sources import CommonProjectSource, WarehouseSource

# `API-01` 的一条**真实形态**样本（字段名 = 素材包实测真名）
REC = {
    "PhId": "3700000000000521",
    "BillNo": "FKTZS2026090001",
    "BillName": "付某某项目材料款",
    "BillDt": "2026-09-08 00:00:00",
    "PhidPc_EXName": "某某项目(XMCB2025080001)",
    "PhidRecPayType_EXName": "其他支出",
    "PhidBusType_EXName": "付材料款",
    "PhidPayOrg_EXName": "四公司",
    "user_skdw_EXName": "某某商贸有限公司",
    "ApproveAmt": "12345.67",
    "PhidFillPsn_EXName": "梁丽佳",
    "AppStatus": 1,
    "Remark": "备注",
}


class _FakeClient:
    """记录调用形态；`payloads` 可给**多次**响应（用于"空结果确认"路径）。"""

    def __init__(self, payload=None, *, payloads=None) -> None:  # noqa: ANN001
        self.payload = payload
        self.payloads = list(payloads) if payloads else None
        self.calls: list[tuple] = []

    def _next(self):  # noqa: ANN001
        if self.payloads:
            return self.payloads.pop(0)
        return self.payload

    def get_json(self, url, params=None, **kw):  # noqa: ANN001
        self.calls.append(("GET", url, params))
        return self._next()

    def post_json(self, url, data=None, **kw):  # noqa: ANN001
        self.calls.append(("POST", url, data))
        return self._next()


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    # 离线契约不读本机配置，并清除测试环境值留下的缓存。
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setattr(app_settings, "_VALUES_LOADER", lambda: {})
    monkeypatch.setattr(app_settings, "_CACHE", {})
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_API01十二字段真名都能正确映射():
    row = _map_record(REC)
    assert row is not None
    assert row["ph_id"] == "3700000000000521"
    assert row["bill_no"] == "FKTZS2026090001"
    assert row["bill_type"] == BILL_TYPE_MATERIAL          # 其他支出 ⇒ 材料（§4.3.3 的列对应）
    assert row["project_name"].startswith("某某项目")
    assert row["approve_status"] == APPROVE_STATUS_DONE
    assert row["amount_approved"] == 12345.67
    assert row["doc_date"] == "2026-09-08"                 # 只取日期部分
    assert row["biz_type"] == "付材料款"
    assert row["payee"] == "某某商贸有限公司"
    assert row["input_by"] == "梁丽佳"
    assert row["fields"] is REC                            # 整条原样留存（不丢信息）


def test_已付金额不由API01提供恒为零():
    # §4.3.3 / §4.4.2：已付金额 = **付款流水汇总**，不是 i8 字段
    assert _map_record(REC)["amount_paid"] == 0.0


def test_缺主键的记录被丢弃():
    assert _map_record({"BillNo": "X"}) is None


def test_审批状态零值判定的映射():
    for raw in (0, "0", "", None, "None", "null"):
        assert approve_status_of({"AppStatus": raw}) == APPROVE_STATUS_OTHER, raw
    for raw in (1, "1", "已审批", 2):
        assert approve_status_of({"AppStatus": raw}) == APPROVE_STATUS_DONE, raw


def test_收付款类型到内部bill_type的分流与直觉相反():
    # §4.3.3：材料 → 其他支出；外租机械 → 付款通知书
    assert bill_type_of({"PhidRecPayType_EXName": "付款通知书"}) == BILL_TYPE_MECHANICAL
    assert bill_type_of({"PhidRecPayType_EXName": "其他支出"}) == BILL_TYPE_MATERIAL
    # 未知取值 ⇒ 原样返回（**不猜**），并由打印侧显式报错
    assert bill_type_of({"PhidRecPayType_EXName": "付款申请"}) == "付款申请"


def test_已批字面量在基础设施层与业务层不得漂移():
    """`mod02` 不依赖 `mod03`，所以字面量各声明一份 —— 用断言把它们钉在一起。"""
    from app.mod03_notice.domain import APPROVE_STATUS_DONE as BIZ_DONE

    assert APPROVE_STATUS_DONE == BIZ_DONE == "已批"


def test_旧别名仍然兼容_回归保护():
    # 真名缺失时回落到旧别名（防御性解析不退回原状）
    legacy = {"phId": "9", "billNo": "B", "ApproveStatus": "x", "AmountApproved": "7"}
    row = _map_record(legacy)
    assert row["ph_id"] == "9" and row["bill_no"] == "B"
    assert row["amount_approved"] == 7.0


def test_API05仓库列表按真字段解析并跳作废(monkeypatch):
    monkeypatch.setenv("I8_BASE_URL", "http://i8/x")
    payload = {
        "Record": [
            {"PhId": "1", "Whname": "甲仓库", "PhidPc_EXName": "某某项目(XMCB2025080001)", "Nullify": "0"},
            {"PhId": "2", "Whname": "已作废仓库", "PhidPc_EXName": "某某项目", "Nullify": "1"},
        ]
    }
    client = _FakeClient(payload)
    rows = WarehouseSource(client).fetch()
    assert rows == [{"warehouse_name": "甲仓库", "owner_full_name": "某某项目(XMCB2025080001)"}]
    # ⚠️ `API-05` 必须是 **POST form**（真机/旁证均为 POST）
    method, _url, form = client.calls[0]
    assert method == "POST" and "orgQuery" in form


def test_API06常用项目按真字段解析(monkeypatch):
    monkeypatch.setenv("I8_BASE_URL", "http://i8/y")
    payload = {"Record": [{"PhId": "P1", "BillNo": "XMCB2025080001", "BillName": "某某项目", "Ab": "某某"}]}
    rows = CommonProjectSource(_FakeClient(payload)).fetch()
    assert rows == [{"name_full": "某某项目", "phid": "P1", "code": "XMCB2025080001", "ab": "某某"}]


def test_API01取数表单契约():
    from app.mod02_i8.notice_source import LIST_FORM, build_list_form, month_range

    assert month_range("2026-08") == ("2026-08-01", "2026-08-31")
    assert month_range("2026-02") == ("2026-02-01", "2026-02-28")
    form = build_list_form("2026-08")
    assert set(LIST_FORM) <= set(form)
    assert form["dataKey"] == ""                       # ⚠️ 必须空串（否则查不到数）
    assert form["busType"] == "PaymentBill" and form["limit"] == "5000"
    # queryfilter 是**双层 JSON 串**（外层 {"queryFilter": "<内层串>"}）
    import json

    inner = json.loads(json.loads(form["queryfilter"])["queryFilter"])
    assert inner == {"BillDt*date*ge*1": "2026-08-01", "BillDt*date*le*1": "2026-08-31"}


def test_API01抓取用POST且空结果会再确认一次(monkeypatch):
    """i8 会**偶发回"有效但空"** ⇒ 第一次 0 条时必须**再确认一次**，否则整月漏抓。"""
    from app.mod02_i8 import notice_source as ns

    monkeypatch.setattr(ns.time, "sleep", lambda *_: None)          # 别真等 1.2s
    monkeypatch.setenv("I8_BASE_URL", "http://i8/list")
    client = _FakeClient(payloads=[{"Record": []}, {"Record": [REC]}])
    rows = ns.NoticeFetcher(client).fetch_month("2026-08")          # type: ignore[arg-type]
    assert len(rows) == 1
    assert [c[0] for c in client.calls] == ["POST", "POST"]         # **两次都是 POST**（确认那一次）
    assert all("queryfilter" in c[2] for c in client.calls)


def test_取数端点一律走配置_未配置时显式报错(monkeypatch):
    from app.core.errors import NotConfiguredError

    # ⚠️ 必须**显式置空** —— `.env` 里已有真值，`delenv` 删掉环境变量也压不住文件里的值
    # ⚠️ 2026-09-16 起判的是「i8 服务地址」（端点 = base ＋ 常量路径，§7.8）
    monkeypatch.setenv("I8_BASE_URL", "")
    get_settings.cache_clear()
    try:
        WarehouseSource(_FakeClient({"Record": []})).fetch()
    except NotConfiguredError as exc:
        assert "I8_BASE_URL" in exc.message
    else:  # pragma: no cover
        raise AssertionError("未配置时应显式报错，而不是静默返回空")
