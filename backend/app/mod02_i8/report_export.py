"""报表类导出（`API-02` 收发结存 / `API-03` 库存单据）—— **通用引擎**。

主人：《技术栈选型分析》**§9.8**（真机实测定稿 · **照抄即可，不要重新探测** —— 探测要登录 i8 ⇒ 强踢在线用户）。
实现层借鉴 = `PRD素材包-20260911/input/common_export.py`（⚠️ 只借鉴**接口形态**，口径不得反推）。

⭐ 与 `API-01`（付款通知书）**不是同一条路**：
- `API-01`：`POST getList` + **`queryfilter` 里的「单据日期」闭区间**（见 `fetch_task.build_fetch_params`）
- 本模块：`POST /reportcenter/reportExport/export` + **JSON 体**，时间入参 = **「起止年月」四个独立值**
  （`a` 开始核算年 / `b` 开始核算月 / `aa` 结束核算年 / `bb` 结束核算月）⇒ 响应**直接是 xlsx**

⚠️ 本模块**不连库、不写文件**（落盘 / 解析 / 落库由调用方负责）。
"""

from __future__ import annotations

import json

from app.core.config import I8_PATH_REPORT_EXPORT, I8_REPORTS
from app.core.errors import ExternalServiceError, MustReportError
from app.core.period import MODE_MONTH, month_of

EXPORT_TYPE = "excel"
SHEET_KEY = "0"

# 响应体最小字节数 —— 低于它基本不是正常 xlsx（素材包同款阈值；异常时把前 200 字节打出来便于诊断）
MIN_XLSX_BYTES = 10000
XLSX_MAGIC = b"PK"


def report_spec(key: str) -> dict:
    """取某张表的导出标识（`rep_id` / `dataset_id` / 项目参数 key / `reportName`）。"""
    try:
        return I8_REPORTS[key]
    except KeyError as exc:
        raise MustReportError(f"未登记的报表：{key}（已登记：{sorted(I8_REPORTS)}）") from exc


REQUIRED_SPEC_KEYS: tuple[str, ...] = ("rep_id", "dataset_id", "proj_param", "report_name")


def require_ready(key: str) -> dict:
    """**抓取前的可用性预检**：登记不全 ⇒ 当场拒（不猜取值、不发请求）。

    两条：
    ① 四项标识**必须都在**（`rep_id` / `dataset_id` / `proj_param` / `report_name`）——
       ⚠️ `report_name` 的值**可以是 `None`**（库存单据就必须传 null），但**键不能缺**：
       缺了键 = 还没决定"这张表要不要传表名"，与"确定传 null"是两件事。
    ② 带 `report_name_undetermined` 标记 ⇒ 显式报"未定稿"。
       （2026-09-16 收发生效过一次：`API-02` 的 `reportName` 当时只在 §9.8 写「需传表名」、
        没给取值 ⇒ 预检挡住，等素材包里取到 `收发结存表` 才放行。机制留着，将来新表同样会拦。）
    """
    spec = report_spec(key)
    missing = [k for k in REQUIRED_SPEC_KEYS if k not in spec]
    if missing:
        raise MustReportError(
            f"报表登记不全：{spec.get('label') or key}（{key}）缺 {' / '.join(missing)} ——"
            "《技术栈选型分析》§9.8 是取值的唯一主人；拿到取值前**不臆造、不发请求**。"
        )
    if spec.get("report_name_undetermined"):
        raise MustReportError(
            f"{spec.get('label') or key} 的 `reportName`（表名）**尚未定稿** ——"
            "请提供该表的导出名（登记到 `app/core/config.py::I8_REPORTS`）后再抓取；"
            "在此之前**不臆造取值**。"
        )
    return spec


