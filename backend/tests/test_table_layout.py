"""真实显隐、缩放和虚拟滚动走同一布局收尾，断言最终列几何。"""
import pytest
from playwright.sync_api import expect

from app.mod03_notice.page import render_theme
from tests.ui_helpers import ui_page  # noqa: F401
from tests.test_tail301_columns import _load
from tools.audit.workspace_paths import output


def check_geometry(p):
    geometry = p.locator('table[data-sort-key="m11:jc"]').evaluate("""table=>{
      const heads=[...table.tHead.rows[0].cells];
      const cells=[...table.tBodies[0].rows].find(r=>!r.classList.contains('vsp')).cells;
      let left=0;
      return heads.slice(0,4).map((head,i)=>{
        const result={header:parseFloat(head.style.left)||0,cell:parseFloat(cells[i].style.left)||0,
          expected:left};left+=head.getBoundingClientRect().width;return result;
      });
    }""")
    for item in geometry:
        assert abs(item['header'] - item['expected']) < 0.6, geometry
        assert abs(item['cell'] - item['expected']) < 0.6, geometry
    trace = p.evaluate('layoutTrace')
    assert trace and len(trace) % 3 == 0, trace
    assert trace == ['hide', 'fit', 'pin'] * (len(trace) // 3), trace


@pytest.mark.parametrize('count', [30, 450])
@pytest.mark.parametrize('scale', [1, 1.25])
def test_布局收尾覆盖重画显隐缩放及虚拟窗口(ui_page, count, scale):
    p = ui_page
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate("scale=>document.documentElement.style.setProperty('--fscale',scale)", scale)
    p.evaluate('document.fonts.ready')
    _load(p, 'base')
    p.evaluate("""count=>{
      const row=JCs[0];JCs.splice(0,JCs.length,...Array.from({length:count},(_,i)=>({...row,id:String(i+1)})));
      window.layoutTrace=[];
      const hide=jcApplyHide,fit=fitWideTable,pin=jcApplyPin;
      jcApplyHide=()=>{layoutTrace.push('hide');hide();};
      fitWideTable=table=>{if(table.dataset.sortKey==='m11:jc')layoutTrace.push('fit');fit(table);};
      jcApplyPin=()=>{layoutTrace.push('pin');pin();};render();
    }""", count)
    check_geometry(p)
    p.evaluate('layoutTrace.length=0;')
    p.locator('#jcTradeBtn').click()
    expect(p.locator('#jcTradeBtn')).to_contain_text('隐藏贸易公司列')
    check_geometry(p)
    p.evaluate('layoutTrace.length=0;')
    p.set_viewport_size({'width': 1120, 'height': 800})
    p.wait_for_function('layoutTrace.includes("pin")')
    check_geometry(p)
    if count > 400:
        p.evaluate('layoutTrace.length=0;')
        p.locator('table[data-sort-key="m11:jc"]').evaluate("""table=>{
          const tw=table.closest('.tw');window.layoutScrollHost=tw;
          tw.scrollTop=3000;tw.dispatchEvent(new Event('scroll'));
        }""")
        p.wait_for_function('VS_TS.some(x=>x.a>0) && layoutTrace.includes("pin")')
        assert p.evaluate('document.contains(layoutScrollHost)')
        check_geometry(p)
        p.screenshot(path=str(output('table-layout-virtual.png', kind='screenshots')))
