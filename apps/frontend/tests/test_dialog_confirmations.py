"""Read-only UI regressions for untouched drafts and the shared discard confirmation."""
from playwright.sync_api import expect
from test_preview import server, browser_page, login
from live_data import get, contract_sample, grid_row


def single_match_notice(api):
    rows=get(api,'/api/m03/notice-list',period='')['items']
    for row in rows:
        if row['category']!='jc' or row['has_link'] or row['jc_supplier'] or row['is_excluded'] or row['is_revoked']:
            continue
        match=api.post('/api/m03/actions/sup-match',json={'notice_id':row['notice_id']}).json()
        if len(match.get('cands',[]))==1:return row,match['cands'][0]
    raise AssertionError('真实副本缺少未关联且自动单命中的通知书，此缺陷未覆盖')


def open_notice(page,server,row):
    page.goto(server+f"/preview/notices?notice={row['notice_id']}")
    page.get_by_label('通知书搜索',exact=True).fill(row['bill_no'])
    page.locator(f"[data-contract-notice=\"{row['notice_id']}\"]").click()
    return page.get_by_role('dialog',name='供应商与合同关联',exact=True)


def test_untouched_automatic_suggestion_cancels_directly(server,browser_page,api):
    page,_=browser_page;row,name=single_match_notice(api);login(page,server)
    dialog=open_notice(page,server,row)
    expect(dialog.get_by_label('供应商名称',exact=True)).to_have_value(name)
    dialog.get_by_role('button',name='取消',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    dialog=open_notice(page,server,row)
    expect(dialog.get_by_label('供应商名称',exact=True)).to_have_value(name)
    dialog.get_by_role('button',name='下一步：选择合同',exact=True).click()
    dialog.get_by_role('button',name='上一步',exact=True).click()
    dialog.get_by_role('button',name='关闭合同关联',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)


def test_discard_confirmation_reuses_contract_content_and_size(server,browser_page,api):
    page,_=browser_page;notice,_=single_match_notice(api);contract,label=contract_sample(api)
    login(page,server);page.goto(server+'/preview/contracts')
    page.get_by_label('搜索',exact=True).fill(label)
    grid_row(page,'.contracts-grid',contract['id']).locator('.contract-object button').click()
    editor=page.get_by_role('dialog',name='材料名',exact=True)
    field=editor.get_by_label('材料名',exact=True)
    expect(field).to_be_enabled();field.fill(contract['material']+'（未保存测试）')
    editor.get_by_role('button',name='取消',exact=True).click()
    reference=page.get_by_role('dialog',name='放弃未保存的修改？',exact=True)
    expect(page.locator('.ant-modal')).to_have_css('transform','none')
    reference_size=reference.locator('.project-dialog').bounding_box()
    reference_text=reference.inner_text()
    reference.get_by_role('button',name='放弃并关闭',exact=True).click()
    dialog=open_notice(page,server,notice)
    field=dialog.get_by_label('供应商名称',exact=True)
    expect(field).to_be_enabled();field.fill('临时筛选（未保存）')
    dialog.get_by_role('button',name='取消',exact=True).click()
    confirmation=page.get_by_role('dialog')
    expect(confirmation).to_have_accessible_name('放弃未保存的修改？')
    expect(confirmation).to_have_text(reference_text)
    size=confirmation.locator('.project-dialog').bounding_box()
    assert abs(size['width']-reference_size['width'])<1,(size,reference_size)
    assert abs(size['height']-reference_size['height'])<1,(size,reference_size)
    confirmation.get_by_role('button',name='继续编辑',exact=True).click()
    expect(field).to_have_value('临时筛选（未保存）')
    dialog.get_by_role('button',name='取消',exact=True).click()
    page.get_by_role('button',name='放弃并关闭',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
