"""撤销白名单：只接无外部副作用、可按完整行版本验证的本地操作。"""
from app.core.history import Rule, bind_policies
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import LedgerRemark, OpeningBalance
from app.mod06_proc.models import ProcMaterialManual
from app.mod07_setl.models import AnalysisBigManual, AnalysisBigMonthProject, WeldGasBalance
from app.mod09_fee.models import FeeItem, FeeManualItem
from app.mod11_jc.models import JcContract
from app.mod13_oilcard.models import OilAccount, OilAccountAssignment, OilCard, OilEntry, OilInvoice, OilInvoiceAllocation, OilInvoiceNumber, OilFeeCustom, OilBigCustom


def configure():
    notice = Rule(PaymentNotice, frozenset({
        'excluded', 'exclude_source', 'category', 'jc_supplier',
    }))
    project = Rule(Project, frozenset({'disp', 'ord'}))
    opening = Rule(OpeningBalance, frozenset({'settle_amount', 'paid_amount', 'remark'}), True)
    historical = Rule(OpeningBalance, frozenset({'cutoff_ym', 'settle_amount', 'paid_amount', 'remark',
                        'entry_kind'}), True)
    remark = Rule(LedgerRemark, frozenset({'remark'}), True)
    fee = Rule(FeeManualItem, frozenset({'item_name', 'amount'}), True)
    fee_item = Rule(FeeItem, frozenset({'name', 'deleted'}), True)
    big = Rule(AnalysisBigManual, frozenset({
        'open_ym', 'mech_est', 'contract_price', 'output_cum', 'note',
    }), True, retired_fields=frozenset({'oil'}))
    big_projects = Rule(AnalysisBigMonthProject, frozenset({'seq'}), True)
    balance = Rule(WeldGasBalance, frozenset({'amount'}), True)
    material = Rule(ProcMaterialManual, frozenset({'amount'}), True)
    contract = Rule(JcContract, frozenset({
        'contract_no', 'contract_date', 'contract_date_locked', 'material_name', 'supplier',
        'contract_amt', 'trade_co', 'trade_contract_amt', 'tag', 'arch', 'arch_no',
        'ret_date', 'remark', 'payment_term', 'payment_method',
    }))
    oil_card = Rule(OilCard, frozenset({'card_no', 'kind', 'parent_card_id', 'remark', 'version', 'updated_by'}), True)
    oil_account = Rule(OilAccount, frozenset({'name', 'project_id', 'card_id', 'status', 'remark', 'version', 'updated_by'}), True)
    oil_assignment = Rule(OilAccountAssignment, frozenset(), True)
    oil_entry = Rule(OilEntry, frozenset({'kind', 'account_id', 'project_id', 'card_id', 'date_text',
        'entry_date', 'amount', 'remark', 'version', 'updated_by'}), True)
    oil_invoice = Rule(OilInvoice, frozenset({'invoice_no', 'invoice_date', 'amount', 'card_no', 'status', 'reason', 'remark', 'version', 'updated_by',
        'kind', 'related_invoice_id', 'review_json', 'change_note', 'void_date'}))
    oil_allocation = Rule(OilInvoiceAllocation, frozenset({'account_id', 'project_id', 'card_id', 'amount'}), True)
    oil_number = Rule(OilInvoiceNumber, frozenset(), True)
    oil_fee_custom = Rule(OilFeeCustom, frozenset({'amount', 'remark', 'version', 'updated_by'}), True)
    oil_big_custom = Rule(OilBigCustom, frozenset({'amount', 'remark', 'version', 'updated_by'}), True)
    bind_policies([
        ('POST', '/api/m03/actions/exclude', '剔除付款通知书', [notice]),
        ('POST', '/api/m03/actions/restore', '恢复付款通知书', [notice]),
        ('POST', '/api/m03/actions/category', '修改通知书分类', [notice]),
        ('POST', '/api/m03/actions/jc-supplier', '修改集采实际供应商', [notice]),
        ('PUT', r'/api/m01/projects/\d+', '修改项目展示资料', [project]),
        ('PUT', r'/api/m01/projects/\d+/ord', '调整项目顺序', [project]),
        ('POST', '/api/m05/ledger/opening-payment', '修改期初付款', [opening]),
        ('POST', '/m05/opening', '保存手动期初', [opening]),
        ('POST', '/m05/opening/delete', '删除手动期初', [opening]),
        ('POST', '/api/m05/history/save', '保存历史数据', [historical]),
        ('POST', '/api/m05/history/delete', '删除历史数据', [historical]),
        ('POST', '/m05/ledger/remark', '修改欠款台账备注', [remark]),
        ('POST', r'/api/m09/fee/(add|name|amount|delete|batch)', '编辑特殊费用', [fee, fee_item]),
        ('POST', r'/api/m09/fee/item/(create|rename|amount|delete)', '编辑特殊费用', [fee, fee_item]),
        ('POST', '/api/m07/big/cell', '编辑月度会大表', [big, big_projects]),
        ('POST', r'/api/m07/big/(selection|move)', '调整大表本月项目与顺序', [big_projects]),
        ('POST', '/api/m07/big/export', '导出并固定大表本月项目', [big_projects]),
        ('POST', '/api/m07/extract/balance', '修改焊材气体历史金额', [balance]),
        ('POST', '/api/m06/material', '编辑过程资料历史材料', [material]),
        ('POST', '/api/m11/tag', '修改集采台账标记', [contract]),
        ('POST', '/api/m11/fields', '编辑集采合同字段', [contract]),
        ('POST', '/api/m13/cards', '建立实体油卡', [oil_card]),
        ('PUT', r'/api/m13/cards/\d+', '维护实体油卡', [oil_card]),
        ('POST', '/api/m13/accounts', '建立用卡账户', [oil_account, oil_assignment]),
        ('PUT', r'/api/m13/accounts/\d+', '维护用卡账户', [oil_account, oil_assignment]),
        ('POST', r'/api/m13/accounts/\d+/replace-card', '用卡账户换卡', [oil_card, oil_account, oil_assignment]),
        ('POST', '/api/m13/ledger/entries', '登记油卡充值或调整', [oil_entry]),
        ('PUT', r'/api/m13/ledger/entries/\d+', '更正油卡账务', [oil_entry]),
        ('PUT', r'/api/m13/ledger/entries/\d+/attribution', '更正油卡历史关联', [oil_entry]),
        ('POST', '/api/m13/ledger/refunds', '登记油卡充值退款', [oil_entry]),
        ('POST', '/api/m13/ledger/transfers', '登记油卡转账', [oil_entry]),
        ('PUT', r'/api/m13/linkage/\d+/\d{4}-\d{2}/fee', '维护特殊费用用油自定义额', [oil_fee_custom]),
        ('PUT', r'/api/m13/linkage/\d+/\d{4}-\d{2}/big', '维护大表用油额外值', [oil_big_custom]),
        ('PUT', r'/api/m13/invoices/\d+/remark', '修改油卡发票备注', [oil_invoice, oil_allocation]),
        ('PUT', r'/api/m13/invoices/\d+/correct', '更正油卡发票票面', [oil_invoice, oil_allocation, oil_number]),
        ('PUT', r'/api/m13/invoices/\d+/allocations', '更正油卡发票整体分配', [oil_invoice, oil_allocation]),
        ('PUT', r'/api/m13/invoices/\d+/originals/\d+/resolve', '核对油卡发票原件', [oil_invoice]),
        ('POST', r'/api/m13/invoices/\d+/credit', '登记油卡发票红冲', [oil_invoice, oil_allocation, oil_number]),
        ('POST', r'/api/m13/invoices/\d+/void', '登记油卡发票作废', [oil_invoice]),
    ])
