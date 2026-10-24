"""TAIL-413: big analysis table, manual values, selection order and export through the real isolated backend."""
import subprocess
import sys
import time
from decimal import Decimal

import httpx
import pytest
from playwright.sync_api import expect
from preview_select import pick_option
from test_preview import server, browser_page, login
from tools.audit.workspace_paths import output

MONTH = '2026-09'
NEXT_MONTH = '2027-01'
WH_A = '大表验收仓库甲'
WH_B = '长名称验收仓库'
WH_C = '大表验收仓库丙'
#: 14 backend totals keys consumed by the pinned row (rates / open_ym / note are never summed).
TOTAL_KEYS = ['hw_cum', 'hw_mon', 'qt_cum', 'qt_mon', 'rent_cum', 'rent_mon', 'lease_cum', 'lease_mon',
              'total_cum', 'mech_est', 'contract', 'output_cum', 'mat_cum', 'oil']
#: Export column layout = the identity mapping over the 20 backend BIG_COLUMNS (§5.5, A..T).
EXPORT_KEYS = ['seq', 'project', 'open_ym', 'hw_cum', 'hw_mon', 'qt_cum', 'qt_mon',
               'rent_cum', 'rent_mon', 'lease_cum', 'lease_mon', 'total_cum', 'mech_est', 'use_rate',
               'output_rate', 'contract', 'output_cum', 'mat_cum', 'oil', 'note']
LEAVES = ['序号', '项目名称', '开工时间', '焊材累计', '焊材当月', '三气累计', '三气当月',
          '外租机械开工累计', '外租机械当月', '设备租赁开工累计', '设备租赁当月', '合计', '机械费测算', '使用率',
          '产值完成率', '合同（预估）价', '产值累计（含税）', '主材累计（含税）', '工程用油', '备注']
GROUPS = ['项目', '辅材使用（不含税）', '机械使用与测算', '产值']
GROUP_STARTS = 6  # 辅材/机械/产值 group starts + standalone 主材累计/工程用油/备注


