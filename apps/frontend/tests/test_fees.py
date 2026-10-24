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


# ------------------------------------------------------------------ TAIL-415 隔离补验（以下为新增）

import time


def fee_manuals(page, server, ym):
    response = page.request.get(server+'/api/m09/fee',params={'ym':ym,'pj':'隔离验收仓库'})
    assert response.status == 200
    # 金额按 Decimal 数值语义对数（后端契约测试同款）；零值序列化为 '0'/'0.00' 均等价。
    return [(r['item'],Decimal(r['amount'])) for r in response.json()['manuals']]


def wait_pair(page, server, ym, pair, timeout=15000):
    """后端落库结果的确定性等待（不依赖 UI 状态文本时序）。"""
    deadline = time.monotonic()+timeout/1000
    while True:
        if pair in fee_manuals(page,server,ym):
            return
        if time.monotonic() > deadline:
            raise AssertionError(f'{ym} 里未出现 {pair}；实际：{fee_manuals(page,server,ym)}')
        time.sleep(0.2)


def test_continuous_editing_keeps_focus_and_receipts_stay_with_their_cell(server,browser_page):
    """明细弹窗内 Tab 连续编辑：前一格保存回执不打断后续输入与焦点，回执归原对象。"""
    page,_ = browser_page
    login(page,server)
    page.get_by_role('link',name='MOD-09 特殊费用',exact=True).click()
    page.get_by_role('button',name='运费 1月明细',exact=True).click()
    dialog = page.locator('.fee-details-dialog')
    add = dialog.get_by_role('button',name='增加手填项',exact=True)
    add.click(); add.click()
    amounts = dialog.get_by_role('textbox',name='新项金额',exact=True)
    expect(amounts).to_have_count(2)
    held = []
    def hold(route):
        response = route.fetch()            # 写请求真实到达后端（会落库）
        held.append((route,response))       # 只把回执压后，模拟迟到回执
    page.route('**/api/m09/fee/amount',hold)
    amounts.nth(0).fill('11.5')
    amounts.nth(0).press('Tab')          # blur 保存第一行金额；Tab 落到第二行项名
    expect(dialog.get_by_role('status')).to_contain_text('正在保存')
    names = dialog.get_by_role('textbox',name='新项项名',exact=True)
    expect(names).to_have_count(2)
    expect(names.nth(1)).to_be_focused()
    names.nth(1).fill('记号乙')           # 第一格回执仍在途，后续输入继续
    names.nth(1).press('Tab')            # 项名 Tab 落到同行金额
    second = dialog.get_by_role('textbox',name='新项金额',exact=True).nth(1)
    expect(second).to_be_focused()
    second.fill('-2.25')
    assert len(held) == 1
    route,response = held.pop()
    route.fulfill(response=response)     # 此刻才把真实回执交给页面
    page.unroute('**/api/m09/fee/amount')
    # 迟到回执既不覆盖新输入，也不抢走焦点。
    saved = dialog.get_by_role('textbox',name='记号乙金额',exact=True)
    expect(saved).to_have_value('-2.25')
    expect(saved).to_be_focused()
    saved.press('Tab')                   # 离格保存改名行的金额
    wait_pair(page,server,'2026-01',('记号乙',Decimal('-2.25')))
    expect(saved).to_have_value('-2.25')
    expect(dialog.get_by_role('status')).to_contain_text('已保存',timeout=15000)
    rows = {r['item']:r for r in annual(page,server)['rows']}
    assert rows['新项']['months'][0] == '11.50'      # A 格回执落在 A 行
    assert rows['记号乙']['months'][0] == '-2.25'    # B 格输入未被 A 的回执覆盖
    page.screenshot(path=str(output('fee-continuous-edit.png',kind='screenshots')),full_page=True)
    dialog.get_by_role('button',name='关闭',exact=True).click()
    expect(dialog).not_to_be_visible()


