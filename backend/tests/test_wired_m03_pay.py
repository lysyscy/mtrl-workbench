"""前端壳「批量付款窗口」的离线断言 —— `§19` 批 4 · **S4⑤**。

⭐ 为什么有这个文件：批量付款窗口原来是**服务端渲染页**（`notice_pay.py` 的 `build_pay_window` /
`render_pay_page` ＋ PRG `POST /m03/pay`），断言写在 `tests/test_notice_pay.py` 里。
旧页删净（授权 `D18`）⇒ **形态与交互那半边改指新壳**（⛔ 判据不删）：

  · `ACC-PAY-BATCH-001/001-01` 存在不可付行 ⇒ 「确认付款」**直接禁用** ＋ 原因 ＋ 解决路径
  · `ACC-PAY-BATCH-001/001-02` **本次应付为 0** 也不可付（不是"点了才拦"）
  · `ACC-PAY-BATCH-001/001-03` 付款方式**默认取付款计划**、取不到兜底「现汇」
  · `ACC-PAY-BATCH-001/001-04` **撤单行与剔除行**不得进入付款（准入判据唯一出口 `ntPayCand`）
  · `ACC-PAY-BATCH-001/001-05` 「移出本次付款」**只去掉该行**（并同时取消它的勾选）
  · `ACC-PAY-BATCH-001/001-06` 移出后**其它行已填的方式 / 金额仍在**（R14③）
  · `ACC-PAY-BATCH-001/001-09` 「本次付款金额」**超出本次应付**被拦（整批不落）
  · `ACC-PAY-BATCH-001/001-10` 付款方式选「其他」**必须填备注**（DEV-P-01）
  · `ACC-PAY-BATCH-001/001-12` **取消**不产生任何流水（动作改走后端后 = **不调接口**）

⚠️ 另外三条（001-03 的 API 半边 / 001-07 落流水 / 001-08 提交时重算不落半批 / 001-11 幂等）
   已在 `tests/test_notice_action_api.py` 上如实落地 ✓ —— 本文件只补**壳侧**这一半。

⚠️ 只读壳源码（`SHELL`）；断言一律在**切片**里找（`_batch_pay()` / `_batch_pay_ok()`），
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


def _batch_pay() -> str:
    """批量付款窗口的组装出口 `batchPay`（含"不可付 / 排除撤单"的提示与页脚按钮）。"""
    return _slice("batchPay:()=>{", "/* 草稿记录", what="批量付款窗口出口")


def _batch_pay_ok() -> str:
    """提交出口 `batchPayOk`（整批重算 + 拦截 + 走后端）。"""
    return _slice("batchPayOk:t=>{", "revDlg:t=>{", what="批量付款提交出口")


def _batch_pay_del() -> str:
    """「移出本次付款」处理器 `batchPayDel`。"""
    return _slice("batchPayDel:t=>{", "batchPayOk:t=>{", what="移出处理器")


def _pay_block() -> str:
    """⭐ 「本次不可付」的**唯一出口** `ntPayBlock` 通用件源码（与 `ntJcUnlinked` 同块）。

    ⚠️ **为什么要"两段拼起来看"**（同 `shell_src.with_kernel` / `with_tbl` 的 doctrine）：
       窗口组装那一段**委托**了这个通用件之后，「切片里必须出现 `n.astat==='已批'&&payEff(n)>0`」
       这类**钉源码形态**的判据就**假红**了 —— 而把判据改回"必须有那串字面"等于**宣布以后不许抽通用件**。
       ⇒ 正确写法 = 切片**委托了谁**（断言 `ntPayBlock(n)` 出现在切片里）＋ **那个件里**真做了那几件事。
    """
    return _slice("const ntPayBlock=n=>", "const ntSelectable", what="「不可付」唯一出口")


# ---------------------------------------------------------------- 前置禁用（R14① / §4.4.4）


@acc("ACC-PAY-BATCH-001", "001-01")
def test_壳里存在不可付行则确认付款禁用并给原因与解决路径():
    """**能预防就不要等用户撞上去**（R14①）：存在不可付行 ⇒ 窗口**直接禁用**「确认付款」，
    并**说清原因 ＋ 给解决路径**（否则用户只知道点不动）。

    新壳：不可付 = `未审批 或 本次应付 ≤ 0` ⇒ `bad.length` 非空 ⇒ 页脚按钮加 `disabled`
    ＋ 一段说明（含"点该行的删除把它移出本次付款"这条路径）。
    """
    reg = _batch_pay()
    # ⭐ 2026-09-24（`TAIL-91`）：判据改成**结构无关**的「**委托 ＋ 内核真做事**」——
    #   不可付的三条判据抽成唯一出口 `ntPayBlock` 之后，原先"切片里必须有那串字面"的写法**必然假红**。
    #   ⛔ 别改回去（那等于宣布"以后不许抽通用件"，与 `TAIL-62/64/67` 反向）。
    assert "const bad=rows.filter(n=>ntPayBlock(n));" in reg, \
        "「不可付」的判据**没走唯一出口**（窗口组装必须委托 `ntPayBlock`）"
    kern = _pay_block()
    assert "n.astat!=='已批'" in kern, "内核没判「未审批」"
    assert "payEff(n)<=0" in kern, "内核没判「本次应付 ≤ 0」"
    assert "ntJcUnlinked(n)" in kern, "内核没判「集采未关联」（§4.4.3 第⑤类）"
    assert '<button class="btn pri" data-act="batchPayOk"${bad.length?` disabled ' \
           'title="有 ${bad.length} 条不可付，请先删除这些行"`:\'\'}>确认付款</button>' in reg, \
        "有不可付行时「确认付款」没有被禁用"
    assert "条不可付，「确认付款」已禁用" in reg, "禁用没给原因"
    # ⭐ 2026-09-25（用户点检后**追加要求**）：**不可付要说清是哪种原因**，⛔ 不能只写"不可付"。
    #   判据仍走「委托 ＋ 内核」两段式：窗口**委托**唯一出口 `ntPayBlock`，
    #   行单元格（`whyCell`）与顶部禁用提示（`badWhy`）**都由它给原因**，壳里⛔ 不另写文案。
    assert "whyCell(n)" in reg, "行内只写「不可付」、没说清是哪种原因"
    assert "badWhy" in reg, "顶部提示只有条数、没有「为什么」"
    assert "ntPayBlock(n)" in reg, "原因没走唯一出口 `ntPayBlock`（另写一套文案 ⇒ 必然漂）"
    assert "请移出不可付记录，或关闭后调整勾选" in reg, "没给解决路径（只说不行、不说怎么办）"
    assert "移出会取消该行勾选，其他行已填方式与金额保留" in reg, "没讲清移出后勾选变化及保留其他行草稿"
    # ⭐ 2026-09-29（`TAIL-64` A′）：这张表的**表外壳**也走统一出口 `TBL`（⛔ 别退回裸 `<table class="dt cond" …>`）。
    #   ⚠️ 它在这条判据里是**第二例**「委托 ＋ 内核」——同一条判据守着同一段切片的两处委托（`ntPayBlock` 与 `TBL`）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M34 去掉这处委托 ⇒ 必须红。
    assert "TBL({cls:'cond',key:'modal:batchPay',head:BP_THEAD," in reg, \
        "批量付款那张表没走统一出口 `TBL`（`TAIL-64` A′）"


@acc("ACC-PAY-BATCH-001", "001-02")
def test_壳里本次应付为0也不可付():
    """§4.4.4 / §4.4.2：**本次应付 = 付款金额**（审批金额 − 已付金额）⇒ **为 0（已付清）不可付**。

    两处都要拦：① 窗口组装时算进 `bad`（按钮直接禁用）；② 提交时逐行复算拦下（兜底）。
    """
    assert "const payEff=n=>payOver(n)?N2(n.payOv):N2(n.approve-paidOf(n.id));" in SHELL, \
        "「本次应付」的口径出口没了（默认 = 审批金额 − 已付金额）"
    assert "payEff(n)<=0" in _pay_block(), "唯一出口没把「本次应付为 0」算作不可付"
    ok = _batch_pay_ok()
    assert "if(can<=0){ errs.push(" in ok, "提交时没有兜底拦「本次应付为 0」"
    assert "本次应付为 0（审批金额 − 已付金额）" in ok, "拦下时没说清是哪种不可付"


# ---------------------------------------------------------------- 付款方式默认值（§4.4.2）


@acc("ACC-PAY-BATCH-001", "001-03")
def test_付款方式默认取付款计划取不到兜底现汇():
    """§4.4.2 的**唯一出口** `notice_pay_actions.default_pay_method`：先取付款计划的值、取不到兜底「现汇」。

    ⚠️ 「取计划」那半边原先只在旧页的 `test_notice_pay.py` 里；那件随页删除 ⇒ 这里守住纯函数本身
       （API 那半边＝"缺省时兜底现汇"由 `test_notice_action_api.py` 的用例守着）。
    """
    # ⚠️ 2026-09-21（`T5` 拆分）：自 `notice_actions` 挪进 `notice_pay_actions` —— **判定一行未变**。
    from app.mod03_notice.notice_pay_actions import default_pay_method

    assert default_pay_method("D1", {"D1": "承兑"}) == "承兑", "取不到计划值"
    assert default_pay_method("D2", {"D1": "承兑"}) == "现汇", "计划里没有该单据号时没兜底「现汇」"
    assert default_pay_method("", {}) == "现汇" and default_pay_method("D3", None) == "现汇"
    # 壳侧：默认值同样是从计划取、取不到「现汇」（与上面同一口径）
    assert "const plan=PLs.find(pl=>pl.docNo===n.code), dm=plan?plan.method:'现汇';" in _batch_pay(), \
        "壳里没按「先取计划、兜底现汇」定默认付款方式"


# ---------------------------------------------------------------- 不进付款的行（§4.2.7 / §4.2.2）


@acc("ACC-PAY-BATCH-001", "001-04")
def test_壳里撤单行与剔除行不得进入付款():
    """**撤单行**（i8 侧已删，§4.2.7）与**剔除行**（§4.2.2）一律**不得进入付款批次**
    —— 付款准入的唯一出口仍是 `ntPayCand`：全选 / 按计划勾选过滤 · 窗口组装 · 提交再兜一道。

    ⚠️⚠️ **2026-09-21 按形态变化重指**（**claim 一字未改**：仍是「两者都不进付款批次
       ＋ 显式告知、不得静默少几行」）。原先这里还断言「勾选框对非付款候选 `disabled`」——
       那是把 claim 的「**不进付款批次**」**过度施加到勾选框上**了，后果是 **剔除行永远勾不上**，
       而「恢复剔除」又要求「必须先勾选」（`ACC-PAY-CAT-001/001-10`）⇒
       **两道门互锁、恢复这条路根本走不通**（用户 2026-09-21 报障）。
       ⭐ 澄清：2026-09-16 那次裁定说的是「**归属校验**前先剔掉规则剔除行」（`ACC-PRJ-OWN-001/001-09`），
          **不是**勾选框 —— 勾选 ≠ 能付款：勾选集服务「批量付款」与「恢复剔除」两件事。
       ⭐ claim 后半句「**显式告知（不得静默少几行）**」在旧形态下**根本测不到**
          （剔除行压根进不了勾选集，那条提示只有撤单行会触发）⇒ 本次一并补上。
    """
    assert "const ntLive=n=>!n.excl&&" in SHELL, "有效行口径没排除**剔除行**"
    assert "const ntPayCand=n=>ntLive(n)&&!ntVoid(n);" in SHELL, "付款准入的唯一出口 `ntPayCand` 变了"
    # ⭐ 勾选框走**可勾选**出口（= 付款候选 ∪ 剔除行）；⛔ 付款闸不许搬回勾选框（那会再上锁）
    assert "const ntSelectable=n=>ntPayCand(n)||!!n.excl;" in SHELL, \
        "可勾选出口没把**剔除行**放进来 ⇒ 「恢复剔除」又无路可走"
    assert "${ntSelectable(n)?'':'disabled'}" in SHELL, "勾选框没走可勾选出口"
    assert "${ntPayCand(n)?'':'disabled'}" not in SHELL, \
        "勾选框又被钉回 `ntPayCand` 上了 —— 与「恢复剔除必须先勾选」互锁"
    reg = _batch_pay()
    assert "const rows=all.filter(ntPayCand), drop=all.filter(n=>!ntPayCand(n));" in reg, \
        "窗口组装没有走付款准入唯一出口"
    # ⭐ claim 的「显式告知」：**按行说真因** —— 剔除与撤单是两回事，⛔ 不能一律写成"i8 已撤单"
    assert "const whyOf=n=>ntVoid(n)?'i8 已撤单':'已剔除';" in reg, "排除提示没按行区分真因"
    assert "已自动排除 ${drop.length} 条不可付款的记录" in reg, "排除时没显式告知（会静默少几行）"
    assert "剔除或撤单记录不产生付款，请核对已付与关联记录" in reg, "要讲清不产生付款及核对已付/关联的后续路径"
    assert ".filter(Boolean).filter(ntPayCand);" in _batch_pay_ok(), "提交时没有兜底复检准入"


# ---------------------------------------------------------------- 移出 / 已填值不丢（R14③）


@acc("ACC-PAY-BATCH-001", "001-05")
def test_壳里移出本次付款只去掉该行():
    """「移出本次付款」= **只去掉该行**（同时取消它的勾选）＋ 就地重建窗口给用户接着看。"""
    reg = _batch_pay_del()
    assert "pickSet.delete(id); render();" in reg, "移出没有只删这一行（或没同步取消勾选）"
    assert "if(pickSet.size){ toast(`已把 <b>${n?n.code:id}</b> 移出本次付款" in reg, \
        "移出后没说明移掉的是哪一条"
    assert "ACT.batchPay();" in reg, "移出后没有重建窗口"
    assert "else { closeModal(); toast('已移除全部记录，本次付款未提交'); }" in reg, \
        "最后一条也移出时没有收尾（会留一个空窗口）"


@acc("ACC-PAY-BATCH-001", "001-06")
def test_壳里移出后其它行已填值仍在():
    """R14③：调整批次**不得丢失已填内容** —— 移出一行后，其它行已填的
    「实际付款方式 / 本次付款金额」必须还在。

    新壳：草稿按 `notice_id` 存在 `payDraft`；重建窗口时**只清掉不在批次里的**，
    每一行的默认值 `df.m || 计划值` / `df.a || 本次应付` 优先取草稿。
    """
    reg = _batch_pay()
    assert "Object.keys(payDraft).forEach(id=>{ if(!pickSet.has(id)) delete payDraft[id]; });" in reg, \
        "草稿清理没有只清「已不在批次里」的那些（会连其它行的已填值一起清掉）"
    assert "const df=payDraft[n.id]||{}, curM=df.m||dm, curA=df.a||can.toFixed(2);" in reg, \
        "重建窗口时没有把已填值带回来（其它行会回默认）"


# ---------------------------------------------------------------- 提交：校验与拦截（§4.4.4）


@acc("ACC-PAY-BATCH-001", "001-09")
def test_壳里付款金额超过本次应付被拦():
    """⛔ **不能多付**：`本次付款金额 > 本次应付` ⇒ 拦下该行 ⇒ **整批不产生任何流水**（不落半批）。

    ⚠️ 前端这一层是"就地提示"；**服务端 `confirm_batch` 会再算一次**（`apply_batch_pay` 里，
      判据由 `test_notice_action_api.py` 的 001-08 守着）—— 两处都在，才是"拦得住"。
    """
    ok = _batch_pay_ok()
    assert "if(amt>can){ errs.push(`" in ok and "超出本次应付" in ok, "超出本次应付没有被拦"
    assert "if(errs.length) return toast(" in ok, "有错时没有拦住整批"
    assert "已拦截 ${errs.length} 条，整批不产生任何流水" in ok, \
        "没讲清「整批不产生任何流水」（用户会以为部分已落）"


@acc("ACC-PAY-BATCH-001", "001-10")
def test_壳里付款方式选其他必须填备注():
    """`DEV-P-01`：付款方式选「其他」⇒ **备注必填**（否则这笔钱的去向就说不清了）。

    窗口里先把这条讲在明处（`选「其他」须填备注`），提交时逐行拦下。
    """
    assert "选「其他」须填备注" in _batch_pay(), "窗口没预先说明「选其他须填备注」"
    ok = _batch_pay_ok()
    assert "if(m==='其他'&&!rm){ errs.push(`" in ok, "选「其他」没填备注时没有被拦"
    assert "付款方式选「其他」必须填备注" in ok, "拦下时没说清是哪条规则"


@acc("ACC-PAY-BATCH-001", "001-12")
def test_壳里取消批量付款不调接口也不产生流水():
    """⭐ **语义已变、必须说清**：动作改走后端之后（`S3③`），「取消」= **根本不调接口**
    —— 不再有"服务端已写一半"的状态要回滚 ⇒ 取消只清草稿 ＋ 关窗口，**零副作用**。
    """
    reg = _slice("batchPayCancel:()=>{", "batchPayDel:t=>{", what="取消处理器")
    assert "closeModal();" in reg, "取消没有关窗口"
    assert "payDraft={};" in reg, "取消没有清掉本次草稿（下次打开会带着上次的填写）"
    for bad in ("API.", "batchPay(", "FLs.push", "fetch("):
        assert bad not in reg, f"取消里出现了写路径 `{bad}` —— 取消应当零副作用"
