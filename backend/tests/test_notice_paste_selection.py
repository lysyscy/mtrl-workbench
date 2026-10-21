"""Pasted bill numbers select only unique active records; manual picks stay put."""
import pytest
from tests.ui_helpers import ui_page  # noqa: F401
from tests.test_tail309_notice_selection import _setup as _base_setup, _ids, _pick


def _setup(p):
    _base_setup(p)
    p.evaluate("async () => {SRV.forEach((n,i)=>n.bill_no='FKTZS202610'+String(101+i).padStart(4,'0'));await reloadNotices();}")


def rows(p):
    return p.locator('tr[data-notice-id]').evaluate_all('(rs)=>rs.map(r=>r.dataset.noticeId)')


def paste(p,text):
    p.click('[data-act="ntPasteOpen"]')
    p.fill('#ntPasteInput',text)
    p.click('[data-act="ntPasteApply"]')
    p.locator('.modal h3').filter(has_text='单据号勾选结果').wait_for()


def test_paste_exact_codes_refresh_all_projects_report_conflicts_and_never_print(ui_page):
    p=ui_page
    _setup(p)
    p.evaluate("""() => {
      SRV.push({...SRV[2],notice_id:106}, {...SRV[0],notice_id:107,bill_no:'QTZC2026100107',amount_paid:'1000'});
      window.requests=[];
      API.m03Batch=async b=>{requests.push(b);return {ok:true};};
      fNt.projs=['测试仓库']; fNt.month='2025-01';fNt.stat='未付清';fNt.q='old';render();
    }""")
    paste(p,'fktzs2026100102\r\nFKTZS2026100101\tFKTZS2026100101, FKTZS2026109999；FKTZS2026100103\nFKTZS2026100104\nFKTZS2026100105\nQTZC2026100107')
    assert _ids(p)==['101','102','107']
    result=p.inner_text('.modal .mb')
    for text in ['未找到','FKTZS2026109999','系统重号','FKTZS2026100103','已剔除','已撤单','重复输入','已付清，仍可打印']:
        assert text in result
    assert p.evaluate('requests')==[]
    p.get_by_role('button',name='完成',exact=True).click()
    assert set(rows(p)[:3])=={'101','102','107'}
    assert p.evaluate('fNt.projs')==[] and p.evaluate('fNt.month')=='全部'
    assert p.locator('[data-act="ntPrint"]').is_enabled()


def test_manual_picks_and_unpicks_keep_positions_only_pasted_batch_is_grouped(ui_page):
    p=ui_page
    _setup(p)
    before=rows(p)
    _pick(p,'103').check()
    assert rows(p)==before
    paste(p,'FKTZS2026100102')
    p.get_by_role('button',name='完成',exact=True).click()
    assert rows(p)==['102','101','103']
    _pick(p,'103').check()
    assert rows(p)==['102','101','103']
    _pick(p,'102').uncheck()
    assert rows(p)==['102','101','103']
    p.get_by_role('button',name='单据编码↕',exact=True).click()
    assert rows(p)==['102','101','103']
    p.get_by_role('button',name='单据编码▲',exact=True).click()
    assert rows(p)==['102','103','101']


def test_empty_or_unmatched_paste_preserves_selection_and_input_for_correction(ui_page):
    p=ui_page
    _setup(p)
    _pick(p,'103').check()
    p.click('[data-act="ntPasteOpen"]')
    p.click('[data-act="ntPasteApply"]')
    assert '请先粘贴' in p.inner_text('#ntPasteError')
    assert _ids(p)==['103']
    p.fill('#ntPasteInput','FKTZS2026109999')
    p.click('[data-act="ntPasteApply"]')
    p.locator('.modal h3').filter(has_text='单据号勾选结果').wait_for()
    assert _ids(p)==['103']
    assert '原勾选保持不变' in p.inner_text('.modal .mb')
    p.get_by_role('button',name='修改清单',exact=True).click()
    assert p.input_value('#ntPasteInput')=='FKTZS2026109999'


def test_read_failure_or_closed_dialog_does_not_apply_stale_selection(ui_page):
    p=ui_page
    _setup(p)
    _pick(p,'103').check()
    p.evaluate("() => {API.notices=async()=>{throw Error('隔离读取失败');};}")
    p.click('[data-act="ntPasteOpen"]')
    p.fill('#ntPasteInput','FKTZS2026100102')
    p.click('[data-act="ntPasteApply"]')
    assert '隔离读取失败' in p.inner_text('#ntPasteError')
    assert _ids(p)==['103']
    p.evaluate('() => {API.notices=()=>new Promise(resolve=>window.finishPaste=resolve);}')
    p.click('[data-act="ntPasteApply"]')
    p.get_by_role('button',name='取消',exact=True).click()
    p.evaluate('finishPaste({items:SRV})')
    p.wait_for_function('!ntPasteBusy')
    assert _ids(p)==['103']


