"""规则配置页的集采剔除条件与抓取结果接口。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod02_i8 import service as records
from app.mod11_jc import repository as R

router = APIRouter(prefix="/api/m14/jc-ignore", tags=["m14-jc-ignore"])


class JcIgnoreIn(BaseModel):
    kind: str = "project"
    name_full: str = ""
    contract_no: str = ""
    bill_name_keyword: str = ""
    reason: str = ""


@router.get("")
def api_jc_ignore_list() -> dict:
    with session_scope() as s:
        return {"ok": True, "items": R.list_ignored(s)}


@router.post("")
def api_jc_ignore_add(req: JcIgnoreIn) -> dict:
    try:
        with session_scope() as s:
            result = R.add_ignored(s, **req.model_dump(), operator=current_operator())
        return {"ok": True, **result, "message": "已有相同规则" if result["reused"] else "已新增剔除规则"}
    except MustReportError as exc:
        return {"ok": False, "message": str(exc)}


@router.delete("/{ignore_id}")
def api_jc_ignore_delete(ignore_id: int) -> dict:
    with session_scope() as s:
        R.delete_ignored(s, ignore_id=ignore_id)
    return {"ok": True, "message": "已删除剔除规则"}


@router.get("/receipt")
def api_jc_ignore_receipt(run_id: int | None = Query(None, ge=1, le=2147483647)) -> dict:
    with session_scope() as s:
        run = records.marked_fetch(s, R.JC_FETCH_MARK, run_id=run_id)
        return {"receipt": R.fetch_receipt(run) if run is not None else None}