def test_batch_month_entry_real_save_semantics(server,browser_page):
    """批量录入（按月）真实保存：非法整批拒绝、空格跳过、同月同名更新最早一条。"""
    import re
    page,_ = browser_page
    login(page,server)
    page.get_by_role('link',name='MOD-09 特殊费用',exact=True).click()
    page.get_by_role('button',name='油卡 9月明细',exact=True).first.click()
    dialog = page.locator('.fee-details-dialog')
    expect(dialog.get_by_role('textbox',name='油卡金额',exact=True)).to_have_count(2)
    dialog.get_by_role('button',name='批量录入（按月）…',exact=True).click()
    batch = page.locator('.fee-batch-dialog')
    expect(batch.get_by_text('同名项合为一行；批量保存更新每月最早一条同名项。',exact=True)).to_be_visible()
    # 报告月格子预填当前最早一条的金额（零值序列化 '0'，数字语义等价 0.00）。
    expect(batch.get_by_role('textbox',name='2026-09油卡金额',exact=True)).to_have_value(re.compile(r'^0(\.00)?$'))
    batch.get_by_role('textbox',name='2026-07油卡金额',exact=True).fill('7.70')
    batch.get_by_role('textbox',name='2026-08油卡金额',exact=True).fill('abc')
    batch.get_by_role('textbox',name='2026-09油卡金额',exact=True).fill('9.90')
    page.screenshot(path=str(output('fee-batch-invalid.png',kind='screenshots')),full_page=True)
    batch.get_by_role('button',name='保存',exact=True).click()
    expect(batch.get_by_role('alert')).to_contain_text('金额不合法')
    expect(batch.get_by_role('alert')).to_contain_text('这一批')
    # 非法整批拒绝：一格都没写。
    assert fee_manuals(page,server,'2026-07') == []
    assert fee_manuals(page,server,'2026-08') == []
    assert fee_manuals(page,server,'2026-09') == [('油卡',Decimal('0.00')),(' 油卡',Decimal('1.00'))]
    batch.get_by_role('textbox',name='2026-08油卡金额',exact=True).fill('')
    batch.get_by_role('button',name='保存',exact=True).click()
    expect(batch).not_to_be_visible()
    assert fee_manuals(page,server,'2026-07') == [('油卡',Decimal('7.70'))]    # 空月新建
    assert fee_manuals(page,server,'2026-08') == []                            # 空格整格跳过（不写 0、不建行）
    assert fee_manuals(page,server,'2026-09') == [('油卡',Decimal('9.90')),(' 油卡',Decimal('1.00'))]  # 同月同名更新最早一条
    rows = {r['item']:r for r in annual(page,server)['rows']}
    assert (rows['油卡']['months'][6],rows['油卡']['months'][8],rows[' 油卡']['months'][8]) == ('7.70','9.90','1.00')
    expect(dialog.get_by_role('textbox',name='油卡金额',exact=True).first).to_have_value('9.90')
    dialog.get_by_role('button',name='关闭',exact=True).click()
    expect(dialog).not_to_be_visible()


def test_empty_zero_and_negative_amount_semantics(server,browser_page):
    """单格清空=清零（记录保留），显式 0 与负数同口径；年度表区分空月与真实零。"""
    import re
    page,_ = browser_page
    login(page,server)
    page.get_by_role('link',name='MOD-09 特殊费用',exact=True).click()
    page.get_by_role('button',name='运费 12月明细',exact=True).click()
    dialog = page.locator('.fee-details-dialog')
    dialog.get_by_role('button',name='增加手填项',exact=True).click()
    name = dialog.get_by_role('textbox',name='新项项名',exact=True)
    expect(name).to_have_count(1)
    name.fill('清零样例'); name.press('Tab')
    amount = dialog.get_by_role('textbox',name='清零样例金额',exact=True)
    expect(amount).to_be_visible()
    zero = re.compile(r'^0(\.00)?$')     # 零值序列化 '0'/'0.00' 数字语义等价
    amount.fill('5'); amount.press('Tab')
    wait_pair(page,server,'2026-12',('清零样例',Decimal('5.00')))
    expect(amount).to_have_value('5.00')
    amount.fill(''); amount.press('Tab')     # 单格清空 = 清零语义（记录保留，不是删除也不是报错）
    wait_pair(page,server,'2026-12',('清零样例',Decimal('0.00')))
    expect(amount).to_have_value(zero)
    amount.fill('0'); amount.press('Tab')    # 显式 0 同口径
    wait_pair(page,server,'2026-12',('清零样例',Decimal('0.00')))
    expect(amount).to_have_value(zero)
    amount.fill('-12.34'); amount.press('Tab')
    wait_pair(page,server,'2026-12',('清零样例',Decimal('-12.34')))
    expect(amount).to_have_value('-12.34')
    expect(dialog.get_by_role('status')).to_contain_text('已保存',timeout=15000)
    rows = {r['item']:r for r in annual(page,server)['rows']}
    assert rows['清零样例']['months'][11] == '-12.34'
    assert rows['清零样例']['months'][10] is None      # 没录的月仍是空，不臆造 0
    page.screenshot(path=str(output('fee-empty-zero-negative.png',kind='screenshots')),full_page=True)
    dialog.get_by_role('button',name='关闭',exact=True).click()
    expect(dialog).not_to_be_visible()


