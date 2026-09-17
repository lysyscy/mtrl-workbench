"""M2 切片 2 验收测试的公共桩（离线：不连库 / 不碰网络）。"""

from __future__ import annotations

from app.mod01_projects.models import (
    STATUS_ACTIVE,
    TYPE_NORMAL,
    Project,
)


def make_project(
    project_id: int,
    *,
    name_full: str = "",
    warehouse: str | None = None,
    disp: str | None = None,
    ptype: str = TYPE_NORMAL,
    status: str = STATUS_ACTIVE,
    order: int = 0,
    parent_shell_id: int | None = None,
    keywords: list[str] | None = None,
    phid: str = "",
) -> Project:
    """构造**内存态**档案行（不落库）。"""
    return Project(
        id=project_id,
        project_type=ptype,
        name_full=name_full,
        warehouse_name=warehouse,
        disp=(warehouse or "") if disp is None else disp,
        phid=phid,
        status=status,
        ord=order,
        parent_shell_id=parent_shell_id,
        match_keywords=list(keywords or []),
    )
