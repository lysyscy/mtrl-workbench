"""付款通知书的**行级动作**（`MOD-03` 能力 2 / 3 / 4）—— 纯函数，**不落库**。

依据：
- 《说明书》§4.2.2（剔除与恢复：**按勾选行**生效 · **只恢复人工剔除** · 混档必须**分开回报**）
- §4.2.3 / §4.2.4（分类**只有三类**，没有"其他"；**手改后重抓不被覆盖**）
- §4.2.6（手动新增行：**统计结算金额恒 0 且不可改** · **录入人 = 当前登录用户** ·
  项目 = 全部已建档项目（含归档；**小微壳除外**）· **编辑 / 删除只对手动行开放** · 上限口径同样适用）
- §9.8.2-5（一切写操作**按 id 定位**，禁止用名字反查）

⚠️ 本模块只做**判定与字段组装**；落库在 `repository`、动作入口在 `router`。
⚠️ 「恢复剔除」**复用 `classify.restore_excluded`**（同一出口，不另写一套判定）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import uuid4

from app.core.errors import MustReportError
from app.core.money import MoneyError, require_non_negative, to_money
from app.mod03_notice.classify import (  # noqa: F401  ← 「恢复剔除」直接复用，不重写
    RestoreReport,
    apply_manual_exclude,
    restore_excluded,
)
from app.mod03_notice.models import EXCLUDE_BY_MANUAL, EXCLUDE_BY_RULE, EXCLUDE_NONE
from app.mod05_flow.domain import CATEGORY_MATERIAL, classify
from app.mod05_flow.models import CATEGORIES

_ZERO = to_money(0)

# 分类的中文名（**唯一出口**；页面不再各写一份 colmap）
CATEGORY_NAMES: dict[str, str] = {
    "material": "辅材",
    "mechanical": "机械",
    "jc": "集采",
}

# §4.2.3：**只有三类**、没有"其他"
CATEGORY_CHOICES: tuple[str, ...] = CATEGORIES


def category_name(value: str) -> str:
    return CATEGORY_NAMES.get(str(value or "").strip(), str(value or "").strip() or "—")


# ============================================================ 能力 2 · 批量改分类（§4.2.4）

# 手改分类**不设留痕**（§9.3 明确"不留痕"），但**重抓不被覆盖**由 `merge.PROTECTED` 保证 ——
# 本模块**不另开"已手改"状态位**（同一事实两处存 ⇒ 副本必然静默过期）。


@dataclass
class CategoryChange:
    """批量改分类的结果（三类分别报，便于逐条核对）。"""

    category: str = ""
    changed: list[int] = field(default_factory=list)
    unchanged: list[int] = field(default_factory=list)
    missing: list[int] = field(default_factory=list)

    @property
    def message(self) -> str:
        label = category_name(self.category)
        parts = [f"已把 {len(self.changed)} 行改为「{label}」"]
        if self.unchanged:
            parts.append(f"另有 {len(self.unchanged)} 行本就是「{label}」、未变")
        if self.missing:
            parts.append(f"另有 {len(self.missing)} 行不在当前数据里、跳过")
        parts.append("分类改动**落库、不留痕**，且再次抓取**不被覆盖**（§4.2.4）")
        return "；".join(parts)


def change_category(rows: list[dict], picked, category: str) -> CategoryChange:
    """**批量改分类**（§4.2.4）—— 只能改成辅材 / 机械 / 集采三类。

    ⚠️ 与「批量剔除」同款：**必须先勾选**（批量 = 对勾选集操作，不是"对整表操作"）。
    ⚠️ 手改后的分类**不被再次抓取覆盖**（`merge.PROTECTED` 落库侧保证）。
    """
    cat = str(category or "").strip()
    if cat not in CATEGORY_CHOICES:
        allowed = " / ".join(category_name(c) for c in CATEGORY_CHOICES)
        raise MustReportError(f"分类只能是「{allowed}」三类，没有「其他」类（§4.2.3）")

    want = {int(x) for x in (picked or ())}
    if not want:
        raise MustReportError("批量改分类必须先勾选要改的行（§4.2.4）")

    result = CategoryChange(category=cat)
    seen: set[int] = set()
    for row in rows or ():
        rid = int(row.get("id") or 0)
        if rid not in want:
            continue
        seen.add(rid)
        if str(row.get("category") or "").strip() == cat:
            result.unchanged.append(rid)
        else:
            result.changed.append(rid)
    result.missing = sorted(want - seen)
    return result


# ============================================================ 能力 3 · 批量剔除 / 恢复剔除（§4.2.2）


@dataclass
class ExcludeReport:
    """**人工批量剔除**的结果（来源 = `manual`，只有这一类能被「恢复剔除」放开）。"""

    marked: list[int] = field(default_factory=list)
    already: list[int] = field(default_factory=list)
    missing: list[int] = field(default_factory=list)

    @property
    def message(self) -> str:
        parts = [f"已把 {len(self.marked)} 行标记为**人工批量剔除**（标记保留、默认隐藏、不销毁数据）"]
        if self.already:
            parts.append(f"另有 {len(self.already)} 行本就已剔除、未重复标记")
        if self.missing:
            parts.append(f"另有 {len(self.missing)} 行不在当前数据里、跳过")
        parts.append("规则命中的剔除**不在此列**（要放开只能改规则配置）")
        return "；".join(parts)


def manual_exclude(rows: list[dict], picked) -> ExcludeReport:
    """**人工批量剔除**（§4.2.2 现行能力）—— 写 `exclude_source = manual`。

    ⚠️ 「恢复剔除」**只放开这一类**；规则命中的剔除不因人工操作而放开。
    """
    ids = apply_manual_exclude(rows, picked)   # ← 复用：含"必须先勾选"的拦截
    want = set(ids)
    report = ExcludeReport()
    seen: set[int] = set()
    for row in rows or ():
        rid = int(row.get("id") or 0)
        if rid not in want:
            continue
        seen.add(rid)
        if bool(row.get("excluded")):
            report.already.append(rid)
        else:
            report.marked.append(rid)
    report.missing = sorted(want - seen)
    return report


# ============================================================ 能力 4 · 手动新增行（§4.2.6）

# 手动行的本地主键前缀（**不是 i8 单据**；`ph_id` 列 unique 且非空 ⇒ 必须给一个不冲突的值）
MANUAL_PH_PREFIX = "MANUAL-"

# 「统计结算金额」对手动行**恒 0 且不可改**（§4.2.6：这笔钱没有新的结算，只有付款）
STAT_SETTLE_FIXED = _ZERO


def new_manual_ph_id() -> str:
    """手动行的本地 `ph_id`（带前缀，**永不与 i8 的单据主键冲突**）。"""
    return f"{MANUAL_PH_PREFIX}{uuid4().hex[:12]}"


def is_manual_ph_id(ph_id: object) -> bool:
    return str(ph_id or "").startswith(MANUAL_PH_PREFIX)


def is_manual_row(row) -> bool:
    """该行是否**手动新增行**（`dict` / ORM / 视图对象都可用）。"""
    if isinstance(row, dict):
        if "is_manual" in row:
            return bool(row.get("is_manual"))
        return is_manual_ph_id(row.get("ph_id"))
    flag = getattr(row, "is_manual", None)
    if flag is not None:
        return bool(flag)
    return is_manual_ph_id(getattr(row, "ph_id", ""))


def assert_manual_editable(row) -> None:
    """**编辑 / 删除只对手动新增行开放**（§4.2.6）。

    ⚠️ i8 抓取回来的行**永不给编辑 / 删除** —— i8 是源数据，本系统只读（§9.3）。
       要改就去 i8 改、再重新抓取（走再次导入合并，§4.2.7）。
    """
    if not is_manual_row(row):
        raise MustReportError(
            "编辑 / 删除只对**手动新增行**开放 —— i8 抓取回来的行是源数据，本系统只读（§4.2.6 / §9.3）；"
            "要改请去 i8 改后**重新抓取**（再次导入会按 §4.2.7 合并）"
        )


@dataclass
class ManualRow:
    """手动新增行的**校验结论 + 落库字段**（§4.2.6）。"""

    values: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def manual_row_payload(
    *,
    entered_by: str,
    bill_no: str = "",
    doc_date: str = "",
    bill_name: str = "",
    project_name: str = "",
    biz_type: str = "",
    payee: str = "",
    category: str = "",
    amount_approved: object = None,
    stat_paid: object = None,
    ownership_id: int | None = None,
    remark: str = "",
    # ⚠️ 下面两个**收下但一律忽略**（不是"签名里没有"）——
    #    §4.2.6：统计结算金额**恒 0 且不可改**；录入人 = **当前登录用户**、不由手填。
    #    收下是为了让"乱传也不生效"这条**真的被防住**（而不是靠调用方不传）。
    stat_settle: object = None,
    input_by: str = "",
) -> ManualRow:
    """组装一条**手动新增付款通知书行**的落库字段（§4.2.6）。

    口径要点（逐条对照 §4.2.6 表）：
    1. **统计结算金额恒 0 且不可改**（`STAT_SETTLE_FIXED`）—— 传进来的值**一律忽略**并说明；
    2. **录入人 = 当前登录用户**（由调用方传 `entered_by`，**不从表单取**）；
    3. **上限口径同样适用**：统计付款金额 ≤ 审批金额（超额**拦截并保留原值**）；
    4. **审批金额由人定**（手动行没有 i8 结算）⇒ 必填且 ≥ 0；
    5. ⭐ 统计付款金额初值 = **已付金额**（手动行无流水 ⇒ 0）；
    6. 归属按**档案 id** 写入（禁止用名字反查，§9.8.2-5）。
    ℹ️ 原「付款金额（源）」字段已取消（§4.2.5，2026-09-16）—— 手动行不再写它。
    """
    notes: list[str] = []

    date_text = str(doc_date or "").strip()
    if not date_text:
        raise MustReportError(
            "手动新增行必须填「单据日期」—— 它是**归月依据**（抓取 / 筛选 / 逐月台账同一条时间轴，§4.5.4）"
        )

    try:
        approved = require_non_negative(amount_approved, field="审批金额")
    except MoneyError as exc:
        raise MustReportError(f"手动行的审批金额不合法（{exc}）—— 该行没有 i8 结算，审批金额**由人定**") from exc

    try:
        paid = to_money(stat_paid) if stat_paid not in (None, "") else _ZERO
        paid = require_non_negative(paid, field="统计付款金额")
    except MoneyError as exc:
        raise MustReportError(f"统计付款金额输入不合法（{exc}）—— 已保留原值") from exc

    if paid > approved:
        raise MustReportError(
            f"统计付款金额不能超过审批金额 {approved}（按发票走，只能少付、不能多付）—— 已保留原值"
        )

    cat = str(category or "").strip()
    if cat and cat not in CATEGORY_CHOICES:
        allowed = " / ".join(category_name(c) for c in CATEGORY_CHOICES)
        raise MustReportError(f"分类只能是「{allowed}」三类，没有「其他」类（§4.2.3）")
    if not cat:
        cat = classify(str(biz_type or ""), str(payee or ""))

    values = {
        "ph_id": new_manual_ph_id(),
        "is_manual": True,
        "bill_no": str(bill_no or ""),
        "doc_date": date_text,
        "project_name": str(project_name or ""),
        "biz_type": str(biz_type or ""),
        "payee": str(payee or ""),
        "input_by": str(entered_by or ""),          # ⑤ 录入人 = 当前登录用户（不从表单取）
        "category": cat,
        "excluded": False,
        "exclude_source": EXCLUDE_NONE,
        "amount_approved": approved,
        "stat_settle": STAT_SETTLE_FIXED,           # ① **恒 0 且不可改**
        "stat_paid": paid,
        "i8_revoked": False,
        "revoked_joint": False,
        "ownership_id": int(ownership_id) if ownership_id not in (None, "") else None,
        # 列表页的「单据名称」从 `fields["BillName"]` 取（表里没有独立列）
        "fields": {"BillName": str(bill_name or ""), "Remark": str(remark or ""), "Manual": "1"},
    }
    notes.append("统计结算金额恒为 0 且不可修改（这笔钱没有新的结算，只有付款）；要入账请填「统计付款金额」")
    if str(remark or ""):
        notes.append("备注已记入该行原始字段")
    return ManualRow(values=values, notes=notes)


def manual_project_options(projects) -> list[dict]:
    """手动新增行的**项目候选**（§4.2.6）：

    **全部已建档项目（含归档）**，⚠️ **小微壳除外** —— 壳本身没有付款单据，选了也挂不上。
    """
    out: list[dict] = []
    for p in projects or ():
        if getattr(p, "is_shell", False):
            continue
        key = str(getattr(p, "id", "") or "")
        if not key:
            continue
        label = (
            str(getattr(p, "disp", "") or "")
            or str(getattr(p, "warehouse_name", "") or "")
            or str(getattr(p, "name_full", "") or "")
            or f"#{key}"
        )
        out.append(
            {
                "key": key,
                "label": label,
                "archived": bool(getattr(p, "is_archived", False)),
            }
        )
    return out


def apply_stat_change(
    session,
    notice_id: int,
    *,
    field: str,
    value: object,
    changed_by: str,
) -> tuple[object | None, str]:
    """**统计金额手改**（§4.5.3）的**唯一出口** —— PRG（`POST /m03/notices/stat`）与 JSON API
    （`POST /api/m03/actions/stat`）**共用这一份**：⛔ 不许两份判定、不许两份文案。

    分三层，各有各的主人（本函数只做"接线"）：
      · **判定**：`domain.adjust_stat` —— 四种拒绝（非法金额 / 非旁路字段 / **超上限** / 值没变）；
      · **落库 + 留痕**：`repository.adjust_notice_stat`（留痕 = 壳判「黄底」的唯一事实来源）；
      · **欠款重算**：MOD-05 的 `service.build_debt`（⛔ 不另写算法）。

    返回 `(trace, message)`：
      · `trace is None` ⇒ **值没变、什么都没做**（§4.2.7：不做无意义的重算，也不产生空留痕）；
      · `message` 一律是**可直接给人看**的中文（改前改后 / 改动人 / 欠款重算结果 / 那条例外说明）。
    """
    from app.mod03_notice import repository as repo
    from app.mod05_flow import service as flow_service

    notice = repo.get_notice(session, int(notice_id))
    if notice is None:
        raise MustReportError(f"通知书 {notice_id} 不存在")

    trace = repo.adjust_notice_stat(
        session, notice, field=field, value=value, changed_by=changed_by
    )
    if trace is None:
        return None, (
            f"「{notice_id}」的该格没有变化 —— **什么都没做**"
            "（§4.2.7：不做无意义的重算、不留空痕）"
        )

    debt = flow_service.build_debt(session)
    parts = " · ".join(f"{d['label']} {d['amount']}" for d in debt["by_category"])
    note = "" if debt.get("mech_settle_ready") else "（机械侧结算额来自过程资料 MOD-06，尚未落地 ⇒ 按 0 计）"
    return trace, (
        f"{trace.label}已由 {trace.before} 改为 {trace.after}（改动人 {trace.changed_by}、已留痕）；"
        f"欠款已实时重算：{parts} · 合计 {debt['total']}{note}"
    )


def apply_manual_save(session, *, row_id: str = "", entered_by: str, fields: dict) -> tuple[object, str]:
    """**手动行新增 / 编辑**（§4.2.6）的**唯一出口** —— PRG（`POST /m03/notices/save`）与 JSON API
    （`POST /api/m03/actions/manual-save`）**共用这一份**：⛔ 不许两份校验、不许两份文案。

    分三层，各有各的主人（本函数只做"接线"）：
      · **校验与载荷**：`manual_row_payload`（录入人取当前登录用户、不从表单取；统计结算恒 0 等口径都在那里）；
      · **是不是手动行**：`assert_manual_editable`（⛔ i8 抓取行永不可改，§4.2.7）；
      · **落库**：`repository.create_manual_notice` / `update_manual_notice`（编辑返回**被改动的列名**）。

    `row_id` 空 = **新增**；有值 = **编辑该手动行**（「新增与编辑共用同一套」，§4.2.6）。
    返回 `(row, message)`，`message` 是可直接给人看的中文（含被改字段数 / 只影响「付款」那类说明）。
    """
    from app.mod03_notice import repository as repo

    # ⚠️ `ownership_id` 表单/JSON 过来都是**字符串** ⇒ 在这里统一转成 `int | None`（`manual_row_payload`
    #    那一层的入参口径没变）—— 两个出口谁都不必自己转（一处转，处处一致）。
    rest = dict(fields or {})
    oid = str(rest.pop("ownership_id", "") or "").strip()
    payload = manual_row_payload(
        entered_by=entered_by, ownership_id=int(oid) if oid.isdigit() else None, **rest
    )
    values = payload.values
    rid = str(row_id or "").strip()
    if rid.isdigit():
        row = repo.get_notice(session, int(rid))
        if row is None:
            raise MustReportError(f"要保存的手动行 {row_id} 不存在")
        assert_manual_editable(row)
        touched = repo.update_manual_notice(session, row, values)
        msg = (
            f"已保存手动行 {row.bill_no or row.id}（改动 {len(touched)} 个字段：{'、'.join(touched) or '无'}）"
            " —— 它参与欠款统计、与 i8 数据无关"
        )
    else:
        row = repo.create_manual_notice(session, values)
        msg = (
            f"已新增 1 行手动付款通知书（本地编号 {row.ph_id}）"
            "；该行**只影响「付款」**、不影响「其他支出金额」"
        )
    if payload.notes:
        msg += "；" + "；".join(payload.notes)
    return row, msg


def default_pay_method(bill_no: str, plan_methods: dict) -> str:
    """**实际付款方式的默认值**（§4.4.2，**唯一出口**）：先取付款计划的值、取不到兜底「现汇」。

    ⚠️ 窗口渲染与提交重算**必须走同一个出口** —— 否则会出现"页面上显示承兑、提交时说付款方式为空"。
    ⚠️ 2026-09-19（`§19` 批 4 · S3a）：**从 `notice_pay.py` 搬到这里**（那是**会被删**的页面件，本件是存活件 ✓）
    —— `notice_pay.py` 现在反向 import 它（临时，随删页一起消失 ✓）。⛔ 别在两边各留一份实现。
    """
    return str((plan_methods or {}).get(str(bill_no or "").strip()) or "") or "现汇"


def apply_batch_pay(
    session,
    *,
    ids,
    drafts: dict,
    pay_date: str = "",
    remark: str = "",
    request_id: str = "",
    plan_methods: dict | None = None,
) -> tuple[list, str]:
    """提交**批量付款**（§4.4.4）的**唯一出口** —— PRG（`POST /m03/pay`）与 JSON API
    （`POST /api/m03/actions/batch-pay`）**共用这一份**：⛔ 不许两份判定、不许两份文案。

    管线（与 `act_pay` 原来的逐句一致，只是搬了个家）：
      ① `build_rows` 取数 ⇒ ② **以库里最新状态重算**（防"勾上之后才被改成不可付"；
         **撤单 / 剔除行一律排除** §4.2.7）⇒ ③ `confirm_batch` 判定（金额 / 方式 / 备注 / 状态）
      ⇒ ④ 有错 ⇒ **整批不产生任何流水**（不落半批）⇒ ⑤ **`request_id` 幂等**（拒重复提交）
      ⇒ ⑥ `flow_repo.create_flow` 逐条落流水（一次付款一条独立流水）。

    `drafts = {notice_id: {"pay_method": str, "amount": Decimal | None}}` —— 表单/JSON 给的值；
    ⚠️ 金额**已由调用方解析**成 `Decimal`（解析器在 `notice_http.parse_amount`，随删页一起搬 ✓）。
    `plan_methods` —— `单据号 -> 计划里的付款方式`（§4.4.2 的默认值来源；⛔ 本层不自己去查，
    免得与页面件耦合）。`cancel` / `move` 属**交互层**，留在调用方。

    返回 `(created, message)`：`created` = 落了流水的 `notice_id` 列表。
    """
    from app.core.money import to_money
    from app.mod03_notice.domain import PayDraft, PayRow, confirm_batch
    from app.mod03_notice.list_view import build_rows
    from app.mod05_flow import repository as flow_repo

    by_id = {r.notice_id: r for r in build_rows(session)}
    targets = [
        by_id[i] for i in ids
        if i in by_id and not by_id[i].i8_revoked and not by_id[i].excluded
    ]
    if not targets:
        raise MustReportError("没有可付款的行（勾选的单据可能已撤单 / 已被剔除）")

    pay_rows = [
        PayRow(notice_id=r.notice_id, approve_status=r.approve_status, payable=r.pay_amount)
        for r in targets
    ]
    plan = plan_methods or {}
    submitted = {}
    for r in targets:
        d = (drafts or {}).get(r.notice_id) or {}
        submitted[r.notice_id] = PayDraft(
            # ⚠️ 表单没给 ⇒ 用**与窗口渲染同一个出口**的默认值（§4.4.2）
            pay_method=str(d.get("pay_method") or default_pay_method(r.bill_no, plan)),
            amount=d.get("amount"),
        )

    result = confirm_batch(pay_rows, submitted, pay_date=str(pay_date or ""), remark=str(remark or ""))
    if result.errors:
        # **整批不产生任何流水**（不落半批）
        raise MustReportError("整批未产生任何流水 —— " + "；".join(result.errors[:6]))

    rid = str(request_id or "").strip()
    if flow_repo.has_request_id(session, rid):
        raise MustReportError(f"该提交（request_id={rid}）已经登记过流水 —— 已拒绝重复提交（§4.4.4）")

    created: list[int] = []
    total = Decimal("0")
    for item in result.flows:
        row = by_id[int(item["notice_id"])]
        flow_repo.create_flow(
            session,
            notice_id=row.notice_id,
            project_id=row.ownership_id,
            amount=item["amount"],
            pay_date=item["pay_date"],
            pay_method=item["pay_method"],
            request_id=rid,
        )
        total += to_money(item["amount"])
        created.append(int(item["notice_id"]))

    return created, (
        f"已登记 {len(result.flows)} 条付款流水，合计 {total:.2f} 元"
        "（一次付款一条独立流水）；相关通知书的已付金额与付款状态已随之更新"
    )


def manual_delete_impact(session, notice_id: int) -> dict:
    """**删除前的影响范围**（§7.2 / §9.4）的**唯一出口** —— ⛔ 前端不许自己拼这段文字。

    这是硬要求：**删除前必须列出影响范围**（关联数据、统计影响）。原先壳在弹窗里**本地算**这段
    （项目名 / 统计付款金额 / 已付金额 / 「欠款回增」那句）✗ ⇒ 现在由后端给，壳原样显示。
    ⚠️ 同一条 `assert_manual_editable`：**i8 抓取行永不可删**（§4.2.7）—— 连"影响范围"都不给看。
    """
    from app.mod03_notice import repository as repo

    row = repo.get_notice(session, int(notice_id))
    if row is None:
        raise MustReportError(f"要删除的行 {notice_id} 不存在")
    assert_manual_editable(row)

    # ⚠️ 金额列可能是 `None`（未取到 ≠ 0）⇒ 显示成 0.00 而不是抛异常（回执给人看，别 500）
    money = lambda v: f"{(v if v is not None else _ZERO):.2f}"   # noqa: E731
    settle = money(row.stat_settle)
    paid_stat = money(row.stat_paid)
    label = row.bill_no or row.ph_id
    return {
        "notice_id": int(row.id),
        "label": label,
        "project_name": row.project_name or "",
        "doc_date": row.doc_date or "",
        "stat_settle": settle,
        "stat_paid": paid_stat,
        "amount_paid": money(row.amount_paid),
        "effects": [
            f"该行的「统计付款金额」{paid_stat} 退出「逐月欠款台账」当月「付款」列（欠款**回增** {paid_stat}）",
            "「已付金额」不受影响（付款流水是另一份记录、不会跟着消失）",
            "该行是**人工补录**的记录 ⇒ 删除即移出列表、**不做软删**",
        ],
        "message": (
            f"⚠️ 删除前必须列出影响范围（§7.2 / §9.4）：删除后，该行（{label}）的"
            f"「统计付款金额」{paid_stat} 退出「逐月欠款台账」当月「付款」列（欠款**回增** {paid_stat}）；"
            "「已付金额」不受影响；该行是**人工补录**的记录，删除即移出列表、**不做软删**。"
        ),
    }


def apply_manual_delete(session, notice_id: int) -> tuple[object, str]:
    """**删除一条手动行**（§4.2.6）的**唯一出口** —— PRG（`POST /m03/notices/delete`）与 JSON API
    （`POST /api/m03/actions/manual-delete`）**共用这一份**：⛔ 不许两份校验、不许两份文案。

    ⚠️ `assert_manual_editable` 是那道铁律：**i8 抓取回来的行永不删**（§4.2.7 明确"不提供删除
       付款通知书按钮"）；本动作只服务**人工补录**的行 —— 删它 = 撤回自己的录入，欠款随取数实时重算。
    """
    from app.mod03_notice import repository as repo

    row = repo.get_notice(session, int(notice_id))
    if row is None:
        raise MustReportError(f"要删除的行 {notice_id} 不存在")
    assert_manual_editable(row)
    label = row.bill_no or row.ph_id
    repo.delete_notice(session, row)
    return row, f"已删除手动行「{label}」（只删这一行；欠款随取数实时重算）"


__all__ = [
    "CATEGORY_NAMES", "CATEGORY_CHOICES", "category_name",
    "CategoryChange", "change_category",
    "ExcludeReport", "manual_exclude",
    "RestoreReport", "restore_excluded",                       # 复用 classify（同一出口）
    "MANUAL_PH_PREFIX", "STAT_SETTLE_FIXED",
    "new_manual_ph_id", "is_manual_ph_id", "is_manual_row", "assert_manual_editable",
    "ManualRow", "manual_row_payload", "manual_project_options",
    "apply_stat_change",
    "EXCLUDE_BY_MANUAL", "EXCLUDE_BY_RULE", "EXCLUDE_NONE", "CATEGORY_MATERIAL",
]
