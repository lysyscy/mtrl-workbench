"""`MOD-12` 差异登记 · JSON API（M6 跨域第一片 · 2026-09-20 开工）。

⚠️ **本模块没有服务端渲染页**（同 `MOD-11`）：从第一天起就是 **JSON API ＋ 新壳**
   —— 页面形态（`V.m12` 切片）**一行不改**，只把数据源从演示数组换成这里。

⚠️ 写动作**恒 HTTP 200 ＋ `ok` 标志**（同 `m03` / `m07` / `m09` / `m14`）：
   必填缺失 / 金额非数字是 §5.8.3 的**可预期拒绝** ⇒ 那句中文必须**原样**给用户看，
   ⛔ 别变成一句 `HTTP 400`（那会逼壳写第二套错误分支）。
   ⚠️ 壳侧同款注意：`API.post` 系的契约是「**恒 200 —— 成败看 `ok`**」⇒ **只判 `ok`，⛔ 不靠 try/catch**。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterator

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod12_diff import repository as R
from app.mod12_diff.domain import OWNER_INV, STATUS_VERIFIED, validate

router = APIRouter(prefix="/api/m12", tags=["mod12"])


def get_session() -> Iterator[Session]:
    """短事务会话（经 `Depends` 暴露 ⇒ 自检可注入假会话、不连库）。"""
    from app.core.db import session_scope

    with session_scope() as session:
        yield session


DBSession = Depends(get_session)


def _row_out(r) -> dict:
    """一行 → API 载荷。

    ⚠️ 金额一律 **str**（Decimal 直接 JSON 化会变 float ⇒ 金额精度不可控；壳只拿它显示与求和）。
    ⚠️ `amount` 是**带符号**原值，**⛔ 不在这里取绝对值**（符号就是它的语义，§5.8.3）。
    """
    return {
        "id": int(r.id),
        "code": str(r.code or ""),
        "month": str(r.month or ""),
        "owner": str(r.owner or ""),
        "project_name": str(r.project_name or ""),
        "detail": str(r.detail or ""),
        "amount": str(r.amount if r.amount is not None else Decimal("0")),
        "status": str(r.status or ""),
        "remark": str(r.remark or ""),
        "created_by": str(r.created_by or ""),
    }


@router.get("/list")
def api_list(session: Session = DBSession) -> dict:
    """全部差异行（**全量**）—— 筛选由壳做（与 `m03`/`m07`/`m08` 同款，见 `repository.list_records`）。"""
    rows = R.list_records(session)
    return {"items": [_row_out(r) for r in rows], "owner_choices": [OWNER_INV]}


class DiffIn(BaseModel):
    """登记入参。⚠️ **刻意没有 `owner`** —— 归属恒为「库存单据」，不由调用方给（判据点 `001-10`）。"""

    month: str = ""
    project_name: str = ""
    detail: str = ""
    amount: str = Field(default="", description="带符号（+ 上调 / − 下调）；字符串以免精度丢失")
    status: str = ""
    remark: str = ""


@router.post("/create")
def api_create(body: DiffIn, session: Session = DBSession) -> dict:
    """登记一条 —— 必填缺一即拒（`001-03`）· 金额带符号且非数字拒（`001-04`）· 编号不撞（`001-02`）。"""
    try:
        data = validate(body.model_dump())
    except MustReportError as exc:
        return {"ok": False, "message": str(exc)}
    row = R.create_record(session, data, operator=current_operator())
    session.commit()
    return {"ok": True, "record": _row_out(row),
            "message": f"已登记差异 {row.code}（{row.month} · {row.detail}）—— 归属恒为「库存单据」"}


class IdIn(BaseModel):
    id: int


@router.post("/delete")
def api_delete(body: IdIn, session: Session = DBSession) -> dict:
    """删除**该行**（`001-06`）—— ⚠️ 本页是手工清单，删除 = **不再跟踪该笔**；
    ⛔ 它**不是**"把差异改掉了"（真正的修正动作在库存单据，§5.8.3）。"""
    row = R.get_record(session, body.id)
    if row is None:
        return {"ok": False, "message": f"找不到差异 {body.id}（可能已被删除，请刷新本页）"}
    code, detail = row.code, row.detail
    R.delete_record(session, row)
    session.commit()
    return {"ok": True, "message": f"已删除差异 {code}（{detail}）—— 本页是手工清单，删除即不再跟踪该笔"}


class StatusIn(BaseModel):
    id: int
    status: str = STATUS_VERIFIED


@router.post("/status")
def api_status(body: StatusIn, session: Session = DBSession) -> dict:
    """改状态（`待核对 → 已核对 / 差异保留`，§8.3）—— 手工标记。"""
    row = R.get_record(session, body.id)
    if row is None:
        return {"ok": False, "message": f"找不到差异 {body.id}（可能已被删除，请刷新本页）"}
    try:
        from app.mod12_diff.domain import STATUSES
        if body.status not in STATUSES:
            raise MustReportError(
                f"「状态」取值不合法：{body.status!r}（只允许 {' / '.join(STATUSES)}）")
    except MustReportError as exc:
        return {"ok": False, "message": str(exc)}
    R.set_status(session, row, body.status)
    session.commit()
    return {"ok": True, "record": _row_out(row), "message": f"{row.code} 已标记「{body.status}」"}


__all__ = ["router"]
