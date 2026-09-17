"""`MOD-01` 路由（项目档案：列表 / 候选 / 建档 / 归档 / 排序 / 归属）。

⚠️ 薄层：判定逻辑全在 `domain.py`（纯函数）、落库在 `repository.py`。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod01_projects import repository as repo
from app.mod01_projects.domain import build_candidates, ordered, resolve_ownership
from app.mod01_projects.models import Project
from app.mod01_projects.schemas import (
    CandidateOut,
    CreateProjectRequest,
    LogOut,
    OrdRequest,
    OwnershipRequest,
    OwnershipResponse,
    ProjectOut,
    StatusRequest,
    TrailOut,
    UpdateProjectRequest,
)

router = APIRouter(prefix="/api/m01", tags=["mod01"])

# 留痕字段 → 中文列名（§9.3 只有这两处；未知字段**原样返回**、不吞）
FIELD_LABEL = {"name_full": "项目全名", "status": "项目状态"}


def _out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id,
        project_type=p.project_type,
        name_full=p.name_full,
        warehouse_name=p.warehouse_name,
        disp=p.disp,
        phid=p.phid,
        status=p.status,
        ord=p.ord,
        parent_shell_id=p.parent_shell_id,
        match_keywords=list(p.match_keywords or []),
        is_placeholder=p.is_placeholder,
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    status: str = Query("active", description="active / archived / all（**默认在建**）"),
    keyword: str = Query("", description="按全名 / 仓库名 / 展示名模糊匹配"),
) -> list[ProjectOut]:
    st = None if status == "all" else status
    with session_scope() as s:
        return [_out(p) for p in repo.list_projects(s, status=st, keyword=keyword)]


@router.get("/candidates", response_model=list[CandidateOut])
def candidates(include_archived: bool = Query(True, description="候选**含归档**（排最后 + 标注）")) -> list[CandidateOut]:
    """项目候选（§2.7.1 / §2.7.4）：键 = 仓库名 · 显示 = 展示名。"""
    with session_scope() as s:
        rows = list(s.execute(select(Project)).scalars().all())
        cands = build_candidates(rows)
    out = [
        CandidateOut(key=c.key, display=c.display, archived=c.archived, placeholder=c.placeholder)
        for c in cands
    ]
    if not include_archived:
        out = [c for c in out if not c.archived]
    return out


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int) -> ProjectOut:
    with session_scope() as s:
        p = repo.get_project(s, project_id)
        if p is None:
            raise HTTPException(status_code=404, detail="档案行不存在")
        return _out(p)


@router.post("/projects", response_model=ProjectOut)
def create_project(req: CreateProjectRequest) -> ProjectOut:
    """建档（链路 A）。⚠️ 壳不写仓库；普通项目/小微不传仓库名则取**占位名**。"""
    with session_scope() as s:
        p = repo.create_project(
            s,
            project_type=req.project_type,
            name_full=req.name_full,
            warehouse_name=req.warehouse_name,
            disp=req.disp,
            phid=req.phid,
            parent_shell_id=req.parent_shell_id,
            match_keywords=req.match_keywords,
        )
        return _out(p)


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, req: UpdateProjectRequest) -> ProjectOut:
    """改全名（**留痕**）/ 展示名（不留痕）/ 关键词（不留痕）。仓库名**不可改**（§2.3.1）。"""
    with session_scope() as s:
        p = repo.get_project(s, project_id)
        if p is None:
            raise HTTPException(status_code=404, detail="档案行不存在")
        if req.name_full is not None:
            repo.rename_full(s, p, req.name_full, changed_by=req.changed_by or current_operator())
        if req.disp is not None:
            repo.set_disp(s, p, req.disp)
        if req.match_keywords is not None:
            repo.set_keywords(s, p, req.match_keywords)
        return _out(p)


@router.put("/projects/{project_id}/status", response_model=ProjectOut)
def set_status(project_id: int, req: StatusRequest) -> ProjectOut:
    """归档 / 取消归档（§2.7.2 不变式：壳下有在建小微 ⇒ **拦截并列出**，状态不改、不写留痕）。"""
    with session_scope() as s:
        p = repo.get_project(s, project_id)
        if p is None:
            raise HTTPException(status_code=404, detail="档案行不存在")
        repo.set_status(s, p, req.status, changed_by=req.changed_by or current_operator())
        return _out(p)


@router.put("/projects/{project_id}/ord", response_model=list[ProjectOut])
def set_ord(project_id: int, req: OrdRequest) -> list[ProjectOut]:
    """自定义排序（§2.7.3）：填序号 = 插到位置；上移/下移 = 与相邻对调；**不跨在建/归档分界**。"""
    if req.to_position is None and req.direction is None:
        raise MustReportError("请给 to_position（插到第几位）或 direction（up/down）")
    with session_scope() as s:
        repo.set_ord(
            s, project_id=project_id, to_position=req.to_position, direction=req.direction
        )
        return [_out(p) for p in repo.list_projects(s, status=None)]


@router.get("/projects/{project_id}/logs", response_model=list[LogOut])
def project_logs(project_id: int) -> list[LogOut]:
    """字段留痕（仅**项目全名 / 项目状态**）。"""
    with session_scope() as s:
        rows = repo.list_logs(s, project_id)
        return [
            LogOut(
                id=r.id,
                field=r.field,
                old_value=r.old_value,
                new_value=r.new_value,
                note=r.note,
                changed_by=r.changed_by,
                changed_at=r.changed_at.isoformat(timespec="seconds"),
            )
            for r in rows
        ]


@router.get("/trails", response_model=list[TrailOut])
def trails(limit: int = Query(20, ge=1, le=200)) -> list[TrailOut]:
    """**最近字段留痕**（§9.3：只有项目全名 / 项目状态）—— 供 `m01`「修改留痕」卡。

    ⚠️ 与 `/projects/{id}/logs` 分工：那个是**单行**明细，这个给**跨项目**的最近改动。
    """
    with session_scope() as s:
        return [
            TrailOut(
                at=e.changed_at.isoformat(sep=" ", timespec="seconds"),
                project=label,
                field=e.field,
                field_label=FIELD_LABEL.get(e.field, e.field),
                before=e.old_value,
                after=e.new_value,
                by=e.changed_by,
                note=e.note or "",
            )
            for e, label in repo.list_recent_logs(s, limit=limit)
        ]


@router.post("/ownership", response_model=OwnershipResponse)
def ownership(req: OwnershipRequest) -> OwnershipResponse:
    """归属判定（§2.5.1 · 链路 C）。**先判是不是壳**；命中多个 / 未命中 ⇒ 交给用户指定。"""
    with session_scope() as s:
        projects = list(s.execute(select(Project)).scalars().all())
        d = resolve_ownership(name_full=req.name_full, doc_name=req.doc_name, projects=projects)
        cands: list[CandidateOut] = []
        if d.shell_id:
            children = [p for p in projects if p.parent_shell_id == d.shell_id]
            cands = [
                CandidateOut(
                    key=p.warehouse_name or "",
                    display=p.disp or p.warehouse_name or "",
                    archived=p.is_archived,
                    placeholder=p.is_placeholder,
                )
                for p in ordered(children)
            ]
        return OwnershipResponse(
            kind=d.kind,
            target_id=d.target_id,
            shell_id=d.shell_id,
            matched_ids=list(d.matched_ids),
            keyword_to_add=d.keyword_to_add,
            reason=d.reason,
            settled=d.settled,
            candidates=cands,
        )
