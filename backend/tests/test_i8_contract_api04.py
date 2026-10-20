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
    # ⭐ 供应商**名字**在带 `_EXName` 后缀的字段里（i8 约定：id 字段 + `_EXName` = 名字）
    "PhidSupplyEnt_EXName": "洛阳市业祥商贸有限公司",
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


def test_请求形态是POST且query挂在url上(monkeypatch):  # noqa: ANN001
    rows, fake = _fetch(monkeypatch, {"Record": [REC]})
    method, url, params, data, timeout = fake.calls[0]
    assert method == "POST", "API-04 必须是 POST（GET 会被 i8 拒：500）"
    assert url == "http://i8/api04"
    assert params["model"] == cs.CONTRACT_MODEL == "7"
    assert "floatmenuCondition" in params and "_dc" in params
    assert len(rows) == 1


def test_必须传limit否则只回10条(monkeypatch):  # noqa: ANN001
    """⛔ 2026-09-19 实测坑：`limit` 不放 body ⇒ i8 只回 **10 条**（默认页）⇒ 静默只抓一小截。"""
    _rows, fake = _fetch(monkeypatch, {"Record": [REC]})
    _m, _u, _p, data, timeout = fake.calls[0]
    assert data["limit"] == cs.LIST_LIMIT == "5000", "limit 必须在 **body** 里"
    assert data["pageId"] == cs.PAGE_ID and data["page"] == "0" and data["start"] == "0"
    assert data["queryfilter"] == ""
    # ⚠️ 本接口实测要 ~41 秒 ⇒ 默认 30s 必超时 ⇒ 必须显式放大
    assert timeout == cs.LIST_TIMEOUT and timeout > 30, "必须放大 timeout（默认 30s 会超时）"


def test_字段真名映射到落库字段(monkeypatch):  # noqa: ANN001
    rows, _ = _fetch(monkeypatch, {"Record": [REC]})
    row = rows[0]
    assert row["contract_no"] == "CGHT2026090188"              # ⭐ 幂等键
    assert row["project_name"] == "晋江市污泥处置中心一期工程核心设备安装工程"
    assert row["contract_amt"] == 27269.82
    assert row["bill_name"].startswith("四分晋江污泥处置项目/主材钢材"), "⭐ i8 原文必须留存（可回溯）"
    # ⚠️ 材料名**不在这里取**：i8 列表接口**没有**材料字段（88 个字段全查过）
    #    ⇒ 由 `fetch_service` 落库前**逐条问详情**（`GetCntMInfoFirst` → `Data.Grid.results[0].ItemName`）。
    #    ⛔ 曾经这里拆单据名第 2 段 —— 实测拿 12 条真合同对照 i8 详情页，**只看对 2 条** ⇒ 已废。
    assert row["material_name"] == "", "取数层**故意留空** —— 材料名由编排层逐条补（见 fetch_service）"
    assert (row.get("fields") or {}).get("PhId"), "详情查询要靠 fields 里的 PhId ⇒ 必须留着"
    # ⚠️ 供应商：取 i8 的 **`_EXName`**（⛔ 不是拆单据名第 3 段 —— 那只是人写的简称、段位还不固定）
    assert row["supplier_name"] == "洛阳市业祥商贸有限公司"
    assert row["supplier_name"] != "业祥", "⛔ 不得回到「拆单据名第 3 段」的老路"
    assert row["sign_date"] == "2026-09-15"
    assert row["cnt_type"] == "物资采购合同"
    assert row["approve_status"] == "已批"                     # AppStatus=1 ⇒ 复用 API-01 的判定
    assert row["remark"].startswith("增补原合同")
    assert row["fields"] is REC, "整条原样留存（不丢信息）"


def test_项目匹配字段是PhidPc_EXName而非解析BillName(monkeypatch):  # noqa: ANN001
    """⛔ 这条钉住"匹配靠谁" —— 若改成从 `BillName` 切项目名，此断言必须红。"""
    rows, _ = _fetch(monkeypatch, {"Record": [REC]})
    assert cs.MATCH_FIELD == "PhidPc_EXName"
    assert rows[0]["project_name"] == REC["PhidPc_EXName"]
    assert rows[0]["project_name"] != "四分晋江污泥处置项目", "⛔ 不得用 BillName 第 1 段当项目"


