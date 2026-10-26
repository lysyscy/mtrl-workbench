"""Real settlement totals and annual extract scope."""
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get,open_page,grid_row,money
from preview_select import pick_option


def test_real_settlement_row_amounts_and_natural_height(server,browser_page,api):
    page,_=browser_page;data=get(api,'/api/m07/settlement')
    assert data['rows'],'真实副本没有收发结存，行与金额接线未覆盖'
    open_page(page,server,'settlement','收发结存与提取')
    field=page.get_by_label('收发结存核算月',exact=True);field.fill(data['ym']);field.press('Enter')
    row=data['rows'][0];dom=grid_row(page,'.settlement-grid',row['id'])
    for key in ['begin','in','out','end']:expect(dom.locator('[col-id="'+key+'"]')).to_have_text(money(row[key]))
    assert page.locator('.settlement-grid .ag-root-wrapper').evaluate('e=>e.getBoundingClientRect().height>0')


def test_real_extract_annual_rows_follow_status(server,browser_page,api):
    page,_=browser_page;open_page(page,server,'settlement','收发结存与提取')
    page.get_by_text('焊材 / 气体提取',exact=True).click()
    field=page.get_by_label('提取年份',exact=True);year=field.input_value()
    pick_option(page,'提取项目状态','全部')
    data=get(api,'/api/m07/extract',year=year,status='全部')
    for kind in ['焊材','气体']:
        grid=page.get_by_role('region',name=kind+'年度汇总',exact=True)
        expect(grid).to_be_visible()
        rows=data['annual'][kind]['rows']
        if rows:
            row=rows[0];dom=grid.locator('[row-id]').filter(has=page.get_by_text(row['warehouse'],exact=True)).first
            expect(dom).to_contain_text(row['warehouse'])
            expect(dom.locator('[col-id="total"]')).to_have_text(money(row['total']))
