"""机械台账读过程资料有效含税两列：项目、月份、期初及其他四列不得混入。"""
from decimal import Decimal
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow import service
from app.mod05_flow.models import CATEGORY_MECH, OpeningBalance
from app.mod06_proc import repository
from tests.test_proc_split_cutoffs import session


def test_mechanical_ledger_uses_effective_taxed_values(session):
    p=Project(project_type='normal',name_full='__tail273_a__',warehouse_name='__tail273_a__',disp='甲')
    q=Project(project_type='normal',name_full='__tail273_b__',warehouse_name='__tail273_b__',disp='乙')
    session.add_all([p,q]); session.flush()
    for ym,wh,values in [
        ('2026-09',p.warehouse_name,dict(mech_0=1255,mech_1=777,mech_2=52600,mech_3=33000,mech_4=51067.96,mech_5=32266.02)),
        ('2026-07',p.warehouse_name,dict(mech_2=99,mech_3=1)),
        ('2026-11',p.warehouse_name,dict(mech_2=600)),
        ('2026-09',q.warehouse_name,dict(mech_2=900000)),
    ]:
        repository.save_mech(session,ym=ym,warehouse=wh,values=values,project_id=p.id if wh==p.warehouse_name else q.id)
    session.add(PaymentNotice(ph_id='__tail273_notice__',bill_no='__tail273_notice__',doc_date='2026-09-15',category=CATEGORY_MECH,ownership_id=p.id,stat_paid=Decimal('5000'),stat_settle=Decimal('999999'),excluded=False,fields={}))
    session.add(OpeningBalance(category=CATEGORY_MECH,project_id=p.id,cutoff_ym='2026-07',settle_amount=Decimal('50'),paid_amount=Decimal('10')))
    session.flush()
    def rows(end):
        return next(x for x in service.build_ledger(session,project_id=p.id,end_ym=end)['sides'] if x['category']==CATEGORY_MECH)['display_rows']
    current=rows('2026-09')
    assert [(r['month'],r['other_expense'],r['payment'],r['debt']) for r in current]==[
        ('2026-07','50.00','10.00','40.00'),
        ('2026-07','100.00','0.00','100.00'),
        ('2026-08','0.00','0.00','0.00'),
        ('2026-09','85600.00','5000.00','80600.00'),
    ]
    # 已存只有机械费、没有通知书的月份也须出现；手录覆盖后实时读回。
    later=rows('')
    assert later[-1]['month']=='2026-11' and later[-1]['other_expense']=='600.00'
    repository.save_mech(session,ym='2026-09',warehouse=p.warehouse_name,values={'mech_2':0})
    changed=rows('2026-09')[-1]
    assert changed['other_expense']=='33000.00' and changed['debt']=='28000.00'
