"""`MOD-01` 路由（项目档案：列表 / 候选 / 建档 / 归档 / 排序 / 归属）。

⚠️ 薄层：判定逻辑全在 `domain.py`（纯函数）、落库在 `repository.py`。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod01_projects import archive_pending as AP
from app.mod01_projects import pending as PE
from app.mod01_projects import repository as repo
from app.mod01_projects.domain import (
    build_candidates, norm_full_name, ordered, resolve_ownership, status_label,
)
from app.mod01_projects.models import Project
from app.mod01_projects.schemas import (
    ArchivePendingOut,
    ArchiveRowOut,
    ArchiveRowRequest,
    CandidateOut,
    CreateProjectRequest,
    LogOut,
    OrdRequest,
    OwnershipRequest,
    OwnershipResponse,
    ProjectOut,
    PromoteCandidatesOut,
    PromoteOut,
    PromotePendingOut,
    PromoteRequest,
    ProjectExportIn,
    PromoteRowOut,
    StatusRequest,
    TrailOut,
    TypeRequest,
    UpdateProjectRequest,
)

#: 「项目类型」的**中文文案** —— ⚠️ 与壳的 `pjType.text`（`index.html` 的枚举表）**同一份口径**。
#: ⚠️ 放在路由层是**有意的**：它是**展示层**的事（"给人看什么字"），不是领域判定
#:    （`domain.py` 只认 `normal/shell/small` 三个值本身）。
#: ⭐ 单独立在这里、⛔ 不散在导出端点里，是为了让下一个加端点的人一眼看见"只有一份"。
TYPE_TEXT = {"normal": "普通项目", "shell": "小微壳", "small": "具体小微"}

router = APIRouter(prefix="/api/m01", tags=["mod01"])

# 留痕字段 → 中文列名（§9.3 的那两处 ＋ `project_type`（人工覆盖判定，`TAIL-42`）；未知字段**原样返回**、不吞）
FIELD_LABEL = {"name_full": "项目全名", "status": "项目状态", "project_type": "项目类型"}


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


@router.post("/projects/export")
def export_projects(payload: ProjectExportIn) -> dict:
    """导出项目档案（`TAIL-04` · `REQ-R1` · §7.1）⇒ `{ok, filename, rows, content_b64}`。

    ⭐ **行** = 传入的那些 id（= **屏幕上看到的**，**连它的顺序一起**）；
    **列** = 页面表头去掉「操作」；**取值** = **页面显示的那个值**。
    ⚠️ 所以这里要先把三处"外键 / 英文枚举"换成**人看的字**（§7.1「取值一律与页面一致」）：
      · `project_type`（`normal/shell/small`）⇒ 中文（`TYPE_TEXT`，与壳的枚举表同一份）
      · `status`（`active/archived`）⇒ 中文（`domain.status_label` —— **它本来就有**，⛔ 别再写一份）
      · `parent_shell_id` ⇒ **父项目的全名**（页面上那格显示的就是全名）
      · `match_keywords`（列表）⇒ 顿号连接（页面上就是一串）

    ⚠️ **为什么取数是"全表捞一遍再按 id 挑"**：项目档案是**几十行**的小表（§2），
       一次 `select` 拿全量再按传入 id 过滤 + **保持传入顺序**，比逐 id 查更简单也更稳
       （逐 id 查要么 N 次查询、要么丢掉顺序）。⚠️ 表大了再改成 `WHERE id IN (...)` ＋ 排序。
    """
    import base64
    from datetime import date

    from app import export_registry as EXP
    X = EXP.get("pj")

    ids = [int(i) for i in (payload.ids or [])]
    with session_scope() as s:
        rows = list(s.execute(select(Project)).scalars().all())
    by_id = {p.id: p for p in rows}
    # ⚠️ **按传入的 id 顺序**出行（⛔ 不是按库里的顺序）—— 那是**屏幕上的行序**
    picked = [by_id[i] for i in ids if i in by_id]
    out = [{
        "ord": p.ord,
        "type_text": TYPE_TEXT.get(p.project_type, p.project_type),
        "disp": p.disp or "",
        "warehouse_name": p.warehouse_name or "",
        "name_full": p.name_full or "",
        "phid": p.phid or "",
        "status": status_label(p.status),
        "parent_full": (by_id[p.parent_shell_id].name_full
                        if p.parent_shell_id in by_id else ""),
        "keywords": "、".join(p.match_keywords or []),
    } for p in picked]
    blob = X.build_xlsx(out)
    name = f"项目档案_{date.today().strftime('%Y%m%d')}.xlsx"
    return {"ok": True, "filename": name, "rows": len(out),
            "content_b64": base64.b64encode(blob).decode("ascii")}


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


@router.get("/projects/{project_id}/delete-impact")
def project_delete_impact(project_id: int):
    from .deletion import impact

    with session_scope() as s:
        return impact(s, project_id)


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, confirmed: bool = Query(False)):
    from .deletion import delete_project as apply_delete

    if not confirmed:
        raise MustReportError('请先查看关联影响并确认删除。')
    with session_scope() as s:
        return apply_delete(s, project_id)


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


@router.put("/projects/{project_id}/type", response_model=ProjectOut)
def set_project_type(project_id: int, req: TypeRequest) -> ProjectOut:
    """**人工覆盖三类判定**（`TAIL-42`）：把一条行在「普通项目 ⇄ 小微壳」之间纠正。

    ⚠️ 这是**人工介入自动判定**的唯一出口 —— 判定口径与优先级仍在 `domain.classify_name`
       （`manual_override` 是它自己的参数）；本层只负责"把人的选择落库"＋仓库名的一致性
       （普通项目要仓库名、壳不要）＋留痕。⛔ `small` 不受理（具体小微由链路产生）。
    """
    with session_scope() as s:
        p = repo.get_project(s, project_id)
        if p is None:
            raise HTTPException(status_code=404, detail="档案行不存在")
        repo.set_type(
            s,
            p,
            req.project_type,
            warehouse_name=req.warehouse_name,
            changed_by=req.changed_by or current_operator(),
        )
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


@router.get("/promote-pending", response_model=PromotePendingOut)
def promote_pending() -> PromotePendingOut:
    """⭐ **「待人工指认」清单**（`TAIL-30`-③）—— `m01` 档案页的入口源。

    **为什么有这条**：链路 B 里「命中 ≥2 条非壳行 ⇒ 挂到哪一行」**必须人来做**（系统不猜），
    而这几条原本只在**抓取回执里出现一次**（一刷新就没了）⇒ `m01` 上没有入口。

    ⚠️ 只认**最近一次材料侧抓取**（`setl` / `inv`），且**逐条按当前档案现算** ——
       已经解决的不再摆着（否则就是让用户对着旧清单白干，`TAIL-41` 同族）。
    """
    with session_scope() as s:
        return PromotePendingOut(**PE.live_pending(s))


@router.get("/promote-candidates", response_model=PromoteCandidatesOut)
def promote_candidates(
    full: str = Query("", description="项目全名 —— **归一化后精确相等**（§17.2：不包含 / 不模糊）"),
) -> PromoteCandidatesOut:
    """该全名下的**候选档案行**（含归档行）—— 人工指认要先看见"有哪些行、哪几行是占位行"。

    ⚠️ 这是**读**（可按全名查候选）；**写**一律按 `id` 定位（铁律 5/6：禁止用名字反查）。
    ⚠️ 判定口径（先判壳 / ≥2 条）**不在本层重写** —— 它属于 `recovery.classify_hits`。
    """
    with session_scope() as s:
        rows = PE.candidates(s, full)
    return PromoteCandidatesOut(
        full_name=full, count=len(rows), rows=[PromoteRowOut(**r) for r in rows]
    )


@router.post("/promote", response_model=PromoteOut)
def promote(req: PromoteRequest) -> PromoteOut:
    """⭐ **人工指认的落库出口**（`TAIL-30`-③ 端点②）：把这条**真实仓库名**写到用户指定的那一行。

    判定与落库**唯一出口 = `repository.promote_placeholder`**（⛔ 本层不另写一份）：
      · 只有**占位行**（`未建仓-N`）能被扶正 —— 非占位行 ⇒ 明确拒（§2.3.1「仓库名不可人工修改」）；
      · 展示名若沿用占位名的 ⇒ 一并跟着换（否则屏幕一直挂「未建仓-N」）。

    ⚠️ **只做「指定到哪一行」**（用户 2026-09-18 裁定）：命中行**本该是壳**时的**类型纠正**另立 `TAIL-42`。
    ⚠️ 一致性守卫：这一行必须是**本次指认的那个全名**下的行（防"张冠李戴"）。
    """
    with session_scope() as s:
        row = repo.get_project(s, req.project_id)
        if row is None:
            raise MustReportError(f"档案行不存在（id={req.project_id}）—— 请刷新后重试")
        want_full = (req.full_name or "").strip()
        if want_full and norm_full_name(row.name_full) != norm_full_name(want_full):
            raise MustReportError(
                f"指认的行对不上：所选行 id={row.id} 的全名 = 「{row.name_full}」，"
                f"而本次要指认的全名是「{want_full}」—— 按 id 定位，⛔ 不用名字反查（铁律 5/6）"
            )
        old = str(row.warehouse_name or "")
        # 展示名**原本沿用占位名**的 ⇒ 扶正时会一并跟着换（`repository.promote_placeholder` 的口径）；
        # 人工设过展示名的 ⇒ 不动它。先记下来，好让回执说清到底动没动。
        followed = str(row.disp or "") == old
        repo.promote_placeholder(s, row, req.warehouse_name)
        real = str(row.warehouse_name or "")
        return PromoteOut(
            ok=True, id=row.id, old_warehouse_name=old, warehouse_name=real,
            disp=str(row.disp or ""), disp_followed=followed,
            message=(f"已扶正：占位名「{old}」→ 真实仓库名「{real}」"
                     + ("；展示名一并跟着换" if followed else "（展示名是人工设过的 ⇒ 未动它）")
                     + " —— 这是**系统写入**，不是人工改仓库名（§2.3.1）"),
        )


@router.get("/archive-pending", response_model=ArchivePendingOut)
def archive_pending() -> ArchivePendingOut:
    """⭐ **「待人工建档」清单**（`TAIL-45`）—— `m01` 那个入口的数据源。

    **为什么有这条**：链路 A ③-b 的「全名对应 ≥2 个仓库」**必须人选定一个**（系统不猜），
    而这条原先只在**同步回执**里报一次（一刷新就没了）⇒ `m01` 上**没有可点的入口**
    （就是 `chain_audit` 里 `A` 链路剩的那条红）。

    ⚠️ 只认**最近一次成功的「常用项目列表」同步**，且**逐条按当前档案现算** ——
       已挑过 / 已建过行的不再摆着（否则就是让用户对着旧清单白干，`TAIL-41` 同族）。
    """
    with session_scope() as s:
        return ArchivePendingOut(**AP.live_pending(s))


@router.post("/archive-row", response_model=ArchiveRowOut)
def archive_row(req: ArchiveRowRequest) -> ArchiveRowOut:
    """⭐ **选定一个仓库 ⇒ 就地建行**（`TAIL-45`）：把链路 A ③-b 的「列出」补成「可点」。

    三条守卫 ＋ 建档出口**唯一**（都在 `archive_pending.pick_row` 里，⛔ 本层不重写）：
    候选必须来自**那次同步报出的 i8 名单** · 该全名**还没有行**（决策 2：1 : 1） ·
    该仓库名**没被别行占用**。
    """
    with session_scope() as s:
        row = AP.pick_row(s, full_name=req.full_name, warehouse_name=req.warehouse_name)
        ptype = str(row.project_type or "")
        return ArchiveRowOut(
            ok=True, id=row.id, name_full=str(row.name_full or ""),
            warehouse_name=str(row.warehouse_name or ""),
            project_type=ptype, type_label=PE.TYPE_LABEL.get(ptype, ptype),
            disp=str(row.disp or ""),
            message=(f"已建档：{row.name_full} → 仓库「{row.warehouse_name}」"
                     f"（{PE.TYPE_LABEL.get(ptype, ptype)}）—— 这是**系统写入**（§9.4 仓库名以 i8 为准）；"
                     "⚠️ 同一项目的**其余仓库不再建行**"),
        )


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
