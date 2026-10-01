"""采购合同取数（`API-04`）—— 归 **`MOD-02`**（i8 接入层能力 #5「集采采购合同抓取」）。

依据：用户 **2026-09-19** 提供的真实接口与响应样例 ⇒ 契约见计划 `§14.4c`「`API-04` 契约」。

⚠️ **实测形态（2026-09-19，本工程直连验证）**：
- 方法 = **POST**（⛔ 不是 GET！GET ⇒ `500 Request method 'GET' is not supported`）·
  query 参数挂在 **URL** 上（`model=7&floatmenuCondition=`）、body 为空；
- **需要 i8 会话**（无会话 ⇒ `401 No SessionInfo found`）⇒ 必须走 `I8Client`
  （它自带登录与"401 重登一次"）。
⭐⭐ **支持按「单据日期」增量抓**（2026-09-19 实测**推翻**了原先这里那句「没有月份参数、只能全量抓」——
  那句话是错的：接口**有**日期过滤，只是**写法特殊**，用户给了真机 body 才试出来）。

**日期过滤必须包一层 `queryFilter`**（关键，写错不报错）：
```
queryfilter = {"queryFilter": "{\"BillDt*date*ge*1\":\"2026-09-06\"}"}
                    ↑ 外层包一层，内层才是过滤条件
```
⛔ 直接把内层 `{"BillDt*date*ge*1": …}` 放上去 ⇒ **不生效** —— 接口照样返回全量、也**不报错**
（2026-09-19 实测踩到：连试 5 种类型名全是"成功但没过滤"）。

**实测提速**（同一接口、同一账号、同日）：

| 过滤条件 | 耗时 | 命中 |
|---|---|---|
| 无过滤（全量 355） | **40.4s** | 355 |
| `BillDt >= 2026-09-06` | **1.0s** | 3 |
| `BillDt >= 2026-09-01` | 1.2s | 5 |
| `BillDt >= 2026-06-01` | 4.9s | 22 |

⇒ ⭐ 耗时**与命中条数成正比** ⇒ 慢的是 **i8 侧扫描匹配**（不是网络、不是响应体大小）
  ⇒ **增量抓（默认起点 = 上次抓到的日期 − 3 天）只要 1~5 秒**。
  ⇒ 依旧靠 `BillNo` **幂等地**增量落库（已存在的不重复插、**已人工标记过的行绝不被覆盖**）
     ⇒ 起点往前多推几天是**安全的**（重复的会被幂等挡掉）。

⚠️ **材料名要逐条问详情**（列表接口一个材料字段都没有 —— 见 `DETAIL_PATH`）：
   全量首次约 347 次请求（几分钟，**就这一次**）；之后增量只补**新增那几条**（秒级）。

⭐ **项目匹配字段 = `PhidPc_EXName`** —— 与 `API-01`（付款通知书）**用的是同一个字段**
  ⇒ 「和付款通知书一个匹配逻辑」在工程上**天然成立**，⛔ 不必新造匹配器。

⚠️ 本模块**复用** `notice_source` 的 `_first` / `_amount` / `_extract_records` / `approve_status_of`
  （同层基础设施，避免在同一件事上出现第二份实现）；⛔ 不复制粘贴。
"""

from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings
from app.core.errors import NotConfiguredError
from app.core.logging import get_logger
from app.mod02_i8.client import I8Client, serialize_fetch
from app.mod02_i8.notice_source import (  # noqa: PLC2701 —— 同层复用，见模块头
    APPROVE_STATUS_DONE,
    _amount,
    _extract_records,
    _first,
    approve_status_of,
)

logger = get_logger()

#: `model=7` —— ⚠️ **含义待确认**（疑为"单据类型"）。取值以真机为准，⛔ 别在别处再写一份 `7`。
CONTRACT_MODEL = "7"

#: ⭐ 列表页大小上限 —— ⛔ **必须放进 POST body**：实测 2026-09-19，**不传 `limit` 时 i8 只回 10 条**
#:   （355 条的全量 = `limit=5000&page=0&start=0` 放在 **body** 里；放 URL 上不生效）。
LIST_LIMIT = "5000"