@pytest.fixture(scope='module')
def preview_seed(make_preview_seed):
    def seed(env):
        code = """
from decimal import Decimal
from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod06_proc.models import ProcMechManual
from app.mod07_setl.models import AnalysisBigManual
from app.mod08_inv.models import InvDetail
from app.mod11_jc.models import JcContract, JcInvoice
from sqlalchemy import select
with session_scope() as s:
    made = {}
    for ord_, disp, wh in [(10, '大表验收甲', '大表验收仓库甲'), (11, '大表验收乙', '大表验收仓库乙'),
                           (12, '大表验收丙', '大表验收仓库丙'), (13, '大表验收丁', '大表验收仓库丁'),
                           (14, '大表验收戊', '大表验收仓库戊'), (15, '大表验收己', '大表验收仓库己'),
                           (16, '大表验收庚', '大表验收仓库庚'), (17, '大表验收辛', '大表验收仓库辛')]:
        made[wh] = Project(project_type='normal', name_full='隔离验收' + disp + '全名', warehouse_name=wh, disp=disp, ord=ord_)
    s.add_all(made.values()); s.flush()
    made['隔离验收仓库'] = s.scalar(select(Project).where(Project.disp == '隔离项目'))
    made['长名称验收仓库'] = s.scalar(select(Project).where(Project.disp == '长项目名验收'))
    s.add_all([InvDetail(project_id=made[wh].id, warehouse_name=wh, ym=ym, direction='入库',
                         material_name=name, amount=Decimal(amt), doc_date='2099-01-01')
               for wh, ym, name, amt in [
                   ('大表验收仓库甲', '2026-01', '二氧化碳气体保护实芯焊丝', '300.50'),
                   ('大表验收仓库甲', '2026-09', '二氧化碳气体保护实芯焊丝', '120.25'),
                   ('大表验收仓库甲', '2026-03', '氩气', '50'),
                   ('大表验收仓库甲', '2026-09', '氧气', '30'),
                   ('大表验收仓库甲', '2026-09', '焊条保温桶', '999'),
                   ('大表验收仓库甲', '2026-09', '氧气瓶', '888'),
                   ('长名称验收仓库', '2026-05', '焊条', '10'),
                   ('长名称验收仓库', '2026-05', '二氧化碳', '20'),
                   ('大表验收仓库丙', '2027-01', '焊丝', '88.50')]])
    for wh, ym, cols in [('大表验收仓库甲', '2026-01', {'mech_1': 5, 'mech_2': 50}),
                         ('大表验收仓库甲', '2026-08', {'mech_1': 10, 'mech_2': 100, 'mech_3': 200}),
                         ('大表验收仓库甲', '2026-09', {'mech_1': 20, 'mech_2': 150, 'mech_3': 250}),
                         ('长名称验收仓库', '2026-09', {'mech_2': 60})]:
        s.add(ProcMechManual(ym=ym, project_id=made[wh].id, warehouse_name=wh, **cols))
    s.add(AnalysisBigManual(ym='2026-08', warehouse_name='大表验收仓库甲', project_id=made['大表验收仓库甲'].id,
                            open_ym='2025-06', mech_est=Decimal('1000'), contract_price=Decimal('8000'),
                            output_cum=Decimal('2000'), oil=Decimal('45.50'), note='八月备注甲'))
    s.add(AnalysisBigManual(ym='2026-09', warehouse_name='长名称验收仓库',
                            project_id=made['长名称验收仓库'].id, mech_est=Decimal('0')))
    s.add(AnalysisBigManual(ym='2027-01', warehouse_name='大表验收仓库丙',
                            project_id=made['大表验收仓库丙'].id, open_ym='2026-03'))
    a = JcContract(project_id=made['隔离验收仓库'].id, contract_no='TAIL413-JC-A',
                   material_name='大表主材甲', supplier='合成供应商', contract_amt=5000)
    b = JcContract(project_id=made['长名称验收仓库'].id, contract_no='TAIL413-JC-B',
                   material_name='大表主材乙', supplier='合成供应商', contract_amt=600)
    s.add_all([a, b]); s.flush()
    s.add(JcInvoice(contract_id=a.id, kind='supplier', invoice_date='2026-08-01', amount=Decimal('1234.56')))
    s.add(JcInvoice(contract_id=b.id, kind='supplier', invoice_date='2026-08-02', amount=Decimal('100')))
"""
        subprocess.run([sys.executable, '-X', 'utf8', '-c', code], env=env, check=True)
    return make_preview_seed(seed)


def money(text) -> str:
    whole, _, part = f"{Decimal(text):.2f}".partition('.')
    sign = '-' if whole.startswith('-') else ''
    return sign + f"{int(whole.replace('-', '')):,}" + '.' + part


def big_api(page, server, ym=MONTH):
    response = page.request.get(server + '/api/m07/big?period=' + ym)
    assert response.status == 200
    return response.json()


def row_by(api, warehouse):
    return next(row for row in api['rows'] if row['warehouse'] == warehouse)


def visible_grid(page):
    return page.locator('.big-month:not([hidden]) .big-grid')


def pinned(page, key):
    return visible_grid(page).locator('.ag-row-pinned').locator(f'[col-id="{key}"]')


def choose_month(page, ym):
    picker = page.get_by_label('大表核算月', exact=True)
    picker.click()
    picker.fill(ym)
    picker.press('Enter')
    expect(picker).to_have_value(ym)


def open_big(page, server):
    login(page, server)
    page.get_by_role('link', name='MOD-07 月度会大表').click()
    expect(visible_grid(page).locator('.ag-row').first).to_be_visible()
    choose_month(page, MONTH)


def row_of(page, warehouse):
    return visible_grid(page).locator(f'[row-id="{warehouse}"]')


def cell_input(page, warehouse, key):
    return row_of(page, warehouse).locator(f'[col-id="{key}"] input')


