"""`MOD-11` 集采台账 · **装配层**（把仓储行 + 域内核算成"页面要的形状"；⛔ 不写判定）。

⭐ 本层是**派生金额的唯一落点**：发票合计 / 付款合计 / 结算 / 欠款**全部现场算**
   （`domain.contract_amounts`）—— §6.4.1 末行要求"派生显示、不单独存储"，
   判据 `ACC-JC-UI-001/001-09` 要的"**改子表即改欠款**"就是靠"每次现算"满足的。

⚠️ 出参是**语义形状**；转成原型演示形状是**壳适配层**的职责（后端出语义、前端 `adapt*` 转形）。
⚠️ 金额在 `api` 层转字符串（`numeric(18,2)` 精度保护）⇒ 本层照实回 `Decimal`。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.mod11_jc import domain as D
from app.mod11_jc import repository as R
from app.mod11_jc.models import (
    INVOICE_KINDS,
    SRC_MANUAL,
    SRC_NOTICE,
    SUBOP_INVOICE_ADD,
    SUBOP_INVOICE_DEL,
    SUBOP_PAYMENT_ADD,
    SUBOP_PAYMENT_DEL,
    TAG_IN,
    JcInvoice,
    JcPayment,
)
from app.core.money import sum_money


def plan_audit_contexts(connection, *, lock=False):
    return R.plan_audit_contexts(connection, lock=lock)


def settlement_totals_by_project(s: Session, warehouse_keys: set[str]) -> dict[str, Decimal]:
    """同会话批量读取纳入合同的结算；无合同为0，空项目集合不查询。"""
    totals = dict.fromkeys(warehouse_keys, D.ZERO)
    if not totals:
        return totals
    rows = [r for r in list_contracts(s, tags=[TAG_IN]) if r["project_key"] in totals]
    invoices = R.invoices_of_many(s, [r["id"] for r in rows])
    for r in rows:
        totals[r["project_key"]] += D.settle_amount(
            trade_co=r["trade_co"], invoices=invoices.get(r["id"], []))
    return totals


def build_list(s: Session, *, tags: list[str] | None = None, arch: str = "",
               supplier: str = "", project_key: str = "") -> dict:
    """集采台账**主表**（含派生金额与合计行）—— 判据 `ACC-JC-UI-001/001-02` / `001-11` 的数据源。

    ⚠️ **筛选后的行数就是 `count`**；判据要求「筛选后行数 = **独立复算**、**复位后回到全量**」⇒
       本函数**不缓存、不带隐式默认筛选**（不给参数 = 全量）。
    """
    sequences = D.project_sequences(list_contracts(s))
    rows = list_contracts(s, tags=tags, arch=arch, supplier=supplier, project_key=project_key)
    inv_map = R.invoices_of_many(s, [r["id"] for r in rows])
    pay_map = R.payments_of_many(s, [r["id"] for r in rows])

    out: list[dict] = []
    totals = {k: D.ZERO for k in D.SUM_KEYS}
    for r in rows:
        amounts = D.contract_amounts(
            trade_co=r["trade_co"],
            invoices=inv_map.get(r["id"], []),
            payments=pay_map.get(r["id"], []),
        )
        row = {**r, **amounts, "project_seq": sequences.get(r["id"])}
        # ⭐ **本行引用过的付款通知书 id**（`M5-7` 接线时补 —— 子表**本来就在内存里**，只差带出来）。
        # ⚠️ 为什么必须带：`m03`（付款通知书页）的「集采关联」是**反查**的 ——
        #    `jcUsedNids`（全库已引用集合）· `jcRefOf`（这条被哪张合同引用）· `jcLinkCands`（候选）
        #    全都按"合同行的付款子表里有没有这个通知书 id"来判。**不带 ⇒ 它们静默变空**
        #    （候选列表消失，页面看起来只是"没数据"，不报错）—— 这正是"接后端时最该防"的那类错。
        # ⛔ 只给 **id 集合**，⛔ 不搬整张子表（那是 `/api/m11/detail` 的活）。
        row["notice_ids"] = [int(p["notice_id"]) for p in (pay_map.get(r["id"]) or [])
                             if p.get("notice_id") is not None]
        for k in D.SUM_KEYS:
            totals[k] = totals[k] + Decimal(str(row.get(k) or 0))
        out.append(row)

    return {
        "rows": out,
        "count": len(out),
        "totals": {k: v.quantize(Decimal("0.01")) for k, v in totals.items()},
        "columns": [dict(c) for c in D.JC_COLUMNS],
        "sum_keys": list(D.SUM_KEYS),
        "projects": R.project_choices(s),
    }


def payment_display_rows(s: Session, payments: list[dict]) -> list[dict]:
    """统计与实付一致才按笔展示；关联与合同金额仍用原始付款行。"""
    from app.mod05_flow import service as flows

    ids = [int(p["notice_id"]) for p in payments if p["source"] == SRC_NOTICE and p["notice_id"] is not None]
    by_notice: dict[int, list] = {}
    for f in flows.flows_of_notices(s, ids):
        if f.status == "effective":
            by_notice.setdefault(f.notice_id, []).append(f)
    out = []
    for p in payments:
        if p["source"] != SRC_NOTICE:
            out.append({**p, "display_kind": "manual"})
            continue
        live = by_notice.get(p["notice_id"], [])
        if not live and p["amount"] == 0:
            continue
        if live and p["amount"] == sum_money(f.amount for f in live):
            out.extend({**p, "date": f.pay_date, "amount": f.amount,
                        "flow_id": f.id, "display_kind": "flow"} for f in live)
        else:
            out.append({**p, "display_kind": "stat", "mismatch": True})
    return out


def notice_payment_effect(s: Session, notice_id: int) -> dict | None:
    """读取关联合同的付款合计，供撤销事务前后回执使用。"""
    link = R.payment_of_notice(s, notice_id)
    if link is None:
        return None
    c = R.contract_of(s, link.contract_id)
    amounts = D.contract_amounts(trade_co=c.trade_co, invoices=R.invoices_of(s, c.id),
                                 payments=R.payments_of(s, c.id))
    return {"contract_id": c.id, "pay_sum": amounts["pay_sum"]}


def _link_candidates(s: Session, notice_ids: list[int], *, supplier: str | None = None):
    """批量读取候选事实；逐条产出，避免为整批通知书同时复制全部候选。"""
    from app.mod01_projects import service as projects
    from app.mod03_notice import service as notices

    ids = list(dict.fromkeys(notice_ids))
    if not ids:
        return
    by_id = {n.id: n for n in notices.get_notices_by_ids(s, ids)}
    keys = {p.id: str(p.warehouse_name or '') for p in projects.all_projects(s)}
    contracts = list_contracts(s)
    sequences = D.project_sequences(contracts)
    links = R.links_by_notice(s, ids)
    for nid in ids:
        notice = by_id.get(nid)
        key = keys.get(notice.ownership_id, '') if notice else ''
        current = next(iter(links.get(nid, [])), None)
        rows = D.pick_candidates(contracts=contracts, project_key=key,
                                 supplier=notice.jc_supplier if supplier is None else supplier, current_id=current) if notice else []
        yield {'notice_id': nid, 'notice': notice, 'project_key': key, 'current_contract_id': current,
               'rows': [{**r, 'project_seq': sequences.get(r['id'])} for r in rows]}


def link_recommendations(s: Session, notice_id: int, *, supplier: str | None = None) -> dict:
    """按现有候选范围批量带回发票与推荐证据；不选择、不保存关联。"""
    from app.mod03_notice import service as notices

    context = next(_link_candidates(s, [notice_id], supplier=supplier))
    notice = context['notice']
    if notice is None or (notice.category != 'jc' or notice.excluded or notice.i8_revoked) and not context['current_contract_id']:
        return {'ok': False, 'message': '找不到可关联的集采通知书'}
    key, current, rows = context['project_key'], context['current_contract_id'], context['rows']
    read_only = notice.category != 'jc' or notice.excluded or notice.i8_revoked
    if read_only:
        rows = [r for r in rows if r['id'] == current]
    actual_supplier = next((r['supplier'] for r in rows if r['id'] == current), notice.jc_supplier)
    ids = [r['id'] for r in rows]
    invoices = R.invoices_of_many(s, ids)
    payments = {cid: [p for p in values if p.get('notice_id') != notice_id]
                for cid, values in R.payments_of_many(s, ids).items()}
    linked_ids = {p['notice_id'] for values in payments.values() for p in values if p.get('notice_id') is not None}
    prior = {n.id: n for n in notices.get_notices_by_ids(s, sorted(linked_ids))
             if n.category == 'jc' and not n.excluded and (not n.i8_revoked or n.revoked_joint)}
    for row in rows:
        row['invoices'] = invoices.get(row['id'], [])
        paid = payments.get(row['id'], [])
        row.update(D.contract_amounts(trade_co=row['trade_co'], invoices=row['invoices'], payments=paid))
        row['notice_ids'] = [int(p['notice_id']) for p in paid if p.get('notice_id') is not None]
        row['supplier_uninvoiced'] = row['contract_amt'] - row['inv_sum']
        row['trade_uninvoiced'] = (row['trade_contract_amt'] - row['trade_inv_sum']
                                    if row['trade_contract_amt'] is not None else None)
        linked = [{'code': prior[nid].bill_no, 'amount': prior[nid].amount_approved}
                  for nid in row['notice_ids'] if nid in prior]
        row['recommendation'] = D.recommend_link(amount=notice.amount_approved, title=(notice.fields or {}).get('BillName', ''),
                                         contract_no=row['contract_no'], trade_co=row['trade_co'],
                                         invoices=row['invoices'], linked_notices=linked)
        if row['project_key'] != key:
            row['recommendation']['reasons'] = []
    rows.sort(key=lambda r: (not bool(r['date']), r['date'], r['id']))
    return {'ok': True, 'notice_amount': str(notice.amount_approved), 'current_contract_id': current,
            'notice_title': (notice.fields or {}).get('BillName', ''),
            'supplier': actual_supplier, 'read_only': bool(read_only), 'project_key': key, 'rows': rows}


def build_detail(s: Session, contract_id: int) -> dict | None:
    """单个合同的**明细**（两张发票子表 + 付款子表 + 派生金额）—— 子表弹窗的数据源。

    ⚠️ 两张发票子表**同款同规则**（§6.4.2）⇒ 这里按 `kind` 分组返回，⛔ 不写两套取数。
    """
    c = R.contract_of(s, contract_id)
    if c is None:
        return None
    invoices = R.invoices_of(s, contract_id)
    payments = R.payments_of(s, contract_id)
    amounts = D.contract_amounts(trade_co=c.trade_co, invoices=invoices, payments=payments)
    return {
        "id": c.id,
        "project_seq": D.project_sequences(list_contracts(s)).get(c.id),
        "contract_no": c.contract_no,
        "date": c.contract_date,
        "material": c.material_name,
        "supplier": c.supplier,
        "contract_amt": c.contract_amt,
        "trade_co": c.trade_co,
        "trade_contract_amt": c.trade_contract_amt,
        "payment_term": c.payment_term,
        "payment_method": c.payment_method,
        "remark": c.remark,
        "tag": c.tag,
        "arch": c.arch,
        "arch_no": c.arch_no,
        "ret_date": c.ret_date,
        "supplier_invoices": [r for r in invoices if r["kind"] != "trade"],
        "trade_invoices": [r for r in invoices if r["kind"] == "trade"],
        "payments": payments,
        "payment_display_rows": payment_display_rows(s, payments),
        **amounts,
    }


def debt_of_ledger(s: Session, *, rows: list[dict] | None = None) -> Decimal:
    """**集采欠款合计**（⭐ **只计「纳入台账」**的合同）—— 供付款域**注入**用（`TAIL-100`）。

    ⚠️ **为什么必须有它**：付款域的口径是「集采欠款**不在本域算** —— 由集采台账负责」
       （§4.5.1 / 判据 `ACC-FLOW-DEBT-001/001-03`）⇒ 那边**需要一个注入方**。
       而原先这个"注入方"**从来没人实现** ⇒ 看板与欠款页的「集采欠款」**恒 ¥0.00**
       （少算 7444 万级、页面还完全看不出来 —— 典型的「看着正常的错数」）。
    ⭐ **唯一出口**：算法留在集采域（⛔ 付款域不自己 sum），取值走 `build_list`
       ⇒ 与**集采台账页**显示的「集采欠款」**必然是同一个数**。
    `rows` 可传入同一请求已装配的集采行，避免为合计再次读取。
    """
    total = D.ZERO
    for r in build_list(s)["rows"] if rows is None else rows:
        if str(r.get("tag") or "") == TAG_IN:
            total += Decimal(str(r.get("debt") or 0))
    return total.quantize(Decimal("0.01"))


# ============================================================ 写动作（`M5-4`）
# ⚠️ 判定（三态归一 / 子表校验 / 去重）一律调 `domain` 出口；本层只做**编排 ＋ 回执**。
# ⚠️ 回执统一形状 `{"ok", "kind", "message", ...}`（同 `m09` 手写动作的口径）；⛔ 不抛业务异常。

#: 手工新增 / Excel 导入的**两态默认值** = 「纳入台账」。
#: 依据：判据 `ACC-JC-FETCH-001/001-07` **原文**就是「三态默认值 = 纳入台账」（现为两态）。
#: ⭐ `TAIL-97`（用户 2026-09-25 取消「待确认」）之后：**抓取与手工新增的默认值已经合流**
#:   —— 两条路都是 `TAG_IN`（`models.JcContract.tag` 的列默认也一并改成它）。
#:   ⚠️ 本常量**保留**：它仍是"人工新增这一条路"的名义出口（判据 `001-07` 指着它）。
DEFAULT_TAG_ON_CREATE = TAG_IN


def act_add_contract(s: Session, *, project_id: int, **fields) -> dict:
    """手工新增合同 ⇒ **建档**（判据 `ACC-JC-UI-001/001-13`「保存真的建档」）。

    ⚠️「取消不入库」= 前端**不调本接口**（本接口一旦被调用就落库）⇒ 本层⛔ 没有"草稿态"。
    """
    try:
        fields = D.normalize_payment_fields(fields)
    except ValueError:
        return {"ok": False, "kind": "err", "message": "账期请填写非负整数 x±y天，合同付款方式请选择候选值"}
    tag = D.normalize_tag(fields.pop("tag", None) or DEFAULT_TAG_ON_CREATE)
    row = R.insert_contract(s, project_id=int(project_id), tag=tag, **fields)
    return {"ok": True, "kind": "ok", "id": int(row.id), "tag": tag,
            "message": f"已建档（三态 = 「{tag}」）"}


def act_set_tag(s: Session, *, contract_id: int, tag) -> dict:
    """单条三态标记（判据 `001-03` 的"逐条"那一半）。"""
    t = D.normalize_tag(tag)
    if not R.set_tag(s, contract_id, t):
        return {"ok": False, "kind": "err", "message": f"找不到合同 {contract_id}"}
    return {"ok": True, "kind": "ok", "id": int(contract_id), "tag": t,
            "message": f"已标记为「{t}」"}


def act_batch_tag(s: Session, *, contract_ids, tag) -> dict:
    """**批量**三态标记（判据 `001-03` 的"批量"那一半 ＋ `001-05`）。

    ⭐ `001-05` 的三条：**只作用于勾选行** · **动作后清空勾选** · **不改行数**
    ⇒ 返回 `affected_ids`（壳据此清空**刚标过的那些**勾选），并返回**前后行数**
    （把"不改行数"做成**可观测**的 —— 断言另用 SQL 独立复算，⛔ 不靠本接口自证）。
    """
    t = D.normalize_tag(tag)
    ids = [int(i) for i in (contract_ids or ())]
    if not ids:
        return {"ok": False, "kind": "err", "message": "请先勾选要标记的行", "affected_ids": []}
    before = R.count_contracts(s)
    affected = R.set_tags(s, ids, t)
    after = R.count_contracts(s)
    return {"ok": True, "kind": "ok", "tag": t, "affected_ids": affected,
            "count": len(affected), "row_count_before": before, "row_count_after": after,
            "message": f"已把 {len(affected)} 行标记为「{t}」"}


def act_update_contract(s: Session, *, contract_id: int, **cols) -> dict:
    """主表可改列（备注 / 收发登记三列 / 金额…）—— 判据 `001-12`「可手改并落值」。

    ⚠️ 白名单在 `repository.EDITABLE_COLS`（三态**不在其中** ⇒ 它走 `act_set_tag`）。
    """
    if "method" in cols:
        return {"ok": False, "kind": "err", "message": "旧付款条件字段已停用，请填写账期和合同付款方式"}
    try:
        cols = D.normalize_payment_fields(cols)
    except ValueError:
        return {"ok": False, "kind": "err", "message": "账期请填写非负整数 x±y天，合同付款方式请选择候选值"}
    if not R.update_contract(s, contract_id, **cols):
        return {"ok": False, "kind": "err", "message": f"找不到合同 {contract_id}"}
    return {"ok": True, "kind": "ok", "id": int(contract_id), "message": "已保存"}


# ------------------------------------------------- 子表操作的可靠保存（局部 · 标识幂等）
#
# ⭐ 用户口径（2026-11-03）：子表增删**带标识**的重复请求 ⇒ 回放原回执，⛔ 不重复产生 / 删除事实；
#    同标识换动作 / 换参数 / 换账号 ⇒ **明确拒绝**；⛔ 绝不"日期金额一样就当同一笔"。
# ⚠️ 只有**带了**标识的调用才走这套（没带的照旧执行 —— 迁移前的前端仍在用）。
# ⚠️ 回执与本函数的业务变更在**同一个 `session`** 里落 ⇒ `session_scope()` 一次性提交 / 回滚
#    ⇒ 事务失败**不会**留下"成功回执"，也不会留下半截事实。

def subtable_account() -> str:
    """回执归属的账号 = **登录会话身份**（`current_name()`）；未登录 ⇒ 空串（回执对谁都不回）。

    ⚠️ 刻意**不**回落到 `current_operator()`：那是"人"的展示名，可以多人共用一个占位；
       回执是"谁提交的"这件事，必须按可校验的账号身份隔离（判据：别的账号读不到我的回执）。
    """
    from app.core.session import current_name
    return str(current_name() or "").strip()


def _request_key(raw) -> str:
    """归一操作标识（空 / `None` ⇒ `""` = 老调用）；不合法返回 `""` 并由调用方回错误文案。"""
    try:
        return D.request_key(raw)
    except ValueError:
        return ""


def _request_conflict(key: str) -> dict:
    return D.subtable_result_conflict(key)


def _replay(s: Session, *, key: str, action: str, **fields) -> dict | None:
    """命中回执 ⇒ 回放原成功回执；同键换了内容 / 换了账号 ⇒ 拒绝；未命中 ⇒ `None`（照常执行）。

    ⚠️ 比对的是「动作 ＋ 参数 ＋ 账号」的摘要（`D.request_hash`）⇒ 内容变了**必须**拒绝，
       ⛔ 不能因为"看起来像同一笔"就重新执行（那正是重复付款 / 重复发票的入口）。
    """
    if not key:
        return None
    row = R.subtable_operation_by_request(s, key)
    if row is None:
        return None
    if str(row.account or "") != subtable_account():
        return _request_conflict(key)
    if str(row.request_hash or "") != D.request_hash(action=action, **fields):
        return _request_conflict(key)
    return dict(row.result or {})


def _remember(s: Session, *, key: str, action: str, result: dict, fields: dict,
              row_id: int | None = None, contract_id: int | None = None) -> None:
    """记下这次操作的**成功**回执（与业务变更同事务）—— ⚠️ 只有成功路径才调用。

    ⚠️ 摘要只按 `fields`（= 请求里**本来就有**的东西）算 ⇒ 重放时客户端还能算出一模一样的摘要；
       而增行得到的**新行 id** 是执行结果、不是请求参数 ⇒ 只进 `row_id` 列、⛔ 不进摘要
       （进了摘要就永远匹配不上，重放会退化成"同键不同内容"被拒）。
    ⚠️ `contract_id` / `row_id` 只从**一处**取（两份来源会变成"同名关键字传两次"的 `TypeError`）。
    ⚠️ 删行请求本身不带 `contract_id` ⇒ 由调用方**在删之前**从那一行读出来传进来（只落列、不进摘要）：
       回执要能说清"这次删的是哪份合同的子表行"，⛔ 但行没了之后不能再要求重新算摘要。
    """
    if not key:
        return
    contract = fields.get("contract_id")
    R.insert_subtable_operation(
        s, request_id=key, account=subtable_account(), action=action,
        contract_id=int((contract if contract_id is None else contract_id) or 0),
        row_id=int(fields.get("row_id") if row_id is None else row_id),
        request_hash=D.request_hash(action=action, **fields), result=result)


def subtable_operation(s: Session, *, request_id) -> dict:
    """`GET /api/m11/subtable-operation` 的读出口 —— 只回**当前账号自己**的回执。

    ⚠️ 未登录 / 没查到 / 是别人的 ⇒ 一律 `{"ok": True, "status": "not_found"}`：
       ⛔ 不区分"没这条"和"不是你的"（那等于泄露别人的操作存在性）。
    """
    key = _request_key(request_id)
    if not key:
        return D.subtable_operation_missing()
    row = R.subtable_operation_of_account(s, account=subtable_account(), request_id=key)
    if row is None:
        return D.subtable_operation_missing()
    return D.subtable_operation_of(row)


def act_add_invoice(s: Session, *, contract_id: int, kind: str, date, amount,
                    request_id: str | None = None) -> dict:
    """发票子表增行（供应商 / 贸易公司**同款**）—— 校验走 `D.invoice_problem`（判据 `001-05`）。

    ⭐ 带 `request_id` 时幂等：重复请求回放原回执，⛔ 不重复增行（见上方"可靠保存"注释）。
    """
    if str(kind) not in INVOICE_KINDS:
        return {"ok": False, "kind": "err", "message": f"不认识的子表类型：{kind}"}
    bad = D.invoice_problem(date, amount)
    if bad:
        return {"ok": False, "kind": "err", "message": bad}
    key = _request_key(request_id)
    if str(request_id or "").strip() and not key:
        return {"ok": False, "kind": "err", "message": D.MSG_REQUEST_BAD}
    money = D.parse_amount(amount)
    fields = dict(contract_id=int(contract_id or 0), kind=str(kind),
                  date=str(date or "").strip(), amount=str(money))
    if key:
        R.lock_subtable_operations(s)
        hit = _replay(s, key=key, action=SUBOP_INVOICE_ADD, **fields)
        if hit is not None:
            return hit
    row = R.insert_invoice(s, contract_id=contract_id, kind=str(kind),
                           invoice_date=date, amount=money)
    result = {"ok": True, "kind": "ok", "id": int(row.id), "message": "已增发票行"}
    _remember(s, key=key, action=SUBOP_INVOICE_ADD, result=result, fields=fields,
              row_id=int(row.id))
    return result


def act_del_invoice(s: Session, *, invoice_id: int, request_id: str | None = None) -> dict:
    """发票子表删行。

    ⭐ 带 `request_id` 时幂等：删成功后重放仍回"已删除"（回执只增不删 ⇒ 删行不会把回执带走）。
    """
    key = _request_key(request_id)
    if str(request_id or "").strip() and not key:
        return {"ok": False, "kind": "err", "message": D.MSG_REQUEST_BAD}
    fields = dict(row_id=int(invoice_id or 0))
    if key:
        R.lock_subtable_operations(s)
        hit = _replay(s, key=key, action=SUBOP_INVOICE_DEL, **fields)
        if hit is not None:
            return hit
    # ⚠️ 合同 id **在删之前**读：删完这行就没了，回执里"这次删的是哪份合同"就再也补不出来。
    #    它只落回执的 `contract_id` 列、⛔ 不进摘要（进摘要 ⇒ 重放时读不到该值 ⇒ 退化成"同键不同内容"）。
    owner = s.get(JcInvoice, int(invoice_id or 0))
    owner_id = int(owner.contract_id) if owner is not None else 0
    if not R.delete_invoice(s, invoice_id):
        return {"ok": False, "kind": "err", "message": f"找不到发票行 {invoice_id}"}
    result = {"ok": True, "kind": "ok", "message": "已删除"}
    _remember(s, key=key, action=SUBOP_INVOICE_DEL, result=result, fields=fields,
              contract_id=owner_id)
    return result


def act_add_payment(s: Session, *, contract_id: int, date, amount,
                    source: str = SRC_MANUAL, notice_id=None,
                    request_id: str | None = None) -> dict:
    """付款子表增行 —— **同款**校验（`D.payment_problem`）；引用付款域时先过**全库去重**。

    ⚠️ 去重范围 = **全库、不分合同**（§6.6.2）⇒ 入参是 `R.notice_ids_used(s)` 的全集。
    ⭐ 带 `request_id` 时幂等：重复请求回放原回执，⛔ 不重复付款。
    """
    bad = D.payment_problem(date, amount)
    if bad:
        return {"ok": False, "kind": "err", "message": bad}
    key = _request_key(request_id)
    if str(request_id or "").strip() and not key:
        return {"ok": False, "kind": "err", "message": D.MSG_REQUEST_BAD}
    money = D.parse_amount(amount)
    fields = dict(contract_id=int(contract_id or 0), date=str(date or "").strip(),
                  amount=str(money), source=str(source or SRC_MANUAL),
                  notice_id=str(notice_id if notice_id not in (None, "") else ""))
    if key:
        R.lock_subtable_operations(s)
        hit = _replay(s, key=key, action=SUBOP_PAYMENT_ADD, **fields)
        if hit is not None:
            return hit
    if str(source) == SRC_NOTICE and D.dedup_blocked(
            notice_id=notice_id, existing_notice_ids=R.notice_ids_used(s)):
        return {"ok": False, "kind": "err",
                "message": "该付款通知书已被引用过（全库去重，不分合同）"}
    row = R.insert_payment(s, contract_id=contract_id, pay_date=date,
                           amount=money, source=source, notice_id=notice_id)
    result = {"ok": True, "kind": "ok", "id": int(row.id), "message": "已增付款行"}
    _remember(s, key=key, action=SUBOP_PAYMENT_ADD, result=result, fields=fields,
              row_id=int(row.id))
    return result


def act_del_payment(s: Session, *, payment_id: int, request_id: str | None = None) -> dict:
    """删除手工付款行；通知书关系由正式解绑入口处理。

    ⭐ 带 `request_id` 时幂等：删成功后重放仍回"已删除"。
    """
    key = _request_key(request_id)
    if str(request_id or "").strip() and not key:
        return {"ok": False, "kind": "err", "message": D.MSG_REQUEST_BAD}
    fields = dict(row_id=int(payment_id or 0))
    if key:
        R.lock_subtable_operations(s)
        hit = _replay(s, key=key, action=SUBOP_PAYMENT_DEL, **fields)
        if hit is not None:
            return hit
    row = s.get(JcPayment, int(payment_id))
    if row is not None and row.source == SRC_NOTICE:
        return {"ok": False, "kind": "err", "message": "请到付款通知书页改关联或解绑"}
    owner_id = int(row.contract_id) if row is not None else 0   # 同上：删之前读，只落 `contract_id` 列
    if not R.delete_payment(s, payment_id):
        return {"ok": False, "kind": "err", "message": f"找不到付款行 {payment_id}"}
    result = {"ok": True, "kind": "ok", "message": "已删除"}
    _remember(s, key=key, action=SUBOP_PAYMENT_DEL, result=result, fields=fields,
              contract_id=owner_id)
    return result


# ---------------------------------------------------------------- 付款域双向引用（`M5-5`）

def act_link_notice(s: Session, *, notice_id: int, contract_id: int) -> dict:
    """**关联**：把这笔集采付款通知书关联到一张集采合同 ⇒ 写合同的**付款子表**（`source=notice`）。

    ⭐ 判据 `ACC-JC-PAY-001/001-01`「两个方向写**同一份**关联记录、**双向可见**」——
       本函数就是那两个方向（`m03` 侧「关联集采合同」与集采侧「从付款域引用 R8」）的**唯一落库口**；
       `m03` 那边的"已关联"态由 `list_view._links_by_notice` **读同一张付款子表**得出 ⇒ 双向可见是**自然结果**。
    ⭐ 判据 `001-03`「一条通知书**只能关联一个合同**（换合同 = **先解绑再写新**）」⇒ 见下面第 1 步。
    ⚠️ **⛔ 不做金额校验**（判据 `001-04`：通知书金额与合同欠款不一致 ⇒ **只提示、不拦**）。
       注意这与"子表**手工录入**金额必须 > 0"**不冲突** —— 那条管的是**录入**，这里是**引用既有付款事实**：
       关联只记录关系；读取时动态取通知书**统计付款金额**，零值保持零，不回退审批金额。
    """
    from app.mod03_notice import service as notices
    from app.mod11_jc.models import JcContract

    s.flush()
    notice = notices.get_notice(s, int(notice_id), with_for_update=True, populate_existing=True)
    if notice is None:
        return {"ok": False, "kind": "err", "message": f"找不到付款通知书 {notice_id}"}
    contract = s.get(JcContract, int(contract_id))
    if contract is None:
        return {"ok": False, "kind": "err", "message": f"找不到集采合同 {contract_id}"}
    if notice.category != 'jc' or notice.excluded or notice.i8_revoked:
        return {"ok": False, "kind": "err", "message": "仅有效集采通知书可新增或更换关联；已有关系仍可查看、解除"}
    if notice.ownership_id is None or notice.ownership_id != contract.project_id:
        return {"ok": False, "kind": "err", "message": "只能关联本通知书所属项目的合同，请重读核对项目归属"}

    # 1) **一对一**：换合同 ⇒ 先把旧的那条关联记录摘掉（判据 `001-03`「先解绑再写新」）
    old = R.payment_of_notice(s, notice_id)
    moved_from = None
    if old is not None:
        if int(old.contract_id) == int(contract_id):
            return {"ok": True, "kind": "ok", "contract_id": int(contract_id), "changed": False,
                    "message": f"这行通知书已经关联在集采合同 #{contract_id} 上（未重复关联）"}
        moved_from = int(old.contract_id)
        R.delete_payment(s, old.id)

    # 2) 兜底再判一次**全库去重**（域内核出口；正常在上面已摘干净 ⇒ 这里只在边界上护一道）
    if D.dedup_blocked(notice_id=notice_id, existing_notice_ids=R.notice_ids_used(s)):
        return {"ok": False, "kind": "err",
                "message": "该付款通知书已被引用过（全库去重，不分合同）—— 请刷新后重试"}

    notice.jc_supplier = contract.supplier
    row = R.insert_payment(s, contract_id=int(contract_id), pay_date="",
                           amount=0, source=SRC_NOTICE, notice_id=int(notice_id))
    return {"ok": True, "kind": "ok", "changed": True, "payment_id": int(row.id),
            "contract_id": int(contract_id), "moved_from": moved_from,
            "message": (f"已从集采合同 #{moved_from} 改关联到 #{contract_id}"
                        if moved_from else f"已关联到集采合同 #{contract_id}")}


def auto_link_plan(s: Session, notice_ids: list[int], payables: list[dict]) -> dict:
    """只补未关联通知书；应付精确对应一个合同且本地候选唯一才可执行。"""
    from app.mod03_notice.domain import APPROVE_STATUS_DONE
    rows = []
    for context in _link_candidates(s, notice_ids):
        nid, n = context['notice_id'], context['notice']
        row = {'notice_id': nid, 'code': n.bill_no if n else str(nid), 'contract_id': None}
        if n is None or n.category != 'jc' or n.excluded or n.i8_revoked or n.approve_status != APPROVE_STATUS_DONE:
            row['reason'] = '非有效集采通知书'
        elif context['current_contract_id'] is not None:
            row['reason'] = '已有合同关联，保持不变'
        elif not context['project_key'] or not n.jc_supplier or n.amount_approved <= 0:
            row['reason'] = '项目、供应商或审批金额未确定'
        else:
            hits = [p for p in payables if p['project'] == n.project_name and p['supplier'] == n.jc_supplier
                    and p['amount'] == n.amount_approved]
            nos = {p['contract_no'] for p in hits}
            targets = [c for c in context['rows'] if c['contract_no'] in nos and c['tag'] == D.TAG_IN]
            if len(nos) == 1 and '' not in nos and len(targets) == 1:
                row.update(contract_id=targets[0]['id'], contract_no=targets[0]['contract_no'],
                           amount=str(n.amount_approved), payable_codes=[p['code'] for p in hits], reason='应付合同来源唯一')
            else:
                row['reason'] = '无唯一应付及本地合同对应，保留人工处理'
        rows.append(row)
    return {'ok': True, 'rows': rows, 'ready': sum(r['contract_id'] is not None for r in rows)}


def act_auto_link(s: Session, expected: list[dict], payables: list[dict]) -> dict:
    """确认时重新取数核对；不允许预览后发生变化的行被批量改关联。"""
    from app.mod03_notice import service as notices
    ids = sorted({r['notice_id'] for r in expected})
    for nid in ids:
        notices.get_notice(s, nid, with_for_update=True, populate_existing=True)
    plan = auto_link_plan(s, ids, payables)
    wanted = {r['notice_id']: r for r in expected}
    linked = 0
    for row in plan['rows']:
        prior = wanted[row['notice_id']]
        if row['contract_id'] is None:
            continue
        if any(row.get(k) != prior.get(k) for k in ('contract_id', 'amount', 'payable_codes')):
            row['contract_id'] = None
            row['reason'] = '来源或金额已变化，请重新预览'
            continue
        result = act_link_notice(s, notice_id=row['notice_id'], contract_id=row['contract_id'])
        if not result['ok']:
            from app.core.errors import MustReportError
            raise MustReportError(result['message'])
        linked += int(result.get('changed', False))
    return {'ok': True, 'linked': linked, 'rows': plan['rows']}


def act_unlink_notice(s: Session, *, notice_id: int) -> dict:
    """**解绑**：摘掉这条通知书的关联记录（= 删合同的付款子表里那条 `source=notice` 行）。

    ⚠️ 解绑后**两侧同时**变回"未关联"（因为只有一份记录）—— 这正是双向可见的另一面。
    """
    from app.mod03_notice import service as notices
    s.flush()
    notice = notices.get_notice(s, int(notice_id), with_for_update=True, populate_existing=True)
    old = R.payment_of_notice(s, notice_id)
    if old is None:
        return {"ok": False, "kind": "err", "message": "这行通知书当前没有关联集采合同"}
    cid = int(old.contract_id)
    contract = R.contract_of(s, cid)
    if notice is not None and contract is not None:
        notice.jc_supplier = contract.supplier
    R.delete_payment(s, old.id)
    return {"ok": True, "kind": "ok", "contract_id": cid,
            "message": f"已取消与集采合同 #{cid} 的关联（两侧同时解除）"}


# ---------------------------------------------------------------- 导出（`M5-9`）

def export_print_xlsx(s: Session, *, projects: list[str]) -> bytes:
    """独立打印版：项目全部纳入合同，判版依据项目所有合同。"""
    from app import export_registry as EXP
    from app.core.errors import MustReportError

    selected = list(dict.fromkeys(str(key).strip() for key in projects if str(key).strip()))
    if not selected:
        raise MustReportError("请先选择要导出的项目")
    data = build_list(s)
    displays = {p["key"]: p["display"] for p in data["projects"] if p["key"]}
    if any(key not in displays for key in selected):
        raise MustReportError("所选项目已不存在，请刷新后重新选择")
    sections = []
    for key in selected:
        project_rows = [r for r in data["rows"] if r["project_key"] == key]
        included = sorted((r for r in project_rows if r["tag"] == TAG_IN),
                          key=lambda r: r["project_seq"])
        if not included:
            raise MustReportError(f"项目「{displays[key]}」没有纳入台账的合同")
        sections.append({"display": displays[key], "rows": included,
                         "trade": any(str(r.get("trade_co") or "").strip() for r in project_rows)})
    return EXP.get("jc_print").build_xlsx(sections)


def export_xlsx(s: Session, *, ids: list[int]) -> bytes:
    """把**页面上当前看到的那些行**导出成一本 xlsx ⇒ 字节。

    ⭐ **为什么收 `ids` 而不是"筛选条件"**：页面的筛选是**前端**算的（还含「合同金额为空/非空」
      这种 `build_list` 里没有的条件）⇒ 传条件就得在后端**再实现一遍** ⇒ **两套口径必打架**。
       传 id ⇒ **行集合就是前端看到的那些**，口径 100% 一致。
    ⚠️ 所以这里先 `build_list(s)`（**不带筛选 = 全量**，拿到派生金额）再**按 id 收窄**：
       多算了一点，但换到的是"导出与屏幕**逐行一致**"——这笔账在本项目永远划算。
    ⚠️ 空 `ids` ⇒ **空表**（不回落全量）：⛔ "我一列都没勾/筛出 0 行，却导出了整本台账" 是最坏的一种意外。
    """
    from app import export_registry as EXP
    jc_export = EXP.get("jc")

    want = {int(x) for x in (ids or ())}
    if not want:
        return jc_export.build_xlsx([])
    data = build_list(s)
    all_rows = data.get("rows") or data.get("items") or []
    by_id = {int(r["id"]): r for r in all_rows}
    rows = [by_id[int(i)] for i in dict.fromkeys(ids) if int(i) in by_id]
    return jc_export.build_xlsx(rows)


# ---------------------------------------------------------------- 甲方单位分类（`M5-6b`）

def party_kinds(s: Session) -> dict:
    """甲方单位分类清单 ＋ **每类下的合同条数** —— `M5-6b` 的读出口（页面用）。

    ⚠️ 条数**现场算**（⛔ 不落库）：落库就是第二份真相（本模块一贯口径）。
    ⭐ `unknown` 排在**最前**（`R.list_party_kinds` 保证）—— 那批正是**要人去指定**的。
    """
    from sqlalchemy import select

    from app.mod11_jc.models import KIND_PARTY_UNKNOWN, PARTY_KIND_NAMES, PARTY_KINDS, JcContract

    items = R.list_party_kinds(s)
    by_party: dict[str, int] = {}
    for nm in s.execute(select(JcContract.party_name)).scalars():
        key = str(nm or "").strip()
        if key:
            by_party[key] = by_party.get(key, 0) + 1
    for it in items:
        it["count"] = by_party.get(it["name"], 0)
    # ⚠️ **在册合同里出现过、但分类表里没有**的甲方（理论上不该有 —— 抓取时会 `ensure`）
    #    ⇒ 若真出现（如手工新增 / Excel 导入带进来的甲方名），**列出来**，⛔ 不静默忽略。
    listed = {it["name"] for it in items}
    for nm, cnt in sorted(by_party.items()):
        if nm not in listed:
            items.append({"name": nm, "kind": KIND_PARTY_UNKNOWN,
                          "kind_name": PARTY_KIND_NAMES[KIND_PARTY_UNKNOWN], "count": cnt})
    unknown = sum(1 for it in items if it["kind"] == KIND_PARTY_UNKNOWN)
    return {"ok": True, "items": items, "unknown": unknown,
            "kinds": list(PARTY_KINDS), "kind_names": PARTY_KIND_NAMES}


def act_set_party_kind(s: Session, *, name: str, kind: str) -> dict:
    """指定某甲方单位的类型（`M5-6b`）—— ⛔ 类型非法一律拒（判定**在后端**，前端不自行判）。

    ⚠️ ⚠️ **只改分类，不回头重算已有合同的金额落位** —— 这与 §4.2.2「改规则不重算历史」同款：
       已经落错列的行，改完分类后**由人重抓一次或手改**（页面对这类行会提示）。
       ⛔ 别在这里补一个"顺便重算"—— 那会**静默改动历史金额**，是本项目最忌的一类动作。
    """
    from app.mod11_jc.models import PARTY_KIND_NAMES, PARTY_KINDS

    nm = str(name or "").strip()
    if kind not in PARTY_KINDS:
        return {"ok": False, "kind": "err", "message": f"未知的甲方类型：{kind}"}
    if not nm:
        return {"ok": False, "kind": "err", "message": "甲方单位名不能为空"}
    R.set_party_kind(s, nm, kind)
    return {"ok": True, "kind": "ok", "name": nm, "party_kind": kind,
            "message": f"已把「{nm}」标为「{PARTY_KIND_NAMES.get(kind, kind)}」"}


__all__ = ["project_references",
    "export_xlsx", "export_print_xlsx",
    "build_list", "build_detail", "link_recommendations", "debt_of_ledger", "settlement_totals_by_project",
    "DEFAULT_TAG_ON_CREATE", "act_add_contract", "act_set_tag", "act_batch_tag",
    "act_update_contract", "act_add_invoice", "act_del_invoice",
    "act_add_payment", "act_del_payment",
    "subtable_operation", "subtable_account",
    "act_link_notice", "act_unlink_notice", "auto_link_plan", "act_auto_link",
    "party_kinds", "act_set_party_kind",
    "list_contracts", "links_by_notice",
]


def list_contracts(session, **kw):
    from app.mod11_jc import repository
    return repository.list_contracts(session, **kw)


def linked_suppliers(session, notice_ids: list[int] | None = None):
    return R.linked_suppliers(session, notice_ids)


def links_by_notice(session, notice_ids: list[int] | None = None):
    from app.mod11_jc import repository
    return repository.links_by_notice(session, notice_ids=notice_ids)


def project_references(session, project_id, warehouse, *, lock=False):
    """项目安全删除的只读关联明细；包括停用、撤销及恢复记录。"""
    from app.core.references import project_references as read
    from .models import JcContract, JcImportBatch

    return read(session, ((JcContract, '集采合同'), (JcImportBatch, '集采导入历史批次'),), project_id, warehouse, lock=lock)



def payment_contexts(s: Session, notice_ids: list[int], pay_date: str = "") -> dict:
    """合同付款约定与提醒事实；复用现有结算/付款/欠款口径。"""
    links = R.links_by_notice(s, notice_ids)
    ids = sorted({cid for linked in links.values() for cid in linked})
    if not ids:
        return {}
    invoices = R.invoices_of_many(s, ids)
    payments = R.payments_of_many(s, ids)
    rows = {r["id"]: r for r in R.list_contracts(s) if r["id"] in ids}
    result = {}
    for nid, linked in links.items():
        c = rows.get(linked[0])
        if not c:
            continue
        cid = c["id"]
        amounts = D.contract_amounts(trade_co=c["trade_co"], invoices=invoices.get(cid, []), payments=payments.get(cid, []))
        result[nid] = {"contract_id": cid, "contract_no": c["contract_no"],
                       "payment_term": c["payment_term"], "contract_payment_method": c["payment_method"],
                       "term_warning": D.payment_term_warning(payment_term=c["payment_term"], trade_co=c["trade_co"],
                           invoices=invoices.get(cid, []), debt=amounts["debt"], pay_date=pay_date)}
    return result
