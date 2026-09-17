"""i8 基础数据源：**仓库列表**（`API-05` GetWareHouseList）· **常用项目列表**（`API-06` GetCommonUseList）。

依据：《说明书》§3.1.1（数据来源清单）· §3.1.2（前置条件）· §3.1.3（触发方式）· 附录 E.1（`API-05`/`API-06`）。

用途：
- 仓库列表 ⇒ **仓库名 ↔ 所属项目全名**（建档推导判据 / 占位行扶正 / 「同步仓库名单」）
- 常用项目列表 ⇒ **`phid` 权威来源**（建档链路 A 步骤 a；项目须先加入 i8 常用项目列表才能抓到）

⚠️ **契约来源（2026-09-15 取齐）**：URL / 参数 / 字段名取自素材包可读实现，
   摘要见 `ops/i8-接口契约-旁证摘要.md` §二（源 = **旁证**，**口径不得反推**）。
   ⚠️ 端点仍**一律走配置**（`.env`）、响应仍**防御性解析**（真名在前、旧别名在后）。
"""

from __future__ import annotations

from typing import Any

from app.core.config import I8_PATH_COMMON_PROJECT, I8_PATH_WAREHOUSE_LIST, get_settings, i8_base_of, i8_endpoint_of
from app.core.errors import NotConfiguredError
from app.mod02_i8.client import I8Client, serialize_fetch


def _extract_records(resp: Any) -> list[dict]:
    if isinstance(resp, dict):
        for key in ("Record", "records", "data", "list", "rows"):
            val = resp.get(key)
            if isinstance(val, list):
                return [r for r in val if isinstance(r, dict)]
    if isinstance(resp, list):
        return [r for r in resp if isinstance(r, dict)]
    return []


def _pick(rec: dict, *keys: str) -> str:
    for k in keys:
        v = rec.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


# `API-05` 固定表单（素材包 `warehouse_sync.WH_PARAMS` 旁证；`orgQuery` 里的机构号 = 第四工程公司）
WH_PARAMS: dict[str, str] = {
    "orgQuery": "#type:ORG#curOrg:3700000000000014#subOrg:#curProj:#cubProj:#parentNode:",
    "pcid": "0", "page": "0", "start": "0", "sort": '[{"property":"PhidPc_EXName","direction":"ASC"}]',
    "ng3_logid": "",
}
WH_LIMIT = 100


class WarehouseSource:
    """仓库列表（`API-05` GetWareHouseList）。返回 `[{warehouse_name, owner_full_name}]`。

    真字段：`PhId` · **`Whname`**（仓库名）· **`PhidPc_EXName`**（全名）· `Nullify`（`"1"` = 作废，跳过）。
    """

    table = "warehouse_list"

    def __init__(self, client: I8Client) -> None:
        self._client = client

    def fetch(self) -> list[dict]:
        """⚠️ `API-05` 是 **POST form**（素材包 `WH_PARAMS` 旁证），不是 GET。"""
        settings = get_settings()
        if not i8_base_of(settings):
            raise NotConfiguredError("i8 服务地址未配置（见 .env 的 I8_BASE_URL，或到「设置」页填写）")
        form = {**WH_PARAMS, "limit": str(WH_LIMIT)}
        with serialize_fetch(self.table):
            resp = self._client.post_json(
                i8_endpoint_of(settings, I8_PATH_WAREHOUSE_LIST), data=form
            )
        rows: list[dict] = []
        for rec in _extract_records(resp):
            # `Nullify == "1"` = **作废仓库**，跳过（素材包 `warehouse_sync` 旁证）
            if str(rec.get("Nullify") or "").strip() == "1":
                continue
            name = _pick(rec, "Whname", "WareHouseName", "warehouseName", "仓库名", "Name")
            if not name:
                continue
            rows.append({
                "warehouse_name": name,
                # 全名（**尾部带项目编号**，剥编号是建档口径、不在取数层做）
                "owner_full_name": _pick(
                    rec, "PhidPc_EXName", "ProjectName", "projectName", "所属项目全名", "FullName"
                ),
            })
        return rows


class CommonProjectSource:
    """常用项目列表（`API-06` GetCommonUseList）—— **`phid` 的权威来源**。

    真字段：**`PhId`**（→ `phid`）· **`BillName`**（→ `name_full`，**尾部带项目编号**）· `BillNo`（→ `code`）· `Ab`。
    """

    table = "common_project"

    def __init__(self, client: I8Client) -> None:
        self._client = client

    def fetch(self) -> list[dict]:
        settings = get_settings()
        if not i8_base_of(settings):
            raise NotConfiguredError("i8 服务地址未配置（见 .env 的 I8_BASE_URL，或到「设置」页填写）")
        with serialize_fetch(self.table):
            resp = self._client.get_json(i8_endpoint_of(settings, I8_PATH_COMMON_PROJECT))
        rows: list[dict] = []
        for rec in _extract_records(resp):
            phid = _pick(rec, "PhId", "phid", "ProjectId")
            name = _pick(rec, "BillName", "ProjectName", "projectName", "项目全名", "FullName", "Name")
            if not phid and not name:
                continue
            rows.append({
                "name_full": name,
                "phid": phid,
                "code": _pick(rec, "BillNo", "code", "项目代码"),   # 项目代码（缺省空）
                "ab": _pick(rec, "Ab", "ab"),                        # 简称（缺省空）
            })
        return rows


__all__ = ["WarehouseSource", "CommonProjectSource", "WH_PARAMS", "WH_LIMIT"]