def test_空结果会再确认一次防整批漏抓(monkeypatch):  # noqa: ANN001
    import app.mod02_i8.contract_source as _cs
    monkeypatch.setattr(_cs.time, "sleep", lambda *_: None)     # 别真等 1.2s
    rows, fake = _fetch(monkeypatch, payloads=[{"Record": []}, {"Record": [REC]}])
    assert len(rows) == 1 and len(fake.calls) == 2, "空结果必须再确认一次"


def test_未配url显式报错不静默(monkeypatch):  # noqa: ANN001
    _patch(monkeypatch, "")
    try:
        cs.ContractFetcher(_FakeClient({"Record": []})).fetch_all()   # type: ignore[arg-type]
    except NotConfiguredError:
        return
    raise AssertionError("未配置 URL 必须抛 NotConfiguredError（⛔ 不得静默返回空）")


def test_没有合同编号的行被丢弃():
    assert cs._map_record({**REC, "BillNo": ""}) is None, "无 BillNo ⇒ 无法幂等落库 ⇒ 必须丢弃"


def test_日期过滤必须包一层queryFilter():
    """⚠️⚠️ 钉住那个「**写错不报错**」的日期过滤写法（2026-09-19 用户给真机 body 才试出来）。

    日期过滤**必须包一层**：
    ```
    queryfilter = {"queryFilter": "{\"BillDt*date*ge*1\":\"2026-09-06\"}"}
                        ↑ 外层包一层；内层才是过滤条件
    ```
    ⛔ 直接把**内层**放上去 ⇒ 接口**照样返回全量、也不报错** —— 实测连试 5 种类型名/格式，
       全是"**成功但没过滤**"（那种错最坏：看着抓成功，其实每次都全量拉 40 秒，
       而且**没人会发现**）。⇒ 所以这条值得一个**专门的反向灵敏度变异**。

    ⭐ 实测依据（同接口、同账号、同日）：

    | 过滤 | 耗时 | 命中 |
    |---|---|---|
    | 无过滤（全量 355） | **40.4s** | 355 |
    | `BillDt >= 2026-09-06` | **1.0s** | 3 |
    | `>= 2026-09-01` | 1.2s | 5 |
    | `>= 2026-06-01` | 4.9s | 22 |

    ⇒ 耗时**与命中条数成正比** ⇒ 慢在 **i8 侧扫描匹配**（不是网络）⇒ 增量抓才能 1~5 秒。
    """
    import json

    b = cs.build_body(since="2026-09-06")
    outer = json.loads(b["queryfilter"])
    assert list(outer) == ["queryFilter"], f"必须是**单键** `queryFilter`，实际={list(outer)}"
    assert json.loads(outer["queryFilter"]) == {"BillDt*date*ge*1": "2026-09-06"}, "内层才是过滤条件"

    # 不带 `since` ⇒ **空串**（全量）⇒ ⛔ 不许残留一个"看着能过滤"的空壳
    full = cs.build_body()
    assert full["queryfilter"] == "", "全量时 queryfilter 必须是空串"
    # ⚠️ 组织范围（clientfilter）与 ng3_logid **照真机原样带上**：缺了可能拿到**别组织**的数据
    #    （那种错会静默混进台账 —— 比"抓不到"危险得多）。
    assert full["clientfilter"] == cs.CLIENT_FILTER and full["ng3_logid"] == cs.LOG_ID
    # 全量不许只抓一页（实测不传 limit ⇒ i8 只回 10 条）
    assert full["limit"] == cs.LIST_LIMIT and full["page"] == "0" and full["start"] == "0"


