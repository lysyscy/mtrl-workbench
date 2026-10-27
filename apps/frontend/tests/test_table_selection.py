"""Native text selection and mouse focus on actual copied table rows."""
import re
import pytest
from playwright.sync_api import expect
from test_preview import server, browser_page, login


@pytest.mark.parametrize('route,title,grid', [
    ('contracts','集采台账','.contracts-grid'),
    ('inventory','库存单据与调整单','.inventory-grid'),
    ('mechanical','机械费','.mechanical-grid'),
    ('fees','特殊费用','.fees-grid'),
    ('big','月度会大表','.big-month:not([hidden]) .big-grid'),
    ('settlement','收发结存与提取','.settlement-grid'),
])
def test_native_table_text_can_be_selected(server,browser_page,route,title,grid):
    page,_=browser_page
    login(page,server)
    page.get_by_role('link',name=title,exact=True).click()
    cells=page.locator(grid+' .ag-row:not(.ag-row-pinned) .ag-cell:not(:has(input,button,a,select,textarea,[role=checkbox]))')
    cell=cells.filter(has_text=re.compile(r'\S')).first
    expect(cell).to_be_visible()
    cell.scroll_into_view_if_needed()
    rect=cell.evaluate("""e=>{const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);while(w.nextNode()){if(w.currentNode.textContent.trim()){const r=document.createRange();r.selectNodeContents(w.currentNode);const b=r.getBoundingClientRect();return {left:b.left,right:b.right,y:b.top+b.height/2}}}throw Error('No actual text')}""")
    page.mouse.move(rect['left']-1,rect['y'])
    page.mouse.down()
    page.mouse.move(rect['right']+1,rect['y'],steps=8)
    page.mouse.up()
    selected=page.evaluate("window.getSelection()?.toString().trim()")
    assert selected and selected in cell.inner_text(), {'selected':selected,'cell':cell.inner_text(),'select':cell.evaluate('e=>getComputedStyle(e).userSelect')}
    assert page.evaluate("document.queryCommandEnabled('copy')"), 'The browser has no native copy range'


def test_contract_mouse_click_has_no_grid_ring(server,browser_page):
    page,_=browser_page
    login(page,server)
    page.get_by_role('link',name='集采台账',exact=True).click()
    cell=page.locator('.contracts-grid .ag-row:not(.ag-row-pinned) .ag-cell[col-id=contract_no]').first
    expect(cell).to_be_visible();cell.click()
    assert cell.evaluate("e=>getComputedStyle(e).borderTopColor")=='rgba(0, 0, 0, 0)'
