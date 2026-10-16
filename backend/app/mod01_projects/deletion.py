"""只删除没有任何业务引用、留痕或小微层级牵涉的项目档案。"""
from sqlalchemy import select, text

from app.core.errors import MustReportError
from app.core.references import project_references
from app.mod01_projects.models import Project, ProjectFieldLog


def impact(session, project_id, *, lock=False):
    from app.mod03_notice import service as notice
    from app.mod04_plan import service as plan
    from app.mod05_flow import service as flow
    from app.mod06_proc import service as proc
    from app.mod07_setl import service as setl
    from app.mod08_inv import service as inv
    from app.mod09_fee import service as fee
    from app.mod11_jc import service as jc

    if lock:
        session.execute(text("SET LOCAL lock_timeout = '3s'"))
        session.execute(text('LOCK TABLE project IN SHARE ROW EXCLUSIVE MODE'))
    p = session.execute(select(Project).where(Project.id == project_id)
                        .execution_options(populate_existing=True)).scalar_one_or_none()
    if p is None:
        raise MustReportError('项目档案已不存在，请刷新列表。')
    groups = project_references(session, ((ProjectFieldLog, '项目修改留痕'),),
                                p.id, p.warehouse_name, lock=lock)
    for provider in (notice, plan, flow, proc, setl, inv, fee, jc):
        groups += provider.project_references(session, p.id, p.warehouse_name, lock=lock)
    children = session.execute(select(Project).where(Project.parent_shell_id == p.id)).scalars().all()
    groups.append({'table': 'project', 'label': '所属小微', 'count': len(children),
                   'rows': [{'id': c.id, 'warehouse_name': c.warehouse_name, 'name_full': c.name_full}
                            for c in children]})
    reasons = [f"{g['label']} {g['count']} 条" for g in groups if g['count']]
    if p.parent_shell_id is not None or p.project_type == 'small':
        reasons.append('该档案属于具体小微')
    elif p.project_type not in ('normal', 'shell'):
        reasons.append('项目类型尚未确认')
    allowed = not reasons
    return {'project': {'id': p.id, 'name_full': p.name_full, 'warehouse_name': p.warehouse_name,
                        'project_type': p.project_type, 'status': p.status},
            'groups': groups, 'can_delete': allowed,
            'message': ('无业务引用，确认后只删除这一条档案。删除不可撤销。' if allowed else
                        '不能删除：' + '；'.join(reasons) + '。请保留档案，需要停用时使用归档。')}


def delete_project(session, project_id):
    session.flush()
    preview = impact(session, project_id, lock=True)
    if not preview['can_delete']:
        raise MustReportError(preview['message'])
    row = session.get(Project, project_id)
    session.delete(row)
    session.flush()
    return {'ok': True, 'id': project_id, 'message': '项目档案已删除。'}
