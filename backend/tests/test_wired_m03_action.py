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
SHELL = (ROOT / "backend" / "app" / "web" / "index.html").read_text(encoding="utf-8")


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


def _revoke() -> str:
    """「撤销付款」处理器 `ntRevoke`。"""
    return _slice("ntRevoke:t=>{", "ntTrace:t=>{", what="撤销付款处理器")


def _trace() -> str:
    """「查看关联」处理器 `ntTrace`。"""
    return _slice("ntTrace:t=>{", "/* —— MOD-05 —— */", what="查看关联处理器")


# ---------------------------------------------------------------- 操作列


@acc("ACC-PAY-MANUAL-001", "001-06")
def test_壳里操作列_i8行无编辑删除_手动行才有():
    """⛔ 铁律：**i8 抓取行**不提供「编辑 / 删除」（源数据只读）；只有**手动行**才有（§4.2.6）。

    新壳：编辑/删除按钮在 `if(n.manual)` 分支里 ⇒ 抓取行**结构上拿不到**这两个入口。
    """
    reg = _act_cell()
    assert "if(n.manual) L.push(" in reg, "编辑/删除没有绑在「手动行」上（i8 抓取行会拿到写入口）"
    assert 'data-act="ntEdit"' in reg and 'data-act="ntDel"' in reg, "手动行的编辑/删除按钮没了"
    # 顺序固定：手动行徽标 → 编辑/删除 → 撤销付款 → 查看关联（i8 行就是后两个）
    assert reg.index("if(n.manual)") < reg.index("if(ntHasFlow(n))") < reg.index("if(ntHasLink(n))"), \
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
    assert "撤销必须填写原因" in SHELL, "「撤销必须填原因」这条没讲清"


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
    """
    reg = _act_cell()
    assert 'data-act="ntTrace"' in reg and "查看关联" in reg, "查看关联入口没了"
    tr = _trace()
    assert "只读视图" in tr, "弹窗没自称只读"
    assert 'data-act="closeModal">关闭</button>' in tr, "弹窗出现了「关闭」以外的按钮（就不只读了）"
    assert "const live=flows.filter(f=>!f.voided), voided=flows.filter(f=>f.voided);" in tr, \
        "流水没分出「生效 / 已撤销」两档"
    assert "enumTag('flowState','已撤销')" in tr and "esc(f.reason)" in tr, \
        "已撤销的流水没有连**原因**一起显示"
    assert "另有 ${voided.length} 条已撤销，不计入" in tr, \
        "「已付金额（生效流水合计）」没说明已撤销的不计入（两格是两件事）"


@acc("ACC-PAY-ACTION-001", "001-05")
def test_壳里查看关联不臆造集采取值():
    """没有集采实际供应商 / 没关联合同 ⇒ **给说明，不给假值**（⛔ 不臆造）。"""
    tr = _trace()
    assert "['集采实际供应商',n.sup?" in tr, "集采实际供应商那格没按「有没有值」分岔"
    assert "['集采合同关联',jcRow]" in tr, "集采合同关联那格没了"
    assert "未关联集采合同（仅「集采」分类的行可关联）" in tr, "没关联时的说明文案丢了"
    assert "还没有付款流水" in tr, "没有流水的空态提示没了"


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
