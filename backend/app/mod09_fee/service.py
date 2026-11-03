"""`MOD-09` 特殊费用月报表 · 数据组装 ＋ 四个写动作（PRG）。

⚠️ **判定一律调 `domain` 出口**（取数 / 合计 / 金额判据 / 显示）；本层只做编排与回执文案。

写路径的边界（§5.5）：**增 / 改 / 删只落在「当前所选核算年月 ＋ 当前所选项目」那一份上**
⇒ 每个动作都先按 (ym, 项目键) 解析出那一份，再按**该份内的下标**取行；行不存在就显式报错。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.mod09_fee.models import FeeItem, FeeManualItem

from app.core.query import query_one
from app.core.errors import MustReportError

from app.mod01_projects import domain as PJ, service as PS
from app.mod01_projects.models import Project
from app.mod09_fee import domain as D
from app.mod09_fee import repository as R
from app.mod09_fee import oil_linkage as O


def parse_state(params: dict | None = None) -> dict:
    """筛选状态：**核算年月（只认 `YYYY-MM`）＋ 项目（键 = 仓库名）**。

    ⚠️ 认不出 / 没给年月 ⇒ 回落**默认年月**（材料报表类 = 上月，§9.2）；**不猜、不报错**（只是默认值）。
    """
    p = params or {}
    return {"ym": D.parse_ym(query_one(p, "ym")) or D.default_ym(), "project": query_one(p, "pj")}


def candidates(s: Session) -> list:
    """项目候选 —— **唯一出口** = `mod01_projects.domain.build_candidates`（§2.7.4：键 = 仓库名 · 显示 = 展示名）。"""
    rows = PS.all_projects(s)
    return PJ.build_candidates(PJ.ordered(list(rows)))


def _resolve(s: Session, state: dict) -> tuple[list, str, Project | None]:
    cands = candidates(s)
    keys = [c.key for c in cands]
    project = state.get("project") if state.get("project") in keys else (keys[0] if keys else "")
    return cands, project, R.project_by_key(s, project)


def build_page_data(s: Session, state: dict | None = None) -> dict:
    st = dict(state or parse_state())
    cands, project, pj = _resolve(s, st)
    ym = st["ym"]
    originals = R.items_of(s, ym=ym, project_id=pj.id) if pj else []
    binding = O.status(s, project_id=pj.id) if pj else {'enabled': False, 'fee_item_id': None}
    items = [item for item in originals if not binding['enabled'] or item['fee_item_id'] != binding['fee_item_id']]
    oil = next((row for row in O.effective_items(s, project_id=pj.id, end_ym=ym, items=[]) if row['ym'] == ym), None) if pj and binding['enabled'] else None
    inv = R.inv_rows(s, ym=ym)
    auto = D.auto_amount(inv, ym=ym, project_key=project)
    total = D.total_amount(inv, [*items, *([oil] if oil else [])], ym=ym, project_key=project)
    return {
        "state": {**st, "project": project},
        "ym": ym,
        "project": project,
        "projects": cands,
        "project_display": next((c.display for c in cands if c.key == project), project or ""),
        "auto": D.auto_row(auto=auto, total=total),
        "manuals": [{**row, 'index': next(i for i, item in enumerate(originals) if item['id'] == row['id'])} for row in D.manual_rows(items, total=total)],
        "oil": {'kind': 'auto', 'item': O.OIL_NAME, 'source': '油卡联动', 'amount': oil['amount'] if oil else D.ZERO,
                'share': D.share_text(oil['amount'] if oil else D.ZERO, total)} if binding['enabled'] else None,
        "summary": D.summary_row(total=total),
        "total": total,
        "count": len(items),
        "can_edit": pj is not None,     # 没档案行 ⇒ 没有可写的那一份
    }


def build_export_data(s: Session, *, end_ym: str, project: str) -> dict:
    """逐月台账的费用矩阵；指定项目精确取数，不回退其他项目。"""
    if not D.parse_ym(end_ym):
        raise MustReportError('请选择有效的台账截止月')
    key = str(project or '').strip()
    pj = R.project_by_key(s, key)
    if pj is None:
        raise MustReportError('导出费用的项目不在档案里，请重新选择')
    items, inv = R.year_facts(s, year=end_ym[:4], project_id=pj.id, warehouse=key)
    items = O.effective_items(s, project_id=pj.id, end_ym=end_ym, items=items)
    return {'ym': end_ym, 'project': key,
            **D.export_rows(end_ym=end_ym, project_key=key, items=items, inv_rows=inv)}


def build_year_data(s: Session, *, year: str, project: str) -> dict:
    if len(year) != 4 or not year.isascii() or not year.isdigit() or not 1 <= int(year) <= 9999:
        raise ValueError("年份请写成 YYYY")
    cands, key, pj = _resolve(s, {"project": project})
    items, inv = R.year_facts(s, year=year, project_id=pj.id if pj else None, warehouse=key)
    if pj:
        items = O.effective_items(s, project_id=pj.id, end_ym=f'{year}-12', items=items)
    indexes: dict[str, int] = {}
    records = []
    for item in items:
        ym = item["ym"]
        if not item.get('manual', True) or not ym.startswith(f"{year}-") or not D.parse_ym(ym):
            continue
        index = indexes.get(ym, 0)
        records.append({"ym": ym, "id": item["id"], "index": index,
                        "item": item["name"], "amount": item["amount"]})
        indexes[ym] = index + 1
    result = D.annual_rows(year=year, project_key=key, items=items, inv_rows=inv)
    binding = O.status(s, project_id=pj.id) if pj else {'enabled': False, 'fee_item_id': None}
    definitions = [] if pj is None else list(s.execute(select(FeeItem).where(FeeItem.project_id == pj.id, FeeItem.deleted.is_(False)).order_by(FeeItem.id)).scalars())
    by_name = {row['business_key']: row for row in result["rows"]}
    for item in definitions:
        if binding['enabled'] and item.id == binding['fee_item_id']:
            continue
        identity = f'fee:{item.id}'
        if identity not in by_name:
            row = {"item": item.name, 'business_key': identity, "manual": True, "prior": None, "months": [None] * 12, "periods": [], "total": D.ZERO}
            result["rows"].append(row)
            by_name[identity] = row
        by_name[identity]["item_id"] = item.id
    if binding['enabled'] and O.OIL_KEY not in by_name:
        result['rows'].append({'item': O.OIL_NAME, 'business_key': O.OIL_KEY, 'manual': False,
            'prior': None, 'months': [None] * 12, 'periods': [], 'total': D.ZERO})
    return {"year": year, "project": key,
            "project_display": next((c.display for c in cands if c.key == key), key),
            "records": records, "auto_name": D.AUTO_NAME, "can_edit": pj is not None, **result}


# ---------------------------------------------------------------- 写动作（PRG：都返回回执）


def _flash(kind: str, message: str) -> dict:
    return {"kind": kind, "message": message}


def _scope(s: Session, *, ym: str, project_key: str) -> tuple[Project | None, list[dict]]:
    pj = R.project_by_key(s, project_key)
    if pj is not None:
        pj = PS.get_project(s, pj.id, for_update=True)
    return pj, (R.items_of(s, ym=ym, project_id=pj.id) if pj else [])


def _label(data_ym: str, disp: str) -> str:
    return f"{data_ym} · {disp}"


def act_add(s: Session, *, ym: str, project_key: str, name: str = D.DEFAULT_ITEM_NAME, raw=0) -> dict:
    """「＋ 增加手填项」：在该 (月, 项目) 那一份末尾追加一行（初值 = 名称可改、金额 0）。"""
    pj, _ = _scope(s, ym=ym, project_key=project_key)
    if pj is None:
        return _flash("err", f"项目「{project_key or '（未选）'}」不在档案里 —— 先建档再录")
    if str(name).strip() in (D.AUTO_NAME, O.OIL_NAME):
        return _flash("err", "自动费用项不能由手填项覆盖")
    problem = D.amount_problem(raw)
    if problem:
        return _flash("err", problem)
    try:
        row = R.add_item(s, ym=ym, project_id=pj.id, name=name, amount=D.parse_amount(raw))
    except ValueError as exc:
        return _flash("err", str(exc))
    return {**_flash("ok", f"已在 {_label(ym, project_key)} 增加手填项：**名称可改、金额可填**（§5.5）"), "row_id": row.id}


def act_rename(s: Session, *, ym: str, project_key: str, index: int, value: str) -> dict:
    """改项名（§5.5：手填项**项名也可改**）。⚠️ 不强制非空 —— 空名在删除反馈里显示为「未命名」。"""
    pj, items = _scope(s, ym=ym, project_key=project_key)
    row = _row_at(s, pj, items, index, ym)
    if row is None:
        return _flash("err", "这一条手填项已经不在了（可能被删或切了月份 / 项目）—— 请刷新后重试")
    if O.is_bound(s, row.fee_item_id):
        return _flash('err', O.READONLY_MESSAGE)
    if str(value).strip() in (D.AUTO_NAME, O.OIL_NAME):
        return _flash("err", "自动费用项不能由手填项覆盖")
    try:
        R.set_item_name(s, row, value)
    except ValueError as exc:
        return _flash("err", str(exc))
    return _flash("ok", f"已把 {_label(ym, project_key)} 的项名改为「{value or D.UNNAMED}」（§5.5）")


def act_set_amount(s: Session, *, ym: str, project_key: str, index: int, raw) -> dict:
    """改金额：**非法输入必须被拒绝且原值不变**（001-07 · §5.5 只拦非数字、允许 0 与负数）。"""
    pj, items = _scope(s, ym=ym, project_key=project_key)
    row = _row_at(s, pj, items, index, ym)
    if row is None:
        return _flash("err", "这一条手填项已经不在了（可能被删或切了月份 / 项目）—— 请刷新后重试")
    if O.is_bound(s, row.fee_item_id):
        return _flash('err', O.READONLY_MESSAGE)
    problem = D.amount_problem(raw)
    if problem:
        return _flash("err", problem)                 # ⛔ 不动库：原值不变
    R.set_item_amount(s, row, D.parse_amount(raw))
    return _flash("ok", f"{_label(ym, project_key)} 的手填项金额已改为 "
                        f"{D.money_text(D.parse_amount(raw))}（§5.5）")


def act_delete(s: Session, *, ym: str, project_key: str, index: int) -> dict:
    """删除手填项：**必须给出反馈，且反馈里带「重算后的合计」**（001-08 · 设计规则 `R9`）。"""
    pj, items = _scope(s, ym=ym, project_key=project_key)
    row = _row_at(s, pj, items, index, ym)
    if row is None:
        return _flash("err", "这一条手填项已经不在了（可能被删或切了月份 / 项目）—— 请刷新后重试")
    if O.is_bound(s, row.fee_item_id):
        return _flash('err', O.READONLY_MESSAGE)
    name, before = str(items[int(index)]["name"] or ""), D.money_text(row.amount)
    R.delete_item(s, row)
    after = _total_after(s, ym=ym, project_key=project_key, project_id=pj.id)
    return _flash("ok", f"已删除 {_label(ym, project_key)} 的手填项「{name or D.UNNAMED}」（原 {before}）"
                        f" —— 合计重算为 {D.money_text(after)}（§5.5）")


def _row_at(s: Session, pj: Project | None, items: list[dict], index, ym: str):
    """按**该份内的下标**取行（原型 `data-i` 语义）—— 下标越界 / 不在当前份 ⇒ `None`。"""
    if pj is None:
        return None
    try:
        i = int(index)
    except (TypeError, ValueError):
        return None
    if i < 0 or i >= len(items):
        return None
    return R.item_of(s, items[i]["id"], ym=ym, project_id=pj.id)


def _total_after(s: Session, *, ym: str, project_key: str, project_id: int):
    return build_page_data(s, {'ym': ym, 'project': project_key})['total']


def act_batch(s: Session, *, project_key: str, items: list, months: list) -> dict:
    """⭐ `TAIL-156`（用户口径「一次录好几个月太麻烦」）· **月度批量录入**：一次写「N 个核算月 × M 个项」。

    ⭐ 三条语义（**唯一出口**，壳里不许复写）：
      ① **按 (核算月, 项目, 项名) 幂等** —— 同一格重提交 = **改那一条**的金额（⛔ 不是又追加一条；见 `R.upsert_item`）；
      ② **空格子整格跳过** —— ⛔ 不写 0、也不建行（**"空 ≠ 0"**，与 `001-05` / `001-11` 同口径）：
         用户没填的格子就是"没打算录"，替它写 0 会**凭空多出一行 0**（拿掉 0 还得再删一次）；
      ③ **先全量校验、通过才落库** ⇒ **一格非法 ⇒ 整批不写**（写一半会让人分不清哪些进去了 —— 宁可整批退回）。
    ⚠️ 金额判据**只走** `domain.amount_problem`（⛔ 本层不许自己判非数字）。
    """
    pj = R.project_by_key(s, project_key)
    if pj is not None:
        pj = PS.get_project(s, pj.id, for_update=True)
    if pj is None:
        return _flash("err", f"项目「{project_key or '（未选）'}」不在档案里 —— 先建档再录")
    names = [str(n or "").strip() for n in (items or [])]
    bound = O.status(s, project_id=pj.id)['fee_item_id']
    bound_name = s.get(FeeItem, bound).name if bound is not None else None
    if any(name in (D.AUTO_NAME, O.OIL_NAME, bound_name) for name in names):
        return _flash("err", "自动费用项不能由手填项覆盖")
    if not names:
        return _flash("err", "一项都没有 —— 先选一个「项名基准月」或加一列，再来填")
    # ---- 第 1 遍：**全量校验**（⛔ 不落库；任何一格非法 ⇒ 整批退回）
    plan: list[tuple[str, str, object]] = []
    for m in months or []:
        ym = D.parse_ym(str((m or {}).get("ym") or ""))
        if not ym:
            return _flash("err", f"核算年月认不出：{(m or {}).get('ym')!r} —— 请写成 YYYY-MM")
        vals = (m or {}).get("values") or {}
        for nm in names:
            raw = vals.get(nm, "")
            if raw is None or str(raw).strip() == "":
                continue                       # ⭐ ② 空 ⇒ 整格跳过（不写 0、不建行）
            problem = D.amount_problem(raw)
            if problem:
                return _flash("err", f"{ym}「{nm or D.UNNAMED}」：{problem}"
                                     f" —— 这一批**一格都没写**，改完请再按一次保存")
            plan.append((ym, nm, D.parse_amount(raw)))
    if not plan:
        return _flash("err", "所有格子都是空的 —— 没有要写的内容（⛔ 不会替你写 0）")
    # ---- 第 2 遍：落库（幂等：有 ⇒ 改，无 ⇒ 增）
    for ym, nm, amt in plan:
        R.upsert_item(s, ym=ym, project_id=pj.id, name=nm, amount=amt)
    yms = sorted({p[0] for p in plan})
    return _flash("ok", f"已写入 {len(yms)} 个核算月 × {len(names)} 项，共 {len(plan)} 格"
                        f"（{yms[0]} ~ {yms[-1]}）；同一「月 + 项名」已有 ⇒ 改值，没有 ⇒ 新建；空格子一律不写")


__all__ = ["project_references",
    "parse_state", "candidates", "build_page_data", "build_export_data",
    "act_add", "act_rename", "act_set_amount", "act_delete", "act_batch",
    "project_by_key",        # ⭐ 包间出口（`TAIL-195` 批 2c）
]


# --------------------------------------------- 包间出口（`TAIL-195` 批 2c）
# ⚠️⚠️ 跨包调用**只许经这一层**（计划 §2.3：「包间只经 `service` 调用，**不得跨包直查对方表**」）。
#    ⛔ 别的包**别** `import app.mod09_fee.repository` —— 守卫 = `backend/tests/test_layering.py` **规则 D**。
#    ⚠️ 导出侧（`report_export`）要它拿「项目 id / 展示名」⇒ 别让那边自己去查档案表。
# ⚠️⚠️ **必须写成函数、且每次经 `repository` 模块取** —— ⛔ 别写成模块级别名：
#    那会在导入时把函数对象**绑死**，测试里的 `monkeypatch.setattr(...repository, "project_by_key", …)` 就打不着。
def project_by_key(session, key):
    """⭐ 包间出口：按 key 取项目档案行（取不到 ⇒ `None`）。"""
    return R.project_by_key(session, key)


def create_item(s: Session, *, project_key: str, name: str) -> dict:
    pj = R.project_by_key(s, project_key)
    if pj is not None:
        pj = PS.get_project(s, pj.id, for_update=True)
    name = name.strip()
    if pj is None or not name or name in (D.AUTO_NAME, O.OIL_NAME) or len(name) > 128:
        return _flash("err", "请选择项目并填写有效的费用项名称")
    if s.execute(select(FeeItem.id).where(FeeItem.project_id == pj.id, FeeItem.name == name, FeeItem.deleted.is_(False))).scalar_one_or_none() is not None:
        return _flash("err", "费用项名称已存在")
    item = FeeItem(project_id=pj.id, name=name)
    s.add(item); s.flush()
    return {**_flash("ok", "已增加费用项"), "row_id": item.id}


def item_action(s: Session, *, project_key: str, item_id: int, action: str, value: str = "", ym: str = "") -> dict:
    pj = R.project_by_key(s, project_key)
    if pj is not None:
        pj = PS.get_project(s, pj.id, for_update=True)
    item = s.execute(select(FeeItem).where(FeeItem.id == item_id).with_for_update()).scalar_one_or_none()
    if pj is None or item is None or item.deleted or item.project_id != pj.id:
        return _flash("err", "费用项已不存在或不属于当前项目")
    if O.is_bound(s, item.id):
        return _flash('err', O.READONLY_MESSAGE)
    if action == "rename":
        name = value.strip()
        if not name or name in (D.AUTO_NAME, O.OIL_NAME) or len(name) > 128:
            return _flash("err", "请填写有效的费用项名称")
        other = s.execute(select(FeeItem.id).where(FeeItem.project_id == pj.id, FeeItem.name == name, FeeItem.id != item.id, FeeItem.deleted.is_(False))).scalar_one_or_none()
        if other is not None:
            return _flash("err", "费用项名称已存在")
        item.name = name
        s.flush()
        return _flash("ok", "费用项名称已修改")
    if action == "amount":
        if not D.parse_ym(ym):
            return _flash("err", "请选择有效的核算月份")
        if not value.strip():
            row = s.execute(select(FeeManualItem).where(FeeManualItem.fee_item_id == item.id, FeeManualItem.ym == ym)).scalar_one_or_none()
            if row is not None:
                s.delete(row); s.flush()
            return _flash("ok", "月度金额已清空")
        problem = D.amount_problem(value)
        if problem:
            return _flash("err", problem)
        row = s.execute(select(FeeManualItem).where(FeeManualItem.fee_item_id == item.id, FeeManualItem.ym == ym)).scalar_one_or_none()
        if row is None:
            row = FeeManualItem(fee_item_id=item.id, project_id=pj.id, item_name=item.name, ym=ym, amount=D.parse_amount(value))
            s.add(row)
        else:
            row.amount = D.parse_amount(value)
        s.flush()
        return {**_flash("ok", "月度金额已保存"), "row_id": row.id}
    if action == "delete":
        item.deleted = True
        s.flush()
        return _flash("ok", "费用项及其月度记录已删除")
    return _flash("err", "不支持的操作")


def project_references(session, project_id, warehouse, *, lock=False):
    """项目安全删除的只读关联明细；包括停用、撤销及恢复记录。"""
    from app.core.references import project_references as read
    from .models import FeeItem, FeeManualItem, FeeOilBinding, LegacyFeeManualItem

    return read(session, ((FeeItem, '特殊费用项'), (FeeManualItem, '特殊费用'), (FeeOilBinding, '用油接续依据'), (LegacyFeeManualItem, '特殊费用原始记录')), project_id, warehouse, lock=lock)


def oil_linkage_status(session, *, project_id):
    return O.status(session, project_id=project_id)


def review_oil_linkage(session, *, project_id):
    return O.review(session, project_id=project_id)


def enable_oil_linkage(session, **values):
    return O.enable(session, **values)


def enable_empty_oil_linkage(session, *, project_id):
    return O.enable_empty(session, project_id=project_id)
