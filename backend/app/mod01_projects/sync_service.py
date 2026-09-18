"""名单同步编排（建档）—— **取数 → 计划 → 落库**。

- 取数：常用项目（`API-06`，phid 权威）＋ 仓库名单（`API-05`，仓库名 ↔ 所属项目全名）—— **一次同步各取一次**。
- 计划：`archive.plan_archive`（**纯函数**，规则主人 = 链路 A）。
- 落库：逐条走 `repository.create_project`（**唯一建档出口**）。
- ⚠️ **失败不得动本地档案**：取数抛错 ⇒ 返回 `plan=None` 与 `degraded=True`（**显式说明**），
  由调用方转成用户可见的回执（`§3.6` 降级 + 铁律「禁静默」）。
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.mod01_projects import archive as A
from app.mod01_projects.models import TYPE_SHELL
from app.mod01_projects.repository import all_projects, create_project

Loader = Callable[[], list[dict]]


def _blank_counts() -> dict[str, int]:
    return A.counts_of(None)


def build_plan(
    *,
    load_common: Loader,
    load_warehouses: Loader,
    existing: set[str] | frozenset[str] | None = None,
    taken: set[str] | frozenset[str] | None = None,
    shells: set[str] | frozenset[str] | None = None,
) -> dict:
    """只出计划、**不落库**（可注入取数件 ⇒ 测试不连 i8）。

    `shells` = **档案里已经是壳的项目全名**（`TAIL-42` 的人工覆盖"粘住"）—— 有的壳全名**不含「小微」**，
    人在 `m01` 上纠正过一次之后，同族的仓库就得一直按壳处理（见 `archive.plan_archive`）。
    """
    try:
        common = load_common()
        warehouses = load_warehouses()
    except Exception as exc:                              # noqa: BLE001
        return {
            "plan": None,
            "counts": _blank_counts(),
            "degraded": True,
            "message": (f"i8 名单同步失败：{type(exc).__name__}: {exc}"
                        "（**未改动本地档案** —— 可稍后重试，或走手动导入）"),
        }
    plan = A.plan_archive(common_rows=common, warehouse_rows=warehouses,
                          existing=existing, taken_names=taken,
                          shell_names_in_archive=shells)
    return {"plan": plan, "counts": A.counts_of(plan), "degraded": False, "message": ""}


def sync_and_archive(
    session: Session,
    *,
    load_common: Loader,
    load_warehouses: Loader,
) -> dict:
    """完整动作：读现状 → 取数 → 计划 → **幂等落库**。→ 回执（含四类计数 + 新建条数）。"""
    projects = all_projects(session)
    existing = {str(p.name_full or "") for p in projects}
    taken = {str(p.warehouse_name or "") for p in projects}
    # ⭐ 档案里已经是壳的全名（含**人工纠正**成壳的）⇒ 交给计划，让判定按壳走（`TAIL-42`）
    shells = {str(p.name_full or "") for p in projects if p.project_type == TYPE_SHELL}

    out = build_plan(load_common=load_common, load_warehouses=load_warehouses,
                     existing=existing, taken=taken, shells=shells)
    if out["plan"] is None:                                # 降级：**一行都不写**
        out["created"] = []
        return out

    created = []
    for row in out["plan"]["create"]:
        created.append(create_project(
            session,
            project_type=row["project_type"],
            name_full=row["name_full"],
            warehouse_name=row["warehouse_name"],
            phid=row["phid"],
        ))
    out["created"] = created
    return out


__all__ = ["Loader", "build_plan", "sync_and_archive"]