def test_read_groups_totals_carry_and_column_groups(server, browser_page):
    page, _ = browser_page
    open_big(page, server)
    api = big_api(page, server)
    rows = api['rows']
    assert len(rows) == 10 and api['month'] == MONTH
    # Never chosen: the default selection is every candidate in archive order.
    assert [r['display'] for r in rows] == ['隔离项目', '长项目名验收', '大表验收甲', '大表验收乙', '大表验收丙',
                                            '大表验收丁', '大表验收戊', '大表验收己', '大表验收庚', '大表验收辛']
    assert api['selected'] == [r['warehouse'] for r in rows]
    a, b = row_by(api, WH_A), row_by(api, WH_B)
    # Hand-computed seed expectations (2026-09): extraction is inbound-origin by keyword/whitelist.
    assert (a['auto']['hw_cum'], a['auto']['hw_mon']) == ('420.75', '120.25')
    assert (a['auto']['qt_cum'], a['auto']['qt_mon']) == ('80.00', '30.00')
    # Months without extraction records come back as the raw int 0 ('0'), not '0.00'; the page formats both to 0.00.
    assert (b['auto']['hw_cum'], b['auto']['hw_mon']) == ('10.00', '0')
    assert (b['auto']['qt_cum'], b['auto']['qt_mon']) == ('20.00', '0')
    # Excluded names (焊条保温桶 → 排除子串, 氧气瓶 → 非精确匹配) must not have entered any number.
    assert a['auto']['hw_mon'] == '120.25' and a['auto']['qt_cum'] == '80.00'
    assert (a['auto']['rent_cum'], a['auto']['rent_mon']) == ('750.00', '400.00')
    assert (a['auto']['lease_cum'], a['auto']['lease_mon']) == ('35.00', '20.00')
    assert (b['auto']['rent_cum'], b['auto']['rent_mon']) == ('60.00', '60.00')
    assert (a['derived']['total_cum'], a['derived']['use_rate']) == ('785.00', '0.7850')  # rate keeps 4 decimals
    assert (a['derived']['output_rate'], a['derived']['mat_cum']) == ('0.2500', '0.00')  # 甲 has no contract
    # The settled jc contracts sit on the two preseeded projects; only tagged-in ones count.
    assert row_by(api, '隔离验收仓库')['derived']['mat_cum'] == '1234.56'
    assert b['derived']['mat_cum'] == '100.00' and b['manual']['mech_est'] == {'value': '0.00', 'from': ''}
    assert a['manual']['mech_est'] == {'value': '1000.00', 'from': '2026-08'}
    assert api['totals'] == {
        'hw_cum': '430.75', 'hw_mon': '120.25', 'qt_cum': '100.00', 'qt_mon': '30.00',
        'rent_cum': '810.00', 'rent_mon': '460.00', 'lease_cum': '35.00', 'lease_mon': '20.00',
        'total_cum': '845.00', 'mech_est': '1000.00', 'contract': '8000.00', 'output_cum': '2000.00',
        'mat_cum': '1334.56', 'oil': '45.50'}
    # Column groups: 项目3 / 辅材4 / 机械7 / 产值3 plus three standalone columns = 20 leaves.
    header = page.evaluate("""() => {
        const scope = '.big-month:not([hidden]) .big-grid ';
        const texts = sel => [...document.querySelectorAll(scope + sel)]
            .map(e => (e.querySelector('.ag-header-cell-text,.ag-header-group-text') ?? {}).textContent ?? '');
        return { groups: texts('.ag-header-group-cell'), leaves: texts('.ag-header-cell') };
    }""")
    assert [name for name in header['groups'] if name] == GROUPS
    assert [name for name in header['leaves'] if name] == LEAVES
    # Totals come straight from the backend passthrough, not a second page-side computation.
    for key in TOTAL_KEYS:
        expect(pinned(page, key)).to_have_text(money(api['totals'][key]))
    expect(pinned(page, 'use_rate')).to_have_text('')
    # Rates and carry render from the same API payload.
    expect(row_of(page, WH_A).locator('[col-id="use_rate"]')).to_have_text('78.5%')
    expect(row_of(page, WH_A).locator('[col-id="output_rate"]')).to_have_text('25.0%')
    expect(cell_input(page, WH_A, 'mech_est')).to_have_value('1000.00')
    expect(row_of(page, WH_A).locator('[col-id="mech_est"] .big-carry-tag')).to_have_text('2026-08 带入')
    expect(cell_input(page, WH_A, 'note')).to_have_value('八月备注甲')
    expect(cell_input(page, WH_C, 'open_ym')).to_have_value('')  # the 2027-01 record is not this month's
    expect(page.locator('.big-count')).to_have_text('10 个项目')
    page.screenshot(path=str(output('tail413-big-1920.png', kind='screenshots')), full_page=True)


