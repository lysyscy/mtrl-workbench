"""Business display fields for the next operation. Replay owns all validation."""
from dataclasses import dataclass
from decimal import Decimal
import json


@dataclass(frozen=True)
class Display:
    area: str
    object_name: str
    identity: tuple[str, ...]
    fields: dict[str, str]
    context: tuple[str, ...] = ()
    presence: str = '在册状态'


DISPLAY = {
    'payment_notice': Display('付款通知书', '通知书', ('bill_no',), {
        'category': '分类', 'jc_supplier': '集采实际供应商', 'excluded': '剔除状态', 'exclude_source': '剔除来源',
    }, ('bill_name', 'project_name')),
    'project': Display('项目档案', '项目', ('name_full', 'warehouse_name', 'disp'), {
        'disp': '项目简称', 'ord': '排序值',
    }),
    'opening_balance': Display('欠款台账', '历史结余', ('project_id',), {
        'cutoff_ym': '截至月份', 'settle_amount': '结算金额', 'paid_amount': '付款金额',
        'remark': '备注', 'entry_kind': '记录类型',
    }, ('category', 'cutoff_ym')),
    'ledger_remark': Display('欠款台账', '台账备注', ('project_id',), {'remark': '备注'}, ('category', 'ym')),
    'fee_item': Display('特殊费用', '费用项', ('name',), {'name': '费用项名称', 'deleted': '费用项状态'},
                        ('project_id',), '费用项状态'),
    'fee_monthly_amount': Display('特殊费用', '月度费用', ('fee_item_id', 'item_name'), {
        'item_name': '费用项名称', 'amount': '金额',
    }, ('project_id', 'ym')),
    'analysis_big_manual': Display('月度会大表', '项目月报', ('warehouse_name', 'project_id'), {
        'open_ym': '开工年月', 'mech_est': '预计机械费', 'contract_price': '合同价',
        'output_cum': '累计产值', 'note': '备注',
    }, ('ym',)),
    'analysis_big_month_project': Display('月度会大表', '本月项目', ('warehouse_name',), {'seq': '顺序'}, ('ym',)),
    'weldgas_balance': Display('收发结存与提取', '焊材气体历史金额', ('warehouse_name',), {
        'amount': '历史金额',
    }, ('kind',)),
    'proc_material_manual': Display('过程资料', '材料历史值', ('warehouse_name', 'project_id'), {
        'amount': '金额',
    }, ('ym', 'column_key')),
    'jc_contract': Display('集采台账', '合同', ('contract_no', 'bill_name'), {
        'contract_no': '合同编号', 'contract_date': '合同日期', 'contract_date_locked': '合同日期锁定',
        'material_name': '材料名称', 'supplier': '供应商', 'contract_amt': '合同金额',
        'trade_co': '贸易公司', 'trade_contract_amt': '贸易合同金额', 'tag': '台账标记', 'arch': '归档状态',
        'arch_no': '档案号', 'ret_date': '退回日期', 'remark': '备注',
        'payment_term': '账期', 'payment_method': '付款方式',
    }, ('bill_name', 'project_id')),
    'oil_card': Display('油卡管理／账户与油卡', '实体油卡', ('card_no',), {
        'card_no': '卡号', 'kind': '主副卡类型', 'status': '在用状态',
        'parent_card_id': '主卡', 'remark': '备注', 'display_order': '排序值',
    }),
    'oil_account': Display('油卡管理／账户与油卡', '用卡账户', ('name',), {
        'name': '账户名称', 'project_id': '项目', 'card_id': '实体油卡',
        'status': '在用状态', 'remark': '备注', 'display_order': '排序值',
    }, ('project_id',)),
    'oil_account_assignment': Display('油卡管理／账户与油卡', '账户关联', ('account_id',), {
        'card_id': '实体油卡', 'previous_card_id': '原实体油卡', 'change_kind': '关联类型', 'project_id': '项目',
    }),
    'oil_entry': Display('油卡管理／充值与调整', '账务记录', ('account_id', 'project_id'), {
        'kind': '类型', 'account_id': '用卡账户', 'project_id': '项目', 'card_id': '实体油卡',
        'date_text': '日期原文', 'entry_date': '入账日期', 'amount': '金额', 'remark': '备注', 'deleted': '充值台账',
    }, ('kind', 'entry_date', 'amount'), '充值台账'),
    'oil_invoice': Display('油卡管理／发票台账', '发票', ('invoice_no', 'manual_date_text'), {
        'invoice_no': '发票号码', 'invoice_date': '开票日期', 'amount': '开票金额', 'card_no': '卡号',
        'status': '登记状态', 'reason': '状态说明', 'remark': '备注', 'kind': '票据类型',
        'related_invoice_id': '关联发票', 'review_json': '原件核对', 'change_note': '更正说明',
        'void_date': '作废日期', 'deleted': '发票台账', 'manual_date_text': '登记日期原文',
        'manual_cutoff_ym': '登记截至月',
    }, ('invoice_date', 'amount'), '发票台账'),
    'oil_invoice_allocation': Display('油卡管理／发票台账', '发票分配', ('invoice_id',), {
        'account_id': '用卡账户', 'project_id': '项目', 'card_id': '实体油卡', 'amount': '分配金额',
    }, ('account_id',)),
    'oil_invoice_number': Display('油卡管理／发票台账', '发票号码登记', ('number',), {}, ('invoice_id',)),
    'oil_fee_custom': Display('特殊费用', '用油自定义额', ('project_id',), {'amount': '金额', 'remark': '备注'}, ('ym',)),
    'oil_big_custom': Display('月度会大表', '用油额外值', ('project_id',), {'amount': '金额', 'remark': '备注'}, ('ym',)),
}

