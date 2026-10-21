"""Payment layout and scroll regressions; all API writes are intercepted."""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.ui_helpers import ui_page  # noqa: F401


@pytest.mark.parametrize('width,scale', [(1920, 1), (1280, 1.4)])
def test_dates_and_inventory_identity_stay_inside_their_columns(ui_page, width, scale):
    p = ui_page
    p.set_viewport_size({'width': width, 'height': 1080})
    p.evaluate('''scale=>{
      document.documentElement.style.setProperty('--fscale',scale);
      Object.assign(NO[0],{date:'2026-10-21',code:'FKTZS2026101521'});render();
    }''', scale)
    date = p.locator('.notice-table tbody tr[data-notice-id="101"] td').nth(1)
    assert date.evaluate('e=>e.scrollWidth<=e.clientWidth+1')
    p.evaluate('''()=>{
      document.querySelector('#view').innerHTML='<div class="tw">'+TBL({key:'m08:invoices',
        head:Array.from({length:20},(_,i)=>'<th>列'+i+'</th>').join(''),
        rows:['<tr>'+Array.from({length:20},(_,i)=>i===0?'<td class="fl now">RKD20261021000123456789</td>':
          i<3?'<td class="now">2026-10-21</td>':'<td>测试内容</td>').join('')+'</tr>']})+'</div>';
      layoutTables();
    }''')
    assert p.locator('tbody td.now').evaluate_all('cells=>cells.every(e=>e.scrollWidth<=e.clientWidth+1)')


@pytest.mark.parametrize('count', [70, 450])
def test_ledger_starts_at_bottom_and_history_save_keeps_both_tables(ui_page, count):
    p = ui_page
    p.set_viewport_size({'width': 1024 if count == 70 else 1920, 'height': 1080})
    p.evaluate('''count=>{
      document.documentElement.style.setProperty('--fscale',count===70?1.4:1);
      VIEW='m05';ledProj='测试仓库';
      M05.ledger={project_id:1,sides:['辅材','机械'].map((label,side)=>({label,rows:
        Array.from({length:count},(_,i)=>({seq:i+1,month:'2025-11',
          row_kind:side?'month':'manual',record_id:side?null:i+1,editable:true,token:'original',
          other_expense:'100',payment:'20',remark:'历史记录'+i}))}))};
      reloadM05=async()=>{Object.keys(LOADERS).forEach(x=>LOADED.add(x));render();};
      render();
    }''', count)
    positions = '''()=>[...document.querySelectorAll('.debt-ledger .tw')].map(e=>({
      top:e.scrollTop,left:e.scrollLeft,max:e.scrollHeight-e.clientHeight}))'''
    initial = p.evaluate(positions)
    assert all(x['max'] > 500 and abs(x['top'] - x['max']) <= 2 for x in initial), initial
    p.evaluate('''()=>{
      document.querySelectorAll('.debt-ledger .tw').forEach((e,i)=>{e.scrollTop=600+i*300;e.scrollLeft=40;});
    }''')
    p.wait_for_timeout(80)
    fields = p.locator('[data-sc="辅材"][data-field="paid_amount"]')
    field = fields.nth(16) if count == 70 else fields.first
    field.scroll_into_view_if_needed()
    field.fill('10.00')
    before = p.evaluate(positions)
    assert all(x['top'] > 0 for x in before), before
    if count == 70:
        assert any(x['left'] > 0 for x in before), before
    view_top = p.locator('#view').evaluate('e=>e.scrollTop')
    writes = []
    p.route('**/api/m05/history/save', lambda r: (writes.append(r.request.post_data_json), r.fulfill(json={'ok': True})))
    # Blur saves without Tab scrolling horizontally to the next editor first.
    field.evaluate('e=>e.blur()')
    expect(p.locator('.toast').last).to_contain_text('台账已保存')
    after = p.evaluate(positions)
    assert writes[0]['paid_amount'] == '10.00' and writes[0]['token'] == 'original'
    assert all(abs(a['top'] - b['top']) <= 2 and abs(a['left'] - b['left']) <= 2 for a, b in zip(after, before)), (before, after)
    assert abs(p.locator('#view').evaluate('e=>e.scrollTop') - view_top) <= 2
    p.evaluate("PJs.push({...PJs[0],id:'2',name:'另一仓库'});ledProj='另一仓库';render()")
    assert all(abs(x['top'] - x['max']) <= 2 for x in p.evaluate(positions))
    p.evaluate("go('home');go('m05')")
    assert all(abs(x['top'] - x['max']) <= 2 for x in p.evaluate(positions))


