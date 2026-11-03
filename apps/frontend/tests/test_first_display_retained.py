"""A retained grid must let the next page open and preserve its own scroll position."""
from playwright.sync_api import expect
from test_preview import browser_page, login, server  # noqa: F401 (fixtures)


def test_retained_page_first_display_and_return(server, browser_page, disposable):
    page, context = browser_page
    # Throttle to make the original hidden-grid contention deterministic.
    context.new_cdp_session(page).send('Emulation.setCPUThrottlingRate', {'rate': 4})
    page.set_viewport_size({'width': 1280, 'height': 480})
    login(page, server)
    projects = page.locator('.page-view').filter(has=page.locator('.projects-page'))
    expect(projects).to_be_visible(timeout=30000)
    expect(projects.locator('.ag-row').first).to_be_visible(timeout=30000)
    before = projects.evaluate('''view => {
        view.scrollTop = view.scrollHeight;
        return {width: view.clientWidth, height: view.clientHeight, scroll: view.scrollTop};
    }''')
    assert before['scroll'] > 0, 'The real project page must exercise outer scrolling'

    page.locator('a[href="/preview/notices"]').click()
    expect(page.locator('#page-title')).to_have_text('付款通知书', timeout=30000)
    expect(page.locator('.notices-page')).to_have_count(1, timeout=15000)
    expect(page.locator('.page-loading')).to_have_count(0, timeout=15000)
    expect(page.locator('.page-view:not([hidden])')).not_to_have_attribute('inert', '')
    expect(projects).to_be_hidden()
    expect(projects).to_have_attribute('inert', '')
    expect(projects).to_have_attribute('aria-hidden', 'true')
    retained = projects.evaluate('view => ({width:view.clientWidth,height:view.clientHeight,scroll:view.scrollTop})')
    assert retained == before, 'Hiding a retained page must preserve its content box and scroll'

    page.locator('a[href="/preview/projects"]').click()
    expect(projects).to_be_visible(timeout=15000)
    expect(page.locator('.page-loading')).to_have_count(0)
    assert projects.evaluate('view => view.scrollTop') == before['scroll']
