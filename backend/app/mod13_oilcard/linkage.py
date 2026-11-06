"""用油接续的事务编排；旧报表仍持有各自依据、绑定及版本保护。"""
from app.core.errors import MustReportError
from app.core.history import record_barrier
from app.core.identity import current_operator
from app.core.session import current_name
from app.mod09_fee import service as fees
from app.mod07_setl import service as big
from . import reporting
from .service import _lock


def enable_fee(session, *, project_id, fee_item_id, reviewed_items, converted_customs, source_note):
    # A rejected conversion must not leave a binding or a subset of custom amounts
    # behind, even when a caller handles the rejection inside its own transaction.
    with session.begin_nested():
        record_barrier(session, str(current_name() or current_operator()), '启用已核对的特殊费用用油联动')
        _lock(session)
        state = fees.bind_oil_linkage(session, project_id=project_id, fee_item_id=fee_item_id,
            reviewed_items=reviewed_items, converted_customs=converted_customs, source_note=source_note)
        for row in converted_customs:
            reporting.save_fee_custom(session, project_id=project_id, ym=row['ym'], amount=row['amount'],
                remark=row['remark'], version=None)
        return state


def enable_empty_fee(session, *, project_id):
    if not fees.oil_linkage_status(session, project_id=project_id)['can_enable']:
        raise MustReportError('此项目已有特殊费用依据，请先完成旧用油接续核对。')
    return enable_fee(session, project_id=project_id, fee_item_id=None, reviewed_items=[],
        converted_customs=[], source_note='油卡页面明确启用；系统核对无旧特殊费用项及原始记录。')


def enable_big(session, *, project_id, reviewed_rows, converted_customs, source_note):
    with session.begin_nested():
        record_barrier(session, str(current_name() or current_operator()), '启用已核对的大表用油联动')
        _lock(session)
        state = big.bind_big_oil(session, project_id=project_id, reviewed_rows=reviewed_rows,
            converted_customs=converted_customs, source_note=source_note)
        for row in converted_customs:
            reporting.stage_big_custom(session, project_id=project_id, ym=row['ym'],
                amount=row['amount'], remark=row['remark'])
        return state


def enable_empty_big(session, *, project_id):
    if not big.big_oil_status(session, project_id=project_id)['can_enable']:
        raise MustReportError('请先完成特殊费用接续；有旧大表用油金额的项目还需核对旧总额。')
    return enable_big(session, project_id=project_id, reviewed_rows=big.review_big_oil(session, project_id=project_id),
        converted_customs=[], source_note='油卡页面明确启用；系统核对无旧大表完整用油金额。')
