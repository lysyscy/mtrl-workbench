"""TAIL-416: contract maintenance through the real isolated backend."""
import subprocess
import sys
import pytest
from playwright.sync_api import expect
from test_preview import server, browser_page, login


@pytest.fixture(scope='module')
def preview_seed():
    def seed(env):
        code = """
from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod11_jc.models import JcContract, JcInvoice, JcPayment
from app.mod03_notice.models import PaymentNotice
from sqlalchemy import select
with session_scope() as s:
    p=s.scalar(select(Project).where(Project.disp=='隔离项目'))
    c=JcContract(project_id=p.id,contract_no='TAIL416-CONTRACT',contract_date='2026-10-01',material_name='隔离钢材合同',supplier='合成供应商',contract_amt=12345.67,payment_term='60±7天',payment_method='承兑')
    s.add(c);s.flush()
    s.add(JcInvoice(contract_id=c.id,kind='supplier',invoice_date='2026-10-10',amount=12345.67))
    b=JcContract(project_id=p.id,contract_no='TAIL416-B',material_name='隔离管件合同B',supplier='合成供应商',contract_amt=100)
    n=PaymentNotice(ph_id='TAIL416-NOTICE-B',bill_no='TAIL416-NOTICE-B',project_name=p.name_full,ownership_id=p.id,category='jc',jc_supplier='合成供应商',doc_date='2026-10-01',approve_status='已批',amount_approved=100,stat_settle=100,stat_paid=0)
    s.add_all([b,n]);s.flush()
    s.add(JcPayment(contract_id=b.id,source='notice',notice_id=n.id,pay_date='',amount=0))
"""
        subprocess.run([sys.executable,'-X','utf8','-c',code],env=env,check=True)
    return seed


def test_contract_save_and_page_draft_survive_navigation(server,browser_page):
    page,context=browser_page
    login(page,server)
    page.get_by_role('link',name='MOD-11 集采合同').click()
    page.get_by_role('button',name='隔离钢材合同',exact=True).click()
    dialog=page.get_by_role('dialog')
    expect(dialog.get_by_label('账期',exact=True)).to_have_value('60±7天')
    dialog.get_by_label('账期',exact=True).fill('90天')
    dialog.get_by_label('备注',exact=True).fill('本次保留草稿')
    # Application navigation preserves the mounted editor and its draft.
    page.go_back()
    page.get_by_role('link',name='MOD-11 集采合同').click()
    expect(dialog.get_by_label('账期',exact=True)).to_have_value('90天')
    cid=next(row['id'] for row in page.request.get(server+'/api/m11/list').json()['rows'] if row['contract_no']=='TAIL416-CONTRACT')
    dialog.get_by_role('button',name='保存合同',exact=True).click()
    expect(dialog).not_to_be_visible()
    data=page.request.get(server+f'/api/m11/detail?id={cid}').json()['data']
    assert (data['payment_term'],data['payment_method'],data['remark'])==('90±0天','承兑','本次保留草稿')
    page.get_by_role('button',name='隔离钢材合同',exact=True).click()
    dialog.get_by_label('备注',exact=True).fill('尚未保存')
    dialog.get_by_role('button',name='关闭弹窗').click()
    expect(dialog.get_by_role('heading',name='放弃未保存的修改？')).to_be_visible()
    dialog.get_by_role('button',name='继续编辑').click()
    dialog.get_by_role('button',name='取消',exact=True).click()
    dialog.get_by_role('button',name='放弃并关闭').click()
    expect(dialog).not_to_be_visible()
    page.reload()
    page.get_by_role('button',name='隔离钢材合同',exact=True).click()
    expect(dialog.get_by_label('备注',exact=True)).to_have_value('本次保留草稿')

    # A successful write with a damaged HTTP 200 body must never offer a second submission.
    dialog.get_by_label('备注',exact=True).fill('模拟损坏回执')
    writes=[]
    def damaged(route):
        writes.append(route.request.post_data)
        response=route.fetch()
        assert response.ok and response.json()['ok'] is True
        route.fulfill(response=response,body='{')
    page.route('**/api/m11/fields',damaged)
    dialog.get_by_role('button',name='保存合同',exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('保存结果待核实')
    expect(dialog.get_by_role('button',name='保存合同',exact=True)).to_have_count(0)
    assert len(writes)==1


def test_contract_reverse_link_preserves_other_contract_draft(server,browser_page):
    page,context=browser_page
    login(page,server)
    page.get_by_role('link',name='MOD-11 集采合同').click()
    page.get_by_role('button',name='隔离钢材合同',exact=True).click()
    page.get_by_role('dialog').get_by_label('备注',exact=True).fill('合同A未保存草稿')
    page.go_back()
    page.get_by_role('link',name='MOD-03 付款通知书').click()
    page.get_by_role('button',name='查看 / 更改关联',exact=True).click()
    page.get_by_role('link',name='查看合同详情',exact=True).click()
    expect(page.get_by_role('dialog').get_by_label('材料名',exact=True)).to_have_value('隔离管件合同B')
    page.get_by_role('dialog').get_by_role('button',name='取消',exact=True).click()
    page.get_by_role('button',name='隔离钢材合同',exact=True).click()
    expect(page.get_by_role('dialog').get_by_label('备注',exact=True)).to_have_value('合同A未保存草稿')
