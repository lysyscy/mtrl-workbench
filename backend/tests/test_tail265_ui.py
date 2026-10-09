"""TAIL-265：真实浏览器验证同窗导出、转置月份递增、失败输入、取消和最大字号布局。"""
from tests.test_tail264_ui import page
from tests.acc_plugin import acc
from app.mod15_user.domain import UI_SCALES
from pathlib import Path


@acc()
def test_month_columns_increment_and_preserve_positions(page):
    page.evaluate('''() => {
      closeModal();awfPj='__隔离项目__';awfYm='2026-12';
      AWF_ROWS=[{item:'测试项',amount:'7.00'}];
      ACT.awfBatch();
    }''')
    first = page.locator('[data-act="awfYmCell"]').first
    first.fill('2026-12')
    first.dispatch_event('change')
    assert page.locator('#awfTbl thead th').count() >= 2
    page.locator('[data-act="awfCell"]').first.fill('123.45')
    page.locator('[data-act="awfRowAdd"]').click()
    assert '2027-03' in page.locator('#awfTbl thead').inner_text()
    first.fill('2025-11');first.dispatch_event('change')
    assert '2025-12' in page.locator('#awfTbl thead').inner_text()
    assert page.locator('[data-act="awfCell"]').first.input_value() == '123.45'
    page.evaluate('() => {API.m09Batch=async body=>{saved.push(body);return {ok:false,message:"金额错误"};};}')
    page.locator('[data-act="awfBatchOk"]').click()
    assert not page._tail_errors, page._tail_errors
    assert page.evaluate('saved.length') == 1, page.evaluate('saved')
    body = page.evaluate('saved[0]')
    assert body['months'][0]['ym'] == '2025-11'
    assert body['months'][0]['values']['测试项'] == '123.45'
    assert [m['ym'] for m in body['months']] == ['2025-11','2025-12','2026-01','2026-02']
    assert [m['values']['测试项'] for m in body['months']] == ['123.45','','7','']
    assert page.locator('[data-act="awfCell"]').first.input_value() == '123.45'


@acc()
def test_export_same_modal_cancel_and_long_list_footer(page):
    page.evaluate('applyUiScale', max(UI_SCALES, key=lambda scale: float(scale[2]))[2])
    page.evaluate('''() => {
      closeModal();PROC_PJS.length=0;
      for(let i=0;i<45;i++) PROC_PJS.push('长项目名称用于验证操作区'+i);
      procPj=PROC_PJS[0];procExpPjs=[];
      window.exports=[];dlExport=async(url)=>{exports.push(url);return null;};
      ACT.procExpToggle();
    }''')
    assert page.locator('#procExportProjects').is_visible()
    assert page.locator('#procExportProjects input:checked').count() == 1
    page.locator('#procExportProjects input').nth(2).check()
    assert page.evaluate('procExpPjs') == ['长项目名称用于验证操作区0','长项目名称用于验证操作区2']
    button = page.locator('[data-act="procExpSave"]')
    box = button.bounding_box()
    assert box and box['y'] + box['height'] <= 900
    page.locator('#procExportProjects').evaluate('(el)=>{el.scrollTop=el.scrollHeight;}')
    assert button.is_visible()
    page.screenshot(path=str(Path(__file__).resolve().parents[2] / '.codebuddy/work/00-scratch/tmp-20261009-proc-export.png'))
    page.locator('[data-act="procExpCancel"]').click()
    assert not page.locator('#procExportProjects').is_visible()
    assert page.evaluate('saved.length') == 0
    assert page.evaluate('exports.length') == 0
    page.evaluate('() => {ACT.procExpToggle();}')
    page.locator('[data-act="procExpPjNone"]').click()
    assert page.locator('[data-act="procExpSave"]').is_disabled()
    assert page.locator('[data-act="procExpSave"]').get_attribute('title') == '请先选择项目'
    page.locator('#procExportProjects input').first.check()
    page.locator('#procExportProjects input').nth(2).check()
    page.locator('[data-act="procExpSave"]').click()
    assert page.evaluate('exports.length') == 1
    assert 'projects=' in page.evaluate('exports[0]')
    assert page.locator('#procExportProjects input:checked').count() == 2


@acc()
def test_batch_invalid_start_failure_success_and_cancel(page):
    page.evaluate('''() => {
      closeModal();awfPj='__隔离项目__';awfYm='2026-12';
      AWF_ROWS=[{item:'第一项',amount:'7'},{item:'第二项',amount:'9'}];
      window.reloaded=0;reloadM09=async()=>{reloaded++;};
      API.m09Batch=async body=>{saved.push(body);return {ok:true};};
      ACT.awfBatch();
    }''')
    start = page.locator('[data-act="awfYmCell"]')
    start.fill('')
    field = page.locator('[data-act="awfCell"]').first
    field.fill('非法金额')
    page.locator('[data-act="awfBatchOk"]').click()
    assert '有效' in page.locator('#awfBatchError').inner_text()
    assert field.input_value() == '非法金额'
    assert page.evaluate('saved.length') == 0
    start.fill('2026-12');start.dispatch_event('change')
    page.evaluate('() => {API.m09Batch=async body=>{saved.push(body);return {ok:false,message:"金额非法，整批未写入"};};}')
    page.locator('[data-act="awfBatchOk"]').click()
    assert '整批未写入' in page.locator('#awfBatchError').inner_text()
    assert field.input_value() == '非法金额'
    field.fill('-12.34')
    page.evaluate('() => {API.m09Batch=async body=>{saved.push(body);return {ok:true};};}')
    page.locator('[data-act="awfBatchOk"]').click()
    page.wait_for_function('reloaded === 1')
    assert not page.locator('#awfTbl').is_visible()
    assert page.evaluate('saved[1].months[0].values["第一项"]') == '-12.34'
    page.evaluate('() => {ACT.awfBatch();}')
    page.locator('#modalRoot [data-act="closeModal"]').last.click()
    assert page.evaluate('saved.length') == 2
    assert not page._tail_errors


@acc()
def test_batch_max_scale_many_items_months_and_visible_footer(page):
    page.set_viewport_size({'width':1280,'height':720})
    page.evaluate('applyUiScale', max(UI_SCALES, key=lambda scale: float(scale[2]))[2])
    page.evaluate('''() => {
      closeModal();awfPj='__长项目名称用于批量录入__';awfYm='2026-12';
      AWF_ROWS=Array.from({length:40},(_,i)=>({item:'费用项'+i,amount:7}));
      ACT.awfBatch();for(let i=0;i<9;i++) ACT.awfRowAdd();
    }''')
    table = page.locator('#awfTbl')
    table.evaluate('(t)=>{t.parentElement.scrollTop=t.parentElement.scrollHeight;t.parentElement.scrollLeft=700;}')
    assert page.locator('#awfTbl thead th[data-ym]').count() == 12
    assert page.locator('#awfTbl tbody tr').count() == 40
    assert page.locator('#awfTbl thead th').first.evaluate('(el)=>{const r=el.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2).textContent;}') == '数据项'
    page.locator('[data-act="awfRowAdd"]').scroll_into_view_if_needed()
    button = page.locator('[data-act="awfBatchOk"]')
    box = button.bounding_box()
    assert box and 0 <= box['y'] and box['y'] + box['height'] <= 720
    assert page.locator('#modalRoot [data-act="closeModal"]').last.is_visible()
    page.screenshot(path=str(Path(__file__).resolve().parents[2] / '.codebuddy/work/00-scratch/tmp-20261009-month-entry.png'))
    page.locator('#modalRoot [data-act="closeModal"]').last.click()
    assert page.evaluate('saved.length') == 0
