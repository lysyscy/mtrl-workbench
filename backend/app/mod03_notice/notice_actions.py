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


__all__ = [
    "CATEGORY_NAMES", "CATEGORY_CHOICES", "category_name",
    "CategoryChange", "change_category",
    "ExcludeReport", "manual_exclude",
    "RestoreReport", "restore_excluded",                       # 复用 classify（同一出口）
    "MANUAL_PH_PREFIX", "STAT_SETTLE_FIXED",
    "new_manual_ph_id", "is_manual_ph_id", "is_manual_row", "assert_manual_editable",
    "ManualRow", "manual_row_payload", "manual_project_options",
    "EXCLUDE_BY_MANUAL", "EXCLUDE_BY_RULE", "EXCLUDE_NONE", "CATEGORY_MATERIAL",
]
