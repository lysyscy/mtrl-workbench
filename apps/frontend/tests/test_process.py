"""Real process matrix mapping and existing manual mechanical cell save."""
from decimal import Decimal
import re
from playwright.sync_api import expect
from preview_select import pick_option, pick_popup_option
from test_preview import server,browser_page
from live_data import get,open_page,money

LABELS=['租分公司设备','内租设备','外租零租含税','外租包月含税','外租零租不含税','外租包月不含税']
KEYS=[d+'_'+name for d in ['in','out'] for name in ['主辅材','工具','劳保','周转材料','临时设施']]+['mech_'+str(i) for i in range(6)]


def saved(field):
    expect(field.locator('..')).not_to_have_class(re.compile(r'.*\bprocess-dirty\b.*'))


def replace_amount(field,value):
    # Focus changes display text to raw digits. Replace after that native focus,
    # as a reader does by clicking the field before selecting its text.
    field.click();field.fill(value)


def test_real_process_enter_saves_without_clicking_elsewhere(server,browser_page,api,projects,disposable):
    data=get(api,'/api/m06/matrix');mechanical=get(api,'/api/m06/mech')
    candidates=[(project,data['matrices'][project['warehouse_name']]['adjusted'][0])
        for project in projects if project['warehouse_name'] in data['matrices']
        and data['matrices'][project['warehouse_name']]['adjusted']
        and data['matrices'][project['warehouse_name']]['adjusted'][0]['ym']
        not in mechanical['detail_signatures'].get(project['warehouse_name'],{})]
    assert candidates,'真实副本没有不需明细确认的过程机械格'
    project,row=candidates[0];page,_=browser_page
    open_page(page,server,'process','过程资料');pick_option(page,'过程资料项目',project['disp'])
    field=page.get_by_label(row['ym']+' '+LABELS[0],exact=True)
    value=Decimal(str(row['mech_0'] or 0))+Decimal('1.25')
    replace_amount(field,str(value));field.press('Enter')
    saved(field)
    expect(field.locator('..').locator('small')).to_have_count(0)
    expect(field).to_have_value(money(value))
    fresh=get(api,'/api/m06/mech')['effective_values'][project['warehouse_name']][row['ym']]
    assert Decimal(fresh['mech_0'])==value


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
        table=page.get_by_role('region',name=f'{label}，金额单位：元',exact=True)
        dom=table.locator('.ag-row[row-id="'+row['ym']+'"]').first
        expect(dom).to_be_visible()
        for index,key in enumerate(KEYS):
            cell=dom.locator('[col-id="'+key+'"]').first;expected='' if row[key] is None else money(row[key])
            if key.startswith('mech_'):
                if cell.locator('input').count():
                    if row[key] is None:expect(cell.locator('input')).to_have_value('')
                    else:expect(cell.locator('input')).to_have_value(money(row[key]))
                else:expect(cell.locator('.process-cell>span')).to_have_text(expected)
            elif row['material_editable']:
                if row[key] is None:expect(cell.locator('input')).to_have_value('')
                else:expect(cell.locator('input')).to_have_value(money(row[key]))
            else:expect(cell).to_have_text(expected)
            expect(table.locator('.ag-row[row-id="合计"] [col-id="'+key+'"]').first).to_have_text('' if matrix['totals'][kind][key] is None else money(matrix['totals'][kind][key]))
        for index,segment in enumerate(matrix['segments'][kind]):
            key=KEYS[[0,5,10,14][index]]
            expect(table.locator('.ag-row[row-id="总求和（本表）"] [col-id="'+key+'"]').first).to_contain_text('' if segment['total'] is None else money(segment['total']))


