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


def export_extract(session: Session, period: str, status: str = "") -> Path:
    """导出一份**焊材 / 气体提取**成品 xlsx（`TAIL-04` **路径① = 模板填充**）→ 成品绝对路径。

    - 取数 = `mod07_setl.service.build_extract_export`（**行集合与页面同一份口径**）；
    - 摆位 / 落点 = `weldgas_export.build_xlsx`（模板闸门 ＋ 显示区对账都在里面）；
    - ⚠️ 本层只做「筛选状态 → 取数 → 转交 → 报路径」，⛔ 不在这里算金额、不在这里拼文件名。
    """
    from app.mod07_setl import service as M7
    from app.report_export import weldgas_export

    raw: dict = {"status": str(status or "")}
    if period is not None:                       # ⚠️「不带 period」与「显式传空」是两件事（同页面）
        raw["ext_period"] = str(period)
    plan = M7.build_extract_export(session, M7.parse_extract_state(raw))
    return Path(weldgas_export.build_xlsx(plan["grids"], EXPORT_ROOT, plan["report_ym"]))


def export_ledger(session: Session, projects, ym: str = "") -> Path:
    """导出**台账成品**（`TAIL-04` 路径① **片 2＋3**）—— 每个项目**一本工作簿 / 三个 sheet**
    （`辅材` / `机械` / `特殊费用月报表`）；≥2 个项目 ⇒ 打一个 zip ⇒ 返回成品（或 zip）的绝对路径。

    - 取数：台账两侧 = `mod05_flow.service.build_ledger`（**行集合与页面同一份口径**）；
      「特殊费用月报表」= `mod09_fee.service.build_page_data`（1 自动项 ＋ N 手填项）。
    - ⚠️ **全本只有一个报告月**（`ym`）：台账的**止月**与「特殊费用月报表」的**月份列**必须是同一个月
      —— 否则一本工作簿里两张表说的不是同一期间（用户在同一个文件里看到两个期间，必然读错）。
    - ⚠️ **三个 sheet 一次做齐**：只填两个就交付，第三张会把模板里**别的项目**的示例数据留给用户
      （`TAIL-43` 同族）⇒ 本函数**不提供"只导两个 sheet"的入口**。
    - 项目**必须在档案里**（拿不到展示名 ⇒ **显式拒做**，⛔ 不猜、不臆造归属）。
    """
    from app.mod05_flow import service as M5
    from app.mod09_fee import domain as M9D
    from app.mod09_fee import repository as M9R
    from app.mod09_fee import service as M9
    from app.report_export import ledger_export

    keys = [str(k) for k in (projects or ()) if str(k or "").strip()]
    if not keys:
        raise MustReportError("导出台账：**一个项目都没选** —— 请先在展开区里勾选要导出的项目。")
    report_ym = str(ym or "").strip() or M9D.default_ym()
    display_of = {c.key: c.display for c in M9.candidates(session)}
    out_dir = EXPORT_ROOT / ledger_export.FILE_SUFFIX / period_label(report_ym)
    made: list[str] = []
    for key in keys:
        pj = M9R.project_by_key(session, key)
        if pj is None:
            raise MustReportError(
                f"导出台账：项目「{key}」**不在档案里** ⇒ 先建档再导（⛔ 不猜项目名、不臆造归属）。")
        display = display_of.get(key) or key
        sides = {s["category"]: s
                 for s in M5.build_ledger(session, project_id=pj.id, end_ym=report_ym)["sides"]}
        fee = M9.build_page_data(session, {"ym": report_ym, "pj": key})
        sections = {cat: sides.get(cat) for cat in ledger_export.SHEET_OF_CATEGORY}
        sections[ledger_export.SHEET_FEE] = fee
        made.append(ledger_export.build_xlsx(sections, out_dir, display=display, ym=report_ym))
    if len(made) == 1:
        return Path(made[0])
    return Path(ledger_export.build_zip(
        made, out_dir, "%s_%s.zip" % (ledger_export.FILE_SUFFIX, period_label(report_ym))))


