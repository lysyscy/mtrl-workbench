"""`MOD-03` 的**后端公共件**（会话 · 筛选解析 · API 列过滤口径）。

⭐ 2026-09-19（`§19` 批 4 · **S4③ 细分**）：本模块原先还塞着**只在页面上成立**的胶水
   （`QueryState` / `State` / `query_state` / `back` / `back_pay` / `LIST_URL` / `PAY_URL`）
   —— 它们已拆进**页面专用件** `notice_page_http.py`（随批 4 的删页一起消失 ✗）。
   本件此后**只留存活 API 要用的东西**：会话、筛选解析、API 必须剔除的页面专用列。
   ⛔ 别再往这里放页面专用的东西（那会让"删页"删不干净）。

⚠️ 本模块**不含任何判定**（判定一律在 `notice_actions` / `domain` 的纯函数里）。
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.period import default_period
from app.mod03_notice.list_data import PERIOD_DEFAULT_KEY
from app.mod03_notice.list_view import CATEGORY_ALL, NoticeFilters

# ⚠️ **只在页面上成立**的列（值是按钮 / 表单 HTML）—— API 必须剔除，否则就"吐 HTML"了
PAGE_ONLY_KEYS: tuple[str, ...] = ("actions", "_picked")


# --------------------------------------------------------------- 会话（可注入 ⇒ 离线自检）


def get_session() -> Iterator[Session]:
    """查询 / 动作共用的会话（**短事务**）—— 经 `Depends` 暴露 ⇒ 自检可注入假会话（不连库）。"""
    with session_scope() as session:
        yield session


DBSession = Depends(get_session)


# --------------------------------------------------------------- 筛选解析（列表 API 在用）


def notice_filters(period, project, category, approve_status, pay_status) -> NoticeFilters:
    """列表查询共用的筛选解析。

    ⚠️ 与其它页同一约定：**`period=None` ⇒ 用默认（北京时间当月）；`period=""` ⇒ 全部**。
    """
    return NoticeFilters(
        period=default_period(PERIOD_DEFAULT_KEY) if period is None else period,
        project_ids=tuple(project or ()),
        category=category or CATEGORY_ALL,
        approve_status=approve_status,
        pay_status=pay_status,
    )


__all__ = ["PAGE_ONLY_KEYS", "get_session", "DBSession", "notice_filters"]
