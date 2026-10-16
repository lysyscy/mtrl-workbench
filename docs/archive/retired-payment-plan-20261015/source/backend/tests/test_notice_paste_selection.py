"""Pasted bill numbers select only unique active records; manual picks stay put."""
import pytest
from tests.acc_plugin import acc
from tests.test_shell_ui_workflow import ui_page  # noqa: F401
from tests.test_tail309_notice_selection import _setup, _ids, _pick


def rows(p):
    return p.locator('tr[data-notice-id]').evaluate_all('(rs)=>rs.map(r=>r.dataset.noticeId)')


def paste(p,text):
    p.click('[data-act="ntPasteOpen"]')
    p.fill('#ntPasteInput',text)
    p.click('[data-act="ntPasteApply"]')
    p.locator('.modal h3').filter(has_text='单据号勾选结果').wait_for()


@acc('ACC-NOTICE-PASTE-001','001-01')
@acc('ACC-NOTICE-PASTE-001','001-02')
@acc('ACC-NOTICE-PASTE-001','001-03')
def test_paste_exact_codes_refresh_all_projects_report_conflicts_and_never_print(ui_page):
    p=ui_page
    _setup(p)
    p.evaluate("""() => {
      SRV.push({...SRV[2],notice_id:106}, {...SRV[0],notice_id:107,bill_no:'DOC-PAID',amount_paid:'1000'});
      window.requests=[];
      API.m03Batch=async b=>{requests.push(b);return {ok:true};};
      fNt.projs=['测试仓库']; fNt.month='2025-01';fNt.stat='未付清';fNt.q='old';render();
    }""")
    paste(p,'doc-b\r\nDOC-A\tDOC-A, MISSING；DOC-C\nDOC-D\nDOC-E\nDOC-PAID')
    assert _ids(p)==['101','102','107']
    result=p.inner_text('.modal .mb')
    for text in ['未找到','MISSING','系统重号','DOC-C','已剔除','已撤单','重复输入','已付清，仍可打印']:
        assert text in result
    assert p.evaluate('requests')==[]
    p.get_by_role('button',name='完成',exact=True).click()
    assert set(rows(p)[:3])=={'101','102','107'}
    assert p.evaluate('fNt.projs')==[] and p.evaluate('fNt.month')=='全部'
    assert p.locator('[data-act="ntPrint"]').is_enabled()


@acc('ACC-NOTICE-PASTE-001','001-04')
def test_manual_picks_and_unpicks_keep_positions_only_pasted_batch_is_grouped(ui_page):
    p=ui_page
    _setup(p)
    before=rows(p)
    _pick(p,'103').check()
    assert rows(p)==before
    paste(p,'DOC-B')
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


@acc('ACC-NOTICE-PASTE-001','001-06')
def test_empty_or_unmatched_paste_preserves_selection_and_input_for_correction(ui_page):
    p=ui_page
    _setup(p)
    _pick(p,'103').check()
    p.click('[data-act="ntPasteOpen"]')
    p.click('[data-act="ntPasteApply"]')
    assert '请先粘贴' in p.inner_text('#ntPasteError')
    assert _ids(p)==['103']
    p.fill('#ntPasteInput','NOT-FOUND')
    p.click('[data-act="ntPasteApply"]')
    p.locator('.modal h3').filter(has_text='单据号勾选结果').wait_for()
    assert _ids(p)==['103']
    assert '原勾选保持不变' in p.inner_text('.modal .mb')
    p.get_by_role('button',name='修改清单',exact=True).click()
    assert p.input_value('#ntPasteInput')=='NOT-FOUND'


@acc()
def test_read_failure_or_closed_dialog_does_not_apply_stale_selection(ui_page):
    p=ui_page
    _setup(p)
    _pick(p,'103').check()
    p.evaluate("() => {API.notices=async()=>{throw Error('隔离读取失败');};}")
    p.click('[data-act="ntPasteOpen"]')
    p.fill('#ntPasteInput','DOC-B')
    p.click('[data-act="ntPasteApply"]')
    assert '隔离读取失败' in p.inner_text('#ntPasteError')
    assert _ids(p)==['103']
    p.evaluate('() => {API.notices=()=>new Promise(resolve=>window.finishPaste=resolve);}')
    p.click('[data-act="ntPasteApply"]')
    p.get_by_role('button',name='取消',exact=True).click()
    p.evaluate('finishPaste({items:SRV})')
    p.wait_for_function('!ntPasteBusy')
    assert _ids(p)==['103']


@acc('ACC-NOTICE-PASTE-001','001-05')
def test_paste_group_reaches_top_of_virtual_table_without_manual_scroll_jumps(ui_page):
    p=ui_page
    _setup(p)
    p.evaluate("""async () => {
      SRV=Array.from({length:550},(_,i)=>({...SRV[0],notice_id:1000+i,bill_no:'DOC-'+(1000+i)}));
      await reloadNotices();
    }""")
    p.evaluate('scrollHost().scrollTop=6500')
    p.wait_for_function('scrollHost().scrollTop>1000')
    paste(p,'DOC-1549\nDOC-1500')
    p.get_by_role('button',name='完成',exact=True).click()
    p.wait_for_function('scrollHost().scrollTop===0')
    assert set(rows(p)[:2])=={'1549','1500'}
    p.evaluate('scrollHost().scrollTop=5000')
    p.wait_for_function('scrollHost().scrollTop>1000')
    notice_id=p.locator('[data-act="pick"]:not(:checked)').first.get_attribute('data-id')
    _pick(p,notice_id).check()
    assert p.evaluate('scrollHost().scrollTop')>1000
