"""显式接续特殊费用用油；候选名称从不决定业务身份。"""
import json
from datetime import datetime

from sqlalchemy import select

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.mod01_projects import service as projects
from app.mod13_oilcard import service as oilcards
from .models import FeeItem, FeeManualItem, FeeOilBinding, LegacyFeeManualItem

OIL_KEY = 'oilcard:monthly'
OIL_NAME = '工程用油（油卡联动）'
READONLY_MESSAGE = '工程用油由油卡管理维护，请在用油联动中修改自定义额及备注。'


def status(session, *, project_id):
    row = session.execute(select(FeeOilBinding).where(FeeOilBinding.project_id == project_id)).scalar_one_or_none()
    empty = row is None and session.execute(select(FeeItem.id).where(
        FeeItem.project_id == project_id).limit(1)).first() is None and session.execute(select(LegacyFeeManualItem.id).where(
        LegacyFeeManualItem.project_id == project_id).limit(1)).first() is None
    return {'enabled': row is not None, 'can_enable': empty, 'fee_item_id': row.fee_item_id if row else None}


def is_bound(session, item_id):
    return session.execute(select(FeeOilBinding.id).where(FeeOilBinding.fee_item_id == item_id)).scalar_one_or_none() is not None


def review(session, *, project_id):
    """接续调用方必须读回并逐项确认的完整原事实，供过期检查及留证。"""
    items = list(session.scalars(select(FeeItem).where(FeeItem.project_id == project_id).order_by(FeeItem.id)))
    return [{'item_id': item.id, 'name': item.name, 'deleted': item.deleted,
        'months': [{'id': row.id, 'ym': row.ym, 'amount': str(row.amount)}
            for row in session.scalars(select(FeeManualItem).where(FeeManualItem.fee_item_id == item.id).order_by(FeeManualItem.id))]}
        for item in items]


def bind(session, *, project_id, fee_item_id, reviewed_items, converted_customs, source_note):
    """显式指定旧项或无旧项；调用方提供已核差额，绝不自动用旧总额作custom。"""
    project = projects.get_project(session, project_id, for_update=True)
    if project is None or project.project_type == 'shell' or not str(source_note).strip():
        raise MustReportError('用油接续需要正式项目及已核对依据。')
    if status(session, project_id=project_id)['enabled']:
        raise MustReportError('此项目用油联动已启用，请先核对已有接续依据。')
    # 所有旧写入口先锁FeeItem；确认时也锁定，再比较完整快照。
    list(session.scalars(select(FeeItem).where(FeeItem.project_id == project_id).order_by(FeeItem.id).with_for_update()))
    current = review(session, project_id=project_id)
    if current != reviewed_items:
        raise DataConflictError('旧特殊费用已变化，请重新核对接续清单。')
    old = next((item for item in current if item['item_id'] == fee_item_id and not item['deleted']), None)
    if fee_item_id is not None and old is None:
        raise MustReportError('指定的旧用油费用项不属于此项目或已删除。')
    months = [row['ym'] for row in old['months']] if old else []
    if sorted(row.get('ym', '') for row in converted_customs) != sorted(months):
        raise MustReportError('请逐月提供已核对的自定义差额及独立备注，不能直接沿用旧完整总额。')
    binding = FeeOilBinding(project_id=project_id, fee_item_id=fee_item_id,
        reviewed_json=json.dumps({'items': current, 'converted_customs': converted_customs}, ensure_ascii=False, sort_keys=True), source_note=source_note,
        enabled_by=current_operator())
    session.add(binding); session.flush()
    if old:
        # 绑定是结构切换；原金额保持，旧历史凭据从此不能越过接续改写原依据。
        session.get(FeeItem, fee_item_id).updated_at = datetime.now()
        session.flush()
    return status(session, project_id=project_id)


def effective_items(session, *, project_id, end_ym, items):
    binding = status(session, project_id=project_id)
    if not binding['enabled']:
        return items
    return [row for row in items if row.get('fee_item_id') != binding['fee_item_id']] + [
        {**row, 'key': OIL_KEY, 'name': OIL_NAME, 'manual': False}
        for row in oilcards.fee_facts(session, project_id=project_id, end_ym=end_ym)]
