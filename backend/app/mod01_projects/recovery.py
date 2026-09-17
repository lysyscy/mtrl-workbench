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
- 全名命中「≥2 条非壳行」⇒ 疑似「名字没带小微的壳」（决策 1 兜底）⇒ 进 `unresolved` 要人确认。
- 全名命中**壳** ⇒ 这条仓库是**具体小微** ⇒ 新建 `small` 行（`parent_shell_id` = 壳）。
  ⚠️ **关键词留空**（材料侧按**仓库名**取数，不需要关键词；关键词是**付款侧**链路 C 才要的）
  —— 不臆造、不阻塞；告警里注明"关键词待补"。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.mod01_projects.domain import DEFAULT_SMALL_KEYWORD, norm_full_name
from app.mod01_projects.models import PLACEHOLDER_PREFIX, TYPE_SHELL, TYPE_SMALL
from app.mod01_projects.repository import (
    all_projects,
    create_project,
    get_project,
    promote_placeholder,
)

PLAN_KEYS: tuple[str, ...] = ("promote", "create", "unresolved")


def _norm(value) -> str:
    """全名比较一律走**归一出入口**（剥尾码 ＋ 压缩空白，`ACC-PRJ-NAME-001/001-05`）。"""
    return norm_full_name(str(value or ""))


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

    rows_by_full: dict[str, list] = {}
    for p in projects or ():
        rows_by_full.setdefault(_norm(getattr(p, "name_full", "")), []).append(p)

    promote: list[dict] = []
    create: list[dict] = []
    unresolved: list[dict] = []

    for wh in sorted({str(w).strip() for w in (unknown_wh or ()) if str(w).strip()}):
        full = owner_of.get(wh, "")
        if not full:
            unresolved.append({
                "warehouse_name": wh,
                "reason": "仓库名单里查不到它的所属项目全名（可能已作废或名单未更新）"
                          "—— 不臆造，请人工核对",
            })
            continue

        hits = rows_by_full.get(_norm(full), [])
        if not hits:
            unresolved.append({
                "warehouse_name": wh, "owner_full_name": full,
                "reason": "所属项目还**没建档** —— i8 侧要先把它加入「常用项目列表」，"
                          "再跑一次「同步常用项目列表」；本次数据已照常入库",
            })
            continue

        shells = [p for p in hits if getattr(p, "project_type", "") == TYPE_SHELL]
        if shells:
            shell = shells[0]
            create.append({
                "warehouse_name": wh, "name_full": full,
                "project_type": TYPE_SMALL, "parent_shell_id": shell.id,
                "phid": str(getattr(shell, "phid", "") or ""),
                "keywords_pending": True,       # ⚠️ 关键词留空（付款侧链路 C 才需要）
            })
            continue

        if len(hits) > 1:
            unresolved.append({
                "warehouse_name": wh, "owner_full_name": full,
                "reason": f"同一全名命中 {len(hits)} 条非壳档案 —— 疑似名字没带「小微」的壳，"
                          "需人工确认类型（决策 1 兜底）",
            })
            continue

        only = hits[0]
        current = str(getattr(only, "warehouse_name", "") or "")
        if current.startswith(PLACEHOLDER_PREFIX):
            promote.append({
                "warehouse_name": wh, "project_id": only.id,
                "name_full": full, "old_placeholder": current,
            })
            continue

        unresolved.append({
            "warehouse_name": wh, "owner_full_name": full,
            "reason": f"该全名的档案行仓库名 = 「{current}」，本次报表里出现的是「{wh}」"
                      "—— 一条普通项目只能挂一个仓库（决策 2：普通项目 ↔ 仓库 = 1 : 1），需人工核对",
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
            f"陌生仓库自动建档未完成（仓库名单取不到）：{type(exc).__name__}: {exc}"
            " —— 数据已照常入库，可稍后重抓一次",
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
                             "reason": f"扶正失败：{type(exc).__name__}: {exc}"})

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
                             "reason": f"建档失败：{type(exc).__name__}: {exc}"})

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


__all__ = ["PLAN_KEYS", "unknown_warehouses", "plan_recovery", "counts_of",
           "recover_unknown_warehouses", "summary_text"]
