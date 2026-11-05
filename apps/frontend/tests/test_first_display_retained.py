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


def test_rules_grids_do_not_paint_through_the_retained_page(server, browser_page):
    """A hidden page must suppress descendant painting while retaining its layout."""
    page, _ = browser_page
    login(page, server)
    page.locator('a[href="/preview/rules"]').click()
    expect(page.locator('.rules-page .business-grid[data-layout-state="ready"]')).to_have_count(3)
    page.locator('a[href="/preview/users"]').click()
    expect(page.locator('#page-title')).to_have_text('用户管理')
    expect(page.locator('.users-table[data-layout-state="ready"], .users-table .business-grid[data-layout-state="ready"]')).to_have_count(1)
    state = page.locator('.rules-page').evaluate("""node => {
      const retained = node.closest('.page-view');
      const rect = retained.getBoundingClientRect();
      return {hidden: retained.hidden, inert: retained.inert, width: rect.width, height: rect.height,
        visibleGrids: [...node.querySelectorAll('.business-grid')]
          .filter(grid => getComputedStyle(grid).visibility === 'visible')
          .map(grid => grid.getAttribute('aria-label'))};
    }""")
    assert state['hidden'] and state['inert'], state
    assert state['width'] > 0 and state['height'] > 0, state
    assert state['visibleGrids'] == [], state


def test_read_grid_uses_the_current_filter_after_first_font_wait(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='机械费', exact=True).click()
    expect(page.locator('.mechanical-grid')).to_have_attribute('data-layout-state', 'ready', timeout=30000)
    page.evaluate("""() => {
      const load = document.fonts.load.bind(document.fonts);
      window.__readGridHeld = false;
      window.__readGridReleased = false;
      const gate = new Promise(resolve => { window.__releaseReadGrid = () => {
        window.__readGridReleased = true; resolve();
      }; });
      document.fonts.load = async (...args) => {
        if (document.querySelector('.mechanical-work') && !window.__readGridReleased) {
          window.__readGridHeld = true; await gate;
        }
        return load(...args);
      };
    }""")
    page.get_by_role('button', name='核对工作台', exact=True).click()
    page.wait_for_function('window.__readGridHeld')
    table = page.get_by_role('region', name='当前累计核对', exact=True, include_hidden=True)
    before = table.locator('.ag-row[row-id]').evaluate_all('rows => rows.map(row => row.getAttribute("row-id"))')
    assert before, '真实核对数据未覆盖准备期间移除行的场景'
    page.get_by_role('group', name='核对筛选').get_by_role('button', name='取数变化', exact=False).click()
    page.wait_for_function("""previous => {
      const node = document.querySelector('[aria-label="当前累计核对"]');
      const current = [...node.querySelectorAll('.ag-row[row-id]')].map(row => row.getAttribute('row-id'));
      return previous.some(id => !current.includes(id));
    }""", arg=before)
    page.evaluate('window.__releaseReadGrid()')
    expect(table).to_have_attribute('data-layout-state', 'ready', timeout=30000)
    expect(table).to_be_visible()
