"""`MOD-14` 规则与清单 · **集采项目剔除名单**的 JSON API（`TAIL-96`）。

⚠️ **页面在 M14、数据主人是集采域** —— 本文件全部存取走 `mod11_jc.repository`
   （与付款侧的「剔除规则」**完全同构**：那份也是"页面在 M14、数据主人在付款域"，见 `rules_api.py` 文件头）。
   依赖单向 `mod14_config → mod11_jc`，不成环。

⚠️ **与付款侧不共用**（用户 2026-09-25 裁定：两边各一份名单）⇒ 本接口**只碰集采那张表**。
⚠️ 语义：命中名单的**项目**，其合同在**抓取时就被剔除** —— 既不落库、也不再进「未落库」清单；
   但**必须留痕**（抓取回执 `ignored` ＋ 执行记录 `jc_ignored`）。
⚠️ 停用 = `active=False`（**保留在册**、可复活），⛔ 不做物理删（要与"这条为什么没了"可追溯）。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator

router = APIRouter(tags=["m14-jc-ignore"])


class JcIgnoreIn(BaseModel):
    name_full: str = ""
    reason: str = ""


class JcIgnoreActiveIn(BaseModel):
    active: bool = True


def _flash(ok: bool, message: str, **extra) -> dict:
    out = {"ok": bool(ok), "message": str(message or "")}
    out.update(extra)
    return out


@router.get("/api/m14/jc-ignore")
def api_jc_ignore_list() -> dict:
    """名单（含停用）—— 页面渲染用。"""
    from app.mod11_jc import repository as R
    with session_scope() as s:
        return {"ok": True, "items": R.list_ignored(s),
                "active": len(R.ignored_names(s))}


@router.post("/api/m14/jc-ignore")
def api_jc_ignore_add(req: JcIgnoreIn) -> dict:
    """加一条（⭐ **同名幂等**：已在册 ⇒ 直接返回它，⛔ 不重复插）。"""
    from app.mod11_jc import repository as R
    try:
        with session_scope() as s:
            out = R.add_ignored(s, name_full=req.name_full, reason=req.reason,
                                operator=current_operator())
            name = str(req.name_full or "").strip()
            if out.get("reactivated"):
                msg = f"「{name}」原本已停用 ⇒ **已复活**（它的合同从下次抓取起不再入库）。"
            elif out.get("reused"):
                msg = f"「{name}」已在名单里（⛔ 没有重复添加）。"
            else:
                msg = f"已加入剔除名单：「{name}」—— 它的合同从下次抓取起**不再写入**，也不再进「未写入」清单。"
            return _flash(True, msg, id=out.get("id"), reused=bool(out.get("reused")))
    except MustReportError as exc:
        return _flash(False, str(exc))


@router.put("/api/m14/jc-ignore/{ignore_id}")
def api_jc_ignore_active(ignore_id: int, req: JcIgnoreActiveIn) -> dict:
    """停用 / 启用（⛔ 不物理删 —— 停用后不再参与抓取过滤，但**留在册**可复活）。"""
    from app.mod11_jc import repository as R
    with session_scope() as s:
        n = R.set_ignored_active(s, ignore_id=int(ignore_id), active=bool(req.active))
        if not n:
            return _flash(False, "这条已经不在名单里了（可能刚被删）—— 请刷新后重试")
        return _flash(True, "已恢复参与抓取过滤。" if req.active else "已停用（记录留在册，可随时恢复）。",
                      active=bool(req.active))
