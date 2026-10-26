"""Real inventory local filter and original amount identity."""
import re
from decimal import Decimal
from playwright.sync_api import expect
from test_preview import server,browser_page
from preview_select import pick_option
from live_data import get,open_page,grid_row,money


def test_real_inventory_filter_is_local_and_keeps_amounts(server,browser_page,api):
    page,_=browser_page;data=get(api,'/api/m08/inventory');assert data['rows']
    row=data['rows'][0];open_page(page,server,'inventory','库存单据与调整单')
    page.get_by_role('button',name='库存核算期间',exact=True).click()
    panel=page.get_by_role('dialog',name='库存核算期间选择',exact=True);panel.get_by_text('全部',exact=True).click()
    page.keyboard.press('Escape')
    page.get_by_role('button',name=re.compile('^列筛选')).click()
    pick_option(page,'筛选列','物料')
    requests=[];page.on('request',lambda r:requests.append(r.url) if '/api/m08/inventory' in r.url else None)
    page.get_by_label('列包含文字',exact=True).fill(row['material'])
    expect(grid_row(page,'.inventory-grid',row['id'])).to_be_visible()
    assert not requests
    expect(page.get_by_role('button',name='导出文件…',exact=True)).to_be_disabled()
    expect(page.get_by_text('导出请选择单月',exact=True)).to_be_visible()


def test_actual_inventory_adjustment_save_readback_and_revoke(server,browser_page,api,disposable):
    page,_=browser_page;data=get(api,'/api/m08/inventory');row=next(r for r in data['rows'] if not r['adjusted'])
    open_page(page,server,'inventory','库存单据与调整单')
    page.get_by_role('button',name='库存核算期间',exact=True).click();page.get_by_role('dialog',name='库存核算期间选择',exact=True).get_by_text('全部',exact=True).click();page.keyboard.press('Escape')
    page.get_by_role('button',name=re.compile('^列筛选')).click();pick_option(page,'筛选列','物料');page.get_by_label('列包含文字',exact=True).fill(row['material'])
    dom=grid_row(page,'.inventory-grid',row['id']);dom.get_by_role('button',name='办理调整',exact=True).click()
    dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
    value=Decimal(row['amount'])+Decimal('1.25');dialog.get_by_label('调整后金额',exact=True).fill(str(value));dialog.get_by_label('调整备注',exact=True).fill('核对原行调整接线')
    dialog.get_by_role('button',name='保存调整单',exact=True).click();expect(dialog.get_by_role('status').filter(has_text='调整单已保存')).to_be_visible()
    after=get(api,'/api/m08/inventory');actual=next(r for r in after['rows'] if r['id']==row['id']);adjustment=next(a for a in after['adjustments'] if a['row_id']==row['id'])
    assert actual['amount']==row['amount'] and Decimal(actual['adj_amount'])==value and Decimal(adjustment['amount'])==value
    dialog.get_by_role('button',name='撤销调整单…',exact=True).click();dialog.get_by_role('button',name='确认撤销调整单',exact=True).click();expect(dialog).not_to_be_visible()
    restored=get(api,'/api/m08/inventory');assert next(r for r in restored['rows'] if r['id']==row['id'])==row
    assert not any(a['row_id']==row['id'] for a in restored['adjustments'])


def test_known_inventory_rows_keep_scroll_extent(server,browser_page,api):
    """Known long rows must not change the scrollbar extent as virtual windows mount."""
    page,_=browser_page;data=get(api,'/api/m08/inventory');assert data['rows']
    open_page(page,server,'inventory','库存单据与调整单')
    grid=page.locator('.inventory-grid')
    expect(grid).to_have_attribute('aria-busy','false')
    page.get_by_role('button',name='库存核算期间',exact=True).click()
    page.get_by_role('dialog',name='库存核算期间选择',exact=True).get_by_text('全部',exact=True).click();page.keyboard.press('Escape')
    expect(page.locator('.inventory-count-feedback')).to_have_text(f"{len(data['rows'])} / {len(data['rows'])} 行")
    expect(grid).to_have_attribute('aria-busy','false',timeout=30000)
    viewport=grid.locator('.ag-grid-viewport,.ag-body-viewport').first
    extent=viewport.evaluate('e=>e.scrollHeight')
    for fraction in [.25,.5,.75,1,0]:
        viewport.evaluate("""async(e,f)=>{e.scrollTop=(e.scrollHeight-e.clientHeight)*f;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));}""",fraction)
        assert viewport.evaluate('e=>e.scrollHeight')==extent
        assert grid.locator('.inventory-cell-text').evaluate_all("""els=>els.every(e=>{const c=e.closest('.ag-cell');return e.getBoundingClientRect().height<=c.clientHeight+1})""")
        assert grid.locator('.ag-cell.money').evaluate_all('els=>els.every(e=>e.scrollWidth<=e.clientWidth+1)')
    # Re-entering the same compressed row model must not compound native rounding.
    viewport.evaluate("async e=>{e.scrollTop=(e.scrollHeight-e.clientHeight)*.5;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));}")
    anchor = """e=>{const box=e.getBoundingClientRect(),row=[...e.querySelectorAll('.ag-row[row-id]')].find(r=>r.getBoundingClientRect().top>=box.top&&r.getBoundingClientRect().top<box.bottom);return [row?.getAttribute('row-id'),row?.getBoundingClientRect().top-box.top]}"""
    before_anchor=viewport.evaluate(anchor)
    for _ in range(3):
        page.get_by_role('link',name='项目档案',exact=True).click()
        page.get_by_role('link',name='库存单据与调整单',exact=True).click()
        expect(grid).to_be_visible();expect(grid).to_have_attribute('aria-busy','false',timeout=30000)
        page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        after_anchor=viewport.evaluate(anchor)
        assert after_anchor[0]==before_anchor[0] and abs(after_anchor[1]-before_anchor[1])<=1
    # A manual width survives a local filter and its reset.
    header=grid.locator('.ag-header-cell[col-id=material]')
    before=header.evaluate('e=>e.getBoundingClientRect().width')
    handle=header.locator('.ag-header-cell-resize').bounding_box();assert handle
    page.mouse.move(handle['x']+handle['width']/2,handle['y']+handle['height']/2);page.mouse.down();page.mouse.move(handle['x']+handle['width']/2+40,handle['y']+handle['height']/2,steps=4);page.mouse.up()
    expect(grid).to_have_attribute('aria-busy','false',timeout=30000)
    resized=header.evaluate('e=>e.getBoundingClientRect().width');assert resized>before+20
    pick_option(page,'库存方向','入库');expect(grid).to_have_attribute('aria-busy','false',timeout=30000)
    pick_option(page,'库存方向','全部');expect(grid).to_have_attribute('aria-busy','false',timeout=30000)
    assert abs(header.evaluate('e=>e.getBoundingClientRect().width')-resized)<1