def export_proc(session: Session, projects, tab, ym: str = "") -> Path:
    """导出**过程资料成品**（`TAIL-04` 路径① **片 4a**）—— **每个项目一本工作簿**；
    选 ≥2 个项目 ⇒ 打成一个 zip ⇒ 返回成品（或 zip）的绝对路径。

    - **取数跟随当前所显示的那张表**（`ACC-RPT-EXP-001/001-04`）：表①原始 ⇒ `adjusted=False`；
      表②调整后 ⇒ `adjusted=True`；⭐ **差异表** ⇒ **逐格差额（调整后 − 原始）**
      —— 用户 **2026-09-18 裁定**：「差异表和汇总表的**形态完全相同**，就是数据不一样，
      最多是导出的文件名不一样」⇒ 三张表**共用同一张模板 / 同一套列映射与尾块**，
      只在**取数**（`domain.difference_rows`）与**文件名**上不同。
    - 每个项目各自的**截止核算月**（分界 = 截止核算月，§5.2.5）—— ⛔ 不共用一个。
    - ⭐ **标题与文件名一律用「展示名」**（用户 2026-09-18 裁）：取不到（该项目还没建档）⇒ **拒做**
      （⛔ 不拿仓库名冒充展示名）；页面清单预览同源（`mod06_proc.service.displays_by_key`）。
    - 文件名 / zip 名**唯一出口** = `mod06_proc.domain.export_file_name` / `export_manifest`
      （页面清单预览用的就是它 ⇒ 预览与真实产物同名）。
    - `ym` = 文件名里的**当前年月**（§7.1「文件名含日期」；⚠️ 本页**不按年月筛数据** —— 表体是
      逐月全量，`ym` 只进文件名）。
    """
    from app.core.timing import today_cn, ym_of
    from app.mod06_proc import domain as D
    from app.mod06_proc import repository as R
    from app.mod06_proc import service as M6
    from app.report_export import process_export

    keys = [str(k) for k in (projects or ()) if str(k or "").strip()]
    if not keys:
        raise MustReportError("导出过程资料：**一个项目都没选** —— 请先在展开区里勾选要导出的项目。")
    tab_no = D.tab_of(tab)
    report_ym = str(ym or "").strip() or ym_of(today_cn())
    inv_rows = R.load_inv_rows(session)
    mech_rows = R.load_mech(session)
    history_rows = R.load_history(session)
    known = M6.projects_of(inv_rows, history_rows)      # ⭐ 候选**唯一出口**（⛔ 不各写一份）
    displays = M6.displays_by_key(session)              # ⭐ 键→展示名（标题与文件名都用它）
    out_dir = EXPORT_ROOT / process_export.FILE_SUFFIX / period_label(report_ym)
    made: list[str] = []
    for key in keys:
        if key not in known:
            raise MustReportError(
                f"导出过程资料：项目「{key}」**没有数据**（库存单据与历史段里都没有它）⇒ 拒做"
                "（⛔ 不导出一份空表，免得被读成「这个项目本来就是空的」）。")
        display = displays.get(key) or ""
        if not display:
            raise MustReportError(
                f"导出过程资料：项目「{key}」**不在档案里**（取不到展示名）⇒ 先建档再导"
                "（⛔ 不拿仓库名冒充展示名）。")
        cutoff = R.load_cutoff(session, warehouse=key)
        raw = D.build_matrix(inv_rows=inv_rows, manual_rows=mech_rows, history_rows=history_rows,
                             warehouse=key, adjusted=False, cutoff_ym=cutoff)
        if tab_no == D.TAB_RAW:
            rows = raw
        else:
            adjusted = D.build_matrix(inv_rows=inv_rows, manual_rows=mech_rows,
                                      history_rows=history_rows, warehouse=key,
                                      adjusted=True, cutoff_ym=cutoff)
            # ⭐ **差异表**（用户 2026-09-18 裁）= 与另两张**同形态**，只有**取数**不同：
            #    逐格 = 调整后 − 原始 ⇒ 见 `domain.difference_rows`（⛔ 不在实现层再差一次）
            rows = adjusted if tab_no == D.TAB_ADJUSTED else D.difference_rows(raw, adjusted)
        made.append(process_export.build_xlsx(rows, out_dir, display=display, tab=tab_no,
                                              ym=report_ym))
    if len(made) == 1:
        return Path(made[0])
    return Path(process_export.build_zip(
        made, out_dir, D.export_manifest(keys, tab=tab_no, ym=report_ym)["zip_name"]))


def export_big(session: Session, month: str = "") -> Path:
    """导出**活动大表成品**（`TAIL-04` 路径① **片 4b**）—— **一份**（全项目在一张表里：⛔ 不是每项目一份、⛔ 无 zip）。

    - ⭐ **行装配 = `mod07_setl.big_service.build_big_data`**（**与页面同一份** ⇒ 两处同序同值，§5.7.3）——
      本层只做「取数 → 转交 → 报路径」。
    - 月份：给了就用、**不给 = 本表默认年月**（材料报表类 = 北京时间上月，§9.2）。
    - ⚠️ **一行都没有 ⇒ 拒做**（⛔ 不产出一张只剩表头与合计的空表 —— 那会被读成「本月真的没有在建项目」）。
    """
    from app.mod07_setl import big_service as BS
    from app.report_export import big_export

    state = BS.parse_state({"period": month} if str(month or "").strip() else {})
    data = BS.build_big_data(session, state)
    if not data.get("rows"):
        raise MustReportError(
            "导出活动大表：**一行都没有**（该月没有在建项目，或大表还没选题）⇒ 拒做"
            "（⛔ 不产出一张空表让你以为「本月真的没有项目」）。")
    ym = str(data["month"])
    out_dir = EXPORT_ROOT / big_export.FILE_SUFFIX / period_label(ym)
    return Path(big_export.build_xlsx(data, out_dir, name=big_export.file_name(ym)))


__all__ = ["EXPORT_ROOT", "period_label", "setl_rows", "setl_count", "export_settlement",
           "export_inventory", "export_extract", "export_ledger", "export_proc", "export_big"]
