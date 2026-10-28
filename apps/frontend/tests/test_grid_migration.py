"""The four migration gates exercise actual copied records and native AG interactions."""
import json
from decimal import Decimal
from uuid import uuid4
from playwright.sync_api import expect
from test_preview import server, browser_page, login
from live_data import get, open_page
from test_grid_widths import resize, storage_key
from preview_select import pick_option


def test_invoice_instances_share_native_width_and_reset(server, browser_page, api, preview_screenshot):
    sample = None
    for row in get(api, '/api/m03/notice-list', period='')['items']:
        if row['category'] != 'jc' or row['is_excluded'] or row['is_revoked']:
            continue
        candidates = get(api, '/api/m11/link-recommendations', notice_id=row['notice_id'], supplier='')['rows']
        if sum(bool(c['invoices']) for c in candidates) > 1:
            sample = row
            break
    assert sample, '真实副本缺少多候选发票表，宽度共享未覆盖'
    page, _ = browser_page
    me = login(page, server)
    page.goto(server + '/preview/notices?notice=' + str(sample['notice_id']))
    page.locator(f'[data-contract-notice="{sample["notice_id"]}"]').click()
    dialog = page.get_by_role('dialog', name='供应商与合同关联', exact=True)
    if sample['has_link']:
        dialog.get_by_role('button', name='上一步', exact=True).click()
    dialog.get_by_label('供应商名称', exact=True).fill('')
    dialog.get_by_role('button', name='下一步：选择合同', exact=True).click()
    grids = dialog.locator('.contract-invoices .business-grid')
    expect(grids.nth(1)).to_have_attribute('data-layout-state', 'ready', timeout=30000)
    # Give the first actual instance a selector; this changes no grid or business state.
    grids.first.evaluate("e=>e.id='migration-first-invoices'")
    width = resize(page, '#migration-first-invoices', 'date', 40)
    expect(grids.nth(1).locator('.ag-header-cell[col-id=date]')).to_have_css('width', width)
    saved = page.evaluate('key=>JSON.parse(localStorage.getItem(key))', storage_key(me, 'notice-candidate-invoices'))
    assert set(saved['widths']) == {'date'}
    grids.first.locator('..').get_by_role('button', name='恢复自动列宽', exact=True).click()
    expect(dialog.locator('.contract-invoices .grid-width-tools button:enabled')).to_have_count(0)
    assert page.evaluate('key=>localStorage.getItem(key)', storage_key(me, 'notice-candidate-invoices')) is None
    if len(candidates)>8:
        assert dialog.locator('.contract-candidate').count()<len(candidates), '大候选集必须由成熟组件虚拟化'
        choice=dialog.locator('.contract-candidate input[type=radio]').first
        label=choice.get_attribute('aria-label');choice.check()
        scroller=dialog.locator('.contract-candidates')
        last=candidates[-1]
        last_label='选择'+(last['material'].strip() or '材料名称未填')+'，'+last['contract_no']
        scroller.evaluate('e=>e.scrollTop=e.scrollHeight')
        expect(dialog.get_by_role('radio',name=last_label,exact=True)).to_be_visible(timeout=15000)
        scroller.evaluate('e=>e.scrollTop=0')
        expect(dialog.get_by_role('radio',name=label,exact=True)).to_be_checked()
    preview_screenshot('pilot-candidate-invoices')


