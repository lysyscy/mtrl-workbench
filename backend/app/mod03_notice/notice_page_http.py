"""`MOD-03` **页面专用**的 HTTP 胶水（当前查询 · PRG 回跳 · 旧页地址常量）。

⭐ 2026-09-19（`§19` 批 4 · **S4③ 细分**）：从 `notice_http.py` 拆出来的一层 ——
   这几件**只在「服务端渲染页 ＋ 表单向 PRG」**这个形态里成立：

   - `QueryState` / `query_state` / `State` —— 把**当前筛选**从请求里取出来（提交时带回，回跳停在原查询）；
   - `back` / `back_pay` —— 303 回跳（防刷新重放提交）；
   - `LIST_URL` / `PAY_URL` —— 旧页地址（新壳没有这两个页面）。

   新壳（`app/web/`）全部走 **JSON API**（`/api/m03/*`）⇒ 上面这些**一个都不用** ⇒
   本件**随批 4 的删页一起消失** ✗。⛔ 别再往本件加东西（它没有未来）。

⚠️ 判定一律在 `notice_actions` / `domain` 的纯函数里 —— 本件**不含任何判定**。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlencode

from fastapi import Depends, Query
from fastapi.responses import RedirectResponse

from app.mod03_notice.page import SORT_NONE

LIST_URL = "/m03/notices"
PAY_URL = "/m03/pay"


@dataclass
class QueryState:
    """PRG 回跳所需的**当前查询**（与页面 GET 同名同义）。"""

    period: str = ""
    project: list[str] = field(default_factory=list)
    category: str = ""
    approve_status: str = ""
    pay_status: str = ""
    sort: str = ""
    dir: int = SORT_NONE


def query_state(
    period: str = Query(""),
    project: list[str] = Query(default=[]),
    category: str = Query(""),
    approve_status: str = Query(""),
    pay_status: str = Query(""),
    sort: str = Query(""),
    dir: int = Query(SORT_NONE),
) -> QueryState:
    """把**当前筛选**从请求里取出来（动作提交时会带回，回跳后停在原查询）。"""
    return QueryState(
        period=period, project=list(project or ()), category=category,
        approve_status=approve_status, pay_status=pay_status, sort=sort, dir=int(dir),
    )


State = Depends(query_state)


def back(st: QueryState, msg: str, *, kind: str = "ok", draft: str = "") -> RedirectResponse:
    """303 回**付款通知书列表页**的原查询（PRG）—— 防止刷新重放提交。"""
    q = {
        "period": st.period, "project": list(st.project or ()), "category": st.category,
        "approve_status": st.approve_status, "pay_status": st.pay_status,
        "sort": st.sort, "dir": int(st.dir), "msg": msg, "msgkind": kind,
    }
    if draft:
        q["draft"] = draft
    return RedirectResponse(f"{LIST_URL}?{urlencode(q, doseq=True)}", status_code=303)


def back_pay(ids, msg: str, *, kind: str = "ok") -> RedirectResponse:
    """回**批量付款窗口**（带消息）；提交成功（`kind=ok` 且无 ids）时回**列表页**。"""
    target = LIST_URL if kind == "ok" and not ids else PAY_URL
    q = {"msg": msg, "msgkind": kind}
    if ids:
        q["ids"] = list(ids)
    return RedirectResponse(f"{target}?{urlencode(q, doseq=True)}", status_code=303)


__all__ = ["LIST_URL", "PAY_URL", "QueryState", "query_state", "State", "back", "back_pay"]