#: i8 前端的列表页标识（body 与请求头各带一份；实测服务端**不校验请求头那份** ⇒ 放 body 即可）。
PAGE_ID = "Web:PMS3.PCM.PCM_INFO_List7"

#: ⭐ **组织范围**（`clientfilter`）—— 照真机 body 原样：`#curOrg:<本组织 id>`。
#:   ⚠️ 它是 i8 前端**必带**的筛选上下文 ⇒ 缺了可能拿到**别组织**的合同（静默混进台账，很难发现）。
#:   ⚠️ 硬编码这一处（真机值）；将来若换组织，改这里（⛔ 别在别处再写一份）。
CLIENT_FILTER = ('{"CntType":"","OrgQuery":"#type:ORG#curOrg:3700000000000014'
                 '#subOrg:#curProj:#cubProj:#parentNode:undefined"}')

#: 真机 body 里的 `ng3_logid`（i8 的日志关联 id）—— 原样带上（取值以真机为准）。
LOG_ID = "3700000000000714"

#: ⭐⭐ **详情接口**（`M5-6`）—— 合同**材料名**（`ItemName`）**只有这里有**。
#:   ⚠️ 列表接口（`GetCntMList`）**一个材料字段都没有**：88 个字段全查过，
#:      `AuxItems1/2/3` / `ItemResource` **恒空**，`_EXName` 一族只有 合同类型/人/组织/供应商/项目。
#:      而 i8 **详情页**显示的"材料"就是它 ⇒ 用户 2026-09-19 亲自指出（`ItemName` 就是材料名）。
#:   ⚠️ 形态（真机）：**POST**，`?id=<合同 PhId>&type=cnt`，body 空 ⇒ 材料在 `Data.Grid.results[0].ItemName`。
DETAIL_PATH = "/PMS/PCM/Contract/GetCntMInfoFirst"
DETAIL_TYPE = "cnt"
DETAIL_TIMEOUT = 60.0

#: ⚠️⚠️ 本接口**特别慢**：实测**10 条与 355 条都要 ~41 秒** ⇒ **慢在 i8 侧查询、与条数无关**。
#:   `I8Client` 默认 `timeout=30s` ⇒ **必然 ReadTimeout**（2026-09-19 实测踩到）⇒ 此处显式放大。
LIST_TIMEOUT = 200.0

#: ⭐ **未审批的不抓**（用户 2026-09-19 定）：实测 355 条里有 8 条 `AppStatus=0`（未审批）⇒ 丢弃。
#:   ⚠️ 丢弃数会**进日志与概要**（禁静默 —— 否则"抓了 355 却只落了 347"没人知道为什么）。
ONLY_APPROVED = True

#: 取数串行锁的键（D9：同一张表抓取互斥）。
TABLE = "jc_contract"

#: 同 `API-01`：i8 会**偶发返回"有效但空"** ⇒ "0 条"务必**再确认一次**（否则整批静默漏抓）。
EMPTY_RETRY = 1
EMPTY_RETRY_SLEEP = 1.2

#: ⭐ 项目匹配字段（**与 `API-01` 同字段** —— 付款项目 / 合同项目在 i8 里就是同一个）。
MATCH_FIELD = "PhidPc_EXName"


