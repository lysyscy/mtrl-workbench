"""Editable manual settlement reaches the API; rejected drafts remain intact."""
from playwright.sync_api import expect
from tests.ui_helpers import ui_page  # noqa: F401


def test_manual_settlement_default_cap_payload_and_edit(ui_page):
    p = ui_page
    p.evaluate('''()=>{
      BOOTING=false;m05Sync=()=>{};
      window.manualCalls=[];
      API.manualSave=async b=>{manualCalls.push(b);return {ok:false,message:'隔离拒绝'};};
      reloadNotices=async()=>render();
    }''')
    p.locator('[data-act="ntRowAdd"]').click()
    draft = p.locator('tr.draftrow')
    expect(draft.locator('[data-k="ss"]')).to_have_value('0')
    draft.locator('[data-k="approve"]').fill('20000')
    draft.locator('[data-k="ss"]').fill('20000.01')
    draft.locator('[data-act="ntRowSave"]').click()
    assert p.evaluate('manualCalls.length') == 0
    expect(draft.locator('[data-k="ss"]')).to_have_value('20000.01')
    draft.locator('[data-k="ss"]').fill('20000')
    draft.locator('[data-k="sp"]').fill('20000')
    draft.locator('[data-act="ntRowSave"]').click()
    p.wait_for_function('manualCalls.length===1 && !ntSaving')
    assert p.evaluate('manualCalls[0].stat_settle') == '20000'
    expect(draft.locator('[data-k="ss"]')).to_have_value('20000')
    draft.locator('[data-act="ntRowCancel"]').click()
    p.evaluate("Object.assign(NO[0],{manual:true,ss:20000,sp:20000,approve:20000});render();")
    expect(p.locator('[data-act="editss"][data-k="ss"]').first).to_have_value('20000.00')
    p.locator('[data-act="ntEdit"]').click()
    expect(draft.locator('[data-k="ss"]')).to_have_value('20000')
    draft.locator('[data-act="ntRowSave"]').click()
    p.wait_for_function('manualCalls.length===2 && !ntSaving')
    assert p.evaluate('manualCalls[1].stat_settle') == '20000'
    draft.locator('[data-act="ntRowCancel"]').click()
    approval = p.locator('[data-act="editApprove"]').first
    approval.fill('19999')
    approval.press('Tab')
    assert p.evaluate('manualCalls.length') == 2
    approval.fill('25000')
    approval.press('Tab')
    p.wait_for_function('manualCalls.length===3 && !ntSaving')
    assert p.evaluate('manualCalls[2].amount_approved') == '25000'
    assert p.evaluate('manualCalls[2].stat_settle') == '20000'
