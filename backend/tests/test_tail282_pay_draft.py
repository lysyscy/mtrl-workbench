"""`TAIL-282`：付款通知书页「付款金额」（本次拟付）的**会话草稿**跨重拉存活、按事实作废。

**它守什么**（票面验收）：手改「付款金额」之后，接着匹配 / 保存 / 采用 / 放弃集采供应商
（四条路最后都走 `reloadNotices()` —— 它 `NO=items.map(adaptNotice)` **整体换行对象**），
改过的那个数**不许被冲回默认值**；真付过款 / 撤销过款 / 审批额或已付额变了 ⇒ 旧草稿**作废**、
回「审批金额 − 已付金额」；`0` 是有效值；供应商写失败不清草稿；整页刷新即散（不写 Storage / 库）。

**为什么必须是真浏览器**：故障本体是"壳的内存态挂在会被整体替换的行对象上" ——
离线静态断言**看不见**它（旧实现那行 `n.payOv` 在源码里完全正常，本文件是真机反例的唯一载体）。
⇒ 复用 `test_shell_ui_workflow.py::ui_page` 的隔离真机 fixture；
⚠️ 只**替换 `API.notices()` 的回包**（模拟后端真事实），⛔ 不整体覆写 `reloadNotices()`
—— 那样会把被测函数绕开，变成"自己测自己"。
"""

from __future__ import annotations

from tests.acc_plugin import acc
from tests.test_shell_ui_workflow import ui_page  # noqa: F401  ← 真浏览器隔离 fixture（唯一出处，⛔ 别在本件另起一套）

#: 两行通知书：A（审批 1000 · 已付 200 ⇒ 派生 800）· B（审批 500 · 已付 100 ⇒ 派生 400）
ROWS = [
    {"id": "101", "code": "DOC-A", "doc": "单据A", "approve": 1000, "paid": 200},
    {"id": "102", "code": "DOC-B", "doc": "单据B", "approve": 500, "paid": 100},
]

#: 装两行列表 + 把 `API.notices()` 换成"后端真事实"替身（`window.SRV` 就是那份事实）。
_SETUP = """(rows) => {
  window.SRV = rows.map(r => ({
    notice_id: Number(r.id), doc_date: '2026-10-02', bill_no: r.code, project_name: '测试项目全名',
    category_label: '辅材', amount_approved: String(r.approve), pay_amount: String(r.approve),
    stat_settle: '0.00', stat_paid: '0.00', amount_paid: String(r.paid), approve_status: '已批',
    is_excluded: false, jc_supplier: '', edited_fields: [], is_manual: false, is_revoked: false,
    has_effective_flow: false, has_any_flow: false, is_overpaid: false, ownership_id: null,
    bill_name: r.doc, payee: '', input_by: '', biz_type: '',
  }));
  API.notices = async () => ({items: JSON.parse(JSON.stringify(window.SRV))});
  NO = window.SRV.map(adaptNotice);
  FLs.splice(0); fNt.month = '全部'; fNt.stat = '全部'; VIEW = 'm03'; render();
}"""


def _setup(page, rows=ROWS):
    page.evaluate(_SETUP, rows)


def _eff(page, nid):
    return page.evaluate(f"payEff(NO.find(n=>n.id==='{nid}'))")


def _over(page, nid):
    return page.evaluate(f"payOver(NO.find(n=>n.id==='{nid}'))")


@acc()
def test_手改拟付后重拉列表草稿不丢且按通知书记(ui_page):
    """票面 ① ② ④：四条供应商路径最后都走 `reloadNotices()` ⇒ 草稿必须活过**整体换行对象**；
    两行互不串值；`0` 是有效覆盖；供应商写失败（`ok:false`）不碰草稿。"""
    p = ui_page
    _setup(p)
    # 手改走真实动作入口（`editss`），⛔ 不是直接写内存
    p.evaluate("() => { ACT.editss({dataset:{id:'101',k:'pay'},value:'300'});"
               " ACT.editss({dataset:{id:'102',k:'pay'},value:'120'}); }")
    assert _eff(p, "101") == 300 and _eff(p, "102") == 120

    # 供应商**写失败**（后端可预期拒绝的常态：HTTP 200 + ok:false）⇒ 草稿不动
    p.evaluate("async () => { API.jcSupplier = async () => ({ok:false, message:'这行不能改供应商'});"
               " await jcLinkAct(() => API.jcSupplier({})); }")
    assert _eff(p, "101") == 300, "供应商写失败后草稿被清了"

    # 供应商**写成功** ⇒ 内部 `reloadNotices()`（新行对象）⇒ 草稿必须还在
    p.evaluate("async () => { await reloadNotices(); }")
    assert p.evaluate("NO.map(n=>n.id).join(',')") == "101,102", "重拉没换过行对象（本用例就失去意义了）"
    assert _eff(p, "101") == 300, "手改的拟付被「整体换行对象」冲回默认值了"
    assert _eff(p, "102") == 120, "两张通知书的草稿串到一起了"
    assert _over(p, "101") is True, "覆盖标记丢了（界面不会再显示「本次会话已临时覆盖」）"

    # 0 是**有效覆盖**（= 本次不付）⇒ 重拉后仍是 0，且行内判成不可付
    p.evaluate("() => { ACT.editss({dataset:{id:'101',k:'pay'},value:'0'}); }")
    p.evaluate("async () => { await reloadNotices(); }")
    assert _eff(p, "101") == 0, "0 被当成「没有覆盖」丢掉了"
    assert _over(p, "101") is True
    assert p.evaluate("ntPayBlock(NO.find(n=>n.id==='101')).indexOf('本次应付为 0')>=0") is True, \
        "0 拟付没有被行内判成不可付"
    assert _eff(p, "102") == 120, "改一行影响了另一行"


