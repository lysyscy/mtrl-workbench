"""`MOD-03` **批量付款**（§4.4.2 / §4.4.4）的入参归一 ＋ 「唯一出口」。

依据：
- 付款方式默认值：通知书拟方式 →「现汇」（用户2026-10-15）；窗口与提交同口径。
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


def default_pay_method(planned_pay_method: str = "") -> str:
    """通知书拟付款方式未设置时默认现汇。"""
    return str(planned_pay_method or "现汇")


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
) -> tuple[list, str]:
    """提交**批量付款**（§4.4.4）的**唯一出口** —— PRG（`POST /m03/pay`）与 JSON API
    （`POST /api/m03/actions/batch-pay`）**共用这一份**：⛔ 不许两份判定、不许两份文案。

    管线（与 `act_pay` 原来的逐句一致，只是搬了个家）：
      ① 所选通知书 / 实际流水 / 关联批量取数 ⇒ ② **以库里最新状态重算**（防"勾上之后才被改成不可付"；
         **撤单 / 剔除行一律排除** §4.2.7）⇒ ③ `confirm_batch` 判定（金额 / 方式 / 备注 / 状态）
      ⇒ ④ 有错 ⇒ **整批不产生任何流水**（不落半批）⇒ ⑤ **`request_id` 幂等**（拒重复提交）
      ⇒ ⑥ `flow_service.create_flow` 逐条落流水（一次付款一条独立流水）。

    `drafts = {notice_id: {"pay_method": str, "amount": Decimal | None}}` —— 表单/JSON 给的值；
    ⚠️ 金额**已由调用方解析**成 `Decimal`（解析器 = 本模块的 `parse_amount` ✓）。
    `cancel` / `move` 属交互层，留在调用方。

    返回 `(created, message)`：`created` = 落了流水的 `notice_id` 列表。
    """
    from app.core.money import to_money
    from app.mod03_notice.domain import PayDraft, PayRow, confirm_batch
    from app.mod03_notice.repository import get_notices_by_ids
    from app.mod05_flow import service as flow_service
    from app.mod05_flow.domain import CATEGORY_MATERIAL, effective_total
    from app.mod11_jc import service as contracts

    selected_ids = list(dict.fromkeys(ids))
    by_id = {int(n.id): n for n in get_notices_by_ids(session, selected_ids)}
    flows: dict[int, list[dict]] = {}
    for f in flow_service.flows_of_notices(session, selected_ids):
        flows.setdefault(int(f.notice_id), []).append({"amount": f.amount, "status": f.status})
    links = contracts.links_by_notice(session, notice_ids=selected_ids)
    targets = [
        by_id[i] for i in selected_ids
        if i in by_id and not by_id[i].i8_revoked and not by_id[i].excluded
    ]
    if not targets:
        raise MustReportError("没有可付款的行（勾选的单据可能已撤单 / 已被剔除）")

    pay_rows = [
        PayRow(
            notice_id=int(r.id),
            approve_status=str(r.approve_status or ""),
            payable=to_money(r.amount_approved) - effective_total(flows.get(int(r.id), [])),
            # 人工统计金额不参与实付；集采闸仍由 PayRow.block 判定。
            category=str(r.category or "").strip() or CATEGORY_MATERIAL,
            jc_linked=bool(links.get(int(r.id))),
        )
        for r in targets
    ]
    submitted = {}
    for r in targets:
        d = (drafts or {}).get(int(r.id)) or {}
        submitted[int(r.id)] = PayDraft(
            # ⚠️ 表单没给 ⇒ 用**与窗口渲染同一个出口**的默认值（§4.4.2）
            pay_method=str(d.get("pay_method") or default_pay_method(r.planned_pay_method)),
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
            notice_id=int(row.id),
            project_id=row.ownership_id,
            amount=item["amount"],
            pay_date=item["pay_date"],
            pay_method=item["pay_method"],
            remark=str(remark or ""),
            request_id=rid,
        )
        total += to_money(item["amount"])
        created.append(int(item["notice_id"]))

    return created, (
        f"已登记 {len(result.flows)} 条付款流水，合计 {total:.2f} 元"
        "（一次付款一条独立流水）；相关通知书的已付金额与付款状态已随之更新"
    )


__all__ = [
    "default_pay_method", "parse_amount", "apply_batch_pay",
]