def test_real_process_grouped_header_stays_visible(server,browser_page,api,projects):
    page,_=browser_page;data=get(api,'/api/m06/matrix')
    candidates=[(p,data['matrices'][p['warehouse_name']]) for p in projects if p['status']=='active' and p['warehouse_name'] in data['matrices']]
    project,matrix=max(candidates,key=lambda pair:len(pair[1]['adjusted']))
    assert matrix['adjusted'],'真实副本没有过程月份，表头滚动保护未覆盖'
    page.set_viewport_size({'width':1761,'height':720});open_page(page,server,'process','过程资料')
    control=page.get_by_label('过程资料项目',exact=True);control.click();control.fill(project['disp']);pick_popup_option(page,project['disp'])
    table=page.locator('.process-matrix');expect(table.locator('.ag-header-row').first).to_be_visible()
    region=page.get_by_role('region',name='过程资料月度表，可横向滚动',exact=True)
    viewport=table.locator('.ag-body-vertical-scroll-viewport')
    expect(table).to_have_attribute('data-layout-state','ready')
    assert viewport.evaluate('e=>e.scrollHeight>e.clientHeight'),'表区未形成纵向滚动，置顶未覆盖'
    before=table.locator('.ag-header').bounding_box()
    viewport.evaluate('e=>e.scrollTop=e.scrollHeight')
    expect(table.locator('.ag-row[row-id="'+matrix['adjusted'][-1]['ym']+'"]').first).to_be_visible()
    after=table.locator('.ag-header').bounding_box()
    assert viewport.evaluate('e=>e.scrollTop')>0
    assert abs(before['y']-after['y'])<1
    expect(table.get_by_role('columnheader',name='入库',exact=True)).to_be_visible()
    expect(table.get_by_role('columnheader',name='出库',exact=True)).to_be_visible()
    expect(table.get_by_role('columnheader',name='外租包月不含税',exact=True)).to_be_visible()


def test_complete_process_input_value_is_readable(server,browser_page,api,projects):
    page,_=browser_page;project,matrix=sample(api,projects)
    candidates=[(index,key,str(row[key])) for index,row in enumerate(matrix['adjusted']) for key in KEYS
                if row[key] is not None and (key.startswith('mech_') or row['material_editable'])]
    assert candidates,'真实副本没有金额输入，此可见性保护未覆盖'
    index,key,value=max(candidates,key=lambda item:len(item[2]))
    row=matrix['adjusted'][index];label=LABELS[int(key[5:])] if key.startswith('mech_') else ('入库' if key.startswith('in_') else '出库')+key.split('_',1)[1]
    open_page(page,server,'process','过程资料');pick_option(page,'过程资料项目',project['disp'])
    grid=page.locator('.process-matrix');expect(grid).to_have_attribute('data-layout-state','ready')
    grid.locator('.ag-body-vertical-scroll-viewport').evaluate('(e,fraction)=>e.scrollTop=(e.scrollHeight-e.clientHeight)*fraction',index/max(1,len(matrix['adjusted'])-1))
    field=grid.get_by_label(row['ym']+' '+label,exact=True)
    expect(field).to_be_visible();expect(field).to_have_value(money(value))
    assert field.evaluate('e=>e.scrollWidth<=e.clientWidth'),'完整金额须在输入框内直接读出'
    field.focus();expect(field).to_have_value(value)
    field.blur();expect(field).to_have_value(money(value))


