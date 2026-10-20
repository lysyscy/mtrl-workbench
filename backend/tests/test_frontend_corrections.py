"""Approved density, grouped totals and real i8 preview comparisons use isolated UI data."""
from tests.ui_helpers import ui_page  # noqa: F401


def test_project_full_name_uses_one_line_without_scrollbars(ui_page):
    p=ui_page
    p.evaluate("() => {PJs[0].full='工程项目全名'.repeat(30);VIEW='m01';render();}")
    field=p.locator('input.project-full').first
    assert field.input_value() == '工程项目全名'*30
    assert field.get_attribute('title') == '工程项目全名'*30
    assert p.locator('textarea.project-full').count() == 0
    assert field.bounding_box()['height'] < 36


def test_i8_preview_computes_exact_changes_and_preserves_confirmation(ui_page):
    p=ui_page
    p.evaluate("""() => {
      window.preview={preview_id:'isolated',counts:{usage:3,project:2,team:2},projects:[
        {warehouse:'测试仓库',complete:true,reduction:true,before:{totals:{usage:'9007199254740993.12',project:'100.00',team:'2.00'}},totals:{usage:'9007199254740993.13',project:'98.80',team:'2.00'}},
        {warehouse:'新项目',complete:true,before:{},totals:{usage:'12.00',project:'10.00',team:'9.00'}},
        {warehouse:'不完整项目',complete:false,before:{totals:{usage:'30.00'}},totals:{usage:'20.00',project:null,team:null}},
        {warehouse:'来源变化项目',complete:true,changed:true,before:{totals:{usage:'10.00',project:'8.00',team:'8.00'}},totals:{usage:'10.00',project:'8.00',team:'8.00'}}]};
      mwI8Review(preview,'测试仓库');
    }""")
    modal=p.locator('.modal')
    assert modal.bounding_box()['width'] > 1200
    assert '+0.01' in modal.inner_text() and '−1.20' in modal.inner_text()
    assert '首次取得' in modal.inner_text() and '待核实' in modal.inner_text()
    assert '单据有变化' in modal.inner_text()
    assert p.locator('[data-mw-i8="0"]').is_checked()
    assert not p.locator('[data-mw-i8="1"]').is_checked()
    assert p.locator('[data-mw-i8="2"]').is_disabled()
    p.locator('#mw-i8-reduction').check()
    p.locator('#mw-i8-reason').fill('核实单据范围后采用')
    p.evaluate("""async () => {
      window.sent=[];mwPost=async(path,data)=>{sent.push([path,data]);return {ok:true};};
      mwRefresh=async()=>{};await ACT.mwI8Confirm();
    }""")
    assert p.evaluate('sent[0]') == ['i8-confirm',{'preview_id':'isolated','warehouses':['测试仓库'],
        'allow_reduction':True,'reduction_reason':'核实单据范围后采用'}]