def test_manual_cell_save_reject_clear_and_uncertain_receipt(server, browser_page):
    page, _ = browser_page
    open_big(page, server)
    # A real HTTP save lands in the database and the reread keeps it.
    box = cell_input(page, WH_A, 'mech_est')
    box.fill('1500')
    box.press('Tab')
    expect(page.locator('.big-feedback')).to_contain_text('大表验收甲 · 机械费测算 · 已保存到本月')
    api = big_api(page, server)
    assert row_by(api, WH_A)['manual']['mech_est'] == {'value': '1500.00', 'from': ''}
    assert api['totals']['mech_est'] == '1500.00'
    expect(box).to_have_value('1500.00')  # the reread does not clobber the saved value
    # Rejections store nothing: bad text, negative, bad month format.
    for raw, needle in [('abc', '金额要填数字'), ('-5', '不得为负')]:
        box.fill(raw)
        box.press('Tab')
        alert = page.get_by_role('alert').first
        expect(alert).to_contain_text(needle)
        expect(alert).to_contain_text('原值不变')
        assert row_by(big_api(page, server), WH_A)['manual']['mech_est']['value'] == '1500.00'
        draft = page.locator('.big-draft')
        expect(draft).to_contain_text(raw)
        expect(draft.locator('[role="alert"]')).to_contain_text(needle)
        page.get_by_role('button', name='取消修改', exact=True).click()
        expect(page.locator('.big-draft')).to_have_count(0)
    year = cell_input(page, WH_A, 'open_ym')
    year.fill('2026-13')
    year.press('Tab')
    expect(page.get_by_role('alert').first).to_contain_text('开工时间要填')
    assert row_by(big_api(page, server), WH_A)['manual']['open_ym']['value'] == '2025-06'
    page.get_by_role('button', name='取消修改', exact=True).click()
    # Clearing returns the cell to the carry state from its earlier month.
    box.fill('')
    box.press('Tab')
    expect(page.locator('.big-feedback')).to_contain_text('已清空，恢复带入')
    assert row_by(big_api(page, server), WH_A)['manual']['mech_est'] == {'value': '1000.00', 'from': '2026-08'}
    expect(row_of(page, WH_A).locator('[col-id="mech_est"] .big-carry-tag')).to_have_text('2026-08 带入')
    # A 200 receipt with a damaged body is treated as uncertain: one write, no retry offer.
    page.route('**/api/m07/big/cell', lambda route: route.fulfill(response=route.fetch(), body='{'))
    contract = cell_input(page, WH_A, 'contract')
    contract.fill('9000')
    contract.press('Tab')
    alert = page.get_by_role('alert').first
    expect(alert).to_contain_text('保存结果待核实。')
    expect(alert).to_contain_text('勿重复提交')
    expect(contract).to_be_disabled()
    assert row_by(big_api(page, server), WH_A)['manual']['contract']['value'] == '9000.00'
    page.unroute('**/api/m07/big/cell')
    page.get_by_role('button', name='重读核对', exact=True).click()
    expect(page.get_by_role('button', name='已核对，继续', exact=True)).to_be_enabled()
    expect(cell_input(page, WH_A, 'contract')).to_have_value('9000')  # the draft is kept for the user to judge
    page.get_by_role('button', name='已核对，继续', exact=True).click()
    page.locator('.big-draft').get_by_role('button', name='取消修改', exact=True).click()
    expect(cell_input(page, WH_A, 'contract')).to_have_value('9000.00')  # the reread value stands
    # Writing works again after the explicit verification.
    oil = cell_input(page, WH_A, 'oil')
    oil.fill('66.6')
    oil.press('Tab')
    expect(page.locator('.big-feedback')).to_contain_text('工程用油 · 已保存到本月')
    assert row_by(big_api(page, server), WH_A)['manual']['oil'] == {'value': '66.60', 'from': ''}


