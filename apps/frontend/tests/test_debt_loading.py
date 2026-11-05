"""Debt overviews keep their own region while their read lands, fails or is refreshed."""

from playwright.sync_api import expect

from test_preview import browser_page, login, server  # noqa: F401 (fixtures)


def open_debt(page, address):
    """Open the debt page without waiting for network idle; a read may be held."""
    login(page, address)
    page.goto(address + '/preview/debt')
    expect(page.get_by_role('heading', name='欠款台账', exact=True)).to_be_visible()


def ledger_top(page):
    return page.locator('.ledger-card').bounding_box()['y']


def covered_by_notice(page):
    """Text actually painted under the summary notice; element boxes would overstate this badly."""
    return page.evaluate("""() => {
      const notice = document.querySelector('.debt-overviews .notice');
      if (!notice) return [];
      const box = notice.getBoundingClientRect();
      const hits = [];
      for (const node of document.querySelectorAll('.debt-overviews h2, .debt-overviews .bar-name, .debt-overviews .money, .debt-overviews .muted')) {
        const range = document.createRange();
        range.selectNodeContents(node);
        for (const rect of range.getClientRects()) {
          const width = Math.min(rect.right, box.right) - Math.max(rect.left, box.left);
          const height = Math.min(rect.bottom, box.bottom) - Math.max(rect.top, box.top);
          if (width > 0 && height > 0) hits.push([node.textContent.trim(), Math.round(width * height)]);
        }
      }
      return hits;
    }""")


def test_debt_overviews_report_their_own_read(server, browser_page):
    page, _ = browser_page
    pending = []
    page.route('**/api/m05/debt', lambda route: pending.append(route))
    open_debt(page, server)

    overviews = page.locator('.debt-overviews')
    expect(overviews).to_be_visible()
    # The region speaks for itself once, not once per summary card.
    expect(page.locator('.debt-overviews [role=status]')).to_have_count(1)
    # A read that has not landed is not an empty result.
    expect(page.locator('.debt-overviews .muted')).to_have_count(0)
    # Reads and measurement run in parallel, but the lower controls wait for their
    # actual vertical position instead of appearing and then being pushed down.
    expect(page.locator('.ledger-card')).to_be_hidden()
    assert page.locator('.ledger-card').bounding_box()['width'] > 0
    assert len(pending) == 1, len(pending)

    route = pending.pop()
    route.fulfill(response=route.fetch())
    expect(page.locator('.debt-overviews .read-placeholder')).to_have_count(0)
    expect(page.locator('.debt-overviews [role=status]')).to_have_count(0)
    expect(page.locator('.ledger-card')).to_be_visible()
    # The region now reports real rows or a genuine empty result, and nothing in between.
    rows = page.locator('.debt-overviews .bar-name').count()
    empty = page.locator('.debt-overviews .muted').count()
    assert rows + empty > 0, (rows, empty)


def test_debt_overviews_failure_does_not_move_the_ledger(server, browser_page):
    page, _ = browser_page
    held = []
    page.route('**/api/m05/debt', lambda route: held.append(route))
    open_debt(page, server)
    expect(page.locator('.ledger-card')).to_be_hidden()
    before = ledger_top(page)
    assert len(held) == 1, len(held)

    # The real path answers nothing here; this only decides that this read fails.
    held.pop().fulfill(
        status=503,
        content_type='application/json',
        body='{"detail": "汇总读取暂时失败"}',
    )

    failure = page.locator('.debt-overviews .notice')
    expect(failure).to_be_visible()
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    # A failed summary read is not an empty summary, and it is not a running read.
    expect(page.locator('.debt-overviews .muted')).to_have_count(0)
    expect(page.locator('.debt-overviews [role=status]')).to_have_count(0)
    # The failure reports inside its own region, so the ledger keeps its place.
    expect(page.locator('.ledger-card')).to_be_visible()
    assert abs(ledger_top(page) - before) < 1, (before, ledger_top(page))
    failure.get_by_role('button', name='重试读取').click()
    expect(page.locator('.debt-overviews [role=status]')).to_have_count(1)
    expect(page.locator('.ledger-card')).to_be_visible()
    assert len(held) == 1
    route = held.pop()
    route.fulfill(response=route.fetch())
    page.unroute('**/api/m05/debt')


def test_debt_overviews_keep_their_result_when_the_return_refresh_fails(server, browser_page):
    page, _ = browser_page
    open_debt(page, server)
    # Settle on the region's own outcome before sampling: only then is the first
    # result on screen and comparable with the result a failed refresh keeps.
    expect(page.locator('.debt-overviews:is([data-read-phase="ready"],[data-read-phase="empty"])')).to_have_count(1)
    first = page.locator('.debt-overviews .bar-name').first
    before_rows = page.locator('.debt-overviews .bar-name').count()
    before_text = first.inner_text() if before_rows else ''
    before_top = ledger_top(page)

    page.route(
        '**/api/m05/debt',
        lambda route: route.fulfill(
            status=503,
            content_type='application/json',
            body='{"detail": "汇总读取暂时失败"}',
        ),
    )
    page.locator('a[href="/preview/ledger"]').click()
    expect(page.locator('#page-title')).to_have_text('付款流水')
    page.locator('a[href="/preview/debt"]').click()
    expect(page.locator('#page-title')).to_have_text('欠款台账')

    failure = page.locator('.debt-overviews .notice')
    expect(failure).to_be_visible()
    expect(failure).to_contain_text('保留上次结果')
    # The result already on screen stays; only its freshness is reported as failed.
    assert page.locator('.debt-overviews .bar-name').count() == before_rows
    if before_rows:
        expect(first).to_have_text(before_text)
    # Reporting the failed refresh adds no layout row above the ledger.
    assert abs(ledger_top(page) - before_top) < 1, (before_top, ledger_top(page))
    # And the kept result stays readable: the notice never prints over a heading or a value.
    assert covered_by_notice(page) == [], covered_by_notice(page)


def test_debt_overviews_failure_never_covers_a_heading_or_a_value(server, browser_page):
    """A narrow window is where a summary failure used to print on top of the third card."""
    page, _ = browser_page
    page.set_viewport_size({'width': 1280, 'height': 720})
    held = []
    page.route('**/api/m05/debt', lambda route: held.append(route))
    with page.expect_request(lambda request: '/api/m05/debt' in request.url):
        open_debt(page, server)
    expect(page.locator('.ledger-card')).to_be_hidden()
    assert len(held) == 1, len(held)

    held.pop().fulfill(
        status=503,
        content_type='application/json',
        body='{"detail": "汇总读取暂时失败"}',
    )
    failure = page.locator('.debt-overviews .notice')
    expect(failure).to_be_visible()

    # The lane owns the notice: it is the region's own line, not something floating over the cards.
    expect(page.locator('.debt-overviews-status .notice')).to_have_count(1)

    # Real text rectangles, not element boxes: a heading box spans the whole card, so only the
    # painted glyph runs can show whether a value is actually covered.
    covered = covered_by_notice(page)
    assert covered == [], covered

    # Retry stays reachable even when the message is long.
    retry = page.get_by_role('button', name='重试读取')
    expect(retry).to_be_visible()
    box = retry.bounding_box()
    assert page.evaluate(
        """([x, y]) => {
          const node = document.elementFromPoint(x, y);
          return Boolean(node && node.closest('button'));
        }""",
        [box['x'] + box['width'] / 2, box['y'] + box['height'] / 2],
    )
