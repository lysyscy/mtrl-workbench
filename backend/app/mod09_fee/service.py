"""`MOD-09` 特殊费用月报表 · 数据组装 ＋ 四个写动作（PRG）。

⚠️ **判定一律调 `domain` 出口**（取数 / 合计 / 金额判据 / 显示）；本层只做编排与回执文案。

写路径的边界（§5.5）：**增 / 改 / 删只落在「当前所选核算年月 ＋ 当前所选项目」那一份上**
⇒ 每个动作都先按 (ym, 项目键) 解析出那一份，再按**该份内的下标**取行；行不存在就显式报错。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.query import query_one

from app.mod01_projects import domain as PJ, service as PS
from app.mod01_projects.models import Project
from app.mod09_fee import domain as D
from app.mod09_fee import repository as R


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
    items = R.items_of(s, ym=ym, project_id=pj.id) if pj else []
    inv = R.inv_rows(s, ym=ym)
    auto = D.auto_amount(inv, ym=ym, project_key=project)
    total = D.total_amount(inv, items, ym=ym, project_key=project)
    return {
        "state": {**st, "project": project},
        "ym": ym,
        "project": project,
        "projects": cands,
        "project_display": next((c.display for c in cands if c.key == project), project or ""),
        "auto": D.auto_row(auto=auto, total=total),
        "manuals": D.manual_rows(items, total=total),
        "summary": D.summary_row(total=total),
        "total": total,
        "count": len(items),
        "can_edit": pj is not None,     # 没档案行 ⇒ 没有可写的那一份
    }


# ---------------------------------------------------------------- 写动作（PRG：都返回回执）


def _flash(kind: str, message: str) -> dict:
    return {"kind": kind, "message": message}


def _scope(s: Session, *, ym: str, project_key: str) -> tuple[Project | None, list[dict]]:
    pj = R.project_by_key(s, project_key)
    return pj, (R.items_of(s, ym=ym, project_id=pj.id) if pj else [])


def _label(data_ym: str, disp: str) -> str:
    return f"{data_ym} · {disp}"


def act_add(s: Session, *, ym: str, project_key: str) -> dict:
    """「＋ 增加手填项」：在该 (月, 项目) 那一份末尾追加一行（初值 = 名称可改、金额 0）。"""
    pj, _ = _scope(s, ym=ym, project_key=project_key)
    if pj is None:
        return _flash("err", f"项目「{project_key or '（未选）'}」不在档案里 —— 先建档再录")
    R.add_item(s, ym=ym, project_id=pj.id, name=D.DEFAULT_ITEM_NAME, amount=D.ZERO)
    return _flash("ok", f"已在 {_label(ym, project_key)} 增加手填项：**名称可改、金额可填**（§5.5）")


def act_rename(s: Session, *, ym: str, project_key: str, index: int, value: str) -> dict:
    """改项名（§5.5：手填项**项名也可改**）。⚠️ 不强制非空 —— 空名在删除反馈里显示为「未命名」。"""
    pj, items = _scope(s, ym=ym, project_key=project_key)
    row = _row_at(s, pj, items, index, ym)
    if row is None:
        return _flash("err", "这一条手填项已经不在了（可能被删或切了月份 / 项目）—— 请刷新后重试")
    R.set_item_name(s, row, value)
    return _flash("ok", f"已把 {_label(ym, project_key)} 的项名改为「{value or D.UNNAMED}」（§5.5）")


def act_set_amount(s: Session, *, ym: str, project_key: str, index: int, raw) -> dict:
    """改金额：**非法输入必须被拒绝且原值不变**（001-07 · §5.5 只拦非数字、允许 0 与负数）。"""
    pj, items = _scope(s, ym=ym, project_key=project_key)
    row = _row_at(s, pj, items, index, ym)
    if row is None:
        return _flash("err", "这一条手填项已经不在了（可能被删或切了月份 / 项目）—— 请刷新后重试")
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
    name, before = str(row.item_name or ""), D.money_text(row.amount)
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
    inv = R.inv_rows(s, ym=ym)
    items = R.items_of(s, ym=ym, project_id=project_id)
    return D.total_amount(inv, items, ym=ym, project_key=project_key)


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
    if pj is None:
        return _flash("err", f"项目「{project_key or '（未选）'}」不在档案里 —— 先建档再录")
    names = [str(n or "").strip() for n in (items or [])]
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
    "parse_state", "candidates", "build_page_data",
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


def project_references(session, project_id, warehouse, *, lock=False):
    """项目安全删除的只读关联明细；包括停用、撤销及恢复记录。"""
    from app.core.references import project_references as read
    from .models import FeeManualItem

    return read(session, ((FeeManualItem, '特殊费用'),), project_id, warehouse, lock=lock)
