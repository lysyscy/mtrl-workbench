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
            elif row['material_editable']:
                if row[key] is None:expect(cell.locator('input')).to_have_value('')
                else:assert Decimal(cell.locator('input').input_value())==Decimal(str(row[key]))
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
    page,_=browser_page;project,matrix=sample(api,projects);mechanical=get(api,'/api/m06/mech');sources=mechanical['sources'];found=None
    for row in matrix['adjusted']:
        keys=[i for i in range(6) if sources.get(project['warehouse_name'],{}).get(row['ym'],{}).get('mech_'+str(i),{}).get('mode')!='detail']
        if len(keys)>=2:found=(row,keys[:2]);break
    assert found,'真实副本缺少两个手填机械格，该交互未覆盖'
    row,keys=found;open_page(page,server,'process','过程资料');pick_option(page,'过程资料项目',project['disp'])
    first=page.get_by_label(row['ym']+' '+LABELS[keys[0]],exact=True);second=page.get_by_label(row['ym']+' '+LABELS[keys[1]],exact=True)
    pending=[];page.route('**/api/m06/mech-cell',lambda route:pending.append(route) if route.request.method=='POST' else route.continue_())
    value=Decimal(str(row['mech_'+str(keys[0])] or 0))+Decimal('1.25');first.fill(str(value));first.blur()
    if row['ym'] in mechanical['detail_signatures'].get(project['warehouse_name'],{}):
        dialog=page.get_by_role('dialog',name='确认保存机械费',exact=True)
        expect(dialog).to_be_visible();dialog.get_by_role('button',name='取消',exact=True).click()
        assert not pending
        expect(first).to_have_value(str(value));first.focus();first.blur()
        dialog.get_by_role('button',name='确认保存',exact=True).click()
    second.fill('2.50');assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok;route.fulfill(response=response)
    expect(first.locator('..').locator('small')).to_have_count(0);expect(second).to_have_value('2.50')
    fresh=get(api,'/api/m06/mech');assert Decimal(str(fresh['mech'][project['warehouse_name']][row['ym']][keys[0]]))==value


def test_history_material_save_readback_keeps_next_draft(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,matrix=sample(api,projects)
    used={row['ym'] for row in matrix['adjusted']}
    ym=next(f'{year}-{month:02}' for year in range(2025,1999,-1) for month in range(1,13)
            if f'{year}-{month:02}' <= '2025-11' and f'{year}-{month:02}' not in used)
    open_page(page,server,'process','过程资料');pick_option(page,'过程资料项目',project['disp'])
    page.get_by_label('增加历史月份',exact=True).fill(ym)
    page.get_by_role('button',name='增加月份',exact=True).click()
    first=page.get_by_label(ym+' 入库主辅材',exact=True);second=page.get_by_label(ym+' 出库工具',exact=True)
    pending=[]
    page.route('**/api/m06/material',lambda route:pending.append(route))
    first.fill('-12.34');first.blur();second.fill('22.50');assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok;route.fulfill(response=response)
    expect(first.locator('..').locator('small')).to_have_count(0)
    expect(second).to_have_value('22.50')
    page.unroute('**/api/m06/material');second.press('Enter')
    expect(second.locator('..').locator('small')).to_have_count(0)
    fresh=get(api,'/api/m06/matrix')['matrices'][project['warehouse_name']]
    for kind in ('raw','adjusted'):
        row=next(row for row in fresh[kind] if row['ym']==ym)
        assert Decimal(str(row['in_主辅材']))==Decimal('-12.34')
        assert Decimal(str(row['out_工具']))==Decimal('22.50')


def test_difference_first_visible_frame_has_final_geometry(server,browser_page,api,projects):
    page,_=browser_page;data=get(api,'/api/m06/matrix')
    project=next(p for p in projects if p['warehouse_name'] in data['matrices'] and not data['matrices'][p['warehouse_name']]['diffs'])
    page.set_viewport_size({'width':2560,'height':1080})
    page.add_init_script("""window.__nativeFrames=[];function nativeFrame(){
      const e=document.querySelector('.process-matrix'),card=document.querySelector('.process-page');
      if(e?.checkVisibility({checkVisibilityCSS:true})&&window.__nativeFrames.length<30)
        window.__nativeFrames.push(JSON.stringify({table:e.offsetWidth,card:card.offsetWidth,
          widths:[...e.querySelectorAll('tbody tr:first-child > th,tbody tr:first-child > td')].map(c=>c.getBoundingClientRect().width)}));
      if(window.__nativeFrames.length<30)requestAnimationFrame(nativeFrame);}nativeFrame();""")
    open_page(page,server,'process','过程资料')
    page.wait_for_function('window.__nativeFrames.length>=30')
    native=page.evaluate('window.__nativeFrames')
    assert len(set(native))==1,native
    page.set_viewport_size({'width':1280,'height':720})
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
    assert len(frames[0]['widths'])==12,frames
    assert len({str(frame) for frame in frames})==1,frames