@acc()
def test_审批额或已付额变化后旧草稿作废(ui_page):
    """票面 ⑤：真付款 / 撤销 / 审批额变 / 已付额变 ⇒ 旧草稿**失效**并按最新事实重算 ——
    免得拿一个过期数字去付款。"""
    p = ui_page
    _setup(p)
    p.evaluate("() => { ACT.editss({dataset:{id:'101',k:'pay'},value:'300'}); }")

    # ① 后端已付事实 200 → 400（真付款 / 撤销过款同一条路：`amount_paid` 变了）
    p.evaluate("() => { window.SRV[0].amount_paid = '400.00'; }")
    p.evaluate("async () => { await reloadNotices(); }")
    assert _eff(p, "101") == 600, "已付事实变了，旧草稿还留着（拿过期金额付款 = 事故）"
    assert _over(p, "101") is False, "事实变了，覆盖标记没作废"
    assert _eff(p, "102") == 400, "另一行的派生默认被连带改坏"

    # ② 审批金额变（本地手改审批额走的就是改行上 `n.approve` 这条）
    p.evaluate("() => { ACT.editss({dataset:{id:'101',k:'pay'},value:'111'});"
               " NO.find(n=>n.id==='101').approve = 900; }")
    assert _eff(p, "101") == 500, "审批额变了，旧草稿没作废"
    assert _over(p, "101") is False


@acc()
def test_付款成功后即使列表刷新失败也作废草稿(ui_page):
    """票面 ⑤ 的硬边界：**写成功是强事实信号** —— 付款成功那一瞬就该作废该单草稿，
    ⛔ 不能等 `reloadNotices()`（它可能失败 ⇒ 过期金额留在页面上，用户再付款看到的数是错的）。
    ⚠️ 同时守"不许伪造新事实"：读回没成功 ⇒ 仍按**已读到的事实**算，不凭空减已付。"""
    p = ui_page
    _setup(p)
    p.evaluate("""() => {
      ACT.editss({dataset:{id:'101',k:'pay'},value:'300'});
      API.batchPay = async () => ({ok:true, created:[101], count:1, message:'已生成 1 笔付款流水'});
      API.notices = async () => { window.__ntFail = 1; throw new Error('列表读不回来'); };
      pickSet.clear(); pickSet.add('101'); ACT.batchPay();
    }""")
    p.click('[data-act="batchPayOk"]')
    p.wait_for_function("window.__ntFail")
    assert _over(p, "101") is False, "付款成功后旧草稿还留在页面上"
    assert _eff(p, "101") == 800, \
        "读回失败时不得伪造新的已付金额（应按已读到的事实算）"
    assert _over(p, "102") is False and _eff(p, "102") == 400, "本次付款之外的行被牵连"


@acc()
def test_撤销成功后即使刷新失败也作废草稿且回执仍在(ui_page):
    """票面 ⑤＋`TAIL-281` 不回归：撤销成功 ⇒ 该通知书草稿作废；
    ⚠️ 刷新失败**不等于**撤销失败 —— 成功回执必须照样显示。"""
    p = ui_page
    _setup(p)
    p.evaluate("""() => {
      ACT.editss({dataset:{id:'101',k:'pay'},value:'300'});
      FLs.splice(0, FLs.length, {id:'F1', nid:'101', date:'2026-10-02', amt:200, method:'现汇',
        remark:'', op:'', voided:false, reason:'', projKey:'', proj:'', doc:''});
      API.flowRevoke = async () => ({ok:true, message:'已撤销', jc_effect:null});
      API.flows = async () => { window.__flFail = 1; throw new Error('流水读不回来'); };
      ACT.revDlg({dataset:{fid:'F1'}});
    }""")
    p.fill("#rReason", "收款单位变更，需重付")
    p.click('[data-act="revOk"]')
    p.wait_for_function("window.__flFail")
    assert _over(p, "101") is False, "撤销成功后旧草稿还留在页面上"
    assert "已撤销流水" in p.inner_text("body"), "刷新失败把「撤销成功」的回执也吞了（TAIL-281 的验收）"
