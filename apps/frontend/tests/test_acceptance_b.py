"""Real notice-code paste and project-state write wiring."""
from playwright.sync_api import expect
from test_preview import server,browser_page,login
from live_data import get,grid_row
from preview_select import pick_option


def test_real_notice_code_paste_selects_exact_existing_row(server,browser_page,api):
    page,_=browser_page
    rows=get(api,'/api/m03/notice-list',period='')['items']
    import re
    selected=next((r for r in rows if re.fullmatch(r'FKTZS\d{10}',r['bill_no']) and not r['is_excluded'] and not r['is_revoked'] and sum(x['bill_no']==r['bill_no'] for x in rows)==1),None)
    assert selected,'真实副本缺少可勾选通知书；粘贴代表未覆盖'
    login(page,server)
    page.goto(server+'/preview/notices')
    page.get_by_role('button',name='粘贴单据号勾选',exact=True).click()
    dialog=page.get_by_role('dialog')
    dialog.get_by_label('单据号',exact=True).fill(selected['bill_no']+'\n'+selected['bill_no'])
    dialog.get_by_role('button',name='匹配并勾选',exact=True).click()
    result=page.get_by_role('dialog',name='单据号勾选结果',exact=True)
    expect(result).to_contain_text('已勾选 1 条')
    result.get_by_role('button',name='完成',exact=True).click()
    row=grid_row(page,'.notice-grid',selected['notice_id'])
    expect(row.get_by_role('checkbox')).to_be_checked()


def test_real_project_state_save_reads_back(server,browser_page,projects,disposable):
    page,_=browser_page
    row=next(p for p in projects if p['project_type']=='normal' and p['status']=='active')
    login(page,server)
    pick_option(page,'项目状态筛选','全部')
    pick_option(page,'状态：'+row['disp'],'归档')
    expect(page.get_by_label('状态：'+row['disp'],exact=True).locator('xpath=ancestor::div[contains(@class, "ant-select")]').first).to_contain_text('归档')
    current=page.request.get(server+'/api/m01/projects?status=all').json()
    assert next(p for p in current if p['id']==row['id'])['status']=='archived'
    pick_option(page,'状态：'+row['disp'],'在建')


def test_notice_code_exception_algorithm_without_browser():
    """Existing Vite loads only the pure domain module; no HTTP listener or DOM."""
    from pathlib import Path
    import shutil,subprocess
    code=r"""
import assert from 'node:assert/strict';
import {createServer} from 'vite';
const server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
try {
  assert.equal(server.httpServer,null);
  const {matchNoticeCodes}=await server.ssrLoadModule('/src/notices-api.ts');
  const row=(id,code,extra={})=>({notice_id:id,bill_no:code,is_excluded:false,is_revoked:false,pay_status:'未付清',...extra});
  const rows=[row(1,'FKTZS2026100001'),row(2,'FKTZS2026100002',{pay_status:'已付清'}),row(3,'FKTZS2026100003'),row(8,'FKTZS2026100003'),row(4,'FKTZS2026100004',{is_excluded:true}),row(5,'FKTZS2026100005',{is_revoked:true})];
  const result=matchNoticeCodes('"fktzs2026100002" FKTZS2026100001 FKTZS2026100001,FKTZS2026100003；FKTZS2026100004\tFKTZS2026100005 QTZC2026100001 FKTZS2026130001 FKTZS2026109999 名称FKTZS2026100006',rows);
  assert.deepEqual([...result.ids],[2,1]);
  assert.deepEqual([...result.paid],['FKTZS2026100002']);
  assert.deepEqual([...result.duplicates],['FKTZS2026100001（2次）']);
  assert.deepEqual([...result.ambiguous],['FKTZS2026100003（系统2条）']);
  assert.deepEqual(result.blocked.map(row=>row.notice_id),[4,5]);
  assert.deepEqual([...result.missing],['FKTZS2026109999']);
  assert.deepEqual([...result.invalid],['QTZC2026100001','FKTZS2026130001','名称FKTZS2026100006']);
  console.log('Pure notice-code exception cases passed; no browser or HTTP listener');
} finally {await server.close()}
"""
    node=shutil.which('node');assert node,'现有Node不可用，纯函数保护未运行'
    result=subprocess.run([node,'--input-type=module','-e',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr
