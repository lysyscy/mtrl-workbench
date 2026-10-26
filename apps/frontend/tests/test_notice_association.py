"""Actual copied notices: drafts, explicit hint save, uncertain receipt, link and unlink."""
from playwright.sync_api import expect
from test_preview import server, browser_page, login
from live_data import get


def test_real_two_step_association_and_uncertain_hint(server, browser_page, api, disposable):
    page, _ = browser_page
    rows = get(api, '/api/m03/notice-list', period='')['items']
    sample = None
    for row in rows:
        if row['category'] != 'jc' or row['is_excluded'] or row['is_revoked'] or row['has_link']:
            continue
        candidates = get(api, '/api/m11/link-recommendations', notice_id=row['notice_id'], supplier='')['rows']
        target = next((c for c in candidates if c['supplier'] and c['supplier'] != row['jc_supplier']), None)
        if target:
            sample = row, candidates, target
            break
    assert sample, '真实副本缺少可关联通知书，保存动线未覆盖'
    row, candidates, target = sample
    nid = row['notice_id']; supplier = target['supplier']
    target = next(c for c in candidates if c['supplier'] == supplier)
    login(page, server)
    page.goto(server + f'/preview/notices?notice={nid}')
    trigger = page.locator(f'[data-contract-notice="{nid}"]')
    trigger.click()
    dialog = page.get_by_role('dialog', name='供应商与合同关联', exact=True)
    field = dialog.get_by_label('供应商名称', exact=True)
    expect(field).to_be_enabled()
    field.fill(supplier)
    expect(page.locator('.ant-modal')).to_have_css('transform','none')
    before = dialog.locator('.notice-association-dialog').bounding_box()
    dialog.get_by_role('button', name='下一步：选择合同', exact=True).click()
    radios = dialog.locator('.contract-candidates input[type=radio]')
    expect(radios.first).to_be_enabled()
    expect(dialog.locator('.contract-candidates input:checked')).to_have_count(0)
    radios.first.check()
    expect(dialog.locator('.contract-selection')).to_contain_text(target['material'])
    after = dialog.locator('.notice-association-dialog').bounding_box()
    assert all(abs(before[k]-after[k]) < 1 for k in ('x','y','width','height')), (before,after)
    dialog.get_by_role('button', name='上一步', exact=True).click()
    expect(field).to_have_value(supplier)
    dialog.get_by_role('button', name='下一步：选择合同', exact=True).click()
    expect(dialog.locator('.contract-candidates input:checked')).to_have_count(1)
    dialog.get_by_role('button', name='取消', exact=True).click()
    page.get_by_role('button', name='放弃并关闭', exact=True).click()
    current = next(r for r in get(api, '/api/m03/notice-list',period='')['items'] if r['notice_id']==nid)
    assert not current['has_link'] and current['jc_supplier']==row['jc_supplier']
    trigger.click();field.fill(supplier)
    writes = []
    def lost_receipt(route):
        response = route.fetch()
        assert response.ok and response.json()['ok']
        writes.append(route.request.post_data_json)
        route.fulfill(response=response,status=503,body='{"ok":false,"message":"保存后回执丢失"}')
    page.route('**/api/m03/actions/jc-supplier', lost_receipt)
    dialog.get_by_role('button', name='记住供应商，稍后关联', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('待核实')
    expect(dialog.get_by_role('button', name='关闭合同关联', exact=True)).to_be_disabled()
    expect(dialog.get_by_role('button', name='记住供应商，稍后关联', exact=True)).to_be_disabled()
    page.unroute('**/api/m03/actions/jc-supplier')
    dialog.get_by_role('button',name='重读核对',exact=True).click()
    expect(dialog).not_to_be_visible()
    assert len(writes)==1
    current = next(r for r in get(api, '/api/m03/notice-list',period='')['items'] if r['notice_id']==nid)
    assert not current['has_link'] and current['jc_supplier']==supplier
    trigger.click()
    dialog.get_by_role('button',name='下一步：选择合同',exact=True).click()
    dialog.locator('.contract-candidates input[type=radio]').first.check()
    dialog.get_by_role('button',name='确认关联',exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(trigger).to_contain_text('已关联合同')
    actual = get(api,'/api/m11/link-recommendations',notice_id=nid)
    assert actual['current_contract_id']==target['id'] and actual['supplier']==supplier
    trigger.click()
    expect(dialog.locator('.association-steps [aria-current=step]')).to_have_text('2 · 选择合同')
    expect(dialog.get_by_role('link',name='查看合同详情',exact=True)).to_be_visible()
    dialog.get_by_role('button',name='解除当前关联',exact=True).click()
    page.get_by_role('button',name='确认解除',exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(trigger).to_contain_text('未关联合同')
    current = next(r for r in get(api,'/api/m03/notice-list',period='')['items'] if r['notice_id']==nid)
    assert not current['has_link'] and current['jc_supplier']==supplier


def test_real_multiple_suppliers_remain_bounded_and_uncommitted(server,browser_page,api):
    page,_=browser_page
    rows=get(api,'/api/m03/notice-list',period='')['items']
    sample=None
    for row in [r for r in rows if r['category']=='jc' and not r['is_excluded'] and not r['is_revoked']][:45]:
        match=api.post('/api/m03/actions/sup-match',json={'notice_id':row['notice_id']}).json()
        assert match['ok']
        if len(match['cands'])>1:
            sample=row,match
            break
    assert sample,'真实副本缺少多供应商命中，候选动线未覆盖'
    row,match=sample
    prior=get(api,'/api/m11/link-recommendations',notice_id=row['notice_id'],supplier='')
    login(page,server)
    page.goto(server+f"/preview/notices?notice={row['notice_id']}")
    page.get_by_label('通知书搜索',exact=True).fill(row['bill_no'])
    page.locator(f"[data-contract-notice=\"{row['notice_id']}\"]").click()
    dialog=page.get_by_role('dialog',name='供应商与合同关联',exact=True)
    if row['has_link']:
        dialog.get_by_role('button',name='上一步',exact=True).click()
    field=dialog.get_by_label('供应商名称',exact=True)
    expect(field).to_be_enabled()
    field.fill('')
    radios=dialog.locator('.association-candidate-list input[type=radio]')
    expect(radios).to_have_count(len(match['cands']))
    expect(dialog.locator('.association-candidate-list input:checked')).to_have_count(0)
    assert radios.first.bounding_box()['width'] <= 20
    size=dialog.locator('.association-candidate-list').first.evaluate('(e)=>({height:e.clientHeight,scroll:e.scrollHeight})')
    assert size['height'] <= 220 and size['scroll'] > size['height']
    radios.last.check()
    expect(field).to_have_value(match['cands'][-1])
    page.set_viewport_size({'width':1366,'height':768})
    expect(page.locator('.ant-modal')).to_have_css('transform','none')
    before=dialog.locator('.notice-association-dialog').bounding_box()
    dialog.get_by_role('button',name='下一步：选择合同',exact=True).click()
    expect(dialog.locator('.association-steps [aria-current=step]')).to_have_text('2 · 选择合同')
    after=dialog.locator('.notice-association-dialog').bounding_box()
    assert all(abs(before[k]-after[k])<1 for k in ('x','y','width','height')),(before,after)
    footer=dialog.locator('.contract-footer').bounding_box()
    assert footer['y']+footer['height']<=768
    dialog.get_by_role('button',name='上一步',exact=True).click()
    expect(field).to_have_value(match['cands'][-1])
    dialog.get_by_role('button',name='取消',exact=True).click()
    page.get_by_role('button',name='放弃并关闭',exact=True).click()
    latest=get(api,'/api/m11/link-recommendations',notice_id=row['notice_id'],supplier='')
    assert latest['current_contract_id']==prior['current_contract_id']
    assert latest['supplier']==prior['supplier']
