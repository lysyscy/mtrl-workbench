"""Rules maintenance keeps validation, receipts, permission and history honest."""
import os

import httpx
import pytest
from playwright.sync_api import expect
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from test_preview import server, browser_page, login  # noqa: F401
from tools.audit.workspace_paths import output


@pytest.fixture(scope='module')
def preview_seed():
    def seed(env):
        from app.mod06_proc.models import ProcMechMatchRule
        from app.mod11_jc.models import JcIgnoreProject
        if os.environ.get('MTRL_RULES_TEST_BUILD'):
            env['FRONTEND_PREVIEW_DIR'] = os.environ['MTRL_RULES_TEST_BUILD']
        engine = create_engine(env['TEST_DATABASE_URL'], connect_args={'options': env['PGOPTIONS']})
        try:
            with Session(engine) as s:
                assert s.execute(text('SELECT current_database(),current_schema()')).one() == ('mtrl_workbench_test', env['PGOPTIONS'].split('search_path=')[1])
                s.add_all([
                    ProcMechMatchRule(warehouse_name='隔离验收仓库', aliases=['别名验收项目']),
                    ProcMechMatchRule(warehouse_name='长名称验收仓库', aliases=['长名报表名']),
                    JcIgnoreProject(name_full='停用样例项目', reason='停用样例', operator='预览管理员', active=False),
                ])
                s.commit()
        finally:
            engine.dispose()
    return seed


def notice_flags(page, server):
    items = page.request.get(server + '/api/m03/notice-list?period=').json()['items']
    return {row['bill_no']: (row['is_excluded'], row['exclude_source']) for row in items}


