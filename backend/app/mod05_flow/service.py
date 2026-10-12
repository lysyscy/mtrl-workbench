"""`MOD-05` 组装层 —— 取数 → 跑域内核 → 视图数据（**页面与 API 共用**）。

⚠️ **不重写任何判定**：撤销走 `domain.revoke_flow`、欠款走 `domain.debt_by_category`、台账走
   `domain.build_ledger`、统计走 `domain.payment_stats`、状态走 `domain.payment_status`
   —— 本文件只做**取数与装配**。
⚠️ 付款统计读有效流水的实际金额和付款日期；欠款/台账读旁路统计金额，
   台账仍按单据日期归月。人工修正欠款不改变付款事实（§4.5.5）。

口径：《说明书》§4.4.2（付款登记 / 两态）· §4.4.5（撤销必填原因）· §4.5.1（欠款三类）
      · §4.5.2（期初占位行）· §4.5.4（逐月台账）· §4.5.5（付款统计）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.core.money import sum_money, to_money
from app.core.projects import project_index, project_key, project_label
from app.mod01_projects.models import Project
from app.mod05_flow import domain as dom
from app.mod05_flow import repository as repo
from app.mod05_flow.domain import LedgerRow, NoticeDebtView, OpeningView
from app.mod05_flow.models import (
    CATEGORY_JC,
    CATEGORY_MATERIAL,
    CATEGORY_MECH,
    FLOW_EFFECTIVE,
    FLOW_REVOKED,
    PAY_METHODS,
    PaymentFlow,
)

# 界面上的类别显示名（**只有三类**，§4.2.3）
CATEGORY_LABELS: dict[str, str] = {
    CATEGORY_MATERIAL: "辅材",
    CATEGORY_MECH: "机械",
    CATEGORY_JC: "集采",
}

# ⚠️ 机械侧「其他支出金额」的输入源 = **机械费结算金额**，它来自**过程资料**（`MOD-06`，未接）。
#    在接上前，本层**显式按 0 计**并把这件事标到页面上（**不臆造数值**）。
MECH_SETTLE_SOURCE_READY = False


# ------------------------------------------------- 包间出口（`TAIL-195` 批 2a）
# ⚠️⚠️ 跨包调用**只许经这一层**（计划 §2.3：「包间只经 `service` 调用，**不得跨包直查对方表**」）。
#    ⛔ 别的包**别** `import app.mod05_flow.repository` —— 守卫 = `backend/tests/test_layering.py` **规则 C**。
#    ⭐ 下面三个名字与 `repository` 里那份**是同一个对象**（纯再导出，⛔ 不另写一套口径）——
#       同款先例：`mod03_notice/repository.py` 再导出 `MOD-02` 的运行记录仓储。
has_request_id = repo.has_request_id    # 付款提交的**幂等**判据（§4.4.4）
create_flow = repo.create_flow          # 落一条流水（⛔ 别绕过它：它自动走 `sync_stat_paid` 重算唯一出口）
flows_of_notices = repo.flows_of_notices
list_flows = repo.list_flows            # 全部流水（含已撤销）—— 通知书列表与撤销入口要看


# ---------------------------------------------------------------- 输入行视图


def notice_debt_views(s: Session) -> list[NoticeDebtView]:
    """付款通知书 → 欠款/台账视图；付款统计只借其归属和剔除信息。"""
    out: list[NoticeDebtView] = []
    for n in repo.notice_rows(s):
        cat = str(n.category or "").strip() or CATEGORY_MATERIAL
        out.append(
            NoticeDebtView(
                notice_id=int(n.id),
                doc_date=str(n.doc_date or ""),          # 归月依据 = 单据日期
                category=cat,
                settle_stat=to_money(n.stat_settle),
                pay_stat=to_money(n.stat_paid),
                excluded=bool(n.excluded),               # 剔除记录不计入
                ownership_id=n.ownership_id,             # 归属（档案行 id）；None = 未判定
            )
        )
    return out


def opening_views(s: Session, project_id: int | None = None) -> list[OpeningView]:
    return [
        OpeningView(
            category=str(o.category or ""),
            project_id=o.project_id,
            cutoff_ym=str(o.cutoff_ym or ""),
            settle_amount=to_money(o.settle_amount),
            paid_amount=to_money(o.paid_amount),
            opening_id=int(o.id or 0),                  # ⭐ 真 id（与 `ledger.opening_id` 同源 · 见 domain 注释）
        )
        for o in repo.list_openings(s, project_id=project_id)
    ]


def project_options(s: Session) -> list[dict]:
    """项目选择器候选（**台账两侧共用同一个选择器**，§4.5.4）。"""
    return [
        {"id": p.id, "label": project_label(p), "warehouse_name": p.warehouse_name or ""}
        for p in sorted(project_index(s).values(), key=lambda x: (x.warehouse_name or "", x.id))
    ]


# ---------------------------------------------------------------- ① 付款流水列表


def _flow_dict(f: PaymentFlow, notices: dict[int, object], projects: dict[int, Project]) -> dict:
    n = notices.get(f.notice_id) if f.notice_id else None
    return {
        "id": f.id,
        "flow_no": f.flow_no,
        "pay_date": f.pay_date,
        "notice_id": f.notice_id,
        "doc_no": str(getattr(n, "bill_no", "") or ""),
        # ⭐ `TAIL-283`：这笔流水**来自哪张付款通知书**的五项展示信息 —— 数据源 = 上面那份
        #    **一次预读**的通知书字典（⛔ 不逐行查库、⛔ 不依赖前端 `NO` 缓存）；
        #    `n is None`（`notice_id` 为 NULL 或指向已删除的通知书）= **失联** ⇒ 五项如实留空，
        #    ⛔ 绝不 join 过滤掉这条流水，也⛔ 不拿 0 冒充"没有这个数"。
        #    ⚠️ 「通知书日期」是**单据日期**（`doc_date`），与下面「付款日期」（`pay_date`）不是一回事。
        #    ⚠️ 「通知书名称」的取值口径 = 通知书列表同一条（`fields['BillName']`，⛔ 模型没有独立列）。
        "doc_date": str(getattr(n, "doc_date", "") or "") if n else "",
        "bill_name": str((getattr(n, "fields", None) or {}).get("BillName") or "") if n else "",
        "payee": str(getattr(n, "payee", "") or "") if n else "",
        # ⚠️ 当前审批金额（i8 源事实，随源变化）—— **不是**"付款发生时的历史快照"（那东西没存）。
        #    失联 ⇒ `None`（前端画「—」、Excel 留空）；真实等于 0 ⇒ `"0.00"`（两件事，别混）。
        "amount_approved": f"{to_money(n.amount_approved):.2f}" if n else None,
        "category_label": CATEGORY_LABELS.get(str(getattr(n, "category", "") or ""), "") if n else "",
        "project_id": f.project_id,
        "project_display": project_label(projects.get(f.project_id) if f.project_id else None),
        # ⚠️ `project_key` = **仓库名**（§2.7.4 的归并键）：前端「付款项目」筛选与付款统计
        #    联动都按它对齐（展示名只是显示名 ⇒ 拿它当键会**静默失配**）。
        "project_key": project_key(projects.get(f.project_id) if f.project_id else None),
        "amount": f"{to_money(f.amount):.2f}",
        "pay_method": f.pay_method,
        "remark": f.remark,
        # ⭐ **操作人**（§1.5.1 末行）—— 2026-09-20 补的列（迁移 `d1f3a5c7e9b2`）。
        # ⚠️ 在此之前页面上那一列显示的是 `created_at`（`core.js::adaptFlow` 的 `op`），
        #    因为表里根本没这个字段。⚠️ 老行是**空串**（如实表示"当时没记"，⛔ 不是编的）。
        "created_by": f.created_by,
        "status": f.status,
        "status_label": "生效" if f.status == FLOW_EFFECTIVE else "已撤销",
        "revoke_reason": f.revoke_reason,
        "revoked_at": f.revoked_at.strftime("%Y-%m-%d %H:%M") if f.revoked_at else "",
        "request_id": f.request_id,
        "created_at": f.created_at.strftime("%Y-%m-%d %H:%M") if f.created_at else "",
    }


def build_flows(
    s: Session,
    *,
    year_month: str | None = None,
    status: str | None = None,
    pay_method: str | None = None,
    project_id: int | None = None,
    keyword: str = "",
) -> dict:
    """流水页数据：筛选（**即时生效**）+ 指标 + 合计。

    ⚠️ 默认月 = **北京时间当月**（`domain.default_flow_period`）；列表**不分页**（`FLOW_PAGINATED=False`）。
    """
    notices = {int(n.id): n for n in repo.notice_rows(s)}
    projects = project_index(s)
    raw = [_flow_dict(f, notices, projects) for f in repo.list_flows(s)]

    # ⚠️ 约定：`None` = 用默认（北京时间当月）；`""` = **全部月份**（与路由同一语义）
    ym = dom.default_flow_period() if year_month is None else year_month
    rows = [r for r in raw if not ym or str(r["pay_date"] or "")[:7] == ym]
    rows = dom.filter_flows(
        rows, status=status, pay_method=pay_method, project_id=None, keyword=keyword
    )
    if project_id is not None:
        rows = [r for r in rows if r["project_id"] == int(project_id)]

    live = [r for r in rows if r["status"] == FLOW_EFFECTIVE]
    dead = [r for r in rows if r["status"] == FLOW_REVOKED]
    return {
        "year_month": ym,
        "status": status or "",
        "pay_method": pay_method or "",
        "project_id": project_id,
        "keyword": keyword,
        "rows": rows,
        "kpis": [
            {"k": "生效流水", "v": len(live), "s": "笔"},
            {"k": "生效金额", "v": f"{sum((Decimal(r['amount']) for r in live), Decimal('0')):.2f}", "s": "元"},
            {"k": "已撤销", "v": len(dead), "s": "笔"},
            {"k": "已撤销金额", "v": f"{sum((Decimal(r['amount']) for r in dead), Decimal('0')):.2f}", "s": "元"},
        ],
        "summary": {
            "flow_no": "合计（生效）",
            "amount": f"{sum((Decimal(r['amount']) for r in live), Decimal('0')):.2f}",
        },
        "pay_methods": list(PAY_METHODS),
        "project_options": project_options(s),
        "paginated": dom.FLOW_PAGINATED,
    }


# ---------------------------------------------------------------- ② 欠款（三类 + 按项目）


def build_debt(s: Session, *, jc_debt=None) -> dict:
    """「按项目看欠款」+ 三类合计（§4.5.1）。

    - 辅材 = Σ辅助统计结算 − Σ辅助统计付款 ＋ 辅材期初
    - 机械 = **机械费结算金额** − Σ机械统计付款 ＋ 机械期初
    - 集采 = **不在本域计算**（由集采台账负责）⇒ 本域只作**合计展示**（`jc_debt` 由调用方注入）
    """
    rows = notice_debt_views(s)
    openings = opening_views(s)
    by_cat = dom.debt_by_category(rows, openings, mech_settle_total=Decimal("0"), jc_debt=jc_debt)
    by_project = dom.debt_by_project(rows)
    index = project_index(s)                       # ⚠️ 取一次（`names` 与 `openings` 共用）
    names = {pid: project_label(p) for pid, p in index.items()}

    items = []
    for key, amount in sorted(by_project.items(), key=lambda kv: str(kv[0])):
        if key == dom.UNASSIGNED:
            items.append({"key": "未判定", "label": "未判定（未指定归属）", "amount": f"{amount:.2f}"})
        else:
            items.append({
                "key": str(key), "label": names.get(int(key), f"#{key}"), "amount": f"{amount:.2f}",
            })
    return {
        "by_category": [
            {"category": c, "label": CATEGORY_LABELS[c], "amount": f"{by_cat[c]:.2f}"}
            for c in (CATEGORY_MATERIAL, CATEGORY_MECH, CATEGORY_JC)
        ],
        "total": f"{dom.total_debt(by_cat):.2f}",
        "by_project": items,
        "mech_settle_ready": MECH_SETTLE_SOURCE_READY,
        # ⭐ 期初占位行**逐条**给前端：前端「按项目看欠款」的柱子要按期初并入（§4.5.2 用户裁定
        #    「卡片要并」）—— 只给 `by_category` 的聚合数，前端就没法按期初修正柱子 ⇒ **与 KPI 打架**。
        "openings": [
            {
                # ⭐ 真 id：壳里「删除期初行」按钮在**台账行**上、要去这一侧取数据 ⇒ 两边 id 必须同源
                #   （2026-09-28 修：此前不返回 id ⇒ 壳只能填假值 `''` ⇒ 点删除**静默无反应**）。
                "id": o.opening_id,
                "category": o.category,
                "category_label": CATEGORY_LABELS.get(o.category, o.category),
                "project_id": o.project_id,
                "project_key": project_key(index.get(int(o.project_id)) if o.project_id else None),
                "project_label": project_label(index.get(int(o.project_id)) if o.project_id else None),
                "cutoff": o.cutoff_ym,
                "settle": f"{o.settle_amount:.2f}",
                "paid": f"{o.paid_amount:.2f}",
            }
            for o in opening_views(s)
        ],
    }


def build_debt_live(s: Session, **kw) -> dict:
    """⭐ **生产用的欠款组装件** = `build_debt` ＋ **注入集采欠款**（`TAIL-100`）。

    ⚠️ **为什么单开一个函数、⛔ 不让 `build_debt` 自己取**：
      `build_debt` 是**纯组装**（离线桩件 `tests/test_page_m05.py` 用 `FakeSession` 在测它
      ⇒ 它里面**不能连库**）；而"**谁去把集采那一格拿回来**"是**装配问题**。
    ⇒ 收在**这一个出口**：看板端点（`/api/m05/debt`）与手改统计金额的回执**都调它**。
      ⛔ 别在各自那里 `build_debt(...)` 一次 —— 那就又成了两处、迟早漏一处（这正是 `TAIL-100` 的成因）。
    """
    from app.mod11_jc import service as M11      # 局部导入：mod11 ⇄ mod05 不成环（同 `total_debt_rows` 写法）
    kw.setdefault("jc_debt", M11.debt_of_ledger(s))
    return build_debt(s, **kw)


# ---------------------------------------------------------------- ③ 逐月台账


# ---------------------------------------------------------------- ④ 总欠款表（用户 2026-09-20）

def order_project_ids(cand: set[int], by_wh: dict[str, int], order: list[str], label_of) -> list[int]:
    """「导出总欠款」的**行序**（2026-09-28 用户口径：可以像月度会大表那样**自己选项目 + 定顺序**）。

    - `order` **非空** ⇒ **按用户给的顺序**出行（只保留：能解析到、且**真有数**的项目；重复的只取一次）；
      ⛔ 不存在的名字**静默跳过**（壳侧候选只给"档案里有的项目"，正常不会出现 —— 跳过比报错好：别让一个
      脏名字把整张表顶掉）。
    - `order` **为空** ⇒ 现状：按**项目展示名**升序（同名再按 id）。

    ⭐ 抽成纯函数是为了**能离线钉住**（`tests/test_page_m05.py`）—— 排序这种事最容易"改一处漏一处"。
    """
    if not order:
        return sorted(cand, key=lambda p: (label_of(p) or "", int(p)))
    seen: set[int] = set()
    out: list[int] = []
    for nm in order:
        pid = by_wh.get(str(nm))
        if pid is None or pid not in cand or pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def total_debt_rows(s: Session, *, order: list[str] | None = None) -> dict:
    """**总欠款**（按项目 × 集采 / 辅材 / 机械）—— 供 `debt_export.build_xlsx` 写表。

    ⭐ **口径一律复用现场那两个函数**（⛔ 绝不在这里另写一套算钱的）：
      · 辅材 / 机械 ⇒ **逐项目**调 `dom.debt_by_category(...)`
        —— 与「按项目看欠款」**同一个函数、同一份口径**（只是把行先按项目切开）；
      · 集采 ⇒ `mod11_jc.service.build_list(...)` 的行
        —— 与**集采台账页**同一个函数（`debt` 就是那一页显示的欠款）。

    ⚠️ 机械欠款**不含机械费结算**（那个来源在 `MOD-06`、还没接通，见 `MECH_SETTLE_SOURCE_READY`）
      ⇒ 本函数**照实算**、把 `mech_settle_ready` 一并回出去，由调用方**显式标在表尾**（禁静默）。
    ⚠️ 集采只计「**纳入台账**」的行（「待确认 / 不纳入」按定义不进台账）；
       排除了几条**一并回出来**（⛔ 禁静默少算）。
    ⚠️ 项目**只从名册里认**（`project_index`）—— 展示名的主人是档案，⛔ 不自己拼名字。
    """
    rows = notice_debt_views(s)
    openings = opening_views(s)
    index = project_index(s)
    by_wh = {str(getattr(p, "warehouse_name", "") or ""): pid for pid, p in index.items()}

    # ① 辅材 / 机械：**逐项目**复用 `debt_by_category`（⚠️ 是内存里切行，不是逐条查库 = 无 N+1）
    per: dict[int, dict[str, Decimal]] = {}
    for pid in index:
        mine = [r for r in rows if r.ownership_id == pid]
        mine_open = [o for o in openings if o.project_id == pid]
        if not mine and not mine_open:
            continue                                    # 该项目两边都没数 ⇒ 不出行（⛔ 别刷一屏 0）
        by_cat = dom.debt_by_category(mine, mine_open, mech_settle_total=Decimal("0"))
        per[pid] = {CATEGORY_MATERIAL: by_cat[CATEGORY_MATERIAL],
                    CATEGORY_MECH: by_cat[CATEGORY_MECH]}

    # ② 集采：与集采台账页同一个函数（`build_list` 不给筛选 = 全量）
    from app.mod11_jc import service as M11
    from app.mod11_jc.models import TAG_IN

    jc: dict[int, Decimal] = {}
    jc_skipped = 0
    for r in M11.build_list(s)["rows"]:
        pid = by_wh.get(str(r.get("project_key") or ""))
        if str(r.get("tag") or "") != TAG_IN or pid is None:
            jc_skipped += 1                             # 不是"纳入台账" / 项目不在名册 ⇒ 不计
            continue
        jc[pid] = jc.get(pid, Decimal("0")) + Decimal(str(r.get("debt") or 0))

    # ⭐ 行序（2026-09-28 用户口径）：用户选了项目 ⇒ **按他给的顺序**；没选 ⇒ 按展示名升序（现状）
    pids = order_project_ids(set(per) | set(jc), by_wh, list(order or []),
                             label_of=lambda p: project_label(index.get(p)))
    items = [
        {
            "index": n,
            "project": project_label(index.get(pid)),
            "jc": jc.get(pid, Decimal("0")),
            "material": (per.get(pid) or {}).get(CATEGORY_MATERIAL, Decimal("0")),
            "mech": (per.get(pid) or {}).get(CATEGORY_MECH, Decimal("0")),
        }
        for n, pid in enumerate(pids, start=1)
    ]
    return {"items": items, "jc_skipped": jc_skipped, "mech_settle_ready": MECH_SETTLE_SOURCE_READY}


def export_total_debt(s: Session, projects: str = "") -> tuple[Path, dict]:
    """导出**总欠款表** ⇒ `(绝对路径, 回执说明)`。

    ⚠️⚠️ 回的是 **`Path`**，⛔ **不是 `str`** —— 端点那边要 `path.name`：
       `2026-09-20` **真机实测踩到**（回 `str` ⇒ 一调就 `AttributeError` ＋ **HTTP 500**，
       而单测全绿，因为没人跨过"返回值 → 端点"这道缝）。

    ⚠️ 回执里必须带三件事（禁静默）：① 出了几行；② 集采**排除了几条**（不是"纳入台账"的）；
      ③ 机械口径**未接通**这件事（表尾也写了同一句 —— 文件离开页面后还得说清）。
    """
    from app.core.config import PROJECT_ROOT
    from app.mod05_flow import debt_export as X

    # ⭐ `projects` = 壳里「选择项目」给的**仓库名**，逗号分隔、**顺序即行序**（空 = 全部，现状行为）
    order = [x.strip() for x in str(projects or "").split(",") if x.strip()]
    data = total_debt_rows(s, order=order or None)
    if not data["items"]:
        raise MustReportError("总欠款：**一个项目的欠款都算不出来**（通知书与集采合同都还没数据）"
                              "—— 请先抓取 / 导入，再导出。")
    out_dir = PROJECT_ROOT / "artifacts" / "exports" / X.FILE_PREFIX
    path = Path(X.build_xlsx(data["items"], out_dir, mark_mech=not data["mech_settle_ready"]))
    return path, {
        "rows": len(data["items"]),
        "jc_skipped": int(data["jc_skipped"]),
        "mech_settle_ready": bool(data["mech_settle_ready"]),
    }


def build_ledger(
    s: Session, *, project_id: int, end_ym: str = "", today: date | None = None
) -> dict:
    """逐月台账（§4.5.4）—— **两侧（辅材 / 机械）共用同一个项目选择器**，各自一套行。

    - 历史段为手动、自动、合计；删除入口仅给真实手动期初记录
    - 空月也出行（三列记 0）
    - 机械侧「其他支出金额」= **派生只读**，**无手填入口**（`MECH_HAS_MANUAL_INPUT=False`）
    """
    rows = notice_debt_views(s)
    today = today or date.today()
    sides = []
    # 同一有效机械值供导入、手录、过程资料和台账读取；只接外租含税两列。
    from app.mod06_proc import service as P6S

    from app.mod01_projects import service as PS
    wh = project_key(next((p for p in PS.all_projects(s) if p.id == int(project_id)), None))
    mech_settle = {str(r['ym']): sum_money([r.get('mech_2'), r.get('mech_3')])
                   for r in P6S.load_mech(s) if wh and r.get('warehouse') == wh and r.get('ym')}
    for cat in dom.LEDGER_SIDES:
        openings = opening_views(s, project_id=project_id)
        mine = [o for o in openings if o.category == cat]
        opening = mine[0] if mine else None
        monthly = dom.monthly_aggregate(rows, cat, int(project_id))
        # 空单据日期归期初；仍取统计付款，保留用户手改统计金额的口径。
        historical_notices = [r for r in rows if not r.excluded and r.category == cat
                              and r.ownership_id == int(project_id) and not r.doc_date]
        automatic = sum_money([r.pay_stat for r in historical_notices])
        history_segment = opening is None or opening.cutoff_ym <= "2025-11" or bool(historical_notices)
        ledger: list[LedgerRow] = dom.build_ledger(
            category=cat,
            monthly=monthly,
            opening=opening,
            mech_settle_by_month=mech_settle if cat == CATEGORY_MECH else None,
            end_ym=end_ym or None,
            remarks=repo.remarks_map(s, category=cat, project_id=int(project_id)),
            opening_auto=automatic if history_segment else None,
        )
        opening_row = repo.list_openings(s, project_id=int(project_id), category=cat)
        sides.append({
            "category": cat,
            "label": CATEGORY_LABELS[cat],
            "opening_id": opening_row[0].id if opening_row else None,
            "opening_default": ({"cutoff_ym": "2025-11", "fallback": False}
                                if history_segment else dom.opening_defaults(rows, cat, today)),
            "has_manual_input": not (cat == CATEGORY_MECH and not dom.MECH_HAS_MANUAL_INPUT),
            "rows": [
                {
                    "seq": r.seq, "month": r.month,
                    "other_expense": f"{r.other_expense:.2f}",
                    "payment": f"{r.payment:.2f}",
                    "debt": f"{r.debt:.2f}",
                    "remark": r.remark,
                    "is_opening": r.is_opening,
                    "row_kind": r.row_kind,
                    "month_label": r.month_label,
                    "counts_in_total": r.counts_in_total,
                    "remark_key": dom.ledger_remarks_key(cat, int(project_id), r.month),
                }
                for r in ledger
            ],
        })
    for side in sides:
        raw = side["rows"]
        manual = next((r for r in raw if r["row_kind"] == "opening_manual"), None)
        auto = next((r for r in raw if r["row_kind"] == "opening_auto"), None)
        visible = []
        for row in raw:
            if row["row_kind"] in ("opening_manual", "opening_auto"):
                continue
            shown = dict(row)
            if row["row_kind"] == "opening_total":
                shown.update(month_label="2025-11及之前", counts_in_total=True,
                             is_opening=bool(manual and manual["is_opening"]),
                             manual_payment=manual["payment"], automatic_payment=auto["payment"],
                             remark=manual["remark"])
            shown["seq"] = len(visible) + 1
            visible.append(shown)
        side["display_rows"] = visible
    return {
        "project_id": int(project_id),
        "project_options": project_options(s),
        "sides": sides,
        "shared_project_selector": dom.SHARED_PROJECT_SELECTOR,
        "has_switch_caliber_button": dom.HAS_SWITCH_CALIBER_BUTTON,
    }


# ---------------------------------------------------------------- ④ 实际付款统计


def set_opening_payment(s: Session, *, project_id: int, category: str, payment: str) -> dict:
    """编辑期初合计付款；按保存时的自动统计金额反算手动值。"""
    side = next((x for x in build_ledger(s, project_id=project_id)["sides"]
                 if x["category"] == category), None)
    if side is None:
        raise MustReportError("请选择辅材或机械台账")
    auto = next((r for r in side["rows"] if r["row_kind"] == "opening_auto"), None)
    if auto is None:
        raise MustReportError("当前台账没有2025-11及之前的期初段")
    existing = next((o for o in repo.list_openings(s, project_id=project_id, category=category)
                     if o.cutoff_ym <= "2025-11"), None)
    paid = to_money(payment) - to_money(auto["payment"])
    opening = repo.upsert_opening(s, category=category, project_id=project_id,
                                 cutoff_ym=existing.cutoff_ym if existing else "2025-11",
                                 settle_amount=existing.settle_amount if existing else 0,
                                 paid_amount=paid, remark=existing.remark if existing else "")
    return {"ok": True, "opening_id": opening.id, "manual_payment": f"{paid:.2f}",
            "automatic_payment": auto["payment"]}


def _current_bucket(granularity: str, today: date) -> str:
    return dom.bucket_of(today.isoformat(), granularity)


def build_stats(
    s: Session, *, granularity: str = "", year: int | None = None,
    quarter: int | None = None, project_id: int | None = None, today: date | None = None, bucket: str = "",
) -> dict:
    """付款统计（§4.5.5）：**左栏 = 按项目 · 右栏 = 时间轴**；换粒度**不换口径**。"""
    today = today or date.today()
    gran = granularity or dom.DEFAULT_GRANULARITY          # 默认**按周**
    year = int(year or today.year)
    if gran == dom.GRAN_WEEK and not quarter:
        quarter = (today.month - 1) // 3 + 1
    buckets = dom.time_buckets(gran, year=year, quarter=quarter)
    selected = dom.bucket_of(bucket + '-01' if len(bucket) == 7 else bucket, gran) if bucket else _current_bucket(gran, today)

    notices = notice_debt_views(s)
    rows = payment_stat_views(notices, repo.list_flows(s))
    index = project_index(s)                      # ⚠️ 循环外取一次（别在循环里回查 = 伪 N+1）
    names = {pid: project_label(p) for pid, p in index.items()}
    grid = dom.payment_stats(rows, granularity=gran, buckets=set(buckets) | {selected})

    left = []
    for key in sorted(grid, key=lambda k: str(k)):
        label = "未判定" if key == dom.UNASSIGNED else names.get(int(key), f"#{key}")
        left.append({
            # ⭐ `key` = **仓库名**（§2.7.4 归并键）——前端「点条目 → 按该项目筛流水」要用它，
            #    ⛔ 用展示名当键会**静默失配**（两者不是一回事）。
            "key": "" if key == dom.UNASSIGNED else project_key(index.get(int(key))),
            "label": label,
            "cells": [f"{to_money(grid[key].get(b, 0)):.2f}" for b in buckets],
        })

    right = [f"{to_money(sum((grid[k].get(b, 0) for k in grid), Decimal('0'))):.2f}" for b in buckets]

    return {
        "granularity": gran,
        "granularity_label": "按周" if gran == dom.GRAN_WEEK else "按月",
        "year": year,
        "quarter": quarter,
        "buckets": buckets,
        "left": left,
        "right": right,
        "selected": {
            "bucket": selected,
            "projects": [{"key": r["key"], "label": r["label"],
                          "amount": f"{to_money(grid[k].get(selected, 0)):.2f}"}
                         for k, r in zip(sorted(grid, key=lambda k: str(k)), left)
                         if grid[k].get(selected, 0)],
            "total": f"{sum((grid[k].get(selected, 0) for k in grid), Decimal('0')):.2f}",
            "count": sum(1 for r in rows if dom.bucket_of(r.pay_date, gran) == selected),
        },
        "total": f"{sum((r.amount for r in rows), Decimal('0')):.2f}",
        "counts": [sum(1 for r in rows if dom.bucket_of(r.pay_date, gran) == b)
                   for b in buckets],
        "layout": dom.LAYOUT,
        "project_id": project_id,
        "project_options": project_options(s),
    }


def payment_stat_views(notices: list[NoticeDebtView], flows: list[PaymentFlow]) -> list[dom.PaymentStatView]:
    """按通知书归属/剔除关联有效流水；欠款人工值不参与付款统计。"""
    included = {n.notice_id: n for n in notices if not n.excluded}
    rows = []
    for f in flows:
        n = included.get(f.notice_id)
        if f.status == FLOW_EFFECTIVE and n is not None:
            rows.append(dom.PaymentStatView(str(f.pay_date or ""), to_money(f.amount), n.ownership_id))
    return rows


__all__ = [
    "CATEGORY_LABELS", "MECH_SETTLE_SOURCE_READY",
    "notice_debt_views", "opening_views", "project_index", "project_label", "project_options",
    "build_flows", "build_debt", "build_debt_live", "build_ledger", "build_stats",
    "total_debt_rows", "export_total_debt", "order_project_ids",
]


def latest_effective_dates(session, notice_ids):
    from app.mod05_flow import repository
    return repository.latest_effective_dates(session, notice_ids)