def test_selection_order_dialog_save_reread_and_cancel(server, browser_page):
    page, _ = browser_page
    open_big(page, server)
    page.get_by_role('button', name='选择项目与排序…', exact=True).click()
    dialog = page.locator('.big-order-dialog')
    expect(dialog.get_by_role('heading', name='选择项目与排序')).to_be_visible()
    expect(dialog.get_by_text('10 个项目 · 页面与导出同序', exact=True)).to_be_visible()
    # Moving writes the big table's own order, independent of the archive order.
    up = dialog.get_by_role('button', name='上移大表验收甲', exact=True)
    up.click()
    up.click()
    expect(dialog.locator('.big-order-table tbody tr').first).to_contain_text('大表验收甲')
    dialog.get_by_role('button', name='保存项目与顺序', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.locator('.big-feedback')).to_contain_text('项目与顺序已保存。')
    api = big_api(page, server)
    assert api['selected'][0] == WH_A and len(api['selected']) == 10
    assert [r['display'] for r in api['rows']][0] == '大表验收甲'
    expect(row_of(page, WH_A).locator('[col-id="seq"]')).to_have_text('1')
    expect(page.locator('.big-count')).to_have_text('10 个项目')
    # Reorder again and drop one project; only the chosen ones stay, in the saved order.
    page.get_by_role('button', name='选择项目与排序…', exact=True).click()
    dialog.get_by_role('button', name='下移大表验收甲', exact=True).click()
    pick_option(page, '大表项目', '大表验收辛')
    page.keyboard.press('Escape')
    expect(dialog.get_by_text('9 个项目 · 页面与导出同序', exact=True)).to_be_visible()
    dialog.get_by_role('button', name='保存项目与顺序', exact=True).click()
    expect(dialog).not_to_be_visible()
    api = big_api(page, server)
    assert api['selected'] == ['隔离验收仓库', WH_A, '长名称验收仓库', '大表验收仓库乙', '大表验收仓库丙',
                               '大表验收仓库丁', '大表验收仓库戊', '大表验收仓库己', '大表验收仓库庚']
    assert [r['warehouse'] for r in api['rows']] == api['selected']
    assert [r['seq'] for r in api['rows']] == list(range(1, 10))
    expect(page.locator('.big-count')).to_have_text('9 个项目')
    expect(row_of(page, WH_A).locator('[col-id="seq"]')).to_have_text('2')
    expect(visible_grid(page).locator('[row-id="大表验收仓库辛"]')).to_have_count(0)
    # Cancelling a dirty dialog keeps the stored order.
    page.get_by_role('button', name='选择项目与排序…', exact=True).click()
    dialog.get_by_role('button', name='上移大表验收甲', exact=True).click()
    dialog.get_by_role('button', name='取消', exact=True).click()
    dialog.get_by_role('button', name='放弃并关闭', exact=True).click()
    expect(dialog).not_to_be_visible()
    assert big_api(page, server)['selected'] == api['selected']


