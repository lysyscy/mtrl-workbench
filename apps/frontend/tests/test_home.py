"""TAIL-421: home todos count from the real backend and land on exact scopes."""
import re
import subprocess
import sys

import pytest
from playwright.sync_api import expect

from test_preview import server, browser_page, login


@pytest.fixture(scope='module')
def preview_seed(make_preview_seed):
    def seed(env):
        code = """
from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import PaymentFlow
from app.mod11_jc.models import JcContract, JcPayment
from sqlalchemy import select
with session_scope() as s:
    p=s.scalar(select(Project).where(Project.disp=='隔离项目'))
    c=JcContract(project_id=p.id,contract_no='TAIL421-C',material_name='隔离集采合同',supplier='合成供应商',contract_amt=500)
    s.add(c);s.flush()
    rows=[dict(ph_id='TAIL421-OWN',bill_no='TAIL421-OWN',project_name='未匹配壳全名',ownership_id=None,category='material',doc_date='2026-09-05',approve_status='已批',amount_approved=100,stat_settle=100,stat_paid=0),
      dict(ph_id='TAIL421-JC',bill_no='TAIL421-JC',project_name=p.name_full,ownership_id=p.id,category='jc',jc_supplier='合成供应商',doc_date='2026-09-06',approve_status='已批',amount_approved=200,stat_settle=200,stat_paid=0),
      dict(ph_id='TAIL421-JCLINK',bill_no='TAIL421-JCLINK',project_name=p.name_full,ownership_id=p.id,category='jc',jc_supplier='合成供应商',doc_date='2026-09-07',approve_status='已批',amount_approved=300,stat_settle=300,stat_paid=0),
      dict(ph_id='TAIL421-VOID',bill_no='TAIL421-VOID',project_name=p.name_full,ownership_id=p.id,category='material',doc_date='2026-09-08',approve_status='已批',amount_approved=400,stat_settle=400,stat_paid=0,i8_revoked=True),
      dict(ph_id='TAIL421-VOIDPLAIN',bill_no='TAIL421-VOIDPLAIN',project_name=p.name_full,ownership_id=p.id,category='material',doc_date='2026-09-09',approve_status='已批',amount_approved=500,stat_settle=500,stat_paid=0,i8_revoked=True),
      dict(ph_id='TAIL421-EXCL',bill_no='TAIL421-EXCL',project_name='未匹配壳全名',ownership_id=None,category='material',doc_date='2026-09-10',approve_status='已批',amount_approved=600,stat_settle=600,stat_paid=0,excluded=True),
      dict(ph_id='TAIL421-JCPAID',bill_no='TAIL421-JCPAID',project_name=p.name_full,ownership_id=p.id,category='jc',jc_supplier='合成供应商',doc_date='2026-09-11',approve_status='已批',amount_approved=700,stat_settle=700,stat_paid=0)]
    for r in rows: s.add(PaymentNotice(**r))
    s.flush()
    linked=s.scalar(select(PaymentNotice).where(PaymentNotice.bill_no=='TAIL421-JCLINK'))
    void=s.scalar(select(PaymentNotice).where(PaymentNotice.bill_no=='TAIL421-VOID'))
    paid=s.scalar(select(PaymentNotice).where(PaymentNotice.bill_no=='TAIL421-JCPAID'))
    s.add(JcPayment(contract_id=c.id,source='notice',notice_id=linked.id,pay_date='',amount=0))
    # amount_paid in the API is the effective-flow total, so seed real flows:
    # VOID keeps a live payment (revoked but involved), JCPAID is paid in full.
    s.add(PaymentFlow(notice_id=void.id,project_id=p.id,amount=50,pay_date='2026-09-12',pay_method='现汇'))
    s.add(PaymentFlow(notice_id=paid.id,project_id=p.id,amount=700,pay_date='2026-09-13',pay_method='承兑'))
    print('SEED tail421 home todos ready',flush=True)
"""
        subprocess.run([sys.executable, '-X', 'utf8', '-c', code], env=env, check=True)
    return make_preview_seed(seed)


