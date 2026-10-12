"""付款通知书列表（§4.2）的**行视图 · 筛选 · 计数** —— 纯函数 ＋ 薄组装。

对应原型 `V.m03` 页（17 列 ＋ 6 项筛选）。本模块只回答三件事：
**这一行的各列值是什么** · **哪些行该显示** · **右侧那几个计数是多少**。

## 口径要点（§4.2）

- **三金额**（§4.2.5）：**审批金额**为**唯一 i8 源**；统计结算金额 / 统计付款金额为**旁路**；
  列表上的「付款金额」是**派生列 = 审批金额 − 已付金额**（会话级可覆盖，**刷新即恢复**，**不落库**）。
  ⭐ 「统计付款金额」默认值 = **已付金额（流水汇总）**（§4.4.7）；原「付款金额（源）」已取消。
- **已付金额 = 生效流水汇总**（撤销的流水不计入）—— 与欠款侧同一定义（`mod05_flow.domain.effective_total`）。
- **付款状态只有两态**（§4.4.2）：已付金额 ≥ 审批金额 ⇒ 已付清；判定基准是**审批金额**。
- **「分类 = 剔除」是专用视图**（§4.2.2）：
  · 切到它时**不再受「审批状态 / 付款状态」筛选约束**（否则默认"未付清"会把剔除行全挡掉）；
  · 该视图**同时承载 i8 已撤单行**，但**按来源分档**（人工剔除 / 规则命中 / i8 已撤单）**不混作一谈**。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.core.money import to_money
from app.core.period import in_period
from app.mod03_notice.models import EXCLUDE_BY_MANUAL, EXCLUDE_BY_RULE, EXCLUDE_NONE
from app.mod05_flow.domain import (
    CATEGORY_JC,
    CATEGORY_MATERIAL,
    CATEGORY_MECH,
    PAY_STATUS_PAID,
    PAY_STATUS_UNPAID,
    effective_total,
    payment_status,
)

# 时间控件的上下文（与原型 `scope:'nt'` 对齐）
PERIOD_SCOPE = "nt"

# 「分类」筛选里的**剔除档** —— ⚠️ 它**不是**第四个分类，而是"看剔除记录"的专用视图（§4.2.2）
CATEGORY_EXCLUDE = "exclude"
CATEGORY_ALL = ""
CATEGORY_OPTIONS: tuple[str, ...] = (CATEGORY_ALL, CATEGORY_MATERIAL, CATEGORY_MECH, CATEGORY_JC, CATEGORY_EXCLUDE)

CATEGORY_LABELS: dict[str, str] = {
    CATEGORY_ALL: "全部",
    CATEGORY_MATERIAL: "辅材",
    CATEGORY_MECH: "机械",
    CATEGORY_JC: "集采",
    CATEGORY_EXCLUDE: "剔除",
}


@dataclass
class NoticeRow:
    """列表一行（列值已算好；页面只负责摆位置）。"""

    notice_id: int
    doc_date: str = ""
    bill_no: str = ""
    bill_name: str = ""                     # 来自 `fields["BillName"]`（表里无独立列）
    project_name: str = ""
    category: str = CATEGORY_MATERIAL
    biz_type: str = ""
    payee: str = ""
    input_by: str = ""
    amount_approved: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")     # 已付金额 = **生效流水汇总**
    stat_settle: Decimal = Decimal("0")
    stat_paid: Decimal = Decimal("0")
    approve_status: str = ""
    excluded: bool = False
    exclude_source: str = EXCLUDE_NONE
    i8_revoked: bool = False
    is_manual: bool = False                 # 手动新增行 ⇒ 「操作」列才有编辑 / 删除（§4.2.6）
    ownership_id: int | None = None
    project_display: str = ""               # 归属项目的展示名（由调用方注入）
    flows: tuple = ()                       # 该行**全部**流水（含已撤销）—— 撤销 / 查看关联要用
    has_link: bool = False                  # 是否有关联集采合同（`MOD-11` 落地前恒 False）
    edited_fields: tuple = ()               # 已被人工手改过的统计字段（判据 = **留痕**，§4.2.7 / R8 的"已改"态）
    jc_supplier: str = ""                   # 集采实际供应商（人工录入 / 自动匹配确认；**不被 i8 导入覆盖**，§4.2.7）

    @property
    def pay_amount(self) -> Decimal:
        """**列表「付款金额」= 派生默认值** = 审批金额 − 已付金额（§4.2.5）。

        ⚠️ 它**不是**那"三个金额"之一；会话级可改，**刷新页面恢复默认**、**不落库**。
        """
        return to_money(self.amount_approved) - to_money(self.amount_paid)

    @property
    def effective_flows(self) -> tuple:
        """**生效**流水（已撤销的不算）—— 撤销付款入口的条件（R18：`Σ payEff > 0`）。"""
        from app.mod05_flow.models import FLOW_EFFECTIVE

        return tuple(f for f in (self.flows or ()) if str(f.get("status") or "") == FLOW_EFFECTIVE)

    @property
    def has_effective_flow(self) -> bool:
        return bool(self.effective_flows)

    @property
    def pay_status(self) -> str:
        """付款状态（**只有两态**，§4.4.2）：已付金额 ≥ **审批金额** ⇒ 已付清。

        ⚠️ 做成**派生属性**而不是字段 —— 它是纯派生的，做成字段就给"字段值与事实不一致"留了口子
           （自检第一版就是这么挂的：传了 100=100 却仍是"未付清"）。
        """
        return payment_status(self.amount_paid, self.amount_approved)

    @property
    def is_overpaid(self) -> bool:
        """⭐ **超付**：已付金额 **>** 审批金额（`P4` 链路 · 《说明书》§4.4.6「超付的处置」）。

        ⚠️ 它是**纯派生**、⛔ **不落库** —— 同 `pay_status` 那条的理由：做成字段就给
           "字段值与事实不一致"留了口子（改一处忘了同步另一处，**静默**且只在超付时才暴露）。
        ⚠️ 判定用 **`>`**（⛔ 不是 `>=`）：实付 == 审批金额 = **付清**，不是超付。
        ⚠️ **超付是既成事实，不是错误**：NC 侧确实付了 ⇒ 流水照记、统计照实不封顶
           （`mod05_flow.repository.sync_stat_paid`），**系统只挂提醒**（§4.4.6），
           ⛔ 不封顶、⛔ 不改写、⛔ 不自动冲销。
        ⚠️ 它与「付款动作禁止超付」（§4.4.4）**不冲突**：那条约束的是**动作**。
        ⚠️ 这里**只回答"这一单超没超"** —— 超付**从哪来**（历史导入 / i8 把审批金额改小…）
           **不由本属性区分**：无论来源，事实一致、处置一致（挂提醒）。
        """
        return to_money(self.amount_paid) > to_money(self.amount_approved)

    @property
    def in_exclude_view(self) -> bool:
        """是否属于「分类 = 剔除」专用视图（§4.2.2：剔除行 **＋** i8 已撤单行）。"""
        return bool(self.excluded or self.i8_revoked)

    @property
    def is_live(self) -> bool:
        """⭐ **统计口径的「有效行」** —— 页面的 `ntLive(n)` 在后端的**唯一对应物**。

        = **未剔除** 且（**未撤单** 或 **撤单但有牵涉**）。

        ⚠️ 两条都不能省，而且是**互相反向**的两件事：
          · **剔除行不计入**（§4.2.2 —— 剔除就是"别算我"）；
          · ⚠️ **有牵涉的撤单行仍要计入**（§4.2.7 —— i8 侧单据被删了，但本系统里**还挂着付款流水 /
            集采关联** ⇒ **不许静默丢账**，得等人先撤销付款 / 解绑关联；处理完它才退场）。
        ⚠️ 「有牵涉」的判据 = **已付金额 > 0 或 有关联集采合同** —— 与页面 `ntVoidJoint` 逐字同条件
          （那里写的是 `paidOf(n.id)>0 || jcRefOf(n.id)`；`amount_paid` 就是生效流水汇总 ⇒ 同一个数）。
        ⚠️ **凡统计出口（合计行 / 欠款 / 计数）一律用它，⛔ 不要再手写 `not excluded`** ——
           `list_data.summary_row` 原先就是这么写的（少算了"有牵涉的撤单行"），
           而那正是本项目反复踩的「同一事实多处写」。
        """
        return (not self.excluded) and (
            (not self.i8_revoked) or (self.amount_paid > 0 or self.has_link)
        )

    @property
    def exclude_reason(self) -> str:
        """**分档**说明（口径要求"不混作一谈"）：人工剔除 / 规则命中 / i8 已撤单。"""
        if self.i8_revoked:
            return "i8 已撤单"
        if self.exclude_source == EXCLUDE_BY_MANUAL:
            return "人工批量剔除"
        if self.exclude_source == EXCLUDE_BY_RULE:
            return "规则命中"
        return "已剔除（来源未标记）" if self.excluded else ""

    @property
    def exclude_bucket(self) -> str:
        """分档键（页面按它分组/打标签）。"""
        if self.i8_revoked:
            return "revoked"
        if self.exclude_source == EXCLUDE_BY_MANUAL:
            return "manual"
        if self.exclude_source == EXCLUDE_BY_RULE:
            return "rule"
        return "other" if self.excluded else ""


# ---------------------------------------------------------------- 装配（薄层：唯一查库处）


def build_rows(session, *, flows_of=None, links_of=None, traces_of=None) -> list[NoticeRow]:
    """读 `payment_notice` ＋ 流水 ＋ 手改留痕 → 列表行。

    `flows_of` / `links_of` / `traces_of` 可注入（`notice_id -> …`），默认自己查 —— **测试注入桩即可离线**。
    """
    from app.mod03_notice.domain import manual_edited_fields
    from app.mod03_notice.repository import notice_rows

    if flows_of is None:
        flows_of = _flows_by_notice(session)
    if links_of is None:
        links_of = _links_by_notice(session)
    if traces_of is None:
        traces_of = _traces_by_notice(session)

    rows: list[NoticeRow] = []
    for n in notice_rows(session):
        approved = to_money(n.amount_approved)
        paid = effective_total(flows_of(int(n.id)))
        rows.append(
            NoticeRow(
                notice_id=int(n.id),
                doc_date=str(n.doc_date or ""),
                bill_no=str(n.bill_no or ""),
                bill_name=str((n.fields or {}).get("BillName") or ""),
                project_name=str(n.project_name or ""),
                category=str(n.category or "").strip() or CATEGORY_MATERIAL,
                biz_type=str(n.biz_type or ""),
                payee=str(n.payee or ""),
                input_by=str(n.input_by or ""),
                amount_approved=approved,
                amount_paid=paid,
                stat_settle=to_money(n.stat_settle),
                stat_paid=to_money(n.stat_paid),
                approve_status=str(n.approve_status or ""),
                excluded=bool(n.excluded),
                exclude_source=str(n.exclude_source or EXCLUDE_NONE),
                i8_revoked=bool(n.i8_revoked),
                is_manual=bool(getattr(n, "is_manual", False)),
                ownership_id=n.ownership_id,
                flows=tuple(flows_of(int(n.id)) or ()),
                has_link=bool(links_of(int(n.id))),
                edited_fields=tuple(manual_edited_fields(traces_of(int(n.id)), int(n.id))),
                # ⛔ **不许漏装**：`list_data._row_dict` 已改为直取本字段（不再 `getattr` 兜空）——
                #    漏装会当场 `AttributeError` 变红，而不是静默变成空串（那会让「点采用」把值清空）。
                jc_supplier=str(n.jc_supplier or ""),
            )
        )
    return rows


def _traces_by_notice(session):
    """`notice_id -> [StatTrace]`（**一次查完**，不得逐行查 = N+1）。"""
    from app.mod03_notice.repository import stat_trace_index

    index = stat_trace_index(session)
    return lambda notice_id: index.get(int(notice_id), [])


def _flows_by_notice(session):
    """`notice_id -> [{字段…}]`（该行**全部**流水，含已撤销）。

    ⚠️ 含已撤销的那几条：撤销入口要判"有几条**生效**流水"（R18），
       查看关联要**列出已撤销的**及其撤销原因（R18 下半）。
    """
    from app.mod05_flow import service as flow_service      # ⭐ 包间出口（§2.3 · `TAIL-195` 批 2a）

    grouped: dict[int, list[dict]] = {}
    for f in flow_service.list_flows(session):
        grouped.setdefault(int(f.notice_id), []).append(
            {
                "id": f.id,
                "flow_no": f.flow_no,
                "amount": f.amount,
                "pay_date": f.pay_date,
                "pay_method": f.pay_method,
                "status": f.status,
                "revoke_reason": f.revoke_reason,
                "revoked_at": f.revoked_at,
            }
        )
    return lambda notice_id: grouped.get(int(notice_id), [])


def _links_by_notice(session):
    """`notice_id -> 关联的集采合同 id 列表`（`MOD-11` 的**付款子表** = 关联关系的唯一载体）。

    ⭐ 2026-09-19（`M5-5`）落地 —— 原注释那句「**本函数是唯一的接入点**：M5 落地时只改这里，
       页面与 API 不必动」正是为此留的，这次就**只改这里**（页面与 API 一个字没动）。

    关联关系**不另建表**：它就存在 `jc_contract` 的**付款子表**里（`source=notice` ＋ `notice_id`）——
    与「从付款域引用（R8）」写的是**同一份记录** ⇒ **双向可见**（判据 `ACC-JC-PAY-001/001-01`）
    是这个设计的**自然结果**，⛔ 不需要"两边各写一遍再同步"。

    ⚠️ **一次查完**（⛔ 不逐行查 = N+1；列表页每行都要问一次）。
    """
    from app.mod11_jc import service as contracts
    grouped = contracts.links_by_notice(session)
    return lambda notice_id: grouped.get(int(notice_id), [])


# ---------------------------------------------------------------- 筛选（§4.2）


@dataclass
class NoticeFilters:
    period: str = ""                        # 统一时间控件取值（**依据 = 单据日期**）
    project_ids: tuple = ()                 # 项目可多选；空 = 全部
    category: str = CATEGORY_ALL            # 全部 / 辅材 / 机械 / 集采 / **剔除**
    approve_status: str = ""                # 空 = 全部
    pay_status: str = ""                    # 空 = 全部
    include_archived: bool = False
    """⚠️⚠️ **要不要把「剔除 / i8 已撤单」行一起给出来**（2026-09-20 新增）。

    默认 `False` = **页面视图**的口径（§4.2.2：剔除行默认隐藏、只在「分类 = 剔除」里出现）。

    ⭐ 但 `GET /api/m03/notice-list`（**壳的数据源**）必须传 `True` ——
       因为壳**自己还要筛一遍**（`ntHit`，含「分类 = 剔除」那个专用视图）。
       取数层若先按页面的"默认隐藏"砍一刀 ⇒ **壳里根本没有剔除行** ⇒ 切「分类 = 剔除」必然全空。
       这正是用户 2026-09-20 报的「**筛选剔除后全是空的**」（实测：库 200 行 → 接口只回 129 行 = 200 − 71）。
       ⚠️ 口径依据是本仓**早已写明**的那条（`repository.notice_rows` 的 docstring）：
          「剔除与撤单行的『默认隐藏』是**筛选层**的事 —— **取数层必须给全**」。
          本字段就是给"取数层"和"页面筛选层"分开用的那个开关。
    """


def filter_rows(rows: list[NoticeRow], f: NoticeFilters, *, project_key=None) -> list[NoticeRow]:
    """按 §4.2 筛选。

    ⚠️ **「分类 = 剔除」是不受其它筛选约束的专用视图**（§4.2.2 明文）——
       切到它时只按**时间 ＋ 项目**筛，**审批状态 / 付款状态一律放开**
       （否则默认的「付款状态 = 未付清」会把剔除行全部挡掉，该视图形同失效）。
    ⚠️ `f.include_archived=True`（取数层）⇒ **不做"默认隐藏"那一刀**，其余照旧。
    """
    keys = {str(k) for k in (f.project_ids or ())}

    def _period_ok(r: NoticeRow) -> bool:
        return not f.period or f.period == "" or in_period(r.doc_date, f.period)

    def _project_ok(r: NoticeRow) -> bool:
        if not keys or project_key is None:
            return True
        return str(project_key(r) or "") in keys

    if f.category == CATEGORY_EXCLUDE:
        return [r for r in rows if _period_ok(r) and _project_ok(r) and r.in_exclude_view]

    out: list[NoticeRow] = []
    for r in rows:
        if not (_period_ok(r) and _project_ok(r)):
            continue
        if r.in_exclude_view and not f.include_archived:
            continue                        # 剔除 / 撤单行**只在专用视图里出现**（默认隐藏）
        if f.category and r.category != f.category:
            continue
        if f.approve_status and r.approve_status != f.approve_status:
            continue
        if f.pay_status and r.pay_status != f.pay_status:
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------- 计数（原型右侧那一条）


@dataclass
class ListCounters:
    shown: int = 0
    effective: int = 0                      # 有效（未剔除、未撤单）
    excluded: int = 0
    revoked: int = 0
    excluded_by: dict = field(default_factory=dict)   # 分档计数：manual / rule

    def text(self) -> str:
        parts = [f"显示 {self.shown} 条", f"有效 {self.effective} 条", f"剔除 {self.excluded} 条"]
        if self.excluded_by:
            detail = "、".join(f"{k} {v}" for k, v in self.excluded_by.items())
            parts.append(f"（其中 {detail}）")
        parts.append(f"i8 已撤单 {self.revoked} 条（切「分类 = 剔除」查看）")
        return " ｜ ".join(parts)


def count_rows(rows: list[NoticeRow], shown: list[NoticeRow] | None = None) -> ListCounters:
    """计数：**全量口径**（同一时间/项目范围内），便于一眼看出"还有多少被挡着"。"""
    c = ListCounters(shown=len(shown if shown is not None else rows))
    by: dict[str, int] = {}
    for r in rows:
        if r.i8_revoked:
            c.revoked += 1
            continue
        if r.excluded:
            c.excluded += 1
            key = "人工" if r.exclude_source == EXCLUDE_BY_MANUAL else (
                "规则" if r.exclude_source == EXCLUDE_BY_RULE else "未标记"
            )
            by[key] = by.get(key, 0) + 1
            continue
        c.effective += 1
    c.excluded_by = dict(sorted(by.items()))
    return c


__all__ = [
    "PERIOD_SCOPE", "CATEGORY_EXCLUDE", "CATEGORY_ALL", "CATEGORY_OPTIONS", "CATEGORY_LABELS",
    "NoticeRow", "NoticeFilters", "ListCounters",
    "build_rows", "filter_rows", "count_rows",
]
