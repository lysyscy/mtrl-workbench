"""`MOD-08` **库存单据明细 · 手动 Excel 导入** —— 前端壳用的 **JSON API**（§3.6 的降级通道）。

> **为什么需要它**：`API-03` 接口不可用时（§3.6）**必须有手动通道**，否则「i8 一坏就断粮」。
> ⚠️ 与抓取**同一条管线**：上传的就是 i8 导出的那个 `.xlsx` ⇒ 同一个解析器
>   （`importer.parse_rows`：按表头认列 · 缺关键列即报错）＋ 同一个幂等落库（`upsert_details`）。
>   ⇒ 本层**不另写判定**，只做「选文件 → 预览 → 确认」的编排。
⚠️ ⛔ **本页没有「整批回滚」**：库存单据是**幂等刷新**（键 = 核算年月 ＋ 仓库 ＋ 单据编号 ＋ 序号）
   ⇒ 「导错了」= **改好文件再导一次**（同月同仓库会被更新而不是新增，§9.5）。
   ⛔ 这与付款域 / 过程资料历史段的「批次 ＋ 整批回滚」**不是同一形态** —— 那两处是**只增不改的旁路账**。
⚠️ ⛔ **本页不写执行记录**：`RunRecord` 的 `run_type` 只登记 `fetch` / `print` / `export_pdf`；
   手动导入不是抓取 ⇒ 看板的「本月尚未抓取」在手动补数后**仍应提示**（那是事实）。
⚠️ **为什么有这个文件**（`TAIL-27` · `§19` 四个暂留件收口）：本页原先只有服务端渲染页
   （`import_view.py` ＋ `import_router.py` 的三条 PRG）⇒ 壳里**零入口**，那页删不得。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, UploadFile

from app.core import preview_store
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.money import sum_money
from app.mod08_inv import importer
from app.mod08_inv.fetch_service import group_by_scope
from app.mod08_inv.repository import upsert_details

router = APIRouter(tags=["mod08-import-api"])


def _payload(rows: list[dict]) -> dict:
    """解析结果 → 可暂存的纯数据（金额列转串；**不含文件本体、不含密钥**）。"""
    out: list[dict] = []
    for row in rows:
        out.append({k: (f"{v}" if k in importer.NUMERIC_FIELDS else v) for k, v in row.items()})
    return {"rows": out}


def _rows_of(payload: dict) -> list[dict]:
    """暂存结果 → 规范行（金额列转回 `Decimal`；**不重新解析文件**）。"""
    out: list[dict] = []
    for row in payload.get("rows") or []:
        out.append({k: (Decimal(str(v)) if k in importer.NUMERIC_FIELDS else v)
                    for k, v in row.items()})
    if not out:
        raise MustReportError("预览结果里没有可写入的行 —— 请重新上传文件解析一次。")
    return out


def _groups_of(rows: list[dict]) -> list[dict]:
    """按「核算年月 ＋ 仓库」分组 → 预览用的小表（**与落库范围同一把尺**）。"""
    out: list[dict] = []
    for (ym, warehouse), group in sorted(group_by_scope(rows).items()):
        out.append({"ym": ym, "warehouse": warehouse, "rows": len(group),
                    "amount": f'{sum_money([r.get("amount") for r in group]):.2f}'})
    return out


def _apply(s, rows: list[dict]) -> dict:
    """分组 ＋ **幂等刷新**落库 → 逐范围统计（与抓取**同一个出口**）。"""
    groups: list[dict] = []
    totals = {"inserted": 0, "updated": 0, "deleted": 0, "kept_with_adjustment": 0}
    for (ym, warehouse), group in sorted(group_by_scope(rows).items()):
        part = upsert_details(s, ym=ym, warehouse=warehouse, rows=group)
        for key in totals:
            totals[key] += part[key]
        groups.append({"ym": ym, "warehouse": warehouse, "rows": len(group), **part})
    return {"groups": groups, "totals": totals}


@router.get("/api/m08/import/meta")
def api_meta() -> dict:
    """文件要求（必有列 / 刻意不采的源列）—— 壳侧「① 文件要求」那块的**唯一数据源**。"""
    return {"ok": True, "required_headers": list(importer.REQUIRED_HEADERS),
            "ignored_headers": list(importer.IGNORED_HEADERS)}


@router.post("/api/m08/import/parse")
async def api_parse(file: UploadFile = File(...)) -> dict:
    """解析上传的 `.xlsx` → **预览**（⚠️ **一个字节都不写库**）。"""
    try:
        rows = importer.parse_rows(await file.read())
        token = preview_store.save(_payload(rows))
        return {"ok": True, "token": token,
                "preview": {"rows": len(rows), "groups": _groups_of(rows)}}
    except MustReportError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:                                # noqa: BLE001
        return {"ok": False, "message": f"解析失败：{type(exc).__name__}: {exc}"}


@router.post("/api/m08/import/confirm")
def api_confirm(body: dict | None = None) -> dict:
    """凭 token 取回解析结果 → **幂等刷新落库** → 给逐范围统计。"""
    try:
        rows = _rows_of(preview_store.load(str((body or {}).get("token") or "")))
        with session_scope() as s:
            result = _apply(s, rows)
        t = result["totals"]
        return {
            "ok": True, "result": result,
            "message": f"已导入 {len(rows)} 行（{len(result['groups'])} 个「核算年月 ＋ 仓库」范围）："
                       f"新增 {t['inserted']} · 更新 {t['updated']} · 删除 {t['deleted']} · "
                       f"因有调整单而保留 {t['kept_with_adjustment']}",
        }
    except MustReportError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:                                # noqa: BLE001
        return {"ok": False, "message": f"导入失败：{type(exc).__name__}: {exc}"}


__all__ = ["router", "_payload", "_rows_of", "_groups_of", "_apply"]