def test_detail_draft_keeps_inputs_and_complete_totals(server, browser_page, api, projects, disposable, preview_screenshot):
    page, _ = browser_page
    open_page(page, server, 'mechanical', '机械费')
    ym = page.get_by_label('月份', exact=True).input_value()
    state = get(api, '/api/m06/workbench', ym=ym)
    warehouse = state['projects'][0]['warehouse']
    project = next(p for p in projects if p['warehouse_name'] == warehouse)
    page.get_by_role('button', name='显示项目', exact=True).click()
    dialog = page.get_by_role('dialog', name='选择显示项目及顺序', exact=True)
    dialog.get_by_role('button', name='全不选', exact=True).click()
    dialog.get_by_role('checkbox', name=project['disp'], exact=True).check()
    dialog.get_by_role('button', name='应用项目选择', exact=True).click()
    page.get_by_role('button', name='表2 零租明细', exact=True).click()
    grid = page.get_by_role('region', name='零租明细', exact=True)
    expect(grid).to_have_attribute('data-layout-state', 'ready')
    group = grid.locator('.ag-row.mechanical-detail-group-row')
    original = group.locator('[col-id=amount]').inner_text().replace(',', '')
    original = Decimal(original) if original != '—' else Decimal(0)
    before = grid.locator('input[aria-label$="设备名称"]').count()
    group.get_by_role('button', name='增行', exact=True).click()
    device = grid.locator('input[aria-label$="设备名称"]').last
    expect(device).to_be_focused()
    device.fill('迁移验证设备')
    row_id=device.locator('xpath=ancestor::*[@row-id][1]').get_attribute('row-id')
    row = grid.locator('[row-id='+json.dumps(row_id,ensure_ascii=False)+']')
    amount = row.locator('[col-id=amount] input')
    tax = row.locator('[col-id=tax] input')
    amount.fill('123.45')
    tax.fill('普票')
    row.locator('[col-id=plate] input').fill('豫A12345')
    row.locator('[col-id=plate] input').blur()
    expect(device).to_have_value('迁移验证设备')
    expect(amount).to_have_value('123.45')
    expect(row.locator('[col-id=net]')).to_have_text('123.45')
    expect(group.locator('[col-id=amount]')).to_have_text(format(original + Decimal('123.45'), ',.2f'))
    page.get_by_role('checkbox', name='仅看待补字段', exact=True).check()
    # Filtering rows must not replace the complete group total.
    expect(group.locator('[col-id=amount]')).to_have_text(format(original + Decimal('123.45'), ',.2f'))
    page.get_by_role('checkbox', name='仅看待补字段', exact=True).uncheck()
    row.get_by_role('button', name='移除', exact=True).click()
    expect(grid.locator('input[aria-label$="设备名称"]')).to_have_count(before)
    page.get_by_role('button', name='撤销未保存修改', exact=True).click()
    page.get_by_role('button', name='确认撤销', exact=True).click()
    preview_screenshot('pilot-mechanical-details')


