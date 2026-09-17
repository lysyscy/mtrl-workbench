"""`MOD-04` 的**项目匹配视图** —— 抽成**中立件**（`router.py` 与 `plan_api_router.py` 共用）。

⚠️ **为什么单独一件**：两个路由件都要用它俩；若让其中一个去 `import` 另一个，
   就会形成 `router ↔ plan_api_router` 的**循环 import**（本仓踩过这个坑 ——
   记忆 §八「多 router 共用件必须抽中立件」）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod01_projects.models import Project
from app.mod04_plan.domain import ProjectBrief


def project_briefs(session: Session) -> list[ProjectBrief]:
    """档案行 → 匹配用视图（**只带匹配所需的三个字段**）。"""
    return [
        ProjectBrief(id=p.id, disp=p.disp or "", warehouse_name=p.warehouse_name,
                     name_full=p.name_full or "")
        for p in session.execute(select(Project)).scalars().all()
    ]


def project_label(session: Session, project_id: int) -> str:
    """项目 id → **填报值**（记展示名；拿不到则用仓库名）—— 与导入的「项目」列同一含义。"""
    for p in session.execute(select(Project)).scalars().all():
        if p.id == int(project_id):
            return p.disp or p.warehouse_name or p.name_full or ""
    return ""


__all__ = ["project_briefs", "project_label"]
