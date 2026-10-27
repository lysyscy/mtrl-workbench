"""真实事务覆盖费用旧入口父子撤销及外部修改保护。"""
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.history_bindings import configure
from app.mod01_projects.models import Project
from app.mod09_fee.models import FeeItem, FeeManualItem
from app.mod09_fee import service
from tests.test_operation_history import perform, replay, status, committed_data

@pytest.fixture
def project(rollback_db):
    configure()
    with session_scope() as s:
        row=Project(project_type='normal',name_full='费用撤销测试',warehouse_name='fee-'+uuid4().hex)
        s.add(row);s.flush()
        return row.id,row.warehouse_name

def create(project):
    result,recorded=perform('/api/m09/fee/add',lambda s:service.act_add(s,ym='2026-03',project_key=project[1],name='运费',raw='7.25'))
    assert result['kind']=='ok' and recorded=='recorded'
    with session_scope() as s:
        row=s.get(FeeManualItem,result['row_id'])
        return row.fee_item_id,row.id

def test_legacy_parent_child_roundtrip(project):
    item_id,month_id=create(project)
    replay('undo')
    with session_scope() as s:
        assert s.get(FeeItem,item_id) is None and s.get(FeeManualItem,month_id) is None
    replay('redo')
    with session_scope() as s:
        assert s.get(FeeItem,item_id).name=='运费'
        assert s.get(FeeManualItem,month_id).amount==Decimal('7.25')
    replay('undo');replay('redo')

@pytest.mark.parametrize('target',['item','month','project'])
def test_other_writer_blocks_entire_parent_child_undo(project,target):
    item_id,month_id=create(project);before=status()
    with session_scope() as s:
        if target=='item':s.get(FeeItem,item_id).name='其他人改名'
        elif target=='month':s.get(FeeManualItem,month_id).amount=Decimal('8')
        else:s.get(Project,project[0]).disp='其他人改项目'
    with pytest.raises(MustReportError,match='后续操作'):
        replay('undo')
    assert status()==before
    with session_scope() as s:
        assert s.get(FeeItem,item_id) is not None and s.get(FeeManualItem,month_id) is not None


def test_zero_blank_negative_global_name_and_scope(project):
    with session_scope() as s:
        item=service.create_item(s,project_key=project[1],name='新项')['row_id']
    def action(action,**values):
        result,_=perform('/api/m09/fee/item/'+action,lambda s:service.item_action(s,project_key=project[1],item_id=item,action=action,**values))
        assert result['kind']=='ok',result
    action('amount',ym='2026-03',value='0')
    action('amount',ym='2025-12',value='-1.25')
    action('rename',value='跨年统一名')
    with session_scope() as s:
        row=next(r for r in service.build_year_data(s,year='2026',project=project[1])['rows'] if r.get('item_id')==item)
        assert row['item']=='跨年统一名' and row['prior']==Decimal('-1.25')
        assert row['months'][2]==0 and row['months'][3] is None and row['total']==Decimal('-1.25')
    action('amount',ym='2026-03',value='')
    with session_scope() as s:
        assert s.scalar(select(FeeManualItem.id).where(FeeManualItem.fee_item_id==item,FeeManualItem.ym=='2026-03')) is None
    replay('undo')
    with session_scope() as s:
        assert s.scalar(select(FeeManualItem.amount).where(FeeManualItem.fee_item_id==item,FeeManualItem.ym=='2026-03'))==0
        assert service.item_action(s,project_key='wrong',item_id=item,action='delete')['kind']=='err'
        auto=service.D.AUTO_NAME
        assert service.create_item(s,project_key=project[1],name=auto)['kind']=='err'
        assert service.act_add(s,project_key=project[1],ym='2026-03',name=auto)['kind']=='err'
        assert service.act_rename(s,project_key=project[1],ym='2026-03',index=0,value=auto)['kind']=='err'
        assert service.act_batch(s,project_key=project[1],items=[auto],months=[{'ym':'2026-03','values':{auto:'4'}}])['kind']=='err'


def test_concurrent_same_name_has_one_value_and_explicit_rejection(committed_data):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.core import history
    from app.mod09_fee.api import ItemRequest, api_item_create
    d=committed_data
    with d['factory']() as s: key=s.get(Project,d['project']).warehouse_name
    start=Barrier(2)
    def create(actor):
        token,_=history.begin_request(actor,'POST','/api/m09/fee/item/create')
        try:
            start.wait(timeout=5)
            return api_item_create(ItemRequest(project=key,name='并发新增'))
        finally:history.end_request(token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(create,d['actor']+suffix) for suffix in ('','other')]
        results=[f.result(timeout=10) for f in futures]
    assert sorted(r['ok'] for r in results)==[False,True]
    with d['factory']() as s:
        assert len(list(s.scalars(select(FeeItem).where(FeeItem.project_id==d['project'],FeeItem.name=='并发新增'))))==1


@pytest.mark.parametrize('clear_month',[False,True])
def test_legacy_write_waits_for_whole_item_deletion(committed_data,monkeypatch,clear_month):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from app.mod09_fee import repository
    d=committed_data;month_id=d['fees'][0]
    with d['factory']() as s:
        row=s.get(FeeManualItem,month_id);item_id=row.fee_item_id
        project_key=s.get(Project,d['project']).warehouse_name
    reached=Event();original=repository.item_of
    def item_of(*args,**kwargs):
        reached.set()
        return original(*args,**kwargs)
    monkeypatch.setattr(repository,'item_of',item_of)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with d['factory'].begin() as s:
            item=s.scalar(select(FeeItem).where(FeeItem.id==item_id).with_for_update())
            if clear_month:s.delete(s.get(FeeManualItem,month_id))
            else:item.deleted=True
            s.flush()
            future=pool.submit(lambda: perform('/api/m09/fee/amount',lambda s:service.act_set_amount(s,ym='2026-10',project_key=project_key,index=0,raw='999'),d['actor']))
            assert reached.wait(timeout=5)
        result,_=future.result(timeout=10)
    assert result['kind']=='err'
    with d['factory']() as s:
        row=s.get(FeeManualItem,month_id)
        assert row is None if clear_month else row.amount==1
