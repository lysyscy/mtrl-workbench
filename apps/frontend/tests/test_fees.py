"""Annual display uses original facts; edits continue to address individual months."""
import os
from decimal import Decimal

import pytest
from playwright.sync_api import expect
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from test_preview import server, browser_page, login
from tools.audit.workspace_paths import output


@pytest.fixture(scope='module')
def preview_seed():
    def seed(env):
        from app.mod01_projects.models import Project
        from app.mod08_inv.models import InvDetail
        from app.mod09_fee.models import FeeManualItem
        if os.environ.get('MTRL_FEE_TEST_BUILD'):
            env['FRONTEND_PREVIEW_DIR'] = os.environ['MTRL_FEE_TEST_BUILD']
        engine = create_engine(env['TEST_DATABASE_URL'], connect_args={'options': env['PGOPTIONS']})
        try:
            with Session(engine) as s:
                assert s.execute(text('SELECT current_database(),current_schema()')).one() == ('mtrl_workbench_test',env['PGOPTIONS'].split('search_path=')[1])
                pj = s.scalar(select(Project).where(Project.warehouse_name == '隔离验收仓库'))
                other = s.scalar(select(Project).where(Project.warehouse_name == '长名称验收仓库'))
                s.add_all([FeeManualItem(project_id=pid,ym=ym,item_name=name,amount=Decimal(amount)) for pid,ym,name,amount in [
                    (pj.id,'2024-03','运费','10.10'),(pj.id,'2025-12','运费','-2.10'),
                    (pj.id,'2026-01','运费','10'),(pj.id,'2026-01','运费','20'),(pj.id,'2026-12','运费','-5'),
                    (pj.id,'2027-01','未来项','999'),(other.id,'2026-01','运费','999'),
                    (pj.id,'2026-09','油卡','0'),(pj.id,'2026-09',' 油卡','1'),
                    (pj.id,'2025-12','大额','999999.99'),(pj.id,'2026-01','大额','1234567.89'),
                ]])
                s.add_all([InvDetail(project_id=pj.id,warehouse_name='隔离验收仓库',ym=ym,direction=direction,cbs_name=cbs,amount=Decimal(amount),doc_date='2099-01-01') for ym,direction,cbs,amount in [
                    ('2025-01','出库','CBS-安文费','100'),('2026-02','出库','CBS-安文费','20'),
                    ('2026-02','入库','CBS-安文费','1000'),('2026-02','出库','其他','1000'),('2027-02','出库','CBS-安文费','1000'),
                ]])
                s.commit()
        finally:
            engine.dispose()
    return seed


def annual(page, base, year='2026'):
    response = page.request.get(base+'/api/m09/fee/year',params={'year':year,'pj':'隔离验收仓库'})
    assert response.status == 200
    return response.json()


