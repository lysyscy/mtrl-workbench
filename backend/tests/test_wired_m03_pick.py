"""前端壳「按付款计划勾选」的离线断言 —— `§19` 批 4 **小轮④a**（`ACC-PAY-PICK-001` 全 7 条绑定）。

⭐ 覆盖 `tests/test_notice_plan_pick.py`：这一页原来走**服务端渲染** ＋ 一条 PRG
（`POST /m03/notices/pick-plan`）—— 由服务端算出「该勾哪些行」再 303 回列表页（`plan=<当月>`）。
旧页删除（授权 `D18`）⇒ **形态这半边改指新壳**（⛔ 判据不删）。

⚠️⚠️ **这条链在壳里已经是"真行为"，不是模拟**（与 m03 的写动作不同 —— 见台账）：
    计划数据来自 `GET /api/m04/plans`（真接口）✓，勾选动作本身在壳里做（客户端 `pickSet`）✓，
    四条口径也都在壳里：**月份由人选**（⭐ 2026-10-08 用户裁定：原先"当月 10 号 → 月底才可点、
    月份定死当月"**两点都取消**）· **只放宽视图参数、「项目」筛选一律不动** ·
    **剔除/撤单行一律不勾**（`ntPayCand`）· **该月没有计划行时不勾并说明原因**。
    ⇒ 按钮可用性的**唯一出口是后端** `mod04_plan/plan_ui.window_button`（恒可点）；
      ⛔ 壳里**不再写第二份**"今天几号够不够 10 号"的判定（原先的 `plWin()` 已随裁定删除）。
    ⚠️ **两个动作**：`planPick` = 选月份（弹窗）· `planPickRun` = 真正勾选那一条；
      钉勾选逻辑的判据一律取 **`act_entry("planPickRun")`**（只取 `planPick` 会拿到选月弹窗那段）。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL, act_entry  # noqa: F401  ← `P4`① 读取点收敛

# ⭐ 2026-10-04（`TAIL-219` 批 2b 余下 ②）：本件那把自造剪刀 `_plan_pick()` 已换成语义窗口子
#   `act_entry("planPick")`（`planPick` 是 `const ACT={…}` 里的一条 —— 两处取到的正文一致，
#   仅首尾空白之差；量测件 `.codebuddy/work/00-scratch/_tail219_batch2b_rest.py`）。


# ⚠️ 「只放宽视图参数」那一行：四个视图参数可以放宽，`fNt.projs`（项目筛选）**一个字都不许动**
_WIDEN = "fNt.month='全部'; fNt.cat='全部'; fNt.astat='全部'; fNt.stat='未付清';"


@acc("ACC-PAY-PICK-001", "001-01")
def test_壳里计划命中的行被预勾选():
    """计划行指向的通知书 ⇒ 勾上；没命中的不勾；并报「已按 <当月> 付款计划勾选 N 条（计划命中 N 条）」。

    新壳：命中判据 = **单据号相等 且 是付款候选**（`ntPayCand`）—— 与旧页同一口径。
    """
    reg = act_entry("planPickRun")
    assert "const plan=PLs.filter(p=>p.ym===ym);" in reg, "没按当月筛计划行"
    assert "NO.find(x=>x.code===c&&ntPayCand(x))" in reg, "命中判据丢了（应含 `ntPayCand`）"
    assert "hit++; pickSet.add(n.id); });" in reg, "命中的行没被勾上"
    assert "已按 <b>${esc(ym)}</b> 付款计划勾选 <b>${pickSet.size}</b> 条（计划命中 <b>${hit}</b> 条" in reg, \
        "回执没报「勾选 N 条 / 计划命中 N 条」（⚠️ 月份是拼进 HTML 的，必须过 `esc`）"


@acc("ACC-PAY-PICK-001", "001-02")
def test_壳里跨月单据也能勾上():
    """§4.3.5：视图放宽到「全部月份」⇒ 当月计划里混着的**上月/更早**通知书也能勾上；
    回执要点出「含跨月 N 条（<月份> ×N）」—— 让人知道勾进来的不全是当月。
    """
    reg = act_entry("planPickRun")
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
    reg = act_entry("planPickRun")
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
    reg = act_entry("planPickRun")
    assert "const c=String(p.docNo||'').trim();" in reg, "没把计划行的单据号规范化（去空格）"
    assert "const n=c?NO.find(x=>x.code===c&&ntPayCand(x)):null;" in reg, \
        "空单据号没被排除（`c` 为空时应判为**查不到**而非命中）"
    assert "行无单据号 / 编号查不到" in reg, "查不到的行没报数"


@acc("ACC-PAY-PICK-001", "001-05")
def test_壳里不再按日期禁用且月份可选():
    """⭐ 2026-10-08 用户裁定：**任何时候都能点**、**月份可选**（原口径"每月 10 号 → 月底才可点、
    月份定死当月"两点都取消 —— 那只是制度上的习惯，制度本身也只约束人、不拦系统，§4.3.7）。

    ⇒ 判据 = **按钮上没有按日期的 `disabled`** ＋ **处理器里没有"今天几号够不够 10 号"的早退**。
    ⚠️ 后端是按钮可用性的**唯一出口**（`plan_ui.window_button`，恒可点）；壳里⛔ 不留第二份判定
    （原先那个 `plWin()` 已删）—— 又一份就迟早漂移、且会把用户重新挡在门外。
    """
    assert 'data-act="planPick" title=' in SHELL, "「按付款计划勾选」按钮没了"
    assert "${win.open?'':'disabled'}" not in SHELL, "按钮还在按生效窗口置灰（2026-10-08 已取消该限制）"
    assert "function plWin(" not in SHELL, "壳里又出现了第二份生效窗口判定（`plWin`）—— 唯一出口在后端"
    reg = act_entry("planPickRun")
    assert "win.open" not in reg, "处理器还在按窗口早退（任何时候都该能勾）"
    assert "const ym=planYm||bjMonth();" in reg, "月份没取自「人挑的那个月」（`planYm`）"
    # 放宽的三档 ＋ 付款状态置「未付清」（与旧路由的 `period=&pay_status=unpaid` 同款）
    assert "fNt.stat='未付清';" in reg, "付款状态没放宽到「未付清」"


@acc("ACC-PAY-PICK-001", "001-06")
def test_壳里该月没有计划行时不勾并说明原因():
    """所选月份**没有计划行** ⇒ **不执行**（勾选集合不动）且**说明原因**（叫人去导入）。

    ⚠️ 取代原先那条"窗口外不执行"（窗口已取消）—— 现在唯一"不该勾"的情形就是**这个月没计划**。
    """
    reg = act_entry("planPickRun")
    assert "const plan=PLs.filter(p=>p.ym===ym);" in reg, "没按所选月份取计划行"
    head = reg[:reg.index("const plan=PLs.filter")]
    assert "pickSet.clear();" not in head, "没取到计划行就把已勾集合清了（应当**什么都不动**）"
    assert "if(!plan.length) return toast(" in reg, "该月没有计划行时不提前返回（会勾了个空）"
    assert "没有付款计划行" in reg and "导入该月计划表" in reg, \
        "没说明「为什么勾不到」＋ 出路（去导入那个月的计划表）"


@acc("ACC-PAY-PICK-001", "001-07")
def test_壳里计划单据号来自所选月份且月份可选():
    """§4.3.5：计划单据号取自**人所选那个月**的计划；候选月份 = **库里真有的计划月份 ＋ 当月**。

    ⚠️ 候选**只列真有数据的月份**（外加当月兜底）—— 列一堆空月份让人点到没东西勾，是另一种烦人。
    """
    pick = act_entry("planPick")
    assert "[...new Set(PLs.map(p=>String(p.ym||'')).filter(Boolean))]" in pick, \
        "候选月份没从真数据（`PLs`）里取"
    assert "[...new Set([bjMonth(),...yms])].sort().reverse()" in pick, "候选里没有当月兜底 / 没按新→旧排"
    assert "data-act=\"planPickSet\"" in pick, "选月份的入口没了"
    assert "data-act=\"planPickOk\"" in pick, "「按所选月份勾选」的确认按钮没了"
    reg = act_entry("planPickRun")
    assert "const plan=PLs.filter(p=>p.ym===ym);" in reg, "没按所选月份过滤计划行"
    assert "PLs" in SHELL and "plans: () => API.get('/api/m04/plans?year_month=')" in SHELL, \
        "计划数据源不是真接口（`/api/m04/plans`）"
