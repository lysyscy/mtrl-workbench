"""项目档案 / 字段留痕 仓储（`MOD-01`）。

依据：§2.3.1（命名与修改约束）· §2.7.2（归档不变式）· §2.7.3（`ord`）· §9.3（留痕范围）· 决策 5（占位名）。
⚠️ 落库走 ORM；schema 变更唯一入口 = 迁移。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DataIntegrityError, MustReportError
from app.mod01_projects.domain import (
    StatusChange,
    apply_status_change,
    can_create_small,
    ordered,
    reorder,
)
from app.mod01_projects.models import (
    PLACEHOLDER_PREFIX,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    TYPE_SHELL,
    TYPE_SMALL,
    Project,
    ProjectFieldLog,
)


def list_projects(session: Session, *, status: str | None = None, keyword: str = "") -> list[Project]:
    """按筛选取档案；**默认只筛「在建」**（§2.7）。返回顺序 = 自定义排序（归档后置 > `ord` > 原序）。"""
    stmt = select(Project)
    if status in (STATUS_ACTIVE, STATUS_ARCHIVED):
        stmt = stmt.where(Project.status == status)
    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        stmt = stmt.where(
            Project.name_full.like(like)
            | Project.warehouse_name.like(like)
            | Project.disp.like(like)
        )
    return ordered(list(session.execute(stmt).scalars().all()))


def all_projects(session: Session) -> list[Project]:
    return list(session.execute(select(Project)).scalars().all())


def export_phids(session: Session) -> str:
    """导出用的项目 id 串（i8 报表参数，技术栈 §9.8：`xmid` / `pc`）—— **保序去重**。

    ⭐ **唯一出口**：`MOD-07`（收发结存）/ `MOD-08`（库存单据）两条抓取链路共用这一份
    （此前两边各写一遍，且都漏了去重）。

    ⚠️ **必须去重**：`phid` 是 **i8 侧项目编号**，而**具体小微是壳下的仓、与壳共享同一个 `phid`**
    （`ACC-PRJ-AUTO-001/001-03` 建档就是这么建的）⇒ 不去重会把同一个项目**导出两遍**。
    真机实测（2026-09-17）：自动建了兰考那条小微后，13 条档案只剩 **12 个唯一 phid**。

    ⚠️ 空 ⇒ **报错不臆造**（没有项目就没法按项目导出）。
    """
    seen: list[str] = []
    for p in all_projects(session):
        phid = str(getattr(p, "phid", "") or "").strip()
        if phid and phid not in seen:
            seen.append(phid)
    if not seen:
        raise MustReportError(
            "本地项目档案里没有可用 phid（i8 项目编号）⇒ 无法按项目导出。"
            "请先「同步常用项目列表」（API-06）建档。"
        )
    return ",".join(seen)


def get_project(session: Session, project_id: int) -> Project | None:
    return session.get(Project, project_id)


def next_placeholder_name(session: Session) -> str:
    """占位仓库名 `未建仓-序号`（**事务内取号**，决策 5 / 链路 A）。

    ⚠️ 唯一约束在仓库名上 ⇒ 取号后若撞名由数据库拦下（`DataIntegrityError`），不静默改写。
    """
    n = int(
        session.execute(
            select(func.count()).select_from(Project).where(
                Project.warehouse_name.like(f"{PLACEHOLDER_PREFIX}%")
            )
        ).scalar_one()
    )
    for i in range(n + 1, n + 1000):
        name = f"{PLACEHOLDER_PREFIX}{i:02d}"
        exists = session.execute(
            select(Project.id).where(Project.warehouse_name == name)
        ).scalar_one_or_none()
        if exists is None:
            return name
    raise DataIntegrityError("占位名取号失败（连续 1000 个都占用）")


def create_project(
    session: Session,
    *,
    project_type: str,
    name_full: str,
    warehouse_name: str | None = None,
    disp: str = "",
    phid: str = "",
    parent_shell_id: int | None = None,
    match_keywords: list[str] | None = None,
) -> Project:
    """建档（新档案行）。`warehouse_name` 为空 ⇒ 自动取占位名（**壳除外** —— 壳没有仓库）。"""
    if project_type == TYPE_SHELL and warehouse_name:
        raise MustReportError("小微壳没有仓库 —— 建档时不得给壳写仓库名（§2.2）")

    if project_type == TYPE_SMALL and parent_shell_id:
        shell = session.get(Project, parent_shell_id)
        if shell is None:
            raise MustReportError(f"所属壳不存在：id={parent_shell_id}")
        can_create_small(shell)   # 001-05：已归档的壳下不许新建小微

    if project_type != TYPE_SHELL and not warehouse_name:
        warehouse_name = next_placeholder_name(session)   # 占位行（full_name 仍写全名 —— 扶正的钥匙）

    project = Project(
        project_type=project_type,
        name_full=(name_full or "").strip(),
        warehouse_name=warehouse_name,
        disp=(disp or warehouse_name or ""),
        phid=phid or "",
        status=STATUS_ACTIVE,
        ord=_next_ord(session),
        parent_shell_id=parent_shell_id,
        match_keywords=list(match_keywords or []),
    )
    session.add(project)
    session.flush()
    return project


def _next_ord(session: Session) -> int:
    mx = session.execute(select(func.max(Project.ord))).scalar_one_or_none()
    return int(mx or 0) + 1


def log_field(
    session: Session,
    project: Project,
    *,
    field: str,
    old_value: str,
    new_value: str,
    changed_by: str,
    note: str = "",
) -> ProjectFieldLog:
    """写一条字段留痕（§9.3：**只有**项目全名 / 项目状态留痕）。"""
    entry = ProjectFieldLog(
        project_id=project.id,
        field=field,
        old_value=str(old_value or ""),
        new_value=str(new_value or ""),
        note=note,
        changed_by=changed_by or "",
        changed_at=datetime.now(),
    )
    session.add(entry)
    session.flush()
    return entry


def set_status(
    session: Session,
    project: Project,
    new_status: str,
    *,
    changed_by: str,
) -> StatusChange:
    """改项目状态（归档 / 取消归档），**带不变式判定与留痕**。

    - 拦截（壳下有在建小微）⇒ **抛 `MustReportError`**（状态不改、**不写留痕**），消息里列明未归档小微。
    - 反向对称：归档壳下最后一个在建小微 ⇒ 壳**自动跟着归档**，并给壳**单独留痕**。
    - ⚠️ 只写 `status`（`writes` 只含该字段）—— **不动任何业务数据**。
    """
    projects = all_projects(session)
    change = apply_status_change(project, new_status, projects)
    if not change.allowed:
        raise MustReportError(change.message)

    id_to_project = {p.id: p for p in projects}
    for w in change.writes:
        target = id_to_project.get(w["id"])
        if target is None:
            continue
        if target.status == w["value"]:
            continue
        old = target.status
        target.status = w["value"]
        log_field(
            session,
            target,
            field="status",
            old_value=old,
            new_value=w["value"],
            changed_by=changed_by,
            note="壳自动跟随归档（反向对称）" if (target.id != project.id and w["id"] == project.id) else "",
        )
    # follow_ups 里的壳单独留痕（若上面没覆盖到）
    for fu in change.follow_ups:
        if fu.get("id") in id_to_project:
            log_field(
                session,
                id_to_project[fu["id"]],
                field="status",
                old_value=STATUS_ACTIVE,
                new_value=STATUS_ARCHIVED,
                changed_by=changed_by,
                note=fu.get("reason", ""),
            )
    session.flush()
    return change


def rename_full(
    session: Session, project: Project, new_full: str, *, changed_by: str
) -> None:
    """改项目全名（**可人工改 + 留痕**，§2.3.1）。"""
    new_full = (new_full or "").strip()
    if new_full == project.name_full:
        return
    old = project.name_full
    project.name_full = new_full
    log_field(
        session, project, field="name_full", old_value=old, new_value=new_full, changed_by=changed_by
    )
    session.flush()


def promote_placeholder(
    session: Session, project: Project, real_warehouse_name: str
) -> None:
    """**系统专用**：占位行扶正 —— 占位名（`未建仓-N`）→ 真实仓库名（§2.4.2 链路 B）。

    ⛔ **人工改名一律拒绝**（§2.3.1「仓库名不允许人工修改」/`ACC-PRJ-NAME-001/001-06`）：
       本函数**只认占位名**；拿到真实名的行 ⇒ 抛 `MustReportError`（**不静默改**）。
    ⚠️ 按 §9.3（留痕范围 = **项目全名 / 项目状态**）**不留痕** —— 扶正结果由调用方在
       **抓取回执 / 告警**里显式列出（§2.4.2 监测点「被打破时必须能察觉」）。
    ⚠️ 展示名若是沿用占位名的（建档时 `disp` 缺省取仓库名）⇒ **一并跟着换**，
       否则屏幕上会一直挂着「未建仓-1」（`ACC-PRJ-NAME-001/001-08`：展示名默认取仓库名）。
    """
    old = str(project.warehouse_name or "")
    if not old.startswith(PLACEHOLDER_PREFIX):
        raise MustReportError(
            f"只有占位行（{PLACEHOLDER_PREFIX}N）才能被系统扶正；"
            f"该行仓库名 = {old or '（空）'} ⇒ 人工不得修改仓库名（§2.3.1）"
        )
    real = (real_warehouse_name or "").strip()
    if not real:
        raise MustReportError("扶正目标仓库名为空 ⇒ 拒绝（不把真实名清成空）")
    if str(project.disp or "") == old:
        project.disp = real
    project.warehouse_name = real
    session.flush()


def set_disp(session: Session, project: Project, disp: str) -> None:
    """改展示名（**可改、不留痕**，§9.3）。"""
    project.disp = (disp or "").strip()
    session.flush()


def set_keywords(session: Session, project: Project, keywords: list[str]) -> None:
    """设置小微识别关键词（可多个、允许重复；**不留痕**）。"""
    seen: list[str] = []
    for k in keywords or []:
        k = (k or "").strip()
        if k and k not in seen:
            seen.append(k)
    project.match_keywords = seen
    session.flush()


def set_ord(
    session: Session,
    *,
    project_id: int,
    to_position: int | None = None,
    direction: str | None = None,
) -> list[tuple[int, int]]:
    """自定义排序（§2.7.3）→ 全表重编号 1..N；**不留痕**。"""
    projects = all_projects(session)
    assignments = reorder(projects, project_id=project_id, to_position=to_position, direction=direction)
    id_to_project = {p.id: p for p in projects}
    for pid, value in assignments:
        if pid in id_to_project:
            id_to_project[pid].ord = value
    session.flush()
    return assignments


def list_logs(session: Session, project_id: int) -> list[ProjectFieldLog]:
    return list(
        session.execute(
            select(ProjectFieldLog)
            .where(ProjectFieldLog.project_id == project_id)
            .order_by(ProjectFieldLog.id.desc())
        ).scalars().all()
    )


def list_recent_logs(
    session: Session, *, limit: int = 20
) -> list[tuple[ProjectFieldLog, str]]:
    """**全站**最近的字段留痕（新 → 旧），带项目标签。

    为什么要有"全站"版本：`m01` 页的「修改留痕」卡是**跨项目**的最近改动列表
    （原型 `V.m01` 里读的就是一个全局列表 `PJ_TRAIL`）⇒ 逐项目调 `list_logs` 取不出来。
    项目标签口径 = **展示名 → 仓库名 → 项目全名**（与 `pjDisp` 一致：屏幕上认哪个名字就用哪个）。
    """
    rows = session.execute(
        select(ProjectFieldLog, Project)
        .join(Project, Project.id == ProjectFieldLog.project_id)
        .order_by(ProjectFieldLog.id.desc())
        .limit(max(1, int(limit)))
    ).all()
    return [(log, str(p.disp or p.warehouse_name or p.name_full or "")) for log, p in rows]
