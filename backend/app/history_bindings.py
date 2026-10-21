"""撤销白名单：只接无外部副作用、可按完整行版本验证的本地操作。"""
from app.core.history import Rule, bind_policies
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import LedgerRemark, OpeningBalance
from app.mod07_setl.models import AnalysisBigManual, WeldGasBalance
from app.mod09_fee.models import FeeManualItem
from app.mod11_jc.models import JcContract


def configure():
    notice = Rule(PaymentNotice, frozenset({
        'excluded', 'exclude_source', 'category', 'jc_supplier',
    }))
    project = Rule(Project, frozenset({'disp', 'ord'}))
    opening = Rule(OpeningBalance, frozenset({'settle_amount', 'paid_amount', 'remark'}), True)
    remark = Rule(LedgerRemark, frozenset({'remark'}), True)
    fee = Rule(FeeManualItem, frozenset({'item_name', 'amount'}), True)
    big = Rule(AnalysisBigManual, frozenset({
        'open_ym', 'mech_est', 'contract_price', 'output_cum', 'oil', 'note',
    }), True)
    balance = Rule(WeldGasBalance, frozenset({'amount'}), True)
    contract = Rule(JcContract, frozenset({
        'contract_no', 'contract_date', 'contract_date_locked', 'material_name', 'supplier',
        'contract_amt', 'trade_co', 'trade_contract_amt', 'tag', 'arch', 'arch_no',
        'ret_date', 'remark',
    }))
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
        ('POST', '/m05/ledger/remark', '修改欠款台账备注', [remark]),
        ('POST', r'/api/m09/fee/(add|name|amount|delete|batch)', '编辑特殊费用', [fee]),
        ('POST', '/api/m07/big/cell', '编辑月度会大表', [big]),
        ('POST', '/api/m07/extract/balance', '修改焊材气体历史金额', [balance]),
        ('POST', '/api/m11/tag', '修改集采台账标记', [contract]),
        ('POST', '/api/m11/fields', '编辑集采合同字段', [contract]),
    ])