def test_search_batches_typing_and_does_not_redraw_after_leaving(ui_page):
    p = ui_page
    p.evaluate('''()=>{
      const original=render;window.searchRenderCount=0;
      render=function(){searchRenderCount++;return original.apply(this,arguments);};
      const input=document.querySelector('#ntSearch');
      for(const q of ['D','DO','DOC']){input.value=q;input.dispatchEvent(new Event('input',{bubbles:true}));}
    }''')
    p.wait_for_function('searchRenderCount===1')
    assert p.locator('#ntSearch').input_value() == 'DOC'
    p.evaluate('''()=>{
      const input=document.querySelector('#ntSearch');input.value='D';
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true}));
      input.value='材料';input.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true}));
    }''')
    p.wait_for_timeout(180)
    assert p.evaluate('searchRenderCount') == 1
    p.evaluate('''()=>{
      const input=document.querySelector('#ntSearch');
      input.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'材料'}));
      input.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:false}));
    }''')
    p.wait_for_function('searchRenderCount===2')
    assert p.locator('#ntSearch').input_value() == '材料'
    p.locator('#ntSearch').fill('不存在')
    p.evaluate("go('home');window.afterLeaveCount=searchRenderCount")
    p.wait_for_timeout(200)
    assert p.evaluate("VIEW==='home'&&searchRenderCount===afterLeaveCount")


@pytest.mark.parametrize('width,scale', [(1920, 1), (1920, 1.4), (1280, 1), (1280, 1.4)])
def test_live_page_headers_and_filters_fit_the_viewport(ui_page, width, scale):
    p = ui_page
    p.set_viewport_size({'width': width, 'height': 1080 if width == 1920 else 720})
    p.evaluate("scale=>document.documentElement.style.setProperty('--fscale',scale)", scale)
    routes = p.evaluate('NAV.flatMap(g=>g.items.map(item=>item[0]))')
    for route in routes:
        p.evaluate('route=>{VIEW=route;render();}', route)
        problems = p.locator('#view').evaluate('''view=>[view,...view.querySelectorAll('.card>h4,.fbar')]
          .filter(e=>e.scrollWidth>e.clientWidth+2).map(e=>({tag:e.className,text:e.textContent.slice(0,100),
            width:e.clientWidth,scroll:e.scrollWidth}))''')
        assert problems == [], (route, width, scale, problems)
        if (output := os.environ.get('MTRL_UI_EVIDENCE_PATH')) and route in ('m03', 'm05', 'm07', 'm08'):
            folder = Path(output)
            folder.mkdir(parents=True, exist_ok=True)
            p.screenshot(path=str(folder / f'{route}-{width}-{scale}.png'))


def test_notice_search_profile(ui_page):
    """Keep a reproducible measurement, without a machine-dependent timing gate."""
    p = ui_page
    p.evaluate('''()=>{
      const sample=NO[0];NO=Array.from({length:1200},(_,i)=>({...sample,id:String(1000+i),
        code:'FKTZS202610'+String(i).padStart(4,'0'),paidApi:0}));render();
    }''')
    results = p.evaluate('''()=>Array.from({length:3},()=>{
      fNt.q='FKTZS';const start=performance.now();ntHit(fNt);const filtered=performance.now();
      const html=V.m03();const generated=performance.now();applySorts(html,'m03');const sorted=performance.now();
      render();const rendered=performance.now();document.querySelector('#view').getBoundingClientRect();
      return {filter:filtered-start,html:generated-filtered,sort:sorted-generated,render:rendered-sorted,
        layout:performance.now()-rendered};
    })''')
    print('SEARCH_PROFILE ' + json.dumps(results))
    assert p.evaluate('ntHit(fNt).length') == 1200
    if output := os.environ.get('MTRL_UI_EVIDENCE_PATH'):
        folder = Path(output)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'search-profile.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
