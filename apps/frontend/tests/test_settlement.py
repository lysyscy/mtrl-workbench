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


def test_annual_first_visible_geometry_is_final_readonly(server,browser_page):
    """Retained-page tab entry must not paint default widths before the final layout."""
    page,context=browser_page
    writes=[]
    def readonly(route):
        if route.request.method not in {'GET','HEAD','OPTIONS'} and '/m15/login' not in route.request.url:
            writes.append(route.request.url);route.abort('blockedbyclient')
        else:route.continue_()
    context.route('**/*',readonly)
    open_page(page,server,'settlement','收发结存与提取')
    page.evaluate("""window.__annualFrames={};function frame(){
      for(const section of document.querySelectorAll('.settlement-annual')){
        const grid=section.querySelector('.annual-grid');
        if(!grid?.checkVisibility({checkVisibilityCSS:true}) || grid.closest('[hidden]') || !grid.querySelector('.ag-row[row-id]'))continue;
        const columns=[...grid.querySelectorAll('.ag-header-cell')].map(c=>[c.getAttribute('col-id'),c.getBoundingClientRect().width,c.getBoundingClientRect().height]);
        const rows=[...grid.querySelectorAll('.ag-row[row-id]')].map(r=>[r.getAttribute('row-id'),r.getBoundingClientRect().height]);
        (window.__annualFrames[section.getAttribute('aria-label')]??=[]).push(JSON.stringify({columns,rows,height:grid.getBoundingClientRect().height}));
      } window.__annualFrame=requestAnimationFrame(frame);
    }requestAnimationFrame(frame);""")
    page.get_by_text('焊材 / 气体提取',exact=True).click()
    page.wait_for_function("Object.keys(window.__annualFrames).length===2 && Object.values(window.__annualFrames).every(frames=>frames.length>=30)")
    samples=page.evaluate('window.__annualFrames')
    page.evaluate('cancelAnimationFrame(window.__annualFrame)')
    assert all(len(set(frames))==1 for frames in samples.values()), samples
    assert not writes,writes