def todo_counts(page, server):
    """Recompute the three todo sets straight from the backend list API."""
    items = page.request.get(server + '/api/m03/notice-list?period=').json()['items']

    def live(row):
        return not row['is_excluded'] and (not row['is_revoked'] or float(row['amount_paid']) > 0 or row['has_link'])

    return {
        'live': [r['bill_no'] for r in items if live(r)],
        'ownership': [r['bill_no'] for r in items if live(r) and r['ownership_id'] is None],
        'jc': [r['bill_no'] for r in items if live(r) and r['category'] == 'jc' and not r['has_link'] and r['pay_status'] != '已付清'],
        'void': [r['bill_no'] for r in items if live(r) and r['is_revoked']],
    }


def tile(page, label):
    return page.locator('.home-tile').filter(has_text=label)


def open_home(page, server):
    page.goto(server + '/preview')


def test_todo_tiles_match_backend_and_land_on_exact_scopes(server, browser_page):
    page, _ = browser_page
    login(page, server)
    open_home(page, server)
    expected = todo_counts(page, server)
    assert (expected['ownership'], expected['jc'], expected['void']) == (['TAIL421-OWN'], ['TAIL421-JC'], ['TAIL421-VOID'])
    expect(page.get_by_role('heading', name='待办')).to_be_visible()
    expect(page.get_by_text('共 3 项需处理', exact=True)).to_be_visible()
    for label, key in [('归属待指定', 'ownership'), ('集采未关联合同', 'jc'), ('撤单但有牵涉', 'void')]:
        expect(tile(page, label).locator('.home-tile-count')).to_have_text(str(len(expected[key])))
    # The jc tile lands through plain filters; the visible row set equals the count set.
    page.get_by_role('link', name='去关联合同', exact=True).click()
    expect(page).to_have_url(re.compile(r'/notices\?todo=jc'))
    expect(page.locator('.notice-count')).to_contain_text('显示 1 条')
    expect(page.get_by_role('row').filter(has_text='TAIL421-JC')).to_be_visible()
    expect(page.get_by_role('row').filter(has_text='TAIL421-JCPAID')).to_have_count(0)
    expect(page.locator('.notice-pending-chip')).to_have_count(0)
    # The ownership tile lands with a removable scope chip; the single unowned row
    # carries its own 待指定归属 action.
    open_home(page, server)
    page.get_by_role('link', name='去指定归属', exact=True).click()
    expect(page).to_have_url(re.compile(r'todo=ownership'))
    expect(page.locator('.notice-pending-chip')).to_contain_text('只看待指定归属')
    expect(page.locator('.notice-count')).to_contain_text('显示 1 条')
    expect(page.get_by_role('row').filter(has_text='TAIL421-OWN')).to_be_visible()
    expect(page.get_by_role('button', name='待指定归属', exact=True)).to_be_enabled()
    page.get_by_role('button', name='清除待办筛选', exact=True).click()
    expect(page.locator('.notice-pending-chip')).to_have_count(0)
    # Clearing the scope chip falls back to the plain live view (seed + base rows).
    expect(page.locator('.notice-count')).to_contain_text(f"显示 {len(expected['live'])} 条")
    # The void tile lands on exactly the revoked rows that still have payments or links.
    open_home(page, server)
    page.get_by_role('link', name='去处理', exact=True).click()
    expect(page).to_have_url(re.compile(r'todo=void'))
    expect(page.locator('.notice-pending-chip')).to_contain_text('只看撤单有牵涉')
    expect(page.locator('.notice-count')).to_contain_text('显示 1 条')
    expect(page.get_by_role('row').filter(has_text='TAIL421-VOID')).to_contain_text('请先撤销付款 / 解绑关联')
    expect(page.get_by_role('row').filter(has_text='TAIL421-VOIDPLAIN')).to_have_count(0)
    # 1080p default reads fine; a narrow viewport keeps tiles and links reachable.
    open_home(page, server)
    expect(page.get_by_role('link', name='去指定归属', exact=True)).to_be_in_viewport()
    page.set_viewport_size({'width': 1000, 'height': 800})
    expect(page.get_by_role('link', name='去处理', exact=True)).to_be_in_viewport()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    # A normal user sees the same backend-driven counts.
    login(page, server, 'preview-user')
    open_home(page, server)
    assert todo_counts(page, server) == expected
    expect(tile(page, '集采未关联合同').locator('.home-tile-count')).to_have_text('1')