class ContractFetcher:
    """采购合同取数器（`API-04`）。"""

    def __init__(self, client: I8Client) -> None:
        self._client = client
        #: 本次因「未审批」丢弃的条数（回执要报，⛔ 不静默）
        self.last_unapproved = 0

    def fetch_all(self, *, since: str = "") -> list[dict]:
        """取一次（**人工触发**）⇒ 映射后的行列表（无法识别编号的**已丢弃**，见 `_map_record`）。

        ⭐ `since`（`YYYY-MM-DD`）= **单据日期起点** ⇒ 空 = **全量**（首次），有值 = **增量**（日常）。
        ⚠️ 增量**必须把起点往前推几天**（由调用方负责，见 `fetch_service`）——
           i8 里**增补合同会沿用原单据日期** ⇒ 起点卡太紧会**漏掉它们**；
           好在落库按 `BillNo` **幂等**，起点推早了只是多拿几条、**不会重复插**。
        """
        url = configured_url()
        params = build_params()
        body = build_body(since=since)
        with serialize_fetch(TABLE):
            records: list[dict] = []
            for attempt in range(EMPTY_RETRY + 1):
                # ⚠️ `timeout` 必须显式放大（见 `LIST_TIMEOUT`：默认 30s 必超时）
                resp = self._client.post_json(
                    url, params=params, data=body, timeout=LIST_TIMEOUT)
                records = _extract_records(resp)
                if records or attempt >= EMPTY_RETRY:
                    break
                logger.warning("i8 采购合同返回 0 条 —— 再确认一次（防偶发回有效空 ⇒ 整批漏抓）")
                time.sleep(EMPTY_RETRY_SLEEP)
        mapped: list[dict] = []
        unapproved = 0
        for rec in records:
            row = _map_record(rec)
            if row is None:
                continue
            if ONLY_APPROVED and row["approve_status"] != APPROVE_STATUS_DONE:
                unapproved += 1                 # ⭐ 未审批不抓（但**必须计数并报出来**，禁静默）
                continue
            mapped.append(row)
        logger.info("采购合同取数：取到 {} 条 / 可落库 {} 条（未审批丢弃 {} 条）",
                    len(records), len(mapped), unapproved)
        self.last_unapproved = unapproved       # 供回执取用（⛔ 不静默丢数据）
        return mapped

    def fetch_item_name(self, ph_id: str) -> str:
        """按合同 `PhId` 取**材料名**（`Data.Grid.results[0].ItemName`）—— ⭐ `M5-6` 的材料来源。

        ⚠️ **为什么必须逐条问详情**：列表接口一个材料字段都没有（见 `DETAIL_PATH` 的注释）；
           i8 详情页显示的"材料"就是 `ItemName`。
        ⚠️ **`Grid` 优先于 `ItemGrid`**：`Grid` = **材料汇总行**（`单位=批`、`数量=1`，
           实测**几乎每条都有**）；`ItemGrid` = **明细行**（实测多数合同为空 —— 尤其增补合同）。
        ⚠️ **查不到 / 报错 ⇒ 回空串、⛔ 不抛**：材料名不是关键字段，不该因它让**整批抓取**失败。
           但调用方**必须计数并报出来**（禁静默 —— 否则"材料名怎么空了"没人知道）。
        """
        pid = str(ph_id or "").strip()
        if not pid:
            return ""
        try:
            resp = self._client.post_json(configured_detail_url(),
                                          params={"id": pid, "type": DETAIL_TYPE},
                                          data={}, timeout=DETAIL_TIMEOUT)
        except Exception as exc:                        # noqa: BLE001 —— 见上：单条失败不断整批
            logger.warning("合同 {} 的材料名取数失败（本条留空，不影响落库）：{}", pid, exc)
            return ""
        data = (resp or {}).get("Data") if isinstance(resp, dict) else None
        if not isinstance(data, dict):
            return ""
        for grid_key in ("Grid", "ItemGrid"):
            grid = data.get(grid_key)
            if not isinstance(grid, dict):
                continue
            for row in (grid.get("results") or []):
                name = str((row or {}).get("ItemName") or "").strip()
                if name:
                    return name[:128]
        return ""


def configured_url() -> str:
    """`API-04` 的端点（取自 `.env` 的 `I8_CONTRACT_LIST_URL`；⛔ 不硬编码）。

    未配置 ⇒ `NotConfiguredError`（**显式报错，绝不静默** —— 与 `API-01` 同口径）。
    """
    url = str(getattr(get_settings(), "i8_contract_list_url", "") or "").strip()
    if not url:
        raise NotConfiguredError("i8 采购合同取数还没配置 —— 请到「设置」页填写 i8 服务地址")
    return url


def build_params(*, now_ms: int | None = None) -> dict[str, str]:
    """**URL 上**的 query 参数（`_dc` = 防缓存时间戳，i8 前端惯例）。"""
    return {
        "model": CONTRACT_MODEL,
        "floatmenuCondition": "",
        "_dc": str(now_ms if now_ms is not None else int(time.time() * 1000)),
    }


