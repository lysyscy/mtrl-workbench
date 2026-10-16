"""㉛ 通知书空态与正常数据往返；仅浏览器内隔离样本，不写数据库。"""
from _shell_common import goto

def check(page, errors):
    goto(page,'m03')
    saved=page.evaluate("() => ({rows:NO.slice(),filter:JSON.parse(JSON.stringify(fNt))})")
    try:
        page.evaluate("() => {fNt.q='__isolated_no_notice_match__';render();}")
        page.wait_for_function("document.querySelector('#view').innerText.includes('当前筛选条件下没有付款通知书')")
        ok_empty=page.locator('#view tbody tr[data-notice-id]').count()==0
        if not ok_empty:errors.append('㉛ 通知书空态仍有数据行')
        page.evaluate("""() => {
          if(!NO.length)NO.push({id:'probe-empty-normal',date:bjMonth()+'-01',code:'PROBE',proj:'',cat:'辅材',astat:'已批',approve:10,pay:10,ss:10,sp:0,excl:false});
          fNt={month:'全部',cat:'全部',astat:'全部',stat:'全部',projs:[],q:''};render();
        }""")
        page.wait_for_function("document.querySelectorAll('#view tbody tr[data-notice-id]').length>0")
        if '合计' not in page.inner_text('#view'):errors.append('㉛ 通知书正常路合计不见了')
    finally:
        page.evaluate("s => {NO=s.rows;fNt=s.filter;render();}",saved)
