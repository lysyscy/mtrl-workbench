"""看板待关联入口与通知书筛选使用相同范围；浏览器数据隔离。"""
from tests.ui_helpers import ui_page  # noqa: F401


def test_pending_navigation_link_refresh_and_reset(ui_page):
    p = ui_page
    p.evaluate('''() => {
      const seed={...NO[0],approve:100,paidApi:0,date:'2026-10-01'};
      NO=[{...seed,id:'101',code:'待关联甲'},
          {...seed,id:'102',code:'已关联乙'},
          {...seed,id:'103',code:'已付清丙',paidApi:100},
          {...seed,id:'104',code:'剔除丁',excl:true},
          {...seed,id:'105',code:'已撤单戊',revoked:true},
          {...seed,id:'106',code:'辅材己',cat:'辅材'},
          {...seed,id:'107',code:'历史待关联庚',date:'2024-01-01',astat:'未批'}];
      JCs.push(adaptJc({id:1,notice_ids:[102],project_key:'测试仓库',supplier:'测试供应商'}));
      fNt={month:'2026-10',cat:'机械',astat:'已批',stat:'全部',link:'已关联',projs:['旧项目'],q:'旧查询'};
      pickSet.add('106');VIEW='home';render();
    }''')
    assert p.locator('[data-todo="jcUnlinked"]').get_attribute('data-n') == '2'
    assert p.locator('[data-todo]').count() == 3
    for text in ('取数状态', '本月抓取', '占位行待扶正'):
        assert text not in p.locator('#view').inner_text()
    p.get_by_role('button', name='去关联合同', exact=True).click()
    assert p.locator('#fLink').input_value() == '未关联'
    assert p.evaluate('ntHit(fNt).map(n=>n.code)') == ['待关联甲', '历史待关联庚']
    assert p.evaluate('pickSet.size') == 0
    assert p.get_by_text('集采待关联 · 2 条', exact=False).is_visible()
    assert p.evaluate("fNt.month==='全部'&&fNt.projs.length===0&&fNt.q===''&&fNt.astat==='全部'")
    # Real save orchestration refreshes both sources before rendering the filtered list.
    p.evaluate('''async () => {
      reloadNotices=async()=>{};reloadM11=async()=>{};
      await jcLinkAct(async()=>{JCs[0].notice_ids.push(101);return {ok:true};},'已关联');
    }''')
    assert p.evaluate('ntHit(fNt).map(n=>n.code)') == ['历史待关联庚']
    assert p.get_by_text('集采待关联 · 1 条', exact=False).is_visible()
    p.get_by_role('button', name='清除此筛选', exact=True).click()
    assert p.locator('#fCat').input_value() == '全部'
    assert p.locator('#fLink').input_value() == '全部'
    assert p.evaluate('ntHit(fNt).length') == 4
    p.select_option('#fLink', '已关联')
    assert p.evaluate('ntHit(fNt).map(n=>n.code)') == ['待关联甲', '已关联乙']
    p.select_option('#fLink', '未关联')
    p.select_option('#fStat', '全部')
    assert p.evaluate('ntHit(fNt).map(n=>n.code)') == ['已付清丙', '历史待关联庚']
    p.select_option('#fCat', '辅材')
    assert p.locator('#fLink').input_value() == '全部'
    assert p.locator('#fLink').is_disabled()
    p.get_by_role('button', name='重置', exact=True).click()
    assert p.evaluate('ntHit(fNt).length') == 4
    p.evaluate('''async () => {
      ACT.homeJcUnlinked();
      await jcLinkAct(async()=>{JCs[0].notice_ids.push(107);return {ok:true};},'已关联');
    }''')
    assert p.evaluate('ntHit(fNt).length') == 0
    assert p.get_by_text('集采待关联 · 0 条', exact=False).is_visible()
    p.evaluate("VIEW='home';render()")
    assert p.locator('[data-todo="jcUnlinked"]').get_attribute('data-n') == '0'


def test_home_loads_contracts_and_drops_run_counts():
    from tests.shell_src import SHELL
    assert "home: ['付款通知书', '项目档案', '集采台账']" in SHELL
    assert 'homeRunCounts:' not in SHELL