def test_todo_jump_clears_conflicting_old_filters(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.goto(server + '/preview/notices')
    from preview_select import open_popup
    open_popup(page, '付款状态').filter(has_text=re.compile('^已付清$')).click()
    page.get_by_label('通知书搜索', exact=True).fill('PREVIEW')
    expect(page.locator('.notice-count')).to_contain_text('显示 0 条')
    open_home(page, server)
    page.get_by_role('link', name='去关联合同', exact=True).click()
    expect(page.get_by_label('通知书搜索', exact=True)).to_have_value('')
    expect(page.locator('.notice-count')).to_contain_text('显示 1 条')
    expect(page.get_by_role('row').filter(has_text='TAIL421-JC')).to_be_visible()


def test_write_refreshes_home_count_with_backend(server, browser_page):
    page, _ = browser_page
    login(page, server)
    open_home(page, server)
    assert len(todo_counts(page, server)['jc']) == 1
    expect(tile(page, '集采未关联合同').locator('.home-tile-count')).to_have_text('1')
    page.goto(server + '/preview/notices?todo=jc')
    from preview_select import pick_popup_option
    page.get_by_label('TAIL421-JC分类', exact=True).click()
    pick_popup_option(page, '辅材')
    expect(page.locator('.notice-feedback').first).to_contain_text('已')
    items = {r['bill_no']: r for r in page.request.get(server + '/api/m03/notice-list?period=').json()['items']}
    assert items['TAIL421-JC']['category'] == 'material'
    open_home(page, server)
    assert todo_counts(page, server)['jc'] == []
    expect(tile(page, '集采未关联合同').locator('.home-tile-count')).to_have_text('0')
    expect(tile(page, '归属待指定').locator('.home-tile-count')).to_have_text('1')
    expect(page.get_by_text(re.compile('共 2 项需处理'), exact=True)).to_be_visible()


def test_home_states_loading_empty_error_and_anonymous(server, browser_page):
    page, _ = browser_page
    # Anonymous visitors read the same real counts; tiles stay usable read-only.
    page.goto(server + '/preview')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expected = todo_counts(page, server)
    for label, key in [('归属待指定', 'ownership'), ('集采未关联合同', 'jc'), ('撤单但有牵涉', 'void')]:
        expect(tile(page, label).locator('.home-tile-count')).to_have_text(str(len(expected[key])))
    page.get_by_role('link', name='去处理', exact=True).click()
    expect(page.locator('.notice-pending-chip')).to_contain_text('只看撤单有牵涉')
    expect(page.get_by_role('row').filter(has_text='TAIL421-VOID')).to_be_visible()
    # Empty state uses a directed substitute response (display branch only).
    page.route('**/api/m03/notice-list**', lambda route: route.fulfill(json={'items': []}))
    page.goto(server + '/preview/projects')
    page.goto(server + '/preview')
    expect(page.get_by_text('当前没有需要处理的事', exact=True)).to_be_visible()
    for label in ['归属待指定', '集采未关联合同', '撤单但有牵涉']:
        expect(tile(page, label).locator('.home-tile-count')).to_have_text('0')
    # A failed read shows the server message with an in-place retry.
    page.unroute('**/api/m03/notice-list**')
    page.route('**/api/m03/notice-list**', lambda route: route.fulfill(status=500, json={'message': '待办读取失败，请稍后重试。'}))
    page.goto(server + '/preview/projects')
    page.goto(server + '/preview')
    expect(page.get_by_role('alert')).to_contain_text('待办读取失败，请稍后重试。')
    page.unroute('**/api/m03/notice-list**')
    page.get_by_role('button', name='重读待办', exact=True).click()
    for label, key in [('归属待指定', 'ownership'), ('集采未关联合同', 'jc'), ('撤单但有牵涉', 'void')]:
        expect(tile(page, label).locator('.home-tile-count')).to_have_text(str(len(expected[key])))
