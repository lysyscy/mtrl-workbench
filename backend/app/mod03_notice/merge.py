"""再次导入的**合并规则**（§4.2.7）—— 纯函数。

抓取是**按月全量**的、同一批单据会被反复抓（i8 那边改了单再抓一次），所以"已抓回来的行怎么合并"
必须有确定口径。本模块只回答一件事：**这条新抓回来的记录，该往现有行上写哪些字段、要提醒什么**。

## 口径（§4.2.7，判据 = **留痕**）

| 字段 | 再次导入时 |
|---|---|
| 审批金额（**唯一 i8 源字段**） | **跟随 i8 新值**（源数据；"不被覆盖"指的是**不被人工改覆盖**，不是不被 i8 覆盖） |
| 统计结算金额 / 统计付款金额 | **未手改**（无留痕）⇒ 跟随新审批金额；**手改过** ⇒ **保留人工值**（两个字段**各判各的**） |
| 分类 / 集采实际供应商 / 调整单 / **剔除标记** / **i8 已撤单标记** | **一律不被覆盖** |
| 归属（`ownership_id`） | 不被覆盖（§9.8 铁律 5/6：按档案 id 写入） |

## 两条容易漏的

- **越界只提醒、不改数**：已手改的统计值若因 i8 把审批金额**调小**而越界（> 新审批金额），
  系统**只提醒、绝不代替用户改写**（自动下调会丢掉"油卡抵扣"这类**业务判断**，且不留痕、事后查不出来）。
- **值没变就不动**：本次抓回的审批金额与现有值**相同** ⇒ **什么都不做**（不做无意义的"重算"）。

⚠️ 判据为什么用留痕而不是"是否手改"开关：留痕本就是"这条被人工改过没有"的**既有事实来源**，
   另开状态位等于把同一件事存两份 —— 而**副本必然静默过期**（§4.2.7 原话）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.core.money import to_money
from app.mod03_notice.domain import (
    F_STAT_PAID,
    F_STAT_SETTLE,
    STAT_LABELS,
    default_stat_value,
    stat_value_on_reimport,
)

# 跟随 i8 的字段（源数据 + 派生自源数据的映射）
SOURCE_FOLLOWED: tuple[str, ...] = (
    "bill_no", "bill_type", "project_name", "approve_status", "doc_date",
    "biz_type", "payee", "input_by", "amount_approved", "fields",
)

# **不被覆盖**的字段（§4.2.7 表：分类 / 剔除 / 撤单 / 归属）
# ⚠️ §4.2.7 表里还有「集采实际供应商」与「调整单」两项 —— 它们分别属 **M5（MOD-11 集采域）**
#    与 **M4（付款计划的调整单）**，本表尚无对应列；到那两个模块落地时**并入本元组**即可。
PROTECTED: tuple[str, ...] = (
    "category", "excluded", "exclude_source", "i8_revoked", "revoked_joint",
    "ownership_id",
)

# 按留痕判定的两个旁路统计字段
TRACED_FIELDS: tuple[str, ...] = (F_STAT_SETTLE, F_STAT_PAID)


@dataclass
class MergePlan:
    """合并结论：**只含真需要写的字段**（不用改的键不会出现在 `values` 里）。"""

    values: dict = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.values)


def _same(a, b) -> bool:
    """值是否相同（金额按 `numeric(18,2)` 比；其余按字符串比）。"""
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        try:
            return to_money(a) == to_money(b)
        except Exception:  # noqa: BLE001
            return str(a) == str(b)
    return str(a if a is not None else "") == str(b if b is not None else "")


def plan_merge(
    current: dict,
    incoming: dict,
    traces=None,
    *,
    notice_id: int = 0,
) -> MergePlan:
    """现有行 `current` ＋ 新抓回 `incoming`（＋留痕 `traces`）→ 该写什么、该提醒什么。

    `current` / `incoming` 都是**普通字典**（键 = `payment_notice` 的列名）—— 不碰 ORM，
    以便完全离线单测（§4.2.7 的合并规则值得被钉住）。
    """
    plan = MergePlan()

    # ① 源字段：**跟随 i8**（只写"真的变了"的）
    for key in SOURCE_FOLLOWED:
        if key not in incoming:
            continue
        if not _same(current.get(key), incoming.get(key)):
            plan.values[key] = incoming[key]

    approved_new = to_money(incoming.get("amount_approved", current.get("amount_approved") or 0))
    approved_old = to_money(current.get("amount_approved") or 0)

    # ② 统计两金额：按留痕（未手改跟随 / 手改保留）；
    #    ⚠️「值没变就不动」—— 审批金额没变 ⇒ **连重算都不做**
    if not _same(approved_old, approved_new):
        for field_name in TRACED_FIELDS:
            new_value = stat_value_on_reimport(
                field=field_name,
                current=current.get(field_name),
                approved_new=approved_new,
                traces=traces,
                notice_id=notice_id,
            )
            # 越界只提醒、绝不代替用户改写（自动下调会丢掉业务判断）
            if new_value > approved_new:
                label = STAT_LABELS.get(field_name, field_name)
                plan.alerts.append(
                    f"{label}（{new_value}）已超过新的审批金额（{approved_new}）—— "
                    "**保留人工值**，请自行复核是否要调整"
                )
            if not _same(current.get(field_name), new_value):
                plan.values[field_name] = new_value

    # ③ 被保护的字段：**一个都不写**（分类 / 供应商 / 调整单 / 剔除 / 撤单 / 归属）
    for key in PROTECTED:
        plan.values.pop(key, None)

    return plan


def apply_placement_to_new(placement, incoming: dict, *, paid_total=0,
                           ownership_id: int | None = None) -> dict:
    """**新行**的初始赋值：分类 / 剔除 / 剔除来源（§4.2.2 / §4.2.3）
    ＋ **统计两金额的初值**（§4.2.5 / §4.4.7：统计结算金额 = 审批金额、
    ⭐ 统计付款金额 = **已付金额**（`paid_total`，该单已有的有效流水汇总 —— 首次落库通常是 0，
    但"补抓一个已导过流水的月份"时必须带上真实值）。

    ⚠️ 只用于**首次落库**。已存在的行**永不**用这几个字段去覆盖（§4.2.7「剔除标记不被覆盖」、
       §4.2.4「分类不被覆盖」、§4.2.5「统计两金额保护人工值」）
       —— 所以 `plan_merge()` 里它们落在 `PROTECTED` / 留痕判定里。
    """
    approved = incoming.get("amount_approved") or 0
    return {
        **incoming,
        "category": placement.category,
        "excluded": placement.excluded,
        "exclude_source": placement.exclude_source,
        # ⭐ **归属**（§2.5.1 链路 C）—— 落在 `**incoming` **之后**，确保它说了算。
        #    抓取链路已在**入库前**整批校验「归属未走完 ⇒ 整批不入库」（§2.7.4 / `ACC-PRJ-OWN-001`），
        #    所以走到这里的一定是**已判定**的 id（小微或普通项目）——⛔ 不会是 None。
        "ownership_id": ownership_id,
        "stat_settle": default_stat_value(F_STAT_SETTLE, approved=approved, paid_total=paid_total),
        "stat_paid": default_stat_value(F_STAT_PAID, approved=approved, paid_total=paid_total),
    }


__all__ = [
    "SOURCE_FOLLOWED", "PROTECTED", "TRACED_FIELDS",
    "MergePlan", "plan_merge", "apply_placement_to_new",
]