def test_rules_page_reads_current_configuration(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-14 规则配置', exact=True).click()
    expect(page.get_by_role('heading', name='规则配置')).to_be_visible()
    rules_block = page.locator('.rules-block').nth(0)
    region = page.get_by_role('region', name='剔除规则列表')
    expect(region.get_by_text('业务类型', exact=True)).to_be_visible()
    expect(region.get_by_text('付劳务公司款')).to_be_visible()
    expect(region.get_by_text('录入人', exact=True)).to_be_visible()
    expect(region.get_by_text('梁丽佳')).to_be_visible()
    expect(rules_block.get_by_text('来源：系统配置')).to_be_visible()
    expect(rules_block).to_contain_text('已有单据的剔除状态保持不变，再次抓取也不重算')
    expect(rules_block).to_contain_text('剔除规则中不得配置「收款单位 = 资产处集中采购」')
    jc = page.get_by_role('region', name='集采项目剔除名单')
    expect(jc).to_contain_text('停用样例项目')
    expect(jc.get_by_text('已停用', exact=True)).to_be_visible()
    expect(jc.get_by_role('button', name='恢复', exact=True)).to_be_visible()
    expect(page.locator('.rules-block').nth(1)).to_contain_text('集采项目剔除名单（0 项在用）')
    mech = page.get_by_role('region', name='机械报表项目匹配')
    expect(mech.get_by_label('隔离项目的报表项目名')).to_have_value('别名验收项目')
    expect(mech.get_by_label('长项目名验收的报表项目名')).to_have_value('长名报表名')
    page.set_viewport_size({'width': 800, 'height': 900})
    expect(page.get_by_role('button', name='＋ 增加规则')).to_be_in_viewport()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.set_viewport_size({'width': 1440, 'height': 900})
    page.screenshot(path=str(output('rules-page-1440-synthetic.png', kind='screenshots')), full_page=True)


def test_exclusion_rule_validation_receipts_and_history(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.goto(server + '/preview/rules')
    rules_block = page.locator('.rules-block').nth(0)
    region = page.get_by_role('region', name='剔除规则列表')
    before = notice_flags(page, server)
    assert before['PREVIEW-HISTORY'] == (False, '') and before['PREVIEW-NORMAL'] == (False, '')
    page.get_by_role('button', name='＋ 增加规则').click()
    dialog = page.locator('.rules-dialog')
    expect(dialog).to_contain_text('修改只影响后续抓取，已有剔除标记不重算。')
    values = dialog.get_by_label('命中值 ＊（多个用 ｜ 分隔）')
    dialog.get_by_role('button', name='新增', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('命中值不能为空')
    values.fill('资产处集中采购')
    dialog.get_by_role('button', name='新增', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('不得为「资产处集中采购」')
    expect(values).to_have_value('资产处集中采购')
    values.fill('测试剔除｜临时规则')
    dialog.get_by_label('剔除的业务含义').fill('测试期间费用')
    dialog.get_by_role('button', name='新增', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(rules_block.get_by_role('status')).to_contain_text('已新增剔除规则「业务类型」（2 个命中值）')
    expect(rules_block.get_by_role('status')).to_contain_text('已有单据的剔除状态保持不变，再次抓取也不重算')
    rules = page.request.get(server + '/api/m14/rules').json()
    added = next(row for row in rules['rules'] if '测试剔除' in row['values'])
    assert added['values'] == '测试剔除｜临时规则' and added['meaning'] == '测试期间费用'
    row = region.locator('tr').filter(has_text='测试剔除')
    row.get_by_role('button', name='编辑', exact=True).click()
    dialog.get_by_label('剔除的业务含义').fill('测试含义改')
    dialog.get_by_role('button', name='保存修改', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(rules_block.get_by_role('status')).to_contain_text('已更新剔除规则「业务类型」')
    rules = page.request.get(server + '/api/m14/rules').json()
    assert next(r for r in rules['rules'] if r['id'] == added['id'])['meaning'] == '测试含义改'
    assert page.request.delete(server + f"/api/m14/rules/{added['id']}").json()['ok'] is True
    row.get_by_role('button', name='编辑', exact=True).click()
    dialog.get_by_label('剔除的业务含义').fill('迟到修改')
    dialog.get_by_role('button', name='保存修改', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('这条规则已经不在了（可能刚被删）—— 请刷新后重试')
    dialog.get_by_role('button', name='取消', exact=True).click()
    dialog.get_by_role('button', name='放弃并关闭').click()
    expect(dialog).not_to_be_visible()
    row.get_by_role('button', name='删除', exact=True).click()
    expect(dialog).to_contain_text('确定删除「业务类型」这条规则？命中值：测试剔除、临时规则。')
    expect(dialog).to_contain_text('硬删、不留痕，删除后无法找回')
    dialog.get_by_role('button', name='删除', exact=True).click()
    expect(rules_block.get_by_role('alert')).to_contain_text('这条规则已经不在了（可能刚被删）—— 请刷新后重试')
    expect(row).to_have_count(0)
    page.get_by_role('button', name='＋ 增加规则').click()
    dialog.get_by_label('命中值 ＊（多个用 ｜ 分隔）').fill('待删规则')
    dialog.get_by_role('button', name='新增', exact=True).click()
    expect(dialog).not_to_be_visible()
    fresh = region.locator('tr').filter(has_text='待删规则')
    fresh.get_by_role('button', name='删除', exact=True).click()
    expect(dialog).to_contain_text('确定删除「业务类型」这条规则？命中值：待删规则。')
    dialog.get_by_role('button', name='删除', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(rules_block.get_by_role('status')).to_contain_text('已删除剔除规则「业务类型」')
    expect(rules_block.get_by_role('status')).to_contain_text('配置类数据 = 硬删、不留痕')
    expect(fresh).to_have_count(0)
    after = notice_flags(page, server)
    assert after['PREVIEW-HISTORY'] == before['PREVIEW-HISTORY'] and after['PREVIEW-NORMAL'] == before['PREVIEW-NORMAL']


def test_jc_ignore_add_toggle_and_idempotence(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.goto(server + '/preview/rules')
    block = page.locator('.rules-block').nth(1)
    block.get_by_role('button', name='加入剔除名单', exact=True).click()
    expect(block.get_by_role('alert')).to_contain_text('项目全名不能为空')
    block.get_by_label('项目全名').fill('新剔除验收项目')
    block.get_by_label('加入理由').fill('测试样例')
    block.get_by_role('button', name='加入剔除名单', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已加入剔除名单：「新剔除验收项目」')
    expect(block.get_by_role('status')).to_contain_text('从下次抓取起不再写入')
    row = block.locator('tr').filter(has_text='新剔除验收项目')
    expect(row.get_by_text('在用', exact=True)).to_be_visible()
    expect(row).to_contain_text('预览管理员')
    expect(block).to_contain_text('集采项目剔除名单（1 项在用）')
    items = page.request.get(server + '/api/m14/jc-ignore').json()['items']
    entry = next(item for item in items if item['name_full'] == '新剔除验收项目')
    assert entry['active'] is True and entry['reason'] == '测试样例'
    block.get_by_label('项目全名').fill('新剔除验收项目')
    block.get_by_role('button', name='加入剔除名单', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('「新剔除验收项目」已在名单里（⛔ 没有重复添加）')
    row.get_by_role('button', name='停用', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已停用（记录留在册，可随时恢复）')
    expect(row.get_by_text('已停用', exact=True)).to_be_visible()
    items = page.request.get(server + '/api/m14/jc-ignore').json()['items']
    assert next(item for item in items if item['id'] == entry['id'])['active'] is False
    row.get_by_role('button', name='恢复', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已恢复参与抓取过滤')
    expect(block).to_contain_text('集采项目剔除名单（1 项在用）')


def test_mech_match_save_and_duplicate_rejected(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.goto(server + '/preview/rules')
    block = page.locator('.rules-block').nth(2)
    field = block.get_by_label('隔离项目的报表项目名')
    field.fill('别名验收项目 ｜ 新增报表名')
    block.get_by_role('row').filter(has_text='隔离项目').get_by_role('button', name='保存', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已保存机械报表项目匹配名称')
    items = page.request.get(server + '/api/m14/mech-match').json()['items']
    assert next(item for item in items if item['warehouse'] == '隔离验收仓库')['aliases'] == ['别名验收项目', '新增报表名']
    field.fill('长名报表名')
    block.get_by_role('row').filter(has_text='隔离项目').get_by_role('button', name='保存', exact=True).click()
    row = block.get_by_role('row').filter(has_text='隔离项目')
    expect(row.get_by_role('alert')).to_contain_text('报表项目「长名报表名」对应多个项目，请到规则配置修改匹配名称后重新预览')
    expect(field).to_have_value('长名报表名')
    items = page.request.get(server + '/api/m14/mech-match').json()['items']
    assert next(item for item in items if item['warehouse'] == '隔离验收仓库')['aliases'] == ['别名验收项目', '新增报表名']


def test_rules_writes_require_login(server, browser_page):
    page, _ = browser_page
    page.goto(server + '/preview/rules')
    expect(page.get_by_role('region', name='剔除规则列表')).to_be_visible()
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='＋ 增加规则')).to_be_disabled()
    expect(page.get_by_label('项目全名')).to_be_disabled()
    expect(page.get_by_label('隔离项目的报表项目名')).to_be_disabled()
    with httpx.Client(base_url=server) as client:
        first_id = client.get('/api/m14/rules').json()['rules'][0]['id']
        for method, path, payload in [
            ('POST', '/api/m14/rules', {'kind': 'biz_type', 'values': '未登录样例', 'meaning': ''}),
            ('PUT', '/api/m14/mech-match', {'warehouse': '隔离验收仓库', 'aliases': ['未登录样例']}),
            ('POST', '/api/m14/jc-ignore', {'name_full': '未登录样例', 'reason': ''}),
            ('DELETE', f'/api/m14/rules/{first_id}', None),
        ]:
            response = client.request(method, path, json=payload) if payload else client.request(method, path)
            assert response.status_code == 401, (method, path, response.status_code)
            assert '未登录' in response.json()['message']
        rules = client.get('/api/m14/rules').json()['rules']
        assert not any(row['values'] == '未登录样例' for row in rules)
        assert not any('未登录样例' in item['name_full'] for item in client.get('/api/m14/jc-ignore').json()['items'])
