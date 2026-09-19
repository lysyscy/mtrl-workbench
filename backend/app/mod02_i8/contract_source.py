"""采购合同取数（`API-04`）—— 归 **`MOD-02`**（i8 接入层能力 #5「集采采购合同抓取」）。

依据：用户 **2026-09-19** 提供的真实接口与响应样例 ⇒ 契约见计划 `§14.4c`「`API-04` 契约」。

⚠️ **实测形态（2026-09-19，本工程直连验证）**：
- 方法 = **POST**（⛔ 不是 GET！GET ⇒ `500 Request method 'GET' is not supported`）·
  query 参数挂在 **URL** 上（`model=7&floatmenuCondition=`）、body 为空；
- **需要 i8 会话**（无会话 ⇒ `401 No SessionInfo found`）⇒ 必须走 `I8Client`
  （它自带登录与"401 重登一次"）。
⛔ **「按月抓取」不可行**：该接口**没有月份参数** ⇒ 只能**每次全量抓**，
  靠 `BillNo` **增量落库**（已存在的不重复插、**已人工标记过的行绝不被覆盖**）。
  ⇒ 这也意味着**每次点一下都要拉完 300+ 条**（故需实测全量耗时）。

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
    _amount,
    _extract_records,
    _first,
    approve_status_of,
)

logger = get_logger()

#: `model=7` —— ⚠️ **含义待确认**（疑为"单据类型"）。取值以真机为准，⛔ 别在别处再写一份 `7`。
CONTRACT_MODEL = "7"

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

    def fetch_all(self) -> list[dict]:
        """全量取一次（**人工触发**）⇒ 映射后的行列表（无法识别编号的**已丢弃**，见 `_map_record`）。"""
        url = configured_url()
        params = build_params()
        with serialize_fetch(TABLE):
            records: list[dict] = []
            for attempt in range(EMPTY_RETRY + 1):
                resp = self._client.post_json(url, params=params, data={})
                records = _extract_records(resp)
                if records or attempt >= EMPTY_RETRY:
                    break
                logger.warning("i8 采购合同返回 0 条 —— 再确认一次（防偶发回有效空 ⇒ 整批漏抓）")
                time.sleep(EMPTY_RETRY_SLEEP)
        mapped: list[dict] = []
        for rec in records:
            row = _map_record(rec)
            if row is not None:
                mapped.append(row)
        logger.info("采购合同取数：取到 {} 条 / 可落库 {} 条", len(records), len(mapped))
        return mapped


def configured_url() -> str:
    """`API-04` 的端点（取自 `.env` 的 `I8_CONTRACT_LIST_URL`；⛔ 不硬编码）。

    未配置 ⇒ `NotConfiguredError`（**显式报错，绝不静默** —— 与 `API-01` 同口径）。
    """
    url = str(getattr(get_settings(), "i8_contract_list_url", "") or "").strip()
    if not url:
        raise NotConfiguredError("i8 采购合同接口未配置（见 `I8_CONTRACT_LIST_URL`，或到「设置」页填写 i8 服务地址）")
    return url


def build_params(*, now_ms: int | None = None) -> dict[str, str]:
    """URL 上的 query 参数（`_dc` = 防缓存时间戳，i8 前端惯例）。"""
    return {
        "model": CONTRACT_MODEL,
        "floatmenuCondition": "",
        "_dc": str(now_ms if now_ms is not None else int(time.time() * 1000)),
    }


def _parse_bill_name(bill_name: str) -> tuple[str, str]:
    """i8 的 `BillName`（`项目/物资/供应商/施工单位/金额（…）`）→ `(材料名称, 供应商简称)`。

    ⚠️ **尽力而为**（段数不够 ⇒ 返回空串，⛔ 不抛）—— 它只是**辅助列**：
    **项目匹配不依赖它**（走 `MATCH_FIELD`）。
    """
    parts = [p.strip() for p in str(bill_name or "").split("/")]
    material = parts[1] if len(parts) > 1 else ""
    supplier = parts[2] if len(parts) > 2 else ""
    return material, supplier


def _map_record(rec: dict) -> dict | None:
    """`API-04` 记录 → 落库字段；**无法识别编号 ⇒ `None`**（调用方丢弃并计数）。

    ⚠️ `BillNo` 是**幂等键**（增量落库靠它）⇒ 没有它这行**没法落**（也不能落）⇒ 丢弃。
    ⚠️ 整条原样留在 `fields`（不丢信息，与 `API-01` 同口径）。
    """
    contract_no = _first(rec, "BillNo", "billNo", "合同编号")
    if not contract_no:
        return None
    material, supplier = _parse_bill_name(_first(rec, "BillName"))
    return {
        "contract_no": contract_no,                              # ⭐ 去重 / 增量键
        "project_name": _first(rec, MATCH_FIELD, "projectName"),  # ⭐ 匹配字段（同 API-01）
        "bill_name": _first(rec, "BillName"),
        "material_name": material,
        "supplier_name": supplier,
        "sign_date": _first(rec, "BillDt", "billDt")[:10],
        "contract_amt": _amount(rec, "CntSumVat", "CntOrgSumVat", "合同金额"),
        "cnt_type": _first(rec, "CntType_EXName", "CntType"),
        "approve_status": approve_status_of(rec),
        "remark": _first(rec, "Remarks", "Remark"),
        "supply_ent": _first(rec, "PhidSupplyEnt"),
        "fields": rec,
    }


def summary(rows: list[dict]) -> dict[str, Any]:
    """取数结果的一句话概要（供抓取回执 / 预览用；⛔ 不做业务判定）。"""
    return {
        "total": len(rows),
        "projects": sorted({r.get("project_name") or "(无项目)" for r in rows}),
    }


__all__ = [
    "ContractFetcher", "MATCH_FIELD", "TABLE", "CONTRACT_MODEL",
    "EMPTY_RETRY", "build_params", "configured_url", "summary",
]
