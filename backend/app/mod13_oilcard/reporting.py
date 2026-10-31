"""用油报表的项目/月事实；期初不摊为发生额，开票不冲减充值。"""
from calendar import monthrange
from datetime import date
import re
from uuid import uuid4

from sqlalchemy import select

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.core.money import ZERO, sum_money
from app.mod01_projects import service as projects
from .ledger import _amount
from .models import OilEntry, OilFeeCustom
from .service import _lock


def month_bounds(ym):
    if not isinstance(ym, str) or not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', ym) or ym[:4] == '0000':
        raise MustReportError('请选择有效的核算月份。')
    year, month = map(int, ym.split('-'))
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def fee_facts(session, *, project_id, end_ym):
    """截至月的独立月度事实；所有费用页面/导出共用，不汇入期初。"""
    _, end = month_bounds(end_ym)
    amounts = {}
    for row in session.scalars(select(OilEntry).where(OilEntry.project_id == project_id,
            OilEntry.entry_date <= end).order_by(OilEntry.id)):
        ym = row.entry_date.strftime('%Y-%m')
        amounts.setdefault(ym, []).append(row.amount)
    customs = {row.ym: row for row in session.scalars(select(OilFeeCustom).where(
        OilFeeCustom.project_id == project_id, OilFeeCustom.ym <= end_ym))}
    return [{'ym': ym, 'recharge': sum_money(amounts.get(ym, [])),
        'custom': customs[ym].amount if ym in customs else None,
        'remark': customs[ym].remark if ym in customs else '',
        'amount': sum_money([*amounts.get(ym, []), customs[ym].amount or ZERO] if ym in customs else amounts[ym])}
        for ym in sorted(amounts.keys() | customs.keys())]


def fee_custom_data(row):
    return {'project_id': row.project_id, 'ym': row.ym,
        'custom_amount': str(row.amount) if row.amount is not None else None,
        'remark': row.remark, 'version': row.version}


def fee_month(session, *, project_id, ym):
    start, end = month_bounds(ym)
    recharge = sum_money(session.scalars(select(OilEntry.amount).where(OilEntry.project_id == project_id,
        OilEntry.entry_date >= start, OilEntry.entry_date <= end)))
    row = session.scalar(select(OilFeeCustom).where(OilFeeCustom.project_id == project_id, OilFeeCustom.ym == ym))
    from app.mod09_fee import service as fees
    state = fees.oil_linkage_status(session, project_id=project_id)
    return {**(fee_custom_data(row) if row else {'project_id': project_id, 'ym': ym,
        'custom_amount': None, 'remark': '', 'version': None}),
        'enabled': state['enabled'], 'can_enable': state['can_enable'], 'recharge_amount': str(recharge),
        'fee_amount': str(sum_money([recharge, (row.amount or ZERO) if row else ZERO]))}


def save_fee_custom(session, *, project_id, ym, amount, remark, version):
    month_bounds(ym)
    _lock(session)
    project = projects.get_project(session, project_id, for_update=True)
    if project is None or project.project_type == 'shell':
        raise MustReportError('请选择项目档案中的正式项目。')
    from app.mod09_fee import service as fees
    if not fees.oil_linkage_status(session, project_id=project_id)['enabled']:
        raise MustReportError('此项目用油尚未接续核对，自定义额暂不能保存。')
    row = session.scalar(select(OilFeeCustom).where(OilFeeCustom.project_id == project_id,
        OilFeeCustom.ym == ym).with_for_update().execution_options(populate_existing=True))
    if (row.version if row else None) != version:
        raise DataConflictError('这个项目的当月自定义额已变化，请重读核对后处理保留输入。')
    value = _amount(amount) if amount is not None and amount.strip() else None
    if row is not None and (row.amount, row.remark) == (value, remark):
        return row
    if row is None:
        row = OilFeeCustom(project_id=project_id, ym=ym)
        session.add(row)
    row.amount, row.remark = value, remark
    row.version, row.updated_by = str(uuid4()), current_operator()
    session.flush()
    return row