def test_fee_writes_require_login_and_change_nothing(server,browser_page):
    """未登录：页面按钮禁用；POST /api/m09/fee/* 直发 401 且数据不变。"""
    import httpx
    page,_ = browser_page
    page.goto(server+'/preview/fees')
    expect(page.get_by_text('未登录 · 只读',exact=True)).to_be_visible()
    expect(page.get_by_role('button',name='增加手填项',exact=True)).to_be_disabled()
    page.get_by_role('button',name='运费 1月明细',exact=True).click()
    dialog = page.locator('.fee-details-dialog')
    expect(dialog.get_by_role('button',name='批量录入（按月）…',exact=True)).to_be_disabled()
    def snapshot():
        return page.request.get(server+'/api/m09/fee',params={'ym':'2026-01','pj':'隔离验收仓库'}).json()
    before = snapshot()
    with httpx.Client(base_url=server) as client:
        for path,payload in [
            ('/api/m09/fee/add',{'ym':'2026-01','project':'隔离验收仓库'}),
            ('/api/m09/fee/name',{'ym':'2026-01','project':'隔离验收仓库','index':0,'value':'越权改名'}),
            ('/api/m09/fee/amount',{'ym':'2026-01','project':'隔离验收仓库','index':0,'value':'999'}),
            ('/api/m09/fee/delete',{'ym':'2026-01','project':'隔离验收仓库','index':0}),
            ('/api/m09/fee/batch',{'project':'隔离验收仓库','items':['越权项'],'months':[{'ym':'2026-01','values':{'越权项':'1'}}]}),
        ]:
            response = client.post(path,json=payload)
            assert response.status_code == 401,(path,response.status_code)
            assert '未登录' in response.json()['message']
    assert snapshot() == before


def test_damaged_amount_receipt_requires_reread_before_recovery(server,browser_page):
    """200 截断回执 → uncertain：禁重复提交；写已落库，重读核对后恢复继续编辑。"""
    page,_ = browser_page
    login(page,server)
    page.get_by_role('link',name='MOD-09 特殊费用',exact=True).click()
    page.get_by_role('button',name='运费 1月明细',exact=True).click()
    dialog = page.locator('.fee-details-dialog')
    target = dialog.get_by_role('textbox',name='运费金额',exact=True).first
    writes = []
    def damaged(route):
        writes.append(route.request.post_data)
        response = route.fetch()
        assert response.ok
        route.fulfill(response=response,body='{')
    page.route('**/api/m09/fee/amount',damaged)
    target.fill('25')
    target.press('Tab')
    expect(dialog.get_by_role('alert').first).to_contain_text('保存结果待核实')
    expect(dialog.get_by_role('alert').first).to_contain_text('勿重复提交')
    assert len(writes) == 1
    expect(target).to_be_disabled()
    page.screenshot(path=str(output('fee-damaged-receipt.png',kind='screenshots')),full_page=True)
    wait_pair(page,server,'2026-01',('运费',Decimal('25.00')))    # 写已真实落库，只是回执不可读
    page.unroute('**/api/m09/fee/amount')
    dialog.get_by_role('button',name='重读核对',exact=True).click()
    expect(dialog.get_by_role('status')).to_contain_text('已重读，请核对刚才的操作结果。')
    dialog.get_by_role('button',name='已核对，保留输入继续',exact=True).click()
    expect(dialog.get_by_role('status')).to_contain_text('已确认，请核对保留输入后再保存。')
    recovered = dialog.get_by_role('textbox',name='运费金额',exact=True).first
    expect(recovered).to_be_enabled()
    expect(recovered).to_have_value('25')
    recovered.fill('26')
    recovered.press('Tab')
    wait_pair(page,server,'2026-01',('运费',Decimal('26.00')))
    expect(dialog.get_by_role('status')).to_contain_text('已保存',timeout=15000)
    assert {r['item']:r for r in annual(page,server)['rows']}['运费']['months'][0] == '26.00'
    dialog.get_by_role('button',name='关闭',exact=True).click()
    expect(dialog).not_to_be_visible()


