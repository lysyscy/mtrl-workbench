"""前端壳「按付款计划勾选」的离线断言 —— `§19` 批 4 **小轮④a**（`ACC-PAY-PICK-001` 全 7 条绑定）。

⭐ 覆盖 `tests/test_notice_plan_pick.py`：这一页原来走**服务端渲染** ＋ 一条 PRG
（`POST /m03/notices/pick-plan`）—— 由服务端算出「该勾哪些行」再 303 回列表页（`plan=<当月>`）。
旧页删除（授权 `D18`）⇒ **形态这半边改指新壳**（⛔ 判据不删）。

⚠️⚠️ **这条链在壳里已经是"真行为"，不是模拟**（与 m03 的写动作不同 —— 见台账）：
    计划数据来自 `GET /api/m04/plans`（真接口）✓，勾选动作本身在壳里做（客户端 `pickSet`）✓，
    四条口径也都在壳里：**窗口**（`plWin()`：当月 10 号 → 月末）· **月份来源**（北京时间当月，不可自选）·
    **只放宽视图参数、「项目」筛选一律不动** · **剔除/撤单行一律不勾**（`ntPayCand`）。
    ⇒ 「窗口外先禁用 + 说明原因」这条在壳侧由 `disabled` ＋ 处理器兜底**两处**保住；
      ⚠️ 旧实现还有一道**服务端**复检 —— 那条随"动作改为纯客户端"**失去保护对象**（不再改服务端状态，
      复检无从谈起），故本文件只守客户端这一半；⛔ 别把它读成"服务端也拦"。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛


def _plan_pick() -> str:
    """「按付款计划勾选」处理器 `planPick` 的正文。"""
    i = SHELL.find("planPick:()=>{ const win=plWin();")
    assert i >= 0, "壳里找不到 `planPick` 处理器"
    j = SHELL.find("/* —— MOD-03 · 手动新增", i)
    assert j > i, "找不到 `planPick` 的收尾"
    return SHELL[i:j]


# ⚠️ 「只放宽视图参数」那一行：四个视图参数可以放宽，`fNt.projs`（项目筛选）**一个字都不许动**
_WIDEN = "fNt.month='全部'; fNt.cat='全部'; fNt.astat='全部'; fNt.stat='未付清';"


@acc("ACC-PAY-PICK-001", "001-01")
def test_壳里计划命中的行被预勾选():
    """计划行指向的通知书 ⇒ 勾上；没命中的不勾；并报「已按 <当月> 付款计划勾选 N 条（计划命中 N 条）」。

    新壳：命中判据 = **单据号相等 且 是付款候选**（`ntPayCand`）—— 与旧页同一口径。
    """
    reg = _plan_pick()
    assert "const plan=PLs.filter(p=>p.ym===ym);" in reg, "没按当月筛计划行"
    assert "NO.find(x=>x.code===c&&ntPayCand(x))" in reg, "命中判据丢了（应含 `ntPayCand`）"
    assert "hit++; pickSet.add(n.id); });" in reg, "命中的行没被勾上"
    assert "已按 <b>${ym}</b> 付款计划勾选 <b>${pickSet.size}</b> 条（计划命中 <b>${hit}</b> 条" in reg, \
        "回执没报「勾选 N 条 / 计划命中 N 条」"


@acc("ACC-PAY-PICK-001", "001-02")
def test_壳里跨月单据也能勾上():
    """§4.3.5：视图放宽到「全部月份」⇒ 当月计划里混着的**上月/更早**通知书也能勾上；
    回执要点出「含跨月 N 条（<月份> ×N）」—— 让人知道勾进来的不全是当月。
    """
    reg = _plan_pick()
    assert _WIDEN in reg, "没把「单据年月」等视图参数放宽（跨月的行会被筛掉）"
    assert "fNt.month='全部'" in reg, "单据年月没放宽到「全部月份」"
    assert "含<b>跨月 ${cx}</b> 条" in reg, "回执没报「含跨月 N 条」"
    assert "const other=Object.keys(months).filter(m=>m!==ym).sort();" in reg, \
        "没算出「哪些行落在别的月份」"


@acc("ACC-PAY-PICK-001", "001-03")
def test_壳里项目筛选不动且被挡的行要报数():
    """用户口径（2026-09-12）：**「项目」筛选一律不动** —— 它是用户表达的业务范围；
    被项目挡掉的行**跳过并报数**（不静默少勾）。
    """
    reg = _plan_pick()
    assert _WIDEN in reg and "projs" not in _WIDEN, "放宽清单里混进了「项目」筛选项"
    assert "fNt.projs='全部'" not in reg and "fNt.projs=[]" not in reg, "把用户的「项目」筛选改了"
    assert "const cut=before-pickSet.size;" in reg, "没数出「被挡掉几条」"
    assert "条不在你选定的「项目」范围内，已跳过" in reg, "被挡的行没报数"
    assert "「项目」筛选未被改动" in reg, "回执没写明「项目筛选未被改动」"


@acc("ACC-PAY-PICK-001", "001-04")
def test_壳里空单据号不参与勾选():
    """§4.3.3：单据号**允许为空** ⇒ 空号认不出对应哪张通知书 ⇒ 不参与勾选；
    并在回执里说明「另 N 行无单据号 / 编号查不到」。
    """
    reg = _plan_pick()
    assert "const c=String(p.docNo||'').trim();" in reg, "没把计划行的单据号规范化（去空格）"
    assert "const n=c?NO.find(x=>x.code===c&&ntPayCand(x)):null;" in reg, \
        "空单据号没被排除（`c` 为空时应判为**查不到**而非命中）"
    assert "行无单据号 / 编号查不到" in reg, "查不到的行没报数"


@acc("ACC-PAY-PICK-001", "001-05")
def test_壳里窗口外先禁用且点不了():
    """可点窗口 = 每月 **10 号 → 月底**（§4.3.2）：窗口外**先禁用**（不是点了才拦）。

    ⚠️ 两处都留着：按钮 `disabled`（看得见）＋ 处理器开头 `if(!win.open)` 兜底（点得到也不执行）。
    """
    assert "data-act=\"planPick\" ${win.open?'':'disabled'}" in SHELL, "按钮没按窗口置灰"
    reg = _plan_pick()
    assert "const win=plWin();" in reg, "处理器没自己再判一次窗口"
    assert "if(!win.open){ toast(" in reg, "处理器没兜底拦窗口外"
    # 放宽的三档 ＋ 付款状态置「未付清」（与旧路由的 `period=&pay_status=unpaid` 同款）
    assert "fNt.stat='未付清';" in reg, "付款状态没放宽到「未付清」"


@acc("ACC-PAY-PICK-001", "001-06")
def test_壳里窗口外不执行并说明原因():
    """窗口外**不执行**（勾选集合不动）且**说明原因**（哪天起生效 / 哪天截止）。

    ⚠️ 旧实现在服务端也复检一次；动作改为纯客户端后那道复检**失去保护对象**（见模块 docstring）。
    """
    reg = _plan_pick()
    head = reg[:reg.index("const ym=win.ym;")]
    assert "return; }" in head, "窗口外没有**提前返回**（会继续往下勾）"
    assert "付款计划 ${win.from} 号起生效、月末截止" in head, "没说明窗口起止"
    assert "不在付款窗口内，暂不可勾选" in head, "没说明「为什么不可勾选」"
    assert "pickSet.clear();" not in head, "窗口外就把已勾集合清了（应当**什么都不动**）"


@acc("ACC-PAY-PICK-001", "001-07")
def test_壳里计划单据号来自当月且月份不可自选():
    """§4.3.5：计划单据号取自**北京时间当月**的计划（月份**不可自选**）。

    新壳：`ym = win.ym`（窗口算出来的当月）⇒ 只取该月计划行 ⇒ 别的月的计划行不参与本次勾选。
    """
    reg = _plan_pick()
    assert "const ym=win.ym;" in reg, "月份不是由窗口出口给的（会变成可自选）"
    assert "const plan=PLs.filter(p=>p.ym===ym);" in reg, "没按当月过滤计划行"
    assert "PLs" in SHELL and "plans: () => API.get('/api/m04/plans?year_month=')" in SHELL, \
        "计划数据源不是真接口（`/api/m04/plans`）"
