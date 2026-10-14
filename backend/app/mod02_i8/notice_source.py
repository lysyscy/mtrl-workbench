"""付款通知书取数（`API-01`，D4 最小取数）—— 归 **`MOD-02`**（i8 接入层能力 #4「付款通知书抓取」）。

依据：《说明书》§3.1.3（抓取触发方式）· §3.2（付款通知书）· §4.2；`API-01`。
⚠️ 抓取一律**按月**、**人工触发**、**失败不自动重试登录**（D9）。
⚠️ 2026-09-15 **归位**：原挂 `mod03_notice`（M1 切片 1 图快），按模块归属移到 `MOD-02`
   ⇒ 依赖方向回归「业务（`mod03`）→ 基础设施（`mod02`）」。

本模块只做"取数 → 解析映射"；落库（按 `ph_id` upsert）由调用方经 `repository.upsert_notice` 完成。

⚠️ **字段名来源（2026-09-15 取齐）**：`API-01` 的 **12 字段真名**已从素材包可读实现取得，
    摘要见 `docs/reference/i8-contract.md` §一（源 = 旁证，**口径不得反推**）。
    ⚠️ 仍保持**防御性解析**：真名优先、兼容少量旧别名；**整条原样存 `fields`（不丢信息）**。
"""

from __future__ import annotations

import calendar
import json
import time
from typing import Any

from app.core.config import I8_PATH_PAYMENT_NOTICE, get_settings, i8_base_of, i8_endpoint_of
from app.core.errors import NotConfiguredError
from app.core.logging import get_logger
from app.mod02_i8.client import I8Client, serialize_fetch

logger = get_logger()

# ============================================================
# `API-01` 请求契约（素材包可读实现 ＋ **2026-09-15 真机复核**）
# ============================================================

# 固定表单：**POST form-urlencoded**
# ⚠️ `dataKey` **必须传空串**（传了别的值会查不到数）
LIST_FORM: dict[str, str] = {
    "busType": "PaymentBill",
    "pageId": "Web:PaymentBill",
    "isLoadHistory": "1",
    "relateId": "14",
    "inputSource": "2",
    "phidOrgList": "3700000000000014",
    "phidProjList": "",
    "dataKey": "",
    "saveTableName": "fc3_code_table",
    "payStatus": "0",
    "summaryCols": "ApplyAmtFc,ApplyAmt,ApproveAmtFc,ApproveAmt",
    "page": "0",
    "start": "0",
}

# 全量抓取用的条数上限（单张精确查请传 limit=5）
LIST_LIMIT = 5000

# 单张单据的另三个来源（渲染打印件必需；素材包 `profiles_payment_bill` 旁证 + 2026-09-15 真机复核）
INFO_PATH = "/FC/FM/PaymentBill/getInfo"
DETAIL_PATH = "/FC/FM/PaymentBill/getDetInfo"
FLOW_PATH = "/api/WorkFlow3/WorkFlowApi/getFlowHisForPrint"

# ⚠️ **空结果必须再确认一次**：i8 会**偶发返回"有效但空"的响应**（并发时更明显）。
#    这里"0 条"等于"该月没有单据" ⇒ 不确认就可能**整月漏抓**。
EMPTY_RETRY = 1
EMPTY_RETRY_SLEEP = 1.2


class NoticeFetcher:
    """付款通知书取数器（`API-01`）。"""

    def __init__(self, client: I8Client) -> None:
        self._client = client

    def fetch_month(self, year_month: str) -> list[dict]:
        """按核算年月抓取付款通知书（`API-01`）。

        ⚠️ 取数方式 = **POST form-urlencoded + `queryfilter` 日期闭区间**（2026-09-15 真机复核）；
        不是 GET、也不接受 `yearMonth` 之类的简写参数。
        """
        settings = get_settings()
        if not i8_base_of(settings):
            raise NotConfiguredError("i8 服务地址未配置（见 .env 的 I8_BASE_URL，或到「设置」页填写）")

        form = build_list_form(year_month)
        # 同表串行（D9：同一张表抓取互斥）
        with serialize_fetch("payment_notice"):
            records: list[dict] = []
            for attempt in range(EMPTY_RETRY + 1):
                resp = self._client.post_json(
                    i8_endpoint_of(settings, I8_PATH_PAYMENT_NOTICE), data=form
                )
                records = _extract_records(resp)
                if records or attempt >= EMPTY_RETRY:
                    break
                logger.warning("i8 返回 0 条 —— 再确认一次（防偶发回有效空 ⇒ 整月漏抓）")
                time.sleep(EMPTY_RETRY_SLEEP)
        mapped: list[dict] = []
        for rec in records:
            row = _map_record(rec)
            if row is not None:
                mapped.append(row)
        logger.info("付款通知书取数：年月={} 解析到 {} 条", year_month, len(mapped))
        return mapped


