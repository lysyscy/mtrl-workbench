"""`MOD-14` 规则配置 · **剔除规则的 JSON API**（前端壳接线 · `TAIL-40`）。

⚠️ **页面的 M14、数据的主人是付款域** —— 本文件的全部存取都走
   `mod03_notice.rules_repository`（§4.2.2 原文即「剔除规则本身属付款域」）；
   依赖**单向** `mod14_config → mod03_notice`，不成环（详见该模块头）。

⚠️ 本层**零判定**：规则的合法性一律走 `classify.validate_rules`（唯一出口，经仓储转发）；
   本层只做「请求 → 仓储 → 中文回执」。

⚠️ 写动作**恒 HTTP 200 ＋ `ok` 标志**（同 `m03` / `m07` / `m09`）：规则不合法是 §4.2.2 的
   **可预期拒绝**（例如「不得按收款单位配置」）⇒ 那句中文必须原样给用户看，别变成一句 `HTTP 400`。

⚠️ **改规则不重算历史**：已产生的剔除标记（`exclude_source=rule`）不受影响、也不重算（§4.2.2）
   ⇒ 本层**不做任何重算**，回执里也要讲清这一句。

⚠️ **只做剔除规则**：分类规则（§4.2.3）是**业务口径 ⇒ 只读**；小微识别关键词**主人在项目行**（`MOD-01`）
   ⇒ 本层不给它们任何写入口（`ACC-CFG-RULE-001/001-02 · 001-05`）。
"""

from __future__ import annotations

from fastapi import APIRouter, Path
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod03_notice import rules_repository as RR

router = APIRouter(tags=["mod14"])

NO_RECOMPUTE_NOTE = "（⚠️ 本次改动**只影响后续抓取**；已产生的剔除标记**不重算**，必要时再抓一次。）"


# ============================================================ 读


@router.get("/api/m14/rules")
def api_rules() -> dict:
    """当前**生效规则集** ＋ 可选类别清单。

    ⚠️ 本端点会做一次**幂等初始化**（库空 ⇒ 把出厂默认落库）：否则首次打开时那几行**没有 `id`**、
       在页面上**改不了也删不掉**。⚠️ **抓取管线不调它** ⇒ 抓取行为与接线前逐字一致。
    """
    with session_scope() as s:
        RR.ensure_seeded(s)
        data = RR.effective_payload(s)
    return {"ok": True, **data}


# ============================================================ 写（增 / 删 / 改 · 硬删不留痕）


class RuleIn(BaseModel):
    """一条规则（`kind` ∈ §4.2.2 的**四类**；`values` = 命中值原文，`｜` 或 `|` 分隔都认）。"""

    kind: str = ""
    values: str = ""
    meaning: str = ""


def _flash(kind: str, message: str) -> dict:
    return {"ok": kind == "ok", "kind": kind, "message": message}


def _label(row) -> str:
    from app.mod03_notice import classify

    return classify.KIND_LABELS.get(row.kind, row.kind)


@router.post("/api/m14/rules")
def api_rule_add(req: RuleIn) -> dict:
    """**新增**一条剔除规则（同 `kind` 允许多行 —— 与原型一致）。"""
    try:
        with session_scope() as s:
            RR.ensure_seeded(s)                    # 首次进入就编辑 ⇒ 先把出厂默认落库，行序才对得上
            row = RR.add_row(s, kind=req.kind, values=req.values, meaning=req.meaning)
            msg = f"已新增剔除规则「{_label(row)}」（{len(RR.split_values(row.values))} 个命中值）。" + NO_RECOMPUTE_NOTE
            return _flash("ok", msg)
    except MustReportError as exc:
        return _flash("err", str(exc))


@router.put("/api/m14/rules/{rule_id}")
def api_rule_update(req: RuleIn, rule_id: int = Path(..., ge=1)) -> dict:
    """**改**一条剔除规则（`kind` / 命中值 / 业务含义都能改）。"""
    try:
        with session_scope() as s:
            row = RR.get_row(s, rule_id)
            if row is None:
                return _flash("err", "这条规则已经不在了（可能刚被删）—— 请刷新后重试")
            RR.update_row(s, row, kind=req.kind, values=req.values, meaning=req.meaning)
            msg = f"已更新剔除规则「{_label(row)}」（{len(RR.split_values(row.values))} 个命中值）。" + NO_RECOMPUTE_NOTE
            return _flash("ok", msg)
    except MustReportError as exc:
        return _flash("err", str(exc))


@router.delete("/api/m14/rules/{rule_id}")
def api_rule_delete(rule_id: int = Path(..., ge=1)) -> dict:
    """**删**一条剔除规则 —— **硬删、不留痕**（§9.4：配置类数据）。"""
    with session_scope() as s:
        row = RR.get_row(s, rule_id)
        if row is None:
            return _flash("err", "这条规则已经不在了（可能刚被删）—— 请刷新后重试")
        label = _label(row)
        RR.delete_row(s, row)
        left = len(RR.all_rows(s))
        tail = ("⚠️ 规则已**全部删空** ⇒ 系统将**回落到出厂默认（§4.2.2）**。"
                if not left else "")
        return _flash("ok", f"已删除剔除规则「{label}」（配置类数据 = 硬删、不留痕，§9.4）。"
                            + tail + NO_RECOMPUTE_NOTE)


__all__ = ["router"]