ENUMS = {
    'category': {'material': '辅材', 'mechanical': '机械', 'jc': '集采'},
    'excluded': {False: '未剔除', True: '已剔除'},
    'exclude_source': {'': '无剔除来源', 'manual': '手动剔除', 'rule': '自动剔除'},
    'deleted': {False: '在台账中', True: '已移除'},
    'entry_kind': {'manual': '手动', 'month': '按月'},
    'status': {'active': '在用', 'archived': '已归档', 'registered': '已登记', 'pending': '待处理', 'voided': '已作废'},
    'kind': {'primary': '主卡', 'secondary': '副卡', 'normal': '普通发票', 'credit': '红票',
             'recharge': '充值', 'adjustment': '调整', 'refund': '退款', 'transfer_out': '转出', 'transfer_in': '转入',
             'weld': '焊材', 'gas': '气体'},
    'change_kind': {'assignment': '关联变更', 'replacement': '换卡'},
}
MONEY = {'amount', 'settle_amount', 'paid_amount', 'mech_est', 'contract_price', 'output_cum',
         'contract_amt', 'trade_contract_amt'}
REFERENCES = {
    'project_id': ('project', '项目', ('disp', 'name_full', 'warehouse_name')),
    'account_id': ('oil_account', '账户', ('name',)),
    'card_id': ('oil_card', '油卡', ('card_no',)),
    'parent_card_id': ('oil_card', '主卡', ('card_no',)),
    'previous_card_id': ('oil_card', '原油卡', ('card_no',)),
    'fee_item_id': ('fee_item', '费用项', ('name',)),
    'invoice_id': ('oil_invoice', '发票', ('invoice_no', 'manual_date_text')),
    'related_invoice_id': ('oil_invoice', '关联发票', ('invoice_no', 'manual_date_text')),
}


def _named(row, keys):
    return next((row[key] for key in keys if row.get(key)), None)


def _value(key, value, related):
    if value is None:
        return None
    if key in REFERENCES:
        table, label, keys = REFERENCES[key]
        return _named(related.get((table, value), {}), keys) or f'{label} #{value}'
    if key in MONEY:
        return f'¥{Decimal(str(value)):,.2f}'
    if isinstance(value, bool):
        return ENUMS.get(key, {}).get(value, '是' if value else '否')
    if isinstance(value, (str, int)):
        return ENUMS.get(key, {}).get(value, str(value)) or None
    return None


def _reviews(raw):
    if not isinstance(raw, str):
        return {}
    records = json.loads(raw)
    return records if isinstance(records, dict) else {}


def _review_values(current, result):
    try:
        first, second = _reviews(current), _reviews(result)
    except ValueError:
        return '历史核对内容', '更新核对内容'
    keys = sorted(key for key in first.keys() | second.keys() if first.get(key) != second.get(key))

    def notes(records):
        parts = []
        for key in keys:
            item = records.get(key)
            parts.append(str(item.get('note') or '已记录核对结论') if isinstance(item, dict) else '未记录核对结论')
        return '\n'.join(parts) or None

    return notes(first), notes(second)


def _record(change, source, target, related):
    spec = DISPLAY.get(change['table'])
    current, result = change[source], change[target]
    row = current if current is not None else result
    if spec is None or row is None:
        return dict(type='历史记录', area='操作历史', name=f'记录 #{change["id"]}', context=[], fields=[],
                    removes=result is None)

    related = {**related, **{(parent['table'], parent['id']): parent['data'] or {}
                            for parent in change.get('parents', ())}}
    field_values = {**row, 'bill_name': (row.get('fields') or {}).get('BillName') if change['table'] == 'payment_notice'
                    else row.get('bill_name')}
    name = next((value for key in spec.identity if (value := _value(key, field_values.get(key), related))),
                f'{spec.object_name} #{change["id"]}')
    context = list(dict.fromkeys(value for key in spec.context
                                if (value := _value(key, field_values.get(key), related)) and value != name))
    if change['table'] == 'oil_invoice':
        if row.get('invoice_no'):
            name = f'发票号码 {name}'
        elif row.get('manual_date_text'):
            name = f'手工登记 · {name}'
        context = [f'{spec.fields[key]} {value}' for key in spec.context
                   if (value := _value(key, row.get(key), related))]
    fields = []
    if current is None or result is None:
        left, right = ('无此记录', '有此记录') if current is None else ('有此记录', '无此记录')
        fields.append(dict(label=spec.presence, current=left, result=right))
    for key, label in spec.fields.items():
        if key == 'deleted' and (current is None or result is None):
            continue
        left, right = (current or {}).get(key), (result or {}).get(key)
        if key == 'deleted' and current is not None and result is not None:
            left, right = bool(left), bool(right)
        if left == right:
            continue
        if key == 'review_json':
            left, right = _review_values(left, right)
        else:
            left = '无此记录' if current is None else _value(key, left, related)
            right = '无此记录' if result is None else _value(key, right, related)
        if left != right:
            fields.append(dict(label=label, current=left, result=right))
    removes = result is None or (current is not None and not current.get('deleted') and bool((result or {}).get('deleted')))
    return dict(type=spec.object_name, area=spec.area, name=name, context=context, fields=fields, removes=removes)


def describe(operation, direction):
    source, target = ('after', 'before') if direction == 'undo' else ('before', 'after')
    related = {(change['table'], change['id']): change[source] or change[target] or {} for change in operation.changes}
    records = [_record(change, source, target, related) for change in operation.changes]
    return dict(id=operation.id, records=records)
