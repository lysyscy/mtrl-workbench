"""`MOD-03` 能力 4 —— **手动新增行**（§4.2.6）的判定 · 载荷组装 · **唯一出口**。

依据：
- 《说明书》§4.2.6（手动新增行：**统计结算金额恒 0 且不可改** · **录入人 = 当前登录用户** ·
  项目 = 全部已建档项目（含归档；**小微壳除外**）· **编辑 / 删除只对手动行开放** · 上限口径同样适用）
- §4.2.7（i8 抓取回来的行**永不改、永不删** —— 要改去 i8 改后重新抓取）
- §7.2 / §9.4（删除前**必须列出影响范围**）
- §9.8.2-5（一切写操作**按 id 定位**）

⚠️ 本模块只做**判定与字段组装**；落库在 `repository`、动作入口在 `notice_api_router`。
⚠️ 分类的合法性判定**复用** `notice_actions.CATEGORY_CHOICES` / `category_name`（同一出口）。

⚠️ **2026-09-21（`T5` 拆分）**：本件自 `notice_actions.py`（614 行）整块搬出 —— 那边此后只管
  分类 · 剔除 · 统计手改。⛔ 别再搬回去，也别在别处另写一份"手动行"判定（`apply_manual_save`
  与 `apply_manual_delete` 是**唯一出口**，有断言钉着）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.core.errors import MustReportError
from app.core.money import MoneyError, require_non_negative, to_money
from app.mod03_notice.models import EXCLUDE_NONE
from app.mod03_notice.notice_actions import CATEGORY_CHOICES, category_name
from app.mod05_flow.domain import classify

# 审批状态字面量 ⛔ **同一个出口**（§4.4.1 唯一需要识别的字面量 =「已批」，附录 E 枚举 = 已批 / 未批）
# —— 另有一处同值声明在 `mod02_i8.notice_source`，`tests/test_i8_contract.py` 钉着两处不漂移。
from app.mod03_notice.domain import APPROVE_STATUS_DONE

#: 审批状态的**合法取值**（附录 E：已批 / 未批，**无例外**）
APPROVE_STATUS_CHOICES: tuple[str, ...] = ("已批", "未批")

_ZERO = to_money(0)


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
    approve_status: str = "",
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

    # ⭐ 审批状态（§4.2.6「手动行一切信息都可改」＋ 附录 E 枚举 = 已批 / 未批；无例外）。
    # ⚠️ **空值落「已批」**（2026-10-08 修）：手动行**没有 i8 审批**，审批状态由人定；
    #    但旧实现**压根没这个字段**（前端没发、后端没收）⇒ 落库取列默认值 `""`
    #    ⇒ `PayRow.block()` 判「非已批」⇒ **手动行永远付不了款**（用户 2026-10-08 实测报障）。
    #    空值给「已批」而不是让它继续空着：空 ⇒ 看不见原因、也付不了，比给个默认值更坏。
    astat = str(approve_status or "").strip()
    if not astat:
        astat = APPROVE_STATUS_DONE
    if astat not in APPROVE_STATUS_CHOICES:
        raise MustReportError(
            f"审批状态只能是「{' / '.join(APPROVE_STATUS_CHOICES)}」（附录 E），没有其它取值"
        )

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
        "approve_status": astat,
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
    "MANUAL_PH_PREFIX", "STAT_SETTLE_FIXED", "APPROVE_STATUS_CHOICES",
    "new_manual_ph_id", "is_manual_ph_id", "is_manual_row", "assert_manual_editable",
    "ManualRow", "manual_row_payload", "manual_project_options",
    "apply_manual_save",
    "manual_delete_impact", "apply_manual_delete",
]
