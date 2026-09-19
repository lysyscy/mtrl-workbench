"""`API-04`（采购合同取数）契约自检 —— 离线 · 不连库 · **不绑定 `ACC-*` 判据点**。

守的是**实现层**这一层：请求形态与**字段真名**映射。样例 = 用户 **2026-09-19** 给的真实响应
（`CGHT2026090188`，见计划 `§14.4c`「`API-04` 契约」）。

⚠️ 特别钉住两条**实测踩出来的**事实（写错任何一条，抓取都是**静默失效**）：
1. 必须是 **POST**（GET ⇒ `500 Request method 'GET' is not supported`）；query 挂在 **URL** 上；
2. **项目匹配字段 = `PhidPc_EXName`**（与 `API-01` 同一个）—— ⛔ **不是**从 `BillName` 解析出来的。
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.errors import NotConfiguredError
from app.mod02_i8 import contract_source as cs
from tests.acc_plugin import acc

# 用户 2026-09-19 提供的**真实**记录（字段名 = i8 真名；已按契约保留关键项）
REC = {
    "PhId": "3700000000700286",
    "BillDt": "2026-09-15",
    "BillNo": "CGHT2026090188",
    "BillName": "四分晋江污泥处置项目/主材钢材/业祥/河南安装/27269.82元（增补合同CGHT2026030048）",
    "CntType": "3",
    "CntOrgSumVat": 27269.82,
    "CntSumVat": 27269.82,
    "CntSum": 24132.58,
    "PhidSupplyEnt": "3700000000025311",
    "AppStatus": 1,
    "PhidOrg": "3700000000000014",
    "Remarks": "增补原合同：CGHT2026030048，原合同金额：99646.56元，单价一致。",
    "PhidPc_EXName": "晋江市污泥处置中心一期工程核心设备安装工程",
    "CntType_EXName": "物资采购合同",
}


class _FakeClient:
    """记录调用形态；`payloads` 可给**多次**响应（用于"空结果确认"路径）。"""

    def __init__(self, payload=None, *, payloads=None) -> None:  # noqa: ANN001
        self.payload = payload
        self.payloads = list(payloads) if payloads else None
        self.calls: list[tuple] = []

    def _next(self):  # noqa: ANN001
        return self.payloads.pop(0) if self.payloads else self.payload

    def post_json(self, url, params=None, **kw):  # noqa: ANN001
        self.calls.append(("POST", url, params, kw.get("data"), kw.get("timeout")))
        return self._next()

    def get_json(self, url, params=None, **kw):  # noqa: ANN001
        self.calls.append(("GET", url, params, None, None))
        return self._next()


def _patch(monkeypatch, url: str = "http://i8/api04") -> None:  # noqa: ANN001
    """把接口地址塞进设置（`.env` 里已有一份真值 ⇒ 测试必须显式覆盖，含"空"这种情形）。"""
    monkeypatch.setenv("I8_CONTRACT_LIST_URL", url)
    get_settings.cache_clear()


def _fetch(monkeypatch, payload=None, *, payloads=None, url="http://i8/api04"):  # noqa: ANN001
    _patch(monkeypatch, url)
    fake = _FakeClient(payload, payloads=payloads)
    return cs.ContractFetcher(fake).fetch_all(), fake          # type: ignore[arg-type]


@acc()
def test_请求形态是POST且query挂在url上(monkeypatch):  # noqa: ANN001
    rows, fake = _fetch(monkeypatch, {"Record": [REC]})
    method, url, params, data, timeout = fake.calls[0]
    assert method == "POST", "API-04 必须是 POST（GET 会被 i8 拒：500）"
    assert url == "http://i8/api04"
    assert params["model"] == cs.CONTRACT_MODEL == "7"
    assert "floatmenuCondition" in params and "_dc" in params
    assert len(rows) == 1


@acc()
def test_必须传limit否则只回10条(monkeypatch):  # noqa: ANN001
    """⛔ 2026-09-19 实测坑：`limit` 不放 body ⇒ i8 只回 **10 条**（默认页）⇒ 静默只抓一小截。"""
    _rows, fake = _fetch(monkeypatch, {"Record": [REC]})
    _m, _u, _p, data, timeout = fake.calls[0]
    assert data["limit"] == cs.LIST_LIMIT == "5000", "limit 必须在 **body** 里"
    assert data["pageId"] == cs.PAGE_ID and data["page"] == "0" and data["start"] == "0"
    assert data["queryfilter"] == ""
    # ⚠️ 本接口实测要 ~41 秒 ⇒ 默认 30s 必超时 ⇒ 必须显式放大
    assert timeout == cs.LIST_TIMEOUT and timeout > 30, "必须放大 timeout（默认 30s 会超时）"


@acc()
def test_字段真名映射到落库字段(monkeypatch):  # noqa: ANN001
    rows, _ = _fetch(monkeypatch, {"Record": [REC]})
    row = rows[0]
    assert row["contract_no"] == "CGHT2026090188"              # ⭐ 幂等键
    assert row["project_name"] == "晋江市污泥处置中心一期工程核心设备安装工程"
    assert row["contract_amt"] == 27269.82
    assert row["material_name"] == "主材钢材"                  # 由 BillName 第 2 段解析（**辅助列**）
    assert row["supplier_name"] == "业祥"                      # 第 3 段
    assert row["sign_date"] == "2026-09-15"
    assert row["cnt_type"] == "物资采购合同"
    assert row["approve_status"] == "已批"                     # AppStatus=1 ⇒ 复用 API-01 的判定
    assert row["remark"].startswith("增补原合同")
    assert row["fields"] is REC, "整条原样留存（不丢信息）"


@acc()
def test_项目匹配字段是PhidPc_EXName而非解析BillName(monkeypatch):  # noqa: ANN001
    """⛔ 这条钉住"匹配靠谁" —— 若改成从 `BillName` 切项目名，此断言必须红。"""
    rows, _ = _fetch(monkeypatch, {"Record": [REC]})
    assert cs.MATCH_FIELD == "PhidPc_EXName"
    assert rows[0]["project_name"] == REC["PhidPc_EXName"]
    assert rows[0]["project_name"] != "四分晋江污泥处置项目", "⛔ 不得用 BillName 第 1 段当项目"


@acc()
def test_空结果会再确认一次防整批漏抓(monkeypatch):  # noqa: ANN001
    import app.mod02_i8.contract_source as _cs
    monkeypatch.setattr(_cs.time, "sleep", lambda *_: None)     # 别真等 1.2s
    rows, fake = _fetch(monkeypatch, payloads=[{"Record": []}, {"Record": [REC]}])
    assert len(rows) == 1 and len(fake.calls) == 2, "空结果必须再确认一次"


@acc()
def test_未配url显式报错不静默(monkeypatch):  # noqa: ANN001
    _patch(monkeypatch, "")
    try:
        cs.ContractFetcher(_FakeClient({"Record": []})).fetch_all()   # type: ignore[arg-type]
    except NotConfiguredError:
        return
    raise AssertionError("未配置 URL 必须抛 NotConfiguredError（⛔ 不得静默返回空）")


@acc()
def test_没有合同编号的行被丢弃():
    assert cs._map_record({**REC, "BillNo": ""}) is None, "无 BillNo ⇒ 无法幂等落库 ⇒ 必须丢弃"


@acc()
def test_BillName段数不足不抛():
    assert cs._parse_bill_name("只有一个项目名") == ("", "")
    assert cs._parse_bill_name("") == ("", "")
    assert cs._parse_bill_name("项目/材料") == ("材料", "")


@acc()
def test_概要给出条数与项目清单():
    s = cs.summary([{"project_name": "A"}, {"project_name": "A"}, {"project_name": "B"}, {}])
    assert s["total"] == 4 and s["projects"] == ["(无项目)", "A", "B"]