def build_body(*, limit: str = LIST_LIMIT, since: str = "") -> dict[str, str]:
    """**POST body**（form-urlencoded）—— ⭐ 真正的"要全量 / 要增量"就靠它。

    ⛔ `limit` / `page` / `start` / `pageId` 都必须在 **body** 里（放 URL 不生效）：
    实测不传 `limit` ⇒ i8 只回 **10 条**（默认页）⇒ 会**静默地只抓到一小截**。

    ⭐ `since`（`YYYY-MM-DD`）= **单据日期起点**（`BillDt >= since`）；空 = 全量。
    ⚠️⚠️ **必须包一层 `queryFilter`**（`{"queryFilter": "<内层 JSON 字符串>"}`）——
       内层才是 `{"BillDt*date*ge*1": "..."}`；⛔ 直接放内层 ⇒ **不生效且不报错**（实测踩到）。
    ⚠️ `clientfilter`（组织范围）与 `ng3_logid` 照真机 body 原样带上 —— 它们是 i8 前端**必带**的，
       缺了可能拿到**别组织**的数据（那种错会静默混进台账）。
    """
    import json

    since = str(since or "").strip()
    inner = json.dumps({"BillDt*date*ge*1": since}, ensure_ascii=False) if since else ""
    query = json.dumps({"queryFilter": inner}, ensure_ascii=False) if since else ""
    return {
        "pageId": PAGE_ID,
        "env": "java",
        "model": CONTRACT_MODEL,
        "floatmenuCondition": "",
        "queryfilter": query,
        "sortinfo": "",
        "clientfilter": CLIENT_FILTER,
        "limit": str(limit),
        "page": "0",
        "start": "0",
        "ng3_logid": LOG_ID,
    }

# ⚠️ 2026-09-19 **删掉了 `_material_from_bill_name`**（原「拆单据名第 2 段」那套）——
#    实测拿 12 条真合同对照 i8 详情页：**只看对 2 条**（段位根本不固定：3 段时第 2 段是**供应商**、
#    4 段时是**项目**，而它们"看着都像材料名"，机器分不出来）⇒ 整段废弃。
#    ⛔ 不保留"已废弃但仍能被调用"的死代码（本仓纪律）；材料名改走 `DETAIL_PATH`（下同）。


def _supplier_of(rec: dict) -> str:
    """供应商全名 —— ⭐ 取 i8 的 **`_EXName`** 字段（**i8 自己给的名字**）。

    ⚠️⚠️ **2026-09-19 修正**：⛔ **别再拆单据名的第 3 段**当供应商 —— 那只是人随手写的简称
       （实测同一段里出现过 `钢材采购合同（业祥157944.48元）` 这种整句话、`配电柜` 这种材料名），
       而且**段位还不固定**（3 段时第 3 段是材料、5 段时才是供应商）。

    正解是 i8 的命名约定「**id 字段 ＋ `_EXName` ＝ 名字**」——
    实测 `PhidSupplyEnt_EXName`：覆盖 **344/347**、去重 **94 家**、**id ↔ 名字一一对应**、
    且**与单据名里那段完全对得上**（`业祥` ⇒ `洛阳市业祥商贸有限公司`）。
    ⚠️ 四个字段实测取值**完全一致**（`PhidSupplyEnt` / `PhidInvComp` / `PhidSenComp` / `InvoiceCmp`）
       ⇒ 按序回退，取到就用（⛔ 不拼、不改写、不猜）。
    """
    return _first(rec, "PhidSupplyEnt_EXName", "PhidInvComp_EXName",
                  "PhidSenComp_EXName", "InvoiceCmp_EXName")


