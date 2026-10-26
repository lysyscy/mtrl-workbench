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
