"""系统设置的读写（`MOD-14` · §7.8）—— 落库 ＋ **变更留痕**。

⚠️ 与「规则配置」有意不同：规则 = **硬删不留痕**（§9.4）；本页**必须留痕**（§7.8 ②）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.app_settings import SPEC_BY_KEY
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


def recent_logs(s: Session, *, limit: int = 30) -> list[AppSettingLog]:
    """最近 N 条变更留痕（倒序）。"""
    return list(
        s.execute(
            select(AppSettingLog).order_by(AppSettingLog.id.desc()).limit(int(limit))
        ).scalars()
    )


__all__ = ["read_values", "save", "recent_logs"]
