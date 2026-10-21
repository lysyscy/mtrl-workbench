"""The six reported tables fit a readable viewport and retain a narrow-screen boundary."""
import pytest

from tests.ui_helpers import ui_page  # noqa: F401


@pytest.mark.parametrize('kind', ['notice', 'flows', 'process', 'weld', 'inventory', 'procurement'])
@pytest.mark.parametrize('scale,viewport', [(1.12, 2320), (1.25, 2552)])
def test_report_tables_fit_resize_without_clipping(ui_page, kind, scale, viewport):
    p = ui_page
    p.set_viewport_size({'width': viewport, 'height': 1100})
    p.evaluate("scale=>document.documentElement.style.setProperty('--fscale',scale)", scale)
    p.evaluate('''kind=>{
      const specs={
        notice:{cls:'notice-table',key:'m03:notices',head:NT_THEAD,n:18,nums:[10,11,12,13,14],inputs:[11,13,14]},
        flows:{cls:'flow-table',key:'m05:flows',head:FL_THEAD,n:14,nums:[6,8]},
        process:{cls:'process-matrix',n:17,nums:Array.from({length:16},(_,i)=>i+1),min:'min-width:2100px'},
        weld:{key:'m07:kinds',head:extHead(),n:16,nums:Array.from({length:14},(_,i)=>i+2),min:'min-width:1800px'},
        inventory:{key:'m08:invoices',n:20,nums:[8,9,10,11,12,13]},
        procurement:{cls:'procurement-table',n:20,nums:[6,7,9,10,11,12,13,14]},
      };
      const s=specs[kind],head=s.head||Array.from({length:s.n},(_,i)=>`<th>列 ${i+1}</th>`).join('');
      const row='<tr>'+Array.from({length:s.n},(_,i)=>{
        if(s.nums.includes(i)) return `<td class="num">${s.inputs?.includes(i)?'<input class="inp num" value="12345678.90">':['process','weld'].includes(kind)?'123,456.78':'12,345,678.90'}</td>`;
        if(i===s.n-1) return '<td class="ctr now"><button class="btn sm">不纳入</button> <button class="btn sm">推进存档</button></td>';
        return `<td${i<2?' class="fl"':''}>${kind==='process'?'2026-10':'项目及单据名称'}</td>`;
      }).join('')+'</tr>';
      document.querySelector('#view').innerHTML='<div class="tw">'+TBL({cls:s.cls,key:s.key,head,rows:[row,row],sty:s.min||''})+'</div>';
      layoutTables();
    }''', kind)
    table = p.locator('#view table')
    assert 'fit-wide' in table.get_attribute('class'), kind
    for width in [viewport, viewport+480, viewport]:
        p.set_viewport_size({'width': width, 'height': 1100})
        p.evaluate('layoutTables()')
        geometry = table.evaluate('''t=>({width:t.getBoundingClientRect().width,
          host:t.closest('.tw').clientWidth,scroll:t.closest('.tw').scrollWidth,
          clipped:[...t.querySelectorAll('td.num,input.num,td.ctr.now')].filter(e=>e.scrollWidth>e.clientWidth+1).length})''')
        assert abs(geometry['width'] - geometry['host']) < 2, (kind, width, geometry)
        assert geometry['scroll'] <= geometry['host'] + 1, (kind, width, geometry)
        assert geometry['clipped'] == 0, (kind, width, geometry)
    p.set_viewport_size({'width': 1024, 'height': 1000})
    p.evaluate('layoutTables()')
    assert table.evaluate('t=>t.closest(".tw").scrollWidth>t.closest(".tw").clientWidth+1'), kind
