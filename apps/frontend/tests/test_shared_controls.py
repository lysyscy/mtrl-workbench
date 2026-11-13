"""Browser regressions for shared dialog, table and operation-history controls."""
import re

from playwright.sync_api import expect
from test_preview import server,browser_page,login
from live_data import contract_sample,get,ledger_sample,open_page
from preview_select import pick_option


def test_oilcard_inline_account_name_keeps_native_caret(server, browser_page):
    page, _ = browser_page
    open_page(page, server, 'oilcard', '油卡管理')
    page.get_by_role('tab', name='账户与油卡', exact=True).click()
    page.get_by_role('button', name='新增账户', exact=True).click()
    field = page.get_by_role('region', name='用卡账户档案').locator('[row-id^="draft-"] input[aria-label^="账户名称："]')
    field.fill('甲乙')
    field.press('ArrowLeft')
    page.keyboard.insert_text('中')
    expect(field).to_have_value('甲中乙')


def select_oilcard_calendar_date(page, dialog, field_name):
    # Use the same mouse target as the visible calendar icon.
    picker = dialog.locator('.oilcard-calendar').filter(has=page.get_by_label('选择' + field_name, exact=True))
    picker.click()
    popup = page.locator('.ant-picker-dropdown:not(.ant-picker-dropdown-hidden)')
    expect(popup).to_be_visible()
    dialog.get_by_role('heading').click()
    expect(popup).to_have_count(0)
    picker.click()
    day = popup.locator('td.ant-picker-cell-in-view[title]').nth(10)
    chosen = day.get_attribute('title')
    assert chosen
    day.click()
    expect(dialog.get_by_label(field_name, exact=True)).to_have_value(chosen)
    expect(popup).to_have_count(0)


def test_oilcard_transfer_and_manual_invoice_calendars(server, browser_page):
    page, _ = browser_page
    open_page(page, server, 'oilcard', '油卡管理')
    page.get_by_role('tab', name='充值与发票', exact=True).click()
    for action, field_name in [('转账', '转账日期'), ('手动增行', '手工登记日期或原标记')]:
        page.get_by_role('button', name=action, exact=True).click()
        dialog = page.get_by_role('dialog', name=action, exact=True)
        select_oilcard_calendar_date(page, dialog, field_name)
        dialog.get_by_role('button', name='取消', exact=True).click()
        page.get_by_role('button', name='放弃并关闭', exact=True).click()
        expect(dialog).not_to_be_visible()


def test_contract_grid_caret_and_party_select_keep_control_keys(server, browser_page, api):
    page, _ = browser_page
    row, label = contract_sample(api)
    open_page(page, server, 'contracts', '集采台账')
    if row['tag'] != '纳入台账':
        pick_option(page, '纳入状态', '全部')
    page.get_by_role('textbox', name='搜索', exact=True).fill(label)
    field = page.get_by_label(label + ' 账期', exact=True)
    field.fill('12')
    field.press('ArrowLeft')
    page.keyboard.insert_text('3')
    expect(field).to_have_value('132')
    # Avoid committing the edit when moving on to the other table.
    page.reload()
    page.route('**/api/m11/party-kinds', lambda route: route.fulfill(json={
        'items': [{'name': '测试甲方', 'kind': 'a', 'kind_name': '测试分类甲', 'count': 1}],
        'kinds': ['a', 'b'],
        'kind_names': {'a': '测试分类甲', 'b': '测试分类乙'},
    }))
    page.get_by_role('button', name='甲方单位分类', exact=True).click()
    dialog = page.get_by_role('dialog', name='甲方单位分类', exact=True)
    picker = dialog.get_by_role('combobox', name='测试甲方分类', exact=True)
    picker.click()
    expect(picker).to_have_attribute('aria-expanded', 'true')
    picker.press('ArrowDown')
    expect(picker).to_have_attribute('aria-activedescendant', re.compile(r'.+'))
    picker.press('Enter')
    expect(picker).to_have_attribute('aria-expanded', 'false')
    expect(dialog.get_by_title('测试分类乙', exact=True)).to_be_visible()


def test_inventory_period_popup_closes_when_leaving_page(server, browser_page):
    page, _ = browser_page
    open_page(page, server, 'inventory', '库存单据与调整单')
    page.get_by_role('button', name=re.compile(r'^库存核算期间')).click()
    popup = page.get_by_role('dialog', name='库存核算期间选择', exact=True)
    expect(popup).to_be_visible()
    page.get_by_role('link', name='首页', exact=True).click()
    expect(popup).not_to_be_visible()


def test_real_unsaved_dialog_confirms_discard_and_keeps_input(server,browser_page):
    page,_=browser_page;login(page,server)
    page.get_by_role('button',name='＋ 手工建档',exact=True).click();dialog=page.get_by_role('dialog')
    textbox=dialog.get_by_role('textbox').first;textbox.fill('未保存输入')
    dialog.press('Escape');expect(dialog.get_by_role('heading',name='放弃未保存的修改？')).to_be_visible()
    dialog.get_by_role('button',name='继续编辑',exact=True).click();expect(textbox).to_have_value('未保存输入')
    dialog.press('Escape');dialog.get_by_role('button',name='放弃并关闭',exact=True).click();expect(dialog).not_to_be_visible()


def test_real_history_confirmation_cancel_undo_redo_and_changed_head(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,side,row,_=ledger_sample(api,projects,editable=True)
    def write_remark(text):
        current=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
        actual=next(r for item in current['sides'] if item['category']==side['category'] for r in item['rows'] if r['record_id']==row['record_id'] and r['month']==row['month'])
        result=api.post('/api/m05/history/save',json={'id':actual['record_id'],'project_id':project['id'],'category':side['category'],'entry_kind':actual['row_kind'],'cutoff_ym':actual['month'],'settle_amount':actual['other_expense'],'paid_amount':actual['payment'],'remark':text,'token':actual['token']})
        assert result.json()['ok']
    def current_remark():
        data=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
        return next(r['remark'] for item in data['sides'] if item['category']==side['category'] for r in item['rows'] if r['record_id']==row['record_id'] and r['month']==row['month'])
    original=current_remark();changed=original+'核验历史';write_remark(changed)
    head=get(api,'/api/history/status')['undo'];assert head
    login(page,server);sent=[];page.on('request',lambda r:sent.append(r) if r.url.endswith('/api/history/undo') else None)
    page.get_by_role('button',name='撤销',exact=True).click();dialog=page.get_by_role('dialog',name='确认撤销？',exact=True)
    expect(dialog).to_contain_text(head['label']);dialog.get_by_role('button',name='取消',exact=True).click();assert not sent
    page.get_by_role('button',name='撤销',exact=True).click();dialog.get_by_role('button',name='确认撤销',exact=True).click()
    expect(page.locator('.history-tools [role=status]')).to_contain_text('已撤销');assert len(sent)==1
    assert current_remark()==original
    page.get_by_role('button',name='重做',exact=True).click();redo=page.get_by_role('dialog',name='确认重做？',exact=True);expect(redo).to_contain_text(head['label']);redo.get_by_role('button',name='确认重做',exact=True).click()
    expect(page.locator('.history-tools [role=status]')).to_contain_text('已重做')
    page.get_by_role('button',name='撤销',exact=True).click();write_remark(changed+'后续')
    dialog.get_by_role('button',name='确认撤销',exact=True).click();expect(page.locator('.history-tools [role=status]')).to_contain_text('历史已变化');assert len(sent)==1
