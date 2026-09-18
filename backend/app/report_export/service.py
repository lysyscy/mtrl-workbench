"""`MOD-07` / `MOD-08` 成品文件写出 · **中立编排**（`TAIL-04`）。

## 职责边界（三条，都别越）

1. **取数**：从**库里**读明细行（生产环境的数据主人在库）—— ⛔ 不读 i8 原始导出件
   （因此**历史月份**与**手动导入**来的月份同样导得出）。
2. **调用**：转交 `setl_export.build_zip` / `kcdj_export.build_xlsx`（实现逐字来自交付面素材包）。
3. **落点**：产物写到 `artifacts/exports/<报表>/<期间>/` —— 路径**唯一出口** = `EXPORT_ROOT`。

⚠️ **判定一律在实现层与域内核**：金额对平、仓库集合、透视规则、剔合计**都不在本层**，
   本层只做「取数 → 转交 → 报路径」。
⚠️ 对账不过 / 数据为空 / 模板缺失 ⇒ **实现层显式抛错**（`MustReportError`），本层**不吞**。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.core.errors import MustReportError
from app.mod07_setl.domain import period_label       # ⭐ 期间标签的**唯一主人**在 m07 域内核
from app.mod07_setl.models import SetlDetail
from app.report_export import setl_export

#: 成品文件的落点根（**唯一出口**；⛔ 别在 router / service 里各拼一次路径）
EXPORT_ROOT: Path = PROJECT_ROOT / "artifacts" / "exports"


def setl_rows(session: Session, period: str) -> list[SetlDetail]:
    """该核算月的收发结存明细（固定排序 ⇒ 同样的数据**产出可复现**）。

    ⚠️ 排序 = 「仓库 → 资源编码 → id」：仓库分组决定分仓库文件的边界，
       资源编码决定总表内行序（与 i8 导出原序一致）。
    """
    stmt = (
        select(SetlDetail)
        .where(SetlDetail.ym == period)
        .order_by(SetlDetail.warehouse_name, SetlDetail.resource_code, SetlDetail.id)
    )
    return list(session.execute(stmt).scalars().all())


def setl_count(session: Session, period: str) -> int:
    """该月明细行数（**只回数、不取行**，供壳侧"能不能导出"的预判用）。"""
    return int(
        session.execute(
            select(func.count()).select_from(SetlDetail).where(SetlDetail.ym == period)
        ).scalar()
        or 0
    )


def export_settlement(session: Session, period: str) -> Path:
    """导出一期**收发结存成品 zip** → 返回 zip 的绝对路径。

    ⚠️ 期间格式错误 ⇒ **显式报错**（⛔ 不猜一个默认月，那会导出成错月份、且看着正常）。
    """
    ym = str(period or "").strip()
    if len(ym) != 7 or ym[4] != "-" or not (ym[:4].isdigit() and ym[5:].isdigit()):
        raise MustReportError(f"核算年月格式不对：`{ym}`（要 `YYYY-MM`，例 `2026-09`）")
    rows = setl_rows(session, ym)
    out_dir = EXPORT_ROOT / "收发结存" / ym
    return Path(setl_export.build_zip(rows, out_dir, period_label(ym)))


__all__ = ["EXPORT_ROOT", "period_label", "setl_rows", "setl_count", "export_settlement"]