def month_range(year_month: str) -> tuple[str, str]:
    """`YYYY-MM` → 该月**首尾日**（闭区间；核算期 = 自然月）。"""
    y, m = int(year_month[:4]), int(year_month[5:7])
    last = calendar.monthrange(y, m)[1]
    return f"{year_month}-01", f"{year_month}-{last:02d}"


def build_list_form(year_month: str, *, limit: int = LIST_LIMIT) -> dict[str, str]:
    """组装 `API-01` 的 POST 表单（含 `queryfilter` 的日期闭区间）。"""
    ge, le = month_range(year_month)
    query_filter = json.dumps(
        {"queryFilter": json.dumps(
            {"BillDt*date*ge*1": ge, "BillDt*date*le*1": le}, ensure_ascii=False
        )},
        ensure_ascii=False,
    )
    return {**LIST_FORM, "queryfilter": query_filter, "limit": str(int(limit))}


def _extract_records(resp: Any) -> list[dict]:
    if isinstance(resp, dict):
        for key in ("Record", "records", "data", "list"):
            val = resp.get(key)
            if isinstance(val, list):
                return val
    if isinstance(resp, list):
        return resp
    return []


class NoticeDetailFetcher:
    """单张单据的**主表 / 明细 / 审批流程**（渲染打印件必需的三个来源）。

    ⚠️ `getInfo` / `getDetInfo` 是 **POST form**（`{"id": <PhId>}`）；
       `getFlowHisForPrint` 是 **GET**（query 带 `bizId` / `bizPk`）。
    ⚠️ 流程**回空要再确认一次** —— 回空的后果是**所有签名静默漏印**
       （单子照常出纸、但一个签名都没有）；素材包实测出现过，重跑即正常。
    """

    def __init__(self, client: I8Client) -> None:
        self._client = client

    def fetch_info(self, ph_id: str) -> dict:
        """主表（`getInfo` → `Data`）。"""
        resp = self._client.post_json(INFO_PATH, data={"id": str(ph_id)})
        if isinstance(resp, dict):
            return dict(resp.get("Data") or {})
        return {}

    def fetch_detail(self, ph_id: str) -> list[dict]:
        """明细（`getDetInfo` → `Record[]`）。⚠️⭐ **空结果再确认一次**（`TAIL-61` · 2026-09-21）：

        与列表抓取、`fetch_flow` **同一条处理** —— i8 会**偶发返回"有效但空"的响应**（模块头注明）。
        明细回空的后果是**收款账号/银行/明细表整块静默丢失**（而**收款单位靠抬头兜底照旧"正常"**
        ⇒ 症状只剩"账号空"，极难发现；2026-09-21 全量 355 张里实取到 **2 张明细 0 行**）。
        ⚠️ 确认真空后**接受空 ＋ 告警**（真有单据没有明细，⛔ 不能死循环）。
        """
        for attempt in range(EMPTY_RETRY + 1):
            resp = self._client.post_json(DETAIL_PATH, data={"id": str(ph_id)})
            rows = _extract_records(resp)
            if rows or attempt >= EMPTY_RETRY:
                if not rows:
                    logger.warning("明细为空（已确认一次）—— 收款账号/银行/明细表会全部留空，请复核单据 {}", ph_id)
                return rows
            logger.warning("明细首次回空，{:.1f}s 后重试确认一次（防收款账号/银行静默丢失）", EMPTY_RETRY_SLEEP)
            time.sleep(EMPTY_RETRY_SLEEP)
        return []

    def fetch_flow(self, ph_id: str) -> list[dict]:
        """审批流程历史（**签名来源**）。空结果**再确认一次**。"""
        params = {"bizId": "paymentbill", "bizPk": str(ph_id)}
        for attempt in range(EMPTY_RETRY + 1):
            resp = self._client.get_json(FLOW_PATH, params=params)
            nodes = _extract_flow_nodes(resp)
            if nodes or attempt >= EMPTY_RETRY:
                if not nodes:
                    logger.warning("流程历史为空（已确认一次）—— 签名会全部留空，请复核单据 {}", ph_id)
                return nodes
            logger.warning("流程历史首次回空，{:.1f}s 后重试确认一次（防签名静默漏印）", EMPTY_RETRY_SLEEP)
            time.sleep(EMPTY_RETRY_SLEEP)
        return []


def _extract_flow_nodes(resp: Any) -> list[dict]:
    """流程历史响应 → 节点列表（兼容 `data` / `Data` / `Record`）。"""
    if isinstance(resp, dict):
        for key in ("data", "Data", "Record", "records"):
            val = resp.get(key)
            if isinstance(val, list):
                return [r for r in val if isinstance(r, dict)]
    if isinstance(resp, list):
        return [r for r in resp if isinstance(r, dict)]
    return []


# ============================================================
# 字段映射（真名见 `docs/reference/i8-contract.md` §一）
# ============================================================

