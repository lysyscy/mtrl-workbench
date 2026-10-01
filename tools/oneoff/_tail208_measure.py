"""`TAIL-208` **量**：m04（付款计划）各月条数 —— 验 ①（`0 vs 107`）③（筛回当月）是不是同一个"月初"根因。

⚠️ 只读（⛔ 不写一行）。
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import text as T  # noqa: E402

from app.core.db import session_scope  # noqa: E402

with session_scope() as s:
    tabs = [r[0] for r in s.execute(T(
        "select table_name from information_schema.tables where table_schema='public' order by 1")).all()]
    cand = [t for t in tabs if "plan" in t.lower()]
    print("含 plan 的表 =", cand)
    for t in cand:
        cols = [r[0] for r in s.execute(T(
            "select column_name from information_schema.columns where table_name=:t"), {"t": t}).all()]
        n = s.execute(T('select count(*) from "' + t + '"')).scalar()
        print(f"\n[{t}] 行数={n}\n  列 = {cols}")
        for c in cols:
            if not any(k in c.lower() for k in ("month", "ym", "date", "time")):
                continue
            sql = ('select ' + c + '::text as m, count(*) as n from "' + t
                   + '" group by 1 order by 1')
            try:
                rows = s.execute(T(sql)).all()
                tail = [(r[0], r[1]) for r in rows][-8:]
                print(f"  按 `{c}` 分组（末 8 个月）= {tail}")
            except Exception as e:  # noqa: BLE001
                s.rollback()
                print(f"  按 `{c}` 分组：失败 {type(e).__name__}: {str(e)[:80]}")

print("\n今天 =", dt.date.today(), "（⭐ 月初第一天？⇒", dt.date.today().day == 1, "）")
