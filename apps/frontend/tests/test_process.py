"""Real process matrix mapping and existing manual mechanical cell save."""
from decimal import Decimal
from playwright.sync_api import expect
from preview_select import pick_option, pick_popup_option
from test_preview import server,browser_page
from live_data import get,open_page,money

LABELS=['租分公司设备','内租设备','外租零租含税','外租包月含税','外租零租不含税','外租包月不含税']
KEYS=[d+'_'+name for d in ['in','out'] for name in ['主辅材','工具','劳保','周转材料','临时设施']]+['mech_'+str(i) for i in range(6)]


def sample(api,projects):
    data=get(api,'/api/m06/matrix')
    for project in projects:
        matrix=data['matrices'].get(project['warehouse_name'])
        if project['status']=='active' and matrix and matrix['adjusted']:return project,matrix
    raise AssertionError('真实副本没有过程矩阵，行及合计保护未覆盖')


def test_real_process_raw_adjusted_rows_and_totals(server,browser_page,api,projects):
    page,_=browser_page;project,matrix=sample(api,projects);open_page(page,server,'process','过程资料')
    control=page.get_by_label('过程资料项目',exact=True);control.click();control.fill(project['disp'])
    pick_popup_option(page,project['disp'])
    for label,kind in [('表② 调整后表','adjusted'),('表① 原始表','raw')]:
        page.get_by_text(label,exact=True).click();row=matrix[kind][0]
        table=page.get_by_role('table',name=f'{label}，金额单位：元',exact=True)
        dom=table.locator('tbody tr').filter(has=page.get_by_role('rowheader',name=row['ym'],exact=True)).first
        expect(dom).to_be_visible()
        for index,key in enumerate(KEYS):
            cell=dom.locator('td').nth(index);expected='' if row[key] is None else money(row[key])
            if key.startswith('mech_'):
                if cell.locator('input').count():
                    if row[key] is None:expect(cell.locator('input')).to_have_value('')
                    else:assert Decimal(cell.locator('input').input_value())==Decimal(str(row[key]))
                else:expect(cell.locator('.process-cell>span')).to_have_text(expected)
            else:expect(cell).to_have_text(expected)
            expect(table.locator('tfoot tr').first.locator('td').nth(index)).to_have_text('' if matrix['totals'][kind][key] is None else money(matrix['totals'][kind][key]))
        for index,segment in enumerate(matrix['segments'][kind]):
            expect(table.locator('tfoot tr').last.locator('td').nth(index)).to_contain_text('' if segment['total'] is None else money(segment['total']))


def test_real_process_grouped_header_stays_visible(server,browser_page,api,projects):
    page,_=browser_page;data=get(api,'/api/m06/matrix')
    candidates=[(p,data['matrices'][p['warehouse_name']]) for p in projects if p['status']=='active' and p['warehouse_name'] in data['matrices']]
    project,matrix=max(candidates,key=lambda pair:len(pair[1]['adjusted']))
    assert matrix['adjusted'],'真实副本没有过程月份，表头滚动保护未覆盖'
    page.set_viewport_size({'width':1761,'height':720});open_page(page,server,'process','过程资料')
    control=page.get_by_label('过程资料项目',exact=True);control.click();control.fill(project['disp']);pick_popup_option(page,project['disp'])
    table=page.locator('.process-matrix');expect(table.locator('thead tr')).to_have_count(2)
    region=page.get_by_role('region',name='过程资料月度表，可横向滚动',exact=True)
    assert region.evaluate('e=>e.scrollHeight>e.clientHeight'),'表区未形成纵向滚动，置顶未覆盖'
    before=table.locator('thead').bounding_box()
    table.locator('tbody tr').last.scroll_into_view_if_needed()
    after=table.locator('thead').bounding_box()
    assert region.evaluate('e=>e.scrollTop')>0
    assert abs(before['y']-after['y'])<1
    expect(table.get_by_role('columnheader',name='入库',exact=True)).to_be_visible()
    expect(table.get_by_role('columnheader',name='出库',exact=True)).to_be_visible()
    expect(table.get_by_role('columnheader',name='外租包月不含税',exact=True)).to_be_visible()


def test_real_process_cell_write_and_later_draft(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,matrix=sample(api,projects);sources=get(api,'/api/m06/mech')['sources'];found=None
    for row in matrix['adjusted']:
        keys=[i for i in range(6) if sources.get(project['warehouse_name'],{}).get(row['ym'],{}).get('mech_'+str(i),{}).get('mode')!='detail']
        if len(keys)>=2:found=(row,keys[:2]);break
    assert found,'真实副本缺少两个手填机械格，该交互未覆盖'
    row,keys=found;open_page(page,server,'process','过程资料');pick_option(page,'过程资料项目',project['disp'])
    first=page.get_by_label(row['ym']+' '+LABELS[keys[0]],exact=True);second=page.get_by_label(row['ym']+' '+LABELS[keys[1]],exact=True)
    pending=[];page.route('**/api/m06/mech',lambda route:pending.append(route) if route.request.method=='POST' else route.continue_())
    value=Decimal(str(row['mech_'+str(keys[0])] or 0))+Decimal('1.25');first.fill(str(value));first.blur();second.fill('2.50');assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok;route.fulfill(response=response)
    expect(page.get_by_role('status').filter(has_text=LABELS[keys[0]]+'已保存')).to_be_visible();expect(second).to_have_value('2.50')
    fresh=get(api,'/api/m06/mech');assert Decimal(str(fresh['mech'][project['warehouse_name']][row['ym']][keys[0]]))==value


def test_difference_first_visible_frame_has_final_geometry(server,browser_page,api,projects):
    page,_=browser_page;data=get(api,'/api/m06/matrix')
    project=next(p for p in projects if p['warehouse_name'] in data['matrices'] and not data['matrices'][p['warehouse_name']]['diffs'])
    page.set_viewport_size({'width':1280,'height':720})
    open_page(page,server,'process','过程资料')
    pick_option(page,'过程资料项目',project['disp'])
    page.evaluate("""window.__differenceFrames=[];
      function sample(){const e=document.querySelector('.process-grid');
        if(e&&e.checkVisibility({checkVisibilityCSS:true}))window.__differenceFrames.push({
          height:e.offsetHeight,header:e.querySelector('.ag-header')?.offsetHeight,
          widths:[...e.querySelectorAll('.ag-header-cell')].map(c=>c.offsetWidth)});
        if(window.__differenceFrames.length<30)requestAnimationFrame(sample);}sample();""")
    page.locator('.process-tabs label').filter(has_text='差异表').click()
    page.wait_for_function('window.__differenceFrames.length>=30')
    frames=page.evaluate('window.__differenceFrames')
    assert len(frames[0]['widths'])==11,frames
    assert len({str(frame) for frame in frames})==1,frames
