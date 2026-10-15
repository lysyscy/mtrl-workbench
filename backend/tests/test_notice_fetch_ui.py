"""真实壳抓取结果弹窗；复用隔离浏览器夹具，不连接 i8。"""
from tests.acc_plugin import acc
from tests.test_shell_ui_workflow import ui_page  # noqa: F401
from app.mod03_notice.page import DEFAULT_THEME, render_theme


def load_styles(page):
    page.add_style_tag(content=render_theme(DEFAULT_THEME))


@acc('ACC-PRJ-OWN-001', '001-08')
def test_fetch_result_shows_ignored_rows_and_escapes_source_text(ui_page, tmp_path):
    p = ui_page
    load_styles(p)
    p.evaluate('''() => {
      API.fetchNotices=async()=>({ok:true,fetched:4,upserted:2,ignored:[
        {bill_no:'BAD-1',project_name:'填错项目',doc_name:'<img src=x onerror=alert(1)>',reason:'付款项目未建档'},
        {bill_no:'BAD-2',project_name:'测试小微',doc_name:'材料款',reason:'单据名命中多个具体小微'}]});
      reloadNotices=async()=>{window.noticesReloaded=true;};
      reloadM02IfOn=async()=>{};
      API.unresolved=async()=>({items:[{bill_no:'BAD-2',project_name:'测试小微',doc_name:'材料款',kind:'needs_choice',shell_id:2,candidates:[]}]});
      ACT.fetchNt();
    }''')
    p.click('[data-act="fetchNtOk"]')
    p.wait_for_function('window.noticesReloaded')
    text = p.inner_text('#modalRoot')
    assert 'i8 返回 4 条，新增或更新 2 条' in text
    assert '本次忽略 2 条，本月数据尚未导齐' in text
    assert all(s in text for s in ['BAD-1', 'BAD-2', '付款项目未建档', '单据名命中多个具体小微'])
    assert '<img src=x onerror=alert(1)>' in text
    assert p.locator('#modalRoot img').count() == 0
    screenshot = tmp_path / 'notice-fetch-result.png'
    p.screenshot(path=str(screenshot))
    print(f'NOTICE_FETCH_SCREENSHOT={screenshot}')
    p.click('[data-act="ownNtOpen"]')
    p.wait_for_function("document.getElementById('modalRoot').innerText.includes('待指定归属')")
    p.click('[data-act="closeModal"]')


@acc('ACC-PRJ-OWN-001', '001-08')
def test_fetch_without_ignored_rows_does_not_show_previous_list(ui_page):
    p = ui_page
    p.evaluate('''async () => {
      reloadNotices=async()=>{}; reloadM02IfOn=async()=>{};
      API.fetchNotices=async()=>({ok:true,fetched:1,upserted:0,ignored:[]});
      await ntFetchBackend('2026-10');
    }''')
    text = p.inner_text('#modalRoot')
    assert 'i8 返回 1 条，新增或更新 0 条' in text
    assert '本次忽略' not in text
    assert p.locator('[data-act="ownNtOpen"]').count() == 0