def test_real_process_cell_write_and_later_draft(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,matrix=sample(api,projects);mechanical=get(api,'/api/m06/mech');sources=mechanical['sources'];found=None
    for row in matrix['adjusted']:
        keys=[i for i in range(6) if sources.get(project['warehouse_name'],{}).get(row['ym'],{}).get('mech_'+str(i),{}).get('mode')!='detail']
        if len(keys)>=2:found=(row,keys[:2]);break
    assert found,'真实副本缺少两个手填机械格，该交互未覆盖'
    row,keys=found;open_page(page,server,'process','过程资料');control=page.get_by_label('过程资料项目',exact=True);control.click();control.fill(project['disp']);pick_popup_option(page,project['disp'])
    first=page.get_by_label(row['ym']+' '+LABELS[keys[0]],exact=True);second=page.get_by_label(row['ym']+' '+LABELS[keys[1]],exact=True)
    pending=[];page.route('**/api/m06/mech-cell',lambda route:pending.append(route) if route.request.method=='POST' else route.continue_())
    value=Decimal(str(row['mech_'+str(keys[0])] or 0))+Decimal('1.25')
    with page.expect_request('**/api/m06/mech-cell'):
        replace_amount(first,str(value));first.blur()
        if row['ym'] in mechanical['detail_signatures'].get(project['warehouse_name'],{}):
            dialog=page.get_by_role('dialog',name='确认保存机械费',exact=True)
            expect(dialog).to_be_visible();dialog.get_by_role('button',name='取消',exact=True).click()
            assert not pending
            expect(first).to_have_value(money(value));first.focus();first.blur()
            dialog.get_by_role('button',name='确认保存',exact=True).click()
    replace_amount(second,'2.50');assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok;route.fulfill(response=response)
    saved(first);expect(first.locator('..').locator('small')).to_have_count(0);expect(second).to_have_value('2.50')
    fresh=get(api,'/api/m06/mech');assert Decimal(str(fresh['mech'][project['warehouse_name']][row['ym']][keys[0]]))==value


def test_history_material_save_readback_keeps_next_draft(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,matrix=sample(api,projects)
    used={row['ym'] for row in matrix['adjusted']}
    ym=next(f'{year}-{month:02}' for year in range(2025,1999,-1) for month in range(1,13)
            if f'{year}-{month:02}' <= '2025-11' and f'{year}-{month:02}' not in used)
    open_page(page,server,'process','过程资料');control=page.get_by_label('过程资料项目',exact=True);control.click();control.fill(project['disp']);pick_popup_option(page,project['disp'])
    page.get_by_label('增加历史月份',exact=True).fill(ym)
    page.get_by_role('button',name='增加月份',exact=True).click()
    first=page.get_by_label(ym+' 入库主辅材',exact=True);second=page.get_by_label(ym+' 出库工具',exact=True)
    pending=[]
    page.route('**/api/m06/material',lambda route:pending.append(route))
    replace_amount(first,'-12.34');first.blur();replace_amount(second,'22.50');assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok;route.fulfill(response=response)
    saved(first)
    expect(first.locator('..').locator('small')).to_have_count(0)
    expect(second).to_have_value('22.50')
    page.unroute('**/api/m06/material');second.press('Enter')
    saved(second)
    expect(second.locator('..').locator('small')).to_have_count(0)
    fresh=get(api,'/api/m06/matrix')['matrices'][project['warehouse_name']]
    for kind in ('raw','adjusted'):
        row=next(row for row in fresh[kind] if row['ym']==ym)
        assert Decimal(str(row['in_主辅材']))==Decimal('-12.34')
        assert Decimal(str(row['out_工具']))==Decimal('22.50')


def test_history_failure_keeps_draft_other_cell_saves_and_blank_differs_from_zero(server,browser_page,api,projects,disposable,preview_screenshot):
    page,_=browser_page;project,matrix=sample(api,projects)
    used={row['ym'] for row in matrix['adjusted']}
    ym=next(f'{year}-{month:02}' for year in range(2025,1999,-1) for month in range(1,13)
            if f'{year}-{month:02}'<='2025-11' and f'{year}-{month:02}' not in used)
    open_page(page,server,'process','过程资料');pick_option(page,'过程资料项目',project['disp'])
    page.get_by_label('增加历史月份',exact=True).fill(ym)
    page.get_by_role('button',name='增加月份',exact=True).click()
    bad=page.get_by_label(ym+' 入库主辅材',exact=True)
    good=page.get_by_label(ym+' 出库工具',exact=True)
    replace_amount(bad,'abc');bad.blur()
    failure=bad.locator('..').get_by_role('alert')
    expect(failure).to_be_visible();expect(bad).to_have_value('abc')
    cell=bad.locator('xpath=ancestor::div[contains(@class,"ag-cell")][1]')
    page.wait_for_function('selector=>{const c=document.querySelector(selector),error=c?.querySelector(".process-cell-error");return error&&error.getBoundingClientRect().bottom<=c.getBoundingClientRect().bottom+1}',arg=f'.process-matrix .ag-row[row-id="{ym}"] [col-id="in_主辅材"]')
    assert failure.bounding_box()['y']+failure.bounding_box()['height']<=cell.bounding_box()['y']+cell.bounding_box()['height']+1
    expect(failure.get_by_role('button',name='重试',exact=True)).to_be_enabled()
    with page.expect_response('**/api/m06/material') as response:
        failure.get_by_role('button',name='重试',exact=True).click()
    assert not response.value.ok
    expect(failure).to_be_visible();expect(bad).to_have_value('abc')
    replace_amount(good,'12345.6');good.press('Enter')
    saved(good)
    expect(good).to_have_value('12,345.60')
    expect(failure).to_be_visible();expect(bad).to_have_value('abc')
    matrix=get(api,'/api/m06/matrix')['matrices'][project['warehouse_name']]
    for kind in ('raw','adjusted'):
        row=next(row for row in matrix[kind] if row['ym']==ym)
        assert Decimal(str(row['out_工具']))==Decimal('12345.60')
        assert row['in_主辅材'] is None
    preview_screenshot('process-failed-cell-and-saved-neighbor')
    good.focus();expect(good).to_have_value(str(row['out_工具']))
    good.blur();box=good.bounding_box()
    offset=good.evaluate('e=>{const s=getComputedStyle(e),c=document.createElement("canvas").getContext("2d");c.font=s.font;return parseFloat(s.paddingRight)+c.measureText("45.60").width}')
    page.mouse.click(box['x']+box['width']-offset,box['y']+box['height']/2)
    cursor=good.evaluate('e=>e.selectionStart');raw=good.input_value()
    assert 0<cursor<len(raw),'鼠标点金额中部后，输入位置应仍在中部'
    good.press('9');expect(good).to_have_value(raw[:cursor]+'9'+raw[cursor:])
    replace_amount(good,'');good.press('Enter');saved(good);expect(good).to_have_value('')
    replace_amount(bad,'0');bad.press('Enter');saved(bad);expect(bad).to_have_value('0.00');expect(failure).to_have_count(0)
    mech=page.get_by_label(ym+' '+LABELS[0],exact=True)
    replace_amount(mech,'0');mech.press('Enter');saved(mech);expect(mech).to_have_value('0.00')
    assert Decimal(get(api,'/api/m06/mech')['effective_values'][project['warehouse_name']][ym]['mech_0'])==0
    replace_amount(mech,'');mech.press('Enter');saved(mech);expect(mech).to_have_value('')
    assert get(api,'/api/m06/mech')['effective_values'][project['warehouse_name']][ym]['mech_0'] is None
    matrix=get(api,'/api/m06/matrix')['matrices'][project['warehouse_name']]
    for kind in ('raw','adjusted'):
        row=next(row for row in matrix[kind] if row['ym']==ym)
        assert row['out_工具'] is None and row['mech_0'] is None
        assert Decimal(str(row['in_主辅材']))==0
    expect(page.locator('.ant-message-notice')).to_have_count(0)


def test_process_unknown_receipt_keeps_submission_context_and_never_retries_itself(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,matrix=sample(api,projects)
    used={row['ym'] for row in matrix['adjusted']}
    ym=next(f'{year}-{month:02}' for year in range(2025,1999,-1) for month in range(1,13)
            if f'{year}-{month:02}'<='2025-11' and f'{year}-{month:02}' not in used)
    open_page(page,server,'process','过程资料');pick_option(page,'过程资料项目',project['disp'])
    page.get_by_label('增加历史月份',exact=True).fill(ym)
    page.get_by_role('button',name='增加月份',exact=True).click()
    writes=[]
    def lose_receipt(route):
        response=route.fetch();assert response.ok
        writes.append(route.request.post_data_json);route.abort('failed')
    page.route('**/api/m06/material',lose_receipt)
    field=page.get_by_label(ym+' 入库主辅材',exact=True)
    replace_amount(field,'789.12');field.press('Enter')
    panel=page.locator('.process-uncertain')
    expect(panel).to_contain_text('保存结果待核实')
    expect(panel).to_contain_text(project['disp']+'，'+ym+' 入库主辅材')
    expect(field).not_to_be_editable()
    other=next(p for p in projects if p['warehouse_name']!=project['warehouse_name'] and p['warehouse_name'] in get(api,'/api/m06/matrix')['matrices'])
    control=page.get_by_label('过程资料项目',exact=True);control.click();control.fill(other['disp']);pick_popup_option(page,other['disp'])
    expect(panel).to_contain_text(project['disp']+'，'+ym+' 入库主辅材')
    page.get_by_role('button',name='重新核对',exact=True).click()
    resume=page.get_by_role('button',name='已核对，保留输入继续',exact=True)
    expect(resume).to_be_enabled();resume.click();expect(panel).to_have_count(0)
    control.click();control.fill(project['disp']);pick_popup_option(page,project['disp'])
    saved(field);field.focus();field.blur();page.wait_for_load_state('networkidle')
    expect(panel).to_have_count(0)
    assert len(writes)==1
    row=next(row for row in get(api,'/api/m06/matrix')['matrices'][project['warehouse_name']]['adjusted'] if row['ym']==ym)
    assert Decimal(str(row['in_主辅材']))==Decimal('789.12')


def test_unknown_receipt_does_not_rebase_a_later_draft_over_another_write(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,matrix=sample(api,projects)
    used={row['ym'] for row in matrix['adjusted']}
    ym=next(f'{year}-{month:02}' for year in range(2025,1999,-1) for month in range(1,13)
            if f'{year}-{month:02}'<='2025-11' and f'{year}-{month:02}' not in used)
    open_page(page,server,'process','过程资料');pick_option(page,'过程资料项目',project['disp'])
    page.get_by_label('增加历史月份',exact=True).fill(ym)
    page.get_by_role('button',name='增加月份',exact=True).click()
    field=page.get_by_label(ym+' 入库主辅材',exact=True);held=[]
    page.route('**/api/m06/material',lambda route:held.append(route))
    with page.expect_request('**/api/m06/material'):
        replace_amount(field,'100.00');field.press('Enter')
    replace_amount(field,'200.00')
    assert len(held)==1
    route=held.pop();response=route.fetch();assert response.ok;route.abort('failed')
    panel=page.locator('.process-uncertain');expect(panel).to_contain_text('本次输入：100.00')
    page.unroute('**/api/m06/material')
    response=api.post('/api/m06/material',json={'warehouse':project['warehouse_name'],'ym':ym,'column':'in_主辅材','value':'300.00','expected':'100.00'})
    assert response.is_success
    page.get_by_role('button',name='重新核对',exact=True).click()
    resume=page.get_by_role('button',name='已核对，保留输入继续',exact=True)
    expect(resume).to_be_enabled();resume.click()
    with page.expect_response('**/api/m06/material') as response:
        field.focus();field.blur()
    assert not response.value.ok
    expect(field).to_have_value('200.00')
    expect(field.locator('..').get_by_role('alert')).to_contain_text('其他操作')
    row=next(row for row in get(api,'/api/m06/matrix')['matrices'][project['warehouse_name']]['adjusted'] if row['ym']==ym)
    assert Decimal(str(row['in_主辅材']))==Decimal('300.00')


def test_difference_first_visible_frame_has_final_geometry(server,browser_page,api,projects):
    page,_=browser_page;data=get(api,'/api/m06/matrix')
    project=next(p for p in projects if p['warehouse_name'] in data['matrices'] and not data['matrices'][p['warehouse_name']]['diffs'])
    page.set_viewport_size({'width':2560,'height':1080})
    page.add_init_script("""window.__nativeFrames=[];function nativeFrame(){
      const e=document.querySelector('.process-matrix'),card=document.querySelector('.process-page');
      if(e?.checkVisibility({checkVisibilityCSS:true})&&window.__nativeFrames.length<30)
        window.__nativeFrames.push(JSON.stringify({table:e.offsetWidth,card:card.offsetWidth,
          widths:[...e.querySelectorAll('.ag-header-cell')].map(c=>c.getBoundingClientRect().width)}));
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