def test_export_download_matches_rows_order_and_template(server, browser_page):
    page, _ = browser_page
    open_big(page, server)
    api = big_api(page, server)
    page.get_by_role('button', name='导出文件…', exact=True).click()
    dialog = page.locator('.settlement-export-dialog')
    expect(dialog.get_by_role('heading', name='导出 · 2026-09 月度会大表')).to_be_visible()
    items = dialog.locator('.big-export-list li')
    expect(items).to_have_count(len(api['rows']))
    assert [items.nth(i).inner_text() for i in range(len(api['rows']))] == [r['display'] for r in api['rows']]
    with page.expect_download() as event:
        dialog.get_by_role('button', name='保存到本地', exact=True).click()
    download = event.value
    assert download.suggested_filename == '经济活动分析大表_2026年9月.xlsx'
    path = output('tail413-big-2026-09.xlsx', kind='exports')
    download.save_as(str(path))
    # The server side also kept its copy inside this round's isolated .artifacts exports.
    from tools.audit.workspace_paths import output_dir
    produced = output_dir('exports') / '活动大表' / '2026年9月' / '经济活动分析大表_2026年9月.xlsx'
    assert produced.exists()
    import openpyxl
    workbook = openpyxl.load_workbook(str(path))
    try:
        sheet = workbook['Sheet1']
        assert sheet.max_column == 20
        assert '（数据截止9月30日）' in sheet['A1'].value and '（9月份数据）' in sheet['A1'].value
        for i, row in enumerate(api['rows']):
            excel = 5 + i
            assert sheet.cell(excel, 1).value == i + 1
            assert sheet.cell(excel, 2).value == row['display']
            for j, key in enumerate(EXPORT_KEYS[2:], start=3):
                expected = (row['manual'][key]['value'] if key in row['manual']
                            else row['auto'][key] if key in row['auto'] else row['derived'][key])
                got = sheet.cell(excel, j).value
                if expected is None:
                    assert got in (None, ''), (key, excel)
                elif key in ('open_ym', 'note'):  # text columns keep their string value
                    assert str(got) == str(expected), (key, excel, got, expected)
                else:
                    assert got is not None and abs(float(got) - float(expected)) < 1e-9, (key, excel, got, expected)
        totals_row = 5 + len(api['rows'])
        assert sheet.cell(totals_row, 1).value == '合计：'
        for j, key in enumerate(EXPORT_KEYS, start=1):
            got = sheet.cell(totals_row, j).value
            if key == 'seq':
                continue  # A:C merged '合计：' label, asserted above
            elif key in TOTAL_KEYS:
                assert got is not None and abs(float(got) - float(api['totals'][key])) < 1e-9, (key, got)
            else:
                assert got in (None, ''), (key, got)  # rates / open_ym / note are never summed
        for excel_row in sheet.iter_rows():
            for cell in excel_row:
                assert not (isinstance(cell.value, str) and cell.value.startswith('=')), cell.coordinate
    finally:
        workbook.close()
    page.screenshot(path=str(output('tail413-big-export-dialog.png', kind='screenshots')), full_page=True)


def test_unauthenticated_readonly_and_api_rejection(server, browser_page):
    page, _ = browser_page
    page.goto(server + '/preview/big')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(visible_grid(page).locator('.ag-row').first).to_be_visible()
    expect(page.get_by_role('button', name='选择项目与排序…', exact=True)).to_be_disabled()
    expect(page.get_by_role('button', name='导出文件…', exact=True)).to_be_disabled()
    expect(page.locator('.big-grid [col-id="mech_est"] input').first).to_be_disabled()
    before = big_api(page, server)
    with httpx.Client(base_url=server) as client:
        cell = client.post('/api/m07/big/cell',
                           json={'month': MONTH, 'warehouse': WH_A, 'key': 'mech_est', 'raw': '1'})
        assert cell.status_code == 401 and '未登录' in cell.json()['message']
        selection = client.post('/api/m07/big/selection', json={'selected': []})
        assert selection.status_code == 401 and '未登录' in selection.json()['message']
    after = big_api(page, server)
    assert after['rows'] == before['rows'] and after['selected'] == before['selected']


