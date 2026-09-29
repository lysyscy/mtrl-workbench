"""`m04`（付款计划）**前端壳接线**断言（离线 · 静态）。

配套：
- 运行时端到端 = `tools/probe/_e2e_m04_wired.py`（真机 ＋ **真库**，跑完清理）
- 结构一致性 = `tools/audit/ui_parity.py`（U1 视图逐行一致 / U2b 已接线页不得留演示数组）

⚠️ **本文件测不了什么**：它是**静态检查**（壳里有没有那些接线点），**不证明运行时真调通**。
   两把都要 —— 这正是「判据绿 ≠ 链路对」的教训。

⭐ 其中四条是**反向**断言：审查结果不许前端自算 · 不许用本地赋值冒充落库 ·
   不许对没接的动作说成功 · 已接线页的**演示数组必须已删**。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛


def _act(name: str, limit: int = 6000) -> str:
    """取 `ACT` 里 `<name>:async ()=>{…}` 的**函数体**（⚠️ 必须**花括号配平**）。

    ⚠️ 别用「起点 + 固定字符数」—— 那是**假绿/假红的温床**：截短了断言看不到要查的代码，
       截长了会**吃进下一个动作**（反向灵敏度实测踩到：`plRowSave` 的 2400 字符窗口
       把后面的 `plRowCancel` 吃了进来 ⇒ 「失败时不许清草稿」这条**误判**）。
    """
    i = SHELL.find(f"{name}:async ()=>{{")
    assert i > 0, f"找不到 `{name}:async ()=>{{`"
    depth, k = 0, SHELL.find("{", i)
    while k < len(SHELL):
        if SHELL[k] == "{":
            depth += 1
        elif SHELL[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    body = SHELL[i:k + 1]
    assert len(body) < limit, f"`{name}` 取到 {len(body)} 字符 —— 配平可能跑偏"
    return body


# --------------------------------------------------------------- 接线点（正向）


@acc()
def test_壳把m04标为已接后端并指向真实端点():
    assert "'m04'" in SHELL and "const WIRED=new Set(" in SHELL
    assert "/api/m04/plans?year_month=" in SHELL
    for fn in ("API.plCell", "API.plRematch", "API.plForce", "API.plForceCancel",
               "API.plDelete", "API.plDeleteImpact"):
        assert fn in SHELL, f"缺写动作接线点：{fn}"


@acc()
def test_付款计划字段在适配层完成转形():
    """后端 `audit_result` / `forced_through` / `is_manual` / 派生两列 → 原型 `PL_COLS` 字段名。"""
    assert "function adaptPlan(x)" in SHELL
    assert "result: x.audit_result" in SHELL
    assert "forced: !!x.forced_through" in SHELL and "manual: !!x.is_manual" in SHELL
    assert "pay_date: 'pay_date'" in SHELL or "PL_COL_API" in SHELL
    # 「项目」列必须保留**用户填报原值**（换成展示名会把「未匹配」这一档抹掉）
    assert "proj: x.project_input || ''" in SHELL


@acc()
def test_写动作统一走后端并以后端为准重拉():
    assert "async function reloadPlans()" in SHELL
    assert "async function plAct(fn, okMsg, ms)" in SHELL
    # 删除走 §4.3.6 两步：先取**后端**影响范围
    assert "await API.plDeleteImpact(ids)" in SHELL


# --------------------------------------------------------------- 反向（不许再出现）


@acc()
def test_审查结果不再由前端自算():
    """唯一出口 = 后端 `domain.audit_rows`（§4.3.4 的 6 种判定）。

    原型原先在浏览器里实时派生（查通知书 ＋ 重复检测）⇒ 那是**第二份口径**。
    """
    assert "const plRev=(p)=>String((p&&p.result)" in SHELL, "`plRev` 没改成读后端"
    assert "if(Number(p.monthAmt)>Number(n.approve)-paidOf(n.id)) return '超过未付';" not in SHELL, \
        "旧的**前端判定**还在 ⇒ 口径有两份"


@acc()
def test_写动作不許用本地赋值冒充落库():
    assert "p[f]=String(t.value" not in SHELL, "行内改列还在改内存"
    assert "p.forced=true" not in SHELL, "强制通过还在改内存"
    assert "PLs.splice(i,1)" not in SHELL, "删除还在改内存"
    assert "plAlert" not in SHELL and "plNextIds('PL',3)" not in SHELL, "旧的造演示行还在"


@acc()
def test_已接线页的演示数组必须已删():
    """`m04` 标了「已接后端」⇒ 演示数组 `PL` 不得残留（产品化红线①）。"""
    assert "const PL = [" not in SHELL
    assert "let PLs=[];" in SHELL


@acc()
def test_导入与手动行已接通():
    """⭐ `TAIL-35` 接线后**改写的断言** —— 旧断言钉的是「**未接通**」这个**临时状态**。

    ⚠️ 改写理由（不是「把绿改红」，是**守的状态变了**）：`TAIL-35` 的定义就是「随 `TAIL-27` 其余页接」，
       现在接了 ⇒ 「必须如实说未接通」这条使命完成。**反向内核保留**：
       ⛔ 不许留任何「说了未接通、却在别处假装成功」的入口（旧的造演示行也仍在禁列）。
    """
    assert "导入尚未接通壳" not in SHELL, "导入还挂着「未接通」提示（已接线）"
    assert "手动行尚未接通壳" not in SHELL, "手动行还挂着「未接通」提示（已接线）"
    # 反向内核（照旧）：不许造演示行冒充成功
    assert "plAlert" not in SHELL and "plNextIds('PL',3)" not in SHELL, "旧的造演示行还在"


@acc()
def test_导入与手动行走后端():
    """⭐ 接线点：导入 = **multipart** → **通用导入面**（`TAIL-69` 三步：解析 → 预览 → 确认）；手动行 = JSON → `/api/m04/plans`。

    ⚠️ 2026-09-22（`TAIL-75` `B5c`）：付款计划**页内弹窗已删**，导入收进「**数据导入**」向导（通用导入面）
       ⇒ **判词一字未改**（"预览不写库、确认才落库"），只把**落点**从 `/api/m04/import/*` 换成
       `/api/imp/m04_plan/*`（域声明见 `mod04_plan/imp_spec.py`）。
       ⚠️ 切片里那个按钮的文案没动（`U1` 零漂移），变的只是它的**动作**（跳到向导并预选本域）。
    """
    assert "impParse: (domain, fd) =>" in SHELL, "通用面的解析没写 multipart 客户端"
    assert "new FormData()" in SHELL, "导入没用 `FormData`（multipart 只能这么传）"
    assert "plImport:async ()=>{ await impSetDomain('m04_plan');" in SHELL, (
        "付款计划页的导入按钮没接到通用向导（也没预选本域）"
    )
    for step in ("API.impParse(", "API.impPreview(", "API.impCommit("):
        assert step in SHELL, f"向导少一步：{step}（预览不写库 → 确认才落库）"
    assert "ACT.impPreview = async () =>" in SHELL and "ACT.impCommit = async () =>" in SHELL, "向导两步动作不在"
    assert "m04PlanSave: body => API.post('/api/m04/plans', body)" in SHELL, (
        "手动行没走 `/api/m04/plans`"
    )
    assert "plRowSave:async ()=>" in SHELL, "`plRowSave` 没改成 async"


@acc()
def test_手动行判据不得在前端复写():
    """⭐ 反向：手动行的校验（年月 / 项目 / 金额）**一律后端**（`plan_manual.manual_row_payload`）。

    前端只把**原值**送上去 —— 复写任何一道 = **第二份口径**（`D18`：判定一律后端）。
    """
    body = _act("plRowSave")
    assert "API.m04PlanSave(" in body, "`plRowSave` 没调后端"
    for bad, why in (
        ("badMoney(", "还在前端复写**金额**校验"),
        ("pjRowOf(d.proj)", "还在前端复写「**项目必选**」"),
    ):
        assert bad not in body, f"`plRowSave` {why}（⇒ 第二份口径）"


@acc()
def test_手动行失败时保留已填内容():
    """§4.3.3.1：**校验失败 ⇒ 保留已填内容**（不清空重填）⇒ 失败分支**不许**清草稿层。"""
    body = _act("plRowSave")
    assert "plRowEditId=''; plD={};" in body, "成功后没清草稿（行已落库，该清）"
    j = body.find("}catch(e){")
    assert j > 0, "`plRowSave` 没有 catch 分支"
    assert "plD={}" not in body[j:], "失败时把草稿清空了（§4.3.3.1 要求**保留已填内容**）"


@acc("ACC-PLAN-MANUAL-001", "001-06")
def test_手动行有徽标_导入行没有():
    """⭐ 判据点**搬家**（`§19` 批 2）：原先钉在**旧服务端页**的 HTML 上（`render_m04` 输出的
    「手动」徽标 ＋ 「编辑」入口只对手动行出现）。旧页整体删除（授权 `D18`）⇒ 改指**新壳**
    （⛔ 判据不删 —— `§19` 铁律：形态变了搬断言）。

    ⚠️ 认法要能**分别看住两种行**：徽标与「编辑」入口**都由 `p.manual` 分支**给出 ——
       ⛔ 不许无条件渲染（那样**导入行也会挂上「手动」**，正是原判据要防的）。
    """
    assert "${p.manual?' <span class=\"tag t-in\"" in SHELL, \
        "手动行徽标没按 `p.manual` 分支渲染 ⇒ 导入行会一起挂上「手动」"
    assert ">手动</span>':''}" in SHELL, "徽标分支没闭合（要么无条件渲染、要么文案与判据对不上了）"
    assert "${p.manual?`<button class=\"btn sm\" data-act=\"plRowEdit\"" in SHELL, \
        "「编辑」入口没按 `p.manual` 分支（§4.3.3.1：只有手动行可编辑）"


@acc()
def test_手动行三个本地动作已恢复原型():
    """⭐ `plRowAdd` / `plRowEdit` 是**本地草稿层**（**不落库**）⇒ 接线后恢复原型实现即可、无需改。"""
    assert "plRowEditId=PL_NEW_ID; plD=plBlank(); render();" in SHELL, "`plRowAdd` 没恢复原型"
    assert "plD={ym:p.ym, proj:plProjKey(p.proj)" in SHELL, "`plRowEdit` 没恢复原型"
    assert "编辑只对「手动行」开放" in SHELL, "「只有手动行可编辑」的提示丢了（§4.3.3.1）"


@acc()
def test_后端两个新端点存在():
    """`TAIL-35` 的后端落点：手动行 JSON 端点 ＋ 导入 multipart 端点。

    ⚠️ 端点**已搬到 `plan_api_router.py`** —— `router.py` 加了这两段后涨到 **668 行 > 600**（禁合入硬线）
       ⇒ 按本仓纪律**拆件**（`router.py` 只留页面端点，用 `include_router` 汇总）。
    ⚠️ 断言必须**进各自函数体**取切片 —— 只写「文件里含 `manual_row_payload(`」是**假绿**
       （反向灵敏度实测：改成 `_` 前缀后照样通过 —— **子串喂饱**）。
    """
    base = Path(__file__).resolve().parents[1] / "app" / "mod04_plan"
    api = (base / "plan_api_router.py").read_text(encoding="utf-8")
    router = (base / "router.py").read_text(encoding="utf-8")
    assert '@router.post("/api/m04/plans")' in api, "后端缺 `POST /api/m04/plans`"
    assert "router.include_router(plan_api_router)" in router, "`router.py` 没汇总 API 路由（端点会 404）"
    # ⚠️ 2026-09-23（`TAIL-75` 余项 · **用户裁定**「只留通用面」）：付款计划的**页内导入面连件删除**
    #    （含 2026-09-22 起已软退役的一步式）⇒ 导入那半的落点改指**通用面**：域声明 `imp_spec.py`。
    #    ⭐ **判词一字未改** —— 还是"落库必须走 `repo.merge_month`（§9.5 幂等）"，只是那件事现在
    #    由域钩子 `imp_spec.commit` 做（通用面调的也是它）。
    imp = (base / "imp_spec.py").read_text(encoding="utf-8")
    for src, fn, needle, why in (
        (api, "def api_plan_row_save(", r"(?<![A-Za-z_])manual_row_payload\(",
         "手动行端点没走 `manual_row_payload`（判定该与 PRG 端点复用**同一出口**）"),
        (imp, "def commit(s, records, mapping_, operator, options):",
         r"(?<![A-Za-z_])repo\.merge_month\(",
         "导入落库没走 `repo.merge_month`（§9.5 幂等就没了）"),
    ):
        i = src.find(fn)
        assert i > 0, f"找不到 `{fn}`（`plan_api_router.py` / `imp_spec.py`）"
        j = src.find("\n@router.", i)                     # 到下一个路由为止（函数体边界）
        body = src[i:j if j > i else i + 2500]
        assert re.search(needle, body), why


# ------------------------- ⭐ `A3` 逐页（`m04` · 2026-09-29）：三处「会让人做错事」的守卫


@acc("ACC-PLAN-UI-001", "001-09")
def test_筛不到行时必须给空态而不是一片空白():
    """守则 §2.1/§5.4：**0 行 ≠ 空白** —— 用户会以为页面坏了、或不知道自己是不是筛过头了。

    ⚠️ 这条是**正向守卫**：本批之前 `V.m04` 的合计行槽位是 `${list.length?sumRowOf(…):''}`
       —— 空串 ⇒ 筛不到时**只剩表头**（同一处槽位 `m03` 给的是 `EMPTYROW`）。
    """
    assert "EMPTYROW(thCount(PL_THEAD),'当前筛选条件下没有付款计划'" in SHELL, \
        "筛不到行时没给空态（守则 §2.1：列表空着不说明下一步）"
    assert "monthAmt,0))}):''}" not in SHELL, "空态被退回空串形态（`${list.length?…:''}`）"
    seg = SHELL.split("EMPTYROW(thCount(PL_THEAD)", 1)[1][:420]
    assert "换个「单据年月 / 项目 / 审查结果」" in seg, "空态没说「怎么回到有数据」（§2.1 下一步）"
    assert "导入付款计划 Excel" in seg, "空态没指出补数据的入口"


@acc("ACC-PLAN-UI-001", "001-10")
def test_删除选中置灰时说明为什么灰():
    """守则 §4.6/§5.5：**置灰必须说明原因**（房内惯例 = 写进 `title`）。

    ⚠️ 实测底数（2026-09-29）：全站 24 处 `disabled` 里 **10 处没有 `title`** ⇒ 本条**只钉本页**；
       全站那 9 处是**跨页**的事（登记在台账），⛔ 别把本条写成"全站凡置灰必须有 title"（会误伤别的页）。
    """
    i = SHELL.find('data-act="plDel"')
    assert i > 0, "找不到「删除选中」"
    seg = SHELL[i:i + 320]
    assert "title=" in seg, "「删除选中」置灰时没给理由（§4.6：灰按钮不给理由）"
    assert "置灰" in seg and "先勾选" in seg, "置灰理由没写清「怎么解锁」"


@acc("ACC-PLAN-UI-001", "001-11")
def test_手动行保存挡重入():
    """守则 §5.5「动作里挡重入」：连点两次「保存」= 两次 `POST /api/m04/plans`。

    ⚠️ 后端**故意不挡**重复 —— 同月完全相同的行是**本业务的合法状态**（§4.3.3：重复由
       「重复上报」提示、不靠自动去重掩盖）⇒ 连点会**静默多一行**，只能由界面挡。
    """
    body = _act("plRowSave")
    assert "if(plSaving) return;" in body, "保存没挡重入（`plRowSave` 里没有 `plSaving` 闸）"
    assert "plSaving=true" in body and "plSaving=false" in body, "挡重入标记没置 / 没复位"
    # ⚠️ 只设一个没人读的标记 = 假守卫：草稿行的按钮必须**真的**变样（禁用 ＋ 文案）
    assert "${plSaving?' disabled':''}" in SHELL, "保存按钮没有跟着禁用"
    assert "保存中…" in SHELL, "保存中没给状态文案（用户会以为没点上）"