# ⚠️ 口径主人 =《说明书》§4.4.1：系统**唯一需要识别的审批状态字面量 =「已批」**。
#    它同时是 `mod03_notice.domain.APPROVE_STATUS_DONE` 的值 —— `mod02`（基础设施）**不得反向依赖 `mod03`**，
#    所以这里**独立声明**，并由 `tests/test_i8_contract.py` 断言两处**不漂移**。
APPROVE_STATUS_DONE = "已批"
APPROVE_STATUS_OTHER = "未批"          # = 「已批」的补集（**仅用于显示**；判定只认 `!= APPROVE_STATUS_DONE`）

# i8 判「未审批」的原始值（素材包 `pay_notice_export_http._ZERO` 旁证）
_STATUS_ZERO = ("0", "", "none", "null", "nonetype")

# i8「收付款类型」→ 本工程 `bill_type`。
# ⚠️ **与直觉相反**：《说明书》§4.3.3 的列对应是 **材料 → 其他支出** · **外租机械 → 付款通知书**（别凭字面猜）。
TYPE_OTHER_EXPENSE = "其他支出"
TYPE_PAYMENT_NOTICE = "付款通知书"
BILL_TYPE_MECHANICAL = "mechanical"
BILL_TYPE_MATERIAL = "material"


def _first(rec: dict, *keys: str) -> str:
    """按序取第一个非空值（防御性：真名在前、旧别名在后）。"""
    for k in keys:
        v = rec.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


def _amount(rec: dict, *keys: str) -> float:
    """金额防御性解析（取不到 / 非法 ⇒ 0.0，**不抛**）。"""
    for k in keys:
        v = rec.get(k)
        if v in (None, ""):
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return 0.0


def approve_status_of(rec: dict) -> str:
    """审批状态（i8 `AppStatus` 原值 ⇒ 本工程判定字面量）。

    i8 的 `AppStatus` 是**原始值**（`0` / 空 = 未审批，其余 = 已审批）⇒ 这里做**零值判定后映射**；
    **i8 原值原样留在 `fields` 里**（不丢信息）。
    """
    raw = str(rec.get("AppStatus") if rec.get("AppStatus") is not None else "").strip().lower()
    return APPROVE_STATUS_OTHER if raw in _STATUS_ZERO else APPROVE_STATUS_DONE


def bill_type_of(rec: dict) -> str:
    """i8「收付款类型」→ 本工程 `bill_type`（见上方常量注释的列对应）。"""
    t = _first(rec, "PhidRecPayType_EXName", "BillType", "billType")
    if t == TYPE_PAYMENT_NOTICE:
        return BILL_TYPE_MECHANICAL
    if t == TYPE_OTHER_EXPENSE:
        return BILL_TYPE_MATERIAL
    return t or BILL_TYPE_MATERIAL


def _map_record(rec: dict) -> dict | None:
    """`API-01` 记录 → 落库字段。返回 upsert 参数字典；无法识别主键则 None。

    ⚠️ 「**已付款金额**」**不由 `API-01` 提供** —— 它 = **付款流水汇总**（§4.3.3 / §4.4.2）
       ⇒ 本函数恒落 `0.0`，真值由付款域按流水派生。
    """
    ph_id = _first(rec, "PhId", "phId", "id")
    if not ph_id:
        return None
    return {
        "ph_id": ph_id,
        "bill_no": _first(rec, "BillNo", "billNo", "单据编码", "单据号"),
        "bill_type": bill_type_of(rec),
        "project_name": _first(rec, "PhidPc_EXName", "Whname", "projectName", "付款项目", "项目名称"),
        "approve_status": approve_status_of(rec),
        "amount_approved": _amount(rec, "ApproveAmt", "AmountApproved", "审批金额"),
        "amount_paid": 0.0,                      # 见 docstring：由付款流水派生
        "doc_date": _first(rec, "BillDt", "billDt", "单据日期")[:10],
        "biz_type": _first(rec, "PhidBusType_EXName", "bizType", "业务类型"),
        "payee": _first(rec, "user_skdw_EXName", "payee", "收款单位"),
        "input_by": _first(rec, "PhidFillPsn_EXName", "inputBy", "录入人"),
        # ⚠️ 签名**不落库**（`sign_nodes` / `signatures` 两列已于 2026-09-15 清理）——
        #    它改为渲染时从 `getFlowHisForPrint` 现场取，见 `print/signatures.py`。
        "fields": rec,
    }


__all__ = [
    "NoticeFetcher", "NoticeDetailFetcher", "approve_status_of", "bill_type_of",
    "INFO_PATH", "DETAIL_PATH", "FLOW_PATH",
    "LIST_FORM", "LIST_LIMIT", "EMPTY_RETRY", "month_range", "build_list_form",
    "APPROVE_STATUS_DONE", "APPROVE_STATUS_OTHER",
    "BILL_TYPE_MATERIAL", "BILL_TYPE_MECHANICAL",
    "TYPE_OTHER_EXPENSE", "TYPE_PAYMENT_NOTICE",
]