def test_draft_survives_month_switch_and_late_response_never_overwrites(server, browser_page):
    page, _ = browser_page
    open_big(page, server)
    # A write held in flight while leaving the month is paused, never sent, draft kept.
    pending = []
    page.route('**/api/m07/big/cell', lambda route: pending.append(route))
    note = cell_input(page, WH_A, 'note')
    note.fill('切月草稿')
    note.press('Tab')
    expect(page.locator('.big-draft')).to_contain_text('切月草稿')
    assert pending
    choose_month(page, NEXT_MONTH)
    expect(row_of(page, WH_C).locator('[col-id="hw_cum"]')).to_have_text('88.50')
    # The write never left the browser: the 2026-09 note is still the untouched carry value.
    assert row_by(big_api(page, server), WH_A)['manual']['note'] == {'value': '八月备注甲', 'from': '2026-08'}
    choose_month(page, MONTH)
    expect(cell_input(page, WH_A, 'note')).to_have_value('切月草稿')
    pending.pop().abort()  # release the held write without any server contact
    page.locator('.big-draft').get_by_role('button', name='取消修改', exact=True).click()
    expect(page.locator('.big-draft')).to_have_count(0)
    expect(cell_input(page, WH_A, 'note')).to_have_value('八月备注甲')
    assert row_by(big_api(page, server), WH_A)['manual']['note'] == {'value': '八月备注甲', 'from': '2026-08'}
    # A slow response for the month that was left must not overwrite the context on screen.
    captured = big_api(page, server, MONTH)
    late = []
    page.route('**/api/m07/big?period=' + MONTH, lambda route: late.append(route))
    choose_month(page, NEXT_MONTH)
    expect(row_of(page, WH_C).locator('[col-id="hw_cum"]')).to_have_text('88.50')
    choose_month(page, MONTH)  # re-entering the old month starts its refetch, which we hold
    choose_month(page, NEXT_MONTH)
    expect(row_of(page, WH_C).locator('[col-id="hw_cum"]')).to_have_text('88.50')
    assert late
    late.pop().fulfill(status=200, json=captured)  # the late 2026-09 answer arrives afterwards
    expect(pinned(page, 'hw_mon')).to_have_text('88.50')  # the visible month keeps 2027-01 numbers
    expect(row_of(page, WH_A).locator('[col-id="hw_cum"]')).to_have_text('0.00')
    expect(page.locator('.big-month:not([hidden])')).to_have_count(1)
    expect(page.locator('.big-month[hidden] .ag-row-pinned [col-id="hw_mon"]')).to_have_text('120.25')
    page.unroute('**/api/m07/big?period=' + MONTH)


