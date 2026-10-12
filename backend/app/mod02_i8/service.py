"""执行记录的包间读出口；四个业务域共用，标记解释留在业务域。"""
from __future__ import annotations


def recent_records(session, *, run_type: str, limit: int):
    from app.mod02_i8 import repository
    return repository.recent_records(session, run_type=run_type, limit=limit)
