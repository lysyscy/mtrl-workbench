"""`MOD-03` **批量付款**（§4.4.2 / §4.4.4）的入参归一 ＋ 「唯一出口」。

依据：
- 《说明书》§4.4.2（付款方式默认值：先取付款计划、取不到兜底「现汇」—— **窗口渲染与提交同一个出口**）
- §4.4.4（批量付款：整批判定 ⇒ **不落半批** · `request_id` **幂等** · 一次付款一条独立流水）
- §4.4.3（集采付款：**未关联集采合同 ⇒ 不可付**——用户 2026-09-24 口述，**无例外**）
- §4.2.7（撤单 / 剔除行一律排除）

⚠️ 本模块只做**判定与落库编排**；落库在 `mod05_flow.repository`、动作入口在 `notice_api_router`。
⚠️ `parse_amount` 只做**格式**归一（去千分位），**不做业务判断** —— 上限 / 正负 / 可否为空由 `domain` 判。

⚠️ **2026-09-21（`T5` 拆分）**：本件自 `notice_actions.py`（614 行）整块搬出（那两个出口原住
  `notice_pay.py` / `notice_http.py` 这类**会被删的页面件**，2026-09-19 先搬进 `notice_actions`，
  再于本日挪到本件 —— 落脚点变了，**判定一行没变**）。
  ⛔ 别再搬回去：`tools/_mut_m03pay.py`（反向灵敏度）按**本件路径**定位变异点，搬动会静默失效。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.errors import MustReportError
from app.core.money import amount_text, to_money


# ======================================================== 批量付款（§4.4.2 / §4.4.4）


def default_pay_method(bill_no: str, plan_methods: dict) -> str:
    """**实际付款方式的默认值**（§4.4.2，**唯一出口**）：先取付款计划的值、取不到兜底「现汇」。

    ⚠️ 窗口渲染与提交重算**必须走同一个出口** —— 否则会出现"页面上显示承兑、提交时说付款方式为空"。
    ⚠️ 2026-09-19（`§19` 批 4 · S3a）：**从 `notice_pay.py` 搬到这里**（那是**会被删**的页面件，本件是存活件 ✓）
    —— `notice_pay.py` 现在反向 import 它（临时，随删页一起消失 ✓）。⛔ 别在两边各留一份实现。
    """
    return str((plan_methods or {}).get(str(bill_no or "").strip()) or "") or "现汇"


def plan_methods_for_pay(session) -> dict[str, str]:
    """`单据号 -> 付款计划的付款方式` —— §4.4.2 默认值的**取数出口**（`default_pay_method` 的输入）。

    ⚠️ 2026-09-19（`§19` 批 4 · **S4②**）：**从 `notice_pay.py` 搬到这里**（那是**会被删**的页面件）
       —— 批量付款的**两个出口**（PRG 与 JSON API）都从本件取它。⛔ 别在别处再写一份同样的查询。
    ⚠️ 付款计划没导入 / 表还没建时**不该让付款窗口打不开** ⇒ 兜底空表（由 `default_pay_method` 兜「现汇」）。
    """
    try:
        from app.mod04_plan import service as P4S       # ⭐ 包间出口（`TAIL-218` 批 3）

        return {
            str(r.doc_no or "").strip(): str(r.pay_method or "")
            for r in P4S.list_rows(session)
            if str(r.doc_no or "").strip() and str(r.pay_method or "").strip()
        }
    except Exception:  # noqa: BLE001
        return {}


def parse_amount(text):
    """把表单 / JSON 里的金额文本解析为 `Decimal`（空 ⇒ `None` = 未手改、取「本次应付」）。

    ⚠️ 2026-09-19（`§19` 批 4 · **S4②**）：**从 `notice_http.py` 搬到这里**（那是**会被删**的页面件）。
    ⚠️ 只做**格式**归一（去千分位），**不做业务判断** —— 上限 / 正负 / 可否为空一律由 `domain` 判。
    """
    raw = amount_text(text)          # ⭐ `TAIL-63`：洗净归到 `app/core/money.py`（原来只去逗号 ⇒ 带 ¥ 会被拒）
    return to_money(raw) if raw else None


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
      ⇒ ⑥ `flow_service.create_flow` 逐条落流水（一次付款一条独立流水）。

    `drafts = {notice_id: {"pay_method": str, "amount": Decimal | None}}` —— 表单/JSON 给的值；
    ⚠️ 金额**已由调用方解析**成 `Decimal`（解析器 = 本模块的 `parse_amount` ✓）。
    `plan_methods` —— `单据号 -> 计划里的付款方式`（§4.4.2 的默认值来源；⛔ 本层不自己去查，
    免得与页面件耦合）。`cancel` / `move` 属**交互层**，留在调用方。

    返回 `(created, message)`：`created` = 落了流水的 `notice_id` 列表。
    """
    from app.core.money import to_money
    from app.mod03_notice.domain import PayDraft, PayRow, confirm_batch
    from app.mod03_notice.list_view import build_rows
    from app.mod05_flow import service as flow_service      # ⭐ 包间出口（§2.3 · `TAIL-195` 批 2a）

    by_id = {r.notice_id: r for r in build_rows(session)}
    targets = [
        by_id[i] for i in ids
        if i in by_id and not by_id[i].i8_revoked and not by_id[i].excluded
    ]
    if not targets:
        raise MustReportError("没有可付款的行（勾选的单据可能已撤单 / 已被剔除）")

    pay_rows = [
        PayRow(
            notice_id=r.notice_id,
            approve_status=r.approve_status,
            payable=r.pay_amount,
            # ⭐ ⑤ 集采未关联不可付（§4.4.3）：两样都取自 `NoticeRow` ——
            #    `build_rows` 已把分类与「有没有关联」**一次查完**（`_links_by_notice`，⛔ 无 N+1），
            #    本层**不另查库**、也不另判一遍（判定唯一出口 = `domain.PayRow.block()`）。
            category=r.category,
            jc_linked=r.has_link,
        )
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
    if flow_service.has_request_id(session, rid):
        raise MustReportError(f"该提交（request_id={rid}）已经登记过流水 —— 已拒绝重复提交（§4.4.4）")

    created: list[int] = []
    total = Decimal("0")
    for item in result.flows:
        row = by_id[int(item["notice_id"])]
        flow_service.create_flow(
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


__all__ = [
    "default_pay_method", "plan_methods_for_pay", "parse_amount", "apply_batch_pay",
]
