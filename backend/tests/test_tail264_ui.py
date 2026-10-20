"""TAIL-264：真实浏览器的候选、自由录入、失败草稿与材料名编辑回归。写请求使用隔离回执。"""
import os
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture
def page():
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', 'C:/ProgramData/ms-playwright')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page._tail_errors = errors
        if os.environ.get('TAIL_ACTIONS_OVERRIDE'):
            from pathlib import Path
            body = Path(os.environ['TAIL_ACTIONS_OVERRIDE']).read_text('utf-8')
            page.route('**/shell/actions.js*', lambda route: route.fulfill(body=body, content_type='application/javascript'))
        page.goto('http://127.0.0.1:8000/app')
        page.wait_for_function('typeof ACT !== "undefined" && PJs.length > 0')
        # No browser scenario can accidentally write production data.
        page.route('**/api/**', lambda route: route.abort() if route.request.method not in ('GET', 'HEAD') else route.continue_())
        page.evaluate('''() => {
          NO.length=0; NO.push({id:'264',code:'自检',sup:'旧供应商',proj:'当前仓',status:'ok',cat:'集采'});
          window.saved=[];
          API.m03SupMatch=async()=>({ok:true,pool:['河南安装集团','河南物资公司','河南安装集团']});
          API.jcSupplier=async body=>{saved.push(body);return {ok:false,message:'保存失败，请重试'};};
          ACT.supEditOpen({dataset:{id:'264'}});
        }''')
        yield page
        browser.close()


def test_supplier_search_choose_and_failed_enter_keeps_full_name(page):
    field = page.locator('#supManualValue')
    field.fill('河南')
    candidates = page.locator('[data-act="supManualPick"]')
    assert candidates.count() == 2
    candidates.first.click()
    assert field.input_value() == '河南安装集团'
    field.press('Enter')
    page.wait_for_function('saved.length === 1')
    assert page.evaluate('saved[0].supplier') == '河南安装集团'
    assert field.input_value() == '河南安装集团'
    assert '保存失败' in page.locator('#supManualError').inner_text()
    field.fill('无匹配自由输入')
    assert candidates.count() == 0
    page.locator('[data-act="supManualSave"]').click()
    page.wait_for_function('saved.length === 2')
    assert page.evaluate('saved[1].supplier') == '无匹配自由输入'


def test_material_edit_uses_contract_id_and_preserves_failure(page):
    page.evaluate('''() => {
      closeModal();JCs.length=0;JCs.push({id:'501',material:'同名材料'},{id:'502',material:'同名材料'});
      API.m11Fields=async body=>{saved.push(body);return {ok:false,message:'保存失败，请重试'};};
      ACT.jcMaterialOpen({dataset:{id:'501'}});
    }''')
    page.locator('#jcMaterialValue').fill('人工修改材料')
    page.locator('#jcMaterialValue').press('Enter')
    page.wait_for_function('saved.length === 1')
    assert page.evaluate('saved[0]') == {'id': '501', 'fields': {'material_name': '人工修改材料'}}
    assert page.locator('#jcMaterialValue').input_value() == '人工修改材料'
    assert page.evaluate('JCs[1].material') == '同名材料'


def test_material_success_reloads_list_and_cancel_writes_nothing(page):
    page.evaluate('''() => {
      closeModal();JCs.length=0;JCs.push({id:'501',material:'旧材料'},{id:'502',material:'别的材料'});
      API.m11Fields=async body=>{saved.push(body);return {ok:true};};
      API.m11List=async()=>({rows:[{id:501,material:'新材料'},{id:502,material:'别的材料'}]});
      ACT.jcMaterialOpen({dataset:{id:'501'}});
    }''')
    page.locator('#jcMaterialValue').fill('新材料')
    page.locator('[data-act="jcMaterialSave"]').click()
    page.wait_for_function('JCs[0].material === "新材料"')
    page.evaluate('''async () => {await reloadM11();ACT.jcMaterialOpen({dataset:{id:'502'}});}''')
    assert page.locator('#jcMaterialValue').input_value() == '别的材料'
    page.locator('#modalRoot [data-act="closeModal"]').last.click()
    assert page.evaluate('saved.length') == 1
    assert not page._tail_errors


def test_supplier_failed_pool_stays_failed_while_free_input_remains(page):
    page.evaluate('''async () => {
      closeModal();API.m03SupMatch=async()=>{throw new Error('离线');};
      await ACT.supEditOpen({dataset:{id:'264'}});
    }''')
    page.locator('#supManualValue').fill('自由输入')
    assert '读取失败' in page.locator('#supManualPoolState').inner_text()
    assert '正在读取' not in page.locator('#supManualPoolState').inner_text()


def test_automatic_multiple_candidates_first_selection_and_confirmation(page):
    page.evaluate('''async () => {
      closeModal();API.m03SupMatch=async()=>({ok:true,pool:['河南安装集团','河南物资公司'],cands:['河南安装集团','河南物资公司'],level:3});
      API.jcSupplier=async body=>{saved.push(body);return {ok:true};};
      jcLinkAct=async call=>await call();
      await ACT.supMatchRun({dataset:{id:'264'}});
    }''')
    assert page.locator('#supPickId').input_value() == '河南安装集团'
    page.locator('[data-act="supOk"]').click()
    assert page.evaluate('saved[0].supplier') == '河南安装集团'
    assert page.evaluate('SUP_SUG["264"]') == '河南安装集团'
    page.evaluate('''async () => {await ACT.supAccept({dataset:{id:'264'}});}''')
    assert page.evaluate('saved[1].supplier') == '河南安装集团'
    assert page.evaluate('SUP_SUG["264"]') is None
    assert not page._tail_errors
