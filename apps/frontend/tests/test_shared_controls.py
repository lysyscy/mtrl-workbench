"""Real dirty-dialog lifecycle and real operation-head confirmation."""
from playwright.sync_api import expect
from test_preview import server,browser_page,login
from live_data import get,ledger_sample


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
