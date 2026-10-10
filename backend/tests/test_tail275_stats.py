"""付款统计用真实组装输出验证选桶、金额、笔数与台账日期。"""
from datetime import date
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import PaymentFlow
from app.mod05_flow.service import build_stats, notice_debt_views
from app.mod05_flow.domain import monthly_aggregate, CATEGORY_MATERIAL
from tests.acc_plugin import acc
from tests.m05_helpers import FakeSession, make_notice_row, make_flow, make_project
from tests.test_shell_ui_workflow import ui_page  # noqa: F401


@acc()
def test_empty_payment_window_keeps_time_controls(ui_page):
    st = build_stats(FakeSession({Project: [], PaymentNotice: [], PaymentFlow: []}),
                     granularity='week', today=date(2026, 10, 10))
    assert not st['left'] and st['buckets']
    ui_page.evaluate('''st => {
      BOOTING=true; VIEW='m05'; pst.gran='周'; M05.stats=st; render();
    }''', st)
    card = ui_page.locator('.card').filter(has=ui_page.locator('h4', has_text='付款统计'))
    assert card.locator('[data-id="pstBucket"]').count() == 1
    assert card.locator('[data-id="pstAxis"]').count() == 1
    assert '窗口合计' in card.inner_text()


@acc()
def test_week_picker_refetches_early_and_cross_quarter_weeks(ui_page):
    s = FakeSession({Project: [], PaymentNotice: [], PaymentFlow: []})
    for week in ('2026-06-29', '2026-07-06', '2026-08-03', '2026-09-28'):
        st = build_stats(s, granularity='week', year=2026, quarter=3,
                         today=date(2026, 10, 10), bucket=week)
        assert week in st['buckets'] and len(st['buckets']) <= 8
        ui_page.evaluate('''st => {
          BOOTING=true; VIEW='m05'; pst.gran='周'; pst.ym='2026-09-28';
          pst.q='2026Q4'; mp.wq='2026Q3'; M05.stats=st;
        }''', st)
        ui_page.evaluate("v=>ACT.mpPick({dataset:{scope:'pstb',m:'周',val:v}})", week)
        assert ui_page.evaluate('m05Params().bucket') == week
        assert ui_page.evaluate('m05Params().quarter') == 3
        assert ui_page.evaluate('pstData().bk') == week


@acc()
def test_selected_bucket_window_total_count_and_ledger(ui_page):
    s = FakeSession({Project: [make_project(11, '甲仓', '甲项目')],
        PaymentNotice: [make_notice_row(1, doc_date='2026-08-03', paid='150'),
                        make_notice_row(2, doc_date='2026-08-04', paid='80'),
                        make_notice_row(3, doc_date='2026-01-04', paid='900')],
        PaymentFlow: [make_flow(1, notice_id=1, amount='100', pay_date='2026-09-02'),
                      make_flow(2, notice_id=2, amount='80', pay_date='2026-08-03'),
                      make_flow(3, notice_id=3, amount='900', pay_date='2026-01-03')]})
    st = build_stats(s, granularity='month', today=date(2026, 10, 10))
    assert st['total'] == '1080.00' and sum(map(float, st['right'])) == 180
    p = ui_page
    p.evaluate('''st => {
      BOOTING=true; VIEW='m05'; pst.gran='月'; pst.ym='2026-09'; pst.year=2026;
      M05.stats=st; FLs.splice(0); FLs.push({date:'2026-09-02',amt:999,voided:false});
      render();
    }''', st)
    pd = p.evaluate('pstData()')
    assert pd['bk'] == '2026-09' and pd['bkTotal'] == 100 and pd['bkCnt'] == 1
    assert pd['total'] == 180 and pd['byPj'] == [['甲仓', 100]]
    text = p.locator('.card').filter(has=p.locator('h4', has_text='付款统计')).inner_text()
    assert '100.00' in text and '180.00' in text and '1 笔' in text
    p.evaluate("ACT.mpPick({dataset:{scope:'pstb',m:'月',val:'2026-08'}})")
    pd = p.evaluate('pstData()')
    assert pd['bk'] == '2026-08' and pd['bkTotal'] == 80 and pd['bkCnt'] == 1
    assert pd['total'] == 180 and pd['byPj'] == [['甲仓', 80]]
    assert monthly_aggregate(notice_debt_views(s), CATEGORY_MATERIAL, 11)['2026-08']['pay'] == 230
    p.evaluate("ACT.mpPick({dataset:{scope:'pstb',m:'月',val:'2020-01'}})")
    assert p.evaluate('pstData().bk') in st['buckets']
    assert '为了监控拖了很久的付款' in p.locator('body').inner_text()
    assert p.evaluate('LED_THEAD').count('按单据日期') == 1


@acc()
def test_week_selection_uses_payment_dates(ui_page):
    p = ui_page
    p.evaluate('''() => {
      BOOTING=true; VIEW='m05'; pst.gran='周'; pst.ym='2026-08-31';
      M05.stats={granularity:'week',year:2026,quarter:3,buckets:['2026-08-31','2026-09-07'],
        right:['50.00','0.00'],counts:[2,0],total:'950.00',
        left:[{key:'甲仓',label:'甲项目',cells:['50.00','0.00']}]}; render();
    }''')
    pd = p.evaluate('pstData()')
    assert pd['bk'] == '2026-08-31' and pd['bkCnt'] == 2 and pd['total'] == 50
    assert pd['bkLabel'] == '08-31 ~ 09-06'
    p.evaluate("ACT.mpPick({dataset:{scope:'pstb',m:'周',val:'2026-09-07'}})")
    assert p.evaluate('pstData().bkTotal') == 0
