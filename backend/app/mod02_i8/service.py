"""执行记录的包间读写出口；标记解释留在业务域。"""
from __future__ import annotations


def recent_records(session, *, run_type: str, limit: int):
    from app.mod02_i8 import repository
    return repository.recent_records(session, run_type=run_type, limit=limit)


def save_run_record(session, *, started_at, **values):
    """包间写出口：一次抓取的结果与失败独立留底。"""
    from app.mod02_i8 import repository
    return repository.save_run_record(session, started_at=started_at, **values)
