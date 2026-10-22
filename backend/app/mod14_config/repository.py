"""系统设置的读写（`MOD-14` · §7.8）—— 落库 ＋ **变更留痕**。

⚠️ 与「规则配置」有意不同：规则 = **硬删不留痕**（§9.4）；本页**必须留痕**（§7.8 ②）。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.app_settings import SETTING_I8_BASE_URL, SPEC_BY_KEY
from app.core.errors import DataConflictError
from app.mod14_config.models import AppSetting, AppSettingLog


def read_values(s: Session) -> dict[str, str]:
    """库里的**当前值**（只含存在的行；缺行 = 未设置）。"""
    return {r.key: (r.value or "") for r in s.execute(select(AppSetting)).scalars()}


def save(s: Session, *, values: dict[str, str], operator: str) -> list[dict]:
    """保存（**只处理调用方给出的 key**）→ 返回**变更清单**（无变化则不记留痕）。

    ⚠️ 只写传进来的 key —— 防止"保存打印机地址时顺带把别的项清空"（`ACC-CFG-SETUP-001/001-05`）。
    """
    changes: list[dict] = []
    now = datetime.now()
    for key, raw in values.items():
        if key not in SPEC_BY_KEY:
            continue
        new = (raw or "").strip()
        row = s.get(AppSetting, key)
        old = (row.value or "") if row is not None else ""
        if old == new:
            continue
        if row is None:
            s.add(AppSetting(key=key, value=new, updated_by=operator, updated_at=now))
        else:
            row.value = new
            row.updated_by = operator
            row.updated_at = now
        s.add(AppSettingLog(key=key, old_value=old, new_value=new,
                            operator=operator, at=now))
        changes.append({"key": key, "old": old, "new": new})
    s.flush()
    return changes



def address_state(s: Session) -> dict[str, str]:
    """Read value and revision from the same row, including the absent-row state."""
    row = s.get(AppSetting, SETTING_I8_BASE_URL)
    return {"stored": (row.value or "").strip() if row else "",
            "version": row.updated_at.isoformat(timespec="microseconds") if row else "missing"}


def save_settings(s: Session, *, values: dict[str, str], operator: str,
                  expected_version: str | None = None) -> list[dict]:
    """Fence late address writes; legacy callers also advance the address revision."""
    if SETTING_I8_BASE_URL not in values:
        return save(s, values=values, operator=operator)
    # Same transaction-lock convention as history; serialize even when the row is absent.
    s.connection().exec_driver_sql("SELECT pg_advisory_xact_lock(%s, %s)", (419, 0))
    current = address_state(s)
    if expected_version is not None and current["version"] != expected_version:
        raise DataConflictError("服务地址已变化，请重读配置后再保存；本次输入已保留。")
    row = s.get(AppSetting, SETTING_I8_BASE_URL)
    previous = row.updated_at if row else None
    changes = save(s, values=values, operator=operator)
    row = s.get(AppSetting, SETTING_I8_BASE_URL)
    if row is None:
        row = AppSetting(key=SETTING_I8_BASE_URL, value="")
        s.add(row)
    # A no-op still fences older requests, without manufacturing a value-change log.
    row.updated_at = max(datetime.now(), previous + timedelta(microseconds=1)) if previous else datetime.now()
    row.updated_by = operator
    s.flush()
    return changes


def recent_logs(s: Session, *, limit: int = 30) -> list[AppSettingLog]:
    """最近 N 条变更留痕（倒序）。"""
    return list(
        s.execute(
            select(AppSettingLog).order_by(AppSettingLog.id.desc()).limit(int(limit))
        ).scalars()
    )


__all__ = ["read_values", "save", "save_settings", "address_state", "recent_logs"]