def test_paste_group_reaches_top_of_virtual_table_without_manual_scroll_jumps(ui_page):
    p=ui_page
    _setup(p)
    p.evaluate("""async () => {
      SRV=Array.from({length:550},(_,i)=>({...SRV[0],notice_id:1000+i,bill_no:'FKTZS202610'+(1000+i)}));
      await reloadNotices();
    }""")
    p.evaluate('scrollHost().scrollTop=6500')
    p.wait_for_function('scrollHost().scrollTop>1000')
    paste(p,'FKTZS2026101549\nFKTZS2026101500')
    p.get_by_role('button',name='完成',exact=True).click()
    p.wait_for_function('scrollHost().scrollTop===0')
    assert set(rows(p)[:2])=={'1549','1500'}
    p.evaluate('scrollHost().scrollTop=5000')
    p.wait_for_function('scrollHost().scrollTop>1000')
    p.wait_for_function("[...document.querySelectorAll('[data-act=pick]:not(:checked)')].some(e=>{const r=e.getBoundingClientRect();return r.top>200&&r.bottom<innerHeight;})")
    notice_id=p.evaluate("[...document.querySelectorAll('[data-act=pick]:not(:checked)')].find(e=>{const r=e.getBoundingClientRect();return r.top>200&&r.bottom<innerHeight;}).dataset.id")
    _pick(p,notice_id).check()
    assert p.evaluate('scrollHost().scrollTop')>1000


def test_only_standard_codes_and_separate_unrecognized_text_from_missing(ui_page):
    p=ui_page
    _setup(p)
    paste(p,'单据号\t说明\n"fktzs2026100101"，FKTZS2026109999；FKTZS2026130001 FKTZS2026100101-1\n<script> 名称FKTZS2026100102 \"FKTZS2026100102 \"\"\"')
    assert _ids(p)==['101']
    report=p.evaluate('ntPasteReport')
    assert report['missing']==['FKTZS2026109999']
    assert report['invalid']==['单据号','说明','FKTZS2026130001','FKTZS2026100101-1','<script>','名称FKTZS2026100102','\"FKTZS2026100102','\"\"\"']
    assert '未识别为单据号' in p.inner_text('.modal .mb')
    assert p.locator('.modal .mb script').count()==0


def test_excluded_details_and_process_only_those_exact_records(ui_page):
    p=ui_page
    _setup(p)
    p.evaluate("""() => {
      SRV[3].exclude_source='manual';SRV[3].payee='甲供应商';
      SRV.push({...SRV[3],notice_id:108,bill_no:'FKTZS2026100108',exclude_source:'rule',
        exclude_rule_hint:'当前匹配规则：录入人 = 张三（历史命中规则未保存）'},
        {...SRV[3],notice_id:109,bill_no:'FKTZS2026100109'});
    }""")
    paste(p,'FKTZS2026100101 FKTZS2026100104 FKTZS2026100108')
    result=p.inner_text('.modal .mb')
    for text in ['通知书D','甲供应商','测试项目','1,000.00','手动剔除','自动剔除']:
        assert text in result
    p.get_by_role('button',name='去处理',exact=True).click()
    assert set(rows(p))=={'104','108'}
    assert '当前筛选条件下没有付款通知书' not in p.inner_text('#view')
    assert _ids(p)==[]  # Never carry active payment picks into archive processing.
    assert '仅显示本次已剔除或撤单单据' in p.inner_text('#view')
    assert p.locator('tr[data-notice-id="104"] .tag').filter(has_text='手动剔除').count()==1
    badge=p.locator('tr[data-notice-id="108"] .tag').filter(has_text='自动剔除')
    assert '录入人 = 张三' in badge.get_attribute('title')
    p.get_by_role('button',name='清除此定位',exact=True).click()
    assert set(rows(p))=={'104','108','109','105'}


@pytest.mark.parametrize('width,scale',[(1440,'1'),(1024,'1.25')])
def test_paste_report_large_font_and_long_details_fit(ui_page,width,scale):
    import os
    from pathlib import Path
    from app.mod03_notice.page import render_theme
    p=ui_page
    p.set_viewport_size({'width':width,'height':900})
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate('(scale)=>document.documentElement.style.setProperty("--fscale",scale)',scale)
    _setup(p)
    p.evaluate("""() => {
      SRV[3].exclude_source='rule';SRV[3].bill_name='十月份机械设备租赁结算付款通知书及多项目明细核对';
      SRV[3].exclude_rule_hint='当前匹配规则：单据名称关键字（房租）；历史命中规则未保存';
    }""")
    paste(p,'单据号 杂文本 FKTZS2026109999 FKTZS2026100101 FKTZS2026100104')
    modal=p.locator('.modal')
    assert modal.evaluate('e=>e.scrollWidth<=e.clientWidth+1')
    assert p.locator('.modal .mb').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
    button=p.get_by_role('button',name='去处理',exact=True)
    button.scroll_into_view_if_needed()
    b=button.bounding_box()
    assert b and 0<=b['x'] and b['x']+b['width']<=width
    badge=p.locator('.modal .tag').filter(has_text='自动剔除')
    assert '单据名称关键字（房租）' in badge.get_attribute('title')
    badge.hover()
    output=os.environ.get('MTRL_NOTICE_PASTE_EVIDENCE')
    if output:
        Path(output).mkdir(parents=True,exist_ok=True)
        p.screenshot(path=str(Path(output)/f'result-{width}-{scale}.png'))
    button.click()
    assert rows(p)==['104']
    p.fill('#ntSearch','自动剔除')
    assert rows(p)==['104']
    if output:
        p.screenshot(path=str(Path(output)/f'process-{width}-{scale}.png'))


def test_duplicate_code_still_shows_excluded_record_details(ui_page):
    p=ui_page
    _setup(p)
    p.evaluate("SRV.push({...SRV[3],notice_id:108,bill_no:SRV[0].bill_no,exclude_source:'manual'});")
    paste(p,'FKTZS2026100101')
    assert _ids(p)==[]
    assert '系统重号' in p.inner_text('.modal .mb')
    assert '通知书D' in p.inner_text('.modal .mb')
    p.get_by_role('button',name='去处理',exact=True).click()
    assert rows(p)==['108']
