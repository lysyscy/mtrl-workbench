"""大表用油接续身份；保留旧完整金额，不推定额外值或备注。"""
import json

from sqlalchemy import select

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.core.money import to_money
from app.core.history import record_barrier
from app.core.session import current_name
from app.mod01_projects import service as projects
from app.mod09_fee import service as fees
from app.mod13_oilcard import service as oilcards
from .models import AnalysisBigManual, BigOilBinding


def _project(session, project_id):
    project = projects.get_project(session, project_id)
    if project is None or project.project_type == 'shell' or not project.warehouse_name:
        raise MustReportError('大表用油请选择有仓库身份的正式项目。')
    return project


def _old_rows(session, project, *, lock=False):
    stmt = select(AnalysisBigManual).where(AnalysisBigManual.warehouse_name == project.warehouse_name).order_by(AnalysisBigManual.id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return list(session.scalars(stmt))


def review(session, *, project_id):
    project = _project(session, project_id)
    return [{'id': row.id, 'ym': row.ym, 'warehouse': row.warehouse_name, 'project_id': row.project_id,
        'oil': str(to_money(row.oil)) if row.oil is not None else None}
        for row in _old_rows(session, project)]


def status(session, *, project_id):
    binding = session.scalar(select(BigOilBinding).where(BigOilBinding.project_id == project_id))
    if binding:
        return {'enabled': True, 'can_enable': False}
    fee_ready = fees.oil_linkage_status(session, project_id=project_id)['enabled']
    project = projects.get_project(session, project_id)
    valid = project is not None and project.project_type != 'shell' and bool(project.warehouse_name)
    empty = valid and not any(row.oil is not None for row in _old_rows(session, project))
    return {'enabled': False, 'can_enable': bool(fee_ready and empty)}


def enable(session, *, project_id, reviewed_rows, converted_customs, source_note):
    record_barrier(session, str(current_name() or current_operator()), '启用已核对的大表用油联动')
    oilcards.lock_reporting(session)
    projects.get_project(session, project_id, for_update=True)
    project = _project(session, project_id)
    if not str(source_note).strip() or not fees.oil_linkage_status(session, project_id=project_id)['enabled']:
        raise MustReportError('请先完成特殊费用用油接续，并提供大表已核对依据。')
    if status(session, project_id=project_id)['enabled']:
        raise MustReportError('此项目大表用油联动已启用，请核对已有接续依据。')
    _old_rows(session, project, lock=True)
    current = review(session, project_id=project_id)
    if current != reviewed_rows:
        raise DataConflictError('旧大表用油依据已变化，请重新核对接续清单。')
    if any(row['project_id'] not in (None, project_id) for row in current):
        raise MustReportError('旧大表仓库与项目归属不一致，请先核对。')
    old_months = [row['ym'] for row in current if row['oil'] is not None]
    if sorted(row.get('ym', '') for row in converted_customs) != sorted(old_months):
        raise MustReportError('请逐月提供已核对的大表额外值及独立备注，不能直接沿用旧完整总额。')
    session.add(BigOilBinding(project_id=project_id, reviewed_json=json.dumps(
        {'rows': current, 'converted_customs': converted_customs}, ensure_ascii=False, sort_keys=True),
        source_note=source_note, enabled_by=current_operator()))
    session.flush()
    for row in converted_customs:
        oilcards.stage_big_custom(session, project_id=project_id, ym=row['ym'], amount=row['amount'], remark=row['remark'])
    return status(session, project_id=project_id)


def enable_empty(session, *, project_id):
    if not status(session, project_id=project_id)['can_enable']:
        raise MustReportError('请先完成特殊费用接续；有旧大表用油金额的项目还需核对旧总额。')
    return enable(session, project_id=project_id, reviewed_rows=review(session, project_id=project_id),
        converted_customs=[], source_note='油卡页面明确启用；系统核对无旧大表完整用油金额。')


def apply_rows(session, rows, *, ym):
    bindings = {row.project_id for row in session.execute(select(BigOilBinding)).scalars()}
    by_warehouse = projects.warehouse_index(session)
    for row in rows:
        project = by_warehouse.get(row['warehouse'])
        row['oil_linked'] = bool(project and project.id in bindings)
        if row['oil_linked']:
            value = oilcards.big_oil_amount(session, project_id=project.id, ym=ym)
            row['manual']['oil'] = {'value': value, 'from': ''}
            row['carry_n'] = sum(bool(cell['from']) for cell in row['manual'].values())