def _map_record(rec: dict) -> dict | None:
    """`API-04` 记录 → 落库字段；**无法识别编号 ⇒ `None`**（调用方丢弃并计数）。

    ⚠️ `BillNo` 是**幂等键**（增量落库靠它）⇒ 没有它这行**没法落**（也不能落）⇒ 丢弃。
    ⚠️ 整条原样留在 `fields`（不丢信息，与 `API-01` 同口径）。
    """
    contract_no = _first(rec, "BillNo", "billNo", "合同编号")
    if not contract_no:
        return None
    bill_name = _first(rec, "BillName")
    return {
        "contract_no": contract_no,                              # ⭐ 去重 / 增量键
        "project_name": _first(rec, MATCH_FIELD, "projectName"),  # ⭐ 匹配字段（同 API-01）
        "bill_name": bill_name,                                  # ⭐ i8 原文（落库保留，可回溯）
        # ⚠️ **材料名不在这里取** —— i8 **列表接口没有**材料字段（88 个字段全查过）。
        #    它在**详情接口**（`DETAIL_PATH` → `Data.Grid.results[0].ItemName`）
        #    ⇒ 由 `fetch_service` 在**落库前逐条补**（且只对"库里还没有的"调，增量时只有几条）。
        #    ⛔ 曾经这里拆单据名第 2 段 —— 实测 12 条只看对 2 条（段位根本不固定）⇒ 已废。
        "material_name": "",
        # ⭐ 供应商：取 i8 的 `_EXName`（⛔ 不再拆第 3 段 —— 那只是人写的简称、段位还不固定）
        "supplier_name": _supplier_of(rec),
        "sign_date": _first(rec, "BillDt", "billDt")[:10],
        "contract_amt": _amount(rec, "CntSumVat", "CntOrgSumVat", "合同金额"),
        "cnt_type": _first(rec, "CntType_EXName", "CntType"),
        "approve_status": approve_status_of(rec),
        "remark": _first(rec, "Remarks", "Remark"),
        "supply_ent": _first(rec, "PhidSupplyEnt"),
        # ⭐ **甲方单位**（`M5-6b` · 用户 2026-09-20 口径）—— 它决定"**i8 这个合同价是谁的价**"：
        #    甲方是**贸易公司**（维萨）⇒ 这个价是贸易公司的价，真供应商的价 i8 里**没有**。
        #    ⚠️ 实测（347 条）取值只有 5 种：第四工程公司 219 / 河南省安装集团 46 /
        #       洛阳盟岳 38 / **洛阳维萨 24** / 化工工程事业部 20 ⇒ 它确实是"甲方（客户方）"。
        #    ⚠️ `PhidRecComp_EXName` 实测与它**逐一相同**（互为印证）；⛔ 别改用
        #       `PhidTickComp_EXName` / `InvoiceSen_EXName` —— 那两个多出「河南省安装集团本部×2」，
        #       与"甲方"不是同一个口径（用错就多出一类甲方，还得人工收拾）。
        "party_name": _first(rec, "PhidCustomerEnt_EXName"),
        "fields": rec,
    }


def summary(rows: list[dict]) -> dict[str, Any]:
    """取数结果的一句话概要（供抓取回执 / 预览用；⛔ 不做业务判定）。"""
    return {
        "total": len(rows),
        "projects": sorted({r.get("project_name") or "(无项目)" for r in rows}),
    }


def configured_detail_url() -> str:
    """**详情接口**的完整地址 —— ⭐ **由 `i8_base_url` 推导**（`DETAIL_PATH`）。

    ⚠️ 列表接口有独立配置项（`I8_CONTRACT_LIST_URL`，是**完整 URL**），详情接口**没有** ——
       但两者**同源**（同一台 i8、同一个前缀）⇒ 从 base 拼，⛔ 不为它再开一个配置项
       （多一个配置项 = 多一处能配错的地方，而它没有"换地址"的独立需求）。
    ⚠️ base 未配置 ⇒ 走 `configured_url()` 的同一句报错口径（**显式报错，绝不静默**）。
    """
    base = str(getattr(get_settings(), "i8_base_url", "") or "").strip().rstrip("/")
    if not base:
        raise NotConfiguredError("i8 服务地址未配置（见 `i8_base_url`，或到「设置」页填写）")
    return base + DETAIL_PATH


__all__ = [
    "ContractFetcher", "MATCH_FIELD", "TABLE", "CONTRACT_MODEL",
    "EMPTY_RETRY", "LIST_LIMIT", "LIST_TIMEOUT", "PAGE_ID",
    "CLIENT_FILTER", "LOG_ID", "DETAIL_PATH", "DETAIL_TYPE", "DETAIL_TIMEOUT",
    "build_body", "build_params", "configured_url", "configured_detail_url", "summary",
]
