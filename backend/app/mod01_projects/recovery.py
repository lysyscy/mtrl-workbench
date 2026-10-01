"""链路 B · **材料侧自动扶正**（《说明书》**§2.4.2** · 《全自动建档-实施计划》**§三 链路 B**）
—— 纯函数（`plan_recovery`）＋ 编排（`recover_unknown_warehouses`）。

**口径**（原文，三条一致）：
- §2.4.2：「**B 材料侧扶正**：材料报表到达，遇**陌生仓库** → 同步仓库名单 → 用全名回查占位行 →
  **扶正改名** → **重跑导入**」
- §2.5：「按仓库名找档案；**找不到 = 陌生仓库** → **触发建档/扶正**」
- 实施计划 §1.1（转向）：「活跃业务（收发结存 / 库存单据）遇陌生仓库」原「**报错**，要求先手工同步项目」
  ⇒ 改为「**自动跑一次仓库同步 → 扶正 → 重跑导入**」

⇒ **无感**：不要求用户点任何东西；抓取 i8 时顺手把档案补齐。
⚠️ 本模块**只出计划与落库**，不做页面；结果由调用方放进**抓取回执**（禁静默）。

**安全绳**（实施计划 §1.2：放开建档前先把当年的坑堵上）：
- **只对"已建档项目名下"的仓库建档** —— 全名在档案里**找不到任何行** ⇒ 进 `unresolved`
  （提示"先跑一次「同步常用项目列表」"），**不臆造**（这条正好挡住"i8 里的历史老项目"被污染进来）。
- **普通项目 ↔ 仓库 = 1 : 1**（决策 2）⇒ 全名命中「1 条**非壳**行」且它已有**真实**仓库名 ≠ 本次仓库名
  ⇒ 异常，进 `unresolved`（**不静默改**）。
- 全名命中「≥2 条非壳行」⇒ 疑似「名字没带「小微」的壳」（决策 1 兜底）⇒ 进 `unresolved` 要人确认。
  ⭐ **这一类有主人**（`TAIL-30`-③ · 用户 2026-09-18 批准）：由人在 `m01` 档案页**指认到哪一行**
  —— 清单与指认入口在 `app.mod01_projects.pending`（⛔ 本模块只**报出来**，不猜、不自动挂）。
- 全名命中**壳** ⇒ 这条仓库是**具体小微** ⇒ 新建 `small` 行（`parent_shell_id` = 壳）。
  ⚠️ **关键词留空**（材料侧按**仓库名**取数，不需要关键词；关键词是**付款侧**链路 C 才要的）
  —— 不臆造、不阻塞；告警里注明"关键词待补"。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import human_reason
from app.mod01_projects.domain import DEFAULT_SMALL_KEYWORD, norm_full_name
from app.mod01_projects.models import TYPE_SHELL, TYPE_SMALL
from app.mod01_projects.repository import (
    all_projects,
    create_project,
    get_project,
    promote_placeholder,
)

PLAN_KEYS: tuple[str, ...] = ("promote", "create", "unresolved")

# ------------------------------------------------------------------ 处置类别（`kind`）
# ⚠️ 每一条 `unresolved` 条目都带 `kind`：`reason` 给人看、`kind` 给机器认。
#    ⛔ **别用中文原因串去判断类别** —— 文案一改（或被人顺口改一个字），"挑出要人指认的那一类"
#    就会**静默失效**（而它恰好是本入口的唯一数据源）。`TAIL-30`-③ 起成为对外契约。
KIND_NO_OWNER = "no_owner"                     # 仓库名单里查不到它的所属项目全名
KIND_NOT_ARCHIVED = "not_archived"             # 该全名还没建档（安全绳：不许臆造）
KIND_MULTI = "multi_non_shell"                 # ⭐ 命中 ≥2 条非壳行 ⇒ **要人指认挂哪一行**（本入口服务的就是它）
KIND_WAREHOUSE_MISMATCH = "warehouse_mismatch"  # 1 条真实仓库名 ≠ 本次（决策 2：普通项目 ↔ 仓库 1 : 1）
KIND_CREATE_SMALL = "create_small"             # 命中壳 ⇒ 新建具体小微（**系统自己做**，不进 unresolved）
KIND_PROMOTE = "promote"                       # 1 条占位行 ⇒ 系统扶正（**系统自己做**，不进 unresolved）
KIND_REAL_WAREHOUSE = "real_warehouse"         # 1 条已有真实仓库名（≠ 本次 ⇒ 异常）

#: 三类处置的**类别**（`plan_recovery` 的键）—— `kind → 落到哪个键`
BUCKET_OF_KIND: dict[str, str] = {
    KIND_PROMOTE: "promote",
    KIND_CREATE_SMALL: "create",
    KIND_NO_OWNER: "unresolved",
    KIND_NOT_ARCHIVED: "unresolved",
    KIND_MULTI: "unresolved",
    KIND_WAREHOUSE_MISMATCH: "unresolved",
    KIND_REAL_WAREHOUSE: "unresolved",
}


def _norm(value) -> str:
    """全名比较一律走**归一出入口**（剥尾码 ＋ 压缩空白，`ACC-PRJ-NAME-001/001-05`）。"""
    return norm_full_name(str(value or ""))


def rows_by_full(projects) -> dict[str, list]:
    """**归一化全名 → 档案行**（含归档行；不筛状态 —— §17.2「查本地档案表」）。

    ⭐ **唯一出口**：`plan_recovery`（判定）与「人工指认」的候选清单（展示）**共用一份索引** ——
      两处各建一份的话，"系统说命中了 2 条、弹窗里只列出 1 条"这类**对不上**会静默发生。
    """
    out: dict[str, list] = {}
    for p in projects or ():
        out.setdefault(_norm(getattr(p, "name_full", "")), []).append(p)
    return out


def hits_of_full(by_full: dict, full) -> list:
    """某全名命中的档案行（**归一化后精确相等**，⛔ 不包含 / 不模糊 / 无兜底）。"""
    return list((by_full or {}).get(_norm(full), []))


def classify_hits(hits) -> str:
    """命中行 → 处置类别（`KIND_*`）。⭐ **唯一出口** —— 判定与「待指认」清单不许各写一份。

    规则（§17.2 / §17.3，顺序即优先级）：
      ① 无命中 ⇒ 没建档　② **先判壳**：命中里有壳 ⇒ 这条仓库是具体小微（新建，不进 `≥2` 分支）
      ③ ≥2 条非壳行 ⇒ **要人指认**　④ 1 条占位行 ⇒ 系统扶正　⑤ 1 条已有真实仓库名 ⇒ 异常
    """
    rows = list(hits or ())
    if not rows:
        return KIND_NOT_ARCHIVED
    if any(getattr(p, "project_type", "") == TYPE_SHELL for p in rows):
        return KIND_CREATE_SMALL
    if len(rows) > 1:
        return KIND_MULTI
    return KIND_PROMOTE if getattr(rows[0], "is_placeholder", False) else KIND_REAL_WAREHOUSE


def unknown_warehouses(session: Session, rows) -> list[str]:
    """导出里出现、但**项目档案里没有**的仓库名（《说明书》§2.5「找不到 = 陌生仓库」）。

    ⚠️ **唯一出口** —— 收发结存 / 库存单据两条链路共用这一份（别各写一份差集）。
    """
    known = {str(getattr(p, "warehouse_name", "") or "") for p in all_projects(session)}
    seen = {str(r.get("warehouse_name") or "") for r in (rows or ()) if r.get("warehouse_name")}
    return sorted(seen - known)


def plan_recovery(
    *,
    unknown_wh,
    warehouse_rows,
    projects,
    shell_keyword: str = DEFAULT_SMALL_KEYWORD,
) -> dict:
    """→ `{promote, create, unresolved}`（**三类都给，禁静默**）。

    - `unknown_wh` = 本次导出里出现、档案里没有的**仓库名**
    - `warehouse_rows` = 仓库名单（`API-05`：仓库名 ↔ 所属项目全名）
    - `projects` = 现有档案行（**给对象本身**，输出里带 `id`）
    """
    owner_of: dict[str, str] = {}
    for r in warehouse_rows or ():
        wh = str(r.get("warehouse_name") or "").strip()
        owner = str(r.get("owner_full_name") or "").strip()
        if wh and owner:
            owner_of.setdefault(wh, owner)

    by_full = rows_by_full(projects)

    promote: list[dict] = []
    create: list[dict] = []
    unresolved: list[dict] = []

    for wh in sorted({str(w).strip() for w in (unknown_wh or ()) if str(w).strip()}):
        full = owner_of.get(wh, "")
        if not full:
            unresolved.append({
                "kind": KIND_NO_OWNER,
                "warehouse_name": wh,
                "reason": "仓库名单里查不到它的所属项目全名（可能已作废或名单未更新）"
                          "—— 不臆造，请人工核对",
            })
            continue

        hits = hits_of_full(by_full, full)
        kind = classify_hits(hits)

        if kind == KIND_NOT_ARCHIVED:
            unresolved.append({
                "kind": kind,
                "warehouse_name": wh, "owner_full_name": full,
                "reason": "所属项目还**没建档** —— i8 侧要先把它加入「常用项目列表」，"
                          "再跑一次「同步常用项目列表」；本次数据已照常入库",
            })
            continue

        if kind == KIND_CREATE_SMALL:
            shell = next(p for p in hits if getattr(p, "project_type", "") == TYPE_SHELL)
            create.append({
                "warehouse_name": wh, "name_full": full,
                "project_type": TYPE_SMALL, "parent_shell_id": shell.id,
                "phid": str(getattr(shell, "phid", "") or ""),
                "keywords_pending": True,       # ⚠️ 关键词留空（付款侧链路 C 才需要）
            })
            continue

        if kind == KIND_MULTI:
            unresolved.append({
                "kind": kind,
                "warehouse_name": wh, "owner_full_name": full,
                "reason": f"同一全名命中 {len(hits)} 条非壳档案 —— 疑似名字没带「小微」的壳，"
                          "需人工确认类型",
            })
            continue

        only = hits[0]
        current = str(getattr(only, "warehouse_name", "") or "")
        if kind == KIND_PROMOTE:
            promote.append({
                "warehouse_name": wh, "project_id": only.id,
                "name_full": full, "old_placeholder": current,
            })
            continue

        unresolved.append({
            "kind": KIND_WAREHOUSE_MISMATCH,
            "warehouse_name": wh, "owner_full_name": full,
            "reason": f"该全名的档案行仓库名 = 「{current}」，本次报表里出现的是「{wh}」"
                      "—— 一条普通项目只能挂一个仓库（普通项目 ↔ 仓库 = 1 : 1），需人工核对",
        })

    return {"promote": promote, "create": create, "unresolved": unresolved}


def counts_of(plan: dict | None) -> dict[str, int]:
    """三类计数（回执用）。"""
    return {k: len((plan or {}).get(k) or ()) for k in PLAN_KEYS}


def _blank(message: str = "", *, degraded: bool = False, unresolved: int = 0) -> dict:
    out = {"promote": 0, "create": 0, "unresolved": unresolved,
           "promoted": [], "created": [], "degraded": degraded, "message": message}
    return out


def recover_unknown_warehouses(
    session: Session,
    *,
    unknown_wh,
    load_warehouse_rows,
    operator: str = "",
) -> dict:
    """编排：**拉仓库名单 → 计划 → 落库**（扶正 / 新建）→ 摘要。

    ⚠️ **本步骤失败绝不拖垮抓取** —— 数据此时**已经入库**，这里只补档案
       ⇒ 取数失败一律**降级进摘要**（不抛），并在消息里说清"可稍后重抓一次"。
    ⚠️ 落库**逐条兜错**：某一条建不了（如壳已归档）⇒ 进 `unresolved`，其余照建。
    """
    unknown = sorted({str(w).strip() for w in (unknown_wh or ()) if str(w).strip()})
    if not unknown:
        return _blank()

    try:
        wh_rows = load_warehouse_rows()
    except Exception as exc:                              # noqa: BLE001 —— 降级，不抛
        return _blank(
            human_reason("陌生仓库自动建档未完成（仓库名单取不到）", exc,
                         next_step="数据已照常入库，可稍后重抓一次"),
            degraded=True, unresolved=len(unknown))

    plan = plan_recovery(unknown_wh=unknown, warehouse_rows=wh_rows,
                         projects=all_projects(session))
    promoted: list[str] = []
    created: list[str] = []
    failures: list[dict] = list(plan["unresolved"])

    for item in plan["promote"]:
        try:
            target = get_project(session, item["project_id"])
            if target is None:
                raise ValueError(f"档案行 id={item['project_id']} 不存在")
            promote_placeholder(session, target, item["warehouse_name"])
            promoted.append(f"{item['old_placeholder']} → {item['warehouse_name']}")
        except Exception as exc:                          # noqa: BLE001
            failures.append({"warehouse_name": item["warehouse_name"],
                             "reason": human_reason("扶正失败", exc)})

    for item in plan["create"]:
        try:
            create_project(
                session,
                project_type=item["project_type"],
                name_full=item["name_full"],
                warehouse_name=item["warehouse_name"],
                phid=item.get("phid") or "",
                parent_shell_id=item.get("parent_shell_id"),
            )
            created.append(f"{item['warehouse_name']}"
                           + ("（具体小微·关键词待补）" if item.get("keywords_pending") else ""))
        except Exception as exc:                          # noqa: BLE001
            failures.append({"warehouse_name": item["warehouse_name"],
                             "reason": human_reason("建档失败", exc)})

    msg = (f"陌生仓库自动建档：扶正 {len(promoted)} · 新建 {len(created)} · "
           f"待人工 {len(failures)}")
    return {"promote": len(promoted), "create": len(created), "unresolved": len(failures),
            "promoted": promoted, "created": created,
            "unresolved_items": failures, "degraded": False, "message": msg}


def summary_text(result: dict | None) -> str:
    """把一次自动建档的摘要变成**回执里给人看的一句**（**没有动作也没有待办 ⇒ 空串**）。

    ⚠️ **逐条列出**（禁静默）：扶正了哪几行、新建了哪几行、还有哪几条要人看 —— 一条不省。
    """
    r = result or {}
    parts: list[str] = []
    promoted = r.get("promoted") or []
    created = r.get("created") or []
    if promoted:
        parts.append(f"自动扶正 {len(promoted)} 行（{'；'.join(promoted)}）")
    if created:
        parts.append(f"自动建档 {len(created)} 行（{'；'.join(created)}）")
    items = r.get("unresolved_items") or []
    if items:
        detail = "；".join(f"{i.get('warehouse_name')}：{i.get('reason')}" for i in items)
        parts.append(f"⚠️ 待人工 {len(items)} 条（{detail}）")
    if r.get("degraded") and r.get("message"):
        parts.append(str(r["message"]))
    return "；".join(parts)


__all__ = ["PLAN_KEYS", "KIND_NO_OWNER", "KIND_NOT_ARCHIVED", "KIND_MULTI",
           "KIND_WAREHOUSE_MISMATCH", "KIND_CREATE_SMALL", "KIND_PROMOTE",
           "KIND_REAL_WAREHOUSE", "BUCKET_OF_KIND",
           "rows_by_full", "hits_of_full", "classify_hits",
           "unknown_warehouses", "plan_recovery", "counts_of",
           "recover_unknown_warehouses", "summary_text"]
