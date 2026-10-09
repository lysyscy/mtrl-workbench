"""MOD-14机械报表项目规则编辑；数据与匹配归过程资料域。"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod06_proc import service

router = APIRouter(tags=["mod14"])


class MatchRuleIn(BaseModel):
    warehouse: str
    aliases: list[str]


@router.get("/api/m14/mech-match")
def list_rules():
    with session_scope() as s:
        return {"ok": True, **service.mech_match_rules(s)}


@router.put("/api/m14/mech-match")
def save_rule(req: MatchRuleIn):
    try:
        with session_scope() as s:
            service.save_mech_match_rule(s, warehouse=req.warehouse, aliases=req.aliases)
        return {"ok": True, "message": "已保存机械报表项目匹配名称"}
    except MustReportError as exc:
        return {"ok": False, "message": str(exc)}
