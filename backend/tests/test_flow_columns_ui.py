"""Long document codes stay in their column after the flow number is removed."""
from tests.ui_helpers import ui_page  # noqa: F401
from tests.test_shell_ui_workflow import FL0
from tools.audit.workspace_paths import output


def test_flow_code_dates_amount_and_total_keep_their_columns(ui_page):
    p = ui_page
    p.evaluate('''f=>{
      FLs.splice(0,FLs.length,adaptFlow({...f,doc_no:'FKTZS2026102112345678901234567890',
        pay_date:bjMonth()+'-15',doc_date:'2026-09-30'}));
      VIEW='m05';flf.ym='全部';flf.state='全部';render();
    }''', FL0)
    p.evaluate('document.fonts.ready')
    for width, scale in [(2320,1.12),(1024,1.25),(2320,1.12)]:
        p.set_viewport_size({'width':width,'height':1100})
        p.evaluate("scale=>{document.documentElement.style.setProperty('--fscale',scale);layoutTables();}",scale)
        t = p.locator('table[data-sort-key="m05:flows"]')
        assert t.locator('thead tr').last.locator('th').count() == 14
        assert '流水号' not in t.locator('thead').inner_text()
        geometry = t.evaluate('''t=>{
          const row=t.querySelector('tr[data-flow-id]'), cells=[...row.cells];
          const code=cells[0].querySelector('button').getBoundingClientRect();
          return {clipped:[cells[1],cells[6],cells[7],cells[8]].filter(e=>e.scrollWidth>e.clientWidth+1).length,
            codeRight:code.right,cellRight:cells[0].getBoundingClientRect().right,
            sumLeft:t.querySelector('tr.sumrow td.num').getBoundingClientRect().left,
            amountLeft:cells[8].getBoundingClientRect().left};
        }''')
        assert geometry['clipped'] == 0, geometry
        assert geometry['codeRight'] <= geometry['cellRight']+1, geometry
        assert abs(geometry['sumLeft']-geometry['amountLeft']) < 1, geometry
    p.screenshot(path=str(output('flow-columns.png',kind='screenshots')))
