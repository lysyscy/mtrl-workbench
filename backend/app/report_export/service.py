"""`MOD-07` / `MOD-08` 成品文件写出 · **中立编排**（`TAIL-04`）。

## 职责边界（三条，都别越）

1. **取数**：**两条报表的来源不同**（各自回它的主人）——
   · `MOD-07` 收发结存：从**库里**读明细行（`setl_detail`）⇒ **历史月份** / 手动导入来的月份
     同样导得出，**不读 i8 原始导出件**；
   · `MOD-08` 库存单据明细表：**HTTP 现导** i8（`API-03`）拿源文件**字节** →
     直接喂实现层出成品（照素材包 `export_runner.run_once()` 的 kcdj 分支）。
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
from app.report_export import kcdj_export, setl_export

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


def _require_ym(period: str) -> str:
    """核算年月 → 干净的 `YYYY-MM`；格式不对 ⇒ **显式报错**（⛔ 不猜一个默认月）。

    ⚠️ 两条导出链路**共用这一份校验**（各写一份必然走形）。
    """
    ym = str(period or "").strip()
    if len(ym) != 7 or ym[4] != "-" or not (ym[:4].isdigit() and ym[5:].isdigit()):
        raise MustReportError(f"核算年月格式不对：`{ym}`（要 `YYYY-MM`，例 `2026-09`）")
    return ym


def export_settlement(session: Session, period: str) -> Path:
    """导出一期**收发结存成品 zip** → 返回 zip 的绝对路径。

    ⚠️ 期间格式错误 ⇒ **显式报错**（⛔ 不猜一个默认月，那会导出成错月份、且看着正常）。
    """
    ym = _require_ym(period)
    rows = setl_rows(session, ym)
    out_dir = EXPORT_ROOT / "收发结存" / ym
    return Path(setl_export.build_zip(rows, out_dir, period_label(ym)))


def _fetch_inventory_bytes(session: Session, ym: str, *, allow_kick: bool = False) -> bytes:
    """HTTP **现导**一期库存单据明细（`API-03`）→ xlsx 字节。

    - phid 列表**唯一出口** = `mod01_projects.repository.export_phids`（**保序去重**）。
    - 与抓取**共用同一把表级串行锁**（`inv_detail`，D9）—— 防两人同时导出 ⇒ 双份顶号。
    - ⚠️ `allow_kick` **默认 `False`**（D9：强踢必须调用方显式授权）：cookie 有效 / **命中磁盘缓存**时
      **不重登、不顶号**；仅会话失效时按既有策略**重登一次**。
    """
    from app.mod01_projects.repository import export_phids
    from app.mod02_i8 import report_export
    from app.mod02_i8.client import I8Client, serialize_fetch
    from app.mod08_inv.fetch_service import TABLE as INV_TABLE

    ids = export_phids(session)
    with serialize_fetch(INV_TABLE):
        client = I8Client(allow_kick=allow_kick)
        try:
            return report_export.export(client, spec_key="inv", year_month=ym, proj_ids=ids)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()


def export_inventory(session: Session, period: str, *, export_bytes=None,
                     allow_kick: bool = False) -> Path:
    """导出一期**库存单据明细表成品 xlsx**（含两张真透视）→ 返回成品绝对路径。

    - **src 来源 = HTTP 现导**（`mod02_i8.report_export.export`，`spec_key="inv"`）
      —— 照素材包 `app/export_runner.py::run_once()` 的 kcdj 分支。
    - **落点** = `EXPORT_ROOT / "库存单据明细表" / <期间标签>`；成品名 = `库存单据明细表_<期间标签>.xlsx`
      （命名规则照素材包不变）；期间标签**唯一出口** = `period_label`（`2026-09` → `2026年9月`）。
    - ⚠️ 失败（模板缺失/损坏 · 该月无数据 · **缓存级对账不过**）⇒ **实现层显式抛 `MustReportError`**，
      本层**不吞**（由端点转成「200 ＋ `ok:false` ＋ 中文原因」）。

    `export_bytes` 仅**测试注入**用（离线驱动成品生成、**不连 i8**）；缺省走真机现导。
    `allow_kick` 透传给 `I8Client`（**默认 `False`** —— D9：强踢只能由界面二次确认后显式授权）。
    """
    ym = _require_ym(period)
    content = (export_bytes() if export_bytes is not None
               else _fetch_inventory_bytes(session, ym, allow_kick=allow_kick))
    out_dir = EXPORT_ROOT / "库存单据明细表" / period_label(ym)
    return Path(kcdj_export.build_xlsx(content, out_dir))


__all__ = ["EXPORT_ROOT", "period_label", "setl_rows", "setl_count", "export_settlement",
           "export_inventory"]