def test_供应商取EXName而不是拆单据名():
    """⭐ `M5-6` 修正：供应商取 i8 的 **`_EXName`**（i8 自己给的名字）—— ⛔ 不再拆单据名。

    ⚠️ 原先拆第 3 段：实测那只是人随手写的**简称**（同一段里出现过 `钢材采购合同（业祥157944.48元）`
       这种整句话、`配电柜` 这种材料名），而且**段位不固定**（3 段时第 3 段是材料、5 段时才是供应商）。
    ⚠️ 拆出来的值与真名**差很远**（`业祥` vs `洛阳市业祥商贸有限公司`）⇒ 会污染下游一切按供应商的统计。
    """
    assert cs._supplier_of({"PhidSupplyEnt_EXName": "洛阳市业祥商贸有限公司"}) == "洛阳市业祥商贸有限公司"
    # 四个字段实测取值一致 ⇒ 按序回退（主字段缺了才轮到后面那几个）
    assert cs._supplier_of({"PhidInvComp_EXName": "洛阳锐亿自动化工程技术有限公司"}) == "洛阳锐亿自动化工程技术有限公司"
    assert cs._supplier_of({}) == "", "一个都没有 ⇒ 空串（⛔ 不猜、⛔ 不从单据名拆）"
    # ⛔⚠️ **只有 id、没有名字 ⇒ 留空** —— 这正是当初踩的坑：`PhidSupplyEnt` 只有数字 id，
    #     拿它去别处换名字会换错（实测换成 `图木舒克市诚汇建材`，而真名是 `洛阳市业祥商贸`）。
    assert cs._supplier_of({"PhidSupplyEnt": "3700000000025311"}) == "", "⛔ 只有 id ⇒ 留空，不拿 id 冒充名字"


def test_概要给出条数与项目清单():
    s = cs.summary([{"project_name": "A"}, {"project_name": "A"}, {"project_name": "B"}, {}])
    assert s["total"] == 4 and s["projects"] == ["(无项目)", "A", "B"]


def test_会话失效判据要认body里的NoSessionInfo():
    """⚠️⚠️ 2026-09-19 修的两处**静默缺陷** —— 症状都是「**抓取成功但 0 条**」。

    ① i8 有时**不用 401**：回 **HTTP 200 ＋ `Msg='No SessionInfo found'`**（错误藏在 body 里）
       ⇒ 只判 401 ⇒ 不重登、不报错 ⇒ **静默拿到空数据**；
       ⚠️ 叠加 `cookie_store` 缓存（命中就不登录）后 ⇒ **失效 cookie 被反复使用**（当日实际踩到两次）。
    ② `Code` 是**字符串**（`'401'`）⇒ 原来拿 int `401` 去比 **恒为假**，那条判断从来没生效过。

    ⚠️ 反向也要钉：**正常响应不许误判** —— 否则每次都会重登，变成"反复顶号"（`D9` 禁止）。
    """
    import httpx

    from app.mod02_i8.client import I8Client

    def resp(status: int, body: dict) -> httpx.Response:
        return httpx.Response(status, json=body)

    # ① HTTP 200 + body 说没会话 ⇒ 必须算失效（这是修的那条）
    assert I8Client._is_session_invalid(  # noqa: SLF001
        resp(200, {"Code": "200", "Success": False, "Msg": "No SessionInfo found"})) is True
    assert I8Client._is_session_invalid(  # noqa: SLF001
        resp(200, {"Code": "0", "Msg": "No SessionInfo found"})) is True
    # ② `Code` 是字符串 401 ⇒ 也要认（原来 int 比恒假）
    assert I8Client._is_session_invalid(resp(200, {"Code": "401"})) is True  # noqa: SLF001
    # ③ 老路子（HTTP 401）不许退化
    assert I8Client._is_session_invalid(httpx.Response(401)) is True         # noqa: SLF001
    # ④ ⛔ 正常响应**不许**误判（否则反复重登 = 反复顶号）
    assert I8Client._is_session_invalid(  # noqa: SLF001
        resp(200, {"Code": "200", "Msg": "操作成功", "Record": []})) is False
    assert I8Client._is_session_invalid(resp(200, {"Code": "0", "Msg": "参数错误"})) is False  # noqa: SLF001


def test_未审批的不抓且计数不静默(monkeypatch):  # noqa: ANN001
    """⭐ 用户 2026-09-19 定：未审批不抓 —— 但**丢弃数必须报出来**（禁静默丢数据）。

    实测背景：355 条里有 8 条 `AppStatus=0` ⇒ 落库 347 条。
    """
    _patch(monkeypatch, "http://i8/api04")
    unapproved = {**REC, "BillNo": "CGHT-BAD-1", "AppStatus": 0}
    ok = {**REC, "BillNo": "CGHT-OK-1", "AppStatus": 1}
    fake = _FakeClient({"Record": [unapproved, ok]})
    fetcher = cs.ContractFetcher(fake)                          # type: ignore[arg-type]
    rows = fetcher.fetch_all()
    assert [r["contract_no"] for r in rows] == ["CGHT-OK-1"], "未审批的必须丢弃"
    assert fetcher.last_unapproved == 1, "丢弃数必须计数（回执要报，⛔ 不静默）"
