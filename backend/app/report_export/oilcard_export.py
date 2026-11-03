"""油卡总台账及兼容单表出口；取数与金额合计归业务服务。"""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.core.money import ZERO, to_money
from app.report_export.save import workbook_bytes

COLUMNS = (('记录编号', 'id'), ('日期', 'date_text'), ('类型', 'kind_label'),
           ('项目', 'project'), ('用卡账户', 'account'), ('实体卡号', 'card'),
           ('金额', 'amount'), ('备注', 'remark'), ('关联原充值', 'related_entry_id'), ('转账关联编号', 'transfer_id'))
INVOICE_COLUMNS = (('记录编号', 'id'), ('开票日期', 'invoice_date'), ('发票号', 'invoice_no'),
    ('项目', 'project'), ('用卡账户', 'account'), ('价税合计', 'amount'), ('已登记金额', 'registered_amount'),
    ('备注', 'remark'), ('待核事项', 'issues'), ('票据关系', 'kind_label'),
    ('关联原票编号', 'related_invoice_id'), ('更正或后续依据', 'change_note'))
STATUS_LABELS = {'registered': '已登记', 'pending': '待确认', 'voided': '作废'}


def _workbook():
    workbook = Workbook()
    workbook.remove(workbook.active)
    return workbook


def _sheet(workbook, title, columns, rows, *, money=(), widths=(), totals=None, total_label='合计'):
    sheet = workbook.create_sheet(title)
    sheet.append([label for label, _ in columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
    for row_index, row in enumerate(rows, 2):
        for column, (_, key) in enumerate(columns, 1):
            value = row.get(key)
            cell = sheet.cell(row_index, column)
            if key in money:
                cell.value = to_money(value) if value is not None else None
                cell.number_format = '#,##0.00'
            else:
                cell.value = value
                if isinstance(value, str):
                    cell.data_type = 's'
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    last_data_row = sheet.max_row
    if totals is not None:
        total_row = last_data_row + 1
        sheet.cell(total_row, 1, total_label)
        for column, (_, key) in enumerate(columns, 1):
            if key in totals:
                sheet.cell(total_row, column, to_money(totals[key])).number_format = '#,##0.00'
        for cell in sheet[total_row]:
            cell.font = Font(bold=True)
    for column, width in enumerate(widths or (24,) * len(columns), 1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = f'A1:{get_column_letter(len(columns))}{last_data_row}'
    return sheet


def _recharges(workbook, snapshot):
    _sheet(workbook, '充值台账', COLUMNS, snapshot['rows'], money=('amount',),
        totals={'amount': snapshot['total_amount']}, widths=(12, 22, 10, 28, 24, 30, 18, 40, 16, 40))


def _invoice_rows(snapshot):
    for row in snapshot['rows']:
        issues = [row['reason'], *(o['reason'] for o in row['originals'] if o['outcome'] == 'conflict' and not o['resolution'])]
        yield {**row, 'registered_amount': row['amount'] if row['status'] == 'registered' else ZERO,
            'issues': '；'.join(x for x in issues if x), 'status_label': STATUS_LABELS[row['status']],
            'kind_label': '作废' if row['status'] == 'voided' else '红冲' if row['kind'] == 'credit' else '普通发票',
            'original_count': len(row['originals'])}


def _invoices(workbook, snapshot, *, total=False):
    columns = INVOICE_COLUMNS + ((('完整卡号', 'card_no'), ('状态', 'status_label'),
        ('作废日期', 'void_date'), ('原件份数', 'original_count')) if total else ())
    _sheet(workbook, '发票台账', columns, _invoice_rows(snapshot), money=('amount', 'registered_amount'),
        totals={'registered_amount': snapshot['total_amount']},
        widths=(12, 16, 28, 28, 24, 18, 18, 40, 60, 16, 16, 40) + ((30, 12, 16, 12) if total else ()))


def build(snapshot):
    workbook = _workbook()
    _recharges(workbook, snapshot)
    return workbook_bytes(workbook)


def build_invoices(snapshot):
    workbook = _workbook()
    _invoices(workbook, snapshot)
    return workbook_bytes(workbook)


def build_total(snapshot):
    workbook = _workbook()
    reconciliation = snapshot['reconciliation']
    amounts = ('opening_amount', 'recharge_amount', 'total_amount', 'invoiced_amount', 'difference_amount')
    _sheet(workbook, '核对汇总', (('账户编号', 'account_id'), ('用卡账户', 'account'),
        ('账户状态', 'account_status'), ('核算项目', 'project'), ('归属', 'attribution'),
        ('实体卡编号', 'card_id'), ('实体卡号', 'card'), ('主卡编号', 'primary_card_id'),
        ('主卡号', 'primary_card'), ('已确认期初', 'opening_amount'), ('充值发生额', 'recharge_amount'),
        ('累计充值', 'total_amount'), ('已登记开票', 'invoiced_amount'), ('差额', 'difference_amount'),
        ('账户备注', 'account_remark'), ('主卡备注', 'primary_remark')), reconciliation['rows'],
        money=amounts, totals={key: reconciliation[key] for key in amounts},
        widths=(12, 24, 12, 28, 12, 12, 30, 12, 30, 18, 18, 18, 18, 18, 40, 40))
    _recharges(workbook, snapshot['ledger'])
    _invoices(workbook, snapshot['invoices'], total=True)
    allocations = [{**row, 'status_label': STATUS_LABELS[row['status']],
        'kind_label': '红冲' if row['kind'] == 'credit' else '普通发票'} for row in snapshot['allocations']]
    _sheet(workbook, '发票分配', (('分配编号', 'id'), ('发票记录编号', 'invoice_id'), ('发票号', 'invoice_no'),
        ('开票日期', 'invoice_date'), ('状态', 'status_label'), ('票据关系', 'kind_label'),
        ('项目编号', 'project_id'), ('核算项目', 'project'), ('账户编号', 'account_id'), ('用卡账户', 'account'),
        ('实体卡编号', 'card_id'), ('实体卡号', 'card'), ('分配金额', 'amount'), ('已登记金额', 'registered_amount')),
        allocations, money=('amount', 'registered_amount'), totals={'registered_amount': snapshot['invoices']['total_amount']},
        widths=(12, 16, 28, 16, 12, 16, 12, 28, 12, 24, 12, 30, 18, 18))
    _sheet(workbook, '用卡账户', (('账户编号', 'id'), ('用卡账户', 'name'), ('项目编号', 'project_id'),
        ('当前项目', 'project'), ('实体卡编号', 'card_id'), ('当前实体卡号', 'card'),
        ('状态', 'status_label'), ('备注', 'remark')), snapshot['accounts'], widths=(12, 24, 12, 28, 12, 30, 12, 40))
    _sheet(workbook, '实体油卡', (('实体卡编号', 'id'), ('完整卡号', 'card_no'), ('类型', 'kind_label'),
        ('所属主卡编号', 'parent_card_id'), ('所属主卡号', 'parent_card'), ('状态', 'status_label'), ('备注', 'remark')),
        snapshot['cards'], widths=(12, 30, 12, 16, 30, 12, 40))
    _sheet(workbook, '期初核对', (('期初编号', 'id'), ('来源标识', 'source_key'), ('来源依据', 'source_note'),
        ('原日期标记', 'original_date_text'), ('截至月份', 'cutoff_ym'), ('确认状态', 'status'),
        ('项目编号', 'project_id'), ('核算项目', 'project'), ('账户编号', 'account_id'), ('用卡账户', 'account'),
        ('实体卡编号', 'card_id'), ('实体卡号', 'card'), ('原始金额', 'amount'), ('已确认计入金额', 'booked_amount'),
        ('备注', 'remark')), snapshot['openings'], money=('amount', 'booked_amount'),
        totals={'booked_amount': reconciliation['opening_amount']}, total_label='已确认期初合计',
        widths=(12, 40, 40, 22, 16, 12, 12, 28, 12, 24, 12, 30, 18, 20, 40))
    _sheet(workbook, '账户关联历史', (('关联编号', 'id'), ('账户编号', 'account_id'), ('用卡账户', 'account'),
        ('项目编号', 'project_id'), ('关联项目', 'project'), ('实体卡编号', 'card_id'), ('实体卡号', 'card'),
        ('原实体卡编号', 'previous_card_id'), ('原实体卡号', 'previous_card'), ('变更类型', 'change_label'),
        ('变更时间', 'changed_at'), ('操作人', 'changed_by')), snapshot['assignments'],
        widths=(12, 12, 24, 12, 28, 12, 30, 16, 30, 16, 28, 24))
    _sheet(workbook, '用油自定义', (('记录编号', 'id'), ('金额类型', 'kind'), ('项目编号', 'project_id'),
        ('项目', 'project'), ('核算月', 'ym'), ('自定义金额', 'amount'), ('备注', 'remark')),
        snapshot['customs'], money=('amount',), widths=(12, 30, 12, 28, 16, 18, 40))
    return workbook_bytes(workbook)
