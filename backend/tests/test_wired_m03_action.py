"""前端壳「付款通知书**行内动作**」的离线断言 —— `§19` 批 4 **小轮③**。

⭐ 覆盖 `tests/test_notice_action_page.py` 的 8 条（**全部是绑定判据点**）：这一页原来走**服务端渲染**
（`notice_page.render_notice_page` / `render_trace_page`），断言全都抠 HTML（`_row_of(html, …)`）。
旧页删除（授权 `D18`）⇒ **形态那半边改指新壳**（⛔ 判据不删）：

  · `ACC-PAY-MANUAL-001/001-06` 操作列：**i8 抓取行不给编辑/删除**，只有手动行才有
  · `ACC-PAY-ACTION-001/001-01` 有生效流水才出「撤销付款」（1 条 ⇒ 就地开撤销窗、原因必填）
  · `ACC-PAY-ACTION-001/001-02` 多条生效流水 ⇒ 跳流水页**只筛这一单**、**不提供一键撤全部**
  · `ACC-PAY-ACTION-001/001-04` 查看关联 = **纯只读**，流水子表**含已撤销**（带原因）
  · `ACC-PAY-ACTION-001/001-05` 查看关联**不臆造集采取值**（没有就给说明，不给假值）
  · `ACC-PAY-MANUAL-001/001-07` 草稿行：「统计结算」**恒 0 且不可改**、录入人不由手填
  · `ACC-PAY-STAT-001/001-08` 统计两列是**行内可改格**；没手改过 ⇒ **不黄底**
  · `ACC-PAY-STAT-001/001-09` 手改过的格子**黄底**，判据 = **留痕**

⚠️ 只读壳源码（`SHELL`）；断言一律在**切片**里找（`_act_cell()` / `_draft_row()` / `_trace()`），
不到全文里撞 —— 否则别的页同款写法会**假命中**。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛


def _slice(start: str, end: str, *, what: str) -> str:
    i = SHELL.find(start)
    assert i >= 0, f"壳里找不到{what}的起点：{start!r}"
    j = SHELL.find(end, i)
    assert j > i, f"找不到{what}的终点：{end!r}"
    return SHELL[i:j]


def _act_cell() -> str:
    """「操作列」出口 `ntActCell`。"""
    return _slice("const ntActCell=n=>{", "return L.length?", what="操作列出口")


def _draft_row() -> str:
    """草稿行出口 `ntDraftRow`。"""
    return _slice("const ntDraftRow=()=>{", "</tr>`; };", what="草稿行出口")


# ⚠️ 2026-10-11（`TAIL-281` 改形后同步）：`ntRevoke` / `ntTrace` **都变成了 `async`**
#    （它们各自要先 `await ntLoadFlows(...)` / `reloadM11()` 才能取到真数据）
#    ⇒ 起点锚从 `xxx:t=>{` 改成 `xxx:async t=>{`。**判词一字未改**，只是指回现在的真身。
#    （这两条红是 `TAIL-281` 留下的既有测试腐化：本轮用 HEAD 版壳复跑证实与 TAIL-282/283 无关。）


def _revoke() -> str:
    """「撤销付款」处理器 `ntRevoke`。"""
    return _slice("ntRevoke:async t=>{", "ntTrace:async t=>{", what="撤销付款处理器")


def _trace() -> str:
    """「查看关联」处理器 `ntTrace`（⭐ `TAIL-281` 起它由**集采列的「已关联」标签**打开）。"""
    return _slice("ntTrace:async t=>{", "/* —— MOD-05 —— */", what="查看关联处理器")


def _flow_table() -> str:
    """两个弹窗**共用**的流水子表渲染 `ntFlowTable`（⭐ `TAIL-281` 把两处收成一份）。

    ⚠️ 为什么要单独取它：`TAIL-281` 之后「流水子表」不再内联在 `ntTrace` 里
    ⇒ 只切 `ntTrace` 那段会**看不到表**，「含已撤销 / 带原因 / 只读」这几条会变成假绿。
    """
    return _slice("function ntFlowTable(flows){", "\n}", what="流水子表渲染")


def _nt_row_save() -> str:
    """「保存手动行」处理器 `ACT.ntRowSave`。"""
    return _slice("ntRowSave:()=>{", "/* 手动行的「审批金额」表内可改", what="手动行保存处理器")


def _sup_accept() -> str:
    """「采用自动匹配值」处理器 `ACT.supAccept`。"""
    return _slice("supAccept:async t=>{", "supReject:async t=>{", what="采用处理器")


@acc()
def test_壳里手动行保存必须把审批状态发出去():
    """⭐ 2026-10-08 BUG 钉子（前端那一半）：草稿行**有**审批状态下拉（默认「已批」），
    可它原先**只留在草稿里、从不发**给后端 ⇒ 落库空值 ⇒ 列表显示为空 ⇒ 付不了款。

    ⚠️ 断的是**发送**这一步 —— 断言必须钉住 `body` 里真的有它（只断言"下拉存在"会假绿）。
    """
    reg = _nt_row_save()
    assert "approve_status:f.astat" in reg, \
        "保存时没把审批状态发给后端（草稿里选的值到不了库里 ⇒ 列表显示为空、付不了款）"
    # 值必须有兜底：草稿默认项是下拉第一项（optsOf 在 cur 为空时不加 selected）⇒ `||'已批'` 是主力路径
    assert "astat:naD.astat||'已批'" in reg, "审批状态没了兜底（草稿未显式选中时会发空串）"


def _sup_match_run() -> str:
    """「自动匹配」处理器 `ACT.supMatchRun`。"""
    return _slice("supMatchRun:async t=>{", "supPick:t=>{", what="自动匹配处理器")


# ---------------------------------------------------------------- 集采供应商：采用

@acc()
def test_壳里采用自动匹配值_取值必须来自待确认标记_不得读列表空值():
    """⭐ 2026-10-08 BUG 钉子：「自动匹配」命中后点「采用」，**供应商这一行没变**。

    根因在**两处**，缺一都不会犯：
      ① 后端 `NoticeRow` 漏装 `jc_supplier` ⇒ `notice-list` 每行恒回空串 ⇒ `n.sup` 恒空；
      ② 「采用」的值取自 `n.sup` ⇒ 提交 `supplier:''` ⇒ **把刚匹配上的值清空**，
         而后端对空串照样回 `ok:true` ⇒ 界面上只弹一句绿色回执，看着像"点了没反应"。
    ⇒ 这里钉住「采用」只认 `SUP_SUG[n.id]`（= 预填时真正落库的那个值），⛔ 不读 `n.sup`。
    """
    a = _sup_accept()
    assert "const v=String(SUP_SUG[n.id]||'').trim();" in a, \
        "「采用」改成读别的来源了（⛔ 不得取 `n.sup`：那是列表读回值，读链路一偏就会提交空串）"
    # ⛔ 只查**取值表达式**（注释里可以、也应该写明"不许取 n.sup"）
    assert "String(n.sup" not in a, "「采用」又改回读 `n.sup` 了（那正是提交空串、把值清空的来源）"
    # ⚠️ 空值必须**拒绝**而不是当采纳值提交（否则又是一次"采纳＝清空"）
    assert "if(!v) return toast(" in a, "「采用」没有对空值设闸 —— 空值提交下去等于清空该字段"
    # ⚠️ 标记要在 `jcLinkAct` **之前**清：它内部会 reload + render，事后再清界面不更新（看着像没生效）
    di, ci = a.find("delete SUP_SUG[n.id];"), a.find("await jcLinkAct(")
    assert 0 <= di < ci, "「采用」的待确认标记仍写在 `jcLinkAct` 之后 ⇒ 界面还显示「待确认 + 采用」"


@acc()
def test_壳里自动匹配命中一家_预填后当场重画出采用按钮():
    """预填成功后必须**当场**出现「采用 / 不采用」—— 标记就是这两个按钮的渲染条件（`supAutoCell`）。

    ⇒ 判据 = **标记与 `render()` 的先后**：`jcLinkAct` 内部已经 render 过一次，
    标记若在它**之后**才落而不补一次 render，这一轮就画不出按钮（要点别的才冒出来）。
    """
    m = _sup_match_run()
    si, ci = m.find("SUP_SUG[n.id]=hit;"), m.find("await jcLinkAct(")
    assert 0 <= si, "1 家命中后没标「待确认」（`SUP_SUG`）⇒ 没有「采用 / 不采用」可点"
    assert 0 <= ci, "预填没走 `jcLinkAct`（那才是落库 + 双侧重拉）"
    si2, ri = m.find("SUP_SUG[n.id]=hit;", ci), m.find("render();", si if si > ci else 0)
    assert si2 >= 0 and si2 < ri, \
        "标记写在最后一次 render 之后 ⇒ 这一轮画不出「采用」按钮（看着像「匹配上了但没法采用」）"


# ---------------------------------------------------------------- 操作列


@acc("ACC-PAY-MANUAL-001", "001-06")
def test_壳里操作列_i8行无编辑删除_手动行才有():
    """⛔ 铁律：**i8 抓取行**不提供「编辑 / 删除」（源数据只读）；只有**手动行**才有（§4.2.6）。

    新壳：编辑/删除按钮在 `if(n.manual)` 分支里 ⇒ 抓取行**结构上拿不到**这两个入口。
    """
    reg = _act_cell()
    assert "if(n.manual) L.push(" in reg, "编辑/删除没有绑在「手动行」上（i8 抓取行会拿到写入口）"
    assert 'data-act="ntEdit"' in reg and 'data-act="ntDel"' in reg, "手动行的编辑/删除按钮没了"
    # 顺序固定：手动行徽标 → 编辑/删除 → 撤销付款 → 查看流水（i8 行就是后两个）
    # ⚠️ 2026-10-11 同步（`TAIL-281` 改形，判词不变）：最后那个入口由「查看关联」(`ntHasLink`)
    #   换成**「查看流水」(`n.hasAnyFlow` = 有任意流水，含已撤销才出)**；
    #   「查看关联 · 完整合同」搬去**集采实际供应商列**的「已关联」标签上（`proj.js::jcLinkCell`）。
    #   ⚠️ 撤销付款的条件仍是 `ntHasFlow`（**有生效**流水）—— 与"有任意流水"**不是同一条**。
    assert reg.index("if(n.manual)") < reg.index("if(ntHasFlow(n))") < reg.index("if(n.hasAnyFlow)"), \
        "操作列的按钮顺序变了"


@acc("ACC-PAY-ACTION-001", "001-01")
def test_壳里有生效流水才出撤销付款且单条就地开窗():
    """「撤销付款」**只在有生效流水时**出现；该行只有 1 条生效流水 ⇒ **就地**开撤销弹窗。

    ⚠️ 不新开口径：撤销弹窗复用流水页的 `revDlg`（**原因必填 ＋ 留痕** ＋ 已付金额回退 ＋ 按审批金额重判）。
    """
    reg = _act_cell()
    assert "const ntHasFlow=n=>N2(paidOf(n.id))>0;" in SHELL, "「有生效流水」的判据没了"
    assert "if(ntHasFlow(n)) L.push(" in reg and 'data-act="ntRevoke"' in reg, \
        "撤销付款入口没绑在「有生效流水」上"
    assert "撤销付款" in reg, "按钮文案丢了"
    rev = _revoke()
    assert "if(live.length===1) return ACT.revDlg(" in rev, "单条流水没有就地开**共用的**撤销弹窗"
    from tests.shell_src import act_entry
    dlg = act_entry("revDlg")
    ok = act_entry("revOk")
    assert "撤销须填原因" in dlg and 'id="rReason"' in dlg, "撤销必须填原因并提供输入框"
    assert "已付金额减少，付款状态重新判定" in dlg, "要说明撤销的真实后果"
    assert "if(!rs) return" in ok and "撤销原因必填" in ok, "空原因须拦下并反馈"
    assert ok.index("if(!rs) return") < ok.index("API.flowRevoke(f.id, rs,"), "原因校验须在提交前"


@acc("ACC-PAY-ACTION-001", "001-02")
def test_壳里多条生效流水跳流水页且只筛这一单():
    """多条生效流水 ⇒ 跳「付款流水与欠款统计」并**只筛出这一单**，让用户**逐条**撤。

    ⛔ 不做"一次撤全部"（撤销是逐条留痕的动作，批量撤会把每条的原因糊成一个）。
    """
    rev = _revoke()
    assert "go('m05')" in rev, "多条流水没有跳流水页"
    assert "flf.q=n.code||''" in rev, "跳到流水页后没把筛选收敛到这一单"
    assert "不做一次撤全部" in rev, "没讲清「不提供一键撤全部」"


@acc("ACC-PAY-ACTION-001", "001-04")
def test_壳里查看关联是纯只读且流水含已撤销():
    """查看关联 = **纯只读**：不写任何数据、不改任何状态；两个弹窗按钮一律「关闭」。

    流水子表要**生效 ＋ 已撤销都列**（撤销的显示**原因**）——「去向」的完整视图。

    ⚠️ 2026-10-11 同步（`TAIL-281` 改形，**判词一字未改**，只把断言指回现在的真身）：
      · 操作列那个入口现在叫**「查看流水」**（`ntFlows`，有任意流水才出）；**「查看关联」**
        （`ntTrace`）搬去**集采实际供应商列**的「已关联」标签上（`proj.js::jcLinkCell`）。
      · 流水子表**两个弹窗共用一份渲染** `ntFlowTable` ⇒ 只读与"含已撤销"那几条必须连它一起看
        （⛔ 只看 `ntTrace` 那一小段会变成假绿：表已经不在那儿了）。
      · 原两条已随实现下线：弹窗里那句范围说明、「另有 N 条已撤销，不计入」——
        后者描述的是旧的两档写法，现在是一张表 ＋ 状态列（已撤销那行连**原因**一起显示）。
    """
    reg = _act_cell()
    assert 'data-act="ntFlows"' in reg and "查看流水" in reg, "操作列的「查看流水」入口没了"
    assert 'data-act="ntTrace"' in SHELL and 'title="查看关联"' in SHELL, \
        "集采列「已关联」标签上的「查看关联」入口没了"
    import re
    tr, tb = _trace(), _flow_table()
    assert "查看关联 · " in tr and "<b>集采合同</b>" in tr and "<b>付款流水</b>" in tr, \
        "查看关联弹窗没把「集采合同 / 付款流水」两块都列出来"
    assert set(re.findall(r'data-act="([^"]+)"', tr)) == {"closeModal", "jcContract"}, "只读窗口只允许关闭和合同定位"
    assert set(re.findall(r'data-act="([^"]+)"', tb)) == set(), "流水子表里不该有任何动作按钮"
    assert "API." not in tr and "API." not in tb, "查看关联 / 查看流水不得发起写请求"
    assert 'data-act="closeModal">关闭</button>' in tr, "只读弹窗必须可关闭"
    assert "enumTag('flowState','已撤销')" in tb and "esc(f.reason)" in tb, \
        "已撤销的流水没有连**原因**一起显示"
    # ⭐ 2026-09-29（`TAIL-64` A′）：那张「流水子表」的**表外壳**也走统一出口 `TBL`（⛔ 别退回裸 `<table class="dt cond">`）。
    #   ⚠️ 它**没有排序身份**（没有 `key` ⇒ 不参与排序）—— 与本仓多数表不同，是本批里唯一的「**纯展示表**」。
    #   ⚠️ 2026-10-11（双轴 review 纠正）：这条断言**在 HEAD 上早已过期** —— 实现那边首列一直写着
    #      「流水记录 ID」（它本来就是数据库行号），且 `TBL({cls:'cond',` 与 `head:` 之间**有换行** ⇒
    #      旧锚点 `TBL({cls:'cond',head:'<th>流水号</th>` **恒不命中**，此前那条红被本函数更前面
    #      「查看关联入口没了」挡着、没暴露出来。⇒ 本轮只把锚点指回现在的真身；
    #      **「流水记录 ID」这个名字不是本轮改的**（`TAIL-283` 只把"流水号"这个词收回给真业务号
    #      `flow_no`，用在流水表与撤销弹窗那些地方）。
    assert "TBL({cls:'cond'," in tb and "head:'<th>流水记录 ID</th>" in tb, \
        "「查看关联」的流水子表没走统一出口 `TBL`，或首列不再叫「流水记录 ID」"


@acc("ACC-PAY-ACTION-001", "001-05")
def test_壳里查看关联不臆造集采取值():
    """没有集采合同关联 ⇒ **给说明，不给假值**（⛔ 不臆造）；没有流水 ⇒ 同样只说实话。

    ⚠️ 2026-10-11 同步（`TAIL-281` 改形，**判词一字未改**）：那张合同块已按票面**补齐 11 项**
    （合同日期 · 材料名 · 供应商 · 项目 · 合同金额 · 结算金额 · 付款金额 · 欠款金额 · 付款方式 ·
    存档情况 · 备注），旧的「集采实际供应商 / 集采合同关联」两格随旧分档下线。
    ⇒ 断言改成钉**现在的分岔结构**：有合同才渲染那 11 项（且都走既有取值出口），
    没合同只给一句说明 —— 两处都⛔ 不编数。
    """
    tr = _trace()
    # 分岔：`j?...:tip` —— 「有合同」那一支才渲染合同块
    assert "const contract=j?kvBlock([" in tr, "合同块没有按「有没有关联」分岔（无关联时可能编出假值）"
    assert "['项目',esc(pjLabel(j.proj))]" in tr and "['欠款金额',M(jcDebt(j))]" in tr, \
        "补全后的合同项没走既有取值出口（项目展示名 / 欠款金额）"
    assert "未关联集采合同。" in tr, "没关联时的说明文案丢了"
    assert "暂无付款流水。" in _flow_table(), "没有流水的空态提示没了"


# ---------------------------------------------------------------- 草稿行 / 统计格


@acc("ACC-PAY-MANUAL-001", "001-07")
def test_壳里草稿行统计结算只读且录入人不由手填():
    """§4.2.6：手动新增行「统计结算」**恒 0 且不可修改**（不是输入框）；录入人**取当前登录用户**。"""
    reg = _draft_row()
    assert 'class="draftrow"' in reg, "草稿行没挂 `draftrow`（排序 pin 也靠它）"
    assert "统计结算金额恒为 0、不可修改" in reg, "「统计结算恒 0 不可改」这条没讲清"
    assert '<td class="num"><span class="mut" title="手动新增行：这笔钱没有新结算' in reg, \
        "统计结算格不是**只读文本**（被做成了可改的输入框）"
    assert "${esc(CUR.name)}" in reg, "录入人不是取当前登录用户（变成可手填了）"
    assert 'data-act="ntRowSave"' in reg and 'data-act="ntRowCancel"' in reg, "草稿行的保存/取消没了"
    assert 'data-act="ntRowAdd"' in SHELL and "＋ 手动新增通知书" in SHELL, "增行入口没了"
    assert "表尾出现一行草稿" in SHELL or "在表尾增行录入一行付款通知书" in SHELL, \
        "「表内增行（不弹窗）」这条口径没讲清"


@acc("ACC-PAY-STAT-001", "001-08")
def test_壳里统计两列是行内可改格且未手改不黄底():
    """§4.2.7 / R8：统计结算 ＋ 统计付款 = **行内可改格**（不用弹窗）；**没手改过 ⇒ 不黄底**。"""
    assert 'data-act="editss" data-id="${n.id}" data-k="ss"' in SHELL, "「统计结算金额」不是行内可改格"
    assert 'data-act="editss" data-id="${n.id}" data-k="sp"' in SHELL, "「统计付款金额」不是行内可改格"
    assert 'data-act="editss" data-id="${n.id}" data-k="pay"' in SHELL, "「付款金额」不是行内可改格"
    for col in ("统计结算金额", "统计付款金额"):
        assert f"hasT(n,'{col}')?'ed':''" in SHELL, f"「{col}」没按**留痕**决定黄底"


@acc("ACC-PAY-STAT-001", "001-09")
def test_壳里手改过的统计格黄底且判据是留痕():
    """§4.2.7：黄底（`ed`）的判据 = **留痕**（`edited_fields` 里有这一列）—— 不是"值看着像改过"。

    新壳：两个统计格各自用 `hasT(n,'<列名>')` 判黄底（`hasT` 就是那份留痕的读口）。
    """
    assert "const impManSS=n=>hasT(n,'统计结算金额');" in SHELL, "留痕读口 `hasT` 没被用在这里"
    assert "hasT(n,'统计结算金额')?'ed':''" in SHELL and "hasT(n,'统计付款金额')?'ed':''" in SHELL, \
        "黄底不是由**留痕**判的"
    # ⚠️ 上界提示：手改值 > 审批金额时要有「导入提醒」的越界标记（同一处留痕机制的延伸）
    assert "impHasWarn(n)" in SHELL, "越界（手改值 > 审批金额）没有提醒入口"


@acc()
def test_壳里统计手改走真接口而不是本地改():
    """`§19` 批 4 · **S1 接线**：统计两金额必须**走后端**（上限 / 留痕 / 欠款重算都在服务端唯一出口
    `notice_actions.apply_stat_change`）—— ⛔ 前端不再本地改值 + 本地留痕冒充落库。

    ⚠️ 这条同时是 `wiring_audit` 的「**零件装上车**」证据：新端点 `POST /api/m03/actions/stat`
    在壳里**真的有调用点**（后端加了端点而壳不调 = 测了零件没装上车，`W1b` 会拦）。
    """
    assert "statCell: body => API.post('/api/m03/actions/stat', body)," in SHELL, "壳没接统计手改接口"
    i = SHELL.find("editss:t=>{")
    assert i >= 0, "找不到 `editss` 处理器"
    reg = SHELL[i:i + 3000]
    assert "API.statCell({" in reg, "统计手改仍然是本地改（没走后端）"
    assert "{ss:'stat_settle', sp:'stat_paid'}" in reg, "壳的短名没映射到后端旁路字段名"
    assert "pushTrail(n.trail,{obj:n.code||n.id, field:NAME" not in reg, "还在本地写留痕冒充落库"
    assert "reloadNotices()" in reg, "改完没重拉列表（黄底 / 欠款就刷不出来）"


@acc()
def test_壳里手动行新增编辑走真接口而不是本地塞数组():
    """`§19` 批 4 · **S2a 接线**：手动行**新增 / 编辑**必须**落库走后端**
    （`POST /api/m03/actions/manual-save`；校验在后端一处）—— ⛔ 前端不再 `NO.push` / `Object.assign`
    冒充落库（原先就是这样，刷新即丢）。

    ⚠️ 同时是 `wiring_audit` 的「零件装上车」证据：新端点在壳里**真的有调用点**。
    """
    assert "manualSave: body => API.post('/api/m03/actions/manual-save', body)," in SHELL, \
        "壳没接手动行保存接口"
    i = SHELL.find("ntRowSave:()=>{")
    assert i >= 0, "找不到 `ntRowSave` 处理器"
    reg = SHELL[i:i + 2600]
    assert "API.manualSave(body)" in reg, "手动行保存仍然是本地塞数组（没走后端）"
    assert "NO.push(n)" not in reg, "还在本地 `NO.push` 冒充落库"
    assert "Object.assign(n,f)" not in reg, "还在本地 `Object.assign` 冒充落库"
    assert "row_id:" in reg, "没把「编辑哪一行」带给后端（会变成永远新增）"
    # ⚠️⭐ 一个真坑（2026-09-19 接线时撞上）：下拉框的值是**中文标签**（`ENUMS.cat`），
    #    而服务端只认**键**（material / mechanical / jc）⇒ 必须映射，否则保存**一律被拒**
    assert "CAT_API[f.cat]" in reg, "分类没从「中文标签」映射成服务端的键（保存会被后端拒掉）"
    # 失败要**保留草稿行**（不清空已填内容，R14③）
    assert "草稿行已保留" in reg, "失败时没说清草稿行还在"


@acc()
def test_壳里手动行删除前的影响范围来自后端且删除走真接口():
    """`§19` 批 4 · **S2b 接线**：**删除前的影响范围必须由后端给**（§7.2/§9.4 是硬要求）——
    项目 / 统计付款金额 / 已付金额 / 「欠款回增」那句全由 `/api/m03/actions/manual-delete-impact` 出，
    ⛔ 前端不再自己拼这段文字；删除本身也走后端（⛔ 不再本地 `splice` 冒充删除）。

    ⚠️ 同时是 `wiring_audit` 的「零件装上车」证据：两个新端点在壳里**都有调用点**。
    """
    assert "manualDeleteImpact: body => API.post('/api/m03/actions/manual-delete-impact', body)," in SHELL, \
        "壳没接「删除影响范围」接口"
    assert "manualDelete: body => API.post('/api/m03/actions/manual-delete', body)," in SHELL, \
        "壳没接删除接口"
    i = SHELL.find("ntDel:t=>{")
    assert i >= 0, "找不到 `ntDel` 处理器"
    reg = SHELL[i:i + 3200]
    assert "API.manualDeleteImpact({notice_id:id})" in reg, "影响范围还是前端自己拼的（没问后端）"
    assert "imp.message" in reg and "imp.effects" in reg, "没把后端给的影响范围原样显示"
    assert "API.manualDelete({notice_id:id})" in reg, "删除还是本地删（没走后端）"
    assert "NO.splice(i,1)" not in reg, "还在本地 `splice` 冒充删除"


@acc()
def test_壳里批量付款走真接口且带幂等号():
    """`§19` 批 4 · **S3③ 接线**：批量付款必须**落库走后端**（整批重算 / 整批不落半批 / 幂等都在服务端）
    —— ⛔ 前端不再本地往 `FLs` 塞流水冒充落库。

    ⭐⭐ **幂等号是这条链的命门**：提交时必须带 `request_id`，服务端据它**拒重复提交**（§4.4.4）
    —— 没有这一行，「重复提交被拒」永远不可能成立（这正是它原先**卡着没法搬**的原因）。

    ⚠️ 同时是 `wiring_audit` 的「零件装上车」证据：新端点在壳里**有调用点**。
    """
    assert "batchPay: body => API.post('/api/m03/actions/batch-pay', body)," in SHELL, "壳没接批量付款接口"
    i = SHELL.find("batchPayOk:")
    assert i >= 0, "找不到 `batchPayOk` 处理器"
    reg = SHELL[i:i + 3000]
    assert "API.batchPay({" in reg, "批量付款还是本地塞流水（没走后端）"
    assert "FLs.push(" not in reg, "还在本地 `FLs.push` 冒充落库"
    assert "request_id:rid" in reg and "crypto.randomUUID" in reg, "提交没带幂等号（重复提交拦不住）"
    assert "if(!r.ok)" in reg, "没按 `ok` 标志分流（后端拦下时会当成成功）"
    assert "reloadNotices()" in reg, "提交成功没重拉列表（已付金额 / 状态刷不出来）"
    # §4.4.4：动作改走后端后，「取消」= **不调接口**（不再有服务端状态要回滚）
    assert "batchPayCancel:" in SHELL, "「取消」按钮的处理器没了"


@acc("ACC-PAY-MANUAL-001", "001-12")
def test_手动行保存挡重入():
    """守则 §5.5「动作里挡重入」（`TAIL-171`-② · 2026-09-29）：连点两次「保存」= 两次
    `POST /api/m03/actions/manual-save` ⇒ **同一份补录落两行**；⚠️ 手动行**没有**「单据号唯一约束」
    这道天然闸（同一笔补两行在业务上是合法状态）⇒ 这一道只能由界面挡（同 `m04` 的 `plSaving`）。

    ⚠️ 闸必须上在**本地校验之后**（校验是早退的：先上闸 ⇒ 校验一失败就把按钮卡死）。
    ⚠️ 能证伪：把 `if(ntSaving) return;` 摘掉、或把按钮那半的 `disabled` 摘掉 ⇒ 本件必红。
    """
    i = SHELL.find("ntRowSave:")
    assert i >= 0, "找不到 `ntRowSave`"
    body = SHELL[i:i + 4200]
    assert "if(ntSaving) return;" in body, "`ntRowSave` 没挡重入（连点会落两行）"
    assert "ntSaving=true" in body, "闸没合上（`ntSaving=true`）"
    assert body.count("ntSaving=false") >= 2, "闸没复位（成功 / 失败 / 异常三条路都要解）"
    # ⚠️ 只设一个没人读的标记 = 假守卫：草稿行的按钮必须**真的**变样
    assert "${ntSaving?' disabled':''}" in SHELL, "草稿行的「保存」按钮没有跟着禁用"
    assert "保存中…" in SHELL, "保存中没给状态文案（用户会以为没点上）"
