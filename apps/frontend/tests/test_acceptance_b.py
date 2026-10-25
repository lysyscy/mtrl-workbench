"""B: exact pasted selection and inline status writes; no real i8 or printing."""
import re
from playwright.sync_api import expect
from preview_select import pick_option
from test_preview import server, browser_page  # noqa: F401


def login_b(page, server):
    page.goto(server + '/login?next=%2Fpreview%2Fprojects')
    page.locator('[name=account]').fill('preview-admin')
    page.locator('[name=password]').fill('')
    page.locator('button[type=submit]').click()
    expect(page.get_by_label('状态：隔离项目', exact=True)).to_be_visible()


def test_exact_paste_replaces_picks_reports_exceptions_and_preserves_order(server, browser_page):
    page, _ = browser_page
    login_b(page, server)
    base = page.request.get(server + '/api/m03/notice-list?period=').json()['items'][0]
    rows = [dict(base, notice_id=900+i, bill_no=f'FKTZS202610{i:04}', is_excluded=i==4,
                 exclude_source='manual' if i==4 else '', is_revoked=i==5,
                 pay_status='已付清' if i==2 else '未付清', amount_paid='100.00' if i==2 else '0.00') for i in range(1,7)]
    rows.append(dict(rows[2],notice_id=908))
    page.route('**/api/m03/notice-list?**', lambda route: route.fulfill(json={'items':rows}))
    page.goto(server + '/preview/notices')
    expect(page.get_by_label('勾选FKTZS2026100006')).to_be_visible()
    page.get_by_label('勾选FKTZS2026100006').click()
    expect(page.get_by_label('勾选FKTZS2026100006')).to_be_checked()
    page.get_by_label('通知书搜索', exact=True).fill('不会匹配')
    page.get_by_role('button',name='粘贴单据号勾选',exact=True).click()
    dialog = page.get_by_role('dialog',name='粘贴单据号勾选',exact=True)
    dialog.get_by_label('单据号',exact=True).fill('"fktzs2026100002"\nFKTZS2026100001 FKTZS2026100001,FKTZS2026100003；FKTZS2026100004\tFKTZS2026100005 QTZC2026100001 FKTZS2026130001 FKTZS2026109999 名称FKTZS2026100006')
    dialog.get_by_role('button',name='匹配并勾选',exact=True).click()
    result = page.get_by_role('dialog',name='单据号勾选结果',exact=True)
    expect(result).to_contain_text('已勾选 2 条')
    for text in ['未识别为单据号','QTZC2026100001','未找到','FKTZS2026109999','系统重号','重复输入','已付清，仍可打印','已剔除或已撤单']:
        expect(result).to_contain_text(text)
    result.get_by_role('button',name='完成',exact=True).click()
    expect(page.get_by_label('通知书搜索',exact=True)).to_have_value('')
    expect(page.get_by_label('付款状态', exact=True).locator('xpath=ancestor::div[contains(@class, "ant-select")]').first).to_contain_text('全部')
    expect(page.get_by_label('勾选FKTZS2026100006')).not_to_be_checked()
    expect(page.get_by_label('勾选FKTZS2026100001')).to_be_checked()
    expect(page.get_by_label('勾选FKTZS2026100002')).to_be_checked()
    codes = lambda: page.locator('.notice-grid .ag-cell[col-id=bill_no]').all_text_contents()
    assert set(codes()[:2]) == {'FKTZS2026100001','FKTZS2026100002'}
    before = codes()
    page.get_by_label('勾选FKTZS2026100001').click()
    expect(page.get_by_label('勾选FKTZS2026100001')).not_to_be_checked()
    assert codes() == before
    page.get_by_role('button',name='粘贴单据号勾选',exact=True).click()
    page.get_by_label('单据号',exact=True).fill('FKTZS2026100004 FKTZS2026100005')
    page.get_by_role('button',name='匹配并勾选',exact=True).click()
    expect(page.get_by_role('dialog')).to_contain_text('原勾选保持不变')
    page.get_by_role('button',name='去处理',exact=True).click()
    expect(page.get_by_label('勾选FKTZS2026100004')).not_to_be_checked()
    expect(page.get_by_label('勾选FKTZS2026100006')).to_have_count(0)
    pick_option(page, '通知书分类', '辅材')
    expect(page.get_by_label('勾选FKTZS2026100004')).to_have_count(0)
    expect(page.get_by_label('通知书搜索',exact=True)).to_be_visible()


def test_inline_project_status_saves_and_failed_save_restores_value(server, browser_page):
    page, _ = browser_page
    login_b(page, server)
    pick_option(page, '项目状态筛选', '全部')
    field = page.get_by_label('状态：隔离项目',exact=True)
    project = next(p for p in page.request.get(server+'/api/m01/projects?status=all').json() if p['disp']=='隔离项目')
    pending=[]
    url=f'**/api/m01/projects/{project["id"]}/status'
    page.route(url,lambda route:pending.append(route))
    pick_option(page, '状态：隔离项目', '归档')
    expect(field).to_be_disabled()
    expect(page.get_by_role('dialog')).to_have_count(0)
    expect(page.get_by_text('正在保存…',exact=True)).to_be_visible()
    pending.pop().fulfill(status=400,json={'ok':False,'message':'合成拒绝：仍有在建小微'})
    expect(field.locator('xpath=ancestor::div[contains(@class, "ant-select")]').first).to_contain_text('在建')
    expect(field).to_be_enabled()
    expect(field.locator('xpath=ancestor::td')).to_contain_text('合成拒绝：仍有在建小微')
    page.unroute(url)
    pick_option(page, '状态：隔离项目', '归档')
    expect(field).to_be_enabled()
    expect(field.locator('xpath=ancestor::div[contains(@class, "ant-select")]').first).to_contain_text('归档')
    actual=next(p for p in page.request.get(server+'/api/m01/projects?status=all').json() if p['id']==project['id'])
    assert actual['status']=='archived'
    trails=page.request.get(server+'/api/m01/trails?limit=8').json()
    assert any(t['field_label']=='项目状态' and t['after']=='archived' for t in trails)
    pick_option(page, '状态：隔离项目', '在建')
    expect(field).to_be_enabled()
    expect(field.locator('xpath=ancestor::div[contains(@class, "ant-select")]').first).to_contain_text('在建')
