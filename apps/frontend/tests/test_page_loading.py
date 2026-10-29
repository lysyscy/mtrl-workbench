"""Static route failures keep navigation and retained business drafts available."""
import pytest
from playwright.sync_api import expect
from test_preview import server,browser_page


@pytest.mark.parametrize('with_draft',[False,True])
def test_project_lazy_wait_failure_and_explicit_recovery(server,browser_page,with_draft):
    page,context=browser_page
    assert context.request.post(server+'/m15/login',form={'account':server.owner['preview_account'],'password':''},max_redirects=0).status==303
    page.goto(server+'/preview')
    expect(page.locator('.page-view:not([hidden]):not([inert])')).to_be_visible()
    if with_draft:
        page.get_by_role('link',name='机械费',exact=True).click()
        page.get_by_role('button',name='表2 零租明细',exact=True).click()
        page.get_by_role('button',name='车牌规则',exact=True).click()
        editor=page.get_by_role('dialog',name='无需车牌设备关键词',exact=True)
        field=editor.get_by_label('无需车牌设备关键词',exact=True)
        draft=field.input_value()+'\n资源加载回归草稿';field.fill(draft)
        page.go_back();expect(page.locator('#page-title')).to_have_text('首页')
    pending=[]
    page.route('**/preview/assets/projects-*.js',lambda route:pending.append(route))
    page.get_by_role('link',name='项目档案',exact=True).click()
    expect(page.get_by_role('status').filter(has_text='正在读取项目档案')).to_be_visible()
    assert pending,'项目页未延迟加载，未覆盖首入资源失败'
    for route in pending:route.abort('failed')
    error=page.locator('[data-route-error]')
    expect(error.get_by_role('alert')).to_contain_text('项目档案未能加载')
    expect(page.get_by_role('navigation').get_by_role('link')).to_have_count(15)
    page.unroute('**/preview/assets/projects-*.js')
    if with_draft:
        error.get_by_role('button',name='重新加载页面',exact=True).click()
        expect(error).to_contain_text('未保存')
        page.get_by_role('link',name='机械费',exact=True).click()
        expect(field).to_have_value(draft)
        editor.get_by_role('button',name='取消',exact=True).click()
        page.get_by_role('button',name='放弃并关闭',exact=True).click()
        page.get_by_role('link',name='项目档案',exact=True).click()
    error.get_by_role('button',name='重新加载页面',exact=True).click()
    expect(page.get_by_role('heading',name='项目档案',exact=True)).to_be_visible()
    expect(page.get_by_role('region',name='项目列表',exact=True)).to_have_attribute('aria-busy','false')
    expect(page.locator('[data-route-error]')).to_have_count(0)
