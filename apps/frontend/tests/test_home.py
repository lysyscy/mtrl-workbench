"""Actual todo sets and navigation; no fixed count or substitute business payload."""
import re
from playwright.sync_api import expect
from test_preview import server, browser_page, login


def todo_counts(page, server):
    items = page.request.get(server+'/api/m03/notice-list?period=').json()['items']
    live = [r for r in items if not r['is_excluded'] and (not r['is_revoked'] or float(r['amount_paid'])>0 or r['has_link'])]
    return {'ownership':sum(r['ownership_id'] is None for r in live),
            'jc':sum(r['category']=='jc' and not r['has_link'] and r['pay_status']!='已付清' for r in live),
            'void':sum(r['is_revoked'] for r in live)}


def test_real_todo_counts_and_scope_links(server, browser_page):
    page, _ = browser_page
    login(page,server)
    expected = todo_counts(page,server)
    for label,key,link in [('归属待指定','ownership','去指定归属'),('集采未关联合同','jc','去关联合同'),('撤单但有牵涉','void','去处理')]:
        page.goto(server+'/preview')
        tile=page.locator('.home-tile').filter(has_text=label)
        expect(tile.locator('.home-tile-count')).to_have_text(str(expected[key]))
        tile.get_by_role('link',name=link,exact=True).click()
        expect(page).to_have_url(re.compile('todo='+key))
        expect(page.locator('.notice-count')).to_contain_text('显示 '+str(expected[key])+' 条')


def test_anonymous_home_uses_real_counts_and_narrow_links(server,browser_page):
    page,_=browser_page
    page.goto(server+'/preview')
    expected=todo_counts(page,server)
    for label,key in [('归属待指定','ownership'),('集采未关联合同','jc'),('撤单但有牵涉','void')]:
        expect(page.locator('.home-tile').filter(has_text=label).locator('.home-tile-count')).to_have_text(str(expected[key]))
    page.set_viewport_size({'width':1000,'height':800})
    expect(page.get_by_role('link',name='去处理',exact=True)).to_be_in_viewport()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