def single_month(year_month: str) -> tuple[str, str, str, str]:
    """核算年月 → **起止年月四个独立值** `(a, b, aa, bb)`。

    ⚠️ 抓取**只允许单月**（§9.2）⇒ 结束年 / 月恒等于开始年 / 月；跨月 / 整年 / 全部**一律拒绝**。
    ⚠️ **月份必须落在 1–12** —— `core.period.parse_period` 只校验「`\\d{4}-\\d{2}` 这个形状」，
       不看数值（那是全站通用的宽松入口）；本函数是**上线的最后一道**，
       不能让 `2026-13` 这种形状合法、数值非法的值发到 i8 去。
    """
    ym = month_of(year_month)
    if ym is None:
        raise MustReportError(
            f"报表导出只允许「单月」核算年月（收到：「{year_month}」）—— 跨月 / 整年 / 全部不支持"
        )
    month = int(ym[5:7])
    if not 1 <= month <= 12:
        raise MustReportError(f"核算年月的月份必须在 1–12（收到：「{year_month}」）")
    return ym[:4], str(month), ym[:4], str(month)


def build_body(*, spec_key: str, year_month: str, proj_ids: str) -> dict:
    """构造导出请求体（**服务器按 `paramKey` 识别、顺序无关**）。"""
    spec = require_ready(spec_key)          # ⚠️ 登记不全（如 `reportName` 未定稿）⇒ 在这里就断掉
    y1, m1, y2, m2 = single_month(year_month)
    ds = spec["dataset_id"]

    def param(key: str, value, *, param_type: str, field_type, label: str) -> dict:
        return {"paramKey": key, "dataSetId": ds, "paramValueSource": "user_input",
                "operator": "in", "fieldType": field_type, "paramValue": value,
                "paramType": param_type, "label": label}

    return {
        "reportId": spec["rep_id"],
        "reportName": spec["report_name"],          # ⚠️ 库存单据 = None（**必须传 null**）
        "dataSetIds": [],
        "queryParams": [{
            "sheetKey": SHEET_KEY,
            "sheetQueryParams": [
                param("a", y1, param_type="1", field_type=None, label="开始核算年"),
                param("b", m1, param_type="1", field_type=None, label="开始核算月"),
                param("aa", y2, param_type="1", field_type=None, label="结束核算年"),
                param("bb", m2, param_type="1", field_type=None, label="结束核算月"),
                # 项目：paramType=0 / fieldType="0" / 值为 **id 列表**（本项目由**本地项目档案**提供 phid）
                param(spec["proj_param"], proj_ids, param_type="0", field_type="0", label="项目信息"),
            ],
        }],
        "querySetting": None,
        "exportType": EXPORT_TYPE,
        "filters": [],
    }


def check_bytes(content: bytes) -> bytes:
    """校验导出响应确实是 xlsx（**不静默**：异常时把前 200 字节带出来）。"""
    if len(content) < MIN_XLSX_BYTES or content[:2] != XLSX_MAGIC:
        head = content[:200].decode("utf-8", "ignore")
        raise ExternalServiceError(f"i8 报表导出响应异常（疑似未登录 / 参数被拒）：{head}")
    return content


def export(client, *, spec_key: str, year_month: str, proj_ids: str) -> bytes:
    """纯 HTTP 导出 → **xlsx 字节**。

    ⚠️ 用调用方给的 `I8Client`（它自带「401 重登**一次**」；**其余一律不重试** —— D9）。
    """
    spec = require_ready(spec_key)
    body = build_body(spec_key=spec_key, year_month=year_month, proj_ids=proj_ids)
    resp = client.request(
        "POST", I8_PATH_REPORT_EXPORT,
        content=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json;charset=UTF-8"},
    )
    if resp.status_code >= 400:
        raise ExternalServiceError(
            f"i8 报表导出返回 HTTP {resp.status_code}（{spec['label']}）：{resp.text[:200]}"
        )
    return check_bytes(resp.content)


__all__ = ["EXPORT_TYPE", "SHEET_KEY", "MIN_XLSX_BYTES", "XLSX_MAGIC", "REQUIRED_SPEC_KEYS",
           "report_spec", "require_ready", "single_month", "build_body", "check_bytes", "export"]