def test_annual_original_history_duplicates_and_record_edits(server,browser_page):
    page,_ = browser_page
    login(page,server)
    data = annual(page,server)
    rows = {r['item']:r for r in data['rows']}
    assert rows['运费']['prior'] == '8.00'
    assert rows['运费']['months'] == ['30.00',None,None,None,None,None,None,None,None,None,None,'-5.00']
    assert rows['运费']['total'] == '33.00'
    auto = rows['安全文明施工费（按 CBS 分类）']
    assert (auto['prior'],auto['months'][1],auto['total']) == ('100.00','20.00','120.00')
    assert rows['油卡']['months'][8] == '0.00' and ' 油卡' in rows and '未来项' not in rows
    assert rows['大额']['total'] == '2234567.88'
    assert data['total'] == '2234721.88'
    assert annual(page,server,'2027')['rows'][0]['prior'] == '120.00'
    page.get_by_role('link',name='MOD-09 特殊费用',exact=True).click()
    grid = page.get_by_label('特殊费用年度表',exact=True)
    expect(grid.get_by_role('columnheader',name='累计',exact=True)).to_be_visible()
    assert grid.get_by_role('columnheader').count() == 15
    expect(page.get_by_label('费用年份',exact=True)).to_have_value('2026')
    page.set_viewport_size({'width':1440,'height':900})
    expect(grid.get_by_role('button',name='大额 累计明细',exact=True)).to_have_text('2,234,567.88')
    assert grid.locator('.ag-cell.money').evaluate_all('(cells)=>cells.every(c=>c.scrollWidth<=c.clientWidth)')
    page.screenshot(path=str(output('fee-year-1440-synthetic.png',kind='screenshots')),full_page=True)
    page.get_by_role('button',name='运费 1月明细',exact=True).click()
    dialog = page.locator('.fee-details-dialog')
    amounts = dialog.get_by_role('textbox',name='运费金额',exact=True)
    expect(amounts).to_have_count(2)
    amounts.first.fill('15')
    amounts.first.press('Tab')
    expect(dialog.get_by_role('status')).to_contain_text('已保存',timeout=15000)
    assert annual(page,server)['rows'][1]['months'][0] == '35.00'
    amounts = dialog.get_by_role('textbox',name='运费金额',exact=True)
    expect(amounts.nth(1)).to_have_value('20.00')
    amounts.first.fill('abc')
    amounts.first.press('Tab')
    expect(dialog.get_by_role('alert').first).to_contain_text('金额不合法')
    assert annual(page,server)['rows'][1]['months'][0] == '35.00'
    dialog.get_by_role('button',name='取消这项修改',exact=True).click()
    dialog.locator('.ag-row').filter(has=page.get_by_role('textbox',name='运费金额',exact=True)).nth(1).get_by_role('button',name='删除',exact=True).click()
    delete = page.locator('.fee-delete-dialog')
    expect(delete).to_contain_text('2026-01')
    expect(delete).to_contain_text('20.00')
    delete.get_by_role('button',name='删除',exact=True).click()
    expect(amounts).to_have_count(1)
    assert annual(page,server)['rows'][1]['months'][0] == '15.00'
    dialog.get_by_role('button',name='增加手填项',exact=True).click()
    names = dialog.get_by_role('textbox',name='新项项名',exact=True)
    expect(names).to_have_count(1)
    names.fill('临建')
    names.press('Tab')
    expect(dialog.get_by_role('textbox',name='临建金额',exact=True)).to_be_visible()
    amount = dialog.get_by_role('textbox',name='临建金额',exact=True)
    amount.fill('-3.5'); amount.press('Tab')
    expect(dialog.get_by_role('status')).to_contain_text('已保存',timeout=15000)
    assert {r['item']:r for r in annual(page,server)['rows']}['临建']['total'] == '-3.50'
    dialog.get_by_role('button',name='批量录入（按月）…',exact=True).click()
    batch = page.locator('.fee-batch-dialog')
    expect(batch).to_be_visible()
    batch.get_by_role('textbox',name='2026-01运费金额',exact=True).fill('18')
    batch.get_by_role('button',name='保存',exact=True).click()
    expect(batch).not_to_be_visible()
    assert {r['item']:r for r in annual(page,server)['rows']}['运费']['months'][0] == '18.00'
    dialog.get_by_role('button',name='关闭',exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role('button',name='运费 1月明细',exact=True)).to_have_text('18.00')


def test_readonly_details_do_not_enable_writes(server,browser_page):
    page,_ = browser_page
    page.goto(server+'/preview/fees')
    expect(page.get_by_label('特殊费用年度表',exact=True)).to_be_visible()
    expect(page.get_by_role('button',name='增加手填项',exact=True)).to_be_disabled()
    page.get_by_role('button',name='运费 1月明细',exact=True).click()
    dialog=page.locator('.fee-details-dialog')
    expect(dialog.get_by_role('textbox',name='运费金额',exact=True).first).to_be_disabled()
    expect(dialog.get_by_role('button',name='删除',exact=True).first).to_be_disabled()