def test_layout_money_complete_narrow_viewport_and_performance(server, browser_page):
    page, _ = browser_page
    timings = {}
    started = time.perf_counter()
    login(page, server)
    page.get_by_role('link', name='MOD-07 月度会大表').click()
    expect(visible_grid(page).locator('.ag-row').first).to_be_visible()
    timings['enter_to_first_row'] = round(time.perf_counter() - started, 2)
    choose_month(page, MONTH)
    expect(page.locator('.big-count')).to_have_text('9 个项目')
    # Group boundaries exist on the group starts and the three standalone columns.
    starts = visible_grid(page).locator('.ag-header-cell.big-group-start, .ag-header-group-cell.big-group-start')
    assert starts.count() >= GROUP_STARTS
    cells = visible_grid(page).locator('.ag-cell.big-money')
    assert cells.count() > 100
    assert cells.evaluate_all('(cells) => cells.every(c => c.scrollWidth <= c.clientWidth)')
    geometry = page.evaluate("""() => {
        const root = document.querySelector('.big-month:not([hidden]) .big-grid');
        const header = [...root.querySelectorAll('.ag-header-cell')];
        const total = Math.round(header.reduce((w, e) => w + e.getBoundingClientRect().width, 0));
        return { total, viewportWidth: Math.round(root.clientWidth) };
    }""")
    timings['grid_columns_1920'] = geometry
    page.screenshot(path=str(output('tail413-big-groups-1920.png', kind='screenshots')), full_page=True)
    # Edit round trip on a wide viewport.
    step = time.perf_counter()
    oil = cell_input(page, WH_A, 'oil')
    oil.fill('12.34')
    oil.press('Tab')
    expect(page.locator('.big-feedback')).to_contain_text('工程用油 · 已保存到本月')
    timings['edit_save_roundtrip'] = round(time.perf_counter() - step, 2)
    # Narrow viewport: every amount stays complete and the far columns stay reachable.
    page.set_viewport_size({'width': 1000, 'height': 900})
    expect(cells.first).to_be_visible()
    scroll_info = page.evaluate("""() => {
        const root = document.querySelector('.big-month:not([hidden]) .big-grid');
        const header = [...root.querySelectorAll('.ag-header-cell')];
        const total = Math.round(header.reduce((w, e) => w + e.getBoundingClientRect().width, 0));
        // AG Grid 36 drives horizontal scroll from its fake scrollbar viewport.
        const candidates = ['.ag-body-horizontal-scroll-viewport', '.ag-center-cols-viewport',
                            '.ag-body-horizontal-scroll'];
        const probed = {};
        let scrolled = 0;
        for (const sel of candidates) {
            const el = root.querySelector(sel);
            if (!el) continue;
            probed[sel] = { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth };
            if (el.scrollWidth > el.clientWidth + 1 && !scrolled) {
                el.scrollLeft = el.scrollWidth;
                scrolled = Math.round(el.scrollLeft);
            }
        }
        const note = [...root.querySelectorAll('.ag-header-cell-text')].find(e => e.textContent === '备注');
        const right = note ? Math.round(note.getBoundingClientRect().right) : 0;
        return { total, viewportWidth: Math.round(root.clientWidth), probed, scrolled, noteRight: right,
                 bodyRight: Math.round(root.getBoundingClientRect().right) };
    }""")
    print('TAIL-413 narrow scroll probe:', scroll_info, flush=True)
    timings['grid_columns_1000'] = scroll_info
    if scroll_info['total'] > scroll_info['viewportWidth']:  # overflowing table keeps its scrollbar reachable
        assert scroll_info['scrolled'] > 0, scroll_info
        # AG Grid applies the column transform on the scroll event; poll until the farthest column shows.
        page.wait_for_function("""() => {
            const root = document.querySelector('.big-month:not([hidden]) .big-grid');
            const note = [...root.querySelectorAll('.ag-header-cell-text')].find(e => e.textContent === '备注');
            return note && note.getBoundingClientRect().right <= root.getBoundingClientRect().right + 1;
        }""")
        assert visible_grid(page).locator('.ag-header-cell-text').filter(has_text='备注').first.is_visible()
    assert cells.evaluate_all('(cells) => cells.every(c => c.scrollWidth <= c.clientWidth)')
    expect(page.get_by_role('button', name='选择项目与排序…', exact=True)).to_be_in_viewport()
    expect(page.get_by_role('button', name='导出文件…', exact=True)).to_be_in_viewport()
    step = time.perf_counter()
    choose_month(page, NEXT_MONTH)
    expect(row_of(page, WH_C).locator('[col-id="hw_cum"]')).to_have_text('88.50')
    timings['month_switch_to_rows'] = round(time.perf_counter() - step, 2)
    page.screenshot(path=str(output('tail413-big-1000-scrolled.png', kind='screenshots')), full_page=True)
    report = output('tail413-big-perf.txt', kind='reports')
    report.write_text('\n'.join(f'{key}: {value}' for key, value in timings.items()) + '\n', encoding='utf-8')
    print('TAIL-413 timings:', timings, flush=True)
