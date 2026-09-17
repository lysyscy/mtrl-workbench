"""`MOD-03` 页面与动作的**公共件**（会话 · 当前查询 · PRG 回跳 · 筛选解析）。

为什么单独立一个模块：页面（`notice_router`）· 行级动作（`notice_actions_router`）·
批量付款与撤销（`notice_pay_router`）**都要用**这几件；
放在任一 router 里都会造成**循环 import** ⇒ 抽到中立件（谁都不依赖它、它不依赖任何 router）。

⚠️ 本模块**不含任何判定**（判定一律在 `notice_actions` / `domain` 的纯函数里）。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.parse import urlencode

from fastapi import Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.money import to_money
from app.core.period import default_period
from app.mod03_notice.list_view import CATEGORY_ALL, NoticeFilters
from app.mod03_notice.notice_page import PERIOD_DEFAULT_KEY
from app.mod03_notice.page import SORT_NONE

LIST_URL = "/m03/notices"
PAY_URL = "/m03/pay"

# ⚠️ **只在页面上成立**的列（值是按钮 / 表单 HTML）—— API 必须剔除，否则就"吐 HTML"了
PAGE_ONLY_KEYS: tuple[str, ...] = ("actions", "_picked")


# --------------------------------------------------------------- 会话（可注入 ⇒ 离线自检）


def get_session() -> Iterator[Session]:
    """页面 / 动作共用的会话（**短事务**）—— 经 `Depends` 暴露 ⇒ 自检可注入假会话（不连库）。"""
    with session_scope() as session:
        yield session


DBSession = Depends(get_session)


# --------------------------------------------------------------- 当前查询（PRG 回跳用）


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


def notice_filters(period, project, category, approve_status, pay_status) -> NoticeFilters:
    """页面 / API 共用的筛选解析。

    ⚠️ 与其它页同一约定：**`period=None` ⇒ 用默认（北京时间当月）；`period=""` ⇒ 全部**。
    """
    return NoticeFilters(
        period=default_period(PERIOD_DEFAULT_KEY) if period is None else period,
        project_ids=tuple(project or ()),
        category=category or CATEGORY_ALL,
        approve_status=approve_status,
        pay_status=pay_status,
    )


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


# --------------------------------------------------------------- 小工具


def parse_amount(text):
    """把表单里的金额文本解析为 `Decimal`（空 ⇒ `None` = 未手改、取「本次应付」）。"""
    raw = str(text or "").strip().replace(",", "")
    return to_money(raw) if raw else None


def parse_ids(ids) -> list[int]:
    """`"1,2,3"` 或 `[1,2,3]` → `[1,2,3]`（逗号分隔的 id 串）。"""
    if isinstance(ids, (list, tuple)):
        return [int(i) for i in ids if str(i).strip().isdigit()]
    return [int(x) for x in str(ids or "").replace(" ", "").split(",") if x.isdigit()]


def plan_methods_for_pay(session: Session) -> dict:
    """`单据号 -> 付款计划的付款方式`（§4.4.2 默认值来源）—— 复用付款窗口的同一个查询。"""
    from app.mod03_notice.notice_pay import _plan_methods

    return _plan_methods(session)


__all__ = [
    "LIST_URL", "PAY_URL", "PAGE_ONLY_KEYS",
    "get_session", "DBSession", "QueryState", "query_state", "State",
    "notice_filters", "back", "back_pay", "parse_amount", "parse_ids", "plan_methods_for_pay",
]