def test_fee_sheet_exports_in_ledger_workbook(server,browser_page):
    """费用随逐月欠款台账三表工作表导出：真实隔离数据经真实模板构建器落本轮 .artifacts。

    ⚠️ 端点全链（`/api/m05/ledger/export`）会把成品写进正式 `EXPORT_ROOT`（`PROJECT_ROOT/exports`，
    代码内固定、无配置覆盖），按本票硬边界不触发；此处取同一构建器 `ledger_export.build_xlsx` ＋
    同一页面数据（`/api/m09/fee`、`/api/m05/ledger`）在隔离数据上产出，落点限定在本轮 .artifacts。
    """
    import re
    from decimal import Decimal
    from pathlib import Path
    from app.report_export import ledger_export as LE
    from tools.audit.workspace_paths import output_dir
    page,_ = browser_page
    login(page,server)
    page.get_by_role('link',name='MOD-09 特殊费用',exact=True).click()
    expect(page.get_by_text('随逐月欠款台账导出 · 特殊费用月报表',exact=True)).to_be_visible()
    assert page.get_by_role('button',name=re.compile('导出')).count() == 0    # 费用页无独立导出
    fee = page.request.get(server+'/api/m09/fee',params={'ym':'2026-09','pj':'隔离验收仓库'}).json()
    assert fee['project'] == '隔离验收仓库'
    projects = page.request.get(server+'/api/m01/projects?status=all&keyword=').json()
    pid = next(p['id'] for p in projects if p['warehouse_name'] == '隔离验收仓库')
    ledger = page.request.get(server+'/api/m05/ledger',params={'project_id':pid,'end_ym':'2026-09'}).json()
    sections = {cat: next(s for s in ledger['sides'] if s['category'] == cat) for cat in ('material','mechanical')}
    sections[LE.SHEET_FEE] = fee
    out_dir = output_dir('exports') / 'tail415-ledger'
    path = Path(LE.build_xlsx(sections,out_dir,display=fee['project_display'],ym='2026-09'))
    assert str(path).startswith(str(output_dir('exports')))              # 只落本轮 .artifacts
    assert not str(path).startswith(str(Path(__file__).resolve().parents[3] / 'exports'))
    assert path.name == f"{fee['project_display']}欠款台账_2026年9月.xlsx"
    import openpyxl
    wb = openpyxl.load_workbook(path)
    assert set(wb.sheetnames) == {'辅材','机械','特殊费用月报表'}
    ws = wb['特殊费用月报表']
    assert ws['A1'].value == f"{fee['project_display']}费用汇总表"
    assert '9月份' in {ws.cell(row=2,column=c).value for c in range(1,ws.max_column+1)}
    items = [fee['auto'],*fee['manuals']]
    for offset,item in enumerate(items):
        row = 3+offset
        assert ws.cell(row=row,column=1).value == (item['item'] or '').strip()
        assert float(ws.cell(row=row,column=2).value) == float(item['amount'])
        assert float(ws.cell(row=row,column=3).value) == float(item['amount'])   # 单月列 ⇒ 合计 = 该月值
    assert ws.cell(row=3+len(items),column=1).value is None    # 行数随数据项派生，无残留
    assert sum(Decimal(it['amount']) for it in items) == Decimal(fee['total'])
    wb.close()
    page.screenshot(path=str(output('fee-export-workbook.png',kind='screenshots')),full_page=True)