def test_project_native_drag_uses_complete_business_order(server, browser_page, api, disposable, preview_screenshot):
    token = '__grid_' + uuid4().hex[:8]
    items = []
    for suffix in ['可见甲', '隐藏乙', '可见丙', '可见归档']:
        result = api.post('/api/m01/projects', json={'project_type':'normal', 'name_full':token+suffix, 'disp':token+suffix, 'warehouse_name':token+suffix})
        result.raise_for_status()
        items.append(result.json())
    response=api.put('/api/m01/projects/'+str(items[3]['id'])+'/status',json={'status':'archived'})
    response.raise_for_status()
    page, _ = browser_page
    login(page, server)
    pick_option(page,'项目状态筛选','全部')
    page.get_by_label('项目搜索', exact=True).fill(token+'可见')
    grid = page.get_by_role('region', name='项目列表', exact=True)
    grid.locator('.ag-header-cell[col-id=disp] .ag-header-cell-label').click()
    expect(grid.locator('.ag-header-cell[col-id=disp]')).to_have_attribute('aria-sort','ascending')
    source = grid.locator(f'.ag-row[row-id="{items[2]["id"]}"] .ag-row-drag')
    target = grid.locator(f'.ag-row[row-id="{items[0]["id"]}"]')
    expect(source).to_be_visible()
    a, b = source.bounding_box(), target.bounding_box()
    page.mouse.move(a['x']+a['width']/2, a['y']+a['height']/2)
    page.mouse.down()
    page.mouse.move(b['x']+30, b['y']+b['height']/3, steps=15)
    expect(page.locator('.project-drag-image')).to_be_visible()
    assert page.locator('.project-drag-image .ag-cell').count()>=8
    with page.expect_response(lambda r: r.url.endswith(f'/api/m01/projects/{items[2]["id"]}/ord') and r.request.method=='PUT') as response:
        page.mouse.up()
    assert response.value.ok
    actual = [p['id'] for p in get(api, '/api/m01/projects', status='all') if p['id'] in [i['id'] for i in items]]
    assert actual == [items[2]['id'], items[0]['id'], items[1]['id'],items[3]['id']]
    calls=[]
    page.on('request',lambda r:calls.append(r.url) if r.method=='PUT' and r.url.endswith('/ord') else None)
    expect(grid.get_by_role('button',name='上移：'+items[2]['disp'],exact=True)).to_be_enabled()
    source=grid.locator(f'.ag-row[row-id="{items[2]["id"]}"] .ag-row-drag')
    archived=grid.locator(f'.ag-row[row-id="{items[3]["id"]}"]')
    a,b=source.bounding_box(),archived.bounding_box()
    page.mouse.move(a['x']+a['width']/2,a['y']+a['height']/2);page.mouse.down()
    page.mouse.move(b['x']+30,b['y']+b['height']/2,steps=15);page.mouse.up()
    expect(page.locator('.project-drag-image')).not_to_be_visible()
    assert calls==[], '跨在建/归档分区不能发出调序写入'
    expect(page.get_by_label('项目搜索', exact=True)).to_have_value(token+'可见')
    grid.locator('.ag-header-cell[col-id=project_type] .ag-header-cell-label').click()
    grid.locator('.ag-header-cell[col-id=disp] .ag-header-cell-label').click(modifiers=['Shift'])
    grid.locator('.ag-header-cell[col-id=disp] .ag-header-cell-label').click(modifiers=['Shift'])
    expect(grid.locator('.ag-header-cell[col-id=project_type]')).to_have_attribute('aria-sort','ascending')
    expect(grid.locator('.ag-header-cell[col-id=disp]')).to_have_attribute('aria-sort','descending')
    expected=[items[0]['id'],items[2]['id'],items[3]['id']]
    assert grid.locator('.ag-row[row-id]:not(.ag-row-pinned)').evaluate_all('rows=>rows.map(row=>Number(row.getAttribute("row-id")))')==expected
    with page.expect_request(lambda request:request.url.endswith('/api/m01/projects/export') and request.method=='POST') as export, page.expect_download():
        page.get_by_role('button',name='导出 Excel',exact=True).click()
    assert export.value.post_data_json['ids']==expected, '项目导出必须保持屏幕原生多列排序后的完整顺序'
    preview_screenshot('pilot-project-drag')


def test_party_classification_updates_while_select_keeps_focus(server,browser_page,api):
    data=get(api,'/api/m11/party-kinds');party=next(item for item in data['items'] if item['kind'] in data['kinds'])
    other=next(kind for kind in data['kinds'] if kind!=party['kind'])
    page,_=browser_page;open_page(page,server,'contracts','集采台账')
    page.get_by_role('button',name='甲方单位分类',exact=True).click()
    grid=page.get_by_role('region',name='甲方单位分类',exact=True)
    expect(grid).to_have_attribute('data-layout-state','ready')
    label=party['name']+'分类';row=grid.locator('.ag-row').filter(has=page.get_by_label(label,exact=True))
    save=row.get_by_role('button',name='保存',exact=True);expect(save).to_be_disabled()
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' and r.url.endswith('/api/m11/party-kind') else None)
    pick_option(page,label,data['kind_names'][other])
    expect(row.get_by_title(data['kind_names'][other],exact=True)).to_be_visible();expect(save).to_be_enabled()
    expect(page.get_by_label(label,exact=True)).to_be_focused()
    pick_option(page,label,data['kind_names'][party['kind']])
    expect(row.get_by_title(data['kind_names'][party['kind']],exact=True)).to_be_visible();expect(save).to_be_disabled()
    assert writes==[], '分类草稿不能自动保存'
